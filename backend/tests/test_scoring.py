from rsb.scoring import PANGRAM_BONUS, RANKS, points_for, thresholds_for


def test_four_letter_word_one_point_no_pangram():
    assert points_for("дом!", is_pangram=False) == 1  # 4 chars
    assert points_for("окно", is_pangram=False) == 1


def test_five_or_more_letters_one_point_per_letter():
    assert points_for("книга", is_pangram=False) == 5
    assert points_for("красивый", is_pangram=False) == 8


def test_pangram_adds_bonus():
    assert points_for("книга", is_pangram=True) == 5 + PANGRAM_BONUS
    # Four-letter pangram (hypothetical): base 1 + bonus 7 = 8.
    assert points_for("домс", is_pangram=True) == 1 + PANGRAM_BONUS


def test_three_letter_words_score_zero():
    # Defensive: dictionary should filter these, but if one sneaks through
    # it shouldn't crash and shouldn't earn points.
    assert points_for("кот", is_pangram=False) == 0


def test_thresholds_ordered_and_complete():
    t = thresholds_for(100)
    assert len(t.cutoffs) == len(RANKS)
    assert t.labels[0] == "Новичок"
    assert t.labels[-1] == "Гений"
    # Monotonic non-decreasing.
    for a, b in zip(t.cutoffs, t.cutoffs[1:]):
        assert a <= b


def test_rank_for_score_steps_through_ranks():
    t = thresholds_for(200)  # cutoffs: 0,10,24,50,80,110,140,170,200
    assert t.rank_for_score(0) == "Новичок"
    assert t.rank_for_score(10) == "Ученик"
    assert t.rank_for_score(50) == "Мастер"
    assert t.rank_for_score(200) == "Гений"
    assert t.rank_for_score(500) == "Гений"  # over-max stays at top


def test_next_cutoff():
    t = thresholds_for(200)
    assert t.next_cutoff(0) == 10
    assert t.next_cutoff(200) is None
