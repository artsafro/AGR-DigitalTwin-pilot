"""Kernel invariant xview_overlaps (#370): overlapping vertices 2 mm / faces 5 mm with 3ds Max xView parity.

All data is SYNTHETIC. The xView rows were measured in headless 3ds Max 2026.3 (OverlappingVertices /
OverlappingFaces.Check), see docs/research/xview-parity-ground-v014.md.
"""
import itertools

import numpy as np
import pytest

from dt_ai.ops.invariants import InvariantReport, InvariantResult, Mesh
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import (
    FACE_M, NAME, PARALLEL_COS_MIN, VERTEX_M, XviewTolerance, check_operation_xview, mesh_report, tolerance_for,
    xview_overlaps, xview_report,
)


def poly(v, f):
    return PolyMesh(np.asarray(v, dtype=float), tuple(tuple(x) for x in f))


def quad(x0=0.0, z=0.0, flip=False, y0=0.0, size=1.0):
    v = [(x0, y0, z), (x0 + size, y0, z), (x0 + size, y0 + size, z), (x0, y0 + size, z)]
    return v, [(3, 2, 1, 0) if flip else (0, 1, 2, 3)]


def join(*parts):
    v, f = [], []
    for pv, pf in parts:
        f += [tuple(i + len(v) for i in face) for face in pf]
        v += list(pv)
    return poly(v, f)


def two_tris(gap):
    """Two triangles touching at x = 0, their corner vertices `gap` apart (not welded)."""
    return poly([(0, 0, 0), (1, 0, 0), (0, 1, 0), (-gap, 0, 0), (-1, 0, 0), (-1, 1, 0)], [(0, 1, 2), (3, 5, 4)])


def rep(mesh, profile="NPM"):
    return xview_report({"p": mesh}, profile)["p"]


# ---- the acceptance table of #370 ----------------------------------------------------------------------------------

def test_two_verts_1_5_mm_apart_not_welded_is_one_vertex_pair():
    r = rep(two_tris(0.0015))
    assert len(r.vertex_pairs) == 1 and r.vertices == (1, 4)   # Max: v=[1,4]
    assert not xview_overlaps({"p": two_tris(0.0015)}, "NPM").passed


def test_two_verts_2_5_mm_apart_is_clean():
    r = rep(two_tris(0.0025))
    assert r.vertex_pairs == () and r.face_pairs == ()
    assert xview_overlaps({"p": two_tris(0.0025)}, "NPM").passed


