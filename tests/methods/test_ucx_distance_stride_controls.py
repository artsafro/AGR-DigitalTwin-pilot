"""LEGACY CHARACTERIZATION of injected ucx_fit distance_stride / inside-zero population.

Pattern: new-case: tests pinning the legacy ucx_fit distance_stride/inside-zero population (#784 proposal 1).

The sample order below is injected by replacing `_samples`. It is not production `_samples`
and not real surface sampling. The measured subset (every inside zero, plus outside ranks
0, stride, 2*stride, ... in injected order) is a LEGACY CHARACTERIZATION of today's reducer,
not an approved approximation policy. A change to the max guarantee, the weighting, or the
pair cap is a user decision. delivery_passed=false. Synthetic unit box only.
"""
from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from tests.methods.test_methods_catalog import BOX_T, box, mesh, mm, scene

# Acceptance table (input -> expected), literal, before the runner.
# Production rounds max/p95 with round(..., 4) and shares with round(..., 5).
# These rows match that rounding exactly, so asserts are == (no 1e-4 / 1e-5 band).
# share_over_m keys are "0.10", "0.30", "1.00" in that order.

_SHARES_S1 = {"0.10": 0.41176, "0.30": 0.29412, "1.00": 0.11765}
_SHARES_S2 = {"0.10": 0.23077, "0.30": 0.15385, "1.00": 0.07692}
_SHARES_S3 = {"0.10": 0.16667, "0.30": 0.16667, "1.00": 0.08333}

# Nine inside zeros first: the 8 corners of (0.25|0.75)^3, then the centre.
INSIDE_XYZ = (
    (0.25, 0.25, 0.25), (0.25, 0.25, 0.75), (0.25, 0.75, 0.25), (0.25, 0.75, 0.75),
    (0.75, 0.25, 0.25), (0.75, 0.25, 0.75), (0.75, 0.75, 0.25), (0.75, 0.75, 0.75),
    (0.5, 0.5, 0.5),
)
# Canonical outside order. Analytic metres, ray (1+d, 0.25, 0.5). Rank 7 is the 5 m outlier.
OUTSIDE_CANONICAL = (
    ((1.0625, 0.25, 0.5), 0.0625),
    ((1.125, 0.25, 0.5), 0.125),
    ((1.25, 0.25, 0.5), 0.25),
    ((1.375, 0.25, 0.5), 0.375),
    ((1.5, 0.25, 0.5), 0.5),
    ((1.75, 0.25, 0.5), 0.75),
    ((3.0, 0.25, 0.5), 2.0),
    ((6.0, 0.25, 0.5), 5.0),
)
# Only the 5 m point moves, to outside rank 0. The other seven keep their relative order.
OUTSIDE_RANK0 = (
    ((6.0, 0.25, 0.5), 5.0),
    ((1.0625, 0.25, 0.5), 0.0625),
    ((1.125, 0.25, 0.5), 0.125),
    ((1.25, 0.25, 0.5), 0.25),
    ((1.375, 0.25, 0.5), 0.375),
    ((1.5, 0.25, 0.5), 0.5),
    ((1.75, 0.25, 0.5), 0.75),
    ((3.0, 0.25, 0.5), 2.0),
)

