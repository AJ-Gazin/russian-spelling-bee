"""Mutable game state — puzzles today, scores tomorrow.

Two implementations behind a single Protocol so api.py is oblivious:

  - LocalSqliteStateStore: a local SQLite file. Default. Used in dev and as
    the fallback when no Turso env vars are set. **Ephemeral** on Hugging
    Face Spaces (filesystem resets on restart).
  - TursoStateStore: a remote libsql/Turso database via the `libsql` package.
    Used when both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are set.
    Durable across restarts and across replicas.

The lemma table is a separate concern — it's read-only at runtime, ~42k rows,
~11 MB on disk, and lives in store.py / data/rsb.db (baked into the image at
build time). Don't conflate the two.

To bootstrap a fresh Turso DB:

    turso db create rsb
    turso db tokens create rsb        # paste into HF Space secret TURSO_AUTH_TOKEN
    turso db show rsb --url           # paste into TURSO_DATABASE_URL
    turso db shell rsb < data/turso_schema.sql

(The TursoStateStore also runs CREATE TABLE IF NOT EXISTS on init, so the
shell-script step is optional — but useful for visibility.)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator, Protocol

from .generator import Puzzle, ScoredLemma
from .scoring import RankThresholds


log = logging.getLogger("rsb.state_store")

# Schema is plain SQLite DDL that works identically on libsql/Turso.
PUZZLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS puzzles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    letters      TEXT    NOT NULL,
    center       TEXT    NOT NULL,
    total_points INTEGER NOT NULL,
    payload      TEXT    NOT NULL
);
"""

