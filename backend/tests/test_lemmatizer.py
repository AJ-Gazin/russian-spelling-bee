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
