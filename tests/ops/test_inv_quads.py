"""Kernel invariant quad_dominance [D129]: triangles only where needed. All data is SYNTHETIC."""
import itertools
import math

import numpy as np
import pytest

from dt_ai.ops.inv_quads import (
    NPM_SHARE_MAX, VPM_SHARE_MAX, PolyMesh, allow_triangles_from_parts, check_operation_quads,
    classify_faces, quad_dominance, quad_report,
)
from dt_ai.ops.invariants import Mesh, check_operation
from dt_ai.parts.model import PartsList


# ---- synthetic builders -----------------------------------------------------------------------------------------

def grid(nx, ny, size=1.0, origin=(0.0, 0.0, 0.0)):
    """(vertices, quads) of a planar nx x ny quad grid in z = origin z, counter-clockwise seen from +z."""
    ox, oy, oz = origin
    v = [(ox + i * size, oy + j * size, oz) for j in range(ny + 1) for i in range(nx + 1)]
    idx = lambda i, j: j * (nx + 1) + i            # noqa: E731
    f = [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)) for j in range(ny) for i in range(nx)]
    return v, f


def poly(v, f):
    return PolyMesh(np.array(v, dtype=float), tuple(tuple(x) for x in f))


def split_quad(faces, k):
    """Replace quad k by two triangles over its 0-2 diagonal; the triangles get ids k and len(faces)."""
    a, b, c, d = faces[k]
    out = list(faces)
    out[k] = (a, b, c)
    out.append((a, c, d))
    return out


def grid_with_border_triangle(n=6):
    """n x n grid plus one triangle on the right border: the disk outline gets 4n + 1 edges (odd)."""
    v, f = grid(n, n)
    p, q = n, 2 * n + 1                            # right border edge (n, 0) -> (n, 1)
    v.append((n + 0.5, 0.5, 0.0))
    f.append((p, len(v) - 1, q))
    return v, f


def grid_with_unneeded_pair(n=6):
    """n x n grid; two neighbouring interior quads become tri + parallelogram + tri: two non-adjacent triangles."""
    v, f = grid(n, n)
    idx = lambda i, j: j * (n + 1) + i             # noqa: E731
    k = 2 * n + 2                                  # quad (2, 2); its right neighbour is k + 1
    v0, v1, v2 = idx(2, 2), idx(3, 2), idx(4, 2)
    v3, v4, v5 = idx(2, 3), idx(3, 3), idx(4, 3)
    f[k] = (v0, v1, v3)
    f[k + 1] = (v1, v2, v4, v3)
    f.append((v2, v5, v4))
    return v, f, (k, len(f) - 1)


def ngon_fan(n, center=(0.0, 0.0, 0.0), radius=1.0):
    """Planar regular n-gon closed by a fan of n triangles around its centre (an open disk)."""
    cx, cy, cz = center
    v = [(cx, cy, cz)] + [(cx + radius * math.cos(2 * math.pi * i / n), cy + radius * math.sin(2 * math.pi * i / n), cz)
                          for i in range(n)]
    f = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    return v, f


def capped_prism(n, rows):
    """Regular n-gon prism: side walls of n x rows quads, top and bottom caps as triangle fans (closed)."""
    v, f = [], []
    for r in range(rows + 1):
        for i in range(n):
            a = 2 * math.pi * i / n
            v.append((math.cos(a), math.sin(a), r * 0.25))
    ring = lambda r, i: r * n + i % n              # noqa: E731
    for r in range(rows):
        for i in range(n):
            f.append((ring(r, i), ring(r, i + 1), ring(r + 1, i + 1), ring(r + 1, i)))
    bottom, top = len(v), len(v) + 1
    v += [(0.0, 0.0, 0.0), (0.0, 0.0, rows * 0.25)]
    for i in range(n):
        f.append((bottom, ring(0, i + 1), ring(0, i)))
        f.append((top, ring(rows, i), ring(rows, i + 1)))
    return v, f


def merge(*parts):
    """Concatenate (v, f) pairs into one disconnected mesh."""
    v, f = [], []
    for pv, pf in parts:
        off = len(v)
        v += list(pv)
        f += [tuple(i + off for i in face) for face in pf]
    return v, f


