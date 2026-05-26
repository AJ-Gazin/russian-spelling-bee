"""FastAPI app exposing the puzzle API and (in deployed builds) the static SPA.

API endpoints — all under `/api`:
  GET  /api/puzzle/current             → the most recent puzzle (auto-generated
                                          on first request if the DB is empty).
  GET  /api/puzzle/{puzzle_id}         → a specific puzzle.
  POST /api/puzzle/{puzzle_id}/guess   → resolve a typed form against the puzzle.
  POST /api/admin/generate             → generate a new puzzle and store it.
  GET  /api/health                     → liveness probe (for HF health checks).

Static SPA — when `./static/` exists (built `frontend/dist/` copied into the
Docker image at build time), it's mounted at `/`. `/docs`, `/openapi.json`,
and `/api/*` resolve first, so the SPA only catches the rest. In local dev
the static dir is absent and `/` simply 404s; use Vite (`npm run dev` at
:5173) which proxies `/api` to this server at :8000.

The /guess response uses one of four statuses:
  - "accepted"      with lemma + points + is_pangram
  - "already_found" with lemma  (caller's responsibility — see below)
  - "not_in_set"    (input parses, but to a lemma not in the puzzle)
  - "unparseable"   (pymorphy3 had nothing for it)

`already_found` is detected client-side from the local found-words list, *or*
sent in the POST body as `found_lemmas: [...]`. Sending it from the client keeps
the API stateless. (Server-side per-player state is deferred.)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .dictionary import Dictionary
from .generator import GeneratorConfig, NoPuzzleFound, Puzzle, generate
from .lemmatizer import Lemmatizer
from .overrides import apply_to_dictionary, load as load_overrides, normalize as normalize_overrides
from . import store
from . import state_store as state_store_mod


# ---------- paths -----------------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = BACKEND_ROOT / "data" / "rsb.db"
DEFAULT_LEMMAS = BACKEND_ROOT / "data" / "stub_lemmas.tsv"
DEFAULT_OVERRIDES = BACKEND_ROOT / "data" / "overrides.yaml"


# ---------- app state -------------------------------------------------------

class State:
    def __init__(self) -> None:
        self.db = None
        self.state_store: state_store_mod.StateStore | None = None
        self.dictionary: Dictionary | None = None
        self.lemmatizer: Lemmatizer | None = None
        self.generator_cfg = _DEFAULT_STUB_CFG  # overwritten in lifespan once dict source is known


# Planning-doc defaults: tight, real-dictionary mode.
_DEFAULT_REAL_CFG = GeneratorConfig(
    min_lemmas=25,
    max_lemmas=70,
    require_pangram=True,
    pangram_freq_floor=2.0,
    dominance_cap=0.25,
    max_attempts=4000,
)
# Loose, stub-mode fallback so a fresh checkout without the real dictionary
# still produces *something* playable.
_DEFAULT_STUB_CFG = GeneratorConfig(
    min_lemmas=8,
    max_lemmas=200,
    require_pangram=False,
    pangram_freq_floor=0.0,
    dominance_cap=0.50,
    max_attempts=4000,
)

_state = State()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import logging
    log = logging.getLogger("rsb")
    db_path = os.environ.get("RSB_DB", str(DEFAULT_DB))
    lemmas_path = os.environ.get("RSB_LEMMAS", str(DEFAULT_LEMMAS))
    _state.db = store.open_db(db_path)

    # Prefer the compiled SQLite lemma table (built by scripts/build_dictionary.py)
    # over the stub TSV. The stub stays as a fallback so a fresh dev environment
    # has something to play with even before the build pipeline has been run.
    if store.count_lemmas(_state.db) > 0:
        _state.dictionary = Dictionary.from_db(_state.db)
        _state.generator_cfg = _DEFAULT_REAL_CFG
        log.info("dictionary: DB-backed, %d lemmas", len(_state.dictionary))
    else:
        _state.dictionary = Dictionary.from_tsv(lemmas_path)
        _state.generator_cfg = _DEFAULT_STUB_CFG
        log.info("dictionary: stub TSV, %d lemmas (run scripts/build_dictionary.py for real)", len(_state.dictionary))

    # Single shared MorphAnalyzer: normalize_overrides + Lemmatizer both need
    # one, and a fresh instance is ~30MB / ~200ms to load.
    import pymorphy3
    morph = pymorphy3.MorphAnalyzer()

    # Apply overrides on every startup. Cheap, and lets a fresh `exclude` take
    # effect without rebuilding the DB. Normalize ё in include/exclude keys
    # first so authors can write `exclude: [ребенок]` and it still matches the
    # DB entry "ребёнок".
    ov_path = os.environ.get("RSB_OVERRIDES", str(DEFAULT_OVERRIDES))
    overrides = load_overrides(ov_path)
    overrides = normalize_overrides(overrides, morph)
    before = len(_state.dictionary)
    _state.dictionary = apply_to_dictionary(_state.dictionary, overrides)
    log.info("overrides: include=%d exclude=%d net=%+d (now %d)",
             len(overrides.include), len(overrides.exclude),
             len(_state.dictionary) - before, len(_state.dictionary))

    _state.lemmatizer = Lemmatizer(analyzer=morph)

    # Mutable game state (puzzles, future scores). Picks Turso if
    # TURSO_DATABASE_URL+TURSO_AUTH_TOKEN are set; otherwise local SQLite.
    _state.state_store = state_store_mod.open_state_store()
    log.info("state store backend: %s", _state.state_store.backend)

    # Auto-generate a starter puzzle if state is empty, so the UI has
    # something to render on first run.
    if _state.state_store.count_puzzles() == 0:
        try:
            p = generate(_state.dictionary, _state.generator_cfg)
            _state.state_store.save_puzzle(p)
        except NoPuzzleFound:
            pass
    yield
    _state.state_store.close()
    _state.db.close()


app = FastAPI(title="Russian Spelling Bee", lifespan=lifespan)

# Permissive CORS for local dev; tighten when deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- schemas ---------------------------------------------------------

class PuzzleResponse(BaseModel):
    id: int
    letters: str
    center: str
    total_points: int
    pangram_count: int
    lemmas: list[dict[str, Any]]
    thresholds: dict[str, Any]


class GuessRequest(BaseModel):
    form: str = Field(..., min_length=1, max_length=64)
    found_lemmas: list[str] = Field(default_factory=list)


class GuessResponse(BaseModel):
    status: str  # "accepted" | "already_found" | "not_in_set" | "unparseable"
    lemma: str | None = None
    points: int | None = None
    is_pangram: bool | None = None
    candidates: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    """Optional body for POST /admin/generate. Empty body ⇒ use server defaults."""

    top_n: int | None = Field(
        default=None,
        ge=200,
        le=200000,
        description="Restrict the lemma pool to the top-N most frequent lemmas. None ⇒ full dictionary.",
    )
    min_lemmas: int | None = Field(default=None, ge=4, le=300)
    max_lemmas: int | None = Field(default=None, ge=4, le=300)
    require_pangram: bool | None = None
    seed: int | None = None


# ---------- helpers ---------------------------------------------------------

def _puzzle_to_response(pid: int, p: Puzzle) -> PuzzleResponse:
    return PuzzleResponse(
        id=pid,
        letters=p.letters,
        center=p.center,
        total_points=p.total_points,
        pangram_count=p.pangram_count,
        lemmas=[asdict(l) for l in p.lemmas],
        thresholds={
            "total_points": p.thresholds.total_points,
            "cutoffs": list(p.thresholds.cutoffs),
            "labels": list(p.thresholds.labels),
        },
    )


# ---------- routes ----------------------------------------------------------

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. HF Spaces' default health check pings `/` (which the SPA
    answers); this gives an explicit API-side probe for monitoring."""
    backend = _state.state_store.backend if _state.state_store else "uninitialized"
    return {"status": "ok", "state_store": backend}


