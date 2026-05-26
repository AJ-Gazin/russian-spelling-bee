from pathlib import Path

import pytest

from rsb.alphabet import hive_mask, letter_bit, letter_mask
from rsb.dictionary import Dictionary

STUB = Path(__file__).resolve().parents[1] / "data" / "stub_lemmas.tsv"


@pytest.fixture(scope="module")
def stub_dict():
    return Dictionary.from_tsv(STUB)


def test_loads_stub_without_error(stub_dict):
    assert len(stub_dict) > 200


def test_lookup_known_lemma(stub_dict):
    assert "дом" in stub_dict
    l = stub_dict.get("дом")
    assert l is not None
    assert l.pos == "NOUN"
    assert l.freq_ipm > 0
    assert l.mask == letter_mask("дом")


def test_form_masks_populated_for_stub(stub_dict):
    # Every stub lemma ≥4 letters should have at least one form_mask after
    # the pymorphy3 enumeration in from_tsv.
    long_enough = [l for l in stub_dict if len(l.lemma) >= 4]
    missing = [l.lemma for l in long_enough if not l.form_masks]
    assert not missing, f"lemmas missing form_masks: {missing[:5]}"


def test_lemmas_fitting_uses_form_masks(stub_dict):
    hive = "дмоксиа"  # д,м,о,к,с,и,а
    hm = hive_mask(hive)
    center_bit = letter_bit("о")
    fitting = stub_dict.lemmas_fitting(hm, center_bit)
    assert fitting, "expected at least one lemma to fit a common-letter hive"
    for l in fitting:
        # New invariant: at least one form_mask is a subset of the hive AND
        # contains the center. The lemma's own mask is no longer required to
        # fit — see the сеть/сети trap.
        masks = l.form_masks or (l.mask,)
        assert any((m & ~hm) == 0 and (m & center_bit) != 0 for m in masks), (
            f"{l.lemma} has no form fitting the hive with center о"
        )


def test_ten_trap_form_fitness_admits_lemma_via_inflected_form(stub_dict):
    """Regression: in a hive with т, е, н, и (but NO ь), the lemma *тень*
    must still appear in lemmas_fitting, because its plural form *тени* fits
    even though the citation form has a soft sign. This is the сеть-style
    trap and the central reason the form-fitness rule exists.
    """
    hive = "тенирок"  # т, е, н, и, р, о, к — no ь
    hm = hive_mask(hive)
    center_bit = letter_bit("т")
    fitting = stub_dict.lemmas_fitting(hm, center_bit)
    lemmas = {l.lemma for l in fitting}
    assert "тень" in lemmas, (
        "тень should be in the puzzle's lemma set via its form 'тени', "
        "even though 'тень' itself has ь outside the hive"
    )


def test_yo_stored_with_yo(stub_dict):
    assert "ёлка" in stub_dict
    assert "елка" not in stub_dict
