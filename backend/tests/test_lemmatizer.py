import pytest

from rsb.lemmatizer import Lemmatizer


@pytest.fixture(scope="module")
def lem():
    return Lemmatizer()


def test_simple_inflection_to_lemma(lem):
    # The classic case: any inflected form of дом → дом.
    r = lem.resolve("домами", valid_lemmas={"дом", "дочь"})
    assert r.status == "accepted"
    assert r.lemma == "дом"


def test_verb_form_to_infinitive(lem):
    r = lem.resolve("читаю", valid_lemmas={"читать"})
    assert r.status == "accepted"
    assert r.lemma == "читать"


def test_yo_input_matches_yo_lemma(lem):
    # User types Е, but the lemma is stored with Ё. pymorphy3 normalizes internally.
    r = lem.resolve("елка", valid_lemmas={"ёлка"})
    assert r.status == "accepted"
    assert r.lemma == "ёлка"


def test_ambiguous_form_picks_first_qualifying_parse(lem):
    # 'стекла' has two competitive parses: стекло (high) and стечь (low).
    # If both are in the valid set, the higher-scored one wins.
    r = lem.resolve("стекла", valid_lemmas={"стекло", "стечь"})
    assert r.status == "accepted"
    assert r.lemma == "стекло"

    # If only the low-scored parse is in the valid set, it still resolves.
    r2 = lem.resolve("стекла", valid_lemmas={"стечь"})
    assert r2.status == "accepted"
    assert r2.lemma == "стечь"


def test_not_in_set_when_lemma_is_outside_puzzle(lem):
    r = lem.resolve("домами", valid_lemmas={"кот"})
    assert r.status == "not_in_set"
    assert "дом" in r.candidates


def test_unparseable(lem):
    # A string of random letters that pymorphy3 will still try to parse:
    # pymorphy3 is generous and almost always returns *something*. We test with
    # something it can't even guess, like punctuation-only input.
    r = lem.resolve("---", valid_lemmas={"дом"})
    # pymorphy3 may parse '---' as nothing, in which case status == unparseable.
    # If it does parse something, it should at least not falsely match a real lemma.
    assert r.status in {"unparseable", "not_in_set"}
    assert r.lemma is None


def test_candidate_lemmas_preserves_order(lem):
    cands = lem.candidate_lemmas("стекла")
    assert cands[0] == "стекло"  # pymorphy3's top-ranked parse
    assert "стечь" in cands


def test_suppletive_plural_дети_resolves_to_ребёнок(lem):
    # Regression: pre-fix, дети → ребёнок but ребёнок was missing from the DB
    # because the freq source spelled it "ребенок" and the build's round-trip
    # check failed. Once canonical_lemma rescues it at build time, the resolve
    # path naturally accepts.
    r = lem.resolve("дети", valid_lemmas={"ребёнок"})
    assert r.status == "accepted"
    assert r.lemma == "ребёнок"


def test_resolve_yo_fallback_in_valid_set(lem, caplog):
    # Defensive fallback for the case where valid_lemmas inadvertently holds
    # the no-yo form. Resolves to whatever is in the valid set (so already-found
    # dedup keeps working), and emits a warning.
    import logging
    with caplog.at_level(logging.WARNING, logger="rsb.lemmatizer"):
        r = lem.resolve("ёлка", valid_lemmas={"елка"})
    assert r.status == "accepted"
    assert r.lemma == "елка"
    assert any("ё-fallback" in rec.message for rec in caplog.records)


def test_alias_fallback_resolves_when_direct_lemma_missing():
    """Lemmatizer's alias map (populated by `rsb.folds`) lets a parsed
    lemma resolve to a different lemma in the valid set. This is the
    *наедал* → *наедать* (alias) → *наедаться* path."""
    lem = Lemmatizer(aliases={"наедать": "наедаться"})
    r = lem.resolve("наедал", valid_lemmas={"наедаться"})
    assert r.status == "accepted"
    assert r.lemma == "наедаться"


def test_alias_not_consulted_when_direct_lemma_in_set():
    """When the parsed lemma is itself in the valid set, the direct match
    wins — the alias must not silently replace it."""
    lem = Lemmatizer(aliases={"наедать": "наедаться"})
    r = lem.resolve("наедал", valid_lemmas={"наедать"})
    assert r.status == "accepted"
    assert r.lemma == "наедать"


def test_empty_aliases_does_not_change_behavior():
    """Smoke check that the alias-empty path is the byte-identical pre-fold
    behavior — `not_in_set` for a parse whose lemma isn't in the set."""
    lem = Lemmatizer(aliases={})
    r = lem.resolve("наедал", valid_lemmas={"дом"})
    assert r.status == "not_in_set"
