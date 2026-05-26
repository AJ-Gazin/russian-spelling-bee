from pathlib import Path

import pytest

from rsb.alphabet import letter_mask
from rsb.dictionary import Dictionary, Lemma
from rsb.overrides import Overrides, apply_to_dictionary, apply_to_rows, load, normalize


def test_load_minimal(tmp_path: Path):
    f = tmp_path / "o.yaml"
    f.write_text(
        "include:\n"
        "  - {lemma: ёлка, pos: NOUN, freq_ipm: 60}\n"
        "exclude:\n"
        "  - садик\n"
        "  - котик\n"
        "aliases:\n"
        "  кот: кот\n",
        encoding="utf-8",
    )
    ov = load(f)
    assert len(ov.include) == 1 and ov.include[0].lemma == "ёлка"
    assert ov.exclude == frozenset({"садик", "котик"})
    assert ov.aliases == {"кот": "кот"}


def test_load_missing_file_returns_empty(tmp_path: Path):
    ov = load(tmp_path / "no-such-file.yaml")
    assert ov.include == ()
    assert ov.exclude == frozenset()
    assert ov.aliases == {}


def test_apply_to_rows_excludes_and_includes():
    rows = [
        ("дом", "NOUN", 1500.0, letter_mask("дом")),
        ("садик", "NOUN", 11.9, letter_mask("садик")),
        ("кот", "NOUN", 280.0, letter_mask("кот")),
    ]
    ov = Overrides(
        include=(Lemma(lemma="ёлка", pos="NOUN", freq_ipm=60.0, mask=letter_mask("ёлка")),),
        exclude=frozenset({"садик"}),
        aliases={},
    )
    out = apply_to_rows(rows, ov)
    lemmas = {r[0] for r in out}
    assert "садик" not in lemmas
    assert "ёлка" in lemmas
    assert "дом" in lemmas
    assert "кот" in lemmas


def test_apply_to_dictionary():
    d = Dictionary([
        Lemma("дом", "NOUN", 1500.0, letter_mask("дом")),
        Lemma("садик", "NOUN", 11.9, letter_mask("садик")),
    ])
    ov = Overrides(exclude=frozenset({"садик"}))
    d2 = apply_to_dictionary(d, ov)
    assert "дом" in d2
    assert "садик" not in d2


def test_apply_include_does_not_duplicate():
    rows = [("дом", "NOUN", 1500.0, letter_mask("дом"))]
    ov = Overrides(include=(Lemma("дом", "NOUN", 9999.0, letter_mask("дом")),))
    out = apply_to_rows(rows, ov)
    assert len(out) == 1
    # Original kept; include is a no-op when the lemma is already present.
    assert out[0][2] == 1500.0


@pytest.fixture(scope="module")
def morph():
    import pymorphy3
    return pymorphy3.MorphAnalyzer()


def test_normalize_yo_in_exclude(morph):
    # Author wrote "ребенок" (no ё) in exclude; should match DB entry "ребёнок".
    ov = Overrides(exclude=frozenset({"ребенок", "садик"}))
    norm = normalize(ov, morph)
    assert "ребёнок" in norm.exclude
    assert "садик" in norm.exclude  # no yo to recover; passthrough


def test_normalize_yo_in_include(morph):
    ov = Overrides(include=(
        Lemma(lemma="ребенок", pos="NOUN", freq_ipm=10.0, mask=letter_mask("ребенок")),
    ))
    norm = normalize(ov, morph)
    assert len(norm.include) == 1
    assert norm.include[0].lemma == "ребёнок"
    # mask was recomputed for the canonical form.
    assert norm.include[0].mask == letter_mask("ребёнок")


def test_normalize_aliases_canonicalizes_values_only(morph):
    # Alias keys are surface forms (not lemmas); values are lemmas.
    ov = Overrides(aliases={"детишки": "ребенок"})
    norm = normalize(ov, morph)
    assert norm.aliases == {"детишки": "ребёнок"}
