# Content Studio Engine

The thinking half of a private Instagram content studio for interior designers. It runs as a
[Claude Code cloud routine](https://code.claude.com/docs/en/routines) on the studio owner's
own Claude subscription and talks only to the studio's web API.

What one run does, depending on the queued job:

- **Audit** the owner's account: medians, per-post breakout, pillars, voice, gaps, profile fixes.
- **Research** competitors: scrape, rank by size-normalized breakout (post likes ÷ that
  creator's median), pull frames/slides/transcripts, reverse-engineer each breakout, mine
  patterns and gaps.
- **Ideas** scored with a 7-factor viral scorecard, tied to observed breakouts.
- **Scripts**: reel and carousel scripts with hook, timed beats, a phone shot list, captions
  and hashtags, in Ukrainian or English.
- **Calendar**, **performance tracking** of what was posted, and **learnings** that feed the
  next run.

It never invents a metric: numbers are observed or `null`.

## How the routine uses it

1. The routine clones this repository. A SessionStart hook installs `ffmpeg`.
2. The routine prompt tells Claude to follow `CLAUDE.md`: read `job:<id>` from the fire
   payload (nothing else), then process every queued job through the matching skill in
   `.claude/skills/`.
3. All reads/writes go through `tools/ce.py` to `$CE_API_URL`. Instagram and Apify are
   reached through the studio Worker's proxy endpoints.

## Environment requirements (set once in the Claude cloud environment)

| Setting | Value |
|---|---|
| Environment variable | `CE_API_URL=https://<your studio host>` |
| API credential | host = your studio host, header `Authorization: Bearer <engine key>` |
| Network access | Trusted (default) is enough |

For local development, export `CE_API_URL` and `CE_ENGINE_KEY`.

## Development

```bash
python3 -m unittest discover -s tests -t .
```
Tools are standard-library Python 3.10+. `tools/media.py` needs `ffmpeg`/`ffprobe`.

MIT licensed.
