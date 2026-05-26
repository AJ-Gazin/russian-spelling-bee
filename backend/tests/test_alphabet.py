from rsb.alphabet import (
    HIVE_LETTERS,
    VOWELS,
    contains_letter,
    fits_hive,
    fold_yo,
    hive_mask,
    is_pangram,
    letter_bit,
    letter_mask,
)


def test_hive_letters_count_and_no_yo_no_hard_sign():
    assert len(HIVE_LETTERS) == 31
    assert "ё" not in HIVE_LETTERS
    assert "ъ" not in HIVE_LETTERS


def test_vowels():
    assert VOWELS == frozenset("аеиоуыэюя")


def test_fold_yo():
    assert fold_yo("ёлка") == "елка"
    assert fold_yo("Ёлка") == "Елка"
    assert fold_yo("красивый") == "красивый"


def test_letter_bit_folds_yo_to_e():
    assert letter_bit("ё") == letter_bit("е")
    assert letter_bit("Ё") == letter_bit("е")


def test_letter_mask_basic():
    m = letter_mask("дом")
    assert m == letter_bit("д") | letter_bit("о") | letter_bit("м")


def test_letter_mask_folds_yo():
    assert letter_mask("ёлка") == letter_mask("елка")


def test_fits_hive_subset_test():
    hm = hive_mask("дмоксиа")  # д,м,о,к,с,и,а
    assert fits_hive(letter_mask("дом"), hm)
    assert fits_hive(letter_mask("мак"), hm)
    assert not fits_hive(letter_mask("друг"), hm)  # 'р','у','г' not in hive


def test_contains_letter():
    m = letter_mask("дом")
    assert contains_letter(m, "д")
    assert not contains_letter(m, "р")


def test_is_pangram_uses_every_hive_letter():
    hm = hive_mask("дмоксиа")
    pangram_word = "комадис"  # uses all 7 hive letters; nonsense lemma, OK for unit test
    assert is_pangram(letter_mask(pangram_word), hm)
    assert not is_pangram(letter_mask("дом"), hm)


def test_letter_bit_rejects_invalid():
    import pytest

    with pytest.raises(ValueError):
        letter_bit("ъ")
    with pytest.raises(ValueError):
        letter_bit("x")  # latin
