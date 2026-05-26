#!/usr/bin/env bash
# Push the project to the bundled HF Space (frontend + backend in one image).
#
# Why staging: `hf upload <dir>` chokes on directories containing .venv even
# with --exclude (Git Bash glob translation + Click positional parsing). The
# robust fix is to assemble a clean tree in tmp and upload from there.
#
# Usage (from repo root):  scripts/deploy_hf.sh
# Requires:                hf (logged in), HF_SPACE in env, or default below.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HF_SPACE="${HF_SPACE:-ajgazin/russian-spelling-bee}"
COMMIT_MSG="${COMMIT_MSG:-redeploy: $(date -u +%Y-%m-%dT%H:%M:%SZ)}"

cd "$REPO_ROOT"

stage="$(mktemp -d -t hf-stage-XXXXXX)"
trap 'rm -rf "$stage"' EXIT
echo "==> staging to $stage"

# Root: Dockerfile, .dockerignore, HF-flavored README.
cp Dockerfile .dockerignore "$stage/"
cp docs/space.README.md "$stage/README.md"

# Backend: source + scripts + small data files. NO .venv, tests, generated DBs.
mkdir -p "$stage/backend/data" "$stage/backend/src" "$stage/backend/scripts"
cp backend/pyproject.toml backend/uv.lock "$stage/backend/"
cp -r backend/src/rsb "$stage/backend/src/"
cp -r backend/scripts/. "$stage/backend/scripts/"
cp backend/data/stub_lemmas.tsv backend/data/overrides.yaml "$stage/backend/data/"
find "$stage/backend" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Frontend: source only. Docker stage 1 will `npm ci` + `npm run build`.
mkdir -p "$stage/frontend"
cp frontend/package.json frontend/package-lock.json "$stage/frontend/"
cp frontend/svelte.config.js frontend/tsconfig.json frontend/vite.config.ts frontend/index.html "$stage/frontend/"
cp -r frontend/src "$stage/frontend/"

echo "==> staged tree:"
( cd "$stage" && find . -type f | sort )
echo "==> $(du -sh "$stage" | cut -f1) total"

echo "==> uploading to $HF_SPACE"
( cd "$stage" && hf upload "$HF_SPACE" . . --type space --commit-message "$COMMIT_MSG" )

echo "==> done. Watch the build:"
echo "    hf spaces logs $HF_SPACE --build --tail 200"
echo "    Live URL: https://$(echo "$HF_SPACE" | tr '/' '-').hf.space"
