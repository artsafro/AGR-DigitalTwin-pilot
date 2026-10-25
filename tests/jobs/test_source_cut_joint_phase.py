"""new-case: independent periodic phase + non-patterned-edge controls for cut_joint_report.

Baseline is GREEN characterization of the legacy joint_origin path (no spec facades).
The fixture is a literal vertical rectangle, width 4 m, z = 1..3, on the plan-bbox
side y = 0, plus a second vertical rectangle on y = 10, x = 20..24, z = 1..3.
zero_m = 0, so the body plan bbox is lo = (0, 0), hi = (24, 10).

Hand frame for the patterned face (winding (0,0,1)-(4,0,1)-(4,0,3)-(0,0,3), Newell
normal -Y). facade_uv uses u = x - lo_x because ny < 0. x span is 4 m and matches
that u span, and the larger x has the larger u, so axis = 0, sign = +1. joint_origin
is the face's minimum x, which is 0, not hi_x. Therefore u = x. P = 1 m.
joint_half_mm = 4, so a point is on a joint when its wrapped distance is <= 0.004 m.
Wrapped distance is min(r, 1 - r) with r = u % 1.

    x      u      r      wrapped   within 4 mm
    2      2      0      0         yes
    1.003  1.003  0.003  0.003     yes
    1.997  1.997  0.997  0.003     yes (the 0.997 remainder wraps)
    1.01   1.01   0.01   0.01      no; recorded u_m 1.01, off_joint_m 0.01

The plain face is finish "Plain", absent from facade_uv. Its own frame (same
reading: axis 0, sign +1, origin 20) is used only to predict the filter mutant.
A new point at x = 21.01 has u = 1.01 on that face.

Geometry eligibility is a separate report, geometry_report. checked == 0 does not
mean the new point is geometrically valid.

Acceptance table (new point; report fields ok / new / checked / off; test)
  none                  -> True / 0 / 0 / 0           test_no_new_vertices_is_vacuous
  (2, 0, 1)             -> True / 1 / 1 / 0           test_integer_joint_on_bottom_edge
  (1.003, 0, 1)         -> True / 1 / 1 / 0           test_phase_0_003_inside_half_joint
  (1.997, 0, 1)         -> True / 1 / 1 / 0           test_phase_0_997_wraps_inside_half_joint
  (1.01, 0, 1)          -> False / 1 / 1 / 1, entry   test_phase_0_010_is_off_joint
                           {source_polygon 0, u_m 1.01, off_joint_m 0.01}
  (21.01, 10, 1) plain  -> True / 1 / 0 / 0           test_non_patterned_edge_is_not_checked
  every case above, pivot shift (3,-5,2) restored, source vertices permuted
  [3,7,1,5,0,4,2,6] with src_faces indices remapped, out_v reversed: reports equal the
  canonical run, inputs unchanged   test_shift_and_vertex_order_leave_results_and_inputs
  mutant: no wrap `dist = r`: (1.997,0,1) -> False / 1 / 1 / 1, polygon 0, u 1.997,
                           distance 0.997                test_mutant_without_period_wrap_is_rejected
  mutant: no patterned filter: (21.01,10,1) -> False / 1 / 1 / 1, polygon 1, u 1.01,
                           distance 0.01          test_mutant_without_pattern_filter_is_rejected
"""
import copy
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "jobs" / "TEC26-OKS" / "scripts"
QA_PATH = SCRIPTS / "qa_packages.py"
sys.path.insert(0, str(SCRIPTS))
import qa_packages  # noqa: E402

PANEL = "Panel"
PLAIN = "Plain"
PERIOD = 1.0
HALF_M = 4 / 1000
ON_EDGE_TOL = 2e-4
T_OPEN = 1e-6
SHIFT = [3.0, -5.0, 2.0]
# Patterned quad, then the separated plain quad. Eight distinct corners.
SRC_V = [
    [0.0, 0.0, 1.0],
    [4.0, 0.0, 1.0],
    [4.0, 0.0, 3.0],
    [0.0, 0.0, 3.0],
    [20.0, 10.0, 1.0],
    [24.0, 10.0, 1.0],
    [24.0, 10.0, 3.0],
    [20.0, 10.0, 3.0],
]
SRC_FACES = [[0, 1, 2, 3], [4, 5, 6, 7]]
EXPECTED = [PANEL, PLAIN]
WRAP_OLD = 'dist = min(r, t["P"][0] - r)'
WRAP_NEW = "dist = r"
FILTER_OLD = "if expected[pi] not in pat or not any(_on_edge(q, sv[f[k]], sv[f[(k + 1) % len(f)]], tol)"
FILTER_NEW = "if not any(_on_edge(q, sv[f[k]], sv[f[(k + 1) % len(f)]], tol)"


