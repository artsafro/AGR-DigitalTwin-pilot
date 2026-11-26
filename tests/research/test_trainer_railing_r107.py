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


# End-to-end probe -> verdict with the real bounds_step (review r1 P1): frozen per-pair bounds gate the verdict.
from types import SimpleNamespace

import pytest

from docs.research.trainer_railing_r107.replay import SCOPE, probe, verdict
from tools.trainer.trainer import bounds_step


def _readback(sel):  # same as the pinned R105 runner
    return {'readback_ok': True, 'meshes': [{'bounds_m': sel['bounds_m'], 'polygons': 0}]}


def _box_of(doc):
    return ([min(m['bounds_m'][0][i] for m in doc['meshes']) for i in range(3)],
            [max(m['bounds_m'][1][i] for m in doc['meshes']) for i in range(3)])


RUNNER = SimpleNamespace(
    contained=lambda rows, box: [r for r in rows if all(a <= b <= c <= d for a, b, c, d in
                                                         zip(box['min'], r[2], r[3], box['max']))],
    as_readback=_readback, box_of=_box_of, bounds_step=bounds_step)


def _tower(tag, wall, rail):
    lo, hi = SCOPE[tag]
    key = {'readback_ok': True, 'meshes': [{'bounds_m': [[0, 0, lo], [4, 4, hi]], 'polygons': 0}]}
    rows = [(1, 'Wall', [wall[0], wall[1], lo + .5], [wall[2], wall[3], hi - .5]),
            (2, RAIL + ' Стеклянное', [rail[0], rail[1], lo + .5], [rail[2], rail[3], lo + 1.5])]
    box = {'id': tag, 'min': [-1, -1, 0], 'max': [6, 6, 99]}
    return probe(RUNNER, rows, box, key, key)


@pytest.mark.parametrize('a_wall, b_wall, b_rail, expected', [
    ((0, 0, 3.97, 4), (0, 0, 4.00, 4), (0, 0, 4.20, 4), 'confirmed'),      # in-limit control: 63A 0 -> 0.03 m
    ((0, 0, 3.93, 4), (0, 0, 4.00, 4), (0, 0, 4.20, 4), 'inconclusive'),   # 63A 0 -> 0.07 m, both native pass
    ((0, 0, 3.97, 4), (.30, 0, 4.20, 4), (0, 0, 1, 4), 'inconclusive'),    # 63B 0.20 -> 0.30 m, both fail
    ((0, 0, 3.97, 4), (.10, 0, 4.20, 4), (0, 0, 1, 4), 'refuted'),         # in-limit 63B: 0.20 -> 0.20 m
])
def test_probe_verdict_enforces_frozen_pair_bounds(a_wall, b_wall, b_rail, expected):
    a, b = _tower('63A', a_wall, (0, 0, 4, 4)), _tower('63B', b_wall, b_rail)
    pair = {'status': 'complete', '63A': a, '63B': b}
    assert verdict([pair] * 3, 'complete') == expected
    assert a['coverage']['rail_rule'] == b['coverage']['rail_rule'] == 'exercised'
    assert all(v for k, v in {**a['controls'], **b['controls']}.items() if k != 'frozen_bound')
    if expected == 'inconclusive':
        assert not (a['bound_check']['ok'] and b['bound_check']['ok'])
    else:
        assert a['bound_check']['ok'] and b['bound_check']['ok']
