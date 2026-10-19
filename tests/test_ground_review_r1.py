"""Regression table of PR #308 review round 1 (#295): every failing input of the review and its expected output.

| # | failing input (review round 1, head c9ab292)                       | expected output                                    |
|---|---------------------------------------------------------------------|----------------------------------------------------|
| 1 | steep TIN break narrower than the 1 mm snap (real: faces 448/767/1346/1347/2352, max 27.652 mm) | every face <= 10 mm, or RuntimeError (never returned) |
| 2 | covering outlines < 1 mm apart: snap spike / dropped sliver (real: Mulch 3575-3579 0.478 m, LawnRolled 2 faces 0.15 m) | every face inside its covering + chord + snap + 1 mm |
| 3 | VPM cell UV side 1.25 + per-face scaling (real: 17 049 / 33 023 straddling) | 0 straddling, tiles [1001], shared edges same texel, steep faces >= 520 px/m and not mirrored |
| 4 | adapter JSON named <out>/ground_master_vpm.json (exit 0, input overwritten) | exit 2 before any write, input hash unchanged      |
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon, box, mapping

from dt_ai.geometry import ground_cake as gc

ROOT = Path(__file__).resolve().parents[1]


def _bg():
    spec = importlib.util.spec_from_file_location("build_ground_vatutino", ROOT / "jobs/VATUTINO-SITE/build_ground.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_ground_vatutino"] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ 1 relief: steep break under the snap


def wall_tin(x1=10.0, x2=10.001, dz=1.0, lean=0.37):
    """Two plateaus joined by a near-vertical wall ``x2 - x1`` wide, leaning in plan (x grows with ``lean * y``): the
    4 m grid line y = 4 crosses the wall between millimetre nodes, so the 1 mm snap moves that crossing across it."""
    pts = []
    for y in (-1.0, 4.3, 10.0):
        pts += [(-1.0, y, 100.0), (x1 + lean * y, y, 100.0), (x2 + lean * y, y, 100.0 + dz), (25.0, y, 100.0 + dz)]
    return gc.build_tin(pts)


def wall_plan():
    return gc.plan_layers(box(0, 0, 20, 8), {"tile": [box(0, 0, 20, 8)]}, "tile", {"tile": "Tile"})


def test_r1_steep_break_under_snap_within_tol():
    plan = wall_plan()
    s = gc.ReliefSampler(wall_tin())
    flat = gc.build_flat(plan, cell=4.0, chord=0.0, sampler=s, tol=0.01, snap=0.001)
    proj, misses = gc.project_z(flat, s, plan.step)
    assert misses == []
    err = gc.measure_relief_error(proj, s, plan.step, tol=0.01)
    assert err["faces_over_tol"] == 0 and err["max_mm"] <= 10.0
    assert flat.report["relief_refine_points_inserted"] > 0
    # still watertight after the edge splits (no T-junction / crack)
    assert gc.measure_open_edges(flat, plan, eps=0.001)["open_edges_off_outline"] == 0


def test_r1_refinement_fail_closed_when_stuck():
    """A point that rounds onto an existing vertex cannot be inserted: raise, never return failed geometry."""
    V = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    T = [[0, 1, 2]]

    def ev(V, T, ids):
        return np.ones(len(ids)), np.array([[0.0, 0.0]] * len(ids))
    with pytest.raises(RuntimeError, match="stuck"):
        gc._insert_points(V, T, ev, "witness")


def test_r1_edge_split_keeps_neighbours_conforming():
    V = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    T = [[0, 1, 2], [0, 2, 3]]
    hit = {"done": False}

    def ev(V, T, ids):  # one bad triangle whose worst point lies on the shared diagonal
        sc = np.zeros(len(ids))
        if not hit["done"] and 0 in ids:
            sc[ids.index(0)] = 1.0
            hit["done"] = True
        return sc, np.array([[1.0, 1.0]] * len(ids))
    V2, T2, rep = gc._insert_points(V, T, ev, "witness")
    assert rep["points_inserted"] == 1 and len(T2) == 4
    edges = {}
    for a, b, c in T2:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(min(u, v), max(u, v))] = edges.get((min(u, v), max(u, v)), 0) + 1
    assert sorted(edges.values()).count(2) == 4  # 4 interior edges shared by exactly two triangles
    P = np.array(V2)[np.array(T2)]
    area = 0.5 * ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 1, 1] - P[:, 0, 1]) * (P[:, 2, 0] - P[:, 0, 0]))
    assert (area > 0).all() and area.sum() == pytest.approx(4.0)


# ------------------------------------------------------------------ 2 containment: outlines closer than the snap


def near_coincident_site(seed: int):
    """Base tile + strips whose shared outlines are offset by 0.05-0.9 mm and tilted by < 1 mm over 6 m."""
    rnd = random.Random(seed)
    cov = {"tile": [box(0, 0, 24, 12)], "mulch": [], "red": [], "lawn": []}
    x = 1.0
    for k in range(6):
        w = rnd.uniform(0.4, 2.5)
        off = rnd.uniform(0.00005, 0.0009)
        tilt = rnd.uniform(-0.0009, 0.0009)
        y0, y1 = rnd.uniform(0.5, 3.0), rnd.uniform(8.0, 11.5)
        a = Polygon([(x, y0), (x + w, y0), (x + w + tilt, y1), (x, y1)])
        b = Polygon([(x + w + off, y0 + 0.3), (x + w + off + 1.0, y0 + 0.3), (x + w + off + 1.0, y1 - 0.4),
                     (x + w + off + tilt, y1 - 0.4)])
        # a narrow tail (< 1 mm wide) of the first strip running along the neighbour
        tail = Polygon([(x + w, y1), (x + w + 0.0006, y1), (x + w + 0.0006, y1 + 0.35), (x + w, y1 + 0.35)])
        cov[["mulch", "red", "lawn"][k % 3]].append(a.union(tail))
        cov[["red", "lawn", "mulch"][k % 3]].append(b)
        x += w + 1.0 + off + 0.7
    return box(0, 0, 24, 12), cov


@pytest.mark.parametrize("seed", [93, 138, 272, 47, 180, 0])  # 93/138/272 fail at c9ab292; 47/180 broke drafts
def test_r1_faces_inside_contour_with_sub_snap_outlines(seed):
    b, cov = near_coincident_site(seed)
    slots = {"tile": "Tile", "mulch": "Mulch", "red": "TileRed", "lawn": "Lawn"}
    plan = gc.plan_layers(b, cov, "tile", slots)
    s = gc.ReliefSampler(gc.build_tin([(-1, -1, 10), (30, -1, 10.5), (-1, 20, 11), (30, 20, 10.2)]))
    flat = gc.build_flat(plan, cell=4.0, chord=0.02, sampler=s, tol=0.01, snap=0.001)
    ins = gc.measure_inside(flat, plan, tol=0.02 + 0.001 + 1e-3)
    assert ins["outside"] == 0, ins


def test_r1_outline_recovery_splits_crossing_triangle():
    V = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    T = [[0, 1, 2], [0, 2, 3]]
    region = box(0, 0, 1.3, 4)  # outline x = 1.3 crosses both triangles
    V2, T2, rep = gc._recover_outlines(V, T, [region], snap=0.001)
    assert rep["points_inserted"] >= 2
    tri = shapely.polygons(np.array(V2)[np.array(T2)])
    inside = shapely.contains(region, shapely.centroid(tri))
    assert shapely.within(tri[inside], region.buffer(0.002)).all()
    assert not shapely.intersects(tri[~inside], region.buffer(-0.002)).any()
    assert shapely.area(tri).sum() == pytest.approx(16.0)


# ------------------------------------------------------------------ 3 VPM UV: UDIM containment and continuity


def _profile_uv(master, prof):
    return _bg().profile_uv(master, prof)


def _master(tin, plan):
    s = gc.ReliefSampler(tin)
    flat = gc.build_flat(plan, cell=4.0, chord=0.0, sampler=s, tol=0.01, snap=0.001)
    proj, _ = gc.project_z(flat, s, plan.step)
    return gc.add_skirt(proj, 1.0)


def test_r1_vpm_flat_cell_one_tile_continuous():
    plan = gc.plan_layers(box(0, 0, 8, 8), {"tile": [box(0, 0, 8, 8)]}, "tile", {"tile": "Tile"})
    m = _master(gc.build_tin([(-1, -1, 5), (9, -1, 5), (-1, 9, 5), (9, 9, 5)]), plan)
    uv, lay = _profile_uv(m, "vpm")
    surf = m.level >= 0
    t = gc.uv_tile_report(uv[surf])
    assert t["straddling"] == 0 and t["tiles"] == [1001]
    d = gc.texel_density(m.verts, m.faces[surf], uv[surf], 4096)
    assert np.allclose(d, 1024.0)
    # shared edges: same texel of the tiling texture (UV equal modulo 1) on both sides of every edge
    F, U = m.faces[surf], uv[surf]
    seen = {}
    for f, u in zip(F, U):
        for k in range(3):
            a, b = f[k], f[(k + 1) % 3]
            key = (min(a, b), max(a, b))
            pair = {a: u[k], b: u[(k + 1) % 3]}
            if key in seen:
                for v in (a, b):
                    dd = (pair[v] - seen[key][v]) % 1.0
                    assert np.all(np.minimum(dd, 1 - dd) < 1e-9)
            else:
                seen[key] = pair


def test_r1_vpm_steep_faces_in_band_contained_not_mirrored():
    plan = wall_plan()
    m = _master(wall_tin(x1=10.0, x2=10.2, dz=1.5, lean=0.0), plan)  # 82 deg slope: top-down density ~ 370 px/m
    uv0 = m.uv
    surf = m.level >= 0
    d0 = gc.texel_density(m.verts, m.faces[surf], uv0[surf], 4096)
    assert (d0 < 520).any()  # the witness really is steep
    uv, lay = _profile_uv(m, "vpm")
    d = gc.texel_density(m.verts, m.faces[surf], uv[surf], 4096)
    assert d.min() >= 520 and lay["side_projected_faces"] == int((d0 < 520).sum())
    t = gc.uv_tile_report(uv[surf])
    assert t["straddling"] == 0 and t["outside_udim_range"] == 0 and t["tiles"] == [1001]
    U = uv[surf]
    e1, e2 = U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]
    assert ((e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) > 0).all()  # no mirrored island
    uvn, _ = _profile_uv(m, "npm")
    dn = gc.texel_density(m.verts, m.faces[surf], uvn[surf], 2048)
    assert dn.min() >= 10 and dn.max() <= 40


# ------------------------------------------------------------------ 4 output alias


def _adapter_json():
    b = box(0, 0, 8, 8)
    return {"boundary": mapping(b), "coverings": {"tile_light": {"geometry": mapping(shapely.MultiPolygon([b]))}},
            "base_covering": "tile_light",
            "elevations": [{"x": x, "y": y, "z": 100.0 + 0.01 * x, "source": "point"}
                           for x in (-1, 9) for y in (-1, 9)]}


@pytest.mark.parametrize("name", ["ground_master_vpm.json", "ground_master_npm.json", "ground_report.json"])
def test_r1_alias_input_refused_unchanged(tmp_path, name):
    out = tmp_path / "out"
    out.mkdir()
    src = out / name
    src.write_text(json.dumps(_adapter_json()), encoding="utf-8")
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    assert _bg().main([str(src), "--out", str(out)]) == 2
    assert hashlib.sha256(src.read_bytes()).hexdigest() == h
    assert sorted(p.name for p in out.iterdir()) == [name]


def test_r1_alias_out_is_input_and_dotted_path(tmp_path):
    src = tmp_path / "a.json"
    src.write_text(json.dumps(_adapter_json()), encoding="utf-8")
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    bg = _bg()
    assert bg.main([str(src), "--out", str(src)]) == 2
    (tmp_path / "o").mkdir()
    dotted = tmp_path / "o" / ".." / "o"
    (tmp_path / "o" / "ground_master_vpm.json").write_text("{}", encoding="utf-8")
    assert bg.main([str(tmp_path / "o" / "ground_master_vpm.json"), "--out", str(dotted)]) == 2
    assert hashlib.sha256(src.read_bytes()).hexdigest() == h


def test_r1_control_build_writes_and_passes_gates(tmp_path):
    src = tmp_path / "a.json"
    src.write_text(json.dumps(_adapter_json()), encoding="utf-8")
    out = tmp_path / "out"
    assert _bg().main([str(src), "--out", str(out)]) == 0
    rep = json.loads((out / "ground_report.json").read_text(encoding="utf-8"))
    assert all(g["pass"] for g in rep["gates"].values())
    assert (out / "ground_master_vpm.json").exists() and (out / "ground_master_npm.json").exists()