def parts_list(part_id, operation="library_replace", part_class="other"):
    entry = {"id": part_id, "part_class": part_class, "sources": [{"kind": "object", "reference": "Src"}],
             "operation": operation, "triangle_budget": {"npm": 10, "vpm": 10}}
    if operation == "library_replace":
        entry["library_ref"] = "lib/tree_a"
    if operation == "primitive":
        entry["build_as"] = "box"
    other = {"id": "wall_a", "part_class": "wall", "sources": [{"kind": "object", "reference": "Wall"}],
             "operation": "keep", "triangle_budget": {"npm": 10, "vpm": 10}}
    return PartsList.model_validate({
        "synthetic": True, "object_id": "SYN1", "source_tier": "B",
        "sources": [{"kind": "synthetic", "reference": "fixture"}],
        "triangle_budget": {"npm": 100, "vpm": 100}, "parts": [entry, other]})


def labels(v, f, **kw):
    return classify_faces(poly(v, f), **kw)


# ---- (a)-(h) acceptance cases -----------------------------------------------------------------------------------

def test_a_all_quad_grid_passes_with_zero_share():
    v, f = grid(4, 4)
    for profile in ("NPM", "VPM"):
        r = quad_dominance({"p": poly(v, f)}, profile)
        assert (r.name, r.passed, r.count, r.offenders) == ("quad_dominance", True, 0, ())
    rep = quad_report({"p": poly(v, f)}, "VPM")["p"]
    assert (rep.faces, rep.triangles, rep.quads, rep.ngons, rep.triangle_share) == (16, 0, 16, 0, 0.0)


def test_b_split_quad_gives_two_mergeable_offenders_with_part_and_face_ids():
    v, f = grid(4, 4)
    f = split_quad(f, 5)
    r = quad_dominance({"grid": poly(v, f)}, "NPM")
    assert not r.passed and r.count == 2
    assert sorted(o.split(":")[0] for o in r.offenders) == ["grid#16", "grid#5"]
    assert all("mergeable" in o for o in r.offenders)
    rep = quad_report({"grid": poly(v, f)}, "NPM")["grid"]
    assert rep.needed == {} and len(rep.offenders) == 2


def test_c_odd_boundary_disk_passes_with_exactly_one_needed_triangle():
    v, f = grid_with_border_triangle(6)
    for profile in ("NPM", "VPM"):
        assert quad_dominance({"disk": poly(v, f)}, profile).passed
    rep = quad_report({"disk": poly(v, f)}, "VPM")["disk"]
    assert rep.triangles == 1 and rep.needed == {"odd_boundary": 1}
    assert labels(v, f)[-1] == "needed:odd_boundary"


@pytest.mark.parametrize("n, expected", [
    (5, {"odd_boundary": 2, "pole_fan": 8}),     # a pentagon outline is odd: rule 2 names one triangle per cap first
    (6, {"pole_fan": 12}),
])
def test_d_ngon_caps_closed_by_fans_pass_as_needed(n, expected):
    v, f = capped_prism(n, rows=40)
    r = quad_dominance({"prism": poly(v, f)}, "VPM")
    assert r.passed, r.offenders
    rep = quad_report({"prism": poly(v, f)}, "VPM")["prism"]
    assert rep.needed == expected and rep.offenders == ()


def test_e_triangle_needed_by_no_rule_is_unneeded():
    v, f, (t1, t2) = grid_with_unneeded_pair(6)
    r = quad_dominance({"wall_a": poly(v, f)}, "NPM")
    assert not r.passed and r.count == 2
    assert sorted(r.offenders) == sorted([f"wall_a#{t1}: unneeded", f"wall_a#{t2}: unneeded"])


def test_f_same_triangles_pass_when_the_part_is_a_library_replacement():
    v, f, _ = grid_with_unneeded_pair(6)
    allow = allow_triangles_from_parts(parts_list("tree_a"))
    assert allow == frozenset({"tree_a"})
    r = quad_dominance({"tree_a": poly(v, f)}, "VPM", allow_triangles=allow)
    assert r.passed, r.offenders
    assert quad_report({"tree_a": poly(v, f)}, "VPM", allow_triangles=allow)["tree_a"].needed == {"parts_list": 2}
    assert not quad_dominance({"wall_a": poly(v, f)}, "VPM", allow_triangles=allow).passed


