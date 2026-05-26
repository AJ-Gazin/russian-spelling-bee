# Russian Spelling Bee — current implementation snapshot

**This file is the canonical description of what is actually live on this branch.** When behavior changes, update this file in the same change. Stale `STATUS.md` is a bug. The original planning document at [`docs/original-design.md`](docs/original-design.md) is preserved as a frozen reference; where the two diverge, `STATUS.md` wins. The active work queue is [`todo.md`](todo.md).

> **Last meaningful update:** difficulty knob (top-N preset selector) live end-to-end. The puzzle is fully playable in the browser against the real ~42k-lemma Lyashevskaya–Sharov dictionary, with a 4-preset difficulty selector and the three distinct rejection-mode toasts. Next planned focus: **UI/UX audit & polish** (separate session).

---

## Build status

| Subsystem | State | Live file(s) |
|---|---|---|
| Project skeleton + docs | live | `README.md`, `STATUS.md`, `todo.md`, `docs/` |
| Backend (Python 3.12, uv) | live | `backend/pyproject.toml` |
| Alphabet + Ё/Е + bitmasks | live | `backend/src/rsb/alphabet.py` |
| Lemmatizer (pymorphy3 wrapper) | live; ambiguity rule + Ё/Е normalization | `backend/src/rsb/lemmatizer.py` |
| Dictionary loader (TSV + DB) | live; loads from SQLite if populated, falls back to stub TSV | `backend/src/rsb/dictionary.py` |
| Stub lemma list | live; hand-curated ~300 words for fallback / tests | `backend/data/stub_lemmas.tsv` |
| Real dictionary pipeline | live; 41,706 lemmas from L–S 2011 (Freq2011.zip) | `backend/scripts/build_dictionary.py` |
| Overrides | live; YAML include/exclude/aliases; 27 seeded excludes; aliases loaded but unused | `backend/src/rsb/overrides.py`, `backend/data/overrides.yaml` |
| Scoring + ranks | live; planning-doc table | `backend/src/rsb/scoring.py` |
| Puzzle generator | live; constraint-checked; deterministic under seed; `top_n` difficulty knob | `backend/src/rsb/generator.py` |
| SQLite store | live; `puzzles` and `lemmas` tables | `backend/src/rsb/store.py` |
| FastAPI server | live; 4 endpoints; auto-generates first puzzle | `backend/src/rsb/api.py` |
| Svelte 5 frontend | live; full play loop in browser; difficulty selector | `frontend/src/` |
| Tests | 44 passing | `backend/tests/*.py` |
| UX polish (final pass) | **partial — see "Open UX work" below** | `frontend/src/lib/*.svelte` |

---

## Where to focus next

The next session is a **UI/UX audit + polish pass**. The functionality is in place; the surface needs work.

Known UX issues / opportunities (not exhaustive — audit needed):

1. **Header wraps awkwardly when the difficulty chip is wide.** "Русский Spelling Bee" wraps to two lines because the dropdown chip ("Эксперт ▾") doesn't leave room. Either shrink the title, drop "Русский" to a subtitle, or restructure the header.
2. **Accept toast doesn't show the lemma resolution.** `Toast.svelte` is already coded to render *form → lemma* when they differ, but only the lemma reaches the toast — `game.guess()` doesn't currently pass the raw `form` through to the toast. Trivial wire-up; see `lib/store.svelte.ts` → `showToast` → `handleGuessResponse`.
3. **Rank pip strip is functional but plain.** Real puzzles have a wide score distribution (e.g. 199 pts across 9 ranks ⇒ varied pip spacing). Could use a refresh now that we have real numbers to design against.
4. **Hive letter typography uses Georgia.** Looks fine for Cyrillic, but a more deliberate font choice (Old Standard TT, PT Serif, or a custom display face) might give the puzzle more identity.
5. **The "уже найдено" toast doesn't show what lemma was credited from the original entry.** It does say the lemma in the message, but visually it's indistinguishable from a typo rejection. Could differentiate more.
6. **No empty-state messaging when the API returns an error or the dictionary fails to load.** Currently shows raw `Error: ...` text.
7. **Mobile / narrow viewport not tested.** The hive's `width: min(360px, 80vw)` scales, but the input row and rank bar may need attention.

The frontend code lives entirely in `frontend/src/`. Start by skimming `App.svelte`, then `lib/store.svelte.ts` (game state, derived score/rank, toast), then each component. All components are Svelte 5 (uses `$state`, `$derived`, `$effect`, `$props` runes — not the Svelte 4 `<script>`-and-export style).

---

## Alphabet and hive composition

Implemented in `backend/src/rsb/alphabet.py`:

