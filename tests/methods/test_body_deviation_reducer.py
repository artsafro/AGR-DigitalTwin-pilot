"""Reducer unit control for building_body deviation max/p95 (improvement card t_c7547350).

Pattern: new-case: unit control of the building_body max/p95 reducer with a frozen sample set.

This is a reducer unit control ONLY. It is NOT verification of real sample_surface spacing, geometric
completeness or bidirectional deviation: _samples is monkeypatched to a frozen set of genuine source-surface
points, and the REAL nearest_triangle_distance measures them against a hand-written variant box.
"""
from __future__ import annotations

import numpy as np
import pytest

from tests.methods.test_building_body import rb_of
from tests.methods.test_methods_catalog import BOX_T, box, mesh, mm

SPACING, STRIDE = 0.123, 7  # explicit stub metadata, deliberately not production values
SRC_V = [(0, 0, .25), (19 / 32, 0, .25), (19 / 32, 1, .25), (0, 1, .25)]
SRC_T = [(0, 1, 2), (0, 2, 3)]


def _source():
    return rb_of(mesh("SM_Test_Main", SRC_V, SRC_T))


def _variant():  # box x in [-1, 0]: every sample (i/32, .5, .25) is exactly i/32 from face x=0
    return rb_of(mesh("SM_Test_Main", box((-1, 0, 0), (0, 1, 1)), BOX_T))


def _pts(xs):
    return np.array([(x, .5, .25) for x in xs], float)


def _p95(vals):  # independent stdlib linear interpolation at rank (n-1)*95/100
    s = sorted(vals)
    r = (len(s) - 1) * 95 / 100
    lo = int(r)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (r - lo)


@pytest.fixture
def spy(monkeypatch):
    calls = []
    state = {"pts": _pts([i / 32 for i in range(20)])}

    def fake(v, t, max_points):
        calls.append((np.array(v), np.array(t), max_points))
        return state["pts"], SPACING, STRIDE

    monkeypatch.setattr(mm, "_samples", fake)
    return calls, state


def test_independent_max_p95_and_metadata(spy):
    calls, _ = spy
    dists = [i / 32 for i in range(20)]
    b = mm.building_body(_variant(), _source())
    assert b["deviation_max_m"] == round(max(dists), 4) == 0.5938
    assert b["deviation_p95_m"] == round(_p95(dists), 4)
    assert b["deviation_p95_m"] != b["deviation_max_m"] and 0 < b["deviation_p95_m"] < b["deviation_max_m"]
    assert b["deviation_samples"] == 20
    assert b["deviation_sample_spacing_m"] == SPACING and b["deviation_sample_stride"] == STRIDE
    assert b["deviation_reason"] is None
    # sampler got the SOURCE rectangle, not the variant box, and was called once
    assert len(calls) == 1
    v, t, _ = calls[0]
    assert np.allclose(v, np.array(SRC_V, float)) and t.shape == (2, 3)


def test_reversed_order_same_result(spy):
    _, state = spy
    fwd = mm.building_body(_variant(), _source())
    state["pts"] = state["pts"][::-1].copy()
    rev = mm.building_body(_variant(), _source())
    for k in ("deviation_max_m", "deviation_p95_m", "deviation_samples"):
        assert fwd[k] == rev[k]


def test_single_point(spy):
    _, state = spy
    state["pts"] = _pts([.25])
    b = mm.building_body(_variant(), _source())
    assert b["deviation_max_m"] == b["deviation_p95_m"] == .25 and b["deviation_samples"] == 1


def test_all_zero_x_samples_give_zero(spy):
    _, state = spy
    state["pts"] = _pts([0.0, 0.0, 0.0])
    b = mm.building_body(_variant(), _source())
    assert b["deviation_max_m"] == 0 and b["deviation_p95_m"] == 0 and b["deviation_samples"] == 3


def test_max_points_forwarded_inputs_unchanged(spy):
    calls, _ = spy
    src, var = _source(), _variant()
    import copy
    before = copy.deepcopy((src, var))
    base = mm.building_body(var, src)
    b = mm.building_body(var, src, max_points=3)
    assert calls[-1][2] == 3
    for k in ("deviation_max_m", "deviation_p95_m", "deviation_samples"):
        assert b[k] == base[k]
    assert (src, var) == before


def test_stub_restored_after_fixture():
    assert mm._samples.__name__ == "_samples"
