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
