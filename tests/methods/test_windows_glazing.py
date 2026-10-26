"""windows-glazing class metrics and variant geometry on tiny synthetic inputs (#721).

Pattern: new-case: tests of the windows-glazing methods class (metric null paths, opening extraction, refusals).
"""
from __future__ import annotations

import json
import math

from pathlib import Path

import numpy as np
import pytest

from tests.methods.test_methods_catalog import BOX_T, TOOLS, _load, bench_file, box, mesh, mm, rmd, rv

wv = _load("methods_windows_variants", TOOLS / "windows" / "windows_variants.py")


def win_scene(*, frame=True, glass=True, per_poly=True, depth=0.07):
    """Main = wall box + (optionally) a frame box on slot 1 named *Frame*; optional MainGlass quad."""
    wall = box((0, 0, 0), (4, 0.3, 3))
    verts, tris = list(wall), [list(t) for t in BOX_T]
    mat_idx = [0] * len(tris)
    slots = ["M_Test_Main_1"]
    if frame:
        fr = box((1, -depth, 1), (2, 0, 2))
        verts += fr
        tris += [[a + 8, b + 8, c + 8] for a, b, c in BOX_T]
        mat_idx += [1] * len(BOX_T)
        slots.append("M_Test_Main_Frame")
    main = mesh("SM_Test_Main", verts, tris, materials=slots)
    meshes = [main]
    if glass:
        meshes.append(mesh("SM_Test_MainGlass", [[1, -0.035, 1], [2, -0.035, 1], [2, -0.035, 2], [1, -0.035, 2]],
                           [[0, 1, 2], [0, 2, 3]], materials=("M_Test_MainGlass_1",)))
    rb = {"readback_ok": True, "blender": "synthetic", "meshes": meshes, "other_objects": [], "images": [],
          "materials": []}
    extra = {"ok": True, "meshes": {}}
    for m in meshes:
        idx = mat_idx if m["name"] == "SM_Test_Main" else [0] * m["polygons"]
        info = {"slots": list(m["materials"]),
                "polygons_by_material_index": {str(k): idx.count(k) for k in sorted(set(idx))},
                "tris": m["face_geometry"]["polygons"]}
        if per_poly:
            info["polygon_material_index"] = idx
        extra["meshes"][m["name"]] = info
    return rb, extra


def test_glass_count_share_and_frame_depth():
    rb, extra = win_scene()
    w = mm.windows_glazing(rb, extra)
    assert w["glass_objects"] == 1 and w["glass_object_names"] == ["SM_Test_MainGlass"]
    assert w["glass_triangles"] == 2 and w["glass_triangle_share"] == round(2 / 26, 5)
    assert w["frame_components"] == 1 and w["frame_polygons"] == 12
    assert w["frame_depth_m"] == {"min": 0.07, "median": 0.07, "max": 0.07}
    assert w["frame_reason"] is None and w["glass_share_reason"] is None


def test_flat_frame_ring_reads_zero_depth():
    rb, extra = win_scene(depth=0.0)
    assert mm.windows_glazing(rb, extra)["frame_depth_m"]["max"] == 0.0


@pytest.mark.parametrize("kw,extra_mod,reason", [
    ({"frame": False}, None, "no polygon on a material slot named *Frame*"),
    ({}, "none", "no extra readback"),
    ({}, "not-ok", "no extra readback"),
    ({"per_poly": False}, None, "extra readback has no per-polygon material index"),
])
def test_frame_depth_null_with_reason(kw, extra_mod, reason):
    rb, extra = win_scene(**kw)
    if extra_mod == "none":
        extra = None
    elif extra_mod == "not-ok":
        extra["ok"] = False
    w = mm.windows_glazing(rb, extra)
    assert w["frame_depth_m"] is None and w["frame_reason"] == reason
    assert w["glass_objects"] == 1  # glass figures do not need the extra readback