# Literal retained distances. Not taken from the reducer: stride 1 keeps every sample,
# stride 2 keeps outside ranks 0,2,4,6, stride 3 keeps 0,3,6, and every inside zero stays.
CANONICAL = (
    {"cap": 400_000_000, "distance_stride": 1, "samples": 17, "measured_samples": 17,
     "model_to_ucx_max_m": 5.0, "model_to_ucx_p95_m": 2.6, "share_over_m": _SHARES_S1,
     "retained_m": (0.0,) * 9 + (0.0625, 0.125, 0.25, 0.375, 0.5, 0.75, 2.0, 5.0),
     "keeps_5m": True, "zeros": 9},
    {"cap": 72, "distance_stride": 2, "samples": 17, "measured_samples": 13,
     "model_to_ucx_max_m": 2.0, "model_to_ucx_p95_m": 1.1, "share_over_m": _SHARES_S2,
     "retained_m": (0.0,) * 9 + (0.0625, 0.25, 0.5, 2.0),
     "keeps_5m": False, "zeros": 9},
    {"cap": 40, "distance_stride": 3, "samples": 17, "measured_samples": 12,
     "model_to_ucx_max_m": 2.0, "model_to_ucx_p95_m": 1.1062, "share_over_m": _SHARES_S3,
     "retained_m": (0.0,) * 9 + (0.0625, 0.375, 2.0),
     "keeps_5m": False, "zeros": 9},
)
# Cap 72 / 40 with the outlier on outside rank 0: the max stays 5 m.
RANK0 = (
    {"cap": 72, "model_to_ucx_max_m": 5.0,
     "retained_m": (0.0,) * 9 + (5.0, 0.125, 0.375, 0.75)},
    {"cap": 40, "model_to_ucx_max_m": 5.0,
     "retained_m": (0.0,) * 9 + (5.0, 0.25, 0.75)},
)
# No inside points, canonical outside order, cap 72. Outside-only stride-2 population.
NO_INSIDE = {
    "cap": 72, "samples": 8, "measured_samples": 4,
    "model_to_ucx_max_m": 2.0, "model_to_ucx_p95_m": 1.775,
    "share_over_m": {"0.10": 0.75, "0.30": 0.5, "1.00": 0.25},
    "retained_m": (0.0625, 0.25, 0.5, 2.0),
}
# Nine inside points, cap 72. len(out) == 0 forces distance_stride 1; every share is 0.
ALL_INSIDE = {
    "cap": 72, "distance_stride": 1, "samples": 9, "measured_samples": 9,
    "model_to_ucx_max_m": 0.0, "model_to_ucx_p95_m": 0.0,
    "share_over_m": {"0.10": 0.0, "0.30": 0.0, "1.00": 0.0},
    "retained_m": (0.0,) * 9,
}

_SHARE_KEYS = ("0.10", "0.30", "1.00")
_SHARE_LIMITS = (0.10, 0.30, 1.00)


def _p95(values):
    """Stdlib linear percentile. k = (n - 1) * 0.95, then interpolate floor(k) and ceil(k).

    Not np.percentile and not the production selector.
    """
    ordered = sorted(values)
    k = (len(ordered) - 1) * 0.95
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _shares(values):
    n = len(values)
    return {f"{limit:.2f}": round(sum(d > limit for d in values) / n, 5) for limit in _SHARE_LIMITS}


def _oracle(retained):
    """Same rounding ucx_fit publishes: round(max/p95, 4), round(share, 5)."""
    return {
        "model_to_ucx_max_m": round(max(retained), 4),
        "model_to_ucx_p95_m": round(_p95(retained), 4),
        "share_over_m": _shares(retained),
        "measured_samples": len(retained),
        "zeros": sum(d == 0.0 for d in retained),
    }


def _xyz(inside, outside):
    return [p for p in inside] + [p for p, _d in outside]


def _unit_scene():
    model = mesh("SM_Test_Main", box((0, 0, 0), (1, 1, 1)), BOX_T)
    assert len(model["face_geometry"]["polygons"]) == 12
    rb, extra = scene(ucx_lo=(0, 0, 0), ucx_hi=(1, 1, 1), model=model)
    ucx = rb["meshes"][1]
    assert ucx["name"] == "UCX_SM_Test_Main_001"
    assert len(ucx["face_geometry"]["polygons"]) == 12
    return rb, extra


