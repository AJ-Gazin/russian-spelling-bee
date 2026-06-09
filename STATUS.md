# Russian Spelling Bee — current implementation snapshot

**This file is the canonical description of what is actually live on this branch.** When behavior changes, update this file in the same change. Stale `STATUS.md` is a bug. The original planning document at [`docs/original-design.md`](docs/original-design.md) is preserved as a frozen reference; where the two diverge, `STATUS.md` wins. The active work queue is [`todo.md`](todo.md). Empirical numbers per generation strategy live in [`docs/benchmarks/`](docs/benchmarks/README.md) — run `backend/scripts/sample_puzzles.py` to add a new entry whenever a generation/selection strategy changes.

> **Last meaningful update:** **Hive/center enforcement on guesses + abuse resistance.** (1) The guess endpoint now validates the *typed form* before any morphology: it must use only hive letters and contain the center (`api._hive_rejection`; new statuses `outside_hive` / `missing_center`). This closes the conceptual hole where form-level fitness admitted a lemma via one inflection but *any* inflection — including a center-less citation form like *сеть* in an и-center puzzle — was accepted. The client mirrors the rule for instant feedback; the server is the authority. (2) Abuse resistance for the public Space: `POST /api/admin/daily/{id}` is gated by `RSB_ADMIN_TOKEN` (when set); `/admin/generate` stays open (the "Новая игра" button calls it) but is rate-limited (`RSB_GENERATE_PER_HOUR`) and the puzzle pool is pruned past `RSB_MAX_PUZZLES` (history + daily pin + newest N always survive) so Turso growth is bounded. Previously shipped: constructible forms in the answer key + homonym cycling; per-POS folding rules (see [`docs/folding-rules.md`](docs/folding-rules.md)). **Pending decision:** pangram-bonus integrity proposal (Task 2 — see `todo.md`).

---

## Build status

| Subsystem | State | Live file(s) |
|---|---|---|
| Project skeleton + docs | live | `README.md`, `STATUS.md`, `todo.md`, `docs/` |
| Backend (Python 3.12, uv) | live | `backend/pyproject.toml` |
| Alphabet + Ё/Е + bitmasks | live; includes yo-aware `canonical_lemma` helper | `backend/src/rsb/alphabet.py` |
| Lemmatizer (pymorphy3 wrapper) | live; ambiguity rule + Ё/Е normalization (incl. defensive fallback); **`found`-aware homonym cycling** | `backend/src/rsb/lemmatizer.py` |
| Dictionary loader (TSV + DB) | live; loads from SQLite if populated, falls back to stub TSV | `backend/src/rsb/dictionary.py` |
| Stub lemma list | live; hand-curated ~300 words for fallback / tests | `backend/data/stub_lemmas.tsv` |
| Real dictionary pipeline | live; 42,775 lemmas from L–S 2011 (Freq2011.zip), yo-recovery, folding rules | `backend/scripts/build_dictionary.py` |
| Overrides | live; YAML include/exclude/aliases; 27 seeded excludes; ё-normalized at load; aliases loaded but unused | `backend/src/rsb/overrides.py`, `backend/data/overrides.yaml` |
| Folding rules (per-POS) | live; reflexive aliases (X↔X+ся) + 3 merger rules with top-parse + POS + 20-ipm guards; 2,893 aliases + 81 mergers; see [`docs/folding-rules.md`](docs/folding-rules.md) | `backend/src/rsb/folds.py`, `backend/data/fold-report.md` |
| Scoring + ranks | live; planning-doc table | `backend/src/rsb/scoring.py` |
| Puzzle generator | live; constraint-checked; deterministic under seed; **form-level fitness** | `backend/src/rsb/generator.py` |
| Lemma store (SQLite, read-only at runtime) | live; `lemmas` (+ `forms` strings) + `aliases` tables (schema v4) — baked into the Docker image | `backend/src/rsb/store.py` |
| State store (puzzles; future: scores) | live; Protocol with two impls (`LocalSqliteStateStore` for dev, `TursoStateStore` for prod) selected by env vars | `backend/src/rsb/state_store.py` |
| FastAPI server | live; endpoints under `/api` (puzzle/daily/current/by-id, guess, history, admin generate/daily); **hive/center guess validation**; admin token + rate limit + pool pruning; serves the built Svelte SPA at `/` when `./static/` exists | `backend/src/rsb/api.py` |
| Svelte 5 frontend | live; full play loop in browser | `frontend/src/` |
| HF Space deploy | live at https://ajgazin-russian-spelling-bee.hf.space; multi-stage Dockerfile; `scripts/deploy_hf.sh` for one-command redeploy | `Dockerfile`, `scripts/deploy_hf.sh`, `docs/deploy-huggingface.md` |
| Tests | 89 passing | `backend/tests/*.py` |
| UX polish (final pass) | **partial — see "Open UX work" below** | `frontend/src/lib/*.svelte` |

