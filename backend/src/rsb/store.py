"""SQLite-backed storage for the compiled lemma table.

This module is now lemma-only. Puzzle CRUD lives in `state_store.py`, which
can run against either local SQLite (ephemeral) or Turso (durable) depending
on whether TURSO_* env vars are set.

The lemma table is compiled by `scripts/build_dictionary.py` and is **read-
only at runtime**. In the Docker image it's baked in; locally it sits at
`backend/data/rsb.db`. Schema migrations live below — bump `SCHEMA_VERSION`
when adding columns.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 4


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS lemmas (
            lemma      TEXT    NOT NULL PRIMARY KEY,
            pos        TEXT    NOT NULL,
            freq_ipm   REAL    NOT NULL,
            mask       INTEGER NOT NULL,
            form_masks TEXT,
            forms      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_lemmas_freq ON lemmas(freq_ipm);
        CREATE TABLE IF NOT EXISTS aliases (
            source_lemma TEXT NOT NULL PRIMARY KEY,
            target_lemma TEXT NOT NULL,
            rule         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_aliases_target ON aliases(target_lemma);
        """
    )
    # Migrations: add form_masks (pre-v2) and forms (pre-v4) columns. The
    # aliases table is idempotently created above for pre-v3 DBs. The legacy
    # `form_masks` column is retained for old-DB compatibility but no longer
    # written — `form_masks` is now derived from the `forms` strings at load.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(lemmas)").fetchall()}
    if "form_masks" not in cols:
        conn.execute("ALTER TABLE lemmas ADD COLUMN form_masks TEXT")
    if "forms" not in cols:
        conn.execute("ALTER TABLE lemmas ADD COLUMN forms TEXT")
    cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version(version) VALUES(?)", (SCHEMA_VERSION,))
    else:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()


def _encode_forms(forms: frozenset[str] | set[str] | tuple[str, ...]) -> str:
    # Russian form strings never contain commas, so a comma join is safe.
    return ",".join(sorted(forms))


def _decode_forms(s: str | None) -> frozenset[str]:
    if not s:
        return frozenset()
    return frozenset(s.split(","))


def open_db(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


# ---------- lemmas table ---------------------------------------------------


def count_lemmas(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM lemmas").fetchone()["c"]


def replace_lemmas(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, float, int]] | list[tuple[str, str, float, int, frozenset[str]]],
) -> None:
    """Truncate-and-insert. Each row is either (lemma, pos, freq_ipm, mask)
    or (lemma, pos, freq_ipm, mask, forms) where `forms` is the set of
    inflected form *strings*. The 4-tuple form is accepted for backwards
    compatibility — `forms` is then left NULL and re-enumerated on first read.
    `form_masks` is derived from `forms` at load and is no longer written."""
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM lemmas")
        normalized: list[tuple[str, str, float, int, str | None]] = []
        for row in rows:
            if len(row) == 4:
                normalized.append((*row, None))
            else:
                lemma, pos, freq, mask, forms = row
                normalized.append((lemma, pos, freq, mask, _encode_forms(forms)))
        conn.executemany(
            "INSERT INTO lemmas(lemma, pos, freq_ipm, mask, forms) VALUES (?, ?, ?, ?, ?)",
            normalized,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def iter_lemmas(conn: sqlite3.Connection):
    """Yield (lemma, pos, freq_ipm, mask, forms) tuples. `forms` is a
    frozenset[str] — empty if the column is NULL (legacy pre-v4 row, which
    Dictionary.from_db then re-enumerates and writes back)."""
    for row in conn.execute("SELECT lemma, pos, freq_ipm, mask, forms FROM lemmas"):
        yield (
            row["lemma"],
            row["pos"],
            row["freq_ipm"],
            row["mask"],
            _decode_forms(row["forms"]),
        )


def update_forms_bulk(
    conn: sqlite3.Connection,
    entries: list[tuple[str, frozenset[str]]],
) -> None:
    """Set `forms` for the given lemmas. Used by Dictionary.from_db to persist
    the one-time migration of legacy rows that predate stored form strings."""
    conn.execute("BEGIN")
    try:
        conn.executemany(
            "UPDATE lemmas SET forms = ? WHERE lemma = ?",
            [(_encode_forms(f), lemma) for lemma, f in entries],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ---------- aliases table --------------------------------------------------


def replace_aliases(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, str]],
) -> None:
    """Truncate-and-insert lemma→lemma aliases. Each row is
    (source_lemma, target_lemma, rule_id). Written by the build pipeline
    after `rsb.folds.compute_folds`."""
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM aliases")
        conn.executemany(
            "INSERT INTO aliases(source_lemma, target_lemma, rule) VALUES (?, ?, ?)",
            rows,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def load_aliases(conn: sqlite3.Connection) -> dict[str, str]:
    """Return the lemma→lemma alias map. Empty dict if the table is empty.
    Used by `Lemmatizer` to fall back from an unmatched parse to its aliased
    target (e.g. *наедать* → *наедаться*)."""
    return {
        row["source_lemma"]: row["target_lemma"]
        for row in conn.execute("SELECT source_lemma, target_lemma FROM aliases")
    }


def count_aliases(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM aliases").fetchone()["c"]