- 31-letter pool for hive composition: standard Russian 33 minus Ъ and Ё. Ё is folded into Е for hive *display* and for player *input matching*, but the dictionary stores lemmas Ё-aware (the `Lemma.lemma` field holds *ёлка*, not *елка*).
- Vowels: `А Е И О У Ы Э Ю Я` (9). Generator enforces `min_vowels >= 2` by default.
- Per-lemma 31-bit `letter_mask` precomputed at load time; hive-fit is a bitmask subset test.

Not yet implemented: per-letter frequency floors that guarantee rare letters (Ф Ц Щ Э) rotate through. Currently letter sampling is weighted by per-letter lemma occurrence count — rare letters are reachable but not guaranteed.

---

## Dictionary

**Real pipeline live.** `backend/scripts/build_dictionary.py` fetches `Freq2011.zip` from `dict.ruslang.ru`, extracts `freqrnc2011.csv` (Lyashevskaya–Sharov 2011 update), parses, filters, and writes 41,706 lemmas to the `lemmas` table in `backend/data/rsb.db`. The API auto-prefers the DB-backed dictionary on startup; if the `lemmas` table is empty it falls back to `backend/data/stub_lemmas.tsv` (~300 hand-curated rows kept for tests and fresh-checkout fallback).

Filters applied at build time:
- Frequency ≥ 0.5 ipm
- Open-class POS only: noun, verb, adjective, adverb, numeral, predicative, synthetic comparative
- Closed-class dropped: prepositions, conjunctions, particles, interjections, all pronoun classes
- Lemmas containing anything outside `{HIVE_LETTERS ∪ Ё}` (hyphens, spaces, latin, digits, Ъ) dropped
- pymorphy3 must round-trip the lemma to itself
- Proper nouns dropped via pymorphy3 grammeme check (Geox, Surn, Patr, Name, Init, Trad, Orgn)

After overrides are applied, the live dictionary holds **41,684 lemmas**.

---

## Overrides

`backend/data/overrides.yaml` carries three sections:
- `include`: force-add entries the pipeline doesn't see — `{lemma, pos, freq_ipm}`.
- `exclude`: force-drop entries (initial list seeded with 27 common diminutives like *садик*, *кадка*, *котик*).
- `aliases`: surface-form → lemma overrides for cases where pymorphy3 mis-parses. **Loaded but not yet consumed** by the lemmatizer — a follow-up will plumb it through (no real-world hits yet).

`overrides.py` exposes:
- `apply_to_rows()` — called by the build script between pymorphy3 validation and the SQLite write.
- `apply_to_dictionary()` — called by the API on startup, so a new `exclude` takes effect on next restart without rebuilding the SQLite table.

---

## Lemma resolution

Implemented in `backend/src/rsb/lemmatizer.py`. Returns `Resolution(status, lemma?, candidates)`:

- A player input is accepted iff **any** `pymorphy3` parse normalizes to a lemma in the puzzle's valid-lemma set.
- When multiple parses qualify, the highest-`pymorphy3.score` parse wins (deterministic).
- pymorphy3 already canonicalizes player Е→Ё internally (so *елка* parses to *ёлка*). We rely on that; lemmas are stored Ё-aware.
- API surfaces three distinct rejection statuses plus `accepted`/`already_found`:
  - `not_in_set`: parsed cleanly but no parse resolves to a puzzle lemma.
  - `unparseable`: pymorphy3 returned no parses at all.
  - `already_found`: the resolved lemma is already in the caller's `found_lemmas`.
- In `not_in_set` we also check whether any candidate parse matches an already-found lemma and reclassify to `already_found` for friendlier UX.

Lemma-rule edge cases from the planning doc (aspect pairs, reflexive -ся, diminutives, etc.) are honored *implicitly* by the dictionary — whatever lemmas the compiled dictionary contains, are valid; filtering happens in `build_dictionary.py` and `overrides.yaml`.

---

## Scoring and ranks

Implemented in `backend/src/rsb/scoring.py`. Follows the planning doc:

- 4-letter words → 1 pt; 5+ letter words → 1 pt per letter; pangram → +7.
- Lemmas <4 letters stay in the dictionary so the lemmatizer still recognizes them (yielding `not_in_set` rather than `unparseable`), but the generator excludes them from any puzzle's valid set.
- Rank thresholds: Новичок (0%) … Гений (100%), per the planning doc's table.

---

## Puzzle generation

Implemented in `backend/src/rsb/generator.py`:

- Weighted letter sampling without replacement (Efraimidis–Spirakis), weighted by per-letter lemma occurrence count in the dictionary.
- Per attempt: enforces `min_vowels`; for each of the 7 letters as candidate center, computes fitting lemmas via 31-bit bitmask subset test; accepts if `min_lemmas ≤ N ≤ max_lemmas`, qualifying pangram present (if required), and no single lemma exceeds `dominance_cap` of total score.
- `generate_many()` produces N distinct (letter-set, center) puzzles for previewing.
- Deterministic under a fixed `seed`.

