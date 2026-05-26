"""SQLite-backed storage for generated puzzles.

A single table for now; will grow when the real-dictionary pipeline lands
(compiled lemma table) and when shared-scoreboard features land (player
scores). Schema migrations are inline below — bump `SCHEMA_VERSION` when
adding columns and apply the migration in `_ensure_schema`.

Puzzle payloads are stored as JSON in a TEXT column. We don't shred the
lemma list into rows because we always load a puzzle whole.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

from .generator import Puzzle, ScoredLemma
from .scoring import RankThresholds, thresholds_for

SCHEMA_VERSION = 2


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS puzzles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            letters      TEXT    NOT NULL,
            center       TEXT    NOT NULL,
            total_points INTEGER NOT NULL,
            payload      TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lemmas (
            lemma      TEXT    NOT NULL PRIMARY KEY,
            pos        TEXT    NOT NULL,
            freq_ipm   REAL    NOT NULL,
            mask       INTEGER NOT NULL,
            form_masks TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_lemmas_freq ON lemmas(freq_ipm);
        """
    )
    # Migration: add form_masks column to pre-v2 DBs.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(lemmas)").fetchall()}
    if "form_masks" not in cols:
        conn.execute("ALTER TABLE lemmas ADD COLUMN form_masks TEXT")
    cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version(version) VALUES(?)", (SCHEMA_VERSION,))
    else:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()


def _encode_form_masks(masks: frozenset[int] | set[int] | tuple[int, ...]) -> str:
    return ",".join(str(m) for m in sorted(masks))


def _decode_form_masks(s: str | None) -> frozenset[int]:
    if not s:
        return frozenset()
    return frozenset(int(x) for x in s.split(","))


def open_db(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


# ---------- serialization ---------------------------------------------------


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


def _puzzle_from_row(row: sqlite3.Row) -> Puzzle:
    raw = json.loads(row["payload"])
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


# ---------- CRUD ------------------------------------------------------------


def save_puzzle(conn: sqlite3.Connection, p: Puzzle) -> int:
    cur = conn.execute(
        "INSERT INTO puzzles(letters, center, total_points, payload) VALUES(?,?,?,?)",
        (p.letters, p.center, p.total_points, _puzzle_to_json(p)),
    )
    pid = cur.lastrowid
    assert pid is not None
    return pid


def get_puzzle(conn: sqlite3.Connection, puzzle_id: int) -> tuple[int, Puzzle] | None:
    row = conn.execute(
        "SELECT id, payload FROM puzzles WHERE id = ?", (puzzle_id,)
    ).fetchone()
    if row is None:
        return None
    return row["id"], _puzzle_from_row(row)


def get_current_puzzle(conn: sqlite3.Connection) -> tuple[int, Puzzle] | None:
    """Latest puzzle by id. 'Current' here means 'the one most recently
    generated' — daily-rollover logic is deferred."""
    row = conn.execute(
        "SELECT id, payload FROM puzzles ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return row["id"], _puzzle_from_row(row)


def list_puzzles(conn: sqlite3.Connection) -> Iterator[tuple[int, str, str, int]]:
    for row in conn.execute(
        "SELECT id, letters, center, total_points FROM puzzles ORDER BY id DESC"
    ):
        yield row["id"], row["letters"], row["center"], row["total_points"]


def count_puzzles(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM puzzles").fetchone()["c"]


# ---------- lemmas table ---------------------------------------------------


def count_lemmas(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM lemmas").fetchone()["c"]


def replace_lemmas(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, float, int]] | list[tuple[str, str, float, int, frozenset[int]]],
) -> None:
    """Truncate-and-insert. Each row is either (lemma, pos, freq_ipm, mask)
    or (lemma, pos, freq_ipm, mask, form_masks). The 4-tuple form is accepted
    for backwards compatibility — form_masks is then left NULL and migrated
    on first read."""
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM lemmas")
        normalized: list[tuple[str, str, float, int, str | None]] = []
        for row in rows:
            if len(row) == 4:
                normalized.append((*row, None))
            else:
                lemma, pos, freq, mask, fm = row
                normalized.append((lemma, pos, freq, mask, _encode_form_masks(fm)))
        conn.executemany(
            "INSERT INTO lemmas(lemma, pos, freq_ipm, mask, form_masks) VALUES (?, ?, ?, ?, ?)",
            normalized,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def iter_lemmas(conn: sqlite3.Connection):
    """Yield (lemma, pos, freq_ipm, mask, form_masks) tuples. `form_masks` is
    a frozenset[int] — empty if the column is NULL (pre-migration row)."""
    for row in conn.execute("SELECT lemma, pos, freq_ipm, mask, form_masks FROM lemmas"):
        yield (
            row["lemma"],
            row["pos"],
            row["freq_ipm"],
            row["mask"],
            _decode_form_masks(row["form_masks"]),
        )


def update_form_masks_bulk(
    conn: sqlite3.Connection,
    entries: list[tuple[str, frozenset[int]]],
) -> None:
    """Set form_masks for the given lemmas. Used by Dictionary.from_db to
    persist the one-time migration of pre-v2 rows."""
    conn.execute("BEGIN")
    try:
        conn.executemany(
            "UPDATE lemmas SET form_masks = ? WHERE lemma = ?",
            [(_encode_form_masks(fm), lemma) for lemma, fm in entries],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