---

## Where to focus next

The next session is a **UI/UX audit + polish pass**. The functionality is in place; the surface needs work.

Known UX issues / opportunities (not exhaustive — audit needed):

1. **Header layout on narrow viewports.** The difficulty chip that originally caused "Русский Spelling Bee" to wrap is gone (presets removed), but the header hasn't been re-audited since — verify the title/buttons row on narrow widths.
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

**Real pipeline live.** `backend/scripts/build_dictionary.py` fetches `Freq2011.zip` from `dict.ruslang.ru`, extracts `freqrnc2011.csv` (Lyashevskaya–Sharov 2011 update), parses, filters, applies overrides, applies folding rules, and writes 42,775 lemmas + 2,893 lemma→lemma aliases into the `lemmas` and `aliases` tables in `backend/data/rsb.db`. The API auto-prefers the DB-backed dictionary on startup; if the `lemmas` table is empty it falls back to `backend/data/stub_lemmas.tsv` (~300 hand-curated rows kept for tests and fresh-checkout fallback).

Filters applied at build time:
- Frequency ≥ 0.5 ipm
- Open-class POS only: noun, verb, adjective, adverb, numeral, predicative, synthetic comparative
- Closed-class dropped: prepositions, conjunctions, particles, interjections, all pronoun classes
- Lemmas containing anything outside `{HIVE_LETTERS ∪ Ё}` (hyphens, spaces, latin, digits, Ъ) dropped
- pymorphy3 must round-trip the lemma to itself (yo-aware: if raw → pymorphy normal_form differs only by ё↔е and the ё-form round-trips, the row is rewritten to that ё-form before the freq-sum dedup)
- Proper nouns dropped via pymorphy3 grammeme check (Geox, Surn, Patr, Name, Init, Trad, Orgn)

The yo-recovery step rescued ~1,200 common nouns (incl. `ребёнок`, `ёлка`, `лёд`, `весёлый`, `чёрный`) that the source spells without ё. Overrides are pre-applied at build time (`apply_to_rows` runs against pymorphy-normalized rows), then folding rules run. The on-disk count *is* the live count — **42,775 lemmas + 2,893 aliases**.

---

## Folding rules

After overrides and before the SQLite write, `rsb.folds.compute_folds` applies four per-POS rules:

