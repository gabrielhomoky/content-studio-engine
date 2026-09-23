#!/usr/bin/env python3
"""media.py - fetch and prepare post media for analysis (stdlib + ffmpeg).

For each picked post it:
  * reels:     downloads the mp4 through the Worker proxy, extracts keyframes
               (0.5 s, then every ~3 s, max 6, 720 px wide) and a mono 16 kHz mp3,
               sends the mp3 to the Worker's Whisper endpoint for a transcript
  * carousels: downloads up to 10 slide images
  * images:    downloads the image
then uploads the frames/slides to the studio media store (so the UI can show them)
and writes ``<out>/<id>/manifest.json``. Every step degrades gracefully: failures are
recorded in ``errors`` and never abort the batch.

    python3 tools/media.py all  picks.json --out work/media [--lang en]
    python3 tools/media.py pick picks.json --id SHORTCODE --out work/media
Options: --no-upload, --no-transcribe, --max-slides N
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ce  # noqa: E402  (sibling module)

FIRST_FRAME_AT = 0.5
FRAME_EVERY = 3.0
MAX_FRAMES = 6
FRAME_WIDTH = 720
MAX_SLIDES = 10
POST_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
MIN_SPEECH_CHARS = 40
# Whisper invents these on music-only or silent audio.
HALLUCINATIONS = ("thank you", "thanks for watching", "subscribe", "you", "music", "дякую",
                  "спасибо", "продолжение следует", "gracias")


def safe_post_id(raw: Any) -> str:
    """Scraped ids become directory names: allow only a conservative shortcode alphabet."""
    post_id = str(raw or "")
    if not POST_ID_RE.match(post_id) or post_id in {".", ".."}:
        raise ValueError(f"unsafe post id: {post_id[:40]!r}")
    return post_id


def clean_transcript(text: str | None) -> str | None:
    """Return None for music-only / no-speech audio (too short or a known Whisper hallucination)."""
    t = (text or "").strip()
    if len(t) < MIN_SPEECH_CHARS:
        return None
    core = re.sub(r"[^\w\s]", " ", t.lower())
    words = set(core.split())
    phrases = [h for h in HALLUCINATIONS if h in core]
    if phrases and len(words) <= 8:
        return None
    return t


def keyframe_times(duration: float | None, first: float = FIRST_FRAME_AT,
                   every: float = FRAME_EVERY, max_frames: int = MAX_FRAMES) -> list[float]:
    if not duration or duration <= first:
        return [first]
    times, t = [], first
    while t < duration and len(times) < max_frames:
        times.append(round(t, 2))
        t = first + every * len(times)
    return times


def probe_cmd(video: str) -> list[str]:
    return ["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video]


def keyframe_cmd(video: str, at: float, out: str, width: int = FRAME_WIDTH) -> list[str]:
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{at}", "-i", video, "-frames:v", "1",
            "-vf", f"scale={width}:-2", "-q:v", "4", out]


def audio_cmd(video: str, out: str) -> list[str]:
    return ["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
            "-b:a", "48k", out]


def run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)


def have_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def video_duration(video: str) -> float | None:
    try:
        return float(run(probe_cmd(video), timeout=30).stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def extract_frames(video: Path, outdir: Path) -> list[Path]:
    frames = []
    for i, at in enumerate(keyframe_times(video_duration(str(video))), 1):
        target = outdir / f"frame_{i:02d}.jpg"
        run(keyframe_cmd(str(video), at, str(target)))
        if target.exists():
            frames.append(target)
    return frames


def extract_audio(video: Path, outdir: Path) -> Path:
    target = outdir / "audio.mp3"
    run(audio_cmd(str(video), str(target)), timeout=180)
    return target


def download(url: str | None, target: Path) -> Path | None:
    if not url:
        return None
    ce.call_bytes_out("/api/engine/proxy", target, query={"url": url})
    return target if target.exists() and target.stat().st_size > 0 else None


def upload(files: list[Path], prefix: str) -> list[str]:
    keys = []
    for i, path in enumerate(files, 1):
        key = f"{prefix}/{i:02d}.jpg"
        ce.call_bytes_in("PUT", f"/api/engine/media/{key}", path.read_bytes(), "image/jpeg",
                         timeout=ce.TIMEOUTS["media"])
        keys.append(key)
    return keys


def step(errors: list[str], label: str, fn: Any, *args: Any) -> Any:
    try:
        return fn(*args)
    except (ce.ApiError, subprocess.SubprocessError, OSError, ValueError) as exc:
        errors.append(f"{label}: {exc}")
        return None


def process_reel(post: dict[str, Any], workdir: Path, manifest: dict[str, Any],
                 transcribe: bool, lang: str) -> list[Path]:
    errors = manifest["errors"]
    if not have_ffmpeg():
        errors.append("ffmpeg not installed: run bash tools/setup.sh")
        thumb = step(errors, "thumb", download, post.get("thumb_url"), workdir / "thumb.jpg")
        return [thumb] if thumb else []
    video = step(errors, "video", download, post.get("video_url"), workdir / "video.mp4")
    if not video:
        thumb = step(errors, "thumb", download, post.get("thumb_url"), workdir / "thumb.jpg")
        return [thumb] if thumb else []
    frames = step(errors, "frames", extract_frames, video, workdir) or []
    if transcribe:
        audio = step(errors, "audio", extract_audio, video, workdir)
        if audio:
            result = step(errors, "transcribe", transcribe_file, audio, lang)
            if isinstance(result, dict):
                text = clean_transcript(result.get("text"))
                manifest["transcript"] = text
                manifest["language"] = result.get("language")
                if text is None:
                    manifest["speech"] = "music only / no speech"
    step(errors, "cleanup", video.unlink)
    return frames


def transcribe_file(audio: Path, lang: str) -> Any:
    return ce.call_bytes_in("POST", "/api/engine/transcribe", audio.read_bytes(), "audio/mpeg",
                            query={"lang": lang}, timeout=ce.TIMEOUTS["transcribe"])


def process_slides(post: dict[str, Any], workdir: Path, manifest: dict[str, Any],
                   max_slides: int) -> list[Path]:
    urls = list(post.get("slide_urls") or []) or [post.get("thumb_url")]
    files = []
    for i, url in enumerate(urls[:max_slides], 1):
        got = step(manifest["errors"], f"slide {i}", download, url, workdir / f"slide_{i:02d}.jpg")
        if got:
            files.append(got)
    return files


def process_post(post: dict[str, Any], out: Path, *, upload_media: bool = True,
                 transcribe: bool = True, lang: str = "auto",
                 max_slides: int = MAX_SLIDES) -> dict[str, Any]:
    post_id = safe_post_id(post.get("id"))
    workdir = out / post_id
    workdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"id": post_id, "type": post.get("type"), "files": [],
                                "media_keys": [], "transcript": None, "errors": []}
    if post.get("type") == "reel":
        files = process_reel(post, workdir, manifest, transcribe, lang)
        prefix = f"frames/{post_id}"
    else:
        files = process_slides(post, workdir, manifest, max_slides)
        prefix = f"slides/{post_id}"
    manifest["files"] = [str(f) for f in files]
    if upload_media and files:
        manifest["media_keys"] = step(manifest["errors"], "upload", upload, files, prefix) or []
    (workdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    return manifest


def load_posts(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("items") or data.get("picks") or []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["all", "pick"])
    ap.add_argument("posts")
    ap.add_argument("--id")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="auto", choices=["uk", "en", "auto"])
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--max-slides", type=int, default=MAX_SLIDES)
    args = ap.parse_args(argv)
    try:
        posts = load_posts(args.posts)
    except (OSError, ValueError) as exc:
        print(f"media.py: {exc}", file=sys.stderr)
        return 2
    if args.mode == "pick":
        posts = [p for p in posts if str(p.get("id")) == args.id]
        if not posts:
            print(f"media.py: id {args.id!r} not found", file=sys.stderr)
            return 2
    out = Path(args.out)
    summary = {}
    for post in posts:
        try:
            safe_post_id(post.get("id"))
        except ValueError as exc:
            print(f"media.py: skipped: {exc}", file=sys.stderr)
            continue
        manifest = process_post(post, out, upload_media=not args.no_upload,
                                transcribe=not args.no_transcribe, lang=args.lang,
                                max_slides=args.max_slides)
        summary[manifest["id"]] = {"files": len(manifest["files"]),
                                   "transcript": bool(manifest["transcript"]),
                                   "errors": manifest["errors"]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifests.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
