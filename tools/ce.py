#!/usr/bin/env python3
"""ce.py - command-line client for the Content Studio API (standard library only).

The engine never talks to Instagram or Apify directly: everything goes through the
studio Worker at $CE_API_URL. Authentication:

* Cloud routine: set NOTHING. The environment's API credential makes the Anthropic
  agent proxy add ``Authorization: Bearer <engine key>`` to every request for the
  Worker host. The key is never visible inside the session.
* Local development: export CE_ENGINE_KEY and the client sends the header itself.

Every command prints JSON (the ``data`` field of the API envelope) to stdout, or
writes it to ``--out FILE`` (accepted before or after the subcommand) and prints a short
``{"written": FILE}`` line instead. Prefer ``--out`` for anything large. Errors go to stderr with a non-zero exit code:
1 = API / network error, 2 = usage error.

Subcommands
    context                                   brand, prefs, accounts, queued jobs, ...
    jobs [--status queued]                    list jobs
    job-create TYPE [--params JSON]           create a job
    job-update ID [--status S] [--summary-uk T --summary-en T | --summary JSON]
                  [--error MSG] [--session-url URL] [--progress MSG]
    upsert COLLECTION --json FILE|-           upsert items ({items:[..]}, [..] or {..})
    list COLLECTION [--filter k=v ...] [--limit N]
    media-put KEY FILE [--content-type CT]    upload bytes to R2 under KEY
    proxy-get URL FILE                        download an Instagram CDN file via the Worker
    transcribe FILE [--lang uk|en|auto]       Whisper transcription of an audio file
    apify ACTOR --input JSON|@FILE            run an allow-listed Apify actor via the Worker
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

USER_AGENT = "content-studio-engine/1.0"
DEFAULT_TIMEOUT = 60
TIMEOUTS = {"apify": 320, "transcribe": 180, "proxy": 180, "media": 120}
RETRY_STATUSES = {500, 502, 503, 504, 520, 522, 524}
MAX_ATTEMPTS = 3
COLLECTIONS = {
    "accounts", "posts", "breakdowns", "reports", "ideas",
    "scripts", "calendar", "jobs", "learnings",
}
JOB_STATUSES = {"queued", "running", "done", "error"}

Opener = Callable[..., Any]


class ApiError(Exception):
    """Raised when the API returns an error or cannot be reached."""


def base_url() -> str:
    url = os.environ.get("CE_API_URL", "").strip().rstrip("/")
    if not url:
        raise ApiError("CE_API_URL is not set (the studio Worker URL).")
    if not url.startswith("https://") and not url.startswith("http://localhost"):
        raise ApiError("CE_API_URL must be an https:// URL.")
    return url


def build_headers(content_type: str | None = None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    key = os.environ.get("CE_ENGINE_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def build_request(method: str, path: str, *, query: dict[str, Any] | None = None,
                  body: bytes | None = None, content_type: str | None = None,
                  accept_json: bool = True) -> urllib.request.Request:
    url = base_url() + path
    if query:
        clean = {k: v for k, v in query.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)
    headers = build_headers(content_type)
    if not accept_json:
        headers["Accept"] = "*/*"
    return urllib.request.Request(url, data=body, headers=headers, method=method)


def _open_with_retry(req: urllib.request.Request, timeout: int,
                     opener: Opener) -> Any:
    delay = 2.0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return opener(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                exc.close()
                time.sleep(delay)
                delay *= 2
                continue
            raise ApiError(_http_error_message(exc)) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt < MAX_ATTEMPTS:
                time.sleep(delay)
                delay *= 2
                continue
            raise ApiError(f"network error: {getattr(exc, 'reason', exc)}") from None
    raise ApiError("request failed")  # pragma: no cover - loop always returns/raises


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    detail = ""
    try:
        payload = json.loads(exc.read().decode("utf-8", "replace"))
        detail = payload.get("error") or ""
    except (ValueError, AttributeError, OSError):
        detail = ""
    finally:
        exc.close()
    return f"HTTP {exc.code}: {detail or exc.reason}"


def call_json(method: str, path: str, *, payload: Any = None,
              query: dict[str, Any] | None = None, timeout: int = DEFAULT_TIMEOUT,
              opener: Opener = urllib.request.urlopen) -> Any:
    body = None
    ctype = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ctype = "application/json"
    req = build_request(method, path, query=query, body=body, content_type=ctype)
    with _open_with_retry(req, timeout, opener) as resp:
        raw = resp.read().decode("utf-8", "replace")
    try:
        envelope = json.loads(raw) if raw else {}
    except ValueError:
        raise ApiError("API returned non-JSON response") from None
    if isinstance(envelope, dict) and envelope.get("ok") is False:
        raise ApiError(envelope.get("error") or "API error")
    return envelope.get("data") if isinstance(envelope, dict) and "data" in envelope else envelope


def call_bytes_out(path: str, out: Path, *, query: dict[str, Any] | None = None,
                   timeout: int = TIMEOUTS["proxy"],
                   opener: Opener = urllib.request.urlopen) -> int:
    req = build_request("GET", path, query=query, accept_json=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with _open_with_retry(req, timeout, opener) as resp, out.open("wb") as fh:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
            size += len(chunk)
    return size


def call_bytes_in(method: str, path: str, data: bytes, content_type: str, *,
                  query: dict[str, Any] | None = None, timeout: int = DEFAULT_TIMEOUT,
                  opener: Opener = urllib.request.urlopen) -> Any:
    req = build_request(method, path, query=query, body=data, content_type=content_type)
    with _open_with_retry(req, timeout, opener) as resp:
        raw = resp.read().decode("utf-8", "replace")
    try:
        envelope = json.loads(raw) if raw else {}
    except ValueError:
        raise ApiError("API returned non-JSON response") from None
    if isinstance(envelope, dict) and envelope.get("ok") is False:
        raise ApiError(envelope.get("error") or "API error")
    return envelope.get("data") if isinstance(envelope, dict) and "data" in envelope else envelope


# ---------------------------------------------------------------- helpers

def load_json_arg(value: str) -> Any:
    """Accept inline JSON, @file, a file path, or '-' for stdin."""
    if value == "-":
        return json.load(sys.stdin)
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text(encoding="utf-8"))
    candidate = Path(value)
    if not value.lstrip().startswith(("{", "[")) and candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def as_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    elif isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = [payload]
    else:
        raise ValueError("upsert payload must be an object, a list, or {items:[...]}")
    if not all(isinstance(i, dict) for i in items):
        raise ValueError("every upsert item must be a JSON object")
    return items


def parse_filters(pairs: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"filter must be key=value, got {pair!r}")
        key, val = pair.split("=", 1)
        out[key.strip()] = val.strip()
    return out


def check_collection(name: str) -> str:
    if name not in COLLECTIONS:
        raise ValueError(f"unknown collection {name!r}; one of {sorted(COLLECTIONS)}")
    return name


def summary_from_args(args: argparse.Namespace) -> Any:
    if getattr(args, "summary", None):
        return load_json_arg(args.summary)
    uk, en = getattr(args, "summary_uk", None), getattr(args, "summary_en", None)
    if uk or en:
        return {k: v for k, v in (("uk", uk), ("en", en)) if v}
    return None


# ---------------------------------------------------------------- commands

def cmd_context(args: argparse.Namespace) -> Any:
    return call_json("GET", "/api/engine/context")


def cmd_jobs(args: argparse.Namespace) -> Any:
    return call_json("GET", "/api/engine/jobs", query={"status": args.status})


def cmd_job_create(args: argparse.Namespace) -> Any:
    params = load_json_arg(args.params) if args.params else {}
    return call_json("POST", "/api/engine/jobs", payload={"type": args.type, "params": params})


def cmd_job_update(args: argparse.Namespace) -> Any:
    patch: dict[str, Any] = {}
    if args.status:
        if args.status not in JOB_STATUSES:
            raise ValueError(f"status must be one of {sorted(JOB_STATUSES)}")
        patch["status"] = args.status
    summary = summary_from_args(args)
    if summary is not None:
        patch["summary"] = summary
    for field in ("error", "session_url", "progress"):
        value = getattr(args, field)
        if value:
            patch[field] = value
    if not patch:
        raise ValueError("job-update needs at least one field")
    job_id = urllib.parse.quote(args.id, safe="")
    return call_json("POST", f"/api/engine/jobs/{job_id}", payload=patch)


def cmd_upsert(args: argparse.Namespace) -> Any:
    collection = check_collection(args.collection)
    items = as_items(load_json_arg(args.json))
    results = []
    for start in range(0, len(items), 50):
        batch = items[start:start + 50]
        results.append(call_json("POST", f"/api/engine/upsert/{collection}",
                                 payload={"items": batch}))
    count = sum(int((r or {}).get("count", 0)) for r in results if isinstance(r, dict))
    return {"collection": collection, "count": count, "batches": len(results)}


def cmd_list(args: argparse.Namespace) -> Any:
    collection = check_collection(args.collection)
    query: dict[str, Any] = parse_filters(args.filter)
    if args.limit:
        query["limit"] = args.limit
    return call_json("GET", f"/api/engine/list/{collection}", query=query)


def cmd_media_put(args: argparse.Namespace) -> Any:
    path = Path(args.file)
    ctype = args.content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    key = urllib.parse.quote(args.key, safe="/")
    return call_bytes_in("PUT", f"/api/engine/media/{key}", path.read_bytes(), ctype,
                         timeout=TIMEOUTS["media"])


def cmd_proxy_get(args: argparse.Namespace) -> Any:
    size = call_bytes_out("/api/engine/proxy", Path(args.target), query={"url": args.url})
    return {"file": args.target, "bytes": size}


def cmd_transcribe(args: argparse.Namespace) -> Any:
    path = Path(args.file)
    ctype = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    return call_bytes_in("POST", "/api/engine/transcribe", path.read_bytes(), ctype,
                         query={"lang": args.lang}, timeout=TIMEOUTS["transcribe"])


def cmd_apify(args: argparse.Namespace) -> Any:
    payload = {"actor": args.actor, "input": load_json_arg(args.input)}
    return call_json("POST", "/api/engine/apify", payload=payload, timeout=TIMEOUTS["apify"])


class _Sub:
    """Adds the shared --out option to every subcommand."""

    def __init__(self, subparsers: Any, common: argparse.ArgumentParser) -> None:
        self._subparsers = subparsers
        self._common = common

    def add_parser(self, name: str) -> argparse.ArgumentParser:
        return self._subparsers.add_parser(name, parents=[self._common])


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ce.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write the JSON result to this file instead of stdout")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", default=argparse.SUPPRESS,
                        help="write the JSON result to this file instead of stdout")
    sub = _Sub(ap.add_subparsers(dest="command", required=True), common)

    sub.add_parser("context").set_defaults(func=cmd_context)

    p = sub.add_parser("jobs")
    p.add_argument("--status", default="queued")
    p.set_defaults(func=cmd_jobs)

    p = sub.add_parser("job-create")
    p.add_argument("type")
    p.add_argument("--params")
    p.set_defaults(func=cmd_job_create)

    p = sub.add_parser("job-update")
    p.add_argument("id")
    p.add_argument("--status")
    p.add_argument("--summary", help="JSON {uk,en} or @file")
    p.add_argument("--summary-uk")
    p.add_argument("--summary-en")
    p.add_argument("--error")
    p.add_argument("--session-url", dest="session_url")
    p.add_argument("--progress")
    p.set_defaults(func=cmd_job_update)

    p = sub.add_parser("upsert")
    p.add_argument("collection")
    p.add_argument("--json", required=True, help="file path, @file, inline JSON or '-'")
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("list")
    p.add_argument("collection")
    p.add_argument("--filter", action="append")
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("media-put")
    p.add_argument("key")
    p.add_argument("file")
    p.add_argument("--content-type")
    p.set_defaults(func=cmd_media_put)

    p = sub.add_parser("proxy-get")
    p.add_argument("url")
    p.add_argument("target", help="local file to write")
    p.set_defaults(func=cmd_proxy_get)

    p = sub.add_parser("transcribe")
    p.add_argument("file")
    p.add_argument("--lang", default="auto", choices=["uk", "en", "auto"])
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("apify")
    p.add_argument("actor")
    p.add_argument("--input", required=True)
    p.set_defaults(func=cmd_apify)
    return ap


def emit(result: Any, out: str | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        size = len(result) if isinstance(result, (list, dict)) else 1
        print(json.dumps({"written": out, "size": size}))
    else:
        sys.stdout.write(text + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit(args.func(args), args.out)
    except (ValueError, OSError) as exc:
        print(f"ce.py: {exc}", file=sys.stderr)
        return 2
    except ApiError as exc:
        print(f"ce.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