Two configs live in `api.py` and are selected at startup based on whether the DB dictionary is populated:

| | `_DEFAULT_REAL_CFG` | `_DEFAULT_STUB_CFG` |
|---|---|---|
| `min_lemmas` | 25 | 8 |
| `max_lemmas` | 70 | 200 |
| `require_pangram` | True | False |
| `pangram_freq_floor` | 2.0 ipm | 0.0 |
| `dominance_cap` | 0.25 | 0.50 |

Not yet implemented: per-weekday difficulty tuning (Mon–Wed 25–35 vs. Thu–Sun 50–70). That ties to daily-rollover, which is deferred.

---

## Difficulty knob (`top_n`)

`GeneratorConfig.top_n` restricts the dictionary to the top-N most-frequent lemmas before sampling. Smaller N ⇒ easier vocabulary.

`POST /admin/generate` accepts a JSON body with `top_n` (and optional `min_lemmas`/`max_lemmas`/`require_pangram`/`seed`). When `top_n ≤ 5000`, the handler auto-scales `min_lemmas = max(8, min(25, top_n // 200))` and drops `pangram_freq_floor` to 0 — small pools rarely satisfy the planning-doc defaults.

UI: `NewGame.svelte` is a "Новая игра" button paired with a dropdown chip offering 4 presets:

| Label | `top_n` |
|---|---|
| Лёгкий | 2,000 |
| Средний | 6,000 |
| Сложный | 15,000 |
| Эксперт | unlimited (all ~42k) |

Selection persists in the chip.

---

## API surface

Implemented in `backend/src/rsb/api.py` (FastAPI). All paths live at `http://localhost:8000` (dev) or `/api` via the Vite proxy.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/puzzle/current` | — | Auto-generates one on first boot if the table is empty. |
| GET | `/puzzle/{id}` | — | 404 if not found. |
| POST | `/puzzle/{id}/guess` | `{form, found_lemmas}` | Returns `{status, lemma?, points?, is_pangram?, candidates}`. |
| POST | `/admin/generate` | `{top_n?, min_lemmas?, max_lemmas?, require_pangram?, seed?}` | All fields optional; empty body uses server defaults. |

`status` ∈ {`accepted`, `already_found`, `not_in_set`, `unparseable`}. Server-side per-player state is deferred; the client passes `found_lemmas` on every guess.

---

## Frontend

Svelte 5 + Vite + TypeScript single-page app under `frontend/`. Uses Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) throughout — not the Svelte 4 `<script>`-with-`export let` style.

| File | Purpose |
|---|---|
| `App.svelte` | Root: header, rank bar, hive, input, found-list, toast. Wires data flow. |
| `lib/Hive.svelte` | SVG hexagonal layout, center cell highlighted yellow, tap dispatches a letter to the input. |
| `lib/Input.svelte` | Text input + ⌫ / ⤿ (shuffle) / ↵ (enter) / × (clear) controls. Enter submits via `game.guess()`. |
| `lib/FoundList.svelte` | Two-column alphabetized list; pangrams styled gold. |
| `lib/RankBar.svelte` | 9-pip rank strip with current label and "current/total" score. |
| `lib/Toast.svelte` | Top toast with 4 visual variants. Supports pangram flair. |
| `lib/NewGame.svelte` | "Новая игра" button + difficulty preset chip + dropdown menu. |
| `lib/store.svelte.ts` | Single `GameState` singleton: puzzle, found, toast, derived score/rank/toNext. |
| `lib/api.ts` | Typed fetch wrappers for the 4 endpoints. |
| `lib/persist.ts` | Per-puzzle localStorage keyed by puzzle id (interim — server-side state is deferred). |

Vite proxies `/api/*` to `http://localhost:8000`. Run `npm run dev` in `frontend/` after starting `uv run uvicorn rsb.api:app` in `backend/`.

---

## Deferred (out of scope for the current build)

See `todo.md` "Future / deferred" for the full list. Headline items:
- All multi-player / family features (shared scoreboard, weekly summaries, *новые слова* digest)
- Daily-puzzle rollover + timezone choice
- Yesterday's puzzle viewer, end-of-day missed-words review, "сохранить слово"
- Hints grid, "редкое слово" badge, single-reveal grace mechanic
- Hosting / deployment

---

## Open questions (still open)

Carried forward from the planning doc; revisit after play data:
- Aspect pairs feel like double-counting?
- Гений at 100% achievable in Russian, or drop to 90% with Queen Bee?
- Hints for fluent players?
