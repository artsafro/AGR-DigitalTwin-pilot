from offset import match, veto


def test_repeated_disjoint_match_is_rejected():
    query = [0, 1, 1, 0, 0, 0, 0, 1, 0, 0]
    curve = match(query, query + [0] * 20 + query, lambda x: x, lambda a, b: float((a == b).all()), 6)
    assert veto(curve)[0] is True


def test_adjacent_tie_has_no_distinct_interval():
    assert veto((4, [(0, 0.8), (1, 0.8), (3, 0.8)])) == (False, 0, 0.8, None, None)


def test_half_width_separation_and_boundary():
    assert veto((25, [(0, 0.5), (12, 0.5), (13, 0.4)])) == (True, 0, 0.5, 13, 0.4)
    assert veto((25, [(0, 0.5), (13, 0.399)]))[0] is False


def test_no_second_alignment_does_not_veto():
    assert veto((20, [(0, 0.8)])) == (False, 0, 0.8, None, None)
