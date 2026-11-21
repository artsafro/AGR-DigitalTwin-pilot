"""SINTEZ 1.6.1 per-polygon parity (#1732, recurrence of #432): mirrored, collapsed, out-of-tile, density, doubles.

Pattern: n/a | new-case: regression tests of twinqa.sintez_uv (#1732).

Staropetrovskiy VPM v001-v007 (2026-11-20): SINTEZ failed single triangles inside islands our per-mesh/per-edge
checks passed. Every mesh below is a SYNTHETIC fixture, not data of a real object.
"""
import math
import random
from copy import deepcopy

import pytest

from test_scene import mesh, rb
from test_validator import PROFILES
from twinqa.geometry.topology import count_defects
from twinqa.scene import scene_findings
from twinqa.sintez_uv import (duplicate_vertex_finding, polygon_density, polygon_uv_issues, sintez_tile,
                              uv_findings)
from twinqa.uv import edge_densities

SIDE = 4096
UV_PER_M = 0.2  # 0.2 x 4096 = 819.2 px/m, inside 512..1706


def test_indexed_drift_repeat_reset_and_order():
    from twinqa.sintez_uv import indexed_uv_drift

    before = [_strip(1), _strip(2, name="second")]
    for _ in range(2):
        assert indexed_uv_drift(before, deepcopy(before[::-1])) == {
            "meshes": 2, "corners": 18, "max_uv": 0.0, "max_world_m": 0.0,
        }


def test_indexed_drift_probes_every_loop():
    from twinqa.sintez_uv import indexed_uv_drift

    before = [_strip(1)]
    for face in range(2):
        for loop in range(3):
            for axis in range(2):
                after = deepcopy(before)
                pair = after[0]["face_geometry"]["polygon_uv"][face][loop]
                pair[axis] = math.nextafter(pair[axis], math.inf)
                report = indexed_uv_drift(before, after)
                assert report["max_uv"] > 0 and report["max_world_m"] == 0


def test_indexed_drift_world_registration():
    from twinqa.sintez_uv import indexed_uv_drift

    before = [_strip(1)]
    after = deepcopy(before)
    after[0]["face_geometry"]["vertices"][0][2] = 0.001
    report = indexed_uv_drift(before, after)
    assert report["max_uv"] == 0 and report["max_world_m"] == 0.001


@pytest.mark.parametrize("case", ["empty", "duplicate", "name", "missing", "nan", "inf", "negative-index",
                                  "connectivity", "material", "quad", "unsupported"])
def test_indexed_drift_refuses_unproved_correspondence(case):
    from twinqa.sintez_uv import indexed_uv_drift

    before = [_strip(1)]
    after = deepcopy(before)
    g = after[0]["face_geometry"]
    if case == "empty":
        after.clear()
    elif case == "duplicate":
        after.append(deepcopy(after[0]))
    elif case == "name":
        after[0]["name"] = "alien"
    elif case == "missing":
        g["polygon_uv"].pop()
    elif case in {"nan", "inf"}:
        g["polygon_uv"][1][1][0] = float(case)
    elif case == "negative-index":
        g["polygons"][1][1] = -1
    elif case == "connectivity":
        g["polygons"][1].reverse()
    elif case == "material":
        g["polygon_material"][1] = "other"
    elif case == "quad":
        g["polygons"][1].append(1)
        g["polygon_uv"][1].append([0.25, 0.05])
    else:
        g["polygon_uv"][1][1] = {0.0: None, 1.0: None}
    with pytest.raises(ValueError):
        indexed_uv_drift(before, after)


def _strip(n=4, name="SM_Test_K_1_Main", material="M_Test_K_1_Main_1"):
    """SYNTHETIC 1 x n m strip of 2n triangles, one island in tile 1001 at 819.2 px/m."""
    vertices = [[float(x), float(y), 0.0] for y in (0, 1) for x in range(n + 1)]
    polygons, polygon_uv = [], []
    for x in range(n):
        a, b, c, d = x, x + 1, n + 2 + x, n + 1 + x
        for tri in ([a, b, c], [a, c, d]):
            polygons.append(tri)
            polygon_uv.append([[0.05 + vertices[i][0] * UV_PER_M, 0.05 + vertices[i][1] * UV_PER_M]
                               for i in tri])
    m = mesh(name=name, tris=len(polygons), materials=(material,))
    m["face_geometry"] = {"vertices": vertices, "polygons": polygons, "polygon_uv": polygon_uv,
                          "polygon_material": [material] * len(polygons)}
    return m


def _incident():
    """Island non-mirrored overall, holding one mirrored, one line-collapsed and one tile-spilling triangle."""
    m = _strip()
    uv = m["face_geometry"]["polygon_uv"]
    (a, b, c) = uv[3]
    uv[3] = [[2 * a[0] - p[0], p[1]] for p in (a, b, c)]  # polygon 3: mirrored in u around its first corner
    (a, b, c) = uv[6]
    uv[6] = [a, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], b]  # polygon 6: UV collapsed to a line
    uv[1] = [[p[0] + 0.9, p[1]] for p in uv[1]]  # polygon 1: corners in 1001 and 1002
    return m


