---
name: studio-ideas
description: Generates scored, non-duplicate post ideas (reels, carousels, stories) for the Content Studio client from observed competitor breakouts, the patterns report, her own audit and past learnings, using the 7-factor viral scorecard. Also writes the `strategy` report when asked. Use for `ideas` jobs, inside `weekly`, and for `custom` requests that ask for ideas.
---

# studio-ideas — what to post next, and why it should work

Knowledge: `../knowledge/viral-scorecard.md`, `../knowledge/hook-library.md`,
`../knowledge/interior-niche-playbook.md`, `../knowledge/pattern-mining.md` (repurpose-into-10),
`../knowledge/output-schemas.md`.

## Inputs

```bash
python3 tools/ce.py list reports --filter kind=patterns --limit 1 --out work/ideas/patterns.json
python3 tools/ce.py list reports --filter kind=audit --limit 1 --out work/ideas/audit.json
python3 tools/ce.py list reports --filter kind=strategy --limit 1 --out work/ideas/strategy.json
python3 tools/ce.py list posts --filter is_pick=1 --limit 40 --out work/ideas/picks.json
python3 tools/ce.py list breakdowns --limit 40 --out work/ideas/breakdowns.json
```
Plus `context.ideas_index` (avoid duplicates), `context.learnings`, `context.brand`,
`context.prefs.cadence`, and the job params: `count` (default 10), `focus`, `format`.

## Generate

- Mix to match cadence (e.g. 3 reels : 2 carousels) unless `format` is set; include 1 story
  idea sequence if useful.
- Goal mix: ~50% reach, ~30% trust, ~20% leads.
- Each idea is tied to at least one observed breakout (`based_on`) OR clearly marked as a
  gap bet (then `pattern` ≤ 5).
- Each idea uses something the client really has: her projects, her colours, her city/market
  lanes, her voice and self-irony, her awards/press only if in the data. Unknown specifics
  become `[placeholders]` in `needs`.
- `needs`: exactly what she must film/prepare (e.g. "3 clips on the next site visit: doorway
  reveal, detail macro of the paint edge, talking head 2 lines").
- `lang_hint`: which language this post should be in and why (home-market story vs
  international portfolio).
- Score all 7 factors, compute `score` with the weights, write `score_reason`.
- Drop anything scoring < 5; keep the best `count`.
- Never duplicate a title/angle in `ideas_index`; a new angle on a proven topic is fine.

Ids: `idea-<YYYYMMDD>-<nn>` (nn continues after existing ids of the same day).
Do NOT send `status` for existing ideas; new ideas get `status: "new"`.

```bash
python3 tools/ce.py upsert ideas --json work/ideas/ideas.json
```

## Strategy report (weekly, or when missing / older than 28 days, or when asked)

`strategy-<date>`: positioning, north star, 4-6 pillars with goal/share/formats, cadence,
funnel (how reach turns into enquiries for this client), language rules, 5-8 rules, and a
4-week plan referencing idea ids. Ground every claim in the audit + patterns.
