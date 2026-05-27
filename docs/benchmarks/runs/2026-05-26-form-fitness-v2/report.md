# Benchmark run — form-fitness-v2

- **Date:** 2026-05-26
- **Strategy:** Form-fitness baseline after yo-recovery (commit f327db5). No per-POS folding yet.
- **Samples per preset:** 50
- **Dictionary:** 42,856 lemmas (fingerprint `d3782febd7a8`)
- **Base config:** `{'min_lemmas': 25, 'max_lemmas': 70, 'min_vowels': 2, 'pangram_freq_floor': 2.0, 'require_pangram': True, 'dominance_cap': 0.25, 'max_attempts': 4000, 'seed': None, 'top_n': None}`

**Notes:** Pre-folding baseline after yo-recovery added ~1,200 lemmas. Captures any drift since 2026-05-26-form-fitness-v1. Naming per todo.md note on the Generator calibration line.

## Summary

| Preset | top_n | n ok | Avg word len | Median | Stdev | Range | Avg lemmas/puzzle | Pangrams/puzzle |
|---|---|---|---|---|---|---|---|---|
| Лёгкий | 2000 | 50/50 | 6.15 | 6.0 | 1.81 | 4–15 | 14.5 (median 14.0, range 10–28) | 1.12 |
| Средний | 6000 | 50/50 | 5.90 | 6.0 | 1.62 | 4–15 | 31.0 (median 29.0, range 25–47) | 1.18 |
| Сложный | 15000 | 50/50 | 6.03 | 6.0 | 1.64 | 4–14 | 42.9 (median 41.0, range 25–69) | 1.58 |
| Эксперт | None | 50/50 | 6.08 | 6.0 | 1.72 | 4–14 | 48.6 (median 50.0, range 25–68) | 1.84 |

## Word-length distribution (% of all sampled lemmas per preset)

| Preset | 4 | 5 | 6 | 7 | 8 | 9-10 | 11+ |
|---|---|---|---|---|---|---|---|
| Лёгкий | 18.3% | 22.6% | 24.6% | 14.2% | 10.3% | 8.1% | 1.9% |
| Средний | 20.9% | 26.8% | 21.3% | 15.6% | 8.2% | 6.4% | 0.9% |
| Сложный | 19.8% | 23.3% | 21.7% | 16.8% | 10.6% | 6.9% | 0.8% |
| Эксперт | 21.2% | 21.6% | 21.2% | 15.5% | 11.2% | 8.1% | 1.3% |

Raw per-puzzle data lives in `raw.json` next to this file.