def _signed(uv):
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(uv, uv[1:] + uv[:1])) / 2


def _found(m, diffuse_px=None):
    side_of = (lambda tile, material: (diffuse_px or {}).get(tile)) if diffuse_px else None
    return {f.name: f for stage in uv_findings([m], "vpm", "SM_Test_K_1.fbx", side_of).values() for f in stage}


def test_incident_island_is_not_mirrored_overall_but_each_bad_triangle_is_flagged():
    m = _incident()
    island = m["face_geometry"]["polygon_uv"]
    assert sum(_signed(uv) for uv in island) > 0  # the island as a whole has positive winding
    got = _found(m, {1001: SIDE})
    assert got["mirrored UV polygons"].status == "fail"
    assert got["mirrored UV polygons"].data["faces"] == {m["name"]: [3]}
    assert got["unwrapped UV polygons"].status == "review"  # SINTEZ recommendation, never pass
    assert got["unwrapped UV polygons"].data["faces"] == {m["name"]: [6]}
    assert got["UV outside UDIM tile"].status == "fail"
    assert got["UV outside UDIM tile"].data["faces"] == {m["name"]: [1]}
    assert got["mirrored UV polygons"].data["sintez_req"] == "2.5.2.1.4"
    assert got["unwrapped UV polygons"].data["sintez_req"] == "4.1.3"
    assert got["UV outside UDIM tile"].data["sintez_req"] == "2.5.2.1.2"


def test_clean_island_passes_every_per_polygon_check():
    got = _found(_strip(), {1001: SIDE})
    assert {n: f.status for n, f in got.items()} == {
        "mirrored UV polygons": "pass", "UV outside UDIM tile": "pass", "unwrapped UV polygons": "pass",
        "texel density per polygon": "pass"}


def test_sliver_triangle_below_512_is_flagged_although_its_edges_are_dense():
    m = _strip()
    xyz = [m["face_geometry"]["vertices"][i] for i in m["face_geometry"]["polygons"][5]]
    uv = [[0.3, 0.3], [0.7, 0.3], [0.5, 0.31]]  # thin but not collapsed: area/edge^2 = 0.0125
    m["face_geometry"]["polygon_uv"][5] = uv
    assert all(512 <= d <= 1706 for d in edge_densities(xyz, uv, SIDE))  # the old per-edge V009 passes it
    assert polygon_density(xyz, uv, SIDE) < 512
    got = _found(m, {1001: SIDE})
    assert got["texel density per polygon"].status == "fail"
    assert got["texel density per polygon"].data["faces"]["less"] == {m["name"]: [5]}
    assert got["texel density per polygon"].data["sintez_req"] == "2.6.2"
    assert got["unwrapped UV polygons"].status == "pass"


def test_two_coincident_vertices_are_a_recommendation_not_a_pass():
    vertices = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [1.0005, 0, 0]]  # vertex 4 within 2 mm of vertex 1
    polygons = [[0, 1, 2], [0, 2, 3], [4, 2, 1]]
    topo = count_defects(vertices, polygons)
    assert topo["duplicate_vertices"] == 1 and topo["tol_m"] == 0.002
    m = mesh(name="SM_Test_K_1_Main", tris=3, topology={"duplicate_vertices": topo["duplicate_vertices"]})
    finding = duplicate_vertex_finding([m], "SM_Test_K_1.fbx")
    assert finding.status == "review"
    assert finding.data["sintez_req"] == "2.3.7" and finding.data["recommendation"] == {m["name"]: 1}


def test_scene_route_reports_the_incident_on_vpm_and_npm():
    """twinqa.scene_findings (the --scene package route) carries the per-polygon findings."""
    vpm = scene_findings(rb(_incident()), "vpm", "oks", PROFILES.vpm, diffuse_px={(1, 1001): SIDE})
    v008 = {f.name: f.status for f in vpm["V008"]}
    assert v008["mirrored UV polygons"] == "fail" and v008["UV outside UDIM tile"] == "fail"
    assert v008["unwrapped UV polygons"] == "review"
    v009 = {f.name: f for f in vpm["V009"]}["texel density per polygon"]
    assert v009.status == "fail" and v009.data["faces"]["less"] == {"SM_Test_K_1_Main": [6]}  # collapsed: 0.01 px/m
    npm_mesh = _incident()
    npm_mesh["topology"]["duplicate_vertices"] = 4  # the shrub builder emitted per-face vertices
    npm = scene_findings(rb(npm_mesh), "npm", "oks", PROFILES.npm)
    v004 = {f.name: f.status for f in npm["V004"]}
    assert v004["unwrapped UV polygons"] == "review" and v004["duplicate vertices"] == "review"
    assert "mirrored UV polygons" not in v004  # SINTEZ checks mirroring on VPM only


# --- fail-closed and boundary probes ------------------------------------------------------------------------