def test_welded_shared_vertex_is_clean():
    m = poly([(0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (-1, 1, 0)], [(0, 1, 2), (0, 4, 3)])
    r = xview_overlaps({"p": m}, "NPM")
    assert (r.name, r.passed, r.count, r.offenders) == (NAME, True, 0, ())


def test_two_coplanar_quads_overlapping_50_percent_is_one_face_pair():
    r = rep(join(quad(), quad(0.5)))
    assert len(r.face_pairs) == 1 and r.faces == (1, 2)          # Max (Editable Poly): f=[1,2]
    assert r.vertex_pairs == ()


def test_same_quads_6_mm_apart_in_normal_direction_are_clean():
    r = rep(join(quad(), quad(0.5, z=0.006)))
    assert r.face_pairs == () and r.vertex_pairs == ()


def test_opposite_facing_coplanar_overlap_is_one_face_pair():
    r = rep(join(quad(), quad(0.5, flip=True)))
    assert len(r.face_pairs) == 1 and r.faces == (1, 2)


# ---- xView behaviour measured in Max (parity rows) -----------------------------------------------------------------

@pytest.mark.parametrize("z,hit", [(0.0, True), (0.001, True), (0.004, True), (0.0049, True), (0.0051, False),
                                   (0.006, False)])
@pytest.mark.parametrize("flip", [False, True])
def test_quad_overlap_distance_band_matches_xview(z, hit, flip):
    assert bool(rep(join(quad(), quad(0.5, z=z, flip=flip))).face_pairs) is hit


def test_zero_area_touch_is_a_contact_pair_like_xview():
    """Max flags faces that only touch along an edge (unwelded coincident vertices): f=[1,2], v=[2,3,5,8]."""
    r = rep(join(quad(), quad(1.0)))
    assert [p[2] for p in r.face_pairs] == ["contact"]
    assert len(r.vertex_pairs) == 2


def test_in_plane_gap_3_mm_is_clean_like_xview():
    assert rep(join(quad(), quad(1.003))).face_pairs == ()


def test_edge_crossing_without_vertex_containment_is_an_area_pair_xview_misses():
    """Max returns f=[] here (no vertex of one face lies in the other); the area rule catches the real overlap."""
    m = join(([(0, 0, 0), (3, 0, 0), (3, 1, 0), (0, 1, 0)], [(0, 1, 2, 3)]),
             ([(1, -1, 0.001), (2, -1, 0.001), (2, 2, 0.001), (1, 2, 0.001)], [(0, 1, 2, 3)]))
    r = rep(m)
    assert [p[2] for p in r.face_pairs] == ["area"] and r.xview_faces == ()


def _tilted(th_deg, flip=False):
    t = np.tan(np.radians(th_deg)) * 2.5
    tri = [(0.5, 0.5, 0.001), (3, 0.5, 0.001 + t), (3, 1.5, 0.001 + t)]
    v, f = quad()
    return join((v, f), (tri, [(0, 2, 1) if flip else (0, 1, 2)]))


@pytest.mark.parametrize("th,hit", [(0.6, True), (0.8, True), (0.805, True), (0.815, False), (0.9, False)])
@pytest.mark.parametrize("flip", [False, True])
def test_parallel_limit_matches_xview(th, hit, flip):
    assert bool(rep(_tilted(th, flip)).xview_faces) is hit


def test_parallel_cos_constant_is_the_measured_xview_limit():
    assert np.degrees(np.arccos(PARALLEL_COS_MIN)) == pytest.approx(0.8103, abs=1e-3)
    assert (VERTEX_M, FACE_M) == (0.002, 0.005)


def test_duplicate_face_with_shared_vertices_is_an_area_pair():
    """xView OverlappingFaces skips it (f=[]), but the same area twice is a z-fight: area pair."""
    r = rep(poly([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2), (0, 1, 2)]))
    assert [p[2] for p in r.face_pairs] == ["area"]


def test_fold_over_shared_edge_is_flagged():
    m = poly([(0, 0, 0), (1, 0, 0), (0.5, 1, 0), (0.5, 0.5, 0.001)], [(0, 1, 2), (1, 0, 3)])
    assert rep(m).faces == (1, 2)


def test_flat_grid_of_shared_quads_is_clean():
    v = [(x, y, 0.0) for y in range(4) for x in range(4)]
    f = [(y * 4 + x, y * 4 + x + 1, y * 4 + x + 5, y * 4 + x + 4) for y in range(3) for x in range(3)]
    assert xview_overlaps({"g": poly(v, f)}, "VPM").passed


def test_triangle_mesh_input_is_accepted():
    m = Mesh(np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.2, 0.2, 0.001), (0.6, 0.2, 0.001), (0.2, 0.6, 0.001)]),
             np.array([(0, 1, 2), (3, 4, 5)]))
    assert rep(m).faces == (1, 2)


# ---- thresholds: one constant block, overridable per profile -------------------------------------------------------

def test_profiles_and_override():
    for p in ("NPM", "VPM", "NPM-OKS", "VPM-GROUND"):
        assert tolerance_for(p) == XviewTolerance(VERTEX_M, FACE_M, PARALLEL_COS_MIN)
    with pytest.raises(ValueError, match="profile"):
        tolerance_for("IFC")
    loose = XviewTolerance(vertex_m=0.001)
    assert xview_overlaps({"p": two_tris(0.0015)}, "NPM", tol=loose).passed


def test_exactly_at_threshold_fails_closed():
    """Fail-closed policy: 2.000 mm vertices / 5.000 mm faces count (Max: faces yes, vertices no - listed)."""
    assert len(rep(two_tris(VERTEX_M)).vertex_pairs) == 1
    assert rep(join(quad(), quad(0.5, z=FACE_M))).face_pairs


