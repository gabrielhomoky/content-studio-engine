# Per-post breakdown brief (give this to each breakdown subagent)

You analyse ONE competitor post that over-performed for its creator and explain why, so the
client can reuse the mechanism (never the content). You receive:

- `post.json`: the pick (handle, type, likes, comments, views, posted_at, median_likes,
  breakout, confidence, caption, url). These are the ONLY metrics you may cite.
- `manifest.json` + the files it lists: keyframes (`frame_01.jpg` is at 0.5 s and shows the
  first-frame hook) or carousel slides in order, and `transcript` (Whisper, may be empty).
  **Open and look at every image** with the Read tool. Read the slide text.
- `client.md`: who the remake is for (brand, markets, voice, goals, languages).

Write `breakdown.json` (UTF-8, valid JSON) in the shape of the `breakdowns` collection in
`knowledge/output-schemas.md`, with `id` and `post_id` = the shortcode and `run_id` given
to you. Every `T` field is an object with the requested language keys (usually
`{"uk": …, "en": …}`), each written natively.

Fields:
- `hook`: the literal first spoken line and/or the on-screen text in frame 1, quoted in the
  original language (same quote in every language key, gloss after ` · ` if useful).
- `hook_observed`: true only if read from the transcript start or visible in frame 1.
- `hook_type`: `spoken` | `on-screen text` | `spoken + on-screen` | `visual`.
- `hook_mechanism`: one of the mechanisms in `knowledge/hook-library.md`.
- `format`, `topic`, `angle`: short.
- `breakdown`: one paragraph, concept + structure (hook → body → payoff → CTA), ≤ 90 words.
- `why_it_worked`: the mechanism, not a restatement, ≤ 90 words. You may cite the observed
  numbers (breakout, comments:likes ratio computed from the given numbers). Flag inflated
  breakouts from very low medians.
- `copy_structurally` and `do_not_copy`: items separated by ` · `.
- `remake_idea`: an ORIGINAL idea for the client, built from her own projects, markets and
  voice. Change at least one axis and name it in `remake_axis` (audience, angle, format,
  medium, stance, market, language). Never "re-shoot this video" or "translate this".
- `cta`: a CTA in the client's style (see `knowledge/reel-structure.md`).
- `confidence`: high | medium | low (lower if no transcript, unclear frames, inflated median).
- `observed_facts`: only things read from the files (metrics copied exactly, what frames show,
  what the transcript says). Claims inside the creator's video/caption are listed as
  "the video claims: …", not as facts.
- `inferred_assumptions`: your judgment calls, labelled as such.

Hard rules: never invent a metric, date, follower count or statistic · transform, don't copy ·
no em dashes in the client-facing text · keep it tight.

Reply to the orchestrator with one line only: `<shortcode>: ok` or `<shortcode>: <problem>`.
