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


# ---------------------------------------------------------------- relief refinement (user decision 2026-10-19 [D153])


def ridge_tin():
    """Planar everywhere except a sharp ridge band 18 <= x <= 22 (0.5 m spacing, 0.4 m high): only cells over the
    ridge need TIN cuts."""
    pts = [(x, y, 100.0) for x in (-5.0, 15.0, 25.0, 45.0) for y in (-5.0, 35.0)]
    xs = [18 + 0.5 * i for i in range(9)]
    for i, x in enumerate(xs):
        for y in [-5.0 + 2.5 * j for j in range(17)]:
            pts.append((x, y, 100.0 + (0.4 if i % 2 else 0.0)))
    return gc.build_tin(pts)


def test_max_error_exact_on_ridge():
    s = gc.ReliefSampler(ridge_tin())
    # one face spanning x 17..19 at constant relief corners 100: the ridge vertex at x = 18.5 is 0.4 m above
    tri = np.array([[[17.0, 1.0], [19.0, 1.0], [17.0, 3.0]]])
    assert s.max_error(tri)[0] == pytest.approx(0.4, abs=1e-9)
    flat = np.array([[[0.0, 0.0], [4.0, 0.0], [0.0, 4.0]]])
    assert s.max_error(flat)[0] == pytest.approx(0.0, abs=1e-12)


def test_relief_refinement_only_where_needed_and_watertight():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    s = gc.ReliefSampler(ridge_tin())
    coarse = gc.build_flat(plan, cell=4.0)
    proj0, _ = gc.project_z(coarse, s, 0.006)
    assert gc.measure_relief_error(proj0, s, 0.006)["max_mm"] > 100  # RED without refinement
    flat = gc.build_flat(plan, cell=4.0, sampler=s, tol=0.01)
    proj, misses = gc.project_z(flat, s, 0.006)
    assert misses == []
    er = gc.measure_relief_error(proj, s, 0.006)
    assert er["max_mm"] <= 10.0 and er["faces_over_tol"] == 0
    rep = flat.report
    assert rep["relief_cut_xy_cells"] > 0 and rep["relief_max_error_before_mm"] > 100
    # cut cells all touch the ridge band (x 16..24 with the 4 m grid anchored at 0)
    assert {ix for ix, _ in rep["relief_cut_xy_list"]} == {4, 5}
    # no crack: every open base edge lies on the outline; Z steps still exact at vertices
    oe = gc.measure_open_edges(flat, plan)
    assert oe["open_edges_off_outline"] == 0 and oe["non_manifold"] == 0
    assert gc.measure_steps(proj, s, 0.006)["vertex_max_mm"] < 1e-6
    cv = gc.measure_coverage(flat, plan)
    assert cv["uncovered_m2"] < 1e-4
    assert gc.measure_inside(flat, plan, tol=0.021)["outside"] == 0


def test_relief_refinement_noop_on_planar_relief():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    a = gc.build_flat(plan, cell=4.0)
    r = gc.build_flat(plan, cell=4.0, sampler=gc.ReliefSampler(plane_tin()), tol=0.01)
    assert r.report["relief_cut_xy_cells"] == 0 and len(r.faces) == len(a.faces)


def test_relief_refinement_fail_closed():
    b, cov = site()
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError):
            gc.build_flat(plan, sampler=gc.ReliefSampler(plane_tin()), tol=bad)


def test_fix_density_only_out_of_band_faces():
    verts = np.array([[0, 0, 0], [4, 0, 0], [0, 4, 0], [4, 0, 12.0], [4, 4, 0], [8, 0, 0]], float)
    faces = np.array([[0, 1, 2], [1, 5, 4]])
    verts[5, 2] = 40.0  # second face: steep, density stretched far below the band
    uv = np.array([[[0, 0], [1, 0], [0, 1]], [[1, 0], [2, 0], [2, 1]]], float) * 1.25
    d0 = gc.texel_density(verts, faces, uv, 4096)
    assert d0[0] == pytest.approx(1280) and d0[1] < 520  # RED: steep face below the VPM band
    out, fixed = gc.fix_density(verts, faces, uv, 4096, 520, 1706, 1280)
    assert list(fixed) == [1] and np.array_equal(out[0], uv[0])
    assert gc.texel_density(verts, faces, out, 4096)[1] == pytest.approx(1280)
    with pytest.raises(ValueError):
        gc.fix_density(verts, faces, uv, 4096, 520, 1706, 2000)


def test_snap_removes_sliver_edges_and_keeps_coverage_within_tol():
    # boundary with a vertex 0.2 mm off a cell line -> sub-millimetre sliver edges without snapping
    b = Polygon([(0, 0), (8.0002, 0), (8.0002, 4.0001), (12, 4.0001), (12, 8), (0, 8)])
    plan = gc.plan_layers(b, {"tile": [b]}, "tile", SLOTS, footprint_min_area=100)
    s = gc.ReliefSampler(plane_tin(extent=(-5, -5, 20, 20)))

    def shortest(m):
        P = m.verts[m.faces]
        return np.linalg.norm(P - np.roll(P, 1, axis=1), axis=2).min()
    assert shortest(gc.build_flat(plan, sampler=s, snap=1e-6)) < 1e-3  # RED: sliver edge
    m = gc.build_flat(plan, sampler=s, snap=1e-3)
    assert shortest(m) >= 1e-3 - 1e-9
    cv = gc.measure_coverage(m, plan, tol=1e-3)
    assert cv["uncovered_beyond_tol_m2"] < 1e-9 and cv["outside_surface_beyond_tol_m2"] < 1e-9
    assert gc.measure_open_edges(m, plan, eps=1e-3)["open_edges_off_outline"] == 0
    for bad in (0.0, 0.02, float("nan")):
        with pytest.raises(ValueError):
            gc.build_flat(plan, snap=bad)


