from src.typing_eval import TypingEvaluator


def ev():
    return TypingEvaluator(window=0.6)


def test_perfect_prediction_is_correct():
    e = ev()
    e.add_truth("a", 1.0); e.add_pred("a", 1.2)
    s = e.stats(now=10.0)
    assert (s.correct, s.wrong, s.missed, s.false_pos) == (1, 0, 0, 0) and s.accuracy == 1.0


def test_wrong_key_missed_and_false_positive():
    e = ev()
    e.add_truth("a", 1.0); e.add_pred("s", 1.1)      # wrong key
    e.add_truth("b", 3.0)                           # missed
    e.add_pred("z", 5.0)                            # false positive
    s = e.stats(now=10.0)
    assert (s.correct, s.wrong, s.missed, s.false_pos) == (0, 1, 1, 1)
    assert s.accuracy == 0.0


def test_recent_events_are_pending_not_scored():
    e = ev()
    e.add_truth("a", 9.8); e.add_pred("q", 9.9)
    s = e.stats(now=10.0)
    assert s.missed == 0 and s.false_pos == 0


def test_prefers_matching_character_and_nearest_time():
    e = ev()
    e.add_truth("a", 1.0)
    e.add_pred("b", 1.0); e.add_pred("a", 1.4)
    s = e.stats(now=10.0)
    assert s.correct == 1 and s.false_pos == 1


def test_accuracy_none_without_data_and_clear():
    e = ev()
    assert e.stats(1.0).accuracy is None
    e.add_truth("a", 0.0); e.clear()
    assert e.stats(5.0).truth == 0