@pytest.mark.parametrize("part_class", ["railing", "rod_ladder", "grille", "ac_screen", "fence"])
def test_f_opacity_classes_are_allowed(part_class):
    assert allow_triangles_from_parts(parts_list("x_a", "primitive", part_class)) == frozenset({"x_a"})


def test_f_other_parts_are_not_allowed():
    assert allow_triangles_from_parts(parts_list("x_a", "keep", "wall")) == frozenset()


def test_g_five_sided_face_is_an_ngon_offender():
    v = [(0, 0, 0), (2, 0, 0), (3, 1, 0), (1, 2, 0), (-1, 1, 0)]
    r = quad_dominance({"p": poly(v, [(0, 1, 2, 3, 4)])}, "NPM")
    assert not r.passed and r.count == 1 and r.offenders == ("p#0: ngon (5 sides)",)


def share_part(quads_y):
    """A 2 x quads_y quad grid plus a separate hexagon fan (6 pole_fan triangles)."""
    return poly(*merge(grid(2, quads_y), ngon_fan(6, center=(10.0, 10.0, 0.0))))


def test_h_six_percent_share_passes_npm_and_fails_vpm():
    p = share_part(47)                             # 94 quads + 6 needed triangles = 6 %
    rep = quad_report({"p": p}, "NPM")["p"]
    assert rep.faces == 100 and rep.needed == {"pole_fan": 6} and rep.needed_share == pytest.approx(0.06)
    assert quad_dominance({"p": p}, "NPM").passed
    r = quad_dominance({"p": p}, "VPM")
    assert not r.passed and r.count == 1 and "6.0%" in r.offenders[0] and "VPM" in r.offenders[0]


@pytest.mark.parametrize("quads_y, profile, passed", [
    (57, "VPM", True),                             # 6 / 120 = 5 % exactly: at the threshold passes (<=)
    (56, "VPM", False),                            # 6 / 118 > 5 %
    (27, "NPM", True),                             # 6 / 60 = 10 % exactly
    (26, "NPM", False),
])
def test_share_exactly_at_threshold(quads_y, profile, passed):
    assert quad_dominance({"p": share_part(quads_y)}, profile).passed is passed


def test_share_constants():
    assert (NPM_SHARE_MAX, VPM_SHARE_MAX) == (0.10, 0.05)


# ---- mergeable edge cases ---------------------------------------------------------------------------------------

def test_folded_pair_at_10_degrees_is_not_mergeable():
    t = math.radians(10)
    v = [(0, 0, 0), (0, 1, 0), (-1, 0.5, 0), (math.cos(t), 0.5, math.sin(t))]
    lab = labels(v, [(0, 1, 2), (1, 0, 3)])
    assert "mergeable" not in lab


def test_same_pair_flat_is_mergeable():
    v = [(0, 0, 0), (0, 1, 0), (-1, 0.5, 0), (1, 0.5, 0)]
    assert labels(v, [(0, 1, 2), (1, 0, 3)]) == ["mergeable", "mergeable"]


def test_pair_within_planar_deg_is_mergeable_and_outside_is_not():
    for deg, merged in ((0.9, True), (1.1, False)):
        t = math.radians(deg)
        v = [(0, 0, 0), (0, 1, 0), (-1, 0.5, 0), (math.cos(t), 0.5, math.sin(t))]
        assert (labels(v, [(0, 1, 2), (1, 0, 3)]) == ["mergeable"] * 2) is merged


def test_non_convex_pair_is_not_mergeable():
    v = [(0, 0, 0), (1, 0, 0), (2, 1, 0), (2, -1, 0)]   # arrowhead: reflex corner at vertex 1
    lab = labels(v, [(0, 1, 2), (1, 0, 3)])
    assert lab == ["unneeded", "unneeded"]


def test_pair_with_a_straight_corner_is_not_mergeable():
    v = [(0, 0, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0)]  # merged quad 0-3-1-2: 180 deg at vertex 0
    assert labels(v, [(0, 1, 2), (1, 0, 3)]) == ["unneeded", "unneeded"]


def test_inconsistent_winding_does_not_hide_a_mergeable_pair():
    v = [(0, 0, 0), (0, 1, 0), (-1, 0.5, 0), (1, 0.5, 0)]
    assert labels(v, [(0, 1, 2), (0, 1, 3)]) == ["mergeable", "mergeable"]


