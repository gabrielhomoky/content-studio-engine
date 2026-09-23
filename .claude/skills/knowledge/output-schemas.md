# Output schemas — what the studio API accepts

Every write goes through `python3 tools/ce.py upsert <collection> --json <file>`.
The Worker validates required fields and shallow-merges into existing rows, so you can
send partial updates for an existing `id`. Write JSON files to `work/` (gitignored).

## Localized text `T`

`T = string | {"uk": "...", "en": "..."}`. For every user-facing analysis text, write an
object with one key per language in `context.prefs.analysis_langs` (default both). Write
each language natively, not as a literal translation. Machine values (enums, ids, handles,
metrics) are never localized. Quotes from posts stay in the original language.

## Metrics rule

Every number is OBSERVED (copied from scraped data or computed by `tools/rank.py`) or it is
`null`. Never estimate likes, views, followers, dates or multipliers.

## accounts (id = handle, lowercase, no @)

```json
{"handle": "studio.x", "role": "competitor", "tier": "mid", "name": "Studio X",
 "country": "UK", "followers": 84000, "following": 900, "posts_count": 1200,
 "bio": "...", "category": "Interior Designer", "external_url": "https://...",
 "why": {"uk": "...", "en": "..."}, "active": true,
 "stats": {"median_likes": 850, "median_comments": 30, "median_views": 21000,
           "reel_share": 0.6, "carousel_share": 0.3, "posts_per_week": 3.1,
           "er_pct": 1.05, "last_post_at": "2026-09-20T10:00:00Z", "sample_size": 28},
 "avatar_url": "https://...cdninstagram.com/..."}
```
Required: `handle`, `role`. `tier`: `mega` | `mid` | `closest` | null. `avatar_url` is fetched and
stored by the Worker (it sets `avatar_key`). Own handles use `role: "own"`, `tier: null`.

## posts (id = shortcode)

```json
{"id": "C8xYz12", "handle": "studio.x", "url": "https://www.instagram.com/p/C8xYz12/",
 "type": "reel", "caption": "...", "likes": 12000, "comments": 340, "views": 410000,
 "posted_at": "2026-09-01T10:00:00.000Z", "pinned": false, "median_likes": 850,
 "breakout": 14.1, "confidence": "high", "rank": 1, "is_pick": true,
 "thumb_url": "https://...", "media_keys": ["frames/C8xYz12/01.jpg"],
 "transcript": "...", "music": "Artist - Song", "run_id": "job-..."}
```
Required: `id`, `handle`, `url`, `type`. Send `thumb_url` (the Worker stores the image and sets
`thumb_key`). Never send `video_url` / `slide_urls` (use `normalize.py --upsert-ready`, or
strip them). Own posts: upsert them too (with breakout vs her own median, `is_pick: false`).

## breakdowns (id = post shortcode)

```json
{"id": "C8xYz12", "post_id": "C8xYz12", "run_id": "job-...",
 "hook": {"uk": "...", "en": "..."}, "hook_observed": true,
 "hook_type": "spoken + on-screen", "hook_mechanism": "curiosity gap",
 "format": T, "topic": T, "angle": T, "breakdown": T, "why_it_worked": T,
 "copy_structurally": T, "do_not_copy": T, "remake_idea": T,
 "remake_axis": "audience + medium", "cta": T, "confidence": "high",
 "observed_facts": ["..."], "inferred_assumptions": ["..."]}
```
`hook_type`: `spoken` | `on-screen text` | `spoken + on-screen` | `visual`. For `hook`, keep the
literal quote in the original language inside both keys and add a gloss after ` · ` where useful.
`copy_structurally` / `do_not_copy`: one string per language, items separated by ` · `.

## reports (id = `<kind>-<YYYY-MM-DD>`)

```json
{"id": "audit-2026-09-23", "kind": "audit", "title": T, "created_at": "...Z",
 "run_id": "job-...", "data": { ... }}
```
`data` by kind:

- **audit**: `{summary:T, verdict:T, kpis:{followers, following, posts_total, posts_last_90d,
  posts_per_week, median_likes, median_comments, er_pct, reel_share, carousel_share, last_post_at},
  scorecard:[{area:T, score:0-10, note:T}], top_posts:[post_id], what_works:[{title:T, evidence:T}],
  what_doesnt:[{title:T, evidence:T}], voice:{description:T, traits:[T]},
  pillars:[{name:T, share_pct, avg_breakout, note:T}], gaps:[{title:T, detail:T}],
  profile_fixes:[{item:T, fix:T, priority:"high"|"medium"|"low"}],
  secondary_accounts:[{handle, verdict:T}], account_strategy:T}`
- **patterns**: `{summary:T, hooks:[P], formats:[P], topics:[P], structures:[P],
  gaps:[{type:"topic"|"format"|"quality"|"audience"|"angle", title:T, detail:T}], formula:T}`
  where `P = {mechanism, title:T, detail:T, examples:[post_id], share_pct}`
- **strategy**: `{positioning:T, north_star:T, pillars:[{name:T, goal:"reach"|"trust"|"leads",
  description:T, formats:[string], share_pct}], cadence:{reels_per_week, carousels_per_week,
  stories_per_day, note:T}, funnel:T, languages:T, rules:[T], plan:[{week:int, focus:T, idea_ids:[id]}]}`
- **landscape**: `{summary:T, tiers:[{tier, title:T, handles:[string], lesson:T}]}`

## ideas (id = `idea-<YYYYMMDD>-<n>`)

```json
{"id": "idea-20260923-01", "title": T, "hook": T, "pillar": "colour stories",
 "format": "reel", "angle": T, "why": T, "based_on": ["C8xYz12"], "score": 8.6,
 "score_parts": {"hook": 9, "pattern": 9, "payload": 8, "share": 9, "timing": 7,
                 "replicability": 8, "differentiation": 8},
 "score_reason": T, "effort": "low", "needs": T, "goal": "reach", "lang_hint": "uk",
 "status": "new", "created_at": "...Z", "run_id": "job-..."}
```
`format`: reel | carousel | story | image. `goal`: reach | trust | leads. `status` starts `new`
(never overwrite a status the owner changed: when updating an existing idea, omit `status`).

## scripts (id = `script-<idea id>-<lang>`)

```json
{"id": "script-idea-20260923-01-uk", "idea_id": "idea-20260923-01", "lang": "uk",
 "format": "reel", "title": "...",
 "reel": {"length_s": 28,
          "hook": {"spoken": "...", "on_screen": "...", "first_frame": "...",
                   "type": "spoken + on-screen", "mechanism": "contrarian claim"},
          "beats": [{"t": "0-2s", "say": "...", "show": "...", "on_screen": "..."}],
          "payoff": "...", "cta": "...", "shot_list": ["..."], "audio_note": "...",
          "cover_text": "..."},
 "captions": [{"variant": "A", "label": "curiosity", "text": "..."}],
 "hashtags": ["#interiordesign"], "posting_tip": "...", "why_it_works": T,
 "status": "draft", "created_at": "...Z"}
```
Carousel scripts use `"carousel": {"slides": [{"n": 1, "headline": "...", "body": "...",
"visual": "..."}], "cover_text": "..."}` instead of `reel`. Script copy (`title`, hook, beats,
captions, slides) is written ONLY in the script's `lang` (plain strings). After writing a
script, update its idea: `{"id": "<idea id>", "status": "scripted"}`.

## calendar (id = `cal-<YYYY-MM-DD>-<am|pm>`)

`{"id": "cal-2026-09-25-pm", "date": "2026-09-25", "slot": "pm", "item_type": "script",
"item_id": "script-...", "note": T}`

## learnings (id = `learn-<YYYYMMDDHHMM>-<n>`)

`{"id": "...", "insight": T, "evidence": "post X: 3.2x her median, 41 saves ...",
"source": "performance" | "research" | "feedback", "created_at": "...Z"}`

## jobs

Only through `ce.py job-update` (status, progress, summary {uk,en}, error) and
`ce.py job-create` (for the scheduled weekly run).
