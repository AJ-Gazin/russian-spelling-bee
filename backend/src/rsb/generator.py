"""Puzzle generation.

Strategy:
  1. Sample a 7-letter set from the 31-letter pool with frequency-weighted
     letter sampling (without replacement).
  2. Require at least N vowels (default 2). If not met, resample.
  3. For each of the 7 as a candidate center, compute the set of fitting lemmas
     (letters ⊆ hive ∧ contains center) via 31-bit bitmask subset test.
  4. Reject if any constraint fails: lemma count out of band, no qualifying
     pangram, or a single lemma exceeds the dominance cap.
  5. Return the first accepted (hive, center) combination, or raise after
     `max_attempts` failed samples.

The generator accepts a `GeneratorConfig` to make per-call tuning trivial
(stub vs. real dictionary, weekday difficulty, etc.).
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field, replace
from typing import Iterable

from .alphabet import HIVE_LETTERS, VOWELS, hive_mask, is_pangram, letter_bit, letter_mask
from .dictionary import Dictionary, Lemma
from .scoring import MIN_WORD_LENGTH, points_for, thresholds_for, RankThresholds


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    min_lemmas: int = 25
    max_lemmas: int = 70
    min_vowels: int = 2
    # The planning doc says "≥1 pangram of freq ≥ 2 ipm". For stub mode we relax.
    pangram_freq_floor: float = 2.0
    require_pangram: bool = True
    # No single lemma may account for more than this fraction of total score.
    dominance_cap: float = 0.25
    # Cap the search effort.
    max_attempts: int = 2000
    # Seed for reproducibility; None → fresh entropy.
    seed: int | None = None
    # Difficulty knob: when set, only consider the top-N most frequent lemmas
    # in the dictionary. None ⇒ use the whole dictionary (default = "hardest").
    # Smaller N ⇒ easier puzzle (only common words).
    top_n: int | None = None


@dataclass(frozen=True, slots=True)
class ScoredLemma:
    lemma: str
    pos: str
    freq_ipm: float
    length: int
    points: int
    is_pangram: bool


@dataclass(frozen=True, slots=True)
class Puzzle:
    letters: str  # 7 distinct lowercase letters; first letter is the center
    center: str  # the center letter (also letters[0] for convenience)
    lemmas: tuple[ScoredLemma, ...]
    total_points: int
    pangram_count: int
    thresholds: RankThresholds
    # Metadata for debugging / future puzzle-history features.
    meta: dict = field(default_factory=dict)


class NoPuzzleFound(RuntimeError):
    pass


def _letter_weights(dictionary: Dictionary) -> dict[str, float]:
    """Per-letter occurrence count across the dictionary (Ё folded into Е).

    Used to bias hive sampling toward letters that participate in many lemmas.
    A uniform sampler would produce mostly empty puzzles.
    """
    counts: dict[str, int] = {ch: 0 for ch in HIVE_LETTERS}
    for l in dictionary:
        # Count distinct letters per lemma so a 5-Ё word doesn't get 5 votes.
        for ch in set(l.lemma.replace("ё", "е")):
            if ch in counts:
                counts[ch] += 1
    return {ch: float(c) for ch, c in counts.items()}


def _weighted_sample_no_replacement(rng: random.Random, weights: dict[str, float], k: int) -> list[str]:
    """Sample k distinct keys, probability proportional to weight.

    Uses the Efraimidis–Spirakis trick (one log-uniform per key, top-k).
    Cheap for k=7 over 31 items.
    """
    keys = list(weights.keys())
    # Add tiny floor to avoid zero-weighted letters being unreachable forever.
    ws = [max(weights[k_], 1e-3) for k_ in keys]
    # E-S key = ln(U)/w  ; pick the k largest.
    scored = []
    for key, w in zip(keys, ws):
        u = rng.random()
        # log(u)/w is negative; the largest (closest to 0) wins.
        # Avoid log(0).
        if u <= 0:
            u = 1e-12
        import math
        scored.append((math.log(u) / w, key))
    scored.sort(reverse=True)  # largest (closest to 0) first
    return [k_ for _, k_ in scored[:k]]


def _count_vowels(letters: Iterable[str]) -> int:
    return sum(1 for c in letters if c in VOWELS)


def _score_lemmas(lemmas: list[Lemma], hive_mask_: int) -> list[ScoredLemma]:
    out: list[ScoredLemma] = []
    for l in lemmas:
        # 4-letter minimum: short lemmas remain in the dictionary (so the
        # lemmatizer recognizes them, giving the correct rejection reason),
        # but they don't appear in any puzzle's valid set.
        if len(l.lemma) < MIN_WORD_LENGTH:
            continue
        # Pangram check uses the lemma's *own* mask, not any of its form
        # masks — this preserves the invariant that an advertised pangram is
        # the citation form itself (a recognizable word), not an obscure
        # inflection that happens to use all 7 letters.
        pangram = is_pangram(l.mask, hive_mask_)
        out.append(
            ScoredLemma(
                lemma=l.lemma,
                pos=l.pos,
                freq_ipm=l.freq_ipm,
                length=len(l.lemma),
                points=points_for(l.lemma, is_pangram=pangram),
                is_pangram=pangram,
            )
        )
    return out


def _accept(
    hive_letters: str,
    center: str,
    scored: list[ScoredLemma],
    cfg: GeneratorConfig,
) -> bool:
    if not (cfg.min_lemmas <= len(scored) <= cfg.max_lemmas):
        return False
    if cfg.require_pangram:
        if not any(s.is_pangram and s.freq_ipm >= cfg.pangram_freq_floor for s in scored):
            return False
    total = sum(s.points for s in scored)
    if total == 0:
        return False
    for s in scored:
        if s.points / total > cfg.dominance_cap:
            return False
    return True


def _restrict_to_top_n(dictionary: Dictionary, top_n: int) -> Dictionary:
    """Return a Dictionary containing only the top-N lemmas by freq_ipm."""
    top = sorted(dictionary, key=lambda l: l.freq_ipm, reverse=True)[:top_n]
    return Dictionary(top)


def generate(dictionary: Dictionary, cfg: GeneratorConfig | None = None) -> Puzzle:
    """Generate a single accepted puzzle, or raise NoPuzzleFound."""
    cfg = cfg or GeneratorConfig()
    if cfg.top_n is not None and cfg.top_n < len(dictionary):
        dictionary = _restrict_to_top_n(dictionary, cfg.top_n)
    rng = random.Random(cfg.seed)
    weights = _letter_weights(dictionary)

    for _ in range(cfg.max_attempts):
        letters = _weighted_sample_no_replacement(rng, weights, 7)
        if _count_vowels(letters) < cfg.min_vowels:
            continue
        hive_str = "".join(letters)
        hm = hive_mask(hive_str)
        # Try each letter as center, prefer ones that yield acceptable puzzles.
        # Deterministic order for reproducibility under a fixed seed.
        centers_to_try = list(letters)
        rng.shuffle(centers_to_try)
        for center in centers_to_try:
            cb = letter_bit(center)
            fitting = dictionary.lemmas_fitting(hm, cb)
            scored = _score_lemmas(fitting, hm)
            if _accept(hive_str, center, scored, cfg):
                # Convention: letters[0] is the center.
                ordered_letters = center + "".join(c for c in letters if c != center)
                total = sum(s.points for s in scored)
                pangrams = sum(1 for s in scored if s.is_pangram)
                # Sort lemmas alphabetically for stable serialization.
                scored.sort(key=lambda s: s.lemma)
                return Puzzle(
                    letters=ordered_letters,
                    center=center,
                    lemmas=tuple(scored),
                    total_points=total,
                    pangram_count=pangrams,
                    thresholds=thresholds_for(total),
                    meta={"seed": cfg.seed, "config": asdict(cfg)},
                )
    raise NoPuzzleFound(f"No acceptable puzzle in {cfg.max_attempts} attempts (cfg={cfg})")


def generate_many(dictionary: Dictionary, n: int, cfg: GeneratorConfig | None = None) -> list[Puzzle]:
    """Generate N distinct puzzles. Distinctness is on the letter-set + center.

    Useful for the sanity-check script that previews a batch before queueing.
    """
    cfg = cfg or GeneratorConfig()
    out: list[Puzzle] = []
    seen: set[tuple[str, str]] = set()
    attempts_per_call = max(50, cfg.max_attempts // max(1, n))
    sub_cfg = replace(cfg, max_attempts=attempts_per_call)
    for i in range(n * 3):  # over-budget loop; we exit early when we have n
        seed = (cfg.seed if cfg.seed is not None else 0) + i
        sub_cfg = replace(sub_cfg, seed=seed)
        try:
            p = generate(dictionary, sub_cfg)
        except NoPuzzleFound:
            continue
        key = (p.letters, p.center)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= n:
            break
    return out
