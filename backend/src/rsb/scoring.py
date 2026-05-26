"""Scoring rules: per-word points, pangram bonus, and rank thresholds.

From the planning doc:
  - 4-letter lemmas: 1 point.
  - 5+-letter lemmas: 1 point per letter (a 6-letter lemma is 6 points).
  - Pangrams: +7 bonus on top of the length score.

Rank labels and percentage thresholds follow NYT/WordBee convention.
"""

from __future__ import annotations

from dataclasses import dataclass

# (label, percent_of_total) — sorted ascending by percent.
RANKS: tuple[tuple[str, int], ...] = (
    ("Новичок", 0),
    ("Ученик", 5),
    ("Опытный", 12),
    ("Мастер", 25),
    ("Профи", 40),
    ("Эксперт", 55),
    ("Гуру", 70),
    ("Легенда", 85),
    ("Гений", 100),
)

PANGRAM_BONUS: int = 7
MIN_WORD_LENGTH: int = 4


def points_for(lemma: str, *, is_pangram: bool) -> int:
    """Return points for a lemma. Caller is responsible for is_pangram."""
    n = len(lemma)
    if n < MIN_WORD_LENGTH:
        return 0  # shouldn't happen if dictionary is filtered, but defend
    base = 1 if n == 4 else n
    return base + (PANGRAM_BONUS if is_pangram else 0)


@dataclass(frozen=True, slots=True)
class RankThresholds:
    total_points: int
    # Absolute thresholds, parallel to RANKS. Each is the score at which the rank unlocks.
    cutoffs: tuple[int, ...]
    labels: tuple[str, ...]

    def rank_for_score(self, score: int) -> str:
        """Return the rank label for a given score."""
        label = self.labels[0]
        for lbl, cut in zip(self.labels, self.cutoffs):
            if score >= cut:
                label = lbl
            else:
                break
        return label

    def next_cutoff(self, score: int) -> int | None:
        """The next rank's score threshold, or None if at Гений."""
        for cut in self.cutoffs:
            if cut > score:
                return cut
        return None


def thresholds_for(total_points: int) -> RankThresholds:
    """Compute absolute rank cutoffs for a puzzle with given total points."""
    cuts = tuple(round(total_points * pct / 100) for _, pct in RANKS)
    labels = tuple(lbl for lbl, _ in RANKS)
    return RankThresholds(total_points=total_points, cutoffs=cuts, labels=labels)
