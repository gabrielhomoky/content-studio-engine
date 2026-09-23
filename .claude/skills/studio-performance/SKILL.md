---
name: studio-performance
description: Closes the loop for the Content Studio. Checks posts the client published from studio scripts, measures them against her own median, stores the performance on the script and writes learnings that future ideas and scripts must use. Use for `performance` jobs and at the end of `weekly`.
---

# studio-performance — did it work, and what do we learn

1. `context.scripts_to_check` = scripts with status `posted`, a `posted_url`, and no
   performance or a check older than 7 days. Nothing to check → skip quietly.
2. Scrape them in one call:
   ```bash
   python3 tools/ce.py apify apify~instagram-scraper \
     --input '{"directUrls": [...posted urls], "resultsType": "posts", "resultsLimit": 1}' \
     --out work/perf/raw.json
   python3 tools/normalize.py posts work/perf/raw.json work/perf/posts.json
   ```
3. Her median = the own account's `stats.median_likes` from `context.accounts`
   (role `own`). `vs_median` = likes ÷ median, one decimal. Posts younger than 48 h are
   marked as early (note in the learning, do not over-interpret).
4. Upsert each script: `{"id", "performance": {"likes", "comments", "views", "vs_median",
   "checked_at"}}` (observed numbers only).
5. Learnings (bilingual `insight`, concrete `evidence`): what beat her median and what did
   not, compared with the idea's score and pattern. One learning per real signal; do not
   restate the same insight every week. These learnings feed `studio-ideas` and
   `studio-scripts` next time.
   ```bash
   python3 tools/ce.py upsert learnings --json work/perf/learnings.json
   ```
