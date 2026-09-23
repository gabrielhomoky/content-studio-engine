---
name: studio-weekly
description: The full weekly cycle of the Content Studio: own-account audit refresh, competitor research with breakdowns and patterns, fresh scored ideas, scripts for the top ideas, strategy refresh, a 7-day calendar, a performance check of posted content and learnings. Use for `weekly` jobs (manual button or the scheduled run).
---

# studio-weekly — one run, a full week of content

Run the stages in order. After each stage send a progress message
(`python3 tools/ce.py job-update <job> --progress "…"`). If a stage fails, record the error
in a progress message and continue with the next stage when it can still produce value;
the final summary lists what was skipped.

1. **Audit** (`studio-audit`) if the latest audit is missing or older than 6 days;
   otherwise reuse it.
2. **Performance** (`studio-performance`) so this week's ideas learn from last week's posts.
3. **Research** (`studio-research`, steps 1-6).
4. **Ideas** (`studio-ideas`, count 10, respecting cadence).
5. **Strategy** (`studio-ideas` strategy section) if missing or older than 28 days.
6. **Scripts** (`studio-scripts`) for the top 3 ideas by score with status `new` or
   `approved`, language per the script rules. At least one reel and, if cadence includes
   carousels, one carousel.
7. **Calendar** for the next 7 days: read existing entries
   (`python3 tools/ce.py list calendar --limit 60`), never overwrite them; fill empty slots
   to match `prefs.cadence` (reels on the best-performing days if the audit shows a
   pattern, else Tue/Thu/Sat pm; carousels Mon/Wed am). Scripts first, then top ideas.
   Each entry gets a short bilingual `note` (what to film/prepare).
8. **Summary** (bilingual, 4-6 sentences, plain language): what changed in her account,
   the single most important pattern of the week, the top 3 things to post and why, what
   she must film this week.
