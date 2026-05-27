"""Tests for `rsb.folds` — per-POS folding rules.

These exercise both:
  - the conservative guards (top-parse rule, candidate-POS gate, freq cutoff)
  - the integration with the resolve path (via the aliases the rules produce)

The fixtures use a real pymorphy3 analyzer so the rule behavior is
end-to-end against actual morphology, not stubbed parses.
"""
from __future__ import annotations

import pytest

from rsb.alphabet import letter_mask
from rsb.dictionary import compute_form_masks
from rsb.folds import (
    DEFAULT_FREQ_CUTOFF,
    RULE_COMPARATIVE_MERGE,
    RULE_PARTICIPLE_MERGE,
    RULE_REFLEXIVE_BASE_TO_REFL,
    RULE_REFLEXIVE_REFL_TO_BASE,
    RULE_SHORT_ADJ_MERGE,
    compute_folds,
)
from rsb.lemmatizer import Lemmatizer


@pytest.fixture(scope="module")
def morph():
    import pymorphy3
    return pymorphy3.MorphAnalyzer()


def _row(morph, lemma, pos, freq):
    """Build a 5-tuple lemma row the way the build pipeline does."""
    return (lemma, pos, freq, letter_mask(lemma), compute_form_masks(morph, lemma))


# ---------- reflexive alias rule -------------------------------------------


def test_reflexive_base_to_refl_alias_for_naedat(morph):
    """The headline case: L–S has *наедаться* but not *наедать*. The fold
    must add an alias `наедать` → `наедаться` so the player's *наедал*
    (pymorphy3-lemmatized to *наедать*) resolves to *наедаться*."""
    rows = [
        _row(morph, "наедаться", "VERB", 0.7),
        # something irrelevant in dict, to make sure we don't crash on it
        _row(morph, "дом", "NOUN", 500.0),
    ]
    new_rows, aliases, report = compute_folds(rows, morph)
    pairs = {(s, t): r for s, t, r in aliases}
    assert ("наедать", "наедаться") in pairs
    assert pairs[("наедать", "наедаться")] == RULE_REFLEXIVE_BASE_TO_REFL
    # No rows should be added or removed by an alias-only rule.
    assert len(new_rows) == len(rows)


def test_reflexive_no_alias_when_both_present(morph):
    """When the dict has both base AND reflexive, no alias is needed.
    Each lemma stands on its own and each gets credit independently."""
    rows = [
        _row(morph, "мыть", "VERB", 16.0),
        _row(morph, "мыться", "VERB", 3.6),
    ]
    _, aliases, _ = compute_folds(rows, morph)
    sources = {s for s, _, _ in aliases}
    assert "мыть" not in sources
    assert "мыться" not in sources


def test_reflexive_no_alias_when_partner_is_hallucinated(morph):
    """pymorphy3's morphological generator will *predict* a reflexive
    partner for almost any verb (`*быться` for быть, `*любиться` for любить),
    but those forms are not actually in OpenCorpora. The `word_is_known`
    guard must filter them out."""
    rows = [
        _row(morph, "быть", "VERB", 12160.7),
    ]
    _, aliases, _ = compute_folds(rows, morph)
    sources = {s for s, _, _ in aliases}
    # We must NOT have an alias `быться` → `быть` — `быться` doesn't really exist.
    assert "быться" not in sources


def test_reflexive_alias_resolves_via_lemmatizer(morph):
    """End-to-end: the alias the fold produces must let the lemmatizer
    accept *наедал* against a valid set that only contains the reflexive."""
    rows = [_row(morph, "наедаться", "VERB", 0.7)]
    _, aliases, _ = compute_folds(rows, morph)
    alias_map = {s: t for s, t, _ in aliases}
    lem = Lemmatizer(analyzer=morph, aliases=alias_map)
    r = lem.resolve("наедал", valid_lemmas={"наедаться"})
    assert r.status == "accepted"
    assert r.lemma == "наедаться"


# ---------- participle merger rule ------------------------------------------


def test_participle_merger_drops_lemma_and_absorbs_freq(morph):
    """*сверкающий* is a productive participle of *сверкать*. Both are in
    L–S. With *сверкающий* (8.0 ipm) below the 20-ipm cutoff and its top
    parse being PRTF→сверкать, the merger drops it and adds its freq
    onto *сверкать*."""
    rows = [
        _row(morph, "сверкать", "VERB", 24.5),
        _row(morph, "сверкающий", "ADJF", 8.0),
        # control row that should be untouched
        _row(morph, "дом", "NOUN", 500.0),
    ]
    new_rows, _, report = compute_folds(rows, morph)
    new_lemmas = {r[0]: r for r in new_rows}
    assert "сверкающий" not in new_lemmas
    assert new_lemmas["сверкать"][2] == pytest.approx(24.5 + 8.0)
    # report records the action
    assert any(
        s == "сверкающий" and t == "сверкать" and rule == RULE_PARTICIPLE_MERGE
        for s, t, rule, _ in report.mergers_applied
    )


