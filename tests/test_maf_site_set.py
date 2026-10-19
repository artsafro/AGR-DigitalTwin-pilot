"""Synthetic tests for tools/library/maf_site_set.py (#313)."""

import importlib.util
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "tools" / "library" / "maf_site_set.py"
    spec = importlib.util.spec_from_file_location("maf_site_set", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mss = _load()


# --- dimension verdict [D094] -------------------------------------------------

def test_dimension_pass_within_tolerance():
    out = mss.dimension_verdict([1.80, 0.47, 0.80], [1.8, 0.5, 0.72])
    assert out["verdict"] == "pass"
    assert out["plan_axes_swapped"] is False


def test_dimension_plan_swap_allowed_height_not():
    out = mss.dimension_verdict([0.5, 1.8, 0.72], [1.8, 0.5, 0.72])
    assert out["verdict"] == "pass" and out["plan_axes_swapped"] is True
    out = mss.dimension_verdict([1.8, 0.72, 0.5], [1.8, 0.5, 0.72])
    assert out["verdict"] == "fail"


def test_dimension_fail_over_tolerance():
    out = mss.dimension_verdict([1.708, 1.999, 2.387], [1.09, 1.09, None])
    assert out["verdict"] == "fail"


def test_dimension_missing_size_is_review_not_pass():
    out = mss.dimension_verdict([1.0, 1.0, 0.5], [1.0, 1.0, None])
    assert out["verdict"] == "review"


def test_dimension_user_exception_turns_fail_into_review_with_reason():
    out = mss.dimension_verdict([1.708, 1.999, 2.387], [1.09, 1.09, None], exception="Q8 seat diameter")
    assert out["verdict"] == "review"
    assert "Q8" in out["reason"]
    # an exception never upgrades to pass
    out = mss.dimension_verdict([1.09, 1.09, 1.0], [1.09, 1.09, 1.0], exception="x")
    assert out["verdict"] == "review"


def test_dimension_exactly_at_threshold_is_pass_like_maf_checks():
    out = mss.dimension_verdict([1.1, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert out["verdict"] == "pass"
    out = mss.dimension_verdict([1.1001, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert out["verdict"] == "fail"


@pytest.mark.parametrize("bad", [[1, 1], [1, 1, float("nan")], [1, 1, float("inf")], [1, -1, 1],
                                 [1, 1, 0], None, [True, 1, 1], "abc"])
def test_dimension_bad_measured_raises(bad):
    with pytest.raises(ValueError):
        mss.dimension_verdict(bad, [1, 1, 1])


@pytest.mark.parametrize("bad", [[1, 1], [1, float("nan"), 1], [1, 0, 1], [None, None, None]])
def test_dimension_bad_schedule_raises(bad):
    with pytest.raises(ValueError):
        mss.dimension_verdict([1, 1, 1], bad)


def test_dimension_probe_random_never_pass_beyond_tolerance():
    rng = random.Random(313)
    for _ in range(2000):
        spec = [rng.uniform(0.2, 5) for _ in range(3)]
        meas = [s + rng.uniform(-0.3, 0.3) for s in spec]
        meas = [max(m, 0.01) for m in meas]
        if rng.random() < 0.5:
            meas[0], meas[1] = meas[1], meas[0]
        out = mss.dimension_verdict(meas, spec)
        plan_ok = min(
            max(abs(meas[0] - spec[0]), abs(meas[1] - spec[1])),
            max(abs(meas[1] - spec[0]), abs(meas[0] - spec[1])),
        ) <= 0.1 + 1e-9
        ok = plan_ok and abs(meas[2] - spec[2]) <= 0.1 + 1e-9
        assert (out["verdict"] == "pass") == ok


# --- budget [D097] -----------------------------------------------------------

def _row(pid, raw, npm, vpm, n):
    return {"set_id": pid, "tris_raw": raw, "tris_npm": npm, "tris_vpm": vpm, "instances": n}


def test_budget_totals_and_under_share():
    out = mss.budget([_row("a", 100, 50, 100, 4), _row("b", 10, 10, 10, 1)], npm_share=1000)
    assert out["npm_total"] == 210 and out["vpm_total"] == 410 and out["raw_total"] == 410
    assert out["npm_within_share"] is True and out["overrun"] == []


def test_budget_at_share_is_within_and_over_lists_causes():
    out = mss.budget([_row("a", 10, 10, 10, 100)], npm_share=1000)
    assert out["npm_within_share"] is True
    out = mss.budget([_row("a", 10, 10, 10, 100), _row("b", 1, 1, 1, 1)], npm_share=1000)
    assert out["npm_within_share"] is False
    assert out["overrun"][0]["set_id"] == "a" and out["overrun_tris"] == 1


@pytest.mark.parametrize("bad", [[], [_row("a", -1, 1, 1, 1)], [_row("a", 1, 1.5, 1, 1)],
                                 [_row("a", 1, 1, 1, True)], [_row("a", 1, None, 1, 1)],
                                 [{"set_id": "a"}]])
def test_budget_bad_input_raises(bad):
    with pytest.raises(ValueError):
        mss.budget(bad, npm_share=60000)


# --- UV inside the material slot -------------------------------------------

RECTS = {"steel": [0.0, 0.0, 0.25, 0.25], "wood": [0.5, 0.5, 0.75, 0.75]}


def test_uv_inside_and_outside_counted_per_material():
    faces = [("steel", [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]),
             ("wood", [(0.6, 0.6), (0.7, 0.6), (0.8, 0.7)]),
             ("wood", [(0.6, 0.6), (0.7, 0.6), (0.7, 0.7)])]
    out = mss.uv_slot_report(faces, RECTS)
    assert out["faces_outside"] == 1
    assert out["materials"]["steel"]["outside"] == 0
    assert out["materials"]["wood"]["faces"] == 2 and out["materials"]["wood"]["outside"] == 1


def test_uv_boundary_inside_unknown_and_nan_outside():
    faces = [("steel", [(0.0, 0.0), (0.25, 0.25), (0.0, 0.25)]),
             ("glass", [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]),
             ("steel", [(float("nan"), 0.1), (0.2, 0.1), (0.2, 0.2)]),
             (None, [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]),
             ("steel", [])]
    out = mss.uv_slot_report(faces, RECTS)
    assert out["materials"]["steel"]["outside"] == 2
    assert out["materials"]["glass"]["outside"] == 1
    assert out["materials"]["None"]["outside"] == 1
    assert out["faces_outside"] == 4


def test_uv_empty_raises():
    with pytest.raises(ValueError):
        mss.uv_slot_report([], RECTS)


def test_uv_probe_random():
    rng = random.Random(7)
    faces, expected = [], 0
    for _ in range(3000):
        name = rng.choice(["steel", "wood"])
        u0, v0, u1, v1 = RECTS[name]
        pts = []
        bad = False
        for _ in range(3):
            u, v = rng.uniform(-0.1, 1.1), rng.uniform(-0.1, 1.1)
            pts.append((u, v))
            bad |= not (u0 - 1e-9 <= u <= u1 + 1e-9 and v0 - 1e-9 <= v <= v1 + 1e-9)
        expected += bad
        faces.append((name, pts))
    assert mss.uv_slot_report(faces, RECTS)["faces_outside"] == expected


def test_remap_into_rect_stays_inside():
    rng = random.Random(1)
    for _ in range(500):
        t = (rng.random(), rng.random())
        u, v = mss.remap_into_rect(t, RECTS["wood"])
        assert 0.5 <= u <= 0.75 and 0.5 <= v <= 0.75
    with pytest.raises(ValueError):
        mss.remap_into_rect((1.5, 0.5), RECTS["wood"])
    with pytest.raises(ValueError):
        mss.remap_into_rect((float("nan"), 0.5), RECTS["wood"])


# --- dominant upward plane (table-top height) -------------------------------

def test_dominant_up_plane_picks_largest_area():
    faces = [(0.76, 2.0, 1.0), (0.761, 2.1, 1.0), (0.91, 0.3, 1.0), (0.0, 5.0, -1.0), (0.4, 9.0, 0.2)]
    z = mss.dominant_up_plane(faces)
    assert math.isclose(z, 0.76, abs_tol=0.005)


def test_dominant_up_plane_none_up_raises():
    with pytest.raises(ValueError):
        mss.dominant_up_plane([(0.0, 1.0, -1.0)])
    with pytest.raises(ValueError):
        mss.dominant_up_plane([])
