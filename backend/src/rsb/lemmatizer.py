"""pymorphy3 wrapper implementing the project's lemma-resolution rule.

The rule: a typed form is *accepted* iff at least one pymorphy3 parse resolves
to a lemma in the puzzle's valid-lemma set. When multiple parses qualify, the
highest-scoring parse (by pymorphy3's `.score`) is the one displayed to the
player as the resolved lemma.

Player input is folded for Ё/Е so a user can type either *елка* or *ёлка*
without caring how the lemma is stored. pymorphy3 internally canonicalizes
to Ё (so *елка* already parses to *ёлка*), but we fold defensively in case
custom alias entries are stored with Е.

The lemmatizer is also consulted on misses to classify the rejection reason:
- `not_in_set`: form parsed cleanly but its lemma isn't in the valid set
  (or uses letters outside the hive — same outcome for player UX).
- `unparseable`: pymorphy3 returned no parses, or only parses to forms that
  themselves don't look like real Russian words (rare; we treat any parse as
  "at least typed something morphologically").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import pymorphy3

from .alphabet import fold_yo

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Resolution:
    """Result of resolving a player input against a puzzle's valid lemma set."""

    status: str  # "accepted" | "not_in_set" | "unparseable"
    lemma: str | None = None  # the matched lemma when status == "accepted"
    candidates: tuple[str, ...] = ()  # all distinct candidate lemmas considered (for debugging / future UI)


class Lemmatizer:
    """Wraps pymorphy3.MorphAnalyzer with the project's resolution rule.

    Construct once and reuse — analyzer initialization loads ~30MB of dictionary
    data and takes ~200ms.
    """

    def __init__(self, analyzer: pymorphy3.MorphAnalyzer | None = None):
        self._morph = analyzer or pymorphy3.MorphAnalyzer()

    def parses_for(self, form: str) -> list[pymorphy3.analyzer.Parse]:
        """All pymorphy3 parses for the (folded, lowercased) input."""
        return self._morph.parse(form.strip().lower())

    def candidate_lemmas(self, form: str) -> list[str]:
        """Distinct normal forms across all parses, preserving pymorphy3's score order."""
        seen: dict[str, None] = {}
        for p in self.parses_for(form):
            if p.normal_form not in seen:
                seen[p.normal_form] = None
        return list(seen.keys())

    def resolve(self, form: str, valid_lemmas: Iterable[str] | set[str] | frozenset[str]) -> Resolution:
        """Resolve a player input against the puzzle's valid-lemma set.

        `valid_lemmas` should be a fast-membership container (set / frozenset / dict).
        Returns a Resolution with status:
          - "accepted" + the lemma (highest-scored qualifying parse)
          - "not_in_set" + the candidates we considered
          - "unparseable" with empty candidates if pymorphy3 returned nothing
        """
        valid = set(valid_lemmas) if not isinstance(valid_lemmas, (set, frozenset)) else valid_lemmas
        parses = self.parses_for(form)
        if not parses:
            return Resolution(status="unparseable")
        # Preserve pymorphy3's score order. Pick the first parse whose lemma is valid.
        candidates: list[str] = []
        seen: set[str] = set()
        first_hit: str | None = None
        # Lazily built fold-keyed view of `valid` for the ё-fallback. After the
        # build pipeline fix, the DB consistently stores ё-forms and pymorphy3
        # normalizes input to ё, so this fallback should never fire in
        # production — the warning logs an early signal if it does.
        folded_valid: dict[str, str] | None = None
        for p in parses:
            lemma = p.normal_form
            if lemma not in seen:
                seen.add(lemma)
                candidates.append(lemma)
            if first_hit is None:
                if lemma in valid:
                    first_hit = lemma
                else:
                    if folded_valid is None:
                        folded_valid = {fold_yo(v): v for v in valid}
                    hit = folded_valid.get(fold_yo(lemma))
                    if hit is not None:
                        _log.warning(
                            "Lemmatizer ё-fallback: parse %r matched valid lemma %r via fold_yo",
                            lemma, hit,
                        )
                        first_hit = hit
        if first_hit is not None:
            return Resolution(status="accepted", lemma=first_hit, candidates=tuple(candidates))
        return Resolution(status="not_in_set", candidates=tuple(candidates))