def test_no_glass_object_is_zero_not_null_and_no_triangles_is_null():
    rb, extra = win_scene(glass=False)
    w = mm.windows_glazing(rb, extra)
    assert w["glass_objects"] == 0 and w["glass_triangle_share"] == 0.0
    rb["meshes"][0]["triangles"] = 0
    w = mm.windows_glazing(rb, extra)
    assert w["glass_triangle_share"] is None and w["glass_share_reason"] == "no model triangle"


def test_frame_index_count_mismatch_and_missing_mesh_are_errors():
    rb, extra = win_scene()
    extra["meshes"]["SM_Test_Main"]["polygon_material_index"].pop()
    with pytest.raises(mm.MetricError, match="material indices"):
        mm.windows_glazing(rb, extra)
    rb, extra = win_scene()
    del extra["meshes"]["SM_Test_MainGlass"]
    with pytest.raises(mm.MetricError, match="SM_Test_MainGlass"):
        mm.windows_glazing(rb, extra)


def test_xview_thresholds_unchanged():
    tol = mm.tolerance_for("VPM")
    assert (tol.vertex_m, tol.face_m) == (0.002, 0.005)
    assert math.isclose(math.degrees(math.acos(tol.parallel_cos_min)), 0.81, abs_tol=0.005)


# ---- opening extraction and variant geometry --------------------------------------------------------------------

def quad(x0, x1, z0, z1, y=0.0):
    return [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]]


def test_extract_openings_groups_drops_and_accounts_every_polygon():
    polys = [quad(0, 1, 0, 1.5), quad(1, 2, 0, 1.5),  # two coplanar panes sharing an edge -> one 2 x 1.5 opening
             quad(5, 6, 0, 1.5, y=0.003),  # separate opening
             [[0, 0, 5], [1, 0, 5], [1, 1, 5], [0, 1, 5]],  # skylight (horizontal)
             quad(8, 8.1, 0, 1),  # 0.1 m wide
             [[10, 0, 0], [10, 0, 0], [10, 0, 0]],  # zero area
             [[12, 0, 0], [14, 0, 0], [12, 0, 2]]]  # triangle: fill 0.5
    openings, dropped = wv.extract_openings(polys, model_centre_xy=(0, 5))
    assert [o["polygons"] for o in openings] == [[0, 1], [2]]
    assert math.isclose(openings[0]["width"], 2) and math.isclose(openings[0]["height"], 1.5)
    assert np.allclose(openings[0]["n"], [0, -1, 0])  # outward = away from the model centre (y = 5)
    reasons = {tuple(d["polygons"]): d["reason"] for d in dropped}
    assert reasons[(3,)].startswith("not a facade window")
    assert "under 0.2 m" in reasons[(4,)] and reasons[(5,)] == "zero-area glass polygon"
    assert reasons[(6,)].startswith("not rectangular")
    seen = sorted(i for o in openings for i in o["polygons"]) + sorted(i for d in dropped for i in d["polygons"])
    assert sorted(seen) == list(range(len(polys)))


def test_extract_openings_rejects_bad_polygons():
    with pytest.raises(ValueError, match="non-finite"):
        wv.extract_openings([[[0, 0, 0], [1, 0, float("nan")], [1, 0, 1]]])
    with pytest.raises(ValueError, match="2 points"):
        wv.extract_openings([[[0, 0, 0], [1, 0, 0]]])
    assert wv.extract_openings([]) == ([], [])


def test_brute_force_every_polygon_ends_in_opening_or_drop():
    rng = np.random.default_rng(721)
    for _ in range(200):
        polys = []
        for _ in range(int(rng.integers(1, 8))):
            x, z = rng.uniform(-5, 5, 2)
            w, h = rng.uniform(0.05, 2, 2)
            y = float(rng.choice([0.0, 0.002, 1.0]))
            polys.append(quad(x, x + w, z, z + h, y) if rng.random() > 0.2 else
                         [[x, y, z], [x + w, y + 1, z], [x, y, z + h]])
        openings, dropped = wv.extract_openings(polys)
        ids = sorted(i for o in openings for i in o["polygons"]) + sorted(i for d in dropped for i in d["polygons"])
        assert sorted(ids) == list(range(len(polys)))