@pytest.mark.parametrize("tol", [0.01, 0.5])
def test_layers_share_triangulation_gap_exact_over_bent_relief(tol):
    """With a 10 mm relief tolerance a base face may bend away from the plate above it; stacked layers must share
    one triangulation so the gap is exactly level * step everywhere (no poke-through, no z-fighting)."""
    b, cov = site()
    cov["bed1"] = [Point(20.3, 21.1).buffer(2.7)]  # a curved plate across the ridge, off the grid lines
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    s = gc.ReliefSampler(ridge_tin())
    proj, _ = gc.project_z(gc.build_flat(plan, cell=4.0, chord=0.02, sampler=s, tol=tol), s, 0.006)
    g = gc.measure_stack_gaps(proj, 0.006)
    assert g["checked"] > 0
    assert g["max_gap_error_mm"] < 1e-6 and g["same_level_overlap_m2"] < 1e-6


def steep_site():
    """Flat for x <= 20, then a 6:1 slope (|n_z| = 0.164, about 80 deg): a +6 mm vertical step gives ~1 mm normal gap.
    Lawn and beds on the slope (level 1), mulch on the sloped lawn (level 2), lawn + mulch also on the flat part."""
    b, cov = site()
    cov["lawn"] = [Point(10, 10).buffer(5), box(24, 16, 36, 24)]
    cov["mulch"] = [box(8, 8, 22, 12), box(28, 18, 32, 22)]
    pts = [(x, y, 0.0 if x <= 20 else 6.0 * (x - 20)) for x in (-5, 20, 50) for y in (-5, 40)]
    s = gc.ReliefSampler(gc.build_tin(pts))
    plan = gc.plan_layers(b, cov, "tile", SLOTS, footprint_min_area=100)
    proj, _ = gc.project_z(gc.build_flat(plan, cell=4.0, chord=0.02, sampler=s, tol=0.01), s, 0.006)
    return proj, s


def test_raise_steep_layers_clears_v004_and_keeps_flat_nominal():
    """User decision 2026-10-19 [D154]: on steep relief raise a layer locally so the normal gap is >= 5 mm (V004 band
    5-20 mm); flat ground keeps +6 / +12 mm. Failing input: the nominal stack on the 6:1 slope (pairs < 5 mm)."""
    proj, s = steep_site()
    assert gc.measure_codirectional(proj)["pairs_below"] > 0  # the defect exists on the nominal stack
    out, off, rep = gc.raise_steep_layers(proj, 0.006)
    assert gc.measure_codirectional(out)["pairs_below"] == 0
    g = gc.measure_stack_gaps(out, 0.006, offsets=off)
    assert g["normal_gap_vertices_below"] == 0 and g["normal_gap_centroids_below"] == 0
    assert g["normal_gap_vertex_min_mm"] >= 5.0 and g["max_gap_error_mm"] < 1e-6 and g["same_level_overlap_m2"] < 1e-9
    # Z only: XY, UV, slots, faces unchanged; base vertices unchanged
    assert np.array_equal(out.verts[:, :2], proj.verts[:, :2]) and np.array_equal(out.uv, proj.uv)
    assert out.slot == proj.slot and np.array_equal(out.faces, proj.faces)
    lev_v = gc._vertex_levels(proj)
    assert np.array_equal(out.verts[lev_v == 0], proj.verts[lev_v == 0])
    # flat ground (away from the slope) keeps the nominal offset exactly
    flat = (lev_v >= 1) & (proj.verts[:, 0] < 19.0)
    assert flat.any() and np.allclose(off[flat], lev_v[flat] * 0.006, atol=1e-12)
    assert rep["steep_vertices"] > 0 and rep["max_raise_mm"] > 20.0
    # the relief and offset bookkeeping stays exact
    assert gc.measure_steps(out, s, 0.006, offsets=off)["vertex_max_mm"] < 1e-6
    assert gc.measure_relief_error(out, s, 0.006, tol=0.01, offsets=off)["faces_over_tol"] == 0
    # level 2 never drops onto level 1 at a shared XY
    st = {}
    for v in np.nonzero(lev_v >= 1)[0]:
        st.setdefault((round(out.verts[v, 0], 4), round(out.verts[v, 1], 4)), {})[lev_v[v]] = off[v]
    assert all(d[2] - d[1] >= 0.0055 * 0.164 for d in st.values() if 1 in d and 2 in d)


def test_raise_steep_layers_reports_vertices_where_20mm_is_infeasible():
    """Where a vertex joins the 80 deg slope and the flat part, no continuous vertical offset gives <= 20 mm on the
    flat face and >= 5 mm on the slope: gap_min wins and the vertex is listed, never silently passed."""
    proj, _ = steep_site()
    out, off, rep = gc.raise_steep_layers(proj, 0.006)
    over = rep["over_gap_max_vertices"]
    assert over and all(abs(out.verts[v, 0] - 20.0) < 1e-6 for v in over)
    assert gc.measure_stack_gaps(out, 0.006, offsets=off)["normal_gap_vertices_above"] > 0


@pytest.mark.parametrize("kw", [{"gap_min": 0.0}, {"gap_min": float("nan")}, {"gap_max": -1.0},
                                {"gap_min": 0.02, "gap_max": 0.01}, {"step": float("inf")}])
def test_raise_steep_layers_fail_closed(kw):
    proj, s = steep_site()
    args = {"step": 0.006, **kw}
    with pytest.raises(ValueError):
        gc.raise_steep_layers(proj, args.pop("step"), **args)


def test_offsets_shape_checked():
    proj, s = steep_site()
    with pytest.raises(ValueError):
        gc.measure_steps(proj, s, 0.006, offsets=np.zeros(3))