def test_participle_protected_by_top_parse(morph):
    """*следующий* and *бывший* are lexicalized to the point that pymorphy3
    ranks them as ADJF (not PRTF) at the top of their parse list. The
    top-parse rule excludes them from consideration entirely — they never
    enter the merger pipeline. This is the *first* line of defense and
    why the freq cutoff is only a backstop."""
    rows = [
        _row(morph, "следовать", "VERB", 305.1),
        _row(morph, "следующий", "ADJF", 301.4),
        _row(morph, "быть", "VERB", 12160.7),
        _row(morph, "бывший", "ADJF", 191.5),
    ]
    new_rows, _, report = compute_folds(rows, morph)
    new_lemmas = {r[0] for r in new_rows}
    assert "следующий" in new_lemmas
    assert "бывший" in new_lemmas
    # Neither candidate makes it past the top-parse filter, so neither
    # appears in mergers_applied OR mergers_protected_by_freq.
    candidates = {s for s, _, _, _ in report.mergers_applied} | {
        s for s, _, _, _ in report.mergers_protected_by_freq
    }
    assert "следующий" not in candidates
    assert "бывший" not in candidates


def test_participle_protected_by_freq_cutoff(morph):
    """*соответствующий* (121 ipm) IS read by pymorphy3 with PRTF→соответствовать
    as its top parse — so the top-parse rule lets it through. The freq
    cutoff catches it: 121.8 ≥ 20, so it's protected and appears in
    `mergers_protected_by_freq` rather than `mergers_applied`."""
    rows = [
        _row(morph, "соответствовать", "VERB", 98.1),
        _row(morph, "соответствующий", "ADJF", 121.8),
    ]
    new_rows, _, report = compute_folds(rows, morph)
    new_lemmas = {r[0] for r in new_rows}
    assert "соответствующий" in new_lemmas
    protected = {s for s, _, _, _ in report.mergers_protected_by_freq}
    assert "соответствующий" in protected
    assert report.mergers_applied == []


def test_participle_merger_requires_verb_target_in_dict(morph):
    """If the parent verb is not in the dict, no merger happens — even when
    pymorphy3's top parse points there. Pulling a lemma out without a
    surviving target would orphan player input."""
    rows = [
        _row(morph, "сверкающий", "ADJF", 8.0),
        # сверкать not in dict
    ]
    new_rows, _, report = compute_folds(rows, morph)
    assert len(new_rows) == 1
    assert report.mergers_applied == []


# ---------- short adjective merger -----------------------------------------


def test_short_adj_merger_requires_top_parse_to_be_adjs(morph):
    """An adverb like *абсолютно* has a *secondary* ADJS reading pointing
    to *абсолютный*. Its top parse is ADVB. The merger must not touch it
    — otherwise the player typing the adverb gets the adjective credited
    against their will."""
    rows = [
        _row(morph, "абсолютный", "ADJF", 47.1),
        _row(morph, "абсолютно", "ADVB", 88.2),
    ]
    new_rows, _, _ = compute_folds(rows, morph)
    new_lemmas = {r[0] for r in new_rows}
    assert "абсолютно" in new_lemmas
    assert "абсолютный" in new_lemmas


# ---------- comparative merger ---------------------------------------------


def test_comparative_merger_requires_comp_pos_on_candidate(morph):
    """*больше* parses with COMP→большой as its top reading, but L–S tags
    *больше* as ADVB (the dict has POS=ADVB). The candidate-POS gate must
    require POS=COMP, blocking the merger and respecting L–S's editorial
    judgment that *больше* is its own lexical item."""
    rows = [
        _row(morph, "большой", "ADJF", 944.4),
        _row(morph, "больше", "ADVB", 634.0),  # NOT POS=COMP
    ]
    new_rows, _, report = compute_folds(rows, morph)
    new_lemmas = {r[0] for r in new_rows}
    assert "больше" in new_lemmas
    assert report.mergers_applied == []


# ---------- shape contracts ------------------------------------------------


def test_compute_folds_preserves_5_tuple_shape(morph):
    rows = [_row(morph, "дом", "NOUN", 500.0)]
    new_rows, _, _ = compute_folds(rows, morph)
    assert all(len(r) == 5 for r in new_rows)


def test_compute_folds_rejects_4_tuple_rows(morph):
    """The form-fitness rule requires form_masks; 4-tuple rows pre-date that.
    Folding without form_masks would corrupt puzzle generation."""
    with pytest.raises(ValueError, match="5-tuple"):
        compute_folds([("дом", "NOUN", 500.0, letter_mask("дом"))], morph)


def test_freq_cutoff_is_overridable(morph):
    """Same `сверкающий` case but with cutoff=5 — now it's *above* the
    cutoff and should be protected."""
    rows = [
        _row(morph, "сверкать", "VERB", 24.5),
        _row(morph, "сверкающий", "ADJF", 8.0),
    ]
    new_rows, _, report = compute_folds(rows, morph, freq_cutoff=5.0)
    new_lemmas = {r[0] for r in new_rows}
    assert "сверкающий" in new_lemmas
    assert report.mergers_applied == []
    protected = {s for s, _, _, _ in report.mergers_protected_by_freq}
    assert "сверкающий" in protected


def test_default_freq_cutoff_is_20(morph):
    """Lock down the documented cutoff so an accidental change shows up in tests."""
    assert DEFAULT_FREQ_CUTOFF == 20.0
