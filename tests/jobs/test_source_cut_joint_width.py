"""new-case: inclusive joint half-width boundary, mm->m conversion and default control of cut_joint_report.

Characterization of the current cut_joint_report (GREEN at baseline). Custom joint_half_mm
values are synthetic function inputs, not approved real joint widths.

Source: one outward -Y quad, vertices (0,0,1), (4,0,1), (4,0,3), (0,0,3), finish "F",
P=[1,1], zero_m=0, facade_uv=["F"], no facades key. Hand frame (axis, sign, origin) = (0, +1, 0).
shift=[0,0,0]. One new point (x, 0, 1) on the bottom edge.

Baseline disagreement (see test_adjacent_float_rounds_onto_boundary): _new_vertices rounds to
5 decimals, so math.nextafter(0.125, 1) becomes 0.125 and the report stays the on-boundary pass.
The card's fail expectation for that witness is not the baseline. Tolerance policy is unchanged.
"""
import copy
import math
import sys
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jobs/TEC26-OKS/scripts"))
import finish_map  # noqa: E402
import qa_packages  # noqa: E402

SRC = [(0.0, 0.0, 1.0), (4.0, 0.0, 1.0), (4.0, 0.0, 3.0), (0.0, 0.0, 3.0)]
FACE = [0, 1, 2, 3]
FINISH = "F"
HALF = Fraction(1, 8)

PASS = {
    "ok": True,
    "new_vertices": 1,
    "checked_on_patterned_edges": 1,
    "off_joint": [],
    "off_joint_count": 0,
}
VACUOUS = {
    "ok": True,
    "new_vertices": 0,
    "checked_on_patterned_edges": 0,
    "off_joint": [],
    "off_joint_count": 0,
}


def _off(u_m, off_joint_m):
    return {
        "ok": False,
        "new_vertices": 1,
        "checked_on_patterned_edges": 1,
        "off_joint": [{"source_polygon": 0, "u_m": u_m, "off_joint_m": off_joint_m}],
        "off_joint_count": 1,
    }


def _spec(half_mm):
    tile = {"P": [1, 1]}
    if half_mm is not None:
        tile["joint_half_mm"] = half_mm
    spec = {"zero_m": 0, "facade_uv": [FINISH], "finishes": {FINISH: tile}}
    assert "facades" not in spec
    return spec


def _report(x, half_mm, *, extra=True):
    src_v = [tuple(p) for p in SRC]
    src_faces = [list(FACE)]
    expected = [FINISH]
    spec = _spec(half_mm)
    out_v = [tuple(p) for p in SRC]
    if extra:
        out_v.append((x, 0.0, 1.0))
    shift = [0, 0, 0]
    snap = copy.deepcopy((src_v, src_faces, expected, spec, out_v, shift))
    report = qa_packages.cut_joint_report(src_v, src_faces, expected, spec, out_v, shift)
    assert (src_v, src_faces, expected, spec, out_v, shift) == snap
    if extra:
        new, missing = qa_packages._new_vertices(src_v, out_v, shift, tol=2e-4)
        assert missing == 0 and len(new) == 1
        assert report["checked_on_patterned_edges"] == 1
    return report


def _frame_u(x):
    """Unrounded frame coordinate. shift is 0; not the production modulo helper."""
    axis, sign, origin = finish_map.joint_origin(SRC, FACE, *finish_map.body_plan_bbox(SRC, 0))
    assert (axis, sign, origin) == (0, 1, 0.0)
    return sign * (Fraction.from_float(x) - Fraction.from_float(origin))


def test_hand_frame():
    lo, hi = finish_map.body_plan_bbox(SRC, 0)
    assert finish_map.joint_origin(SRC, FACE, lo, hi) == (0, 1, 0)


# x, joint_half_mm (None omits the key), exact report. Synthetic widths.
CASES = [
    ("on_125", 0.125, 125, PASS),
    ("wrap_875", 0.875, 125, PASS),
    ("wrap_874", 0.874, 125, _off(0.874, 0.126)),
    ("wrap_876", 0.876, 125, PASS),
    ("override_125_at_0625", 0.0625, 125, PASS),
    ("omitted_at_0625", 0.0625, None, _off(0.0625, 0.0625)),
    ("override_250_at_1875", 0.1875, 250, PASS),
    ("override_125_at_1875", 0.1875, 125, _off(0.1875, 0.1875)),
]


@pytest.mark.parametrize("x,half_mm,want", [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_cut_joint_width(x, half_mm, want):
    assert _report(x, half_mm) == want


@pytest.mark.parametrize(
    "x,want",
    [(0.003, PASS), (0.005, _off(0.005, 0.005))],
    ids=["inside_003", "outside_005"],
)
def test_omitted_equals_explicit_4(x, want):
    omitted = _report(x, None)
    explicit = _report(x, 4)
    assert omitted == explicit == want


def test_adjacent_float_rounds_onto_boundary():
    """Counterexample: both adjacent floats collapse in production.

    _new_vertices rounds the delivered point to 5 decimals before the joint test.
    math.nextafter(0.125, 0) = 0.12499999999999999
        = 9007199254740991/72057594037927936 = 1/8 - 1/72057594037927936
    math.nextafter(0.125, 1) = 0.12500000000000003
        = 4503599627370497/36028797018963968 = 1/8 + 1/36028797018963968
    Both round to 0.125, so the new vertex is [[0.125, 0.0, 1.0]] and the report is the
    on-boundary pass (dist == 0.125 m, comparison is strict >). The card expected the high
    witness to fail: ok False, off_joint_count 1, off_joint exactly
    [{source_polygon: 0, u_m: 0.125, off_joint_m: 0.125}]. Baseline does not. The low
    witness's pass expectation still holds. Unrounded sides are asserted with
    Fraction.from_float against Fraction(1, 8); shift stays 0.
    """
    low = math.nextafter(0.125, 0.0)
    high = math.nextafter(0.125, 1.0)
    assert low == 0.12499999999999999
    assert high == 0.12500000000000003
    assert _frame_u(0.125) == HALF
    assert _frame_u(low) < HALF
    assert _frame_u(high) > HALF
    assert Fraction.from_float(low) == Fraction(9007199254740991, 72057594037927936)
    assert Fraction.from_float(high) == Fraction(4503599627370497, 36028797018963968)
    for witness in (low, high):
        src_v = [tuple(p) for p in SRC]
        out_v = src_v + [(witness, 0.0, 1.0)]
        new, missing = qa_packages._new_vertices(src_v, out_v, [0, 0, 0], tol=2e-4)
        assert missing == 0 and new.tolist() == [[0.125, 0.0, 1.0]]
        assert _report(witness, 125) == PASS


def test_source_only_is_vacuous():
    assert _report(None, 125, extra=False) == VACUOUS
