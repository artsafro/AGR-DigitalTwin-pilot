"""new-case: shared facade-field origin across split source faces.

Synthetic characterization of finish_map.field_frames and qa_packages.cut_joint_report
when spec.facades is nonempty. Two coplanar outward -Y rectangles (corner order
bottom-left, bottom-right, top-right, top-left as seen from -Y) span x=10..11.25 and
x=11.25..14 at y=0, z=1..3. The spec field is 4 m with 4 ribs, so the patterned finish
period is P=[1, 1] and joint_half_mm is 4. zero_m is 0. Every expected number below is
a hand-derived literal (field origin 10). No assets.

1. Both faces together -> frame (axis 0, sign +1, origin 10) on each face;
   field_lo 10, field_hi 14, pitch 1, joints_world [11, 12, 13].
2. Delivered vertices equal the source -> new 0, checked 0, off 0, ok True.
3. Extra bottom-edge point (12, 0, 1) on the second face -> new 1, checked 1, off 0,
   ok True. A per-face origin at 11.25 would put u at 0.75 and reject it.
4. Extra point (12.25, 0, 1) -> new 1, checked 1, off 1, ok False, source_polygon 1,
   u_m 2.25, off_joint_m 0.25. A per-face origin at 11.25 would put u at 1 and accept it.
5. field_m 4.1 -> ValueError mentioning the measured panel field.
6. outline_z_m [1, 3] leaves the result unchanged; [1, 3.1] -> ValueError mentioning
   panel field z.
7. Reordering the faces with their finishes remaps diagnostic indices; a genuine
   permutation of the source vertices remaps both faces; subtracting a literal pivot
   from the output and passing that pivot as shift keeps the geometrical results.
8. Deep-copied inputs are unchanged after the calls.
"""
import copy
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "jobs" / "TEC26-OKS" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import finish_map  # noqa: E402
import qa_packages  # noqa: E402

FINISH = "Panel"
# Shared split edge at x=11.25. Winding keeps the outward normal on -Y.
VERTS = [
    [10, 0, 1],
    [11.25, 0, 1],
    [11.25, 0, 3],
    [10, 0, 3],
    [14, 0, 1],
    [14, 0, 3],
]
FACES = [[0, 1, 2, 3], [1, 4, 5, 2]]
EXPECTED = [FINISH, FINISH]
LO = (10, 0)
HI = (14, 0)
SHIFT0 = [0, 0, 0]
FRAME = (0, 1, 10)
ON_JOINT = [12, 0, 1]
OFF_JOINT = [12.25, 0, 1]
PIVOT = [100, -20, 7]
SPEC = {
    "zero_m": 0,
    "facade_uv": {FINISH: {}},
    "facades": {
        "south": {"normal": "-y", "finish": FINISH, "ribs": 4, "field_m": 4},
    },
    "finishes": {
        FINISH: {"P": [1, 1], "joint_half_mm": 4},
    },
}


def _with_outline(band):
    spec = copy.deepcopy(SPEC)
    spec["finishes"][FINISH]["outline_z_m"] = list(band)
    return spec


def _frames(vertices, faces, expected, spec):
    return finish_map.field_frames(vertices, faces, expected, spec, LO, HI)


def _cut(vertices, faces, expected, spec, out, shift):
    return qa_packages.cut_joint_report(vertices, faces, expected, spec, out, shift)


def _assert_cut(report, new, checked, off, ok):
    assert report["new_vertices"] == new
    assert report["checked_on_patterned_edges"] == checked
    assert report["off_joint_count"] == off
    assert report["ok"] is ok


def test_both_split_faces_share_field_origin_ten():
    assert finish_map.facade_key(VERTS, FACES[0]) == "-y"
    assert finish_map.facade_key(VERTS, FACES[1]) == "-y"
    frames, report = _frames(VERTS, FACES, EXPECTED, SPEC)
    assert frames == [FRAME, FRAME]
    south = report["south"]
    assert south["field_lo"] == 10
    assert south["field_hi"] == 14
    assert south["pitch_m"] == 1
    assert south["joints_world"] == [11, 12, 13]


def test_unchanged_source_vertices_are_not_new_cuts():
    report = _cut(VERTS, FACES, EXPECTED, SPEC, VERTS, SHIFT0)
    _assert_cut(report, 0, 0, 0, True)
    assert report["off_joint"] == []


def test_second_face_joint_at_twelve_is_on_the_shared_field():
    report = _cut(VERTS, FACES, EXPECTED, SPEC, VERTS + [ON_JOINT], SHIFT0)
    _assert_cut(report, 1, 1, 0, True)
    assert report["off_joint"] == []


def test_second_face_point_at_twelve_point_two_five_is_off_joint():
    report = _cut(VERTS, FACES, EXPECTED, SPEC, VERTS + [OFF_JOINT], SHIFT0)
    _assert_cut(report, 1, 1, 1, False)
    assert report["off_joint"] == [
        {"source_polygon": 1, "u_m": 2.25, "off_joint_m": 0.25}
    ]


def test_wrong_field_m_names_measured_panel_field():
    spec = copy.deepcopy(SPEC)
    spec["facades"]["south"]["field_m"] = 4.1
    with pytest.raises(ValueError, match="measured panel field"):
        _frames(VERTS, FACES, EXPECTED, spec)