1. **Reflexive alias** (`X+ся ↔ base`) — both directions, gated by `pymorphy3.dictionary.word_is_known` so we don't add aliases for morphologically-generated-but-not-real partner verbs. Today: 2,893 aliases (424 base→reflexive incl. **`наедать → наедаться`**, 2,469 reflexive→base).
2. **Participle merger** (`PRTF lemma → parent verb`) — drops ADJF lemmas whose top pymorphy3 parse is PRTF→verb-in-dict, with freq < 20 ipm. Today: 81 mergers; 7 candidates protected by the freq cutoff (e.g. `соответствующий`, `действующий`).
3. **Short adjective merger** (`ADJS lemma → parent ADJF`) — same shape; 0 mergers today (L–S doesn't ship pure short-form lemmas), 1 protected (`намерен`).
4. **Comparative merger** (`COMP lemma → parent ADJF`) — same shape; 0 mergers today (no L–S COMP lemmas at all).

Every build writes a human-readable diff at `backend/data/fold-report.md`. The full rationale (what ships, what doesn't, and how to judge a new rule without being a linguist) lives in [`docs/folding-rules.md`](docs/folding-rules.md).

---

## Overrides

`backend/data/overrides.yaml` carries three sections:
- `include`: force-add entries the pipeline doesn't see — `{lemma, pos, freq_ipm}`.
- `exclude`: force-drop entries (initial list seeded with 27 common diminutives like *садик*, *кадка*, *котик*).
- `aliases`: surface-form → lemma overrides for cases where pymorphy3 mis-parses. **Loaded but not yet consumed** by the lemmatizer — a follow-up will plumb it through (no real-world hits yet).

`overrides.py` exposes:
- `normalize()` — routes each include/exclude lemma and each alias *value* through `alphabet.canonical_lemma` so an author can write `exclude: [ребенок]` and still match the canonical `ребёнок` in the DB. Called by both the build script and the API on startup. Alias *keys* are surface forms (not lemmas) and are left untouched.
- `apply_to_rows()` — called by the build script between pymorphy3 validation and the SQLite write.
- `apply_to_dictionary()` — called by the API on startup, so a new `exclude` takes effect on next restart without rebuilding the SQLite table.

---

## Lemma resolution

Implemented in `backend/src/rsb/lemmatizer.py`. `resolve(form, valid_lemmas, found=())` returns `Resolution(status, lemma?, candidates, reachable)`:

- A player input is accepted iff **any** `pymorphy3` parse normalizes to a lemma in the puzzle's valid-lemma set.
- **Homonym cycling.** A typed string can map to several in-set lemmas (a homonym — e.g. *линял* → `линять`(гл.)/`линялый`(прил.); *стекла* → `стекло`/`стечь`). `resolve` collects **all** reachable in-set lemmas in `pymorphy3.score` order (`Resolution.reachable`) and returns the first one **not yet in `found`**. Re-entering the same string therefore walks to the next homonym, so each is separately earnable. When every reachable lemma is already found, status is `already_found`.
- pymorphy3 already canonicalizes player Е→Ё internally (so *елка* parses to *ёлка*). We rely on that; lemmas are stored Ё-aware. A defensive `fold_yo` retry catches the rare case where a parse lemma differs from a valid-set entry only by ё↔е (e.g. a hand-curated stub spells a lemma without ё); when it fires, the resolved lemma is the *valid-set* spelling and a warning is logged.
- Statuses from the lemmatizer: `accepted` (+ `reachable`), `already_found`, `not_in_set` (parsed cleanly but no parse resolves to a puzzle lemma), `unparseable` (pymorphy3 returned no parses).
- **Hive/center validation happens before the lemmatizer** (in `api._hive_rejection`, not in `lemmatizer.py`): the typed form itself must use only hive letters (`outside_hive` otherwise) and contain the center letter (`missing_center` otherwise). This is the game's defining constraint applied to the *form*, independent of which lemma it resolves to — necessary because form-level fitness admits a lemma when *some* inflection fits, so other inflections of an in-set lemma may escape the hive or lack the center. `Input.svelte` mirrors both checks client-side (blocked submit + named reason, no round-trip); the server is the authority for non-UI clients.
- The guess endpoint passes the client's `found_lemmas` as `found`, and sets `homonym_remaining` on the response when `reachable` still holds an unfound lemma after this accept — the UI uses it to prompt the player to enter the string again. POS of the accepted lemma is returned for homonym disambiguation in the UI.
- **Alias fallback (folding rules):** lemma→lemma aliases (loaded from the `aliases` table at startup) extend `reachable` when a parse's normal_form isn't directly in the valid set. This is the path that makes a player typing *наедал* — pymorphy3-lemmatized to *наедать*, not in L–S — credit *наедаться* via the reflexive alias. See [`docs/folding-rules.md`](docs/folding-rules.md).

Lemma-rule edge cases from the planning doc (aspect pairs, reflexive -ся, diminutives, etc.) are honored either by the dictionary (whatever lemmas it contains are valid; filtered in `build_dictionary.py` + `overrides.yaml`) or by the folding rules (which add alias fallbacks and merge participle/short/comp variants into their parent lemma).

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
- Per attempt: enforces `min_vowels`; for each of the 7 letters as candidate center, computes fitting lemmas via **form-level** 31-bit bitmask subset test (see "Form-level fitness rule" below); accepts if `min_lemmas ≤ N ≤ max_lemmas`, qualifying pangram present (if required), and no single lemma exceeds `dominance_cap` of total score.
- `generate_many()` produces N distinct (letter-set, center) puzzles for previewing.
- Deterministic under a fixed `seed`.

### Form-level fitness rule

A lemma belongs in the puzzle's answer list iff **at least one of its inflected forms** (length ≥ 4, alphabet-clean) has letters ⊆ hive AND contains the center.

- **Storage:** the inflected form *strings* (Ё-aware) are stored per lemma in `lemmas.forms TEXT` (comma-separated), enumerated at build time via pymorphy3's lexeme. `Lemma.form_masks: frozenset[int]` (the 31-bit letter-set masks used by the subset test) is **derived from those strings at load** — single source of truth, no drift. Legacy DBs without `forms` re-enumerate on first read (one-time). Schema is **v4**; the older `form_masks` column is retained for backward compat but no longer written.
- **Why store the strings:** the citation form often carries a final ь (сеть, линь) or a letter outside the hive (лисёнок needs к) that the *other* forms don't — so the headword alone is untypeable. The answer key shows the **constructible forms** (`сети`, `линя`, `лисят`) as a learning aid. Per puzzle, the generator filters each lemma's forms to those that fit the hive (subset ∧ contains center) and stores them on `ScoredLemma.forms` (ordered shortest-first); the API returns them and `AnswersModal.svelte` renders them under each headword.
- **Pangram still uses `Lemma.mask`** (the citation form), so a flagged pangram is always a recognizable word, not an obscure participle that happens to use all 7 letters. *(Pangram-findability/homonym-safety is a separate, deferred task — see `todo.md`.)*
- **Calibration follow-up:** `min_lemmas`/`max_lemmas` bands will likely need re-tuning since more lemmas fit per hive — see `todo.md`.

Two configs live in `api.py` and are selected at startup based on whether the DB dictionary is populated:

| | `_DEFAULT_REAL_CFG` | `_DEFAULT_STUB_CFG` |
|---|---|---|
| `min_lemmas` | 25 | 8 |
| `max_lemmas` | 70 | 200 |
| `require_pangram` | True | False |
| `pangram_freq_floor` | 2.0 ipm | 0.0 |
| `dominance_cap` | 0.25 | 0.50 |

Not yet implemented: per-weekday difficulty tuning (Mon–Wed 25–35 vs. Thu–Sun 50–70). That ties to daily-rollover, which is deferred.

**Removed:** the `top_n` difficulty knob (vocabulary-restricted presets Лёгкий/Средний/Сложный/Эксперт). The full lexicon is always in play now; acknowledging rare words is tracked in `todo.md` ("Word rarity representation"). Historical benchmark runs under `docs/benchmarks/runs/` still carry per-preset rows — compare new runs against their Эксперт row.

---

## API surface

Implemented in `backend/src/rsb/api.py` (FastAPI). All routes are mounted on an `APIRouter(prefix="/api")`, so paths are `/api/puzzle/...` in both dev (via the Vite proxy) and production (same-origin under the bundled HF Space). When `./static/` exists in the working dir (production build), the Svelte SPA is mounted at `/` after the router and FastAPI's auto-routes resolve.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/health` | — | `{status, state_store}`. Liveness + which state backend booted (`local-sqlite` vs `turso`). |
| GET | `/api/puzzle/daily` | — | The pinned daily/featured puzzle — the default a brand-new browser opens on. Stable: `/admin/generate` does NOT move it. Set at boot (seed); re-pin via `/admin/daily/{id}`. |
| GET | `/api/puzzle/current` | — | Latest puzzle by id. Auto-generates one on first boot if the store is empty. (The frontend uses `daily` + the browser's stored active id, not this.) |
| GET | `/api/puzzle/{id}` | — | 404 if not found. Used to reopen the browser's active puzzle and history entries. |
| POST | `/api/puzzle/{id}/guess` | `{form, found_lemmas}` | Returns `{status, lemma?, points?, is_pangram?, pos?, homonym_remaining, candidates}`. The typed form is validated against the hive first (`outside_hive` / `missing_center`) before lemma resolution. On `accepted`, records the puzzle into history (idempotent). `homonym_remaining`=true ⇒ same string reaches another unfound homonym (re-submit to cycle). |
| GET | `/api/history` | `?limit=10` | Last `limit` puzzles that have had ≥1 correct guess, newest first. Global/shared, Turso-durable. `[{id, letters, center, total_points, started_at}]`. |
| POST | `/api/admin/generate` | `{min_lemmas?, max_lemmas?, require_pangram?, seed?}` | All fields optional; empty body uses server defaults. Saves to the shared pool but does NOT change the daily. Open (the "Новая игра" button calls it) but rate-limited globally (`RSB_GENERATE_PER_HOUR`, default 30/h ⇒ 429 past it); past `RSB_MAX_PUZZLES` (default 200) the pool is pruned of old never-played puzzles (history + daily + newest N survive). |
| POST | `/api/admin/daily/{id}` | — | Pin an existing puzzle as the daily/featured default. 404 if the id is unknown. Requires header `X-Admin-Token` matching `RSB_ADMIN_TOKEN` when that env var is set (401 otherwise); unset ⇒ open (local dev). |

`status` ∈ {`accepted`, `already_found`, `outside_hive`, `missing_center`, `not_in_set`, `unparseable`}.

**Per-browser vs shared model:** each browser tracks its own *active* puzzle in `localStorage` (`rsb:active`) plus per-puzzle found-words (`rsb:found:{id}`). Pressing "New Game" generates a puzzle and rebinds only the local active id — other visitors are untouched. The **daily** puzzle (new-visitor default) and the **history** list are the shared surfaces. Server-side per-player scoring is still deferred; the client passes `found_lemmas` on every guess.

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
| `lib/NewGame.svelte` | "Новая игра" button (difficulty presets removed — full lexicon always). |
| `lib/HistoryModal.svelte` | "История" modal: last-10 (global) puzzles; click reopens one (continue playing). Per-row found-count is this browser's localStorage. |
| `lib/store.svelte.ts` | Single `GameState` singleton: puzzle, found, toast, derived score/rank/toNext. |
| `lib/api.ts` | Typed fetch wrappers for the API endpoints. |
| `lib/persist.ts` | localStorage: per-puzzle found-words (`rsb:found:{id}`) + this browser's active puzzle id (`rsb:active`). |

Vite proxies `/api/*` to `http://localhost:8000` (path preserved — the backend mounts its router at `/api`, so dev and prod paths match). Run `npm run dev` in `frontend/` after starting `uv run uvicorn rsb.api:app` in `backend/`.

---

## Deploy + state persistence

**Live:** https://ajgazin-russian-spelling-bee.hf.space

The Space is a single Docker image bundling the Svelte SPA and FastAPI backend (see `Dockerfile` at repo root). Multi-stage build:

1. `node:20-slim` runs `npm ci && npm run build` on `frontend/` → `/build/dist`.
2. `python:3.12-slim` installs backend deps via uv, runs `scripts/build_dictionary.py` to bake the ~42k lemma SQLite into the image, then copies the SPA's `dist/` into `./static/`.
3. uvicorn binds `0.0.0.0:7860` (HF Spaces default).

**State store selection happens at startup** in `state_store.open_state_store()`:

| Env var present | Backend chosen | Notes |
|---|---|---|
| `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` | `TursoStateStore` (libsql) | Production. Durable across Space restarts/rebuilds. |
| Neither | `LocalSqliteStateStore` at `data/rsb_state.db` (or `$RSB_STATE_DB`) | Dev default. Ephemeral on Spaces. |

The lemma table is a separate concern — read-only, baked into the image, lives in `backend/data/rsb.db`.

**Abuse-resistance env vars** (all optional): `RSB_ADMIN_TOKEN` (set as a Space secret — gates the daily re-pin; unset ⇒ open), `RSB_GENERATE_PER_HOUR` (default 30; ≤0 disables), `RSB_MAX_PUZZLES` (default 200; ≤0 disables pruning).

**Redeploy:** `scripts/deploy_hf.sh` from repo root. It stages a clean tree in `/tmp`, swaps in the HF-flavored `docs/space.README.md` as the Space's `README.md`, and `hf upload`s. (Staging is necessary because `hf upload` chokes on a CWD containing `.venv`.)

Full notes including provisioning + secret rotation: [`docs/deploy-huggingface.md`](docs/deploy-huggingface.md).

---

## Deferred (out of scope for the current build)

See `todo.md` "Future / deferred" for the full list. Headline items:
- All multi-player / family features (shared scoreboard, weekly summaries, *новые слова* digest)
- Daily-puzzle rollover + timezone choice
- Yesterday's puzzle viewer, end-of-day missed-words review, "сохранить слово"
- Hints grid, "редкое слово" badge, single-reveal grace mechanic
- Per-player scoreboard rows in the existing `scores` table (schema ready in `state_store.py`)

---

## Open questions (still open)

Carried forward from the planning doc; revisit after play data:
- Aspect pairs feel like double-counting?
- Гений at 100% achievable in Russian, or drop to 90% with Queen Bee?
- Hints for fluent players?
