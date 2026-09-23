#!/usr/bin/env python3
"""normalize.py - turn raw Apify Instagram items into studio records (stdlib only).

Invents nothing: any field the scraper did not return stays ``None``.

    python3 tools/normalize.py posts   raw-posts.json    posts.json
    python3 tools/normalize.py profile raw-profiles.json accounts.json [--role competitor]

``posts`` output: a list of post dicts shaped like the ``posts`` collection plus
transient media fields (``video_url``, ``slide_urls``) used locally for media work.
Use ``--upsert-ready`` to drop the transient fields before sending to the API.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TRANSIENT_FIELDS = ("video_url", "slide_urls")
SHORTCODE_RE = re.compile(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")


def first(d: Any, keys: list[str]) -> Any:
    if not isinstance(d, dict):
        return None
    for key in keys:
        value = d.get(key)
        if value not in (None, ""):
            return value
    return None


def nested(d: Any, path: list[str]) -> Any:
    cur = d
    for part in path:
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def handle_of(item: dict[str, Any]) -> str | None:
    raw = (first(item, ["ownerUsername", "username", "handle"])
           or nested(item, ["owner", "username"]) or nested(item, ["user", "username"]))
    return str(raw).strip().lstrip("@").lower() if raw else None


def url_of(item: dict[str, Any]) -> str | None:
    url = first(item, ["url", "postUrl", "permalink", "link"])
    if url:
        return str(url)
    code = first(item, ["shortCode", "shortcode", "code"])
    return f"https://www.instagram.com/p/{code}/" if code else None


def shortcode_of(item: dict[str, Any]) -> str | None:
    code = first(item, ["shortCode", "shortcode", "code"])
    if code:
        return str(code)
    url = url_of(item) or first(item, ["inputUrl"]) or ""
    match = SHORTCODE_RE.search(str(url))
    return match.group(1) if match else None


def comments_of(item: dict[str, Any]) -> int | None:
    value = first(item, ["commentsCount", "comments", "commentCount"])
    if isinstance(value, list):
        return None  # a list of comment objects is a sample, not the count
    if value is None:
        value = nested(item, ["edge_media_to_comment", "count"])
    return to_int(value)


def views_of(item: dict[str, Any]) -> int | None:
    return to_int(first(item, ["videoPlayCount", "videoViewCount", "views", "playCount",
                               "igPlayCount", "viewsCount"]))


def image_of(item: Any) -> str | None:
    return first(item, ["displayUrl", "imageUrl", "thumbnailUrl", "displayUri", "thumbnailSrc"])


def slides_of(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    children = first(item, ["childPosts", "children", "sidecarItems"])
    if isinstance(children, list):
        for child in children:
            node = child.get("node", child) if isinstance(child, dict) else None
            img = image_of(node)
            if img:
                urls.append(str(img))
    images = item.get("images")
    if isinstance(images, list):
        for img in images:
            url = img if isinstance(img, str) else image_of(img)
            if url:
                urls.append(str(url))
    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def type_of(item: dict[str, Any], slides: list[str]) -> str:
    raw = str(first(item, ["productType", "type", "typeName", "__typename"]) or "").lower()
    if any(k in raw for k in ("clip", "reel", "video", "igtv")):
        return "reel"
    if any(k in raw for k in ("sidecar", "carousel", "album")) or len(slides) > 1:
        return "carousel"
    if first(item, ["videoUrl"]):
        return "reel"
    return "image"


def music_of(item: dict[str, Any]) -> str | None:
    info = item.get("musicInfo")
    if isinstance(info, dict):
        artist = info.get("artist_name") or ""
        song = info.get("song_name") or ""
        label = " - ".join(part for part in (artist, song) if part)
        return label or None
    return None


def normalize_post(item: dict[str, Any]) -> dict[str, Any] | None:
    code = shortcode_of(item)
    handle = handle_of(item)
    if not code or not handle:
        return None
    slides = slides_of(item)
    caption = first(item, ["caption", "text", "title"])
    return {
        "id": code,
        "handle": handle,
        "url": url_of(item) or f"https://www.instagram.com/p/{code}/",
        "type": type_of(item, slides),
        "caption": str(caption).strip() if caption else None,
        "likes": to_int(first(item, ["likesCount", "likes", "likeCount"])),
        "comments": comments_of(item),
        "views": views_of(item),
        "posted_at": first(item, ["timestamp", "takenAt", "date"]),
        "pinned": bool(first(item, ["isPinned", "pinned", "is_pinned"]) or False),
        "music": music_of(item),
        "thumb_url": image_of(item),
        "video_url": first(item, ["videoUrl", "video_url"]),
        "slide_urls": slides,
    }


def normalize_posts(items: list[Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("error"):
            continue
        post = normalize_post(item)
        if post and post["id"] not in seen:
            seen.add(post["id"])
            out.append(post)
    return out


def normalize_profile(item: dict[str, Any], role: str = "competitor") -> dict[str, Any] | None:
    handle = handle_of(item)
    if not handle:
        return None
    return {
        "handle": handle,
        "role": role,
        "name": first(item, ["fullName", "full_name", "name"]),
        "followers": to_int(first(item, ["followersCount", "followers"])),
        "following": to_int(first(item, ["followsCount", "following"])),
        "posts_count": to_int(first(item, ["postsCount", "mediaCount"])),
        "bio": first(item, ["biography", "bio"]),
        "category": first(item, ["businessCategoryName", "categoryName"]),
        "external_url": first(item, ["externalUrl", "external_url"]),
        "avatar_url": first(item, ["profilePicUrlHD", "profilePicUrl"]),
        "verified": bool(item.get("verified") or False),
    }


def strip_transient(post: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in post.items() if k not in TRANSIENT_FIELDS}


def load_items(path: Path) -> list[Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("items", "data", "posts", "results"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("input must be a JSON array or an object wrapping one")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["posts", "profile"])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--role", default="competitor", choices=["own", "competitor"])
    ap.add_argument("--upsert-ready", action="store_true")
    args = ap.parse_args(argv)
    try:
        items = load_items(Path(args.input))
    except (OSError, ValueError) as exc:
        print(f"normalize.py: {exc}", file=sys.stderr)
        return 2
    if args.kind == "posts":
        records = normalize_posts(items)
        if args.upsert_ready:
            records = [strip_transient(p) for p in records]
    else:
        records = [r for r in (normalize_profile(i, args.role) for i in items
                               if isinstance(i, dict)) if r]
    Path(args.output).write_text(json.dumps(records, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    missing_likes = sum(1 for r in records if args.kind == "posts" and r["likes"] is None)
    print(json.dumps({"written": args.output, "count": len(records),
                      "missing_likes": missing_likes}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
