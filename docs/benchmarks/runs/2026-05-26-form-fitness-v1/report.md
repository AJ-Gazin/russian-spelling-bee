# Benchmark run — form-fitness-v1

- **Date:** 2026-05-26
- **Strategy:** Form-level fitness: a lemma is admitted if any of its inflected forms fits the hive. Pangram still requires citation form. Schema v2.
- **Samples per preset:** 50
- **Dictionary:** 41,706 lemmas (fingerprint `94e4567f8776`)
- **Base config:** `{'min_lemmas': 25, 'max_lemmas': 70, 'min_vowels': 2, 'pangram_freq_floor': 2.0, 'require_pangram': True, 'dominance_cap': 0.25, 'max_attempts': 4000, 'seed': None, 'top_n': None}`

**Notes:** First baseline run after the form-fitness rule lands. Same configuration as the live API. No per-POS folding yet.

## Summary

| Preset | top_n | n ok | Avg word len | Median | Stdev | Range | Avg lemmas/puzzle | Pangrams/puzzle |
|---|---|---|---|---|---|---|---|---|
| Лёгкий | 2000 | 50/50 | 6.19 | 6.0 | 1.81 | 4–15 | 14.0 (median 13.5, range 10–25) | 1.14 |
| Средний | 6000 | 50/50 | 5.98 | 6.0 | 1.71 | 4–15 | 30.8 (median 29.0, range 25–50) | 1.3 |
| Сложный | 15000 | 50/50 | 6.07 | 6.0 | 1.65 | 4–14 | 42.5 (median 40.0, range 25–69) | 1.6 |
| Эксперт | None | 50/50 | 6.15 | 6.0 | 1.72 | 4–14 | 48.7 (median 48.5, range 26–70) | 2.0 |

## Word-length distribution (% of all sampled lemmas per preset)

| Preset | 4 | 5 | 6 | 7 | 8 | 9-10 | 11+ |
|---|---|---|---|---|---|---|---|
| Лёгкий | 16.1% | 23.7% | 26.1% | 12.7% | 11.3% | 7.9% | 2.1% |
| Средний | 20.5% | 26.0% | 20.6% | 15.1% | 9.7% | 6.7% | 1.4% |
| Сложный | 19.0% | 23.0% | 22.1% | 16.8% | 10.9% | 7.3% | 0.9% |
| Эксперт | 19.6% | 21.5% | 21.1% | 16.3% | 11.5% | 8.6% | 1.4% |

Raw per-puzzle data lives in `raw.json` next to this file.