def opening(w=2.0, h=1.5):
    return wv.extract_openings([quad(0, w, 0, h)], model_centre_xy=(0, 5))[0][0]


def test_atlas_planes_one_quad_per_opening_inside_tile():
    a = wv.atlas_planes([opening(), opening(1.0, 1.0), opening()], tile=1020)
    assert len(a["faces"]) == 3 and a["types"] == [(1.0, 1.0), (2.0, 1.5)] and a["grid"] == 2
    uv = np.array(a["uvs"]).reshape(-1, 2)
    du, dv = wv.tile_offset(1020)
    assert (uv[:, 0] >= du).all() and (uv[:, 0] < du + 1).all() and (uv[:, 1] >= dv).all() and (uv[:, 1] < dv + 1).all()


def test_inset_glass_trim_ring_and_pane_share_edges_never_overlap():
    o = opening()
    r = wv.inset_glass_trim([o], tile=1002)
    fv, ff, fuv = r["frame"]
    gv, gf, _ = r["glass"]
    assert len(ff) == 4 and len(gf) == 1
    pane = gv[gf[0]]
    local = (pane - o["centre"]) @ np.stack([o["u"], o["v"]]).T
    assert np.allclose(np.abs(local), [o["width"] / 2 - wv.TRIM_W_M, o["height"] / 2 - wv.TRIM_W_M])
    ring_area = sum(np.linalg.norm(wv._newell(fv[f])) for f in ff)
    assert math.isclose(ring_area + 1.88 * 1.38, 2.0 * 1.5, rel_tol=1e-9)  # ring + pane tile the opening exactly
    assert all(1.0 <= u < 2.0 and 0.0 <= v < 1.0 for face in fuv for u, v in face)


def test_bad_tile_refused():
    with pytest.raises(ValueError, match="UDIM tile"):
        wv.tile_offset(1000)


bvb = _load("methods_windows_build", TOOLS / "windows" / "build_variant_blender.py")


@pytest.mark.parametrize("argv,msg", [
    (["a.fbx", "b.fbx", "modelled-frames"], "usage"),
    (["a.fbx", "b.fbx", "no-such", "tile=1001"], "unknown variant"),
    (["a.fbx", "b.obj", "atlas-planes", "tile=1001"], "must be an .fbx"),
    (["a.fbx", "b.fbx", "atlas-planes", "glass_map=x.png"], "tile=<UDIM> is required"),
    (["a.fbx", "b.fbx", "atlas-planes", "tile=1001", "glass_map=C:/no/such/map.png"], "does not exist"),
    (["a.fbx", "b.fbx", "atlas-planes", "tile=999"], "bad tile"),
    (["a.fbx", "b.fbx", "atlas-planes", "tile=1001", "tile=1002"], "bad option"),
    (["a.fbx", "b.fbx", "atlas-planes", "tile=1001", "colour=red"], "bad option"),
])
def test_driver_refuses_bad_arguments(argv, msg):
    opts, err = bvb._parse(argv)
    assert opts is None and err and __import__("re").search(msg, err)


@pytest.mark.parametrize("alias", ["source", "glass_map"])
def test_driver_output_aliasing_an_input_exits_4_and_writes_nothing(tmp_path, monkeypatch, alias):
    src = tmp_path / "SM_Test.fbx"
    src.write_bytes(b"fbx")
    gm = tmp_path / "T_m_1.png"
    gm.write_bytes(b"png")
    out = src if alias == "source" else tmp_path / "T_m_1.png.fbx"
    if alias == "glass_map":  # the report path <out>.variant.json is fine; make the FBX itself the map
        out = gm.with_suffix(".fbx")
        gm.rename(out)
        gm = out
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr("sys.argv", ["blender", "--", str(src), str(out), "atlas-planes", "tile=1002",
                                     f"glass_map={gm}"])
    assert bvb.main() == 4
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


