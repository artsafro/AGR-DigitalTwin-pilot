"""Shared UCX builder (#166): src/dt_ai/geometry/ucx_build.py.

All meshes here are SYNTHETIC fixtures, not data of a real object. The checks reuse the read-only audit
geometry of src/twinqa/geometry/ucx_audit.py (closed, convex, SAT overlap, gaps) and the scene grammar of
src/twinqa/naming.py, so the builder is judged by the same code that judges deliveries.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dt_ai.geometry import ucx_build as ub
from twinqa.geometry import ucx_audit as ua
from twinqa.scene import ucx_triangle_limit as checker_limit

BOX_TRIS = ub._BOX_TRIS


def box_mesh(lo, hi, angle_deg=0.0):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    c = np.array([(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
                  (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])])
    return c @ ub._rot(angle_deg).T, BOX_TRIS.copy()


def union(*meshes):
    vs, ts, off = [], [], 0
    for v, t in meshes:
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(ts)


def courtyard_building(angle=0.0):
    """SYNTHETIC: 30 x 30 m ring, 12 m high, 10 x 10 m courtyard, one 4 m tower on the roof."""
    parts = [box_mesh((0, 0, 0), (30, 10, 12), angle), box_mesh((0, 20, 0), (30, 30, 12), angle),
             box_mesh((0, 10, 0), (10, 20, 12), angle), box_mesh((20, 10, 0), (30, 20, 12), angle),
             box_mesh((2, 2, 12), (6, 6, 16), angle)]
    return union(*parts)


def hull(piece):
    return [tuple(map(float, p)) for p in piece.verts], [tuple(map(int, t)) for t in piece.tris]


def relations(res):
    out = []
    hs = [hull(p) for p in res.pieces]
    bs = [ua.bounds(h[0]) for h in hs]
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            if ua.bbox_gap(bs[i], bs[j]) > ua.NEIGHBOUR_M:
                continue
            out.append(ua.pair_relation(hs[i], hs[j]))
    return out


def assert_valid_pieces(res):
    assert res.pieces
    for p in res.pieces:
        v, t = hull(p)
        assert len(v) == 8 and len(t) == 12
        assert ua.is_closed(t)
        assert ua.is_convex(v, t)
        assert ua.classify(v, t)["kind"] != "custom"
    rel = relations(res)
    kinds = {r[0] for r in rel}
    assert "overlap" not in kinds and "touch" not in kinds, kinds
    gaps = [g for cls, g, _ in rel if cls != "apart"]
    assert all(g >= ub.GAP_BAND_M[0] - ua.BAND_TOL_M for g in gaps), min(gaps)
    return rel


@pytest.mark.parametrize("angle", [0.0, 20.0, -33.0])
def test_main_courtyard_building_valid_and_within_r12(angle):
    v, t = courtyard_building(angle)
    res = ub.build_main(v, t, cell=0.5)
    assert abs(((res.angle_deg - angle + 45) % 90) - 45) < 0.5
    rel = assert_valid_pieces(res)
    assert rel, "neighbouring pieces expected"
    kinds = {ua.classify(*hull(p))["kind"] for p in res.pieces}
    assert kinds <= ({"box_aabb"} if angle == 0 else {"box_oriented"})
    pts = ub.sample_surface(v, t, 0.5)
    dev = ub.main_deviation(pts, res)
    assert dev.max() <= ub.PEDESTRIAN_TOL_M  # R12 holds everywhere, so R13 too
    # courtyard stays open (R01): its centre at mid height is outside every piece
    centre = np.array([[15, 15, 6]]) @ ub._rot(angle).T
    assert ub.main_deviation(centre, res)[0] > 4.0
    # every piece stays within one cell of the source bounds (no collision in the air)
    lo, hi = v.min(axis=0) - res.cell_m * 1.8, v.max(axis=0) + res.cell_m * 1.8
    for p in res.pieces:
        assert (p.verts >= lo).all() and (p.verts <= hi).all()


def test_main_pieces_reverse_distance_bounded_by_cell():
    """UCX -> Main: every exposed piece corner is within one cell diagonal of the source surface."""
    v, t = courtyard_building(12.0)
    res = ub.build_main(v, t, cell=0.5)
    tris = [tuple(v[k] for k in tr) for tr in t]
    worst = 0.0
    for p in res.pieces:
        for q in p.verts:
            d = min(ua.point_triangle_distance(tuple(q), *map(tuple, tr)) for tr in tris)
            inside = ub.main_deviation(q[None], res)[0] == 0.0
            worst = max(worst, d if inside else 0.0)
    assert worst <= res.cell_m * math.sqrt(3) + 1e-6


def test_main_names_pass_scene_grammar():
    from twinqa import naming

    v, t = courtyard_building()
    res = ub.build_main(v, t, cell=1.0)
    names = ub.ucx_names("Kpp_1", "Main", len(res.pieces))
    rep = ua.name_report(names, "SM_Kpp_1_Main")
    assert rep["mask_bad_count"] == 0 and rep["Main"]["contiguous_from_1"]
    assert all(naming.is_ucx(n) for n in names)


def test_budget_grows_cell_and_fails_closed():
    """SYNTHETIC: 1 300 separate 0.6 m cubes need 1 300 boxes > 1 250 (15 000 tris) at cell 0.3."""
    cubes = [box_mesh((2 * i, 2 * j, 0), (2 * i + 0.6, 2 * j + 0.6, 0.6)) for i in range(26) for j in range(50)]
    v, t = union(*cubes)
    with pytest.raises(ub.UcxBuildError, match="budget"):
        ub.build_main(v, t, cell=0.3, max_attempts=1)
    res = ub.build_main(v, t, cell=0.3)
    assert res.triangles <= res.budget == 15000 and len(res.attempts) > 1
    assert res.attempts[0]["pieces"] >= 1300


@pytest.mark.parametrize("n", [0, 49999, 50000, 50001, 300000, 2000001, 2000000])
def test_budget_formula_matches_checker(n):
    assert ub.ucx_triangle_limit(n) == checker_limit(n)


def terrain(nx=60, ny=40, step=1.0):
    """SYNTHETIC rolling ground (amplitude ~0.8 m) as a triangulated grid."""
    xs, ys = np.arange(nx + 1) * step, np.arange(ny + 1) * step
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    gz = 0.5 * np.sin(gx / 7.0) + 0.3 * np.cos(gy / 5.0) + 0.02 * gx
    v = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)
    idx = lambda i, j: i * (ny + 1) + j  # noqa: E731
    t = []
    for i in range(nx):
        for j in range(ny):
            t += [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1)), (idx(i, j), idx(i + 1, j + 1), idx(i, j + 1))]
    return v, np.array(t)


def test_ground_within_r11_and_valid():
    v, t = terrain()
    res = ub.build_ground(v, t, tol=0.08)
    assert res.target == "Ground" and res.max_vertical_dev_m <= 0.08
    assert_valid_pieces(res)
    pts = ub.sample_surface(v, t, 0.25)
    dev = ub.ground_deviation(pts, res)
    assert np.isfinite(dev).all(), "every surface point lies over a piece"
    assert dev.max() <= ub.GROUND_TOL_M  # R11
    rep = ua.name_report(ub.ucx_names("Kpp_1", "Ground", len(res.pieces)), "SM_Kpp_1_Main")
    assert rep["Ground"]["contiguous_from_1"] and rep["mask_bad_count"] == 0


def test_ground_random_terrains_probe():
    """Probe: 8 seeded random terrains -> every piece closed/convex, no overlap; the reported
    max_vertical_dev_m is exact (never below the dense-sample deviation), so 'within R11' is never claimed
    falsely; terrains with noise below the mesh step pass R11."""
    rng = np.random.default_rng(166)
    passed = 0
    for k in range(8):
        v, t = terrain(16, 12, 1.5)
        v[:, 2] += rng.normal(0, 0.15 if k % 2 else 0.03, len(v))
        res = ub.build_ground(v, t, cell=12.0, min_cell=0.75, tol=0.08)
        assert_valid_pieces(res)
        pts = ub.sample_surface(v, t, 0.3)
        dev = ub.ground_deviation(pts, res)
        assert np.isfinite(dev).all()
        inner = ub.ground_deviation(pts, res, margin=0.0)  # inside a piece plan: the builder's value is exact
        assert inner[np.isfinite(inner)].max() <= res.max_vertical_dev_m + 1e-9
        assert res.within_tol == (res.max_vertical_dev_m <= 0.08)
        if res.within_tol:
            assert dev.max() <= ub.GROUND_TOL_M
            passed += 1
    assert passed >= 4, passed


def test_main_random_buildings_probe():
    """Probe: 15 seeded random block buildings (2-5 boxes, random facade angle) -> valid, no overlap/touch,
    Main -> UCX <= R12 0.3 m."""
    rng = np.random.default_rng(1661)
    for _ in range(15):
        ang = float(rng.uniform(-45, 45))
        parts = []
        for _k in range(int(rng.integers(2, 6))):
            x, y = rng.uniform(0, 20, 2)
            w, d, h = rng.uniform(3, 12, 3)
            z = float(rng.choice([0.0, rng.uniform(0, 6)]))
            parts.append(box_mesh((x, y, z), (x + w, y + d, z + h), ang))
        v, t = union(*parts)
        res = ub.build_main(v, t, cell=0.6)
        assert_valid_pieces(res)
        assert ub.main_deviation(ub.sample_surface(v, t, 0.5), res).max() <= ub.PEDESTRIAN_TOL_M


@pytest.mark.parametrize("target", ["Main", "Ground"])
@pytest.mark.parametrize("case", ["empty", "nan", "inf", "index", "flat_zero_area"])
def test_bad_meshes_fail_closed(target, case):
    v, t = box_mesh((0, 0, 0), (5, 5, 5))
    v = v.astype(float)
    if case == "empty":
        v, t = np.zeros((0, 3)), np.zeros((0, 3), int)
    elif case == "nan":
        v[3, 1] = np.nan
    elif case == "inf":
        v[0, 2] = np.inf
    elif case == "index":
        t = t.copy()
        t[0, 0] = 99
    else:
        v = np.zeros_like(v)
    with pytest.raises(ub.UcxBuildError):
        ub.build(target, v, t)


@pytest.mark.parametrize("gap", [0.002, 0.0029, 0.0061, 0.01, 0.0, -0.004, float("nan"), float("inf")])
def test_gap_outside_build_band_fails_closed(gap):
    v, t = courtyard_building()
    with pytest.raises(ub.UcxBuildError):
        ub.build_main(v, t, cell=1.0, gap=gap)
    tv, tt = terrain(10, 10)
    with pytest.raises(ub.UcxBuildError):
        ub.build_ground(tv, tt, gap=gap)


@pytest.mark.parametrize("gap", [0.003, 0.006])
def test_gap_band_edges_accepted(gap):
    v, t = courtyard_building()
    res = ub.build_main(v, t, cell=1.0, gap=gap)
    assert_valid_pieces(res)


def test_unknown_target_and_names_fail_closed():
    v, t = courtyard_building()
    with pytest.raises(ub.UcxBuildError):
        ub.build("Glass", v, t)
    for args in (("Kpp-1", "Main", 3), ("", "Main", 3), ("Kpp_1", "MAF", 3), ("Kpp_1", "Main", 0),
                 ("Kpp_1", "Main", 1000)):
        with pytest.raises(ub.UcxBuildError):
            ub.ucx_names(*args)
    assert ub.ucx_names("Kpp_1", "Main", 999)[-1] == "UCX_SM_Kpp_1_Main_999"


def test_bad_cell_fails_closed():
    v, t = courtyard_building()
    for cell in (0.0, -1.0, float("nan"), float("inf"), 0.008):
        with pytest.raises(ub.UcxBuildError):
            ub.build_main(v, t, cell=cell)


DRIVER = __import__("pathlib").Path(__file__).resolve().parents[1] / "tools" / "blender" / "ucx_build.py"


def _drive(*args):
    import subprocess
    import sys

    return subprocess.run([sys.executable, str(DRIVER), "--", *map(str, args)], capture_output=True, text=True,
                          timeout=120)


@pytest.mark.parametrize("case", ["same", "case_dotdot", "hardlink", "report_alias", "not_fbx", "no_target",
                                  "bad_opt", "missing_input"])
def test_driver_refuses_before_any_write(tmp_path, case):
    """The driver refuses (exit 4) before bpy is imported: nothing is written, the source is unchanged."""
    import os

    src = tmp_path / "SM_X_1.fbx"
    src.write_bytes(b"fbx-bytes")
    out, extra = tmp_path / "new.fbx", ["Main"]
    if case == "same":
        out = src
    elif case == "case_dotdot":
        out = tmp_path / "sub" / ".." / "SM_X_1.FBX" if os.name == "nt" else tmp_path / "sub" / ".." / "SM_X_1.fbx"
        (tmp_path / "sub").mkdir()
    elif case == "hardlink":
        out = tmp_path / "link.fbx"
        os.link(src, out)
    elif case == "report_alias":  # the JSON report next to the output would be the source
        src2 = tmp_path / "o.fbx.ucx_build.json"
        src2.write_bytes(b"fbx-bytes")
        src, out = src2, tmp_path / "o.fbx"
    elif case == "not_fbx":
        out = tmp_path / "new.blend"
    elif case == "no_target":
        extra = ["Glass"]
    elif case == "bad_opt":
        extra = ["Main", "cell=abc"]
    else:
        src = tmp_path / "absent.fbx"
    before = sorted(p.name for p in tmp_path.rglob("*"))
    r = _drive(src, out, *extra)
    assert r.returncode == 4, (r.returncode, r.stderr)
    assert "UCX_BUILD refused" in r.stderr
    assert sorted(p.name for p in tmp_path.rglob("*")) == before
    if src.exists():
        assert src.read_bytes() == b"fbx-bytes"


# --- review round 1 (PR #307): Ground footprint coverage, driver selection, target-scoped replacement ---

def plan_mesh(xs, ys, keep, z=lambda x, y: 0.0 * x):
    """Flat/heightfield mesh on the rectilinear grid xs x ys; cell (i, j) kept when keep(cx, cy).
    Only referenced vertices are returned (no stray vertex inside a hole)."""
    vid, v, t = {}, [], []

    def idx(i, j):
        if (i, j) not in vid:
            vid[(i, j)] = len(v)
            v.append((xs[i], ys[j], float(z(xs[i], ys[j]))))
        return vid[(i, j)]

    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            if keep((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2):
                a, b, c, d = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
                t += [(a, b, c), (a, c, d)]
    return np.array(v, float), np.array(t)


def footprint_uncovered(v, t, res, n=24):
    """Dense plan grid over every piece top -> points the surface does not cover (diagnostic witness)."""
    hf = ub.HeightField(v, t)
    out = []
    for pc in res.pieces:
        lo, hi = pc.verts[:, :2].min(axis=0), pc.verts[:, :2].max(axis=0)
        g = (np.arange(n) + 0.5) / n
        gx, gy = np.meshgrid(lo[0] + g * (hi[0] - lo[0]), lo[1] + g * (hi[1] - lo[1]))
        q = np.stack([gx.ravel(), gy.ravel()], axis=1)
        out.append(q[~np.isfinite(hf.z(q))])
    return np.concatenate(out) if out else np.zeros((0, 2))


@pytest.mark.parametrize("w", [2.0, 4.0, 6.0])
@pytest.mark.parametrize("cell", [8.0, 3.0])
def test_ground_ring_hole_never_filled(w, cell):
    """Reviewer witness: 8 x 8 m ring with a central w x w hole, cell=8 -> no piece over the hole."""
    a, b = 4 - w / 2, 4 + w / 2
    xs = sorted({0.0, 8.0, a, b} | {float(k) for k in range(9)})
    v, t = plan_mesh(xs, xs, lambda x, y: not (a < x < b and a < y < b))
    res = ub.build_ground(v, t, cell=cell)
    assert_valid_pieces(res)
    assert len(footprint_uncovered(v, t, res)) == 0
    for pc in res.pieces:  # hole centre lies under no piece
        lo, hi = pc.verts[:, :2].min(axis=0), pc.verts[:, :2].max(axis=0)
        assert not (lo[0] < 4 < hi[0] and lo[1] < 4 < hi[1])
    assert res.footprint_overhang_bound_m == 0.0 and res.within_tol


def test_ground_unaligned_rectilinear_hole_exact():
    """Hole edges and corners off the quadtree grid: split at the boundary vertices -> exact footprint."""
    xs = [0.0, 1.0, 2.3, 5.7, 7.0, 8.0]
    v, t = plan_mesh(xs, xs, lambda x, y: not (2.3 < x < 5.7 and 2.3 < y < 5.7))
    res = ub.build_ground(v, t, cell=8.0)
    assert_valid_pieces(res)
    assert len(footprint_uncovered(v, t, res)) == 0
    assert res.footprint_overhang_bound_m == 0.0 and res.within_tol
    pts = ub.sample_surface(v, t, 0.25)
    assert np.isfinite(ub.ground_deviation(pts, res)).all(), "every surface point lies over a piece"


def test_ground_rectangle_control_exact():
    """Rectangle 7.3 x 5.1 m (not a multiple of the cell): fitted grid, no overhang, within tol."""
    v, t = plan_mesh(np.linspace(0, 7.3, 8), np.linspace(0, 5.1, 6), lambda x, y: True,
                     z=lambda x, y: 0.05 * x)
    res = ub.build_ground(v, t, cell=4.0)
    assert_valid_pieces(res)
    assert len(footprint_uncovered(v, t, res)) == 0
    assert res.footprint_overhang_bound_m == 0.0 and res.within_tol
    area = sum(float(np.prod(p.verts[:, :2].max(axis=0) - p.verts[:, :2].min(axis=0))) for p in res.pieces)
    assert 7.3 * 5.1 * 0.97 < area <= 7.3 * 5.1


def test_ground_l_shaped_site_exact():
    xs = [0.0, 3.1, 6.2, 9.0]
    v, t = plan_mesh(xs, xs, lambda x, y: not (x > 3.1 and y > 3.1))
    res = ub.build_ground(v, t, cell=16.0)
    assert_valid_pieces(res)
    assert len(footprint_uncovered(v, t, res)) == 0 and res.within_tol


def test_ground_diagonal_perimeter_one_sided_tolerance():
    """[D134] SYNTHETIC diagonal perimeter: reverse overhang is diagnostic, not an R11 failure."""
    v = np.array([(0, 0, 0), (10, 0, 0), (0, 10, 0)], float)
    t = np.array([(0, 1, 2)])
    res = ub.build_ground(v, t, cell=8.0, min_cell=0.5, tol=0.08)
    assert_valid_pieces(res)
    unc = footprint_uncovered(v, t, res)
    assert len(unc) > 0
    measured = float(((unc[:, 0] + unc[:, 1] - 10) / math.sqrt(2)).max())  # plan distance to the hypotenuse
    assert res.footprint_overhang_bound_m >= measured - 1e-9
    assert res.footprint_overhang_bound_m > 0.08
    pts = ub.sample_surface(v, t, 0.1)
    assert ub.ground_deviation(pts, res).max() <= 0.08
    assert res.within_tol  # model -> UCX passes even though the reverse bound exceeds R11


def test_ground_random_rectilinear_holes_probe():
    """Probe: 12 seeded random rectilinear sites with two holes each (edges off the grid) -> pieces valid,
    no piece point over a hole, no overhang, every surface point under a piece."""
    rng = np.random.default_rng(1661)
    for _ in range(12):
        holes = [tuple(sorted(np.round(rng.uniform(0.5, 11.5, 2), 2))) + tuple(sorted(np.round(rng.uniform(0.5, 11.5, 2), 2)))
                 for _ in range(2)]
        xs = sorted({0.0, 12.0, *(h[k] for h in holes for k in (0, 1))} | {float(k) for k in range(0, 13, 3)})
        ys = sorted({0.0, 12.0, *(h[k] for h in holes for k in (2, 3))} | {float(k) for k in range(0, 13, 3)})
        keep = lambda x, y, hs=holes: not any(h[0] < x < h[1] and h[2] < y < h[3] for h in hs)  # noqa: E731
        v, t = plan_mesh(xs, ys, keep, z=lambda x, y: 0.02 * x + 0.01 * y)
        res = ub.build_ground(v, t, cell=6.0, min_cell=0.5)
        assert_valid_pieces(res)
        assert len(footprint_uncovered(v, t, res)) == 0
        assert res.footprint_overhang_bound_m == 0.0 and res.within_tol
        pts = ub.sample_surface(v, t, 0.3)
        assert np.isfinite(ub.ground_deviation(pts, res)).all()


def test_select_inputs_with_any_order():
    names = ["SM_X_Glass2", "SM_X_MainGlass", "SM_X_Main", "SM_X_Ground"]
    for perm in (names, names[::-1], names[1:] + names[:1]):
        main, extra, addr = ub.select_inputs(perm, "Main", with_=["SM_X_MainGlass"])
        assert (main, extra, addr) == ("SM_X_Main", ["SM_X_MainGlass"], "X")
        main, extra, _ = ub.select_inputs(perm, "Main", with_=["SM_X_Glass2", "SM_X_MainGlass"])
        assert extra == ["SM_X_Glass2", "SM_X_MainGlass"]


@pytest.mark.parametrize("with_", [["SM_X_MainGlas"], ["SM_X_MainGlass", "Nope"], ["SM_X_Main"],
                                   ["SM_X_MainGlass", "SM_X_MainGlass"], [""], ["UCX_SM_X_Main_001"]])
def test_select_inputs_bad_extra_fails(with_):
    with pytest.raises(ub.UcxBuildError):
        ub.select_inputs(["SM_X_Main", "SM_X_MainGlass"], "Main", with_=with_)


def test_select_inputs_target_object_rules():
    with pytest.raises(ub.UcxBuildError):
        ub.select_inputs(["SM_X_Glass"], "Main")
    with pytest.raises(ub.UcxBuildError):
        ub.select_inputs(["SM_X_Main", "SM_Y_Main"], "Main")
    with pytest.raises(ub.UcxBuildError):
        ub.select_inputs(["SM_X_Main"], "Main", object="SM_Z_Main")
    assert ub.select_inputs(["SM_X_Main", "SM_X_Ground"], "Ground")[:2] == ("SM_X_Ground", [])


@pytest.mark.parametrize("target,with_", [("Main", []), ("Main", ["SM_X_MainGlass"]), ("Ground", [])])
def test_ucx_replace_plan_scoped_to_inputs(target, with_):
    model = ["SM_X_Main", "SM_X_MainGlass", "SM_X_Ground"]
    ucx = ["UCX_SM_X_Main_001", "UCX_SM_X_Main_002", "UCX_SM_X_Ground_001", "UCX_SM_X_MainGlass_001"]
    for perm in (ucx, ucx[::-1]):
        main, extra, _ = ub.select_inputs(model, target, with_=with_)
        replace, keep = ub.ucx_replace_plan(perm, [main] + extra, model)
        owners = {main, *extra}
        assert sorted(replace) == sorted(u for u in ucx if u[4:-4] in owners)
        assert sorted(keep) == sorted(u for u in ucx if u[4:-4] not in owners)
    if target == "Main":
        assert "UCX_SM_X_Ground_001" in keep
    else:
        assert keep and "UCX_SM_X_Ground_001" not in keep


@pytest.mark.parametrize("bad", ["UCX_box", "UCX_SM_Y_Main_001", "UCX_SM_X_Main_01", "ucx_SM_X_Main_001x"])
def test_ucx_replace_plan_refuses_orphans(bad):
    with pytest.raises(ub.UcxBuildError):
        ub.ucx_replace_plan(["UCX_SM_X_Main_001", bad], ["SM_X_Main"], ["SM_X_Main", "SM_X_Ground"])


def test_driver_parse_with_once():
    import importlib.util

    spec = importlib.util.spec_from_file_location("ucx_build_driver", DRIVER)
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    opts, err = drv._parse(["a.fbx", "b.fbx", "Main", "with=SM_X_MainGlass,SM_X_G2", "cell=0.5"])
    assert err is None and opts["with"] == ["SM_X_MainGlass", "SM_X_G2"] and opts["cell"] == 0.5
    for bad in ("with=", "with=A,,B", "with=A", "object="):
        opts, err = drv._parse(["a.fbx", "b.fbx", "Main", bad, bad]) if bad == "with=A" else \
            drv._parse(["a.fbx", "b.fbx", "Main", bad])
        assert err, bad


# --- review round 2: kept UCX triangles count against the whole-file [D012] budget -------------------

def two_cubes():
    """SYNTHETIC Main: two 1 m cubes 20 m apart -> exactly two boxes (24 tris) at any tried cell."""
    return union(box_mesh((0, 0, 0), (1, 1, 1)), box_mesh((20, 0, 0), (21, 1, 1)))


@pytest.mark.parametrize("reserved,ok", [(2508, False), (2487, False), (2486, True), (2485, True), (0, True)])
def test_main_reserved_triangles_enforce_file_budget(reserved, ok):
    """Reviewer input: 50 200 model tris -> limit 2510; kept Ground+Main UCX 2508 leave no room for 24."""
    v, t = two_cubes()
    assert ub.ucx_triangle_limit(50200) == 2510
    if not ok:
        with pytest.raises(ub.UcxBuildError, match="budget"):
            ub.build_main(v, t, model_triangles=50200, reserved_triangles=reserved)
        return
    res = ub.build_main(v, t, model_triangles=50200, reserved_triangles=reserved)
    assert res.triangles == 24 and reserved + res.triangles <= 2510
    assert res.reserved_triangles == reserved and res.budget == 2510 - reserved


def test_ground_reserved_triangles_enforce_file_budget():
    v, t = terrain()
    free = ub.build_ground(v, t, model_triangles=50200)
    need = free.triangles
    at = ub.build_ground(v, t, model_triangles=50200, reserved_triangles=2510 - need)
    assert at.triangles == need and at.budget == need
    with pytest.raises(ub.UcxBuildError, match="budget"):
        ub.build_ground(v, t, model_triangles=50200, reserved_triangles=2510 - need + 1)


@pytest.mark.parametrize("bad", [-1, 1.5, float("nan"), float("inf"), True, None, "12"])
def test_reserved_triangles_bad_values_fail_closed(bad):
    v, t = two_cubes()
    with pytest.raises(ub.UcxBuildError):
        ub.build("Main", v, t, reserved_triangles=bad)


@pytest.mark.parametrize("model,kept,avail", [(50200, 0, 2510), (50200, 2498, 12), (100, 14988, 12),
                                              (2000000, 99988, 12)])
def test_file_budget_available(model, kept, avail):
    assert ub.file_budget_available(model, kept) == avail


@pytest.mark.parametrize("model,kept", [(50200, 2499), (50200, 2510), (50200, 2511), (100, 15001)])
def test_file_budget_no_room_fails_closed(model, kept):
    with pytest.raises(ub.UcxBuildError, match="budget"):
        ub.file_budget_available(model, kept)


@pytest.mark.parametrize("model,total,ok", [(50200, 2510, True), (50200, 2511, False), (100, 15000, True),
                                            (100, 15001, False), (50200, 0, True)])
def test_check_file_budget(model, total, ok):
    if ok:
        ub.check_file_budget(model, total)
    else:
        with pytest.raises(ub.UcxBuildError, match="budget"):
            ub.check_file_budget(model, total)


@pytest.mark.parametrize("target", ["Main", "Ground"])
@pytest.mark.parametrize("order", [1, -1])
def test_scoped_replace_with_budget_combined(target, order):
    """Reviewer scene: 208 kept Ground boxes + 1 Main box; a Main rebuild may not discard Ground UCX
    and must fail on budget; a Ground rebuild keeps the Main box and reserves its 12 tris."""
    model = ["SM_X_Main", "SM_X_MainGlass", "SM_X_Ground"][::order]
    ucx = ([f"UCX_SM_X_Ground_{i:03d}" for i in range(1, 209)] + ["UCX_SM_X_Main_001"])[::order]
    main, extra, _ = ub.select_inputs(model, target, with_=["SM_X_MainGlass"] if target == "Main" else None)
    replace, keep = ub.ucx_replace_plan(ucx, [main] + extra, model)
    kept_tris = 12 * len(keep)
    if target == "Main":
        assert len(keep) == 208 and replace == ["UCX_SM_X_Main_001"]
        v, t = two_cubes()
        assert ub.file_budget_available(50200, kept_tris) == 14
        with pytest.raises(ub.UcxBuildError, match="budget"):
            ub.build("Main", v, t, model_triangles=50200, reserved_triangles=kept_tris)
    else:
        assert keep == ["UCX_SM_X_Main_001"] and len(replace) == 208
        v, t = terrain()
        res = ub.build("Ground", v, t, model_triangles=50200, reserved_triangles=kept_tris)
        ub.check_file_budget(50200, kept_tris + res.triangles)


@pytest.mark.parametrize("field", ["max_vertical_dev_m", "uncovered_strip_m", "tol_m"])
@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -float("inf"), -0.01])
def test_ground_one_sided_missing_nonfinite_measurements_fail_closed(field, bad):
    """[D134] Removing the reverse gate must not turn missing/invalid forward evidence into a pass."""
    res = ub.UcxResult("Ground", [], 1.0, 0.004, max_vertical_dev_m=0.0,
                       uncovered_strip_m=0.0, tol_m=0.08, footprint_overhang_bound_m=10.0)
    setattr(res, field, bad)
    assert not res.within_tol


@pytest.mark.parametrize("scale,offset", [(1.0, 0.0), (1.2, 23.0), (0.8, -19.0),
                                        (1.1, 100.0), (0.9, -100.0), (1.3, 1.5)])
def test_one_sided_ground_generated_perimeters_probe(scale, offset):
    """[D134] SYNTHETIC translated/scaled diagonal sites: forward R11 passes; reverse bound > R11."""
    v = np.array([(0, 0, 0), (10, 0, 0), (0, 10, 0)], float)
    v[:, :2] = scale * v[:, :2] + offset
    t = np.array([(0, 1, 2)])
    res = ub.build("Ground", v, t, cell=8.0, min_cell=0.5, tol=0.08,
                   model_triangles=50200, reserved_triangles=12)
    assert_valid_pieces(res)
    assert res.footprint_overhang_bound_m > ub.GROUND_TOL_M
    assert ub.ground_deviation(ub.sample_surface(v, t, 0.15), res).max() < 0.08
    assert res.within_tol
    ub.check_file_budget(50200, res.triangles + 12)


