"""Load and apply manual overrides from `data/overrides.yaml`.

Three sections:
  - `include`: list of dicts with keys `lemma`, `pos`, `freq_ipm`.
  - `exclude`: list of lemma strings.
  - `aliases`: dict of `surface_form: lemma`.

The build script (`scripts/build_dictionary.py`) calls `apply_to_rows` before
writing to SQLite. The API also calls `apply_to_dictionary` on startup, so
adding an `exclude` entry takes effect on the next API restart without a
full dictionary rebuild.

For now, `aliases` is loaded but not consumed — `Lemmatizer` will read it in
a follow-up change to short-circuit pymorphy3 parsing for known exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from .alphabet import letter_mask
from .dictionary import Dictionary, Lemma


@dataclass(frozen=True, slots=True)
class Overrides:
    include: tuple[Lemma, ...] = ()
    exclude: frozenset[str] = field(default_factory=frozenset)
    aliases: dict[str, str] = field(default_factory=dict)


def load(path: Path | str) -> Overrides:
    path = Path(path)
    if not path.exists():
        return Overrides()
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    inc_raw = data.get("include") or []
    inc: list[Lemma] = []
    for row in inc_raw:
        lemma = str(row["lemma"]).strip().lower()
        pos = str(row.get("pos", "NOUN")).strip()
        freq = float(row.get("freq_ipm", 0.0))
        inc.append(Lemma(lemma=lemma, pos=pos, freq_ipm=freq, mask=letter_mask(lemma)))

    exc_raw = data.get("exclude") or []
    exc = frozenset(str(x).strip().lower() for x in exc_raw)

    al_raw = data.get("aliases") or {}
    aliases = {str(k).strip().lower(): str(v).strip().lower() for k, v in al_raw.items()}

    return Overrides(include=tuple(inc), exclude=exc, aliases=aliases)


def apply_to_rows(
    rows: Iterable[tuple[str, str, float, int]],
    ov: Overrides,
) -> list[tuple[str, str, float, int]]:
    """Apply overrides to (lemma, pos, freq_ipm, mask) rows.

    Used by `scripts/build_dictionary.py` between pymorphy3 validation and the
    SQLite write. Returns a new list; does not mutate input.
    """
    out: list[tuple[str, str, float, int]] = [r for r in rows if r[0] not in ov.exclude]
    existing = {r[0] for r in out}
    for l in ov.include:
        if l.lemma not in existing:
            out.append((l.lemma, l.pos, l.freq_ipm, l.mask))
    return out


def apply_to_dictionary(d: Dictionary, ov: Overrides) -> Dictionary:
    """Apply overrides to an in-memory Dictionary. Used by the API on startup
    so a fresh `exclude` takes effect without rebuilding the SQLite table."""
    rows: list[Lemma] = [l for l in d if l.lemma not in ov.exclude]
    existing = {l.lemma for l in rows}
    for l in ov.include:
        if l.lemma not in existing:
            rows.append(l)
    return Dictionary(rows)