def make_spec():
    spec = {
        "zero_m": 0,
        "facade_uv": {PANEL: "metres along the facade from the face origin"},
        "finishes": {
            PANEL: {"P": [1, 1], "joint_half_mm": 4},
            PLAIN: {"P": [1, 1], "joint_half_mm": 4},
        },
    }
    assert "facades" not in spec
    assert set(spec["facade_uv"]) == {PANEL}
    assert spec["finishes"][PANEL]["P"] == [1, 1]
    assert spec["finishes"][PANEL]["joint_half_mm"] == 4
    assert HALF_M == 0.004
    return spec


def assert_clear_of_ends(x, x0, x1):
    """Point is deep on the open segment: far from vertices and from both tolerances."""
    t = (x - x0) / (x1 - x0)
    clearance = min(x - x0, x1 - x)
    assert 0.2 < t < 0.8
    assert clearance > 0.5
    assert clearance > ON_EDGE_TOL * 1000
    assert min(t, 1.0 - t) > T_OPEN * 1000


def call_report(report_fn, extra, shift, permute):
    src_v = copy.deepcopy(SRC_V)
    src_faces = copy.deepcopy(SRC_FACES)
    if permute:
        # Jointly permute source vertices and remap src_faces indices.
        perm = [3, 7, 1, 5, 0, 4, 2, 6]
        assert sorted(perm) == list(range(len(SRC_V))) and perm != sorted(perm)
        inv = {old: new for new, old in enumerate(perm)}
        src_v = [list(SRC_V[old]) for old in perm]
        src_faces = [[inv[i] for i in f] for f in SRC_FACES]
        assert src_faces != SRC_FACES
        for f, g in zip(SRC_FACES, src_faces):
            assert [SRC_V[i] for i in f] == [src_v[i] for i in g]
    expected = copy.deepcopy(EXPECTED)
    spec = make_spec()
    shift_v = list(shift)
    world = [list(p) for p in src_v]
    if extra is not None:
        point = [float(extra[0]), float(extra[1]), float(extra[2])]
        assert point not in world
        world.append(point)
    order = list(range(len(world)))
    indices = list(order)
    if permute:
        order = list(reversed(order))
        indices = [indices[i] for i in order]
        assert indices == order
        assert sorted(order) == list(range(len(world)))
    out_v = [[world[i][k] - shift_v[k] for k in range(3)] for i in order]
    for i, xyz in enumerate(world):
        restored = [out_v[order.index(i)][k] + shift_v[k] for k in range(3)]
        assert restored == xyz
    snap = {
        "src_v": copy.deepcopy(src_v),
        "src_faces": copy.deepcopy(src_faces),
        "expected": copy.deepcopy(expected),
        "spec": copy.deepcopy(spec),
        "out_v": copy.deepcopy(out_v),
        "shift": copy.deepcopy(shift_v),
    }
    result = report_fn(src_v, src_faces, expected, spec, out_v, shift_v)
    assert src_v == snap["src_v"]
    assert src_faces == snap["src_faces"]
    assert expected == snap["expected"]
    assert spec == snap["spec"]
    assert out_v == snap["out_v"]
    assert shift_v == snap["shift"]
    return result


def delivered(report_fn, extra):
    """Acceptance calls use a non-zero pivot shift and a reversed out_v order."""
    return call_report(report_fn, extra, SHIFT, permute=True)


def assert_on_joint(report_fn, x, y, z):
    got = delivered(report_fn, (x, y, z))
    assert got["ok"] is True
    assert got["new_vertices"] == 1
    assert got["checked_on_patterned_edges"] == 1
    assert got["off_joint_count"] == 0
    assert got["off_joint"] == []
    return got


def assert_period_wrap(report_fn):
    """Phase 0.997 m on the patterned bottom edge. Wrapped distance is 0.003 m."""
    assert_clear_of_ends(1.997, 0.0, 4.0)
    assert 0.997 > HALF_M
    wrapped = min(0.997, PERIOD - 0.997)
    assert 0.002 < wrapped < 0.0031
    assert wrapped < HALF_M
    return assert_on_joint(report_fn, 1.997, 0.0, 1.0)


def assert_plain_not_checked(report_fn):
    """New point only on the plain bottom edge. The joint report does not check it.

    geometry_report is the separate check for whether a new point lies on a source
    edge. This assertion does not claim the unchecked point is geometrically valid.
    """
    assert_clear_of_ends(21.01, 20.0, 24.0)
    assert abs(10.0 - 0.0) == 10.0
    got = delivered(report_fn, (21.01, 10.0, 1.0))
    assert got["new_vertices"] == 1
    assert got["checked_on_patterned_edges"] == 0
    assert got["ok"] is True
    assert got["off_joint_count"] == 0
    assert got["off_joint"] == []
    return got


