# Benchmark run — folds-v1

- **Date:** 2026-05-26
- **Strategy:** Per-POS folding rules 1-4: reflexive alias + participle/short-adj/comparative mergers with top-parse + POS + 20-ipm-freq guards.
- **Samples per preset:** 50
- **Dictionary:** 42,775 lemmas (fingerprint `9813284ce0af`)
- **Base config:** `{'min_lemmas': 25, 'max_lemmas': 70, 'min_vowels': 2, 'pangram_freq_floor': 2.0, 'require_pangram': True, 'dominance_cap': 0.25, 'max_attempts': 4000, 'seed': None, 'top_n': None}`

**Notes:** Adds 2,893 lemma->lemma aliases (covers наедал->наедаться class) and merges 81 participle-style lemmas into parent verbs (with 8 protected by 20 ipm cutoff). Net dict change: 42,856 -> 42,775.

## Summary

| Preset | top_n | n ok | Avg word len | Median | Stdev | Range | Avg lemmas/puzzle | Pangrams/puzzle |
|---|---|---|---|---|---|---|---|---|
| Лёгкий | 2000 | 50/50 | 6.15 | 6.0 | 1.81 | 4–15 | 14.5 (median 14.0, range 10–28) | 1.12 |
| Средний | 6000 | 50/50 | 5.90 | 6.0 | 1.63 | 4–15 | 30.9 (median 29.0, range 25–47) | 1.18 |
| Сложный | 15000 | 50/50 | 6.06 | 6.0 | 1.65 | 4–14 | 43.6 (median 41.5, range 25–69) | 1.58 |
| Эксперт | None | 50/50 | 6.07 | 6.0 | 1.71 | 4–14 | 48.4 (median 50.0, range 25–68) | 1.82 |

## Word-length distribution (% of all sampled lemmas per preset)

| Preset | 4 | 5 | 6 | 7 | 8 | 9-10 | 11+ |
|---|---|---|---|---|---|---|---|
| Лёгкий | 18.3% | 22.6% | 24.6% | 14.2% | 10.3% | 8.1% | 1.9% |
| Средний | 21.0% | 26.6% | 21.2% | 15.5% | 8.1% | 6.6% | 0.9% |
| Сложный | 19.4% | 23.2% | 21.5% | 17.1% | 10.8% | 7.2% | 0.8% |
| Эксперт | 21.1% | 21.6% | 21.3% | 15.6% | 11.1% | 8.0% | 1.2% |

Raw per-puzzle data lives in `raw.json` next to this file.