@api.get("/puzzle/current", response_model=PuzzleResponse)
def get_current() -> PuzzleResponse:
    pair = _state.state_store.get_current_puzzle()
    if pair is None:
        raise HTTPException(status_code=404, detail="No puzzle yet — POST /api/admin/generate")
    return _puzzle_to_response(*pair)


@api.get("/puzzle/{puzzle_id}", response_model=PuzzleResponse)
def get_one(puzzle_id: int) -> PuzzleResponse:
    pair = _state.state_store.get_puzzle(puzzle_id)
    if pair is None:
        raise HTTPException(status_code=404, detail=f"No puzzle with id {puzzle_id}")
    return _puzzle_to_response(*pair)


@api.post("/puzzle/{puzzle_id}/guess", response_model=GuessResponse)
def guess(puzzle_id: int, req: GuessRequest) -> GuessResponse:
    pair = _state.state_store.get_puzzle(puzzle_id)
    if pair is None:
        raise HTTPException(status_code=404, detail=f"No puzzle with id {puzzle_id}")
    _, puzzle = pair

    valid_set = {l.lemma for l in puzzle.lemmas}
    already = set(req.found_lemmas)

    res = _state.lemmatizer.resolve(req.form, valid_set)
    if res.status == "accepted":
        if res.lemma in already:
            return GuessResponse(status="already_found", lemma=res.lemma)
        # Pull the scored lemma to return points + pangram flag.
        sl = next(l for l in puzzle.lemmas if l.lemma == res.lemma)
        return GuessResponse(
            status="accepted",
            lemma=sl.lemma,
            points=sl.points,
            is_pangram=sl.is_pangram,
            candidates=list(res.candidates),
        )
    if res.status == "not_in_set":
        # Did the user type a form of an already-found lemma? Treat as already_found
        # — friendlier than "слова нет в наборе" when they just retyped a synonym form.
        for cand in res.candidates:
            if cand in already:
                return GuessResponse(status="already_found", lemma=cand)
        return GuessResponse(status="not_in_set", candidates=list(res.candidates))
    return GuessResponse(status="unparseable")


