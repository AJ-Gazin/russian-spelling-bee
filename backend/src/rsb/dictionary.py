"""Lemma table loading and querying.

A row in the lemma table is:
    lemma   pos     freq_ipm   mask   form_masks
where `lemma` is the Ё-aware canonical form (e.g. *ёлка*, not *елка*).

`form_masks` is the set of 31-bit letter-set masks across all of the lemma's
inflected forms (length ≥ MIN_WORD_LENGTH, alphabet-clean). A lemma "fits" a
hive iff at least one form-mask is a subset of the hive AND contains the
center — this is the form-level fitness rule (see `lemmas_fitting`). The
lemma's own `mask` is still used for pangram detection (pangrams must be the
citation form, not an arbitrary inflection).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .alphabet import HIVE_LETTERS, letter_mask
from .scoring import MIN_WORD_LENGTH

_ALPHABET_OK: frozenset[str] = frozenset(HIVE_LETTERS) | {"ё"}


def _clean_word(word: str) -> bool:
    return all(ch in _ALPHABET_OK for ch in word.lower())


def compute_form_masks(morph, lemma: str) -> frozenset[int]:
    """Enumerate inflected forms of `lemma` via pymorphy3 and return the set
    of distinct letter-masks across forms with length ≥ MIN_WORD_LENGTH whose
    characters all live in the 31-letter alphabet (Ё folded into Е).

    The lemma's own mask is always included if the lemma itself qualifies —
    this is the safety net for the pangram-on-citation-form invariant and for
    lemmas whose lexeme pymorphy3 fails to expand.
    """
    masks: set[int] = set()
    for parse in morph.parse(lemma):
        if parse.normal_form != lemma:
            continue
        for f in parse.lexeme:
            word = f.word.lower()
            if len(word) < MIN_WORD_LENGTH or not _clean_word(word):
                continue
            masks.add(letter_mask(word))
        break
    if len(lemma) >= MIN_WORD_LENGTH and _clean_word(lemma):
        masks.add(letter_mask(lemma))
    return frozenset(masks)


@dataclass(frozen=True, slots=True)
class Lemma:
    lemma: str
    pos: str
    freq_ipm: float
    mask: int = field(compare=False)
    form_masks: frozenset[int] = field(default=frozenset(), compare=False)

    @property
    def length(self) -> int:
        return len(self.lemma)


class Dictionary:
    """In-memory lemma store. Cheap to construct, cheap to filter by hive."""

    def __init__(self, lemmas: Iterable[Lemma]):
        self._by_lemma: dict[str, Lemma] = {l.lemma: l for l in lemmas}

    @classmethod
    def from_tsv(cls, path: Path | str) -> "Dictionary":
        """Load lemmas from a hand-curated TSV. Form-masks are computed via
        pymorphy3 on load — fine for the small stub list (~250 lemmas)."""
        import pymorphy3
        morph = pymorphy3.MorphAnalyzer()
        path = Path(path)
        rows: list[Lemma] = []
        with path.open(encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) != 3:
                    raise ValueError(f"{path}:{lineno}: expected 3 tab-separated columns, got {len(parts)}")
                lemma, pos, freq_s = parts
                lemma = lemma.strip().lower()
                pos = pos.strip()
                try:
                    freq = float(freq_s)
                except ValueError as e:
                    raise ValueError(f"{path}:{lineno}: bad freq {freq_s!r}") from e
                rows.append(Lemma(
                    lemma=lemma,
                    pos=pos,
                    freq_ipm=freq,
                    mask=letter_mask(lemma),
                    form_masks=compute_form_masks(morph, lemma),
                ))
        return cls(rows)

    @classmethod
    def from_db(cls, conn) -> "Dictionary":
        """Load the compiled lemma table from SQLite (see store.py).

        Form-masks come from the `form_masks` column when populated. Rows
        whose `form_masks` is empty (legacy DBs built before the form-fitness
        change) are migrated in-place: we compute via pymorphy3 and write
        back. This makes the migration automatic on first startup after
        upgrade and a no-op thereafter.
        """
        # Inline imports avoid module-load cycles with store.py + pymorphy3 cost.
        from .store import iter_lemmas, update_form_masks_bulk
        rows: list[Lemma] = []
        needs_migration: list[tuple[str, frozenset[int]]] = []
        morph = None
        for lemma, pos, freq, mask, form_masks in iter_lemmas(conn):
            if not form_masks:
                if morph is None:
                    import pymorphy3
                    morph = pymorphy3.MorphAnalyzer()
                form_masks = compute_form_masks(morph, lemma)
                needs_migration.append((lemma, form_masks))
            rows.append(Lemma(
                lemma=lemma,
                pos=pos,
                freq_ipm=freq,
                mask=mask,
                form_masks=form_masks,
            ))
        if needs_migration:
            update_form_masks_bulk(conn, needs_migration)
        return cls(rows)

    def __len__(self) -> int:
        return len(self._by_lemma)

    def __iter__(self) -> Iterator[Lemma]:
        return iter(self._by_lemma.values())

    def __contains__(self, lemma: str) -> bool:
        return lemma in self._by_lemma

    def get(self, lemma: str) -> Lemma | None:
        return self._by_lemma.get(lemma)

    def lemmas_fitting(self, hive_mask_: int, center_bit: int) -> list[Lemma]:
        """All lemmas that have at least one *inflected form* whose letter-set
        is a subset of the hive AND contains the center letter.

        This is the form-level fitness rule: a lemma counts as available in
        the puzzle if any of its forms can be built from the hive letters
        (with the center). The lemma's citation form does not itself need to
        fit — e.g. *сеть* (с,е,т,ь) belongs in a с,е,т,и,…-hive because its
        plural form *сети* fits. Pangram detection uses `Lemma.mask` (the
        citation form), not `form_masks`, so pangrams stay citation forms.

        Backwards compatibility: when a Lemma was constructed without
        `form_masks` (older tests, hand-built fixtures), fall back to the
        single-mask citation-form check.
        """
        out: list[Lemma] = []
        for l in self._by_lemma.values():
            masks = l.form_masks or (l.mask,)
            for m in masks:
                if (m & ~hive_mask_) == 0 and (m & center_bit) != 0:
                    out.append(l)
                    break
        return out
