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
  - "accepted"      with lemma + points + is_pangram + pos + homonym_remaining
  - "already_found" with lemma
  - "not_in_set"    (input parses, but to a lemma not in the puzzle)
  - "unparseable"   (pymorphy3 had nothing for it)

The client sends its found-words list in the POST body as `found_lemmas: [...]`,
keeping the API stateless (server-side per-player state is deferred). The
lemmatizer is `found`-aware: it both reports "already_found" and powers homonym
cycling — when a typed string maps to several in-set lemmas, each call returns
the first not-yet-found one, so re-entering the string walks to the next. The
`homonym_remaining` flag tells the client another homonym is still unfound.
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

    # Load lemma→lemma aliases (produced by `rsb.folds` at dict build time).
    # Empty when the build script hasn't been re-run since folds shipped —
    # the lemmatizer falls back to its pre-folding behavior in that case.
    aliases = store.load_aliases(_state.db)
    if aliases:
        log.info("aliases: %d lemma→lemma entries from folding rules", len(aliases))
    _state.lemmatizer = Lemmatizer(analyzer=morph, aliases=aliases)

    # Mutable game state (puzzles, future scores). Picks Turso if
    # TURSO_DATABASE_URL+TURSO_AUTH_TOKEN are set; otherwise local SQLite.
    _state.state_store = state_store_mod.open_state_store()
    log.info("state store backend: %s", _state.state_store.backend)

    # Auto-generate a starter puzzle if state is empty, so the UI has
    # something to render on first run. The seed becomes the pinned "daily"
    # puzzle — the default a brand-new visitor opens on.
    if _state.state_store.count_puzzles() == 0:
        try:
            p = generate(_state.dictionary, _state.generator_cfg)
            pid = _state.state_store.save_puzzle(p)
            _state.state_store.set_featured(pid)
        except NoPuzzleFound:
            pass
    elif _state.state_store.get_featured_puzzle() is None:
        # Existing DB from before the daily-puzzle feature: pin the latest
        # puzzle as the daily so /api/puzzle/daily has something to serve.
        cur = _state.state_store.get_current_puzzle()
        if cur is not None:
            _state.state_store.set_featured(cur[0])
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


class HistoryEntry(BaseModel):
    """One entry in the recently-played list. Lightweight summary — the full
    puzzle (with lemmas) is fetched on demand via GET /api/puzzle/{id} when the
    player reopens it."""

    id: int
    letters: str
    center: str
    total_points: int
    started_at: str


class GuessRequest(BaseModel):
    form: str = Field(..., min_length=1, max_length=64)
    found_lemmas: list[str] = Field(default_factory=list)


class GuessResponse(BaseModel):
    status: str  # "accepted" | "already_found" | "not_in_set" | "unparseable"
    lemma: str | None = None
    points: int | None = None
    is_pangram: bool | None = None
    candidates: list[str] = Field(default_factory=list)
    # POS of the accepted lemma (e.g. "NOUN", "VERB") — lets the UI disambiguate
    # homonyms (стекло (сущ.) vs стечь (гл.)).
    pos: str | None = None
    # True when the typed string still maps to another in-set lemma the player
    # hasn't found yet — the UI prompts them to enter it again (homonym cycling).
    homonym_remaining: bool = False


class GenerateRequest(BaseModel):
    """Optional body for POST /admin/generate. Empty body ⇒ use server defaults."""

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


@api.get("/puzzle/daily", response_model=PuzzleResponse)
def get_daily() -> PuzzleResponse:
    """The pinned daily/featured puzzle — the default a new visitor opens on.
    Stable: pressing "New Game" does NOT change it (that only rebinds the
    caller's own browser). Re-pin via POST /api/admin/daily/{id}."""
    pair = _state.state_store.get_featured_puzzle()
    if pair is None:
        raise HTTPException(status_code=404, detail="No daily puzzle yet — POST /api/admin/generate")
    return _puzzle_to_response(*pair)


@api.get("/history", response_model=list[HistoryEntry])
def get_history(limit: int = 10) -> list[HistoryEntry]:
    """The last `limit` puzzles that have had at least one word correctly
    guessed, newest first. Global (shared across visitors) and Turso-durable."""
    limit = max(1, min(limit, 50))
    rows = _state.state_store.list_history(limit=limit)
    return [
        HistoryEntry(id=i, letters=l, center=c, total_points=tp, started_at=sa)
        for (i, l, c, tp, sa) in rows
    ]


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

    res = _state.lemmatizer.resolve(req.form, valid_set, found=already)
    if res.status == "accepted":
        # A correct guess enters this puzzle into the recently-played history
        # (idempotent — only the first solve records a row).
        _state.state_store.mark_started(puzzle_id)
        # Pull the scored lemma to return points + pangram flag.
        sl = next(l for l in puzzle.lemmas if l.lemma == res.lemma)
        # Does the same typed string still reach another unfound homonym? If so
        # the client prompts the player to enter it again to cycle to it.
        remaining = [
            r for r in res.reachable if r != res.lemma and r not in already
        ]
        return GuessResponse(
            status="accepted",
            lemma=sl.lemma,
            points=sl.points,
            is_pangram=sl.is_pangram,
            pos=sl.pos,
            candidates=list(res.candidates),
            homonym_remaining=bool(remaining),
        )
    if res.status == "already_found":
        return GuessResponse(status="already_found", lemma=res.lemma)
    if res.status == "not_in_set":
        return GuessResponse(status="not_in_set", candidates=list(res.candidates))
    return GuessResponse(status="unparseable")


@api.post("/admin/generate", response_model=PuzzleResponse)
def admin_generate(req: GenerateRequest | None = None) -> PuzzleResponse:
    cfg = _state.generator_cfg
    if req is not None:
        overrides: dict[str, Any] = {}
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


@api.post("/admin/daily/{puzzle_id}", response_model=PuzzleResponse)
def admin_set_daily(puzzle_id: int) -> PuzzleResponse:
    """Pin an existing puzzle as the daily/featured default for new visitors."""
    pair = _state.state_store.get_puzzle(puzzle_id)
    if pair is None:
        raise HTTPException(status_code=404, detail=f"No puzzle with id {puzzle_id}")
    _state.state_store.set_featured(puzzle_id)
    return _puzzle_to_response(*pair)


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
