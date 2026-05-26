"""Lemma table loading and querying.

Until the real OpenCorpora ∩ Lyashevskaya–Sharov pipeline lands (todo task #7),
this module reads from a small hand-curated TSV at `backend/data/stub_lemmas.tsv`.
Once the real pipeline exists, the same `Dictionary` API will be backed by SQLite.

A row in the lemma table is:
    lemma   pos     freq_ipm
where `lemma` is the Ё-aware canonical form (e.g. *ёлка*, not *елка*).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .alphabet import letter_mask


@dataclass(frozen=True, slots=True)
class Lemma:
    lemma: str
    pos: str
    freq_ipm: float
    mask: int = field(compare=False)

    @property
    def length(self) -> int:
        return len(self.lemma)


class Dictionary:
    """In-memory lemma store. Cheap to construct, cheap to filter by hive."""

    def __init__(self, lemmas: Iterable[Lemma]):
        self._by_lemma: dict[str, Lemma] = {l.lemma: l for l in lemmas}

    @classmethod
    def from_tsv(cls, path: Path | str) -> "Dictionary":
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
                rows.append(Lemma(lemma=lemma, pos=pos, freq_ipm=freq, mask=letter_mask(lemma)))
        return cls(rows)

    @classmethod
    def from_db(cls, conn) -> "Dictionary":
        """Load the compiled lemma table from a SQLite connection (see store.py).

        Uses the mask stored in the DB rather than recomputing — they should
        match what `letter_mask()` would produce, but if the alphabet ever
        changes we'll catch the mismatch by rebuilding the dictionary.
        """
        # Inline import avoids a module-load circular dep with store.py.
        from .store import iter_lemmas
        rows: list[Lemma] = []
        for lemma, pos, freq, mask in iter_lemmas(conn):
            rows.append(Lemma(lemma=lemma, pos=pos, freq_ipm=freq, mask=mask))
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
        """All lemmas that (a) use only letters in the hive and (b) contain the center letter."""
        out: list[Lemma] = []
        for l in self._by_lemma.values():
            m = l.mask
            if (m & ~hive_mask_) == 0 and (m & center_bit) != 0:
                out.append(l)
        return out
