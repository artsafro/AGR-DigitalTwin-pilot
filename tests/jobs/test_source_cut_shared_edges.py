"""new-case: shared indexed edge is checked on every patterned source polygon in cut_joint_report.

Pattern: new-case (characterization on the current code; GREEN at baseline, not a historical RED).

minimal function-level spec, not an approved building/material allocation; synthetic checker contract, not delivery acceptance.

Two literal coplanar outward -Y quads share the indexed edge z=2 (vertices 2 and 3).
Vertices: 0:(0,0,1) 1:(4,0,1) 2:(4,0,2) 3:(0,0,2) 4:(4,0,3) 5:(0,0,3).
Faces A=[0,1,2,3] (z 1..2), B=[3,2,4,5] (z 2..3). Newell n=(0,-8,0) on both,
so the outward normal is -Y. Hand check of finish_map.joint_origin: plan bbox
lo=(0,0), hi=(4,0); facade u = x - lo_x because n_y < 0, so axis 0, sign +1,
origin 0 (the face's smallest x). The test asserts that triple.

Spec has zero_m 0, facade_uv keys A and B (string values, same form as the
TEC26 texture spec; membership is by key), finishes A P[1,1] and B P[1.5,1],
joint_half_mm 4 (0.004 m). No facades key. Default tolerance 2e-4. Shift
(0,0,0) except the pivot row. Output is the source vertices plus the extra
points. Witnesses sit at least 1 m from the edge endpoints x=0 and x=4, and
0.25 m or 0.5 m from the joint, far from the 4 mm half-width.

u = x. A joint distance is min(x % P, P - x % P) with P = P[0].
  x=1:    A dist 0 (on 1*1), B dist 0.5 (between 0 and 1.5)
  x=3:    A dist 0, B dist 0 (on 2*1.5)
  x=1.25: A dist 0.25, B dist 0.25

Acceptance table (input -> exact report -> one test each):
  source-only
    -> new_vertices 0, checked_on_patterned_edges 0, off_joint_count 0, ok True
  add (1,0,2)
    -> new 1, checked 2, off count 1, ok False,
       off_joint == [{"source_polygon":1,"u_m":1.0,"off_joint_m":0.5}]
  add (3,0,2)
    -> new 1, checked 2, off 0, ok True
  add (1.25,0,2)
    -> new 1, checked 2, off 2, ok False, one entry per polygon
       (source_polygon 0 and 1), u_m 1.25, off_joint_m 0.25
  repeat identical extra-point rows (1,0,2) three times
    -> report identical to the single-row one (unique new vertices)
  remove B only from facade_uv, x=1 witness
    -> new 1, checked 1, off 0, ok True
  reverse face order with expected labels reversed
    -> same semantic entries after remapping source_polygon and sorting;
       checked/off totals unchanged
  permute source vertices and remap both face index lists
    -> same normalized reports
  output minus pivot (10,20,30) with shift (10,20,30)
    -> same normalized reports
  deep snapshots of src_v, src_faces, expected, spec, out_v, shift unchanged
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jobs/TEC26-OKS/scripts"))
import finish_map  # noqa: E402
import qa_packages  # noqa: E402

SRC = [(0, 0, 1), (4, 0, 1), (4, 0, 2), (0, 0, 2), (4, 0, 3), (0, 0, 3)]
FACES = [[0, 1, 2, 3], [3, 2, 4, 5]]
EXPECTED = ["A", "B"]
SPEC = {
    "zero_m": 0,
    "facade_uv": {
        "A": "u' = metres along the facade from the panel field's smaller world coordinate (joints at u' = k * P), v = world z",
        "B": "same frame, P of this finish",
    },
    "finishes": {
        "A": {"P": [1, 1], "joint_half_mm": 4},
        "B": {"P": [1.5, 1], "joint_half_mm": 4},
    },
}
SHIFT0 = (0, 0, 0)
PIVOT = (10, 20, 30)
X1 = (1, 0, 2)
X3 = (3, 0, 2)
X125 = (1.25, 0, 2)

SOURCE_ONLY = {
    "ok": True,
    "new_vertices": 0,
    "checked_on_patterned_edges": 0,
    "off_joint": [],
    "off_joint_count": 0,
}
OFF_X1 = {
    "ok": False,
    "new_vertices": 1,
    "checked_on_patterned_edges": 2,
    "off_joint": [{"source_polygon": 1, "u_m": 1.0, "off_joint_m": 0.5}],
    "off_joint_count": 1,
}
ON_X3 = {
    "ok": True,
    "new_vertices": 1,
    "checked_on_patterned_edges": 2,
    "off_joint": [],
    "off_joint_count": 0,
}
OFF_X125 = {
    "ok": False,
    "new_vertices": 1,
    "checked_on_patterned_edges": 2,
    "off_joint": [
        {"source_polygon": 0, "u_m": 1.25, "off_joint_m": 0.25},
        {"source_polygon": 1, "u_m": 1.25, "off_joint_m": 0.25},
    ],
    "off_joint_count": 2,
}
ONLY_A = {
    "ok": True,
    "new_vertices": 1,
    "checked_on_patterned_edges": 1,
    "off_joint": [],
    "off_joint_count": 0,
}


def _deliver(src, extra, shift):
    return [[p[i] - shift[i] for i in range(3)] for p in list(src) + list(extra)]


def _report(extra, src=SRC, faces=FACES, expected=EXPECTED, spec=SPEC, shift=SHIFT0):
    return qa_packages.cut_joint_report(src, faces, expected, spec, _deliver(src, extra, shift), shift)


def _by_finish(report, expected):
    rows = tuple(sorted(
        (expected[row["source_polygon"]], row["u_m"], row["off_joint_m"])
        for row in report["off_joint"]
    ))
    return {
        "ok": report["ok"],
        "new_vertices": report["new_vertices"],
        "checked_on_patterned_edges": report["checked_on_patterned_edges"],
        "off_joint_count": report["off_joint_count"],
        "off_joint": rows,
    }


def _assert_joint_frame():
    assert "facades" not in SPEC
    lo, hi = finish_map.body_plan_bbox(SRC, SPEC["zero_m"])
    assert lo == [0, 0] and hi == [4, 0]
    for face in FACES:
        assert finish_map.joint_origin(SRC, face, lo, hi) == (0, 1, 0)


def test_source_only():
    _assert_joint_frame()
    assert _report([]) == SOURCE_ONLY


def test_add_x1_off_on_b_only():
    assert _report([X1]) == OFF_X1


def test_add_x3_on_both_joints():
    assert _report([X3]) == ON_X3


def test_add_x125_off_on_both_polygons():
    assert _report([X125]) == OFF_X125


def test_repeated_extra_points_are_unique():
    assert _report([X1, X1, X1]) == _report([X1]) == OFF_X1


def test_remove_b_from_facade_uv():
    spec = copy.deepcopy(SPEC)
    del spec["facade_uv"]["B"]
    assert "facades" not in spec and "B" not in spec["facade_uv"] and "A" in spec["facade_uv"]
    assert _report([X1], spec=spec) == ONLY_A


def test_reverse_face_order_and_vertex_permutation():
    """x=1: B is the only off entry, so reversing faces changes source_polygon 1 -> 0.
    x=1.25: both polygons are off. Normalized finish rows and totals stay put.
    """
    x1_norm = {
        "ok": False,
        "new_vertices": 1,
        "checked_on_patterned_edges": 2,
        "off_joint_count": 1,
        "off_joint": (("B", 1.0, 0.5),),
    }
    x125_norm = {
        "ok": False,
        "new_vertices": 1,
        "checked_on_patterned_edges": 2,
        "off_joint_count": 2,
        "off_joint": (("A", 1.25, 0.25), ("B", 1.25, 0.25)),
    }
    rev_faces = [FACES[1], FACES[0]]
    rev_expected = ["B", "A"]
    order = [1, 3, 5, 0, 2, 4]
    perm_src = [SRC[i] for i in order]
    inv = [order.index(i) for i in range(len(SRC))]
    perm_faces = [[inv[k] for k in face] for face in FACES]
    assert [perm_src[k] for k in perm_faces[0]] == [SRC[k] for k in FACES[0]]
    assert [perm_src[k] for k in perm_faces[1]] == [SRC[k] for k in FACES[1]]

    for extra, norm in (([X1], x1_norm), ([X125], x125_norm)):
        plain = _report(extra)
        rev = _report(extra, faces=rev_faces, expected=rev_expected)
        perm = _report(extra, src=perm_src, faces=perm_faces)
        assert _by_finish(plain, EXPECTED) == norm
        assert _by_finish(rev, rev_expected) == norm
        assert _by_finish(perm, EXPECTED) == norm
        assert plain["checked_on_patterned_edges"] == rev["checked_on_patterned_edges"] == perm["checked_on_patterned_edges"]
        assert plain["off_joint_count"] == rev["off_joint_count"] == perm["off_joint_count"]

    plain_x1 = _report([X1])
    rev_x1 = _report([X1], faces=rev_faces, expected=rev_expected)
    assert plain_x1["off_joint"][0]["source_polygon"] == 1
    assert rev_x1["off_joint"][0]["source_polygon"] == 0
    assert rev_expected[rev_x1["off_joint"][0]["source_polygon"]] == "B"


def test_shift_matches_unshifted_report():
    shifted = _report([X1], shift=PIVOT)
    assert shifted == OFF_X1
    assert _by_finish(shifted, EXPECTED) == _by_finish(_report([X1]), EXPECTED)


def test_inputs_unchanged():
    src_v = [list(map(float, p)) for p in SRC]
    src_faces = copy.deepcopy(FACES)
    expected = ["A", "B"]
    spec = copy.deepcopy(SPEC)
    out_v = [list(map(float, p)) for p in list(SRC) + [X125]]
    shift = [0.0, 0.0, 0.0]
    snap_src_v = copy.deepcopy(src_v)
    snap_src_faces = copy.deepcopy(src_faces)
    snap_expected = copy.deepcopy(expected)
    snap_spec = copy.deepcopy(spec)
    snap_out_v = copy.deepcopy(out_v)
    snap_shift = copy.deepcopy(shift)
    assert qa_packages.cut_joint_report(src_v, src_faces, expected, spec, out_v, shift) == OFF_X125
    assert src_v == snap_src_v
    assert src_faces == snap_src_faces
    assert expected == snap_expected
    assert spec == snap_spec
    assert out_v == snap_out_v
    assert shift == snap_shift
