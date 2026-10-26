"""windows-glazing class metrics and variant geometry on tiny synthetic inputs (#721)."""
from __future__ import annotations

import json
import math

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
