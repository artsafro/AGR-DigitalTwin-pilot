"""Focused witnesses for the #148 research variant."""
import runpy
from pathlib import Path

import numpy as np

API = runpy.run_path(str(Path(__file__).with_name('run.py')))
SPAN, VETO = API['span'], API['veto']


def test_adjacent_planes_do_not_concatenate():
    depth = np.tile([1.] * 10 + [2.] * 10, (10, 1))
    facing = np.ones_like(depth)
    assert SPAN(depth, facing, .1) == 1.
    assert SPAN(depth, facing * 0, .1) == 0.
    assert SPAN(depth[:-1], facing[:-1], .1) == 0.


def test_only_short_interior_gap_bridges():
    depth = np.tile([np.nan] * 3 + [1.] * 5 + [np.nan] * 5 + [1.] * 5, (10, 1))
    assert SPAN(depth, np.ones_like(depth), .1) == 1.5
    depth[:, 7] = np.nan
    assert SPAN(depth, np.ones_like(depth), .1) == .5


def test_slack_boundary_and_non_rescue():
    assert VETO('0', 1.6, {'0': 1.}) == '0'
    assert VETO('0', 1.600001, {'0': 1.}) is None
    assert VETO(None, 1., {}) is None
    assert VETO('0', .4, {'0': 0.}) is None
