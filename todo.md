# Russian Spelling Bee — to-do list

Canonical, hand-maintained task list. Tracks both in-flight work and deferred items. Cross-references to design state belong in [`STATUS.md`](STATUS.md); the original (frozen) planning document is at [`docs/original-design.md`](docs/original-design.md).

Conventions:
- `[ ]` open, `[x]` done, `[~]` in progress, `[-]` deferred / out of current scope.
- Anything checked here should also be reflected in `STATUS.md` if it changes user-visible behavior.

---

## Next up — UI / UX audit & polish (separate session)

A dedicated session will own the visual / interaction pass over the frontend. Specific known issues (not exhaustive — audit needed):

- [ ] Header layout: "Русский Spelling Bee" wraps to two lines when the difficulty chip is wide
- [ ] Accept toast doesn't show *form → lemma* even though `Toast.svelte` supports it — `game.guess()` needs to thread the raw `form` into the toast (`lib/store.svelte.ts`)
- [ ] Rank pip strip looks plain against real puzzle score distributions
- [ ] Hive typography (Georgia) is functional but unopinionated
- [ ] `already_found` toast visually indistinguishable from typo rejection
- [ ] Empty-state / error rendering when the API errors or returns 404
- [ ] Mobile / narrow-viewport pass
- [ ] Decide if a "top-N" badge should be visible on the rendered puzzle so players can see which difficulty they're playing

All frontend code lives in `frontend/src/`. Start with `App.svelte` → `lib/store.svelte.ts` → each component.

---

## Loose ends in the current build

Small backend items that aren't blocking but should be revisited:

- [ ] Per-letter rare-letter floors (Ф Ц Щ Э rotation guarantees) — currently best-effort via frequency weights only
- [ ] Lemmatizer consults `aliases` from `overrides.yaml` — currently the section is loaded but unused (no real-world hits today; trivial to plumb when needed)
- [ ] **Difficulty future:** custom-N input for power users (presets only today)
- [ ] **Generator calibration after form-fitness:** the form-level fitness rule (a lemma is admitted if any of its inflected forms fits the hive) admits more lemmas per hive than the old citation-form rule. Re-tune `min_lemmas` / `max_lemmas` bands and `top_n` preset thresholds once we have play data on real puzzles. The yo-recovery fix also added ~1,200 lemmas; re-run `backend/scripts/sample_puzzles.py` for a `form-fitness-v2` baseline before re-tuning.

---

## Per-POS folding rules (deferred)

The form-fitness rule (post-implementation) accepts any inflected form of a lemma. Separate from that — and still open — is **how aggressively to fold related lemmas into one entry** before they reach the puzzle. Each item below is a calibration question, not a blocker.

- [ ] **Participles → parent verb vs standalone adjective.** pymorphy3 lemmatizes *пишущий* as its own ADJF lemma, not as a form of *писать*. Decide whether to merge active/passive participles into their parent verb (so finding *пишущий* counts as finding *писать*) or keep them as distinct entries.
- [ ] **Aspect pairs.** *читать* / *прочитать*, *делать* / *сделать* are separate lemmas. Many pairs differ only by a semantically-vacuous prefix and feel like one verb to players. Decide which prefixes (по-, про-, с-, на-, …) collapse and which preserve a meaning distinction.
- [ ] **Reflexives.** *мыть* / *мыться*, *учить* / *учиться*. Almost always semantically distinct (transitive vs reflexive); recommend keeping separate, but worth confirming on real data. **Concrete known miss:** the L–S source lists `наедаться` / `наесться` (reflexive imperfective/perfective) but not the transitive imperfective `наедать`, so typing *наедал* falls through with `not_in_set` even though the reflexive partner is in the puzzle. A reflexive-folding rule (`X+ся ↔ X`) would fix this.
- [ ] **Adjective short forms.** *красив* (short) vs *красивый* (long). pymorphy3 may produce *красив* as its own lemma in some parses. Decide whether short forms collapse into long forms always.
- [ ] **Comparatives & superlatives.** *красивее* (comparative), *красивейший* (synthetic superlative). Often have their own headwords in some dictionaries. Decide whether to collapse.
- [ ] **Diminutives.** *кот* / *котик*, *дом* / *домик*. Probably keep separate (semantically distinct), but the diminutive overrides file already curates some of these — audit.

A reasonable approach: write a folding script that walks the lemma table, proposes merges by rule, dumps a YAML diff for human review (yes/no/keep), and applies accepted merges as an `aliases` extension to `overrides.yaml`. Defers the linguistic judgment to a one-time editorial pass rather than baking it into the build pipeline.

---

## Completed (current build)

### Scaffold
- [x] Project skeleton (`backend/`, `frontend/`, `docs/`, root docs)
- [x] `backend/pyproject.toml` (Python 3.12, deps: pymorphy3, fastapi, uvicorn, pyyaml, pytest)
- [x] `frontend/` Vite + Svelte 5 + TypeScript scaffold
- [x] `.gitignore` for both stacks

