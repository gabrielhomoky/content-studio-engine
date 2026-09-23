# Viral scorecard — breakout math + the 1-10 idea model

Two different numbers. Never confuse them.

## 1. Breakout multiplier (OBSERVED, only from real data)

```
breakout = post likes ÷ median likes of that creator's recent, non-pinned posts
```

A small creator's post at 30× their own median is a stronger signal than a huge creator's
post at 1.2×. Median, not mean, so one old viral post does not hide new breakouts.
`tools/rank.py` computes it; never eyeball it.

| Breakout | Reading |
|---|---|
| < 1.5× | normal for that creator, ignore |
| 1.5-3× | solid over-performer |
| 3-10× | strong outlier, study it |
| 10-30× | major outlier, high-priority pattern |
| > 30× | viral outlier, reverse-engineer hard |

- Fewer than ~6 recent posts → confidence `low`, say so.
- Pinned posts are excluded from the median (they are cumulative).
- A breakout built on a very low median (e.g. 12 likes) is inflated: say it in `why_it_worked`
  and lower the confidence.
- No like count → breakout `null`. Never estimate.
- Useful secondary ratios, only from observed numbers: comments ÷ likes (conversation /
  keyword-funnel strength), views ÷ followers (reach beyond the base).

## 2. Viral-potential score (1-10, JUDGMENT, for ideas)

Score each factor 0-10, multiply by weight, sum, round to one decimal.

| Factor | Weight | 0-3 weak | 4-6 ok | 7-10 strong |
|---|---|---|---|---|
| `hook` | 0.25 | generic opener | mild curiosity | scroll-stopping in 1-2 s |
| `pattern` | 0.20 | untested here | loosely related | built on an observed breakout pattern |
| `payload` (emotion or utility) | 0.15 | forgettable | mildly useful | strong feeling or a real takeaway |
| `share` (share/save-ability) | 0.15 | nobody shares | maybe a save | "send this to someone" / save-worthy |
| `timing` | 0.10 | stale | evergreen | hot right now (season, trend, news) |
| `replicability` | 0.10 | client cannot produce it | doable | on-brand and easy with her projects |
| `differentiation` | 0.05 | adds to the noise | slight twist | a distinct angle in the cluster |

```
score = 0.25*hook + 0.20*pattern + 0.15*payload + 0.15*share
      + 0.10*timing + 0.10*replicability + 0.05*differentiation
```

Bands: **8.5-10** shoot first · **7-8.4** queue · **5-6.9** test slot · **< 5** rework or cut.
Always write the one-line `score_reason`. A score without a reason is noise.

`pattern` can only be ≥ 7 when `based_on` lists at least one observed breakout post.
`replicability` must account for what the client actually has (finished projects, site
visits, her own face/voice on camera or not).

## 3. Report confidence

- **High**: many observed posts, clear breakouts, transcripts and frames read directly.
- **Medium**: real data with gaps (few transcripts, thin samples).
- **Low**: little or no real data. Say it up front.
Confidence is bounded by the worst input.
