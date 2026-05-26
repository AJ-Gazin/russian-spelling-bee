# Benchmarks — puzzle-generation strategies

Objective measurements of how each word-selection strategy behaves at scale, so we can compare strategies across iterations without relying on memory or anecdote.

Each run captures:

- **Avg / median / stdev / range** of word length per difficulty preset
- **Lemmas per puzzle** distribution
- **Pangrams per puzzle** rate
- **Word-length histogram** in buckets (4, 5, 6, 7, 8, 9–10, 11+)
- **Raw per-puzzle records** in `raw.json` for cross-run deltas

## How to run

```bash
cd backend
.venv/Scripts/python.exe -u scripts/sample_puzzles.py \
    --label <strategy-slug> \
    --strategy "<one-line description>" \
    --n 50 \
    --notes "<context for the run>"
```

Output goes to `docs/benchmarks/runs/{YYYY-MM-DD}-{label}/`:

- `report.md` — human-readable summary
- `raw.json` — per-puzzle records (seed, hive, lemma list with lengths/points), plus a `run` block capturing dictionary size, dictionary fingerprint, base config, and notes

The fingerprint is a sha1 over the sorted lemma set; if it changes between runs, a delta could be either the strategy or the dictionary itself. Always note which.

## Methodology

- Seeds are deterministic (0 .. N-1) per preset. Two runs against the same dictionary and the same strategy must produce identical output.
- Per-preset config softening mirrors the live API (`backend/src/rsb/api.py:admin_generate`). When that softening changes, `sample_puzzles.py` and the API need to change together.
- The four production difficulty presets are sampled (Лёгкий / Средний / Сложный / Эксперт). When a preset list changes, sample_puzzles.py's `PRESETS` constant and `frontend/src/lib/NewGame.svelte` need to stay in sync.
- Default sample size is 50 puzzles per preset (200 total). Tighter confidence intervals: bump `--n` to 100 or 200; runtime scales linearly.

## Reference points

External numbers we benchmark against (see `STATUS.md` for citations):

- NYT Spelling Bee: ~5.3 avg letters per word, ~45 words per puzzle (2025), ~1.5 pangrams per puzzle (2026).
- Russian inflection adds ~0.5–1.0 letters to lemmas vs. English equivalents; treat 5.5–6.5 as "comparable to NYT" for Russian lemma length.

## Runs

Newest first. Each row links to the run's `report.md`.

| Date | Strategy | n/preset | Dict size | Headline finding |
|---|---|---|---|---|
| 2026-05-26 | [form-fitness-v1](runs/2026-05-26-form-fitness-v1/report.md) | 50 | 41,706 (`94e4567f8776`) | Avg word length 5.98–6.19 across all presets (essentially flat). Per-puzzle counts 14 / 31 / 43 / 49 — Лёгкий below NYT-equivalent floor; Сложный hits NYT pangram-rate (1.6) on the nose. |

### Adding a new entry

When a new run completes, prepend a row to the table above with:

- `[YYYY-MM-DD label](runs/YYYY-MM-DD-label/report.md)` in the Strategy column
- The headline finding in 1 short sentence in the Notes column (e.g., "Avg word length 6.10 across all presets; Лёгкий below NYT-equivalent answer count")

Do not delete old runs — even superseded strategies are reference points.