### Core puzzle logic
- [x] `alphabet.py` — 31-letter alphabet constant, Ё/Е normalization, bitmask helpers
- [x] Stub lemma list (~300 hand-picked words covering several POS) at `backend/data/stub_lemmas.tsv`
- [x] `dictionary.py` — loads lemmas + per-lemma metadata from TSV or SQLite
- [x] `lemmatizer.py` — pymorphy3 wrapper, ambiguity rule, lemma-resolution lookup
- [x] `scoring.py` — length-based points, +7 pangram bonus, rank thresholds
- [x] `generator.py` — weighted letter sampling, candidate enumeration, constraint enforcement, deterministic under seed
- [x] Unit tests for each module — **47 passing**

### API + UI
- [x] `store.py` — SQLite layer for the read-only `lemmas` table (puzzle CRUD lives in `state_store.py`)
- [x] `state_store.py` — Protocol with `LocalSqliteStateStore` + `TursoStateStore` implementations; picks via env vars
- [x] `api.py` — FastAPI with `GET /api/puzzle/current`, `GET /api/puzzle/{id}`, `POST /api/puzzle/{id}/guess`, `POST /api/admin/generate`, `GET /api/health`
- [x] Four API statuses surfaced: `accepted`, `already_found`, `not_in_set`, `unparseable`
- [x] API tests (6, all passing)
- [x] Svelte components: `Hive`, `Input`, `FoundList`, `RankBar`, `Toast`, `NewGame`
- [x] `lib/api.ts` + `lib/store.svelte.ts` + `lib/persist.ts` (localStorage by puzzle id)
- [x] End-to-end manual play verified in browser

### Real dictionary
- [x] `scripts/build_dictionary.py` — fetches `Freq2011.zip` from `dict.ruslang.ru`, extracts and parses
- [x] Intersects L–S lemmas with OpenCorpora via pymorphy3 round-trip check
- [x] Filters ≥0.5 ipm; closed-class POS, hyphenated, non-alphabet, proper nouns all dropped
- [x] **Yo-recovery:** `alphabet.canonical_lemma` rewrites raw freq-list lemmas the source spells without ё (e.g. `ребенок` 658 ipm) to pymorphy3's ё-form before the freq-sum dedup; rescued ~1,200 lemmas including `ребёнок`, `ёлка`, `лёд`, `весёлый`, `чёрный`
- [x] Writes compiled lemma table to SQLite (42,856 rows from L–S 2011)
- [x] API auto-prefers DB-backed dictionary when present; falls back to stub TSV

### Overrides
- [x] `backend/data/overrides.yaml` with `include` / `exclude` / `aliases`; seeded with 27 diminutives
- [x] `overrides.py`: `apply_to_rows` (build script) + `apply_to_dictionary` (API startup)
- [x] `normalize()` routes include/exclude/alias-values through `canonical_lemma` so authors can spell entries with or without ё
- [x] Live dictionary holds 42,856 lemmas after overrides (overrides pre-applied at build time)

### Dynamic difficulty (top-N)
- [x] `top_n` field on `GeneratorConfig`; `generate()` filters the dictionary to top-N by freq before sampling
- [x] `POST /admin/generate` accepts `top_n` (+ optional `min_lemmas`/`max_lemmas`/`require_pangram`/`seed`)
- [x] API auto-relaxes `min_lemmas` and pangram floor when `top_n ≤ 5000` so small pools stay satisfiable
- [x] `NewGame.svelte` dropdown with 4 presets (Лёгкий / Средний / Сложный / Эксперт), selection persists

### UX (initial pass — refined further in the upcoming UX session)
- [x] Three distinct rejection toasts wired to API status codes
- [x] Pangram detection + "Панграмма!" toast variant with +7 callout
- [x] 9-pip rank strip with current label
- [x] Shuffle / delete-last / enter / clear controls
- [x] Tap-on-hive routes letter to input

---

## Future / deferred

Everything below is **out of scope for the current build** but worth preserving so we don't lose the design intent.

### Family + sharing
- [-] Shared scoreboard: per-day per-player rank, who's reached Гений
- [-] Daily-puzzle rollover + timezone choice
- [-] Weekly summary (most Гений days, average score, words only one person found)
- [-] Shared *новые слова* list with weekly digest
- [-] Name-based auth (no password)

### Single-player extensions
- [-] Yesterday's puzzle viewer + past results
- [-] End-of-day missed-words review with one-line definitions
- [-] "Сохранить слово" personal vocabulary affordance
- [-] Hints grid (words-by-letter, two-letter starters)
- [-] "Редкое слово" badge for lemmas below 1 ipm
- [-] Single "show me one word I missed" reveal per day

### Hosting / ops
- [x] Decide deployment target — bundled Docker Space on Hugging Face (free CPU tier)
- [x] Persist generated puzzles across restarts — Turso libsql via `state_store.py`
- [x] One-command redeploy (`scripts/deploy_hf.sh`)
- [ ] Tighten `allow_origins` in `api.py` from `["*"]` to the Space's known origin
- [-] Weekly puzzle pre-generation cron
- [-] Light editorial pass workflow (review queued puzzles before they go live)

### Tunable / observational (re-evaluate after play data)
- [-] Whether aspect pairs (читать / прочитать) should remain separate or merge when prefix is semantically vacuous
- [-] Whether Гений at 100% is achievable in Russian; consider 90% + Queen Bee badge
- [-] Whether to expose hints at all to fluent players (in-family A/B)
