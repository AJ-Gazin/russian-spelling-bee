# Russian Spelling Bee

A Spelling-Bee-style daily Russian puzzle. The central design move is **lemma-level scoring**: any inflected form a player types is mapped to its dictionary headword via pymorphy3 and credited once, so the puzzle isn't dominated by Russian inflection.

> **If you're joining this project fresh:** start by reading [`STATUS.md`](STATUS.md) — it's the canonical, in-sync description of what's actually live on this branch. The [`todo.md`](todo.md) is the work queue. The original planning document at [`docs/original-design.md`](docs/original-design.md) is preserved for context but is **not** canonical — where it diverges from `STATUS.md`, `STATUS.md` wins.

---

## Layout

```
Dockerfile          Multi-stage (Node build → Python runtime) for the bundled HF Space.
.dockerignore

backend/            Python (uv-managed, Python 3.12). pymorphy3 + FastAPI.
  src/rsb/          Library modules (alphabet, dictionary, lemmatizer, generator,
                    scoring, store, state_store, overrides, api).
  scripts/          build_dictionary.py — fetches L–S frequency list and compiles
                    the lemma table.
  tests/            pytest. 47 passing.
  data/             stub_lemmas.tsv (checked in), overrides.yaml (checked in),
                    rsb.db (gitignored — generated).

frontend/           Svelte 5 + Vite + TypeScript. Single-page app.
  src/lib/          Components and the GameState singleton.

scripts/
  deploy_hf.sh      One-command redeploy to the HF Space.

docs/
  deploy-huggingface.md  Deploy notes (Space, secrets, Turso).
  space.README.md   HF-flavored README copied to the Space root at deploy time.
  original-design.md     Frozen copy of the planning doc.
  benchmarks/

STATUS.md        ← Canonical "what's live on this branch."
todo.md          ← Canonical task list.
```

---

## Running it

Two processes. Run both, then open `http://localhost:5173`.

**Backend** (Python 3.12 + uv):

```sh
cd backend
uv sync                                      # first time only
uv run python scripts/build_dictionary.py    # one-time: fetches L–S, compiles ~42k lemmas into SQLite (~30s)
uv run uvicorn rsb.api:app --reload          # dev server on :8000
uv run pytest                                # 47 tests
```

If `build_dictionary.py` hasn't been run yet, the API falls back to the small hand-curated stub at `backend/data/stub_lemmas.tsv`. The auto-generated puzzles will be tiny but the play loop works.

**Frontend** (Node + Vite):

```sh
cd frontend
npm install                                  # first time only
npm run dev                                  # dev server on :5173, proxies /api to :8000
npm run check                                # svelte-check (TS errors)
npm run build                                # production build
```

---

## Windows-specific gotchas

These bit me during development; flagged here so you don't pay for them again.

1. **Console UTF-8.** Set `PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`) before any CLI script that prints Cyrillic. Not needed for the API server itself, but needed for `build_dictionary.py` and any ad-hoc Python you run from the shell.
2. **Zombie uvicorn after killing the parent shell.** On Windows, killing the bash/PowerShell process that spawned uvicorn does **not** kill uvicorn — it keeps holding port 8000. Subsequent `uvicorn` starts then fail to bind, but the failure can look like "stale data" because the old process keeps responding. If you see this: `Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }`. Prefer starting uvicorn via PowerShell `Start-Process -PassThru` and tracking the PID, rather than via a shell wrapper.
3. **`npm` is a `.cmd` shim.** PowerShell `Start-Process npm ...` fails with "%1 is not a valid Win32 application." Use `Start-Process cmd.exe -ArgumentList '/c','npm',...` or call `npm` from a normal console.

---

## API at a glance

All routes are namespaced under `/api`:

| Method | Path | Body | Returns |
|---|---|---|---|
| GET  | `/api/health`                |  | `{status, state_store}` |
| GET  | `/api/puzzle/current`        |  | current puzzle |
| GET  | `/api/puzzle/{id}`           |  | a specific stored puzzle |
| POST | `/api/puzzle/{id}/guess`     | `{form, found_lemmas}` | `{status, lemma?, points?, is_pangram?, candidates}` |
| POST | `/api/admin/generate`        | `{top_n?, min_lemmas?, max_lemmas?, require_pangram?, seed?}` | a new stored puzzle |

`status` ∈ {`accepted`, `already_found`, `not_in_set`, `unparseable`}. The frontend talks to all of these via the Vite `/api` proxy in dev, and directly (same origin) in production.

---

## Deploy

Live at https://ajgazin-russian-spelling-bee.hf.space — a Hugging Face Space (Docker SDK) that bundles the Svelte SPA and FastAPI backend in a single image. Generated puzzles persist to a [Turso](https://turso.tech) libsql DB across Space restarts.

One-command redeploy from repo root:

```sh
scripts/deploy_hf.sh
```

Full notes: [`docs/deploy-huggingface.md`](docs/deploy-huggingface.md).

---

## Scope reminder

Single-player today. Multi-player / family / daily-rollover features are still out of scope and live in the `todo.md` "Future / deferred" section.