# ---- runner + RESULTS.md -------------------------------------------------------------------------------------------

def test_run_variant_writes_windows_class_metrics_and_results_columns(tmp_path):
    rb, extra = win_scene()
    out = tmp_path / "SM_Test.fbx"
    out.write_bytes(b"synthetic fbx bytes")
    (tmp_path / "rb.json").write_text(json.dumps(rb), encoding="utf-8")
    (tmp_path / "extra.json").write_text(json.dumps(extra), encoding="utf-8")
    results = tmp_path / "results.jsonl"
    code = rv.main([str(out), "--bench", "synth", "--class", "windows-glazing", "--variant", "v1",
                    "--benchmarks", str(bench_file(tmp_path, classes=("windows-glazing",))),
                    "--readback", str(tmp_path / "rb.json"), "--extra", str(tmp_path / "extra.json"),
                    "--results", str(results), "--wall-time-s", "1.5"])
    assert code == 0
    row = json.loads(results.read_text(encoding="utf-8"))
    assert row["class_metrics"]["windows"]["frame_depth_m"]["median"] == 0.07
    md = rmd.render(rmd.read_rows(results), "windows-glazing")
    assert "| Glass objs | Glass tris (share) | Frame comps |" in md
    assert "| 1 | 2 (7.7%) | 1 | 0.07 / 0.07 / 0.07 |" in md
    head, sep = md.splitlines()[5:7]
    assert head.count("|") == sep.count("|")
    assert "Glass objs" not in rmd.render(rmd.read_rows(results), "ucx-collisions")


def test_results_md_lists_window_null_reasons():
    rows = [{"row": "R1", "class": "windows-glazing", "benchmark": "b", "variant": "v",
             "class_metrics": {"windows": {"glass_objects": 0, "glass_triangles": 0, "glass_triangle_share": 0.0,
                                           "frame_components": 0, "frame_depth_m": None,
                                           "frame_reason": "no polygon on a material slot named *Frame*"}}}]
    md = rmd.render(rows, "windows-glazing")
    assert "- windows frame: no polygon on a material slot named *Frame* (R1)" in md


def test_committed_results_regenerate_byte_identical():
    path = TOOLS.parents[1] / "docs" / "methods" / "windows-glazing" / "results.jsonl"
    if not path.is_file():
        pytest.skip("no committed windows-glazing rows yet")
    md = path.with_name("RESULTS.md").read_text(encoding="utf-8")
    assert rmd.render(rmd.read_rows(path), "windows-glazing") == md