def test_no_face_geometry_is_not_run_never_pass():
    got = _found(mesh(), {1001: SIDE})
    assert {f.status for f in got.values()} == {"not_run"}


def test_no_archive_sides_leaves_coverage_and_density_not_run_but_still_fails_crossing():
    got = _found(_strip())
    assert got["UV outside UDIM tile"].status == "not_run"
    assert got["texel density per polygon"].status == "not_run"
    assert _found(_incident())["UV outside UDIM tile"].status == "fail"


def test_tile_without_texture_counts_as_outside_like_sintez():
    got = _found(_strip(), {1002: SIDE})
    assert got["UV outside UDIM tile"].status == "fail"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_uv_fails_every_finding(bad):
    m = _strip()
    m["face_geometry"]["polygon_uv"][2][1][0] = bad
    got = _found(m, {1001: SIDE})
    assert {f.status for f in got.values()} == {"fail"}
    assert all(m["name"] in f.observed for f in got.values())


def test_partial_polygon_uv_fails():
    m = _strip()
    m["face_geometry"]["polygon_uv"].pop()
    assert {f.status for f in _found(m, {1001: SIDE}).values()} == {"fail"}


def test_density_exactly_at_the_bounds_passes_and_just_outside_fails():
    xyz = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    for scale, flagged in ((512 / SIDE, False), (1706 / SIDE, False), (511.99 / SIDE, True), (1706.01 / SIDE, True)):
        uv = [[0.1, 0.1], [0.1 + scale, 0.1], [0.1, 0.1 + scale]]
        m = mesh(tris=1, materials=("M",))
        m["face_geometry"] = {"vertices": xyz, "polygons": [[0, 1, 2]], "polygon_uv": [uv], "polygon_material": ["M"]}
        status = _found(m, {1001: SIDE})["texel density per polygon"].status
        assert status == ("fail" if flagged else "pass"), (scale * SIDE, status)


def test_placeholder_tile_exempt_from_density_only():
    m = _strip()
    for uv in m["face_geometry"]["polygon_uv"]:
        for p in uv:
            p[0] *= 0.01  # far below 512 px/m on a 4096 tile
    got = _found(m, {1001: 256})
    assert got["texel density per polygon"].status == "pass"
    assert got["texel density per polygon"].data["placeholder_polygons"] == 8
    assert _found(m, {1001: SIDE})["texel density per polygon"].status == "fail"


def test_sintez_tile_formula_keeps_the_vendor_edge_quirk():
    assert sintez_tile(0.5, 0.5) == 1001 and sintez_tile(1.0, 0.5) == 1001 and sintez_tile(1.0001, 0.5) == 1002
    assert sintez_tile(0.0, 0.5) == 1000 and sintez_tile(0.5, 1.0) == 1011


@pytest.mark.parametrize("count, status", [(0, "pass"), (1, "review"), (100, "review"), (101, "fail")])
def test_duplicate_vertex_thresholds(count, status):
    finding = duplicate_vertex_finding([mesh(topology={"duplicate_vertices": count})], "x.fbx")
    assert finding.status == status


@pytest.mark.parametrize("topology", [{"duplicate_vertices": None}, {"tol_m": 0.001}, {"duplicate_vertices": -1}])
def test_duplicate_count_missing_or_at_another_tolerance_is_not_run(topology):
    assert duplicate_vertex_finding([mesh(topology=topology)], "x.fbx").status == "not_run"
    assert duplicate_vertex_finding([], "x.fbx").status == "not_run"


def test_thin_polygon_unwrapped_as_thin_is_honest_and_point_collapse_is_flagged():
    sliver = [[0, 0, 0], [10, 0, 0], [5, 0.001, 0]]  # thin in 3D
    assert polygon_uv_issues(sliver, [[0.1, 0.1], [0.9, 0.1], [0.5, 0.1 + 0.00008]]) == set()
    assert polygon_uv_issues([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0.3, 0.3]] * 3) == {"uv_zero"}
    assert polygon_uv_issues([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [[0.1, 0.1], [0.2, 0.1], [0.1, 0.2]]) == {"geo_zero"}


def test_probe_mirroring_toggles_and_collapse_is_scale_invariant():
    """Generated probe: 500 random triangles, seed 1732."""
    rng = random.Random(1732)
    checked = 0
    for _ in range(500):
        xyz = [[rng.uniform(-5, 5) for _ in range(3)] for _ in range(3)]
        uv = [[rng.uniform(0.01, 0.99), rng.uniform(0.01, 0.99)] for _ in range(3)]
        base = polygon_uv_issues(xyz, uv)
        small = polygon_uv_issues(xyz, [[0.5 + (u - 0.5) * 0.01, 0.5 + (v - 0.5) * 0.01] for u, v in uv])
        assert ("uv_zero" in base) == ("uv_zero" in small)
        if base & {"uv_zero", "geo_zero"}:
            continue
        mirrored = polygon_uv_issues(xyz, [[1 - u, v] for u, v in uv])
        assert ("mirrored" in base) != ("mirrored" in mirrored)
        checked += 1
    assert checked > 400
