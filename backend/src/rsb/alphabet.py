"""Russian Spelling Bee alphabet, Ё/Е normalization, and letter-set bitmasks.

The effective alphabet is 31 letters: the standard Russian 33 minus Ъ (excluded
entirely — frequency too low for pangram construction), with Ё treated as a
typographic variant of Е for hive *display* and player *input* purposes only.

Internally, lemmas are stored Ё-aware: pymorphy3 emits `ёлка` (not `елка`) as
the normal form, and we preserve that to keep the option of distinguishing
*ёлка* from *елка* (or *все* from *всё*) at a later date. The hive renders
Е regardless of whether the lemma's spelling uses Е or Ё; player input is
matched by trying both folded forms.
"""

from __future__ import annotations

# 31 letters: standard 33 minus Ъ. Ё is kept as a first-class letter internally
# but folded to Е for hive composition and input matching.
ALPHABET: tuple[str, ...] = tuple(
    "абвгдеёжзийклмнопрстуфхцчшщыьэюя"
)
assert len(ALPHABET) == 32, "expected 32 distinct chars (Ё included), got %d" % len(ALPHABET)

# Hive composition pool: 31 letters, Ё folded into Е, Ъ excluded.
# This is what generator.py samples from.
HIVE_LETTERS: tuple[str, ...] = tuple(
    "абвгдежзийклмнопрстуфхцчшщыьэюя"
)
assert len(HIVE_LETTERS) == 31

VOWELS: frozenset[str] = frozenset("аеиоуыэюя")  # Ё folded → Е; no Ы/Ъ in vowels

# Bit positions for each *folded* letter (Ё → Е's bit). 31 bits fit in one int.
_BIT: dict[str, int] = {ch: 1 << i for i, ch in enumerate(HIVE_LETTERS)}


def fold_yo(s: str) -> str:
    """Fold Ё → Е (both cases). Used for hive display and player-input matching."""
    return s.replace("ё", "е").replace("Ё", "Е")


def letter_bit(letter: str) -> int:
    """Return the bit for a single hive letter (after Ё folding). Raises on invalid input."""
    letter = letter.lower()
    if letter == "ё":
        letter = "е"
    try:
        return _BIT[letter]
    except KeyError as e:
        raise ValueError(f"not a hive letter: {letter!r}") from e


def letter_mask(word: str) -> int:
    """Return the 31-bit letter-set mask for a word. Ё folds into Е. Ъ → 0 contribution
    (but a word containing Ъ will have a 0 bit for Ъ, which means the subset test
    against any hive will succeed unless we filter Ъ-containing words upstream;
    the dictionary build does this)."""
    mask = 0
    for ch in word.lower():
        if ch == "ё":
            ch = "е"
        bit = _BIT.get(ch)
        if bit is not None:
            mask |= bit
    return mask


def hive_mask(letters: str) -> int:
    """Return the 31-bit mask covering all letters of a hive (string of 7 chars)."""
    mask = 0
    for ch in letters:
        mask |= letter_bit(ch)
    return mask


def fits_hive(word_mask: int, hive_mask_: int) -> bool:
    """True iff the word uses only letters present in the hive (subset test)."""
    return (word_mask & ~hive_mask_) == 0


def contains_letter(word_mask: int, letter: str) -> bool:
    """True iff the word contains the given (single) letter."""
    return (word_mask & letter_bit(letter)) != 0


def is_pangram(word_mask: int, hive_mask_: int) -> bool:
    """True iff the word uses *every* hive letter at least once."""
    return (word_mask & hive_mask_) == hive_mask_


def canonical_lemma(morph, raw: str) -> str | None:
    """Yo-aware lemma normalization for the dictionary build + override loader.

    The Lyashevskaya–Sharov frequency source spells common Ё-words without ё
    (e.g. "ребенок" 658 ipm, "елка", "лед"); pymorphy3 canonicalizes those to
    the Ё-form. Without this helper, the round-trip check `parse.normal_form ==
    raw` fails and the row is silently dropped.

    Returns:
      - `raw` if pymorphy3 has any parse with `normal_form == raw` (already
        canonical; fast path).
      - the yo-corrected form `cand` if pymorphy3 normalizes `raw` to `cand`
        where they differ ONLY by ё↔е, AND `cand` itself round-trips.
      - `None` otherwise (the row would have been dropped today; same outcome).

    The `fold_yo` guard prevents accidental rewrites from pymorphy3 reparsing
    an oblique form as an unrelated lexeme (e.g. "стекла" → "стекло").
    """
    folded = fold_yo(raw)
    yo_candidate: str | None = None
    for p in morph.parse(raw):
        if p.normal_form == raw:
            return raw
        if yo_candidate is None and fold_yo(p.normal_form) == folded:
            yo_candidate = p.normal_form
    if yo_candidate is None:
        return None
    for p in morph.parse(yo_candidate):
        if p.normal_form == yo_candidate:
            return yo_candidate
    return None
