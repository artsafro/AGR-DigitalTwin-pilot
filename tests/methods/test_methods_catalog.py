"""Methods catalog (#706): metric runner, variants, RESULTS generator, benchmark set and docs structure.

Pattern: new-case: tests of the methods catalog (#706).
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "methods"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mm = _load("methods_metrics", TOOLS / "methods_metrics.py")
rv = _load("run_variant", TOOLS / "run_variant.py")
rmd = _load("results_md", TOOLS / "results_md.py")
uv_ = _load("ucx_variants", TOOLS / "ucx" / "ucx_variants.py")

BOX_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6),
         (3, 0, 4), (3, 4, 7)]


def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1],
            [x0, y1, z1]]


def mesh(name, verts, tris, *, uv=True, materials=("M_Test_Main_1",)):
    polys = [list(t) for t in tris]
    m = {"name": name, "vertices": len(verts), "polygons": len(polys), "triangles": len(polys),
         "polygon_degrees": {"3": len(polys)},
         "bounds_m": [[min(p[i] for p in verts) for i in range(3)], [max(p[i] for p in verts) for i in range(3)]],
         "location": [0.0, 0.0, 0.0], "rotation_euler_deg": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0],
         "world_scale": [1.0, 1.0, 1.0], "parent": None, "uv_channels": 1 if uv else 0,
         "materials": list(materials), "udim_tiles": [1001] if uv else [], "mirrored_uv_triangles": 0,
         "face_geometry": {"vertices": verts, "polygons": polys}}
    if uv:  # 1 m of geometry = 0.5 UV -> 512 px/m on a 1024 map; planar per face
        puv = []
        for p in polys:
            pts = np.array([verts[i] for i in p])
            n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
            drop = int(np.argmax(np.abs(n)))
            keep = [k for k in range(3) if k != drop]
            puv.append([[round(0.5 * pts[j][keep[0]], 6), round(0.5 * pts[j][keep[1]], 6)] for j in range(3)])
        m["face_geometry"]["uv"] = [[0.0, 0.0]] * len(verts)
        m["face_geometry"]["polygon_uv"] = puv
    if name.startswith("UCX_"):
        m["hull"] = {"verts": verts, "tris": [list(t) for t in tris]}
    return m


def scene(ucx_lo=(-0.01, -0.01, -0.01), ucx_hi=(1.01, 1.01, 1.01), with_ucx=True, model=None):
    meshes = [model or mesh("SM_Test_Main", box((0, 0, 0), (1, 1, 1)), BOX_T)]
    if with_ucx:
        meshes.append(mesh("UCX_SM_Test_Main_001", box(ucx_lo, ucx_hi), BOX_T, uv=False, materials=()))
    rb = {"source": "C:/synthetic/SM_Test.fbx", "readback_ok": True, "blender": "synthetic", "meshes": meshes,
          "other_objects": [], "images": [{"name": "T_Test_Main_d_1", "size": [1024, 1024], "packed": False,
                                           "packed_bytes": 0, "packed_sha256": None, "filepath": "T.png"}],
          "materials": [{"name": "M_Test_Main_1", "maps": [{"image": "T_Test_Main_d_1", "output": "Color",
                                                            "socket": "Base Color"}]}],
          "fbx_units": {"unit_scale_factor": 100.0, "original_unit_scale_factor": 100.0}}
    extra = {"ok": True, "meshes": {m["name"]: {"slots": list(m["materials"]),
                                                "polygons_by_material_index": {"0": m["polygons"]},
                                                "tris": m["face_geometry"]["polygons"]} for m in meshes}}
    return rb, extra


def bench_file(tmp_path, refs=None, classes=("ucx-collisions",), name="benchmarks.json"):
    data = {"schema": "methods-benchmarks/1", "objects": [
        {"id": "synth", "classes": list(classes), "source": {"kind": "fbx", "local_path": "C:/synthetic/SM_Test.fbx",
                                                             "sha256": "0" * 64}, "reference_pictures": refs or {}}]}
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def cli_args(tmp_path, rb, extra, **kw):
    out = tmp_path / "SM_Test.fbx"
    out.write_bytes(b"synthetic fbx bytes")
    (tmp_path / "rb.json").write_text(json.dumps(rb), encoding="utf-8")
    (tmp_path / "extra.json").write_text(json.dumps(extra), encoding="utf-8")
    args = [str(out), "--bench", "synth", "--class", "ucx-collisions", "--variant", "v1",
            "--benchmarks", str(kw.pop("benchmarks", None) or bench_file(tmp_path)),
            "--readback", str(tmp_path / "rb.json"), "--extra", str(tmp_path / "extra.json"),
            "--results", str(kw.pop("results", tmp_path / "results.jsonl"))]
    for k, v in kw.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return args


def last_row(path):
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


# ---- runner: every field ---------------------------------------------------------------------------------------------

def test_row_covers_every_metric_field(tmp_path):
    rb, extra = scene()
    assert rv.main(cli_args(tmp_path, rb, extra, wall_time_s=1.5)) == 0
    row = last_row(tmp_path / "results.jsonl")
    assert row["row"] == "R1" and row["schema"] == mm.SCHEMA
    assert row["wall_time_s"] == 1.5 and row["file_size_bytes"] == len(b"synthetic fbx bytes")
    assert row["triangles"] == {"model": 12, "ucx": 12}
    assert row["objects"] == {"meshes": 2, "model": 1, "ucx": 1, "other": 0}
    x = row["xview"]
    assert (x["vertex_m"], x["face_m"], x["parallel_cos_min"]) == (0.002, 0.005, 0.9999)
    assert (x["overlapping_vertices"], x["overlapping_faces"], x["passed"]) == (0, 0, True)
    u = row["ucx"]
    assert u["checks"]["UCX present"] == "pass" and u["checks"]["UCX intersections"] == "pass"
    assert u["closed_convex"] == 1 and u["limit_triangles"] == 15000 and u["status"] in ("pass", "open")
    assert row["texel"]["min_px_m"] == pytest.approx(512, rel=1e-3)
    assert row["texel"]["median_px_m"] == pytest.approx(512, rel=1e-3) and row["texel"]["reason"] is None
    assert row["matid"]["passed"] is True and row["matid"]["material_ids"] == [0]
    assert row["render_score"]["value"] is None
    assert row["render_score"]["reason"] == "benchmark has no reference picture"
    fit = row["class_metrics"]["ucx_fit"]
    assert fit["model_to_ucx_max_m"] == 0.0 and fit["reason"] is None
    assert fit["ucx_volume_m3"] > 0 and fit["ucx_outside_share"] is not None
    assert row["measure_time_s"] >= 0 and row["output_sha256"]


def test_missing_reference_picture_is_null_never_a_score(tmp_path):
    a = np.full((16, 16, 3), 128, np.uint8)
    from PIL import Image

    Image.fromarray(a).save(tmp_path / "ref.png")
    assert mm.render_score({}, {})["value"] is None
    assert mm.render_score({}, {"east": tmp_path / "ref.png"})["value"] is None  # no reference: never scored
    r = mm.render_score({"east": tmp_path / "ref.png"}, {})
    assert r["value"] is None and r["reason"] == "no variant render given"


def test_ssim_identical_one_different_lower_and_fail_closed(tmp_path):
    from PIL import Image

    rng = np.random.default_rng(7)
    a = rng.integers(0, 255, (32, 40, 3), dtype=np.uint8)
    b = a.copy()
    b[8:20, 8:20] = 0
    Image.fromarray(a).save(tmp_path / "a.png")
    Image.fromarray(b).save(tmp_path / "b.png")
    Image.fromarray(a[:30]).save(tmp_path / "small.png")
    same = mm.render_score({"e": tmp_path / "a.png"}, {"e": tmp_path / "a.png"})
    assert same["value"] == pytest.approx(1.0) and same["per_view"] == {"e": pytest.approx(1.0)}
    assert mm.render_score({"e": tmp_path / "a.png"}, {"e": tmp_path / "b.png"})["value"] < 0.95
    with pytest.raises(mm.MetricError, match="differ in size"):
        mm.render_score({"e": tmp_path / "a.png"}, {"e": tmp_path / "small.png"})
    with pytest.raises(mm.MetricError, match=r"\['w'\] have no render"):
        mm.render_score({"e": tmp_path / "a.png", "w": tmp_path / "a.png"}, {"e": tmp_path / "a.png"})
    with pytest.raises(mm.MetricError, match=r"\['n'\] have no reference"):
        mm.render_score({"e": tmp_path / "a.png"}, {"e": tmp_path / "a.png", "n": tmp_path / "a.png"})


def test_cli_render_score_against_benchmark_reference(tmp_path):
    from PIL import Image

    img = np.zeros((20, 20, 3), np.uint8)
    Image.fromarray(img).save(tmp_path / "ref.png")
    sha = rv.sha256(tmp_path / "ref.png")
    bench = bench_file(tmp_path, refs={"east": {"local_path": str(tmp_path / "ref.png"), "sha256": sha}}, name="b1.json")
    rb, extra = scene()
    assert rv.main(cli_args(tmp_path, rb, extra, benchmarks=bench, render=f"east={tmp_path / 'ref.png'}")) == 0
    assert last_row(tmp_path / "results.jsonl")["render_score"]["value"] == pytest.approx(1.0)
    bad = bench_file(tmp_path, refs={"east": {"local_path": str(tmp_path / "ref.png"), "sha256": "f" * 64}}, name="b2.json")
    assert rv.main(cli_args(tmp_path, rb, extra, benchmarks=bad, results=tmp_path / "r2.jsonl")) == 2
    assert not (tmp_path / "r2.jsonl").exists()


def test_xview_thresholds_are_the_shared_ones_unchanged():
    from dt_ai.ops import inv_xview

    assert (inv_xview.VERTEX_M, inv_xview.FACE_M, inv_xview.PARALLEL_COS_MIN) == (0.002, 0.005, 0.9999)
    assert math.degrees(math.acos(inv_xview.PARALLEL_COS_MIN)) == pytest.approx(0.81, abs=0.005)


def test_xview_counts_overlapping_vertices_inside_2mm_only():
    def two_tris(dx):
        v = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1 + dx, 0, 0], [2, 0, 0], [1 + dx, 1, 0]]
        return mesh("SM_Test_Main", v, [(0, 1, 2), (3, 4, 5)], uv=False)

    for dx, want in ((0.001, True), (0.0019, True), (0.003, False)):
        rb, _ = scene(model=two_tris(dx), with_ucx=False)
        assert (mm.xview(rb)["overlapping_vertices"] > 0) is want, dx


def test_texel_null_without_texture_size_never_guessed():
    rb, _ = scene()
    rb["images"] = []
    rb["materials"] = []
    t = mm.texel(rb)
    assert t["min_px_m"] is None and t["median_px_m"] is None and "texture size" in t["reason"]


def test_texel_from_package_udim_tiles_and_missing_tile_named(tmp_path):
    rb, _ = scene()
    rb["images"], rb["materials"] = [], []
    t = mm.texel(rb, {1001: 1024})
    assert t["min_px_m"] == pytest.approx(512, rel=1e-3) and t["texture_px_source"] == "package diffuse PNG"
    t = mm.texel(rb, {1002: 1024})
    assert t["min_px_m"] is None and "tile 1001 has no diffuse PNG" in t["reason"]
    assert mm.texel(rb, {None: 2048})["median_px_m"] == pytest.approx(1024, rel=1e-3)
    from PIL import Image

    Image.new("RGB", (64, 64)).save(tmp_path / "T_X_Diffuse_1.1001.png")
    Image.new("RGB", (32, 32)).save(tmp_path / "T_X_Normal_1.1001.png")  # not a diffuse map: ignored
    assert mm.package_tile_sides(tmp_path) == {1001: 64}
    Image.new("RGB", (64, 32)).save(tmp_path / "T_X_Diffuse_1.1002.png")
    with pytest.raises(mm.MetricError, match="not square"):
        mm.package_tile_sides(tmp_path)
    assert mm.package_tile_sides(tmp_path / "none") is None


def test_envelope_closes_window_openings_but_keeps_wide_courtyard():
    surface = np.zeros((40, 40, 12), bool)
    surface[5:35, 5, 2:10] = surface[5:35, 34, 2:10] = surface[5, 5:35, 2:10] = surface[34, 5:35, 2:10] = True
    surface[5:35, 5:35, 2] = surface[5:35, 5:35, 9] = True  # closed hollow box 30 x 30 x 8 cells
    surface[15:17, 5, 4:6] = False  # a 2-cell window in a wall
    env = mm._envelope(surface, 2)
    assert env[20, 20, 5]  # interior counted despite the window
    ring = np.zeros((60, 60, 6), bool)  # courtyard 20 cells wide inside a square ring, open at the top
    ring[10:50, 10:50, 1:5] = True
    ring[20:40, 20:40, 1:5] = False
    assert not mm._envelope(ring, 2)[30, 30, 3]


def test_matid_problems_and_unmapped_mesh_named():
    rb, extra = scene()
    extra["meshes"]["UCX_SM_Test_Main_001"]["slots"] = ["M_bad"]
    extra["meshes"]["SM_Test_Main"]["slots"] = ["M_Test_Main_1", "M_unused"]
    r = mm.matid(rb, extra)
    assert r["passed"] is False and any("UCX has 1" in p for p in r["problems"])
    assert any("unused slot(s) [1]" in p for p in r["problems"])
    extra["meshes"]["SM_Test_Main"] = {"slots": [None], "polygons_by_material_index": {"0": 12, "2": 1}, "tris": []}
    r = mm.matid(rb, extra)
    assert any("slot 0 is empty" in p for p in r["problems"]) and any("index 2 without a slot" in p for p in r["problems"])
    del extra["meshes"]["SM_Test_Main"]
    with pytest.raises(mm.MetricError, match="'SM_Test_Main' missing"):
        mm.matid(rb, extra)
    assert mm.matid(rb, None)["passed"] is None


def test_ucx_fit_reports_uncovered_model_part():
    rb, extra = scene(ucx_lo=(0, 0, 0), ucx_hi=(1, 1, 0.5))  # top half of the cube is not covered
    fit = mm.ucx_fit(rb, extra)
    assert fit["model_to_ucx_max_m"] == pytest.approx(0.5, abs=1e-6)
    assert fit["share_over_m"]["0.10"] > 0 and fit["share_over_m"]["1.00"] == 0.0
    rb, extra = scene(ucx_lo=(-1, -1, -1), ucx_hi=(2, 2, 2))  # loose piece: most of it outside the model
    fit = mm.ucx_fit(rb, extra)
    assert fit["model_to_ucx_max_m"] == 0.0 and fit["ucx_outside_share"] > 0.5


def test_point_triangle_distance_matches_dense_brute_force():
    """Probe: exact distance == min over a dense barycentric grid (within grid error), 200 random cases."""
    rng = np.random.default_rng(706)
    k = 120
    ii, jj = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing="ij")
    keep = ii + jj <= k
    u, w = ii[keep] / k, jj[keep] / k
    for _ in range(200):
        a, b, c, p = rng.normal(size=(4, 3)) * rng.uniform(0.1, 5)
        grid = a + (b - a) * u[:, None] + (c - a) * w[:, None]
        brute = np.linalg.norm(grid - p, axis=1).min()
        exact = float(mm.point_triangle_distance(p, a, b, c))
        tol = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / k
        assert exact <= brute + 1e-9 and brute - exact <= tol


# ---- runner: fail closed -----------------------------------------------------------------------------------------------

def test_results_path_aliasing_an_input_is_refused_and_nothing_written(tmp_path):
    rb, extra = scene()
    out = tmp_path / "SM_Test.fbx"
    args = cli_args(tmp_path, rb, extra, results=out)
    before = out.read_bytes()
    assert rv.main(args) == 4
    assert out.read_bytes() == before
    alias = str(tmp_path / "sub" / ".." / "rb.json")
    assert rv.main(cli_args(tmp_path, rb, extra, results=alias)) == 4
    assert json.loads((tmp_path / "rb.json").read_text(encoding="utf-8"))["readback_ok"] is True


@pytest.mark.parametrize("extra_args, code", [
    (["--bench", "nope"], 4), (["--class", "nope"], 4), (["--class", "sources"], 4),
    (["--wall-time-s", "nan"], 4), (["--wall-time-s", "-1"], 4), (["--wall-time-s", "inf"], 4),
    (["--render", "east"], 4)])
def test_bad_arguments_refused(tmp_path, extra_args, code):
    rb, extra = scene()
    args = cli_args(tmp_path, rb, extra) + extra_args
    assert rv.main(args) == code
    assert not (tmp_path / "results.jsonl").exists()


def test_failed_variant_report_and_failed_readback_never_give_a_row(tmp_path):
    rb, extra = scene()
    rep = tmp_path / "v.json"
    rep.write_text(json.dumps({"ok": False, "error": "boom"}), encoding="utf-8")
    assert rv.main(cli_args(tmp_path, rb, extra, variant_report=rep)) == 4
    rep.write_text(json.dumps({"ok": True}), encoding="utf-8")
    assert rv.main(cli_args(tmp_path, rb, extra, variant_report=rep)) == 4
    rb["readback_ok"] = False
    assert rv.main(cli_args(tmp_path, rb, extra)) == 2
    assert not (tmp_path / "results.jsonl").exists()


def test_zip_with_two_fbx_is_an_error(tmp_path):
    z = tmp_path / "pkg.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("a.fbx", b"1")
        f.writestr("b.fbx", b"2")
    with pytest.raises(mm.MetricError, match="holds 2 FBX"):
        rv.fbx_from(z, tmp_path / "x")
    with pytest.raises(rv.Refused, match="unsupported"):
        rv.fbx_from(tmp_path / "model.obj", tmp_path / "x")


def test_ucx_without_hull_is_an_error_not_a_fit():
    rb, extra = scene()
    rb["meshes"][1].pop("hull")
    with pytest.raises(mm.MetricError, match="no hull"):
        mm.ucx_fit(rb, extra)


def test_no_ucx_gives_fail_status(tmp_path):
    rb, extra = scene(with_ucx=False)
    assert rv.main(cli_args(tmp_path, rb, extra)) == 0
    row = last_row(tmp_path / "results.jsonl")
    assert row["ucx"]["status"] == "fail" and row["ucx"]["checks"]["UCX present"] == "fail"


# ---- rows and RESULTS.md -------------------------------------------------------------------------------------------------

def test_rows_are_numbered_and_results_md_generated(tmp_path):
    rb, extra = scene()
    for _ in range(3):
        assert rv.main(cli_args(tmp_path, rb, extra, wall_time_s=0.5)) == 0
    res = tmp_path / "results.jsonl"
    assert [json.loads(ln)["row"] for ln in res.read_text(encoding="utf-8").splitlines()] == ["R1", "R2", "R3"]
    md = rmd.write(res).read_text(encoding="utf-8")
    assert "| R3 | synth | v1 | 0.50 |" in md and not (tmp_path / "RESULTS.md.partial").exists()
    lines = res.read_text(encoding="utf-8").splitlines()
    res.write_text("\n".join([lines[1], lines[0]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not R1..R2"):
        rmd.read_rows(res)


def test_partial_results_file_refused(tmp_path):
    res = tmp_path / "results.jsonl"
    res.write_text('{"row": "R1"', encoding="utf-8")
    with pytest.raises(mm.MetricError, match="newline"):
        rv.append_row(res, {"x": 1})


# ---- variants ---------------------------------------------------------------------------------------------------------------

def _scene_arrays(*boxes):
    v, t = [], []
    for lo, hi in boxes:
        t += [tuple(i + len(v) for i in tri) for tri in BOX_T]
        v += box(lo, hi)
    return np.array(v, float), np.array(t, np.int64)


def box_hull(points):
    p = np.asarray(points, float)
    return np.array(box(p.min(0), p.max(0))), np.array(BOX_T)


def _min_gap(pieces):
    gaps = [uv_.sat_gap((np.asarray(a[0], float), np.asarray(a[1])), (np.asarray(b[0], float), np.asarray(b[1])))
            for i, a in enumerate(pieces) for b in pieces[i + 1:]]
    return min(gaps) if gaps else math.inf


@pytest.mark.parametrize("variant", uv_.VARIANTS)
def test_every_variant_gives_separated_closed_pieces(variant):
    v, t = _scene_arrays(((0, 0, 0), (4, 4, 3)), ((6, 0, 0), (9, 3, 6)), ((4, 0, 0), (6, 1, 1)))
    pieces, info = uv_.build(variant, v, t, model_triangles=len(t), hull_fn=box_hull)
    assert info["pieces"] == len(pieces) >= 1
    assert _min_gap(pieces) >= uv_.MERGE_GAP_M - 1e-9
    from twinqa.geometry.ucx_audit import is_closed, is_convex

    for pv, pt in pieces:
        pv, pt = [tuple(map(float, p)) for p in pv], [tuple(map(int, f)) for f in pt]
        assert is_closed(pt) and is_convex(pv, pt)


def test_part_boxes_keeps_separated_parts_and_merges_touching_ones():
    v, t = _scene_arrays(((0, 0, 0), (1, 1, 1)), ((3, 0, 0), (4, 1, 1)))
    assert len(uv_.build("part-boxes", v, t, model_triangles=24)[0]) == 2
    v, t = _scene_arrays(((0, 0, 0), (1, 1, 1)), ((1.001, 0, 0), (2, 1, 1)))  # 1 mm apart < 3 mm
    assert len(uv_.build("part-boxes", v, t, model_triangles=24)[0]) == 1
    v, t = _scene_arrays(((0, 0, 0), (1, 1, 1)), ((1.0031, 0, 0), (2, 1, 1)))  # just over the gap: kept apart
    assert len(uv_.build("part-boxes", v, t, model_triangles=24)[0]) == 2


def test_slice_prisms_cut_at_levels():
    v, t = _scene_arrays(((0, 0, 0), (10, 10, 3)), ((0, 0, 3), (5, 5, 6)))
    pieces, info = uv_.build("slice-prisms", v, t, model_triangles=24)
    assert info["levels_m"] == [0.0, 3.0, 6.0] and len(pieces) == 2


def test_slice_prisms_near_collinear_plan_gives_convex_pieces_after_float32():
    """Regression (TOW02 R12: 48/49 non-convex): near-collinear plan points made sliver cap triangles."""
    from twinqa.geometry.ucx_audit import is_closed, is_convex, weld

    ring = []
    for x in np.linspace(0, 30, 61):  # long facade bulging out by < 1 mm: all 61 points are on the hull
        ring.append((100 + x, 200 - 8e-4 * (1 - ((x - 15) / 15) ** 2)))
    ring += [(130, 215), (100, 215)]
    v, t = [], []
    for z0, z1 in ((0, 3), (3, 6)):
        base = len(v)
        v += [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
        k = len(ring)
        t += [(base + i, base + (i + 1) % k, base + k + i) for i in range(k)]
        t += [(base, base + i + 1, base + i) for i in range(1, k - 1)]  # bottom cap: horizontal face -> level
    pieces, _ = uv_.build("slice-prisms", np.array(v, float), np.array(t), model_triangles=len(t))
    for pv, pt in pieces:
        f32 = [tuple(float(c) for c in np.float32(p)) for p in pv]
        wv, wt = weld(f32, [tuple(map(int, f)) for f in pt])
        assert is_closed(wt) and is_convex(wv, wt)
        assert len(pv) <= 2 * 8  # the 61 facade points are one edge after simplification


@pytest.mark.parametrize("bad", [np.zeros((0, 3)), np.array([[0, 0, 0], [1, 0, 0], [np.nan, 1, 0]])])
def test_variants_fail_closed_on_empty_and_nan(bad):
    t = np.zeros((0, 3), np.int64) if len(bad) == 0 else np.array([[0, 1, 2]])
    for variant in uv_.VARIANTS:
        with pytest.raises(uv_.VariantError):
            uv_.build(variant, bad, t, model_triangles=1, hull_fn=box_hull)


def test_more_than_999_pieces_is_an_error():
    boxes = [((3 * i, 0, 0), (3 * i + 1, 1, 1)) for i in range(1000)]
    v, t = _scene_arrays(*boxes)
    with pytest.raises(uv_.VariantError, match="1000 pieces > 999"):
        uv_.build("part-boxes", v, t, model_triangles=len(t))
    with pytest.raises(uv_.VariantError, match="unknown variant"):
        uv_.build("nope", v, t, model_triangles=len(t))


# ---- benchmark set and docs -------------------------------------------------------------------------------------------------

def test_benchmarks_list_four_objects_with_sha256_and_no_private_file_committed():
    data = json.loads((ROOT / "benchmark/methods/benchmarks.json").read_text(encoding="utf-8"))
    ids = [o["id"] for o in data["objects"]]
    assert ids == ["kpp1", "ac08", "tow02", "vatutino-ground"]
    for o in data["objects"]:
        assert re.fullmatch(r"[0-9a-f]{64}", o["source"]["sha256"]) and o["source"]["fetch"]
        assert set(o["classes"]) <= set(mm.CLASSES)
        for ref in o["reference_pictures"].values():
            assert re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "benchmark/methods", "docs/methods", "tools/methods"],
                             capture_output=True, text=True, check=True).stdout.split()
    assert not [p for p in tracked if p.lower().endswith((".fbx", ".zip", ".max", ".blend", ".png"))]


def test_docs_structure_six_classes():
    base = ROOT / "docs" / "methods"
    assert (base / "README.md").is_file()
    assert sorted(p.name for p in base.iterdir() if p.is_dir()) == sorted(mm.CLASSES)
    for cls in mm.CLASSES:
        for f in ("VARIANTS.md", "RESULTS.md", "WHEN.md"):
            assert (base / cls / f).is_file(), (cls, f)


def test_ucx_class_has_nine_measured_rows_and_when_rules_cite_rows():
    base = ROOT / "docs" / "methods" / "ucx-collisions"
    rows = rmd.read_rows(base / "results.jsonl")
    measured = [r for r in rows if not r.get("build_error")]
    pairs = {(r["variant"], r["benchmark"]) for r in measured}
    assert len({v for v, _ in pairs}) >= 3 and {"kpp1", "ac08", "tow02"} <= {b for _, b in pairs}
    assert len(measured) >= 9
    assert (base / "RESULTS.md").read_text(encoding="utf-8") == rmd.render(rows, "ucx-collisions")
    ids = {r["row"] for r in rows}
    rules = [ln for ln in (base / "WHEN.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- ")]
    assert 1 <= len(rules) <= 15
    for rule in rules:
        cited = re.findall(r"\bR\d+\b", rule)
        assert cited and set(cited) <= ids, rule


@pytest.mark.blender
def test_end_to_end_tiny_fbx_in_blender(tmp_path):
    """A real FBX: build a cube in Blender, run a variant, measure it (opt-in: -m blender)."""
    from dt_ai.core.blender_runner import blender_executable

    exe = blender_executable()
    src = tmp_path / "SM_Test.fbx"
    make = tmp_path / "make.py"
    make.write_text("import bpy,sys\nbpy.ops.wm.read_factory_settings(use_empty=True)\n"
                    "bpy.ops.mesh.primitive_cube_add(size=2)\nbpy.context.object.name='SM_Test_Main'\n"
                    "bpy.ops.export_scene.fbx(filepath=sys.argv[-1])\n", encoding="utf-8")
    subprocess.run([exe, "--background", "--factory-startup", "--python", str(make), "--", str(src)], check=True,
                   capture_output=True, timeout=300)
    out = tmp_path / "v" / "SM_Test.fbx"
    subprocess.run([exe, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                    str(TOOLS / "ucx" / "build_variant_blender.py"), "--", str(src), str(out), "kernel-boxes"],
                   check=True, capture_output=True, timeout=600)
    bench = bench_file(tmp_path)
    res = tmp_path / "res.jsonl"
    code = rv.main([str(out), "--bench", "synth", "--class", "ucx-collisions", "--variant", "kernel-boxes",
                    "--variant-report", str(out) + ".variant.json", "--results", str(res), "--benchmarks", str(bench)])
    assert code == 0
    row = last_row(res)
    assert row["objects"]["ucx"] >= 1 and row["class_metrics"]["ucx_fit"]["model_to_ucx_max_m"] < 0.01
