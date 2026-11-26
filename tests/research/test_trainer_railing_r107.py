from docs.research.trainer_railing_r107.replay import FLOOR, RAIL, pick_face, stated, witness

ROWS = [
    (1, 'Wall', [1, 2, 4.65], [4, 6, 7]),
    (2, 'Wall', [0, 3, 7], [5, 7, 8]),
    (3, RAIL + ' Стеклянное огражд_1', [-2, 0, 5], [9, 9, 6]),
    (4, FLOOR + ' example', [-9, -9, 7], [9, 9, 8]),
    (5, 'Wall', [-8, -8, 4.64], [8, 8, 7]),
]


def test_stated_drops_railings_and_floors_half_open():
    expected = {'ids': [1, 2], 'bounds_m': [[0, 2, 4.65], [5, 7, 8]]}
    assert stated(ROWS, (4.65, 8)) == expected
    assert stated(list(reversed(ROWS)), (4.65, 8)) == expected
    assert stated(ROWS, (4.65, 8), drop_rails=False)['ids'] == [1, 2, 3]
    assert stated(ROWS, None) is None
    assert stated(ROWS, (8.5, 9)) is None


def test_witness_face_needs_headroom_in_fixed_order():
    sel = stated(ROWS, (4.65, 8))
    assert pick_face(sel, {'min': [-1, -1, 0], 'max': [5.5, 7.7, 99]}) == ('xmin', 0)
    assert pick_face(sel, {'min': [-0.5, 1.5, 0], 'max': [5.5, 7.5, 99]}) is None
    face = pick_face(sel, {'min': [-9, -9, 0], 'max': [9, 9, 99]})
    assert face == ('xmax', 3)
    row = witness(sel, (4.65, 8), face, 'SYNTHETIC facade')
    assert row[3][0] == 5.5 and row[2][0] == 0 and row[2][2] == (4.65 + 8) / 2
