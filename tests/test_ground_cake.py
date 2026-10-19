"""Synthetic tests of the Ground layered cake (#295): layer step, coverage, Z-only projection, density."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest
from shapely.geometry import Point, Polygon, box

from dt_ai.geometry import ground_cake as gc

SLOTS = {"tile": "Tile", "lawn": "Lawn", "mulch": "Mulch", "bed1": "Bed", "bed2": "Bed"}


def site():
    boundary = box(0, 0, 40, 30)
    cov = {
        "tile": [box(0, 0, 40, 30).difference(box(25, 15, 38, 28))],  # footprint hole 13 x 13 uncovered
        "lawn": [Point(10, 10).buffer(5)],
        "mulch": [box(8, 8, 20, 12)],  # lies partly on the lawn -> level 2 there
        "bed1": [box(30, 2, 32, 4)],
        "bed2": [box(33, 2, 35, 4)],
    }
    return boundary, cov


def plane_tin(a=0.05, b=-0.02, c=100.0, extent=(-5, -5, 50, 40)):
    x0, y0, x1, y1 = extent
    pts = [(x, y, a * x + b * y + c) for x in (x0, x1) for y in (y0, y1)]
    pts += [((x0 + x1) / 2, (y0 + y1) / 2, a * (x0 + x1) / 2 + b * (y0 + y1) / 2 + c)]
    return gc.build_tin(pts)


def test_plan_holes_levels_and_shared_slots():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    assert plan.report["holes_m2"] == [169.0]
    assert plan.surface.area == pytest.approx(1200 - 169)
    lv = {(l.slot, l.level) for l in plan.layers}
    assert ("Tile", 0) in lv and ("Lawn", 1) in lv and ("Mulch", 2) in lv and ("Mulch", 1) in lv
    assert [l.slot for l in plan.layers].count("Bed") == 1  # two bed types share one slot


def test_plan_fail_closed():
    b, cov = site()
    with pytest.raises(ValueError):
        gc.plan_layers(None, cov, "tile", SLOTS)
    with pytest.raises(ValueError):
        gc.plan_layers(b, cov, "nope", SLOTS)
    with pytest.raises(ValueError):
        gc.plan_layers(b, cov, "tile", SLOTS, step=float("nan"))


def test_flat_cake_steps_coverage_inside_uv():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    m = gc.build_flat(plan, cell=4.0, chord=0.02)
    for slot, lev in zip(m.slot, m.level):
        pass
    z_by_face = m.verts[m.faces][:, :, 2]
    assert np.allclose(z_by_face, (m.level * 0.006)[:, None])
    cov_r = gc.measure_coverage(m, plan)
    assert cov_r["coverage_pct"] == pytest.approx(100.0, abs=1e-6)
    ins = gc.measure_inside(m, plan, tol=0.02)
    assert ins["outside"] == 0 and ins["faces"] == len(m.faces)
    assert m.uv.min() >= -1e-9 and m.uv.max() <= 1 + 1e-9  # stacked tiling: one cell = unit square
    # every face lies inside one grid cell
    lo = np.floor((m.verts[m.faces][:, :, :2].min(axis=1) - m.report["origin"]) / 4.0 + 1e-9)
    hi = np.floor((m.verts[m.faces][:, :, :2].max(axis=1) - m.report["origin"]) / 4.0 - 1e-9)
    assert (lo == hi).all()


def test_flat_rejects_bad_cell():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    for cell in (0, -4, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            gc.build_flat(plan, cell=cell)


def test_tin_passes_through_points_and_flags_contradictory():
    pts = [(0, 0, 1.0), (10, 0, 2.0), (0, 10, 3.0), (10, 10, 4.0), (5, 5, 9.0), (5, 5, 9.0005), (2, 2, 1.0),
           (2, 2, 1.5)]
    tin = gc.build_tin(pts)
    assert tin.contradictory == [(2.0, 2.0, [1.0, 1.5])]
    assert tin.merged == 1
    s = gc.ReliefSampler(tin)
    z, hit = s.sample(tin.pts[:, :2])
    assert hit.all() and np.max(np.abs(z - tin.pts[:, 2])) < 1e-3


def test_tin_fail_closed():
    with pytest.raises(ValueError):
        gc.build_tin([(0, 0, 1), (1, 1, 2)])
    with pytest.raises(ValueError):
        gc.build_tin([(0, 0, 1), (1, 1, 2), (2, 2, 3)])  # collinear
    with pytest.raises(ValueError):
        gc.build_tin([(0, 0, 1), (1, 0, float("nan")), (0, 1, 3)])


def test_projection_z_only_keeps_xy_uv_material_and_steps():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    flat = gc.build_flat(plan, cell=4.0)
    s = gc.ReliefSampler(plane_tin())
    proj, misses = gc.project_z(flat, s, 0.006)
    assert misses == []
    assert np.array_equal(proj.verts[:, :2], flat.verts[:, :2])
    assert np.array_equal(proj.uv, flat.uv) and proj.slot == flat.slot
    st = gc.measure_steps(proj, s, 0.006)
    assert st["vertex_max_mm"] < 1e-6 and st["centre_max_mm"] < 1e-6 and st["misses"] == 0  # planar relief


def test_projection_misses_listed_not_moved():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    flat = gc.build_flat(plan, cell=4.0)
    s = gc.ReliefSampler(plane_tin(extent=(-5, -5, 20, 40)))  # covers only x <= 20
    proj, misses = gc.project_z(flat, s, 0.006)
    assert misses and all(flat.verts[i, 0] > 20 for i in misses)
    assert np.array_equal(proj.verts[misses], flat.verts[misses])


def test_random_relief_vertices_exact_and_centres_reported():
    rnd = random.Random(295)
    pts = [(rnd.uniform(-5, 45), rnd.uniform(-5, 35), rnd.uniform(140, 150)) for _ in range(60)]
    pts += [(-5, -5, 141), (45, -5, 142), (-5, 35, 143), (45, 35, 144)]
    s = gc.ReliefSampler(gc.build_tin(pts))
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    proj, misses = gc.project_z(gc.build_flat(plan), s, 0.006)
    st = gc.measure_steps(proj, s, 0.006)
    assert misses == [] and st["vertex_max_mm"] < 1e-6
    assert st["centres"] == len(proj.faces)


def test_skirt_depth_outward_and_fail_closed():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    m = gc.add_skirt(gc.build_flat(plan), depth=1.0)
    sk = m.level == -1
    assert sk.sum() > 0
    p = m.verts[m.faces[sk]]
    assert p[:, :, 2].min() == pytest.approx(-1.0)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    c = p.mean(axis=1)
    # outer boundary walls face away from the plot centre... hole walls face into the hole: both away from surface
    probe = c[:, :2] + 0.01 * n[:, :2] / np.linalg.norm(n[:, :2], axis=1)[:, None]
    assert not any(plan.surface.contains(Point(*q)) for q in probe)
    assert np.allclose(n[:, 2], 0, atol=1e-9)
    for d in (0.99, float("nan")):
        with pytest.raises(ValueError):
            gc.add_skirt(gc.build_flat(plan), depth=d)


def test_texel_density_matches_uv_scale():
    verts = np.array([[0, 0, 0], [4, 0, 0], [0, 4, 0]], float)
    faces = np.array([[0, 1, 2]])
    k = gc.uv_scale_for_density(4.0, 2048, 20)
    uv = np.array([[[0, 0], [k, 0], [0, k]]])
    assert gc.texel_density(verts, faces, uv, 2048)[0] == pytest.approx(20.0)
    assert gc.texel_density(verts, faces, uv / k, 4096)[0] == pytest.approx(1024.0)
    deg = np.array([[[0, 0], [0, 0], [0, 0]]], float)
    assert math.isnan(gc.texel_density(verts, faces, deg, 2048)[0])
