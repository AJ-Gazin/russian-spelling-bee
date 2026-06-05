"""pymorphy3 wrapper implementing the project's lemma-resolution rule.

The rule: a typed form is *accepted* iff at least one pymorphy3 parse resolves
to a lemma in the puzzle's valid-lemma set. When multiple parses qualify (a
homonym — e.g. *стекла* → `стекло`/`стечь`), `resolve` returns the
highest-scoring one the player has not already found, so re-entering the same
string cycles to the next homonym. This makes each homonym separately earnable
(see the `found` parameter and `Resolution.reachable`).

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

Optional `aliases` map (lemma → lemma) is applied as a *final fallback*:
when no parse's normal_form is in the valid set, each candidate's alias is
also checked. This is how the reflexive folding rule (`rsb.folds`) makes
*наедал* → `наедать` (pymorphy3) → `наедаться` (alias) → accepted resolve
when `наедать` isn't in L–S but its reflexive partner is.
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

    status: str  # "accepted" | "already_found" | "not_in_set" | "unparseable"
    lemma: str | None = None  # the matched lemma when status in {"accepted", "already_found"}
    candidates: tuple[str, ...] = ()  # all distinct candidate lemmas considered (for debugging / future UI)
    # All in-set lemmas this form can map to, in pymorphy3-score order (aliases
    # last). Length > 1 means the typed string is a homonym spanning multiple
    # puzzle answers — the basis for homonym cycling (see `resolve`).
    reachable: tuple[str, ...] = ()


class Lemmatizer:
    """Wraps pymorphy3.MorphAnalyzer with the project's resolution rule.

    Construct once and reuse — analyzer initialization loads ~30MB of dictionary
    data and takes ~200ms.

    `aliases` (optional) is a lemma→lemma map consulted as a final fallback
    when no parse's normal_form is in the valid set. Produced by the build
    pipeline's folding rules (see `rsb.folds`). Empty by default — when empty
    the resolve path is byte-identical to the pre-folding behavior.
    """

    def __init__(
        self,
        analyzer: pymorphy3.MorphAnalyzer | None = None,
        *,
        aliases: dict[str, str] | None = None,
    ):
        self._morph = analyzer or pymorphy3.MorphAnalyzer()
        self._aliases: dict[str, str] = aliases or {}

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

    def resolve(
        self,
        form: str,
        valid_lemmas: Iterable[str] | set[str] | frozenset[str],
        found: Iterable[str] | set[str] | frozenset[str] = (),
    ) -> Resolution:
        """Resolve a player input against the puzzle's valid-lemma set.

        `valid_lemmas` should be a fast-membership container (set / frozenset / dict).
        `found` is the set of lemmas the player has already scored.

        Homonym cycling: a typed string can map to more than one in-set lemma
        (e.g. *стекла* → `стекло` (noun) or `стечь` (verb), both in the puzzle).
        `resolve` collects *all* such reachable lemmas in pymorphy3-score order
        and returns the first one the player has NOT yet found. Re-entering the
        same string therefore walks to the next homonym, so each is earnable in
        turn. When every reachable lemma is already found, status is
        "already_found".

        Returns a Resolution with status:
          - "accepted"      + the first not-yet-found reachable lemma (+ reachable)
          - "already_found" + a reachable lemma, when all reachable are found
          - "not_in_set"    + the candidates we considered
          - "unparseable"   with empty candidates if pymorphy3 returned nothing
        """
        valid = set(valid_lemmas) if not isinstance(valid_lemmas, (set, frozenset)) else valid_lemmas
        found_set = found if isinstance(found, (set, frozenset)) else set(found)
        parses = self.parses_for(form)
        if not parses:
            return Resolution(status="unparseable")
        # Walk parses in pymorphy3-score order, collecting candidates (all
        # distinct normal forms, for the not_in_set message) and `reachable`
        # (those that map into the valid set, de-duplicated, order preserved).
        candidates: list[str] = []
        seen: set[str] = set()
        reachable: list[str] = []
        reach_seen: set[str] = set()
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
            hit: str | None = None
            if lemma in valid:
                hit = lemma
            else:
                if folded_valid is None:
                    folded_valid = {fold_yo(v): v for v in valid}
                h = folded_valid.get(fold_yo(lemma))
                if h is not None:
                    _log.warning(
                        "Lemmatizer ё-fallback: parse %r matched valid lemma %r via fold_yo",
                        lemma, h,
                    )
                    hit = h
            if hit is not None and hit not in reach_seen:
                reach_seen.add(hit)
                reachable.append(hit)
        # Extend reachability with lemma→lemma aliases from folding rules. Walks
        # candidates in pymorphy3-score order, so a higher-scoring parse's alias
        # comes first. This is the *наедал* → `наедать` → `наедаться` path.
        if self._aliases:
            for cand in candidates:
                tgt = self._aliases.get(cand)
                if tgt is not None and tgt in valid and tgt not in reach_seen:
                    reach_seen.add(tgt)
                    reachable.append(tgt)
        if not reachable:
            return Resolution(status="not_in_set", candidates=tuple(candidates))
        reachable_t = tuple(reachable)
        for lemma in reachable:
            if lemma not in found_set:
                return Resolution(
                    status="accepted", lemma=lemma,
                    candidates=tuple(candidates), reachable=reachable_t,
                )
        # Every reachable lemma is already in the found set.
        return Resolution(
            status="already_found", lemma=reachable[0],
            candidates=tuple(candidates), reachable=reachable_t,
        )
