"""#2097: checks ported from the Codex UCX skill pack (scripts/check c3, c12, v5extra) and the two simplification
passes of oks-collision-builder SKILL.md as an OBSERVE report (`agr ucx ... --simplify-report`).

Every test was written before its code (RED: module missing / wrong class), then made green.

Pattern: n/a | new-case: tests of the #2097 simplify report and the ported Codex checks.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from dt_ai.geometry import ucx_simplify as us
from twinqa.geometry import ucx_seams as sm

BOX_TRIS = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return [list(map(float, p)) for p in v], [list(t) for t in BOX_TRIS]


def hexa(v):
    """Hexahedron with the box vertex order (convex if the input is)."""
    return [list(map(float, p)) for p in v], [list(t) for t in BOX_TRIS]


def body(name, mesh):
    return {"name": name, "verts": mesh[0], "tris": mesh[1]}


# ---- ported c3: seam gap over the whole facing face, not the pair minimum -------------------------------------
def test_seam_uniform_gap_in_band_is_ok():
    a, b = box((0, 0, 0), (1, 1, 1)), box((1.005, 0, 0), (2, 1, 1))
    rows = sm.seam_face_gaps([body("A", a), body("B", b)])
    assert len(rows) == 1
    r = rows[0]
    assert r["class"] == "ok"
    assert r["gap_min_m"] == pytest.approx(0.005, abs=1e-6) and r["gap_max_m"] == pytest.approx(0.005, abs=1e-6)
    assert r["overlap_area_m2"] == pytest.approx(1.0, rel=1e-6)


def test_seam_wedge_opens_beyond_band_although_minimum_is_in_band():
    a = box((0, 0, 0), (1, 1, 1))
    # B's facing face goes from 5 mm (y=0) to 25 mm (y=1): pair minimum 5 mm passes D098, the seam does not
    b = hexa([(1.005, 0, 0), (2, 0, 0), (2, 1, 0), (1.025, 1, 0), (1.005, 0, 1), (2, 0, 1), (2, 1, 1), (1.025, 1, 1)])
    r = sm.seam_face_gaps([body("A", a), body("B", b)])[0]
    assert r["gap_min_m"] == pytest.approx(0.005, abs=1e-5)
    assert r["gap_max_m"] == pytest.approx(0.025, abs=1e-4)
    assert r["class"] == "wedge"


def test_seam_wide_slot_and_tight_seam():
    a = box((0, 0, 0), (1, 1, 1))
    slot = sm.seam_face_gaps([body("A", a), body("B", box((1.05, 0, 0), (2, 1, 1)))])[0]
    assert slot["class"] == "slot" and slot["gap_min_m"] == pytest.approx(0.05, abs=1e-6)
    tight = sm.seam_face_gaps([body("A", a), body("B", box((1.001, 0, 0), (2, 1, 1)))])[0]
    assert tight["class"] == "tight"


def test_seam_ignores_faces_without_overlap_and_far_pairs():
    a = box((0, 0, 0), (1, 1, 1))
    assert sm.seam_face_gaps([body("A", a), body("B", box((1.005, 3, 0), (2, 4, 1)))]) == []
    assert sm.seam_face_gaps([body("A", a), body("B", box((1.5, 0, 0), (2, 1, 1)))]) == []  # beyond reach 0.30 m


# ---- ported c12: winding consistency and outward normals -------------------------------------------------------
def test_winding_good_box():
    v, t = box((0, 0, 0), (1, 1, 1))
    r = sm.winding_report(v, t)
    assert r == {"consistent": True, "outward": True, "signed_volume_m3": pytest.approx(1.0)}


def test_winding_one_flipped_triangle_is_inconsistent():
    v, t = box((0, 0, 0), (1, 1, 1))
    t[3] = t[3][::-1]
    assert sm.winding_report(v, t)["consistent"] is False


def test_winding_inward_box():
    v, t = box((0, 0, 0), (1, 1, 1))
    r = sm.winding_report(v, [tri[::-1] for tri in t])
    assert r["consistent"] is True and r["outward"] is False


# ---- ported v5extra (7): short edges and sliver triangles ------------------------------------------------------
def test_sliver_box_is_clean():
    v, t = box((0, 0, 0), (1, 1, 1))
    r = sm.sliver_report(v, t)
    assert r["flag"] is False and r["min_edge_m"] == pytest.approx(1.0)


def test_sliver_wedge_with_short_edge_is_flagged():
    # hexahedron with a 4 mm edge at one corner: convex and closed, but carries a micro-face
    v, t = hexa([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 0.004, 1)])
    r = sm.sliver_report(v, t)
    assert r["flag"] is True and r["min_edge_m"] < 0.01


# ---- simplification pass A: empty and duplicate blocks ---------------------------------------------------------
def _plane(x0, y0, x1, y1, z=0.0):
    v = np.array([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], float)
    return v, np.array([(0, 1, 2), (0, 2, 3)])


def test_pass_a_empty_block_is_a_delete_candidate():
    mv, mt = _plane(0, 0, 10, 10)
    bodies = [body("UCX_slab", box((0, 0, -0.5), (10, 10, 0))), body("UCX_air", box((2, 2, 5), (3, 3, 6)))]
    rep = us.simplify_report(mv, mt, bodies)
    rows = {r["name"]: r for r in rep["bodies"]}
    assert rows["UCX_air"]["decision"] == "delete" and rows["UCX_air"]["covered_m2"] == 0
    assert rows["UCX_slab"]["decision"] == "keep"
    assert rows["UCX_slab"]["covered_m2"] == pytest.approx(100.0, rel=1e-6)
    assert rep["lists"]["delete"] == ["UCX_air"]


def test_pass_a_uses_full_triangles_not_vertices_or_centres():
    mv = np.array([(0, 0, 0), (10, 0, 0), (0, 10, 0)], float)
    mt = np.array([(0, 1, 2)])
    # the box covers a strip at the middle of the long edge: no vertex and no centroid inside it
    rep = us.simplify_report(mv, mt, [body("UCX_strip", box((4, -0.5, -0.5), (6, 0.5, 0.5)))], margin_m=0.0)
    r = rep["bodies"][0]
    assert r["covered_m2"] == pytest.approx(1.0, rel=1e-6)  # x in [4, 6] x y in [0, 0.5] inside the triangle
    assert r["decision"] != "delete"


def test_pass_a_interchangeable_duplicates_are_not_deleted_together():
    mv = np.array([(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], float)  # a wall face at x = 0
    mt = np.array([(0, 1, 2), (0, 2, 3)])
    a = body("UCX_a", box((-1, 0, 0), (-0.002, 1, 1)))
    b = body("UCX_b", box((0.002, 0, 0), (1, 1, 1)))
    rep = us.simplify_report(mv, mt, [a, b], margin_m=0.01)
    rows = {r["name"]: r for r in rep["bodies"]}
    assert rows["UCX_a"]["unique_m2"] == 0 and rows["UCX_b"]["unique_m2"] == 0
    decisions = sorted(r["decision"] for r in rows.values())
    assert decisions == ["delete", "keep"]
    kept = next(r for r in rows.values() if r["decision"] == "keep")
    assert "unique once" in kept["reason"]


# ---- simplification pass B: useful but over-split blocks -------------------------------------------------------
def test_pass_b_two_boxes_forming_one_box_are_a_merge_candidate():
    mv, mt = _plane(0, 0, 2, 1, z=1.0)
    bodies = [body("UCX_1", box((0, 0, 0), (1, 1, 1))), body("UCX_2", box((1.004, 0, 0), (2, 1, 1)))]
    rep = us.simplify_report(mv, mt, bodies)
    merges = rep["lists"]["absorb_rebuild"]
    assert any(m["kind"] == "merge" and {m["name"], m["into"]} == {"UCX_1", "UCX_2"} for m in merges)
    m = next(m for m in merges if m["kind"] == "merge")
    assert m["added_air_m3"] == pytest.approx(0.004, abs=1e-4) and m["triangles_saved"] == 12


def _belt_case():
    # wall 10 m wide, 10 m high; a 0.2 m belt at 5-5.5 m stands out of the facade y = 0
    wall = box((0, 0, 0), (10, 1, 10))
    belt = box((0, -0.2, 5), (10, -0.004, 5.5))
    mv = np.array([(0, -0.2, 5), (10, -0.2, 5), (10, -0.2, 5.5), (0, -0.2, 5.5),  # belt front
                   (0, 0, 0), (10, 0, 0), (10, 0, 10), (0, 0, 10)], float)  # facade
    mt = np.array([(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)])
    return mv, mt, [body("UCX_wall", wall), body("UCX_belt", belt)]


def test_pass_b_thin_belt_is_absorbed_by_moving_the_main_plane():
    mv, mt, bodies = _belt_case()
    rep = us.simplify_report(mv, mt, bodies, absorb_m=0.30)
    belt = next(r for r in rep["bodies"] if r["name"] == "UCX_belt")
    assert belt["unique_m2"] > 4.9  # deletion would lose coverage ...
    assert belt["decision"] == "absorb_rebuild"  # ... but the block need not be separate
    cand = next(c for c in rep["lists"]["absorb_rebuild"] if c["name"] == "UCX_belt")
    assert cand["kind"] == "plane_shift" and cand["into"] == "UCX_wall"
    assert cand["shift_m"] == pytest.approx(0.2, abs=1e-6) and cand["moved_face_area_m2"] == pytest.approx(100.0)


def test_pass_b_shift_beyond_tolerance_keeps_the_belt_with_reason():
    mv, mt, bodies = _belt_case()
    rep = us.simplify_report(mv, mt, bodies, absorb_m=0.10)
    belt = next(r for r in rep["bodies"] if r["name"] == "UCX_belt")
    assert belt["decision"] == "keep" and "tolerance" in belt["reason"]


def _rot(mesh, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c * x - s * y + 50.0, s * x + c * y + 20.0, z] for x, y, z in mesh[0]], mesh[1]


def test_merge_hull_is_exact_on_rotated_boxes():
    # regression: real case 03 (facade frame 31 deg) gave negative "added air" (-1 046 m3) with the incremental
    # hull of the Max core; the merge hull must be >= both bodies and add only the seam slab here
    b1, b2 = _rot(box((0, 0, 0), (4, 3, 10)), 31), _rot(box((4.004, 0, 0), (9, 3, 10)), 31)
    tris, vol = us._hull_triangles_volume(np.vstack([b1[0], b2[0]]))
    assert tris == 12 and vol == pytest.approx(9 * 3 * 10, rel=1e-9)
    mv = np.array(_rot(([(0, 0, 10), (9, 0, 10), (9, 3, 10), (0, 3, 10)], None), 31)[0])
    rep = us.simplify_report(mv, np.array([(0, 1, 2), (0, 2, 3)]), [body("UCX_1", b1), body("UCX_2", b2)])
    m = next(a for a in rep["lists"]["absorb_rebuild"] if a["kind"] == "merge")
    assert m["added_air_m3"] == pytest.approx(0.004 * 3 * 10, rel=1e-3)


def test_merge_hull_is_never_smaller_than_its_bodies_with_float32_noise():
    # regression: real case 03 pair 015/004 gave a hull 80.5 m3 < 84.5 m3 of the two bodies when near-coplanar
    # float32 facets were merged by a loose tolerance before measuring their area
    b1 = _rot(box((0, 0, 0), (4, 3, 10)), 31)
    b2 = _rot(box((4.004, 0.00003, 0), (9, 3.00004, 10.00005)), 31)
    pts = np.vstack([b1[0], b2[0]]).astype(np.float32).astype(float)
    v1 = us._volume(np.array(b1[0]), np.array(b1[1]))
    v2 = us._volume(np.array(b2[0]), np.array(b2[1]))
    _, vol = us._hull_triangles_volume(pts)
    assert vol >= v1 + v2 - 1e-6


def test_open_seam_reports_source_surface_showing_through():
    # two blocks 5 cm apart; a source wall face runs through the slot, then a third block fills the slot
    a, b = box((0, 0, 0), (1, 1, 1)), box((1.05, 0, 0), (2, 1, 1))
    mv = np.array([(1.025, 0, 0), (1.025, 1, 0), (1.025, 1, 1), (1.025, 0, 1),
                   (0, 0, 1), (2, 0, 1), (2, 1, 1), (0, 1, 1)], float)  # wall in the slot + roof over both
    mt = np.array([(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)])
    rep = us.simplify_report(mv, mt, [body("UCX_a", a), body("UCX_b", b)])
    seams = rep["ported_checks"]["seams"]
    # 1 m2 wall in the slot + the 0.048 m2 strip of roof spanning the open slot (both show through)
    assert seams["open_with_model"] == 1 and seams["open_with_model_m2"] == pytest.approx(1.048, rel=1e-3)
    filler = body("UCX_f", box((1.004, 0, 0), (1.046, 1, 1)))
    rep = us.simplify_report(mv, mt, [body("UCX_a", a), body("UCX_b", b), filler])
    assert rep["ported_checks"]["seams"]["open_with_model"] == 0


def test_plane_shift_never_chains_through_an_absorbing_body():
    # belt in front of a plate in front of the wall: the plate absorbs the belt, so it is not itself absorbed
    wall = box((0, 0, 0), (10, 1, 10))
    plate = box((0, -0.104, 4), (10, -0.004, 6))
    belt = box((0, -0.2, 5), (10, -0.108, 5.5))
    mv = np.array([(0, -0.2, 5), (10, -0.2, 5), (10, -0.2, 5.5), (0, -0.2, 5.5),
                   (0, -0.104, 4), (10, -0.104, 4), (10, -0.104, 6), (0, -0.104, 6),
                   (0, 0, 0), (10, 0, 0), (10, 0, 10), (0, 0, 10)], float)  # belt, plate and facade fronts
    rep = us.simplify_report(mv, np.array([(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (8, 9, 10), (8, 10, 11)]),
                             [body("UCX_wall", wall), body("UCX_plate", plate), body("UCX_belt", belt)])
    shifts = {a["name"]: a["into"] for a in rep["lists"]["absorb_rebuild"] if a["kind"] == "plane_shift"}
    assert shifts == {"UCX_belt": "UCX_plate"}


def test_report_is_json_and_never_refuses():
    mv, mt, bodies = _belt_case()
    rep = us.simplify_report(mv, mt, bodies)
    json.dumps(rep, allow_nan=False)
    assert rep["status"] == "observe" and set(rep["lists"]) == {"delete", "absorb_rebuild", "keep_with_reason"}
    assert {"seams", "winding", "slivers"} <= set(rep["ported_checks"])


def test_loose_parts_of_one_object_are_separate_bodies():
    v1, t1 = box((0, 0, 0), (1, 1, 1))
    v2, t2 = box((3, 0, 0), (4, 1, 1))
    one = {"name": "UCX_one", "verts": v1 + v2, "tris": t1 + [[i + 8 for i in t] for t in t2]}
    parts = us.split_bodies([one])
    assert [p["name"] for p in parts] == ["UCX_one#1", "UCX_one#2"]


def test_agr_ucx_simplify_report_refuses_existing_output(tmp_path):
    from dt_ai.geometry import ucx_command

    fbx = tmp_path / "m.fbx"
    fbx.write_bytes(b"x")
    out = tmp_path / "r.json"
    out.write_text("{}")
    assert ucx_command.main([str(fbx), str(out), "Main", "--simplify-report"]) == 4
    assert out.read_text() == "{}"