def test_outline_z_accepts_field_band_and_rejects_a_taller_band():
    base_frames, base_report = _frames(VERTS, FACES, EXPECTED, SPEC)
    frames, report = _frames(VERTS, FACES, EXPECTED, _with_outline([1, 3]))
    assert frames == base_frames == [FRAME, FRAME]
    assert report == base_report
    assert report["south"]["joints_world"] == [11, 12, 13]
    with pytest.raises(ValueError, match="panel field z"):
        _frames(VERTS, FACES, EXPECTED, _with_outline([1, 3.1]))


def test_reorder_permutation_and_pivot_shift_keep_geometry():
    wide_first = [FACES[1], FACES[0]]
    wide_expected = [EXPECTED[1], EXPECTED[0]]
    frames, report = _frames(VERTS, wide_first, wide_expected, SPEC)
    assert frames == [FRAME, FRAME]
    assert report["south"]["field_lo"] == 10
    assert report["south"]["field_hi"] == 14
    assert report["south"]["pitch_m"] == 1
    assert report["south"]["joints_world"] == [11, 12, 13]
    reordered_off = _cut(VERTS, wide_first, wide_expected, SPEC, VERTS + [OFF_JOINT], SHIFT0)
    _assert_cut(reordered_off, 1, 1, 1, False)
    assert reordered_off["off_joint"] == [
        {"source_polygon": 0, "u_m": 2.25, "off_joint_m": 0.25}
    ]
    reordered_on = _cut(VERTS, wide_first, wide_expected, SPEC, VERTS + [ON_JOINT], SHIFT0)
    _assert_cut(reordered_on, 1, 1, 0, True)

    # new[i] = VERTS[order[i]]; both face index lists change, corner order does not.
    order = (2, 5, 0, 4, 1, 3)
    permuted = [
        [11.25, 0, 3],
        [14, 0, 3],
        [10, 0, 1],
        [14, 0, 1],
        [11.25, 0, 1],
        [10, 0, 3],
    ]
    permuted_faces = [[2, 4, 0, 5], [4, 3, 1, 0]]
    assert [VERTS[i] for i in order] == permuted
    assert permuted != VERTS
    assert permuted_faces[0] != FACES[0] and permuted_faces[1] != FACES[1]
    frames, report = _frames(permuted, permuted_faces, EXPECTED, SPEC)
    assert frames == [FRAME, FRAME]
    assert report["south"]["joints_world"] == [11, 12, 13]
    permuted_off = _cut(permuted, permuted_faces, EXPECTED, SPEC, permuted + [OFF_JOINT], SHIFT0)
    _assert_cut(permuted_off, 1, 1, 1, False)
    assert permuted_off["off_joint"] == [
        {"source_polygon": 1, "u_m": 2.25, "off_joint_m": 0.25}
    ]

    local_off = [
        [-90, 20, -6],
        [-88.75, 20, -6],
        [-88.75, 20, -4],
        [-90, 20, -4],
        [-86, 20, -6],
        [-86, 20, -4],
        [-87.75, 20, -6],
    ]
    local_on = local_off[:6] + [[-88, 20, -6]]
    local_source = local_off[:6]
    world_off = _cut(VERTS, FACES, EXPECTED, SPEC, VERTS + [OFF_JOINT], SHIFT0)
    world_on = _cut(VERTS, FACES, EXPECTED, SPEC, VERTS + [ON_JOINT], SHIFT0)
    assert _cut(VERTS, FACES, EXPECTED, SPEC, local_off, PIVOT) == world_off
    assert _cut(VERTS, FACES, EXPECTED, SPEC, local_on, PIVOT) == world_on
    assert _cut(VERTS, FACES, EXPECTED, SPEC, local_source, PIVOT) == _cut(
        VERTS, FACES, EXPECTED, SPEC, VERTS, SHIFT0
    )
    _assert_cut(world_off, 1, 1, 1, False)
    assert world_off["off_joint"] == [
        {"source_polygon": 1, "u_m": 2.25, "off_joint_m": 0.25}
    ]
    _assert_cut(world_on, 1, 1, 0, True)


def test_calls_leave_deep_copied_inputs_unchanged():
    vertices = copy.deepcopy(VERTS)
    faces = copy.deepcopy(FACES)
    expected = copy.deepcopy(EXPECTED)
    spec = _with_outline([1, 3])
    out = copy.deepcopy(vertices)
    out.append([12.25, 0, 1])
    shift = [100, -20, 7]
    local = [
        [-90, 20, -6],
        [-88.75, 20, -6],
        [-88.75, 20, -4],
        [-90, 20, -4],
        [-86, 20, -6],
        [-86, 20, -4],
        [-87.75, 20, -6],
    ]
    before = copy.deepcopy((vertices, faces, expected, spec, out, local, shift, LO, HI))
    _frames(vertices, faces, expected, spec)
    _cut(vertices, faces, expected, spec, out, SHIFT0)
    _cut(vertices, faces, expected, spec, local, shift)
    assert (vertices, faces, expected, spec, out, local, shift, LO, HI) == before
