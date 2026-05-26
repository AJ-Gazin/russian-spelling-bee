"""Tests for `alphabet.canonical_lemma` — the yo-recovery helper that lets the
build pipeline rescue common Ё-words the source spells without ё."""
from __future__ import annotations

import pytest

from rsb.alphabet import canonical_lemma


@pytest.fixture(scope="module")
def morph():
    import pymorphy3
    return pymorphy3.MorphAnalyzer()


def test_passthrough_when_raw_round_trips(morph):
    # "дом" is its own normal_form — no yo-recovery needed.
    assert canonical_lemma(morph, "дом") == "дом"
    assert canonical_lemma(morph, "читать") == "читать"


def test_yo_form_passes_through(morph):
    # Already-canonical Ё-form: fast path.
    assert canonical_lemma(morph, "ребёнок") == "ребёнок"
    assert canonical_lemma(morph, "ёлка") == "ёлка"


def test_yo_recovery_for_source_without_yo(morph):
    # The headline cases: the freq source spells these without ё; pymorphy3
    # canonicalizes to the ё-form; we rewrite raw → canonical.
    assert canonical_lemma(morph, "ребенок") == "ребёнок"
    assert canonical_lemma(morph, "елка") == "ёлка"
    assert canonical_lemma(morph, "лед") == "лёд"


def test_returns_none_when_no_round_trip(morph):
    # An oblique form: pymorphy3 normalizes to a different lexeme, not a
    # ё-variant. We must NOT rewrite — return None so the row is dropped, same
    # as today's behavior.
    # "стекла" parses to "стекло" / "стечь" — neither differs from "стекла"
    # by only ё↔е, so canonical_lemma should refuse.
    assert canonical_lemma(morph, "стекла") is None