def test_when_rules_cite_existing_rows_and_numbers():
    import re

    base = TOOLS.parents[1] / "docs" / "methods" / "windows-glazing"
    if not (base / "results.jsonl").is_file():
        pytest.skip("no committed windows-glazing rows yet")
    n = len(rmd.read_rows(base / "results.jsonl"))
    text = (base / "WHEN.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 15
    rules = [ln for ln in text.splitlines() if ln.startswith("- ")]
    assert rules
    for rule in rules:
        cited = [int(x) for x in re.findall(r"\bR(\d+)\b", rule)]
        assert cited and all(1 <= c <= n for c in cited), rule
        assert re.search(r"\d", re.sub(r"\bR\d+\b", "", rule)), f"rule without a number: {rule}"



# ---- review round 1: generated textures bound, every source mesh kept (pure parts) ------------------------------
wvm = _load("methods_windows_variants_t", TOOLS / "windows" / "windows_variants.py")


@pytest.mark.parametrize("variant", wvm.VARIANTS)
def test_texture_pixels_shape_and_not_uniform(variant):
    px = wvm.texture_pixels(variant, 64, 2)
    assert px.shape == (64, 64, 4) and px.dtype == np.float32 and np.isfinite(px).all()
    assert len(np.unique(px[:, :, :3].reshape(-1, 3), axis=0)) >= 2 and (px[:, :, 3] == 1).all()


@pytest.mark.parametrize("args", [("no-such", 64, 1), ("atlas-planes", 8, 1), ("atlas-planes", 64, 0),
                                  ("atlas-planes", 64.0, 1), ("atlas-planes", 64, True)])
def test_texture_pixels_refuses_bad_input(args):
    with pytest.raises(ValueError):
        wvm.texture_pixels(*args)


def _entry(tris=12, slots=("M_A",), lo=(0, 0, 0), hi=(1, 1, 1)):
    return {"tris": tris, "slots": list(slots), "bbox": [list(lo), list(hi)]}


@pytest.mark.parametrize("actual,needle", [
    ({"SM_T_Main": _entry()}, "missing in output: SM_T_RoofDetail"),
    ({"SM_T_Main": _entry(), "SM_T_RoofDetail": _entry(), "X": _entry()}, "not expected in output: X"),
    ({"SM_T_Main": _entry(), "SM_T_RoofDetail": _entry(tris=10)}, "triangles 12 -> 10"),
    ({"SM_T_Main": _entry(), "SM_T_RoofDetail": _entry(slots=("M_B",))}, "material slots"),
    ({"SM_T_Main": _entry(), "SM_T_RoofDetail": _entry(hi=(1, 1, 1.0002))}, "bounding box moved"),
    ({"SM_T_Main": _entry(), "SM_T_RoofDetail": _entry(hi=(1, 1, float("nan")))}, "not finite"),
    ({"SM_T_Main": _entry(), "SM_T_RoofDetail": None}, "no read-back entry"),
])
def test_inventory_diff_names_every_problem(actual, needle):
    expected = {"SM_T_Main": None, "SM_T_RoofDetail": _entry()}
    assert any(needle in p for p in wvm.inventory_diff(expected, actual))


def test_inventory_diff_reconciled_and_exactly_at_tolerance():
    expected = {"SM_T_Main": None, "SM_T_RoofDetail": _entry()}
    assert wvm.inventory_diff(expected, {"SM_T_Main": _entry(tris=99), "SM_T_RoofDetail": _entry()}) == []
    at = {"SM_T_Main": None, "SM_T_RoofDetail": _entry(hi=(1, 1, 1 + wvm.INVENTORY_TOL_M / 2))}
    assert wvm.inventory_diff(expected, at) == []  # inside tol passes; 2x tol (above) fails


@pytest.mark.parametrize("argv,msg", [
    (["a.fbx", "b.fbx", "atlas-planes", "tile=1002", "texture=sub/T.png"], "bare file name"),
    (["a.fbx", "b.fbx", "atlas-planes", "tile=1002", "texture=T.tga"], "bare file name"),
    (["a.fbx", "b.fbx", "atlas-planes", "tile=1002", "texture_side=8"], "bad texture_side"),
    (["a.fbx", "b.fbx", "atlas-planes", "tile=1002", "texture_side=big"], "bad texture_side"),
])
def test_driver_refuses_bad_texture_options(argv, msg):
    opts, err = bvb._parse(argv)
    assert opts is None and err and __import__("re").search(msg, err)


def test_driver_texture_aliasing_an_input_exits_4_and_writes_nothing(tmp_path, monkeypatch):
    src = tmp_path / "SM_Test.fbx"
    src.write_bytes(b"fbx")
    gm = tmp_path / "T_m_1.png"
    gm.write_bytes(b"png")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr("sys.argv", ["blender", "--", str(src), str(tmp_path / "SM_Out.fbx"), "atlas-planes",
                                     "tile=1002", f"glass_map={gm}", "texture=T_m_1.png"])
    assert bvb.main() == 4
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


# ---- review round 1: real Blender witnesses (opt-in: -m blender) ---------------------------------------------------
MAKE_SCENE = """
import bpy, sys
bpy.ops.wm.read_factory_settings(use_empty=True)
glass, ucx, out = sys.argv[-3] == "1", sys.argv[-2] == "1", sys.argv[-1]
def obj(name, verts, faces, mat, loc=(0, 0, 0), rot=0.0):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.uv_layers.new(name="UVMap")
    me.materials.append(bpy.data.materials.get(mat) or bpy.data.materials.new(mat)); me.update()
    ob = bpy.data.objects.new(name, me); ob.location = loc; ob.rotation_euler[2] = rot
    bpy.context.scene.collection.objects.link(ob); return ob
def box(x0, y0, z0, x1, y1, z1):
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f
obj("SM_Test_Main", *box(0, 0, 0, 4, 0.3, 3), "M_Test_Main_1")
obj("SM_Test_RoofDetail", *box(-0.4, -0.4, 0, 0.4, 0.4, 0.6), "M_Test_RoofDetail_1", loc=(2, 0.15, 3), rot=0.5)
if ucx:
    obj("UCX_SM_Test_Main_00", *box(0, 0, 0, 4, 0.3, 3), "M_Test_Main_1")
if glass:
    q = lambda x0, x1: [(x0, -0.01, 0.8), (x1, -0.01, 0.8), (x1, -0.01, 2.0), (x0, -0.01, 2.0)]
    obj("SM_Test_MainGlass", q(0.5, 1.5) + q(2.5, 3.5), [(0, 1, 2, 3), (4, 5, 6, 7)], "M_Test_MainGlass_1")
bpy.ops.export_scene.fbx(filepath=out, object_types={"MESH"}, bake_anim=False)
"""

PROBE = """
import bpy, sys, json, hashlib
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=sys.argv[-2])
res = {"meshes": {}, "materials": {}}
for o in bpy.context.scene.objects:
    if o.type != "MESH":
        continue
    co = [o.matrix_world @ v.co for v in o.data.vertices]
    res["meshes"][o.name] = {"tris": sum(len(p.vertices) - 2 for p in o.data.polygons),
        "slots": [s.material.name for s in o.material_slots],
        "bbox": [[min(c[i] for c in co) for i in range(3)], [max(c[i] for c in co) for i in range(3)]]}
for m in bpy.data.materials:
    links = [lk for lk in (m.node_tree.links if m.node_tree else []) if lk.to_socket.name == "Base Color"
             and lk.from_node.type == "TEX_IMAGE" and lk.from_node.image]
    files = [bpy.path.abspath(lk.from_node.image.filepath) for lk in links]
    res["materials"][m.name] = [{"file": f, "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest()}
                                for f in files]
open(sys.argv[-1], "w").write(json.dumps(res))
"""


def _blender_run(exe, script, *args, check=True):
    import subprocess

    return subprocess.run([exe, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                           str(script), "--", *map(str, args)], capture_output=True, text=True, timeout=600,
                          check=check)


def _probe(exe, tmp_path, fbx, tag):
    (tmp_path / "probe.py").write_text(PROBE, encoding="utf-8")
    res = tmp_path / f"{tag}.probe.json"
    _blender_run(exe, tmp_path / "probe.py", fbx, res)
    return json.loads(res.read_text())


def _make_source(exe, tmp_path, glass, script=MAKE_SCENE):
    (tmp_path / "make.py").write_text(script, encoding="utf-8")
    src = tmp_path / "src" / "SM_Test.fbx"
    src.parent.mkdir()
    _blender_run(exe, tmp_path / "make.py", int(glass), 1, src)
    return src


@pytest.mark.blender
@pytest.mark.parametrize("glass", [True, False], ids=["glass", "no-glass"])
@pytest.mark.parametrize("variant", ["modelled-frames", "atlas-planes", "inset-glass-trim"])
def test_driver_keeps_accessory_ucx_and_binds_the_generated_texture(tmp_path, variant, glass):
    """Main + RoofDetail accessory (rotated, own material) + UCX, with or without MainGlass: every source mesh
    except the glass survives unchanged; the new material samples the packaged PNG through a clean import."""
    import hashlib
    import shutil

    from dt_ai.core.blender_runner import blender_executable

    exe = blender_executable()
    src = _make_source(exe, tmp_path, glass)
    out = tmp_path / "v" / "SM_Test.fbx"
    r = _blender_run(exe, TOOLS / "windows" / "build_variant_blender.py", src, out, variant, "tile=1002",
                     "texture_side=64", check=False)
    rep = out.with_name(out.name + ".variant.json")
    report = json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else {}
    assert r.returncode == 0 and report.get("ok"), report.get("error") or r.stderr[-500:]
    assert not out.with_name("SM_Test.partial.fbx").exists()
    before = _probe(exe, tmp_path, src, "before")
    pkg = tmp_path / "pkg"  # clean import from a package-like folder: only the FBX and the PNG(s) next to it
    pkg.mkdir()
    shutil.copyfile(out, pkg / out.name)
    for png in out.parent.glob("*.png"):
        shutil.copyfile(png, pkg / png.name)
    after = _probe(exe, tmp_path, pkg / out.name, "after")
    keep = {"SM_Test_RoofDetail", "UCX_SM_Test_Main_00"}
    want = {"SM_Test_Main"} | keep | ({"SM_Test_MainGlass"} if glass and variant != "atlas-planes" else set())
    assert set(after["meshes"]) == want
    for n in keep:
        a, b = after["meshes"][n], before["meshes"][n]
        assert a["tris"] == b["tris"] and a["slots"] == b["slots"]
        assert np.abs(np.array(a["bbox"]) - np.array(b["bbox"])).max() < 1e-4
    assert report["source_inventory"] == sorted(before["meshes"])
    mat = f"M_SM_Test_Main_{wvm.GEN_MATERIAL[variant]}"
    if not glass:
        assert report["openings"] == 0 and report["texture"] is None and mat not in after["materials"]
        assert not list(out.parent.glob("*.png"))
        return
    assert report["openings"] == 2
    png = pkg / report["texture"]
    assert report["texture"] == f"T_SM_Test_{wvm.GEN_MATERIAL[variant]}.png"
    bound = after["materials"][mat]
    assert len(bound) == 1 and Path(bound[0]["file"]).samefile(png)
    assert bound[0]["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest() == report["texture_sha256"]
    assert mat in after["meshes"]["SM_Test_Main"]["slots"]


@pytest.mark.blender
def test_driver_name_collision_publishes_nothing(tmp_path):
    """A source that already has the variant's material name: exit 2, no FBX (stale one removed), no PNG."""
    from dt_ai.core.blender_runner import blender_executable

    exe = blender_executable()
    src = _make_source(exe, tmp_path, True,
                       MAKE_SCENE.replace('"M_Test_RoofDetail_1"', '"M_SM_Test_Main_WindowAtlas"'))
    out = tmp_path / "v" / "SM_Test.fbx"
    out.parent.mkdir()
    out.write_bytes(b"stale")
    r = _blender_run(exe, TOOLS / "windows" / "build_variant_blender.py", src, out, "atlas-planes", "tile=1002",
                     check=False)
    report = json.loads(out.with_name(out.name + ".variant.json").read_text(encoding="utf-8"))
    assert r.returncode == 2 and not report["ok"] and "collide" in report["error"]
    assert sorted(q.name for q in out.parent.iterdir()) == ["SM_Test.fbx.variant.json"]


def test_texel_package_tiles_win_over_one_bound_readback_image():
    """Review round 1: binding one generated 1024 px image must not make every tile read as 1024 px."""
    from tests.methods.test_methods_catalog import scene

    rb, _ = scene()
    rb["images"] = [{"name": "T_Test_Diffuse.1002.png", "size": [1024, 1024]}]
    rb["materials"] = []
    assert mm.texel(rb)["texture_px"] == 1024  # readback-only rule unchanged
    t = mm.texel(rb, {1001: 2048})
    assert t["texture_px_source"] == "package diffuse PNG" and t["texture_px"] == [2048]
    assert t["min_px_m"] == pytest.approx(1024, rel=1e-3)
