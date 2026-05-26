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

from .alphabet import canonical_lemma, letter_mask
from .dictionary import Dictionary, Lemma, compute_form_masks


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
        # form_masks left empty here — populated lazily when overrides are
        # actually applied (so unit tests that load overrides don't pay for
        # pymorphy3 startup).
        inc.append(Lemma(lemma=lemma, pos=pos, freq_ipm=freq, mask=letter_mask(lemma)))

    exc_raw = data.get("exclude") or []
    exc = frozenset(str(x).strip().lower() for x in exc_raw)

    al_raw = data.get("aliases") or {}
    aliases = {str(k).strip().lower(): str(v).strip().lower() for k, v in al_raw.items()}

    return Overrides(include=tuple(inc), exclude=exc, aliases=aliases)


def normalize(ov: Overrides, morph) -> Overrides:
    """Route every include/exclude lemma and every alias *value* through
    `canonical_lemma` so authors can spell entries with or without ё and still
    match the canonical Ё-form used in the DB.

    Alias *keys* are user-facing surface forms (not lemmas), so they are not
    canonicalized.

    Entries that fail to round-trip are left unchanged (in exclude: harmless;
    in include: will be re-dropped at the apply step).
    """
    new_include: list[Lemma] = []
    for l in ov.include:
        canon = canonical_lemma(morph, l.lemma)
        if canon is None or canon == l.lemma:
            new_include.append(l)
        else:
            new_include.append(Lemma(
                lemma=canon,
                pos=l.pos,
                freq_ipm=l.freq_ipm,
                mask=letter_mask(canon),
                form_masks=l.form_masks,
            ))
    new_exclude = frozenset(
        (canonical_lemma(morph, x) or x) for x in ov.exclude
    )
    new_aliases = {
        k: (canonical_lemma(morph, v) or v) for k, v in ov.aliases.items()
    }
    return Overrides(include=tuple(new_include), exclude=new_exclude, aliases=new_aliases)


def apply_to_rows(
    rows: Iterable[tuple],
    ov: Overrides,
    *,
    morph=None,
) -> list[tuple]:
    """Apply overrides to lemma rows.

    Each row is either a 4-tuple (lemma, pos, freq_ipm, mask) or a 5-tuple
    (lemma, pos, freq_ipm, mask, form_masks). The output preserves the
    arity of the *input* rows for backwards compatibility. When a 5-tuple is
    expected and an `include` entry has no form_masks attached, pymorphy3 is
    used to compute them (pass `morph` to avoid spinning up a fresh analyzer).
    """
    rows_list = list(rows)
    arity = len(rows_list[0]) if rows_list else 5
    out: list[tuple] = [r for r in rows_list if r[0] not in ov.exclude]
    existing = {r[0] for r in out}
    for l in ov.include:
        if l.lemma in existing:
            continue
        if arity == 4:
            out.append((l.lemma, l.pos, l.freq_ipm, l.mask))
        else:
            fm = l.form_masks
            if not fm:
                if morph is None:
                    import pymorphy3
                    morph = pymorphy3.MorphAnalyzer()
                fm = compute_form_masks(morph, l.lemma)
            out.append((l.lemma, l.pos, l.freq_ipm, l.mask, fm))
    return out


def apply_to_dictionary(d: Dictionary, ov: Overrides) -> Dictionary:
    """Apply overrides to an in-memory Dictionary. Used by the API on startup
    so a fresh `exclude` takes effect without rebuilding the SQLite table.

    Include entries get form_masks computed on the fly via pymorphy3 if the
    Lemma was constructed without them (the common case for overrides loaded
    from YAML)."""
    rows: list[Lemma] = [l for l in d if l.lemma not in ov.exclude]
    existing = {l.lemma for l in rows}
    morph = None
    for l in ov.include:
        if l.lemma in existing:
            continue
        if not l.form_masks:
            if morph is None:
                import pymorphy3
                morph = pymorphy3.MorphAnalyzer()
            l = Lemma(
                lemma=l.lemma,
                pos=l.pos,
                freq_ipm=l.freq_ipm,
                mask=l.mask,
                form_masks=compute_form_masks(morph, l.lemma),
            )
        rows.append(l)
    return Dictionary(rows)