def _fit(monkeypatch, xyz, cap):
    """Two ucx_fit calls. Patches only _samples and FIT_MAX_PAIRS; both restore with the fixture."""
    injected = np.array(xyz, dtype=float)
    pristine = injected.copy()
    handed = []

    def _samples(_v, _t, _max_points):
        arr = injected.copy()  # new copy per call; injected itself stays put
        handed.append(arr)
        return arr, 0.0, 1

    monkeypatch.setattr(mm, "_samples", _samples)
    monkeypatch.setattr(mm, "FIT_MAX_PAIRS", cap)
    rb, extra = _unit_scene()
    rb_before, extra_before = copy.deepcopy(rb), copy.deepcopy(extra)
    first = mm.ucx_fit(rb, extra)
    second = mm.ucx_fit(rb, extra)
    assert first == second
    assert rb == rb_before and extra == extra_before
    assert len(handed) == 2 and handed[0] is not handed[1]
    assert np.array_equal(injected, pristine)
    for arr in handed:
        assert np.array_equal(arr, pristine)
    return first


def _assert_population(fit, row):
    expect = _oracle(row["retained_m"])
    # The independent oracle lands on the literal table with no last-decimal slack.
    for key in ("model_to_ucx_max_m", "model_to_ucx_p95_m", "share_over_m", "measured_samples"):
        assert expect[key] == row[key]
    assert list(expect["share_over_m"]) == list(_SHARE_KEYS)
    assert fit["samples"] == row["samples"]
    assert fit["measured_samples"] == row["measured_samples"]
    assert fit["model_to_ucx_max_m"] == row["model_to_ucx_max_m"]
    assert fit["model_to_ucx_p95_m"] == row["model_to_ucx_p95_m"]
    assert fit["share_over_m"] == row["share_over_m"]
    assert fit["reason"] is None


@pytest.mark.parametrize("row", CANONICAL, ids=lambda r: f"cap_{r['cap']}_stride_{r['distance_stride']}")
def test_canonical_outside_order(monkeypatch, row):
    fit = _fit(monkeypatch, _xyz(INSIDE_XYZ, OUTSIDE_CANONICAL), row["cap"])
    assert fit["distance_stride"] == row["distance_stride"]
    _assert_population(fit, row)
    # Stride 1 at the production cap keeps the 5 m sample. Stride > 1 drops it and still
    # counts every inside zero: zero fraction 9/17, 9/13, 9/12 via measured_samples.
    assert (5.0 in row["retained_m"]) is row["keeps_5m"]
    assert (fit["model_to_ucx_max_m"] == 5.0) is row["keeps_5m"]
    assert row["zeros"] == 9
    assert fit["measured_samples"] == row["measured_samples"]
    assert row["zeros"] == sum(d == 0.0 for d in row["retained_m"])


@pytest.mark.parametrize("row", RANK0, ids=lambda r: f"cap_{r['cap']}")
def test_outlier_at_outside_rank_0_keeps_max_5m(monkeypatch, row):
    fit = _fit(monkeypatch, _xyz(INSIDE_XYZ, OUTSIDE_RANK0), row["cap"])
    expect = _oracle(row["retained_m"])
    assert expect["model_to_ucx_max_m"] == row["model_to_ucx_max_m"] == 5.0
    assert 5.0 in row["retained_m"]
    assert fit["model_to_ucx_max_m"] == 5.0
    assert fit["samples"] == 17
    assert fit["measured_samples"] == expect["measured_samples"]
    assert fit["model_to_ucx_p95_m"] == expect["model_to_ucx_p95_m"]
    assert fit["share_over_m"] == expect["share_over_m"]
    assert fit["reason"] is None


def test_no_inside_canonical_cap_72(monkeypatch):
    fit = _fit(monkeypatch, _xyz((), OUTSIDE_CANONICAL), NO_INSIDE["cap"])
    _assert_population(fit, NO_INSIDE)
    assert sum(d == 0.0 for d in NO_INSIDE["retained_m"]) == 0


def test_all_inside_cap_72(monkeypatch):
    fit = _fit(monkeypatch, list(INSIDE_XYZ), ALL_INSIDE["cap"])
    assert fit["distance_stride"] == ALL_INSIDE["distance_stride"] == 1
    _assert_population(fit, ALL_INSIDE)
