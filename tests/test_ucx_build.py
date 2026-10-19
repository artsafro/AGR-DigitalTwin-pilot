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
