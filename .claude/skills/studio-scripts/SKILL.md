---
name: studio-scripts
description: Writes ready-to-shoot reel scripts and carousel scripts for the Content Studio client in Ukrainian or English, with exact hook (spoken, on-screen, first frame), timed beats, a phone shot list for one site visit, cover text, three caption variants, hashtags and a posting tip, in the client's own voice. Use for `script` jobs, the top ideas inside `weekly`, and `custom` requests that ask for a script.
---

# studio-scripts — from idea to something she can film tomorrow

Knowledge (read before writing): `../knowledge/reel-structure.md`,
`../knowledge/carousel-frameworks.md`, `../knowledge/caption-rules.md`,
`../knowledge/hook-library.md`, `../knowledge/interior-niche-playbook.md`,
`../knowledge/output-schemas.md`.

## Inputs

- The idea: `python3 tools/ce.py list ideas --limit 200 --out work/scripts/ideas.json`, then
  take the row whose `id` is the job's `idea_id`; plus the breakdowns of its `based_on`
  posts (`python3 tools/ce.py list breakdowns --limit 60 --out work/scripts/breakdowns.json`).
  If the idea id does not exist, mark the job `error` ("idea not found").
- Language: `job.params.lang` → else the idea's `lang_hint` → else
  `context.prefs.default_script_lang`. `both` means two scripts (uk and en), each written
  natively, not translated line by line.
- Voice: `context.brand.voice` and the latest audit `voice` (traits). Imitate her rhythm,
  humour and vocabulary.

## Write

**Reel** (`reel` object): `length_s`; `hook` {spoken, on_screen, first_frame, type,
mechanism}; `beats` with timing (`t` like "0-2s"), `say`, `show`, `on_screen`; `payoff`;
`cta`; `shot_list` (5-10 shots using the playbook vocabulary, filmable on ONE site visit
with a phone, in shooting order); `audio_note` (voiceover vs sound; no invented track
names); `cover_text` (3-5 words).

**Carousel** (`carousel` object): 5-10 `slides` {n, headline, body, visual}; `cover_text`.
Slide 1 follows PIE or a before/after hook.

Both: `captions` A (curiosity) / B (value stack) / C (story, her voice); 3-6 `hashtags`
(language-appropriate, include one location/market tag when relevant); `posting_tip`
(best slot, pin?, trial reel?, story follow-up); `why_it_works` (bilingual T, cites the
pattern and the observed breakout it is built on).

Rules: value first, then the gate · one CTA · keyword CTAs only if the client can deliver
the DM (check `context.brand` funnel notes; otherwise save/send/enquire) · real facts only,
`[placeholders]` for unknown specifics · no em dashes · premium tone · run the 10-point tone
check in `reel-structure.md` and fix before saving.

Ids: `script-<idea_id>-<lang>`. Status `draft` (the owner marks `ready` / `posted`).

```bash
python3 tools/ce.py upsert scripts --json work/scripts/<id>.json
python3 tools/ce.py upsert ideas --json '{"id": "<idea_id>", "status": "scripted"}'
```