def test_four_triangle_fan_of_a_square_is_neither_mergeable_nor_a_pole():
    v, f = ngon_fan(4)                             # merging two fan triangles puts a 180 deg corner on the centre
    assert set(labels(v, f)) == {"unneeded"}


# ---- odd boundary budget ----------------------------------------------------------------------------------------

def test_odd_boundary_names_only_the_minimal_triangle():
    v2, f2, pair = grid_with_unneeded_pair(6)
    # both modifications in one disk: outline 25 edges (odd), three triangles, only one is needed
    f2 = list(f2)
    v2.append((6.5, 0.5, 0.0))
    f2.append((6, len(v2) - 1, 13))
    lab = labels(v2, f2)
    assert lab.count("needed:odd_boundary") == 1 and lab[-1] == "needed:odd_boundary"
    assert [lab[i] for i in pair] == ["unneeded", "unneeded"]


def test_annulus_with_two_odd_loops_has_even_parity():
    # 3x3 ring (outer loop 12 edges, hole 4): a notch on each loop -> loops 13 and 5, total 18 (even)
    v, f = grid(3, 3)
    f = [q for k, q in enumerate(f) if k != 4]             # hole in the middle
    v += [(3.5, 1.5, 0.0), (1.5, 1.5 - 0.0, 0.0)]
    f.append((7, len(v) - 2, 11))                          # notch on the outer right border
    lab = labels(v, f)
    assert lab[-1] == "needed:odd_boundary"                # outline 13 + 4 = 17 edges: odd
    f.append((5, 6, len(v) - 1))                           # a notch into the hole: loops 13 + 5 = 18, even
    lab = labels(v, f)
    assert lab.count("needed:odd_boundary") == 0


# ---- fail-closed probes -----------------------------------------------------------------------------------------

def test_empty_scene_fails():
    r = quad_dominance({}, "NPM")
    assert not r.passed and r.offenders


def test_empty_changed_list_fails():
    v, f = grid(2, 2)
    r = quad_dominance({"p": poly(v, f)}, "NPM", parts=[])
    assert not r.passed and r.offenders


def test_part_without_faces_fails():
    r = quad_dominance({"p": PolyMesh(np.zeros((0, 3)), ())}, "NPM")
    assert not r.passed and r.offenders == ("p: no faces",)


def test_zero_area_faces_fail():
    v = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0)]
    r = quad_dominance({"p": poly(v, [(0, 1, 2)])}, "NPM")
    assert not r.passed and r.offenders == ("p#0: degenerate (zero area)",)
    r = quad_dominance({"p": poly([(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)], [(0, 1, 2, 3)])}, "NPM")
    assert not r.passed and "degenerate" in r.offenders[0]


@pytest.mark.parametrize("vertices, faces", [
    ([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 1)]),               # repeated index
    ([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1)]),                  # fewer than 3 sides
    ([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 3)]),               # index out of range
    ([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, -1)]),              # negative index
    ([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2.5)]),             # non-integer index
    ([(0, 0, 0), (1, 0, float("nan")), (0, 1, 0)], [(0, 1, 2)]),    # NaN coordinate
    ([(0, 0, 0), (1, 0, float("inf")), (0, 1, 0)], [(0, 1, 2)]),    # inf coordinate
    ([(0, 0), (1, 0), (0, 1)], [(0, 1, 2)]),                         # not (n, 3)
])
def test_malformed_poly_mesh_raises(vertices, faces):
    with pytest.raises(ValueError):
        PolyMesh(np.array(vertices, dtype=float), tuple(tuple(x) for x in faces))


@pytest.mark.parametrize("profile", ["", "IFC", "npm-roof", None, "NPMX"])
def test_unknown_profile_raises(profile):
    v, f = grid(2, 2)
    with pytest.raises(ValueError):
        quad_dominance({"p": poly(v, f)}, profile)


@pytest.mark.parametrize("profile", ["NPM", "VPM", "NPM-OKS", "VPM-OKS", "NPM-Ground", "VPM-Ground", "vpm-oks"])
def test_known_profiles(profile):
    v, f = grid(2, 2)
    assert quad_dominance({"p": poly(v, f)}, profile).passed


def test_unknown_part_raises():
    v, f = grid(2, 2)
    with pytest.raises(ValueError):
        quad_dominance({"p": poly(v, f)}, "NPM", parts=["q"])


