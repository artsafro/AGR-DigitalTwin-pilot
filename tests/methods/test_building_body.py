"""building-body class metrics on tiny synthetic inputs (#727).

Pattern: new-case: tests of the building-body methods class (deviation, closed shells, budget, null paths).
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from tests.methods.test_methods_catalog import BOX_T, bench_file, box, cli_args, last_row, mesh, mm, rmd, rv


def rb_of(*meshes):
    return {"readback_ok": True, "blender": "synthetic", "meshes": list(meshes), "other_objects": [], "images": [],
            "materials": []}


def cube(name="SM_Test_Main", lo=(0, 0, 0), hi=(1, 1, 1), tris=BOX_T):
    return mesh(name, box(lo, hi), tris)


def test_identical_body_has_zero_deviation_and_one_closed_shell():
    b = mm.building_body(rb_of(cube()), rb_of(cube()))
    assert b["deviation_max_m"] == 0.0 and b["deviation_p95_m"] == 0.0 and b["deviation_samples"] > 0
    assert b["closed_shell_share"] == 1.0 and b["components"] == 1 and b["closed_components"] == 1
    assert b["triangles"] == 12 and b["triangle_budget"] == 150_000 and b["within_budget"] is True
    assert b["deviation_reason"] is None and b["shell_reason"] is None


def test_deviation_is_one_sided_source_to_variant():
    # variant is the source shifted 0.1 m along x: the source face x=0 is 0.1 m from the variant
    b = mm.building_body(rb_of(cube(lo=(0.1, 0, 0), hi=(1.1, 1, 1))), rb_of(cube()))
    assert b["deviation_max_m"] == pytest.approx(0.1, abs=1e-6)
    # a variant that contains the whole source surface plus extra geometry deviates 0 (one-sided)
    big = rb_of(cube(), cube("SM_Test_Main_2", (5, 5, 5), (6, 6, 6)))
    assert mm.building_body(big, rb_of(cube()))["deviation_max_m"] == 0.0


def test_open_box_is_not_a_closed_shell_and_shares_count_triangles():
    open_box = cube(tris=BOX_T[2:])  # bottom removed
    b = mm.building_body(rb_of(open_box, cube("SM_Test_Main_2", (3, 0, 0), (4, 1, 1))), None)
    assert b["components"] == 2 and b["closed_components"] == 1
    assert b["closed_shell_share"] == pytest.approx(12 / 22, abs=1e-5)


def test_split_vertices_are_welded_before_the_edge_count():
    v = box((0, 0, 0), (1, 1, 1))
    verts, tris = [], []
    for t in BOX_T:  # every triangle has its own three vertices (FBX corner split)
        tris.append([len(verts), len(verts) + 1, len(verts) + 2])
        verts += [list(v[i]) for i in t]
    assert mm.closed_shells(rb_of(mesh("SM_Test_Main", verts, tris)))["closed_shell_share"] == 1.0


def test_null_with_reason_paths_never_a_number():
    b = mm.building_body(rb_of(cube()), None)
    assert b["deviation_max_m"] is None and b["deviation_reason"] == "no source readback"
    ucx_only = rb_of(mesh("UCX_SM_Test_Main_001", box((0, 0, 0), (1, 1, 1)), BOX_T, uv=False, materials=()))
    b = mm.building_body(rb_of(cube()), ucx_only)
    assert b["deviation_max_m"] is None and b["deviation_reason"] == "source has no model triangle"
    b = mm.building_body(ucx_only, rb_of(cube()))
    assert b["deviation_max_m"] is None and b["deviation_reason"] == "variant has no model triangle"
    assert b["closed_shell_share"] is None and b["shell_reason"] == "no model triangle"


def test_failed_or_nonfinite_source_is_an_error_not_a_null():
    with pytest.raises(mm.MetricError, match="source readback failed"):
        mm.building_body(rb_of(cube()), {"readback_ok": False, "error": "boom"})
    bad = cube()
    bad["face_geometry"]["vertices"][0] = [float("nan"), 0, 0]
    with pytest.raises(mm.MetricError, match="non-finite"):
        mm.building_body(rb_of(cube()), rb_of(bad))
    with pytest.raises(mm.MetricError, match="no triangle"):
        mm.nearest_triangle_distance(np.zeros((1, 3)), np.zeros((0, 3, 3)))


@pytest.mark.parametrize("n, within", [(150_000, True), (150_001, False)])
def test_budget_exactly_at_threshold(n, within):
    m = cube()
    m["triangles"] = n  # counts() reads the readback triangle count
    b = mm.building_body(rb_of(m), None)
    assert b["within_budget"] is within and b["budget_share"] == round(n / 150_000, 5)


def test_grid_distance_matches_brute_force_on_random_soup():
    rng = np.random.default_rng(727)
    for _ in range(20):
        tri = rng.uniform(-5, 5, (int(rng.integers(1, 40)), 3, 3)) * rng.uniform(0.05, 1)
        pts = rng.uniform(-8, 8, (200, 3))
        brute = mm.point_triangle_distance(pts[:, None], tri[None, :, 0], tri[None, :, 1], tri[None, :, 2]).min(1)
        np.testing.assert_allclose(mm.nearest_triangle_distance(pts, tri, r0=0.05), brute, atol=1e-9)


def test_cli_writes_body_metrics_and_results_md_column(tmp_path):
    rb = rb_of(cube())
    (tmp_path / "src.json").write_text(json.dumps(rb_of(cube(lo=(0, 0, 0), hi=(1, 1, 1.2)))), encoding="utf-8")
    bench = bench_file(tmp_path, classes=("building-body",))
    args = cli_args(tmp_path, rb, {"ok": False}, benchmarks=bench, results=tmp_path / "results.jsonl")
    args[args.index("ucx-collisions")] = "building-body"
    assert rv.main(args + ["--source-readback", str(tmp_path / "src.json")]) == 0
    body = last_row(tmp_path / "results.jsonl")["class_metrics"]["body"]
    assert body["deviation_max_m"] == pytest.approx(0.2, abs=1e-6) and body["closed_shell_share"] == 1.0
    md = rmd.write(tmp_path / "results.jsonl").read_text(encoding="utf-8")
    assert "Deviation src->variant max / p95 m" in md and "| 0.2 / " in md and "1/1 (100.0%)" in md


def test_cli_missing_source_fbx_is_an_error_and_appends_nothing(tmp_path):
    bench = bench_file(tmp_path, classes=("building-body",))  # source C:/synthetic/SM_Test.fbx does not exist
    args = cli_args(tmp_path, rb_of(cube()), {"ok": False}, benchmarks=bench, results=tmp_path / "results.jsonl")
    args[args.index("ucx-collisions")] = "building-body"
    assert rv.main(args) == 2
    assert not (tmp_path / "results.jsonl").exists()


# ---- shared contour input + our kernel's prisms ---------------------------------------------------------------------

from tests.methods.test_methods_catalog import _load, TOOLS  # noqa: E402

bc = _load("body_contours", TOOLS / "body" / "contours.py")
kp = _load("body_kernel_prisms", TOOLS / "body" / "kernel_prisms.py")


def test_two_storey_box_gives_two_bands_and_closed_prisms_matching_it():
    # 10 x 6 m storey 0..3 m under a 6 x 6 m storey 3..6 m (synthetic, closed boxes)
    rb = rb_of(cube("SM_Test_Main", (0, 0, 0), (10, 6, 3)), cube("SM_Test_Main_2", (0, 0, 3), (6, 6, 6)))
    c = bc.contours(rb)
    assert c["synthetic_drawing"] is True and c["levels_m"] == [0.0, 3.0, 6.0] and not c["empty_bands"]
    areas = [round(sum(q.area for q in bc.polygons(b)), 2) for b in c["bands"]]
    assert areas == [60.0, 36.0]
    m = kp.prisms(c)
    out = rb_of(mesh("SM_Test_Main", m["vertices"], m["triangles"], uv=False))
    b = mm.building_body(out, rb)
    assert b["deviation_max_m"] == pytest.approx(0.0, abs=1e-6)
    # each prism is closed, but stacked prisms share the edge (0,0,3)-(0,6,3) four times: one non-manifold shell
    assert b["components"] == 1 and b["closed_shell_share"] == 0.0
    single = mm.building_body(rb_of(mesh("SM_Test_Main", *[kp.prisms({"bands": c["bands"][:1]})[k]
                                                           for k in ("vertices", "triangles")], uv=False)), None)
    assert single["closed_shell_share"] == 1.0


def test_hole_touching_the_outline_is_filled_never_a_repeated_vertex():
    from shapely.geometry import Polygon

    q = bc.simple_rings(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(0, 0), (3, 1), (1, 3)], [(5, 5), (7, 5), (7, 7), (5, 7)]]))
    assert len(q.interiors) == 1 and Polygon(q.interiors[0]).area == 4.0  # touching triangle hole filled
    kp.prisms({"bands": [{"z0": 0, "z1": 3, "polygons": [{"exterior": list(q.exterior.coords)[:-1],
                                                           "holes": [list(r.coords)[:-1] for r in q.interiors]}]}]})


def test_contours_fail_closed_on_empty_or_nonfinite_source():
    with pytest.raises(ValueError, match="no model triangle"):
        bc.contours(rb_of())
    bad = cube()
    bad["face_geometry"]["vertices"][0] = [float("inf"), 0, 0]
    with pytest.raises(ValueError, match="non-finite"):
        bc.contours(rb_of(bad))
    with pytest.raises(ValueError, match="no band polygon"):
        kp.prisms({"bands": []})
