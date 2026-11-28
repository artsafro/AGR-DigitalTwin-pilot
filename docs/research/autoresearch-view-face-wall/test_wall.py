"""#153 research harness tests (synthetic only; no customer inputs).

new-case: docs/research/autoresearch-view-face-wall/test_wall.py - #153 wall gate tests
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wall as WL  # noqa: E402


def _u(v, m):  # toy agreement: fraction of equal labels
    return float(np.mean(v == m))


def test_planes_split_at_gap_and_mode():
    dep = np.array([[5.0, 5.2, np.nan, 1.0, 1.1]] * 3)
    cp = WL.planes(WL.column_depth(dep), 1.0)
    assert cp.tolist() == [1, 1, -1, 0, 0]
    assert WL.interval_wall(cp, 0, 2) == 1 and WL.interval_wall(cp, 2, 5) == 0
    assert WL.interval_wall(cp, -3, 0) == -1


def test_periodic_same_wall_answers_and_cross_wall_abstains():
    model = np.tile(np.array([[1, 2, 1, 2, 1, 2, 1, 2]]), (4, 1))
    view = model[:, :2].copy()
    same = np.zeros(8, np.int32)  # one wall: periodic repeats do not matter
    start, w0, w1, walls = WL.localise(WL.profile(view, model, 0, _u), same, 0, 2, 0.05)
    assert (start, w0, w1, walls) == (0, 0, 0, [0])
    split = np.array([0, 0, 0, 0, 1, 1, 1, 1], np.int32)  # repeats land on two walls -> abstain
    start, w0, w1, walls = WL.localise(WL.profile(view, model, 0, _u), split, 0, 2, 0.05)
    assert w0 == 0 and w1 is None and walls == [0, 1]


def test_unique_offset_on_second_wall():
    model = np.tile(np.array([[1, 1, 1, 1, 3, 4, 1, 1]]), (4, 1))
    split = np.array([0, 0, 0, 0, 1, 1, 1, 1], np.int32)
    start, w0, w1, _ = WL.localise(WL.profile(model[:, 4:6].copy(), model, 0, _u), split, 0, 2, 0.05)
    assert (start, w0, w1) == (4, 1, 1)
    assert WL.outcome(90, 90, w1, 1) == 'correct' and WL.outcome(90, 90, None, 1) == 'abstain'
    assert WL.outcome(0, 90, 1, 1) == 'wrong'


def _row(case, w, nontrivial=False, w0=None):
    return dict(case=case, W0=w if w0 is None else w0, W1=w, nontrivial=nontrivial)


def _verdict(rows):
    nt = [r for r in rows if r['nontrivial']]
    return WL.verdict(rows, WL.summarize(rows, 'W1'), WL.summarize(nt, 'W1'))


def _base():
    return [_row('full', 'correct')] + [_row('partial25@0.0', 'correct') for _ in range(30)]


def test_nontrivial_all_abstained_is_inconclusive():  # #2075
    rows = _base() + [_row('partial40@0.0', 'abstain', nontrivial=True) for _ in range(5)]
    hyp, checks, gate = _verdict(rows)
    assert all(checks.values())
    assert gate['nontrivial_crops_exercised'] == 0
    assert gate['nontrivial_crops_abstained'] == 5
    assert hyp == 'inconclusive'


def test_nontrivial_answered_counts_toward_confirmed():  # #2075
    rows = _base() + [_row('partial40@0.0', 'correct', nontrivial=True) for _ in range(5)]
    rows.append(_row('partial40@0.5', 'abstain', nontrivial=True))
    hyp, _, gate = _verdict(rows)
    assert gate['nontrivial_crops_exercised'] == 5
    assert gate['nontrivial_abstain_rate'] == round(1 / 6, 4)
    assert hyp == 'confirmed'