def test_offenders_capped_at_five_but_report_is_full():
    v, f = grid(4, 4)
    for k in range(0, 16, 2):
        f = split_quad(f, k)
    r = quad_dominance({"p": poly(v, f)}, "NPM")
    assert r.count == 16 and len(r.offenders) == 5
    assert len(quad_report({"p": poly(v, f)}, "NPM")["p"].offenders) == 16


# ---- generated probes -------------------------------------------------------------------------------------------

def test_probe_every_split_quad_in_a_grid_is_caught():
    """Generated: each quad of a 5x5 grid split on either diagonal, in turn -> exactly 2 mergeable offenders."""
    v, base = grid(5, 5)
    n = 0
    for k, flip in itertools.product(range(25), (False, True)):
        f = list(base)
        if flip:
            a, b, c, d = f[k]
            f[k] = (b, c, d, a)
        f = split_quad(f, k)
        r = quad_dominance({"p": poly(v, f)}, "NPM")
        assert not r.passed and r.count == 2 and all("mergeable" in o for o in r.offenders)
        n += 1
    assert n == 50


def test_probe_random_planar_quad_grids_pass_and_random_ngons_fail():
    rng = np.random.default_rng(345)
    for _ in range(30):
        nx, ny = rng.integers(1, 7, size=2)
        v, f = grid(int(nx), int(ny), size=float(rng.uniform(0.05, 3.0)), origin=tuple(rng.uniform(-1e3, 1e3, 3)))
        assert quad_dominance({"p": poly(v, f)}, "VPM").passed
        k = int(rng.integers(0, len(f)))
        a, b, c, d = f[k]
        v2 = v + [tuple((np.array(v[a]) + np.array(v[b])) / 2)]
        f2 = list(f)
        f2[k] = (a, len(v2) - 1, b, c, d)                  # a 5-gon (its neighbour keeps a T-junction)
        r = quad_dominance({"p": poly(v2, f2)}, "VPM")
        assert not r.passed and f"p#{k}: ngon (5 sides)" in r.offenders


# ---- wrapper ----------------------------------------------------------------------------------------------------

BOX_V = [(i & 1, (i >> 1) & 1, (i >> 2) & 1) for i in range(8)]
BOX_Q = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]


def to_tri_mesh(v, faces):
    tris = [(f[0], f[i], f[i + 1]) for f in faces for i in range(1, len(f) - 1)]
    return Mesh(np.array(v, dtype=float), np.array(tris))


@pytest.mark.parametrize("split, passed", [(False, True), (True, False)])
def test_wrapper_keeps_earlier_results_and_adds_quad_dominance(split, passed):
    faces = split_quad(BOX_Q, 1) if split else BOX_Q      # same triangles either way: only the polygons differ
    after = {"box": to_tri_mesh(BOX_V, BOX_Q)}
    plain = check_operation(None, after, ["box"])
    assert plain.passed
    rep = check_operation_quads(plain, {"box": poly(BOX_V, faces)}, ["box"], "VPM-OKS")
    assert len(rep.results) == len(plain.results) + 1
    for old, new in zip(plain.results, rep.results):
        assert (old.name, old.passed, old.count, old.offenders) == (new.name, new.passed, new.count, new.offenders)
    assert rep.results[-1].name == "quad_dominance"
    assert [r.name for r in rep.results].count("quad_dominance") == 1
    assert rep.passed is passed and rep.results[-1].passed is passed


def test_wrapper_rejects_changed_parts_missing_from_the_polygons():
    after = {"box": to_tri_mesh(BOX_V, BOX_Q)}
    with pytest.raises(ValueError):
        check_operation_quads(check_operation(None, after, ["box"]), {}, ["box"], "NPM")


def test_wrapper_rejects_a_second_quad_dominance():
    after = {"box": to_tri_mesh(BOX_V, BOX_Q)}
    rep = check_operation_quads(check_operation(None, after, ["box"]), {"box": poly(BOX_V, BOX_Q)}, ["box"], "NPM")
    with pytest.raises(ValueError):
        check_operation_quads(rep, {"box": poly(BOX_V, BOX_Q)}, ["box"], "NPM")


def test_closed_quad_box_is_all_quads():
    assert set(classify_faces(poly(BOX_V, BOX_Q))) == {"quad"}