# Forward-looking: per-player score state. Not used by the current routes,
# but creating the table here means we can ship the migration without a
# separate deploy when scoring lands.
SCORES_SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_id     INTEGER NOT NULL,
    player_id     TEXT    NOT NULL,
    found_lemmas  TEXT    NOT NULL,
    points        INTEGER NOT NULL,
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(puzzle_id, player_id)
);
CREATE INDEX IF NOT EXISTS idx_scores_puzzle ON scores(puzzle_id);
"""


# ---------- serialization (shared by both implementations) ----------------


def _puzzle_to_json(p: Puzzle) -> str:
    return json.dumps(
        {
            "letters": p.letters,
            "center": p.center,
            "lemmas": [asdict(l) for l in p.lemmas],
            "total_points": p.total_points,
            "pangram_count": p.pangram_count,
            "thresholds": {
                "total_points": p.thresholds.total_points,
                "cutoffs": list(p.thresholds.cutoffs),
                "labels": list(p.thresholds.labels),
            },
            "meta": p.meta,
        },
        ensure_ascii=False,
    )


def _puzzle_from_payload(payload: str) -> Puzzle:
    raw = json.loads(payload)
    lemmas = tuple(ScoredLemma(**l) for l in raw["lemmas"])
    th = raw["thresholds"]
    thresholds = RankThresholds(
        total_points=th["total_points"],
        cutoffs=tuple(th["cutoffs"]),
        labels=tuple(th["labels"]),
    )
    return Puzzle(
        letters=raw["letters"],
        center=raw["center"],
        lemmas=lemmas,
        total_points=raw["total_points"],
        pangram_count=raw["pangram_count"],
        thresholds=thresholds,
        meta=raw.get("meta", {}),
    )


# ---------- protocol ------------------------------------------------------


class StateStore(Protocol):
    """The handful of operations api.py needs from the mutable state layer."""

    backend: str  # "local-sqlite" | "turso" — for logging only

    def save_puzzle(self, p: Puzzle) -> int: ...
    def get_puzzle(self, puzzle_id: int) -> tuple[int, Puzzle] | None: ...
    def get_current_puzzle(self) -> tuple[int, Puzzle] | None: ...
    def list_puzzles(self) -> Iterator[tuple[int, str, str, int]]: ...
    def count_puzzles(self) -> int: ...
    def close(self) -> None: ...


# ---------- local SQLite implementation -----------------------------------


class LocalSqliteStateStore:
    """SQLite-backed implementation. Ephemeral on HF Spaces — use only when
    Turso env vars are unset, or in local development.

    Lives in its OWN file (separate from the lemma DB) so the lemma DB can
    stay genuinely read-only at runtime.
    """

    backend = "local-sqlite"

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.Lock()

    @classmethod
    def open(cls, path: Path | str) -> "LocalSqliteStateStore":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(path), isolation_level=None, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(PUZZLES_SCHEMA + SCORES_SCHEMA)
        return cls(conn)

    def save_puzzle(self, p: Puzzle) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO puzzles(letters, center, total_points, payload) VALUES(?,?,?,?)",
                (p.letters, p.center, p.total_points, _puzzle_to_json(p)),
            )
            pid = cur.lastrowid
            assert pid is not None
            return pid

    def get_puzzle(self, puzzle_id: int) -> tuple[int, Puzzle] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, payload FROM puzzles WHERE id = ?", (puzzle_id,)
            ).fetchone()
        if row is None:
            return None
        return row["id"], _puzzle_from_payload(row["payload"])

    def get_current_puzzle(self) -> tuple[int, Puzzle] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, payload FROM puzzles ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return row["id"], _puzzle_from_payload(row["payload"])

    def list_puzzles(self) -> Iterator[tuple[int, str, str, int]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, letters, center, total_points FROM puzzles ORDER BY id DESC"
            ).fetchall()
        for row in rows:
            yield row["id"], row["letters"], row["center"], row["total_points"]

    def count_puzzles(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) AS c FROM puzzles").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ---------- Turso (libsql) implementation ---------------------------------


class TursoStateStore:
    """Remote libsql/Turso implementation.

    Uses INSERT ... RETURNING id (libsql/SQLite both support it) instead of
    cursor.lastrowid, because libsql's lastrowid semantics over HTTP aren't
    something we want to rely on.

    Tuple-based row access (no Row factory in libsql's Python binding as of
    libsql 0.1.x). Indices match the SELECT column order — keep that in sync
    if you edit a query.
    """

    backend = "turso"

    def __init__(self, conn: Any):
        # Conn is libsql.Connection — typed Any to avoid importing libsql
        # at module load time. Callers should go through open() instead.
        self._conn = conn
        self._lock = threading.Lock()

    @classmethod
    def open(cls, url: str, auth_token: str) -> "TursoStateStore":
        try:
            import libsql  # type: ignore[import-not-found]
        except ImportError as e:
            raise RuntimeError(
                "TURSO_DATABASE_URL is set but the `libsql` package is not "
                "installed. Add `libsql` to backend/pyproject.toml dependencies."
            ) from e
        conn = libsql.connect(database=url, auth_token=auth_token)
        # Idempotent — same DDL works on both sqlite3 and libsql.
        for stmt in (PUZZLES_SCHEMA + SCORES_SCHEMA).split(";"):
            s = stmt.strip()
            if s:
                conn.execute(s)
        conn.commit()
        return cls(conn)

    def save_puzzle(self, p: Puzzle) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO puzzles(letters, center, total_points, payload) "
                "VALUES(?,?,?,?) RETURNING id",
                (p.letters, p.center, p.total_points, _puzzle_to_json(p)),
            )
            row = cur.fetchone()
            self._conn.commit()
            assert row is not None, "INSERT RETURNING produced no row"
            return int(row[0])

    def get_puzzle(self, puzzle_id: int) -> tuple[int, Puzzle] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, payload FROM puzzles WHERE id = ?", (puzzle_id,)
            ).fetchone()
        if row is None:
            return None
        return int(row[0]), _puzzle_from_payload(row[1])

    def get_current_puzzle(self) -> tuple[int, Puzzle] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, payload FROM puzzles ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return int(row[0]), _puzzle_from_payload(row[1])

    def list_puzzles(self) -> Iterator[tuple[int, str, str, int]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, letters, center, total_points FROM puzzles ORDER BY id DESC"
            ).fetchall()
        for row in rows:
            yield int(row[0]), row[1], row[2], int(row[3])

    def count_puzzles(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM puzzles").fetchone()
        return int(row[0])

    def close(self) -> None:
        # libsql.Connection has no explicit close in 0.1.x; let GC handle it.
        pass


# ---------- factory -------------------------------------------------------


DEFAULT_LOCAL_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "rsb_state.db"
)


def open_state_store(
    *,
    local_path: Path | str | None = None,
    turso_url: str | None = None,
    turso_token: str | None = None,
) -> StateStore:
    """Pick an implementation based on env vars / explicit args.

    Resolution order:
      1. Explicit `turso_url` + `turso_token` args → TursoStateStore.
      2. TURSO_DATABASE_URL + TURSO_AUTH_TOKEN env vars → TursoStateStore.
      3. Otherwise → LocalSqliteStateStore at `local_path` (or env RSB_STATE_DB,
         or the default `backend/data/rsb_state.db`).

    Test isolation: tests that need a clean DB should pass `local_path=tmp/foo`
    explicitly — relying on env munging is fine but explicit is clearer.
    """
    url = turso_url or os.environ.get("TURSO_DATABASE_URL")
    token = turso_token or os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        log.info("state store: Turso (%s)", _redact(url))
        return TursoStateStore.open(url, token)
    if url and not token:
        log.warning(
            "TURSO_DATABASE_URL set but TURSO_AUTH_TOKEN missing — "
            "falling back to local SQLite"
        )

    path = (
        Path(local_path)
        if local_path is not None
        else Path(os.environ.get("RSB_STATE_DB", DEFAULT_LOCAL_PATH))
    )
    log.info("state store: local SQLite (%s)", path)
    return LocalSqliteStateStore.open(path)


def _redact(url: str) -> str:
    """Strip any embedded credentials for logging."""
    if "@" in url:
        head, tail = url.split("@", 1)
        scheme = head.split("://", 1)[0] if "://" in head else ""
        return f"{scheme}://***@{tail}" if scheme else f"***@{tail}"
    return url
