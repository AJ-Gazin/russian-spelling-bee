from pathlib import Path

from rsb.alphabet import letter_mask
from rsb.dictionary import Dictionary, Lemma
from rsb.overrides import Overrides, apply_to_dictionary, apply_to_rows, load


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