@api.post("/admin/generate", response_model=PuzzleResponse)
def admin_generate(req: GenerateRequest | None = None) -> PuzzleResponse:
    cfg = _state.generator_cfg
    if req is not None:
        overrides: dict[str, Any] = {}
        if req.top_n is not None:
            overrides["top_n"] = req.top_n
            # Smaller pools rarely satisfy the 25-lemma floor, so soften it
            # proportionally unless the caller explicitly set it.
            if req.min_lemmas is None and req.top_n <= 5000:
                overrides["min_lemmas"] = max(8, min(25, req.top_n // 200))
            # Same for pangram requirement: low top_n hives often have no
            # pangram with freq ≥ 2 ipm. Drop the floor for small pools.
            if req.require_pangram is None and req.top_n <= 5000:
                overrides["pangram_freq_floor"] = 0.0
        if req.min_lemmas is not None:
            overrides["min_lemmas"] = req.min_lemmas
        if req.max_lemmas is not None:
            overrides["max_lemmas"] = req.max_lemmas
        if req.require_pangram is not None:
            overrides["require_pangram"] = req.require_pangram
        if req.seed is not None:
            overrides["seed"] = req.seed
        if overrides:
            cfg = replace(cfg, **overrides)
    try:
        p = generate(_state.dictionary, cfg)
    except NoPuzzleFound as e:
        raise HTTPException(status_code=503, detail=str(e))
    pid = _state.state_store.save_puzzle(p)
    return _puzzle_to_response(pid, p)


app.include_router(api)


# ---------- static frontend -------------------------------------------------
# In the production image, the Dockerfile copies the built Svelte SPA to
# ./static (relative to this module's parents[2] — i.e. /home/user/app/static
# in the container). In local dev that directory is absent; we mount it only
# when present so the API is still runnable standalone.
#
# IMPORTANT: this mount must come AFTER include_router and after FastAPI's
# auto-routes (/docs, /openapi.json). StaticFiles at "/" otherwise shadows them.

_STATIC_DIR = BACKEND_ROOT / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")
