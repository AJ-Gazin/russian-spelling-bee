# Deploying to Hugging Face Spaces

Live: https://ajgazin-russian-spelling-bee.hf.space

The Space bundles the Svelte SPA and the FastAPI backend in a single Docker
image. One image, one URL, no CORS. Generated puzzles persist across Space
restarts via a Turso libsql DB.

## Layout

Repo root → Space root (same shape after `scripts/deploy_hf.sh`):

- `Dockerfile` — multi-stage: `node:20-slim` builds `frontend/` → `python:3.12-slim` installs backend deps, bakes the ~42k-lemma SQLite, copies SPA `dist/` into `./static/`.
- `.dockerignore` — keeps `.venv`, caches, generated DBs out of the build context.
- `README.md` (Space root) — HF frontmatter; the deploy script copies `docs/space.README.md` into place here so the project README at repo root stays unchanged.
- `backend/` — Python source.
- `frontend/` — Svelte source. Docker stage 1 runs `npm ci && npm run build`.

FastAPI mounts the API at `/api/*` and the SPA at `/` (only when `./static/` exists in the cwd). Both share the same origin in production; in dev, Vite proxies `/api/*` to `:8000`.

## One-time setup

### 1. Create the Space

On https://huggingface.co/new-space:

| Field | Value |
|---|---|
| Owner | your HF username |
| Name | `russian-spelling-bee` |
| SDK | **Docker** → **Blank** |
| Hardware | **CPU basic (free)** |
| Visibility | Public |

The Space repo starts empty. We push to it from this project.

### 2. Provision Turso (durable state)

State (generated puzzles, future scores) lives in [Turso](https://turso.tech) — a serverless libsql/SQLite. HF Spaces have ephemeral disks, so without Turso, puzzles vanish on restart.

```sh
# Need the Turso platform API token from https://app.turso.tech/account/api-tokens
export TURSO_API_TOKEN=...

# Create a group (one-time per region)
curl -X POST -H "Authorization: Bearer $TURSO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"default","location":"aws-us-east-1"}' \
  https://api.turso.tech/v1/organizations/<your-org>/groups

# Create the DB
curl -X POST -H "Authorization: Bearer $TURSO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"russian-spelling-bee","group":"default"}' \
  https://api.turso.tech/v1/organizations/<your-org>/databases

# Mint a non-expiring full-access auth token
curl -X POST -H "Authorization: Bearer $TURSO_API_TOKEN" \
  "https://api.turso.tech/v1/organizations/<your-org>/databases/russian-spelling-bee/auth/tokens?expiration=never&authorization=full-access"
```

The DB hostname (e.g. `russian-spelling-bee-<org>.aws-us-east-1.turso.io`) becomes `libsql://<hostname>` for `TURSO_DATABASE_URL`. The minted JWT is `TURSO_AUTH_TOKEN`.

Stash both in the repo's `.env` (gitignored). Also stash `TURSO_API_TOKEN` there for future admin work — never put it in an HF Space secret.

### 3. Set Space secrets

Two **secrets** (sensitive — use secrets, not variables) on the Space:

```sh
hf spaces secrets add <user>/russian-spelling-bee \
  --secrets TURSO_DATABASE_URL=libsql://... TURSO_AUTH_TOKEN=...
```

Or via UI: Space → Settings → Variables and secrets → add both.

If either is missing, the Space silently falls back to ephemeral local SQLite (`GET /api/health` will report `"state_store":"local-sqlite"`).

## Redeploying

From repo root:

```sh
scripts/deploy_hf.sh
```

What it does:

1. Stages a clean tree in `/tmp/hf-stage-...`:
   - `Dockerfile`, `.dockerignore`, `docs/space.README.md` → root (the README is renamed to `README.md`)
   - `backend/{pyproject.toml, uv.lock, src/rsb/, scripts/, data/{stub_lemmas.tsv,overrides.yaml}}`
   - `frontend/{package.json, package-lock.json, svelte.config.js, tsconfig.json, vite.config.ts, index.html, src/}`
2. `hf upload <space> . . --type space`. Single commit on the Space repo.
3. Prints the build-log and live-URL commands.

The staging step is essential — `hf upload <dir>` mishandles a CWD that contains `.venv`. Don't bypass it.

Override target via env vars:

```sh
HF_SPACE=other-user/other-space COMMIT_MSG="fix: ..." scripts/deploy_hf.sh
```

## Watching the build + verifying

```sh
hf spaces logs ajgazin/russian-spelling-bee --build --tail 200
# After build finishes, watch runtime:
hf spaces logs ajgazin/russian-spelling-bee --tail 50

# Smoke test:
curl https://ajgazin-russian-spelling-bee.hf.space/api/health
# {"status":"ok","state_store":"turso"}
```

On Windows, prefix log-tailing commands with `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` — the `hf` CLI's stdout can choke on Cyrillic or `✓` characters with the default cp1252 codepage.

First build takes ~5 min (frontend build + pymorphy3 install + Freq2011 download + lemma compile). Subsequent builds reuse layers; only changed code re-runs.

## Rotating or recreating the Turso DB

```sh
# Mint a new auth token (e.g. after revocation)
curl -X POST -H "Authorization: Bearer $TURSO_API_TOKEN" \
  "https://api.turso.tech/v1/organizations/<your-org>/databases/russian-spelling-bee/auth/tokens?expiration=never&authorization=full-access"

# Wipe + recreate the DB (e.g. schema reset)
curl -X DELETE -H "Authorization: Bearer $TURSO_API_TOKEN" \
  https://api.turso.tech/v1/organizations/<your-org>/databases/russian-spelling-bee
curl -X POST -H "Authorization: Bearer $TURSO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"russian-spelling-bee","group":"default"}' \
  https://api.turso.tech/v1/organizations/<your-org>/databases
```

After either, update `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` in the Space's secrets and restart the Space.

## Operational notes

- **Sleep:** free CPU Spaces auto-sleep after **48 h** of no traffic; first request after sleep cold-starts in ~10–20 s. Turso doesn't sleep.
- **Ephemeral filesystem:** HF resets the disk on restart. The lemma DB is baked into the image so it survives restarts; mutable state must live in Turso.
- **Resources:** 2 vCPU, 16 GB RAM, 50 GB ephemeral disk. Way more than this app needs.
- **Outbound network:** only ports 80/443/8080 are allowed. The build-time download from `http://dict.ruslang.ru` (port 80) works.
- **Factory rebuild:** Space Settings → **Restart this Space** (warm) or **Factory rebuild** (cold — re-runs the Dockerfile from scratch).

## Pointing things at the Space

The frontend is bundled in, so no separate URL config is needed. If you ever split the frontend off (e.g. Cloudflare Pages):

1. Set the frontend API base to `https://ajgazin-russian-spelling-bee.hf.space`.
2. Tighten the backend's CORS allowlist. Currently `backend/src/rsb/api.py` sets `allow_origins=["*"]` — fine for a same-origin bundle but should be the explicit Pages origin once cross-origin.
