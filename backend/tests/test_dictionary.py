from pathlib import Path

from rsb.alphabet import hive_mask, letter_bit, letter_mask
from rsb.dictionary import Dictionary

STUB = Path(__file__).resolve().parents[1] / "data" / "stub_lemmas.tsv"


def test_loads_stub_without_error():
    d = Dictionary.from_tsv(STUB)
    assert len(d) > 200


def test_lookup_known_lemma():
    d = Dictionary.from_tsv(STUB)
    assert "дом" in d
    l = d.get("дом")
    assert l is not None
    assert l.pos == "NOUN"
    assert l.freq_ipm > 0
    assert l.mask == letter_mask("дом")


def test_lemmas_fitting_returns_only_subset_with_center():
    d = Dictionary.from_tsv(STUB)
    hive = "дмоксиа"  # д,м,о,к,с,и,а
    hm = hive_mask(hive)
    center_bit = letter_bit("о")
    fitting = d.lemmas_fitting(hm, center_bit)
    assert fitting, "expected at least one lemma to fit a common-letter hive"
    for l in fitting:
        assert (l.mask & ~hm) == 0, f"{l.lemma} has letters outside the hive"
        assert (l.mask & center_bit) != 0, f"{l.lemma} does not contain center letter"


def test_yo_stored_with_yo():
    d = Dictionary.from_tsv(STUB)
    assert "ёлка" in d
    assert "елка" not in d
