# Russian Spelling Bee — bundled deploy for Hugging Face Spaces (Docker SDK).
#
# Stage 1 builds the Svelte SPA with Node; stage 2 runs FastAPI under Python
# and serves the built dist/ at "/". API routes are namespaced under /api/*
# so the SPA never shadows them.
#
# HF Spaces conventions (https://huggingface.co/docs/hub/spaces-sdks-docker):
#  - Containers run as uid 1000; create the user first, COPY --chown=user.
#  - Default port 7860; overridable via app_port in README frontmatter.
#  - Ephemeral filesystem — anything mutable must live in Turso (see
#    backend/src/rsb/state_store.py). The lemma DB is baked at build time.

# ---- stage 1: Svelte build ------------------------------------------------
FROM node:20-slim AS frontend-build
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build
# -> /build/dist

# ---- stage 2: Python runtime ---------------------------------------------
FROM python:3.12-slim

RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/home/user/app/.venv

WORKDIR $HOME/app

RUN pip install --no-cache-dir --user uv==0.5.*

# Backend dependencies first (cached layer).
COPY --chown=user backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Backend source + small data files.
COPY --chown=user backend/src/ ./src/
COPY --chown=user backend/scripts/ ./scripts/
COPY --chown=user backend/data/stub_lemmas.tsv backend/data/overrides.yaml ./data/

# Install the project itself so `rsb.api` is importable.
RUN uv sync --frozen --no-dev

# Compile the real ~42k-lemma dictionary. Allowed to fail soft — api.py
# falls back to the stub TSV at startup if rsb.db is missing or empty.
RUN uv run python scripts/build_dictionary.py \
    || echo "WARN: dictionary build failed; runtime will fall back to stub TSV"

# Drop the built SPA where api.py expects it (./static, mounted at "/").
COPY --from=frontend-build --chown=user /build/dist ./static

EXPOSE 7860

CMD ["sh", "-c", "uv run uvicorn rsb.api:app --host 0.0.0.0 --port ${PORT:-7860}"]
