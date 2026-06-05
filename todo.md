# Russian Spelling Bee — to-do list

Canonical, hand-maintained task list. Tracks both in-flight work and deferred items. Cross-references to design state belong in [`STATUS.md`](STATUS.md); the original (frozen) planning document is at [`docs/original-design.md`](docs/original-design.md).

Conventions:
- `[ ]` open, `[x]` done, `[~]` in progress, `[-]` deferred / out of current scope.
- Anything checked here should also be reflected in `STATUS.md` if it changes user-visible behavior.

---

## Next up — UI / UX audit & polish (separate session)

A dedicated session will own the visual / interaction pass over the frontend. Specific known issues (not exhaustive — audit needed):

- [ ] Header layout: title line can wrap awkwardly on narrow viewports
- [ ] Accept toast doesn't show *form → lemma* even though `Toast.svelte` supports it — `game.guess()` needs to thread the raw `form` into the toast (`lib/store.svelte.ts`)
- [ ] Rank pip strip looks plain against real puzzle score distributions
- [ ] Hive typography (Georgia) is functional but unopinionated
- [ ] `already_found` toast visually indistinguishable from typo rejection
- [ ] Empty-state / error rendering when the API errors or returns 404
- [ ] Mobile / narrow-viewport pass

All frontend code lives in `frontend/src/`. Start with `App.svelte` → `lib/store.svelte.ts` → each component.

---

## Loose ends in the current build

Small backend items that aren't blocking but should be revisited:

- [ ] Per-letter rare-letter floors (Ф Ц Щ Э rotation guarantees) — currently best-effort via frequency weights only
- [ ] Lemmatizer consults `aliases` from `overrides.yaml` — currently the section is loaded but unused (no real-world hits today; trivial to plumb when needed)
- [ ] **Generator calibration after form-fitness:** the form-level fitness rule admits more lemmas per hive than the old citation-form rule. Re-tune `min_lemmas` / `max_lemmas` bands once we have play data on real puzzles.

---

## Per-POS folding rules

Full writeup of what ships, what doesn't, and how to judge a new rule without being a linguist: [`docs/folding-rules.md`](docs/folding-rules.md). Per-build diff at `backend/data/fold-report.md`.

