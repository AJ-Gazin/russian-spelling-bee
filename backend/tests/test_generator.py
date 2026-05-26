from pathlib import Path

import pytest

from rsb.dictionary import Dictionary
from rsb.generator import GeneratorConfig, NoPuzzleFound, generate

STUB = Path(__file__).resolve().parents[1] / "data" / "stub_lemmas.tsv"


@pytest.fixture(scope="module")
def stub_dict():
    return Dictionary.from_tsv(STUB)


def _stub_cfg(**overrides) -> GeneratorConfig:
    """Generator config relaxed for the small stub list."""
    base = dict(
        min_lemmas=8,
        max_lemmas=200,
        pangram_freq_floor=0.0,  # stub has rough freq estimates
        require_pangram=False,  # most stub-sized hives won't have a pangram
        dominance_cap=0.50,
        max_attempts=4000,
        seed=42,
    )
    base.update(overrides)
    return GeneratorConfig(**base)


def test_generator_returns_valid_puzzle_on_stub(stub_dict):
    p = generate(stub_dict, _stub_cfg())
    assert len(p.letters) == 7
    assert p.center in p.letters
    assert p.letters[0] == p.center
    assert len(set(p.letters)) == 7
    assert p.total_points == sum(s.points for s in p.lemmas)
    assert all(p.center in s.lemma.replace("ё", "е") or p.center in s.lemma for s in p.lemmas)


def test_generator_respects_min_vowels(stub_dict):
    from rsb.alphabet import VOWELS

    p = generate(stub_dict, _stub_cfg(min_vowels=3))
    vowels_in_hive = sum(1 for c in p.letters if c in VOWELS)
    assert vowels_in_hive >= 3


def test_generator_respects_dominance_cap(stub_dict):
    p = generate(stub_dict, _stub_cfg(dominance_cap=0.20))
    for s in p.lemmas:
        assert s.points / p.total_points <= 0.20 + 1e-9


def test_generator_raises_when_no_acceptable_puzzle(stub_dict):
    # Demand a high pangram frequency that the stub almost certainly can't satisfy.
    cfg = _stub_cfg(require_pangram=True, pangram_freq_floor=10000.0, max_attempts=200)
    with pytest.raises(NoPuzzleFound):
        generate(stub_dict, cfg)


def test_generator_deterministic_under_seed(stub_dict):
    a = generate(stub_dict, _stub_cfg(seed=7))
    b = generate(stub_dict, _stub_cfg(seed=7))
    assert a.letters == b.letters
    assert a.center == b.center
    assert [s.lemma for s in a.lemmas] == [s.lemma for s in b.lemmas]
