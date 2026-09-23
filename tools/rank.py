#!/usr/bin/env python3
"""rank.py - size-normalized breakout ranking + account stats (stdlib only).

breakout = post likes / the creator's MEDIAN likes (pinned posts excluded from the
median, because pinned posts are cumulative, not recent). A small creator's post at
20x their own median beats a big creator's post at 1.2x. Nothing is invented: a post
without a like count gets ``breakout = None`` and ``confidence = "none"``.

    python3 tools/rank.py annotate posts.json annotated.json
    python3 tools/rank.py select   posts.json picks.json --top-per-handle 3 --pool 15
    python3 tools/rank.py stats    posts.json stats.json [--accounts accounts.json]

Input: a list of normalized posts (tools/normalize.py output).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIN_SAMPLE = 6
HIGH_BREAKOUT = 3.0


def parse_time(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def median_or_none(values: list[int]) -> float | None:
    return float(statistics.median(values)) if values else None


def group_by_handle(posts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        groups.setdefault(post.get("handle") or "unknown", []).append(post)
    return groups


def within_window(posts: list[dict[str, Any]], days: int | None,
                  now: datetime | None = None) -> list[dict[str, Any]]:
    if not days:
        return list(posts)
    now = now or datetime.now(timezone.utc)
    kept = []
    for post in posts:
        ts = parse_time(post.get("posted_at"))
        if ts is None or (now - ts).days <= days:
            kept.append(post)
    return kept


def confidence_for(breakout: float | None, sample: int, min_sample: int) -> str:
    if breakout is None:
        return "none"
    if sample < min_sample:
        return "low"
    return "high" if breakout >= HIGH_BREAKOUT else "medium"


def annotate(posts: list[dict[str, Any]], min_sample: int = MIN_SAMPLE) -> list[dict[str, Any]]:
    """Return copies of posts with median_likes, breakout and confidence per handle."""
    out: list[dict[str, Any]] = []
    for items in group_by_handle(posts).values():
        base = [p["likes"] for p in items if p.get("likes") is not None and not p.get("pinned")]
        median = median_or_none(base)
        for post in items:
            likes = post.get("likes")
            breakout = round(likes / median, 1) if likes is not None and median else None
            out.append({**post, "median_likes": median, "breakout": breakout,
                        "confidence": confidence_for(breakout, len(base), min_sample)})
    return out


def select(posts: list[dict[str, Any]], top_per_handle: int = 3, pool: int = 15,
           min_sample: int = MIN_SAMPLE, include_pinned: bool = False) -> list[dict[str, Any]]:
    """Top N per handle by breakout, pooled, ranked, cut to ``pool`` picks."""
    annotated = annotate(posts, min_sample)
    candidates: list[dict[str, Any]] = []
    for items in group_by_handle(annotated).values():
        eligible = [p for p in items if include_pinned or not p.get("pinned")]
        eligible.sort(key=lambda p: (p["breakout"] is not None, p["breakout"] or 0,
                                     p.get("likes") or 0), reverse=True)
        candidates.extend(eligible[:top_per_handle])
    candidates.sort(key=lambda p: (p["breakout"] is not None, p["breakout"] or 0,
                                   p.get("likes") or 0), reverse=True)
    picks = candidates[:pool]
    return [{**p, "rank": i, "is_pick": True} for i, p in enumerate(picks, 1)]


def posts_per_week(items: list[dict[str, Any]]) -> float | None:
    stamps = sorted(t for t in (parse_time(p.get("posted_at")) for p in items
                                if not p.get("pinned")) if t)
    if len(stamps) < 2:
        return None
    span_days = max((stamps[-1] - stamps[0]).total_seconds() / 86400, 1.0)
    return round((len(stamps) - 1) / span_days * 7, 2)


def share(items: list[dict[str, Any]], kind: str) -> float | None:
    if not items:
        return None
    return round(sum(1 for p in items if p.get("type") == kind) / len(items), 2)


def handle_stats(items: list[dict[str, Any]], followers: int | None = None) -> dict[str, Any]:
    recent = [p for p in items if not p.get("pinned")]
    likes = [p["likes"] for p in recent if p.get("likes") is not None]
    comments = [p["comments"] for p in recent if p.get("comments") is not None]
    views = [p["views"] for p in recent if p.get("views") is not None]
    med_likes, med_comments = median_or_none(likes), median_or_none(comments)
    er = None
    if followers and med_likes is not None:
        er = round((med_likes + (med_comments or 0)) / followers * 100, 2)
    stamps = [t for t in (parse_time(p.get("posted_at")) for p in items) if t]
    return {
        "median_likes": med_likes,
        "median_comments": med_comments,
        "median_views": median_or_none(views),
        "reel_share": share(recent, "reel"),
        "carousel_share": share(recent, "carousel"),
        "posts_per_week": posts_per_week(items),
        "er_pct": er,
        "last_post_at": max(stamps).isoformat().replace("+00:00", "Z") if stamps else None,
        "sample_size": len(likes),
    }


def stats(posts: list[dict[str, Any]], followers: dict[str, int] | None = None) -> dict[str, Any]:
    followers = followers or {}
    return {handle: handle_stats(items, followers.get(handle))
            for handle, items in group_by_handle(posts).items()}


def load_list(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items") or data.get("posts") or data.get("picks") or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["annotate", "select", "stats"])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--top-per-handle", type=int, default=3)
    ap.add_argument("--pool", type=int, default=15)
    ap.add_argument("--min-sample", type=int, default=MIN_SAMPLE)
    ap.add_argument("--window-days", type=int, default=0)
    ap.add_argument("--include-pinned", action="store_true")
    ap.add_argument("--accounts", help="accounts JSON (for followers → er_pct)")
    args = ap.parse_args(argv)
    try:
        posts = within_window(load_list(args.input), args.window_days)
        if args.mode == "annotate":
            result: Any = annotate(posts, args.min_sample)
        elif args.mode == "select":
            result = select(posts, args.top_per_handle, args.pool, args.min_sample,
                            args.include_pinned)
        else:
            followers = {}
            if args.accounts:
                followers = {a["handle"]: a.get("followers") for a in load_list(args.accounts)
                             if a.get("handle")}
            result = stats(posts, followers)
    except (OSError, ValueError) as exc:
        print(f"rank.py: {exc}", file=sys.stderr)
        return 2
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    line = {"written": args.output, "count": len(result)}
    if args.mode == "select" and result:
        top = result[0]
        line["top"] = f"@{top['handle']} {top['breakout']}x" if top["breakout"] else "n/a"
        line["handles"] = len({p["handle"] for p in result})
    print(json.dumps(line, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