- [x] **Participles → parent verb.** Top-parse PRTF + candidate POS=ADJF + parent VERB in dict + freq < 20 ipm. 81 merged today; 7 protected by cutoff. Lexicalized participles (`бывший`, `следующий`, `текущий`, `грядущий`, `будущий`) automatically excluded because pymorphy3 ranks them as ADJF at top.
- [x] **Reflexives** (`X+ся ↔ X`). Bidirectional alias, gated by `pymorphy3.dictionary.word_is_known` so we don't add aliases for partner verbs pymorphy3 over-generates. 2,893 aliases today (424 base→reflexive incl. **`наедать → наедаться`**, 2,469 reflexive→base). The `наедал` regression is closed.
- [x] **Adjective short forms.** Top-parse ADJS + candidate POS=ADJF + parent ADJF in dict + freq < 20 ipm. 0 mergers today (L–S doesn't ship pure short-form lemmas); 1 protected (`намерен`). Watchdog rule for future data.
- [x] **Synthetic comparatives.** Top-parse COMP + candidate POS=COMP + parent ADJF in dict. 0 mergers today (L–S has zero COMP lemmas; high-freq comparatives like `больше` are tagged ADVB and protected by the candidate-POS gate). Watchdog rule.
- [-] **Aspect pairs.** *читать* / *прочитать*, *делать* / *сделать*. Deferred. No mechanical prefix rule cleanly separates "vacuous aspectual prefix" from "prefix with semantic load," and suppletive pairs (*говорить* / *сказать*) would need a curated table. See `docs/folding-rules.md`. Revisit if play-data shows players consistently expecting one to credit the other.
- [-] **Productive prefix folding.** Generally unsafe (`наедать` ≠ `есть`, `припомнить` ≠ `помнить`). If dictionary coverage is the real issue, the right tool is a richer frequency source (OpenCorpora-corpus union experiment), not prefix collapsing.
- [-] **Verbal nouns (`-ние` / `-тие`).** Often lexicalize (*понимание* "understanding") so wholesale folding loses nuance. Revisit per play-data.
- [-] **Diminutives.** Curated case-by-case in `overrides.yaml exclude:` (27 entries today). Rule-based folding would over-merge; per-word judgment is correct here.

A reasonable approach for new fold proposals: pick a rule that fits the three-guard template (top-parse + candidate-POS gate + freq cutoff), add a test in `tests/test_folds.py` with both a positive case and a tricky-negative case, run the build, eyeball `data/fold-report.md`, ship.

---

## Answer-key forms + homonyms

- [x] **Constructible forms in the answer key.** Inflected form *strings* stored per lemma (`lemmas.forms`, schema v4; `form_masks` derived from them at load). Generator records each lemma's hive-constructible forms on `ScoredLemma.forms`; API returns them; `AnswersModal.svelte` lists them under each headword so a player learns the typeable form (`сеть`→`сети`, `линь`→`линя`, `лисёнок`→`лисят`) instead of an untypeable citation form.
- [x] **Homonym cycling (Task 3).** `Lemmatizer.resolve(form, valid, found=)` collects all in-set lemmas a homographic string reaches (`Resolution.reachable`) and returns the first not-yet-found, so re-entering the string walks through each homonym (`линял`→`линять`/`линялый`). Guess response carries `pos` + `homonym_remaining`; the UI refills the input and prompts "enter again" with a POS chip. `already_found` is now decided server-side (all reachable found).
- [ ] **Pangram findability / homonym-safety (Task 2 — needs a solution).** The advertised pangram must always be typeable *and* credit the pangram lemma rather than a homonym, while keeping pangram variety as wide as possible. Today pangram detection uses `Lemma.mask` (the citation form) in `generator._score_lemmas`, which guarantees neither. Solution TBD.
- [x] **Dictionary hyperlinks on answers.** Each lemma in the answer key (`AnswersModal`) and the found-words list (`FoundList`) links to `ru.wiktionary.org/wiki/{lemma}`. Styled as invisible links (inherit text color, no underline) with a faint underline on hover — zero visual noise at rest. Opens in new tab.

---

## Word rarity representation

Each lemma already carries `freq_ipm`; now that difficulties are gone and the full lexicon is always in play, we want some way to acknowledge rare words. Form TBD — possibilities include:

- [ ] **Visual indicator in answer key / found list.** A subtle color or symbol (e.g. a gem, a star) for words below a rarity threshold (say < 2 ipm or < 5 ipm). Pure cosmetic reward — "you knew an obscure word."
- [ ] **Scoring bonus for rare words.** Award extra points for low-frequency lemmas — a sliding scale or discrete tiers. Would require recalibrating rank thresholds.
- [ ] **Post-game "rare finds" callout.** A summary section after revealing the answer key that highlights which rare words the player found (and which they missed), framed as a vocabulary-learning moment.

Design constraint: the signal should feel rewarding, not punitive — a player who only knows common words should feel normal, not penalized. The rarity badge is a bonus for vocabulary depth, not a mark of failure for its absence.

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
- [x] **Folding rules** (`rsb.folds`): reflexive alias + 3 merger rules; 2,893 aliases + 81 mergers; schema bumped to v3 with new `aliases` table; see [`docs/folding-rules.md`](docs/folding-rules.md)
- [x] Writes compiled lemma table + aliases table to SQLite (42,775 rows + 2,893 aliases from L–S 2011)
- [x] API auto-prefers DB-backed dictionary when present; falls back to stub TSV

### Overrides
- [x] `backend/data/overrides.yaml` with `include` / `exclude` / `aliases`; seeded with 27 diminutives
- [x] `overrides.py`: `apply_to_rows` (build script) + `apply_to_dictionary` (API startup)
- [x] `normalize()` routes include/exclude/alias-values through `canonical_lemma` so authors can spell entries with or without ё
- [x] Live dictionary holds 42,775 lemmas after overrides + folding (both pre-applied at build time)

### New game
- [x] `POST /admin/generate` accepts optional `min_lemmas`/`max_lemmas`/`require_pangram`/`seed`
- [x] `NewGame.svelte` single button generates a puzzle from the full lexicon

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
- [-] "Редкое слово" badge — subsumed by the "Word rarity representation" section above
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