def replace_once(source, old, new):
    assert source.count(old) == 1
    assert source.count(new) == 0
    mutated = source.replace(old, new, 1)
    assert mutated.count(old) == 0
    assert mutated.count(new) == 1
    assert mutated != source
    return mutated


def module_from_source(source, name):
    module = types.ModuleType(name)
    module.__file__ = str(QA_PATH)
    exec(compile(source, str(QA_PATH), "exec"), module.__dict__)
    return module


def test_no_new_vertices_is_vacuous():
    got = delivered(qa_packages.cut_joint_report, None)
    assert got == {
        "ok": True,
        "new_vertices": 0,
        "checked_on_patterned_edges": 0,
        "off_joint": [],
        "off_joint_count": 0,
    }


def test_integer_joint_on_bottom_edge():
    assert_clear_of_ends(2.0, 0.0, 4.0)
    assert 2.0 % PERIOD == 0.0
    assert_on_joint(qa_packages.cut_joint_report, 2.0, 0.0, 1.0)


def test_phase_0_003_inside_half_joint():
    assert_clear_of_ends(1.003, 0.0, 4.0)
    assert 0.003 < HALF_M
    assert abs(0.003 - HALF_M) == pytest.approx(0.001)
    assert_on_joint(qa_packages.cut_joint_report, 1.003, 0.0, 1.0)


def test_phase_0_997_wraps_inside_half_joint():
    assert_period_wrap(qa_packages.cut_joint_report)


def test_phase_0_010_is_off_joint():
    assert_clear_of_ends(1.01, 0.0, 4.0)
    assert 0.01 > HALF_M
    assert round(1.01, 4) == 1.01
    assert round(0.01, 4) == 0.01
    got = delivered(qa_packages.cut_joint_report, (1.01, 0.0, 1.0))
    assert got["ok"] is False
    assert got["new_vertices"] == 1
    assert got["checked_on_patterned_edges"] == 1
    assert got["off_joint_count"] == 1
    assert got["off_joint"] == [{"source_polygon": 0, "u_m": 1.01, "off_joint_m": 0.01}]


def test_non_patterned_edge_is_not_checked():
    assert_plain_not_checked(qa_packages.cut_joint_report)


def test_shift_and_vertex_order_leave_results_and_inputs():
    cases = [None, (2.0, 0.0, 1.0), (1.003, 0.0, 1.0), (1.997, 0.0, 1.0), (1.01, 0.0, 1.0), (21.01, 10.0, 1.0)]
    for extra in cases:
        canonical = call_report(qa_packages.cut_joint_report, extra, [0.0, 0.0, 0.0], permute=False)
        transformed = call_report(qa_packages.cut_joint_report, extra, SHIFT, permute=True)
        assert transformed == canonical


def test_mutant_without_period_wrap_is_rejected():
    """Dropping min(r, P-r) leaves the 0.997 remainder, which is outside the half-joint."""
    source = QA_PATH.read_text(encoding="utf-8")
    mutant = module_from_source(replace_once(source, WRAP_OLD, WRAP_NEW), "cut_joint_wrap_mutant")
    with pytest.raises(AssertionError):
        assert_period_wrap(mutant.cut_joint_report)
    got = delivered(mutant.cut_joint_report, (1.997, 0.0, 1.0))
    assert got["ok"] is False
    assert got["new_vertices"] == 1
    assert got["checked_on_patterned_edges"] == 1
    assert got["off_joint_count"] == 1
    assert got["off_joint"] == [{"source_polygon": 0, "u_m": 1.997, "off_joint_m": 0.997}]
    assert_period_wrap(qa_packages.cut_joint_report)


def test_mutant_without_pattern_filter_is_rejected():
    """Checking every face sends the plain-edge point through the joint test."""
    source = QA_PATH.read_text(encoding="utf-8")
    mutant = module_from_source(replace_once(source, FILTER_OLD, FILTER_NEW), "cut_joint_filter_mutant")
    with pytest.raises(AssertionError):
        assert_plain_not_checked(mutant.cut_joint_report)
    got = delivered(mutant.cut_joint_report, (21.01, 10.0, 1.0))
    assert got["new_vertices"] == 1
    assert got["checked_on_patterned_edges"] == 1
    assert got["ok"] is False
    assert got["off_joint_count"] == 1
    assert got["off_joint"] == [{"source_polygon": 1, "u_m": 1.01, "off_joint_m": 0.01}]
    assert_plain_not_checked(qa_packages.cut_joint_report)