# ---- fail-closed input ---------------------------------------------------------------------------------------------

def test_no_parts_or_empty_part_never_pass():
    r = xview_overlaps({}, "NPM")
    assert not r.passed and r.count == 1
    r = xview_overlaps({"p": two_tris(0.01)}, "NPM", parts=[])
    assert not r.passed
    r = xview_overlaps({"p": PolyMesh(np.zeros((0, 3)), ())}, "NPM")
    assert not r.passed and "no faces" in r.offenders[0]


def test_unknown_part_is_an_error_naming_it():
    with pytest.raises(ValueError, match="ghost"):
        xview_overlaps({"p": two_tris(0.01)}, "NPM", parts=["ghost"])


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_nonfinite_vertices_raise(bad):
    with pytest.raises(ValueError):
        poly([(0, 0, 0), (1, 0, 0), (0, bad, 0)], [(0, 1, 2)])
    with pytest.raises(ValueError):
        mesh_report(np.array([(0, 0, 0), (1, 0, 0), (0, bad, 0)]), np.array([(0, 1, 2)]))


def test_bad_tolerance_raises():
    for t in (XviewTolerance(vertex_m=-1.0), XviewTolerance(face_m=np.nan), XviewTolerance(parallel_cos_min=1.5)):
        with pytest.raises(ValueError):
            xview_overlaps({"p": two_tris(0.01)}, "NPM", tol=t)


# ---- wiring: report-only first -------------------------------------------------------------------------------------

def test_check_operation_xview_is_report_only_by_default():
    base = InvariantReport((InvariantResult("no_close_overlap", True, 0),))
    out = check_operation_xview(base, {"p": two_tris(0.0015)}, ["p"], "NPM")
    r = out.results[-1]
    assert (r.name, r.passed, r.gating) == (NAME, False, False)
    assert out.passed is True and out.broken == ()
    assert out.to_dict()["results"][-1]["gating"] is False
    gate = check_operation_xview(base, {"p": two_tris(0.0015)}, ["p"], "NPM", gating=True)
    assert gate.passed is False
    with pytest.raises(ValueError, match="already"):
        check_operation_xview(out, {"p": two_tris(0.0015)}, ["p"], "NPM")
    with pytest.raises(ValueError, match="q"):
        check_operation_xview(base, {"p": two_tris(0.0015)}, ["q"], "NPM")


def test_mesh_report_is_json_ready_and_one_based():
    v, f = quad()
    v2, f2 = quad(0.5)
    out = mesh_report(np.array(v + v2), np.array([(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]))
    assert out["gating"] is False and out["passed"] is False
    assert out["xview_faces"] and min(out["faces"]) >= 1
    assert out["thresholds"] == {"vertex_m": VERTEX_M, "face_m": FACE_M, "parallel_cos_min": PARALLEL_COS_MIN}


# ---- generated probes (guarantees of the issue) --------------------------------------------------------------------

def test_probe_vertex_pairs_equal_brute_force():
    """Random clouds: the vertex pairs equal the O(n^2) brute force (<= vertex_m), 40 seeds."""
    for seed in range(40):
        rng = np.random.default_rng(seed)
        v = rng.uniform(0, 0.02, size=(60, 3))
        f = [(i, i + 1, i + 2) for i in range(0, 57, 3)]
        got = {(a, b) for a, b, _ in rep(poly(v, f)).vertex_pairs}
        want = {(a + 1, b + 1) for a, b in itertools.combinations(range(60), 2)
                if np.linalg.norm(v[a] - v[b]) <= VERTEX_M}
        assert got == want, seed


def test_probe_translation_invariant_far_from_origin():
    """Same layout 120 m / 150 m from the origin (Ground coordinates) gives the same pairs."""
    m = join(quad(), quad(0.5, z=0.003), quad(3.0), quad(4.0015))
    far = poly(m.vertices + np.array([120.0, -95.0, 150.0]), m.faces)
    a, b = rep(m), rep(far)
    assert len(a.vertex_pairs) == len(b.vertex_pairs) == 2
    assert [p[:3] for p in a.face_pairs] == [p[:3] for p in b.face_pairs]
