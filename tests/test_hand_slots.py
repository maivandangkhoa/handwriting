from src.hand_slots import HandSlots


def test_two_hands_get_distinct_slots_and_keep_them_while_moving():
    s = HandSlots()
    first = s.assign([(3.0, 4.0), (10.0, 4.0)])
    assert sorted(first) == [0, 1]
    for dx in (0.5, 1.0, 1.5):
        again = s.assign([(3.0 + dx, 4.0), (10.0 - dx, 4.0)])
        assert again == first


def test_order_in_the_list_does_not_matter():
    s = HandSlots()
    a, b = s.assign([(3.0, 4.0), (10.0, 4.0)])
    swapped = s.assign([(10.2, 4.0), (3.2, 4.0)])
    assert swapped == [b, a]


def test_single_hand_keeps_its_slot_and_a_returning_hand_reuses_a_free_one():
    s = HandSlots()
    first = s.assign([(3.0, 4.0), (10.0, 4.0)])
    only_right = s.assign([(10.1, 4.0)])
    assert only_right == [first[1]]
    both = s.assign([(3.0, 4.0), (10.1, 4.0)])
    assert both == first


def test_more_hands_than_slots_and_reset():
    s = HandSlots(max_slots=2)
    ids = s.assign([(1.0, 1.0), (5.0, 1.0), (9.0, 1.0)])
    assert ids.count(None) == 1 and sorted(i for i in ids if i is not None) == [0, 1]
    s.reset()
    assert s.assign([(2.0, 2.0)]) == [0]


def test_a_far_jump_is_a_new_hand_and_the_other_hand_keeps_its_slot():
    s = HandSlots(max_jump=5.0)
    left, right = s.assign([(2.0, 4.0), (12.0, 4.0)])
    ids = s.assign([(2.1, 4.0), (6.0, 4.0)])       # second hand moved 6 units in one frame: not the same hand
    assert ids[0] == left and ids[1] == right      # it simply takes the only free slot
