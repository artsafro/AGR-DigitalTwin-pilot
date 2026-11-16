"""#1410: MAF NPM-light tool (plan #425 step 5) + shared UV transfer to the atlas (step 6), one owner each."""
from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


uvr = _load("maf_uv_remap", "tools/materials/maf_uv_remap.py")
mss = _load("maf_site_set_1410", "tools/library/maf_site_set.py")
flora = _load("flora_atlas_1410", "tools/library/flora_atlas_from_scene.py")
light = _load("maf_npm_light", "tools/library/maf_npm_light.py")

RECTS = {"steel": [0.0, 0.0, 0.5, 0.5], "wood": [0.5, 0.5, 1.0, 1.0]}


# ---------------------------------------------------------------- shared UV transfer (step 6)
def _random_mesh(rng):
    coords = [(rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(0, 2)) for _ in range(rng.randint(3, 30))]
    polys, normals, rects = [], [], []
    names = list(RECTS)
    for _ in range(rng.randint(1, 40)):
        polys.append(rng.sample(range(len(coords)), rng.choice((3, 3, 4)) if len(coords) >= 4 else 3))
        normals.append((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        rects.append(RECTS[rng.choice(names)])
    return coords, polys, normals, rects


def test_box_projection_puts_every_corner_inside_its_slot_generated():
    """Probe: 500 random meshes x random slots -> every corner inside its own rect (inset 0.02)."""
    rng = random.Random(1410)
    checked = 0
    for _ in range(500):
        coords, polys, normals, rects = _random_mesh(rng)
        uvs = uvr.box_project_uvs(coords, polys, normals, rects, inset=0.02)
        assert len(uvs) == len(polys)
        for poly, face, rect in zip(polys, uvs, rects):
            assert len(face) == len(poly)
            faces = [("m", face)]
            assert mss.uv_slot_report(faces, {"m": rect})["faces_outside"] == 0
            checked += 1
    assert checked > 5000


@pytest.mark.parametrize("bad, match", [
    (dict(coords=[]), "empty mesh"),
    (dict(polys=[]), "empty mesh"),
    (dict(rects=[None]), "face 0 has no atlas slot"),
    (dict(rects=[[0.5, 0.5, 0.5, 1.0]]), "no area"),
    (dict(rects=[[0.0, 0.0, 1.5, 1.0]]), "leaves the atlas"),
    (dict(rects=[[0.0, 0.0, float("nan"), 1.0]]), "finite"),
    (dict(coords=[(0, 0, 0), (1, 0, 0), (0, float("inf"), 0)]), "vertex 2"),
    (dict(polys=[[0, 1, 7]]), "out of range"),
    (dict(polys=[[0, 1]]), "needs >= 3"),
    (dict(normals=[(0, 0, float("nan"))]), "normal"),
    (dict(normals=[]), "normals"),
    (dict(inset=0.5), "inset"),
    (dict(inset=float("nan")), "inset"),
])
def test_box_projection_fails_closed(bad, match):
    args = dict(coords=[(0, 0, 0), (1, 0, 0), (0, 1, 0)], polys=[[0, 1, 2]], normals=[(0, 0, 1)],
                rects=[RECTS["wood"]], inset=0.02)
    args.update(bad)
    with pytest.raises(uvr.UvRemapError, match=match):
        uvr.box_project_uvs(args["coords"], args["polys"], args["normals"], args["rects"], inset=args["inset"])


def test_one_owner_maf_and_flora_share_the_transfer():
    """MAF rules re-export the owner; Flora tiles give the same bytes as the owner (2000 random pairs)."""
    assert mss.remap_into_rect.__module__ == "maf_uv_remap"
    rng = random.Random(7)
    for _ in range(2000):
        u0, v0 = rng.uniform(0, 0.8), rng.uniform(0, 0.8)
        tile = (u0, v0, rng.uniform(u0 + 0.01, 1.0), rng.uniform(v0 + 0.01, 1.0))
        uv = (rng.random(), rng.random())
        assert flora.remap_uv(uv, tile) == uvr.remap_into_rect(uv, tile)
    with pytest.raises(flora.FloraAtlasError):
        flora.remap_uv((0.5, 0.5), (0.0, 0.0, 1.5, 1.0))   # tile outside the atlas: named, never clamped


def test_builder_uses_the_shared_owner_and_keeps_no_private_projection():
    text = (ROOT / "tools/blender/maf_site_set_build.py").read_text(encoding="utf-8")
    assert "mss.uv_remap.box_project_uvs(" in text
    assert "span[a]" not in text and "remap_into_rect((s, t)" not in text


@pytest.mark.parametrize("st, rect, inset", [
    ((0.5, 0.0), [0.5, 0.5, 0.4, 1.0], 0.0),            # zero/negative-area rect
    ((-0.1, 0.5), RECTS["wood"], 0.0),                   # outside [0, 1]
    ((float("nan"), 0.5), RECTS["wood"], 0.0),           # NaN
    ((0.5, 0.5), RECTS["wood"], -0.01),                  # negative inset
    ((0.5, 0.5), RECTS["wood"][:3], 0.0),                # rect of three numbers
])
def test_remap_into_rect_rejects_bad_input(st, rect, inset):
    with pytest.raises(ValueError):
        uvr.remap_into_rect(st, rect, inset)


# ---------------------------------------------------------------- floor rule (step 5)
def test_light_ratio_floor_is_inclusive_and_fail_closed():
    assert mss.light_ratio(400, 0.5, 400) == (1.0, "refused_floor")       # exactly at the floor: refused
    assert mss.light_ratio(401, 0.5, 400) == (0.5, "decimated")
    assert mss.light_ratio(158, 0.5, 400) == (1.0, "refused_floor")
    assert mss.light_ratio(900, 1.0, 400) == (1.0, "kept")
    assert mss.light_ratio(900, 0.5, None) == (0.5, "decimated")
    for ratio in (0.0, -0.1, 1.01, float("nan"), float("inf"), True, "0.5"):
        with pytest.raises(ValueError):
            mss.light_ratio(900, ratio, 400)
    for tris in (0, -1, 1.5, True):
        with pytest.raises(ValueError):
            mss.light_ratio(tris, 0.5, 400)
    with pytest.raises(ValueError):
        mss.light_ratio(900, 0.5, -1)


def test_light_ratio_generated_never_lightens_at_or_under_floor():
    rng = random.Random(400)
    for _ in range(3000):
        tris, floor = rng.randint(1, 2000), rng.randint(0, 1000)
        ratio = rng.choice((1.0, rng.uniform(0.01, 0.99)))
        got, why = mss.light_ratio(tris, ratio, floor)
        if tris <= floor:
            assert (got, why) == (1.0, "refused_floor")
        else:
            assert got == ratio and why in ("kept", "decimated")


# ---------------------------------------------------------------- spec fail-closed
def _spec(tmp_path, **over):
    src = tmp_path / "in"
    src.mkdir(exist_ok=True)
    (src / "a.fbx").write_bytes(b"fbx-a")
    (src / "atlas.png").write_bytes(b"png")
    (src / "atlas.json").write_text(json.dumps({"materials": {k: {"uv": v} for k, v in RECTS.items()}}),
                                    encoding="utf-8")
    row = {"set_id": "SYN_01", "catalogue_id": "MAF_9999", "source_fbx": "a.fbx", "decimate_ratio": 0.5,
           "material_map": {"src_wood": "wood"}, "height_rule": "overall"}
    spec = {"schema": light.SCHEMA, "set": "SYN", "atlas_json": "atlas.json", "atlas_png": "atlas.png",
            "smoothing_deg": 40.0, "positions": [row]}
    for k, v in over.items():
        if k.startswith("row_"):
            if v is KeyError:
                row.pop(k[4:])
            else:
                row[k[4:]] = v
        elif v is KeyError:
            spec.pop(k)
        else:
            spec[k] = v
    path = src / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


@pytest.mark.parametrize("over, match", [
    (dict(schema="x/1"), "schema"),
    (dict(extra=1), "unknown key"),
    (dict(positions=[]), "positions"),
    (dict(set="../x"), "set"),
    (dict(atlas_json="missing.json"), "atlas_json"),
    (dict(smoothing_deg=float("nan")), "smoothing_deg"),
    (dict(smoothing_deg=0), "smoothing_deg"),
    (dict(floor_tris=-1), "floor_tris"),
    (dict(floor_tris=True), "floor_tris"),
    (dict(iou_min=0), "iou_min"),
    (dict(iou_min=1.01), "iou_min"),
    (dict(row_decimate_ratio=0), "decimate_ratio"),
    (dict(row_decimate_ratio=1.5), "decimate_ratio"),
    (dict(row_decimate_ratio=KeyError), "decimate_ratio"),
    (dict(row_material_map={}), "material_map"),
    (dict(row_material_map={"src_wood": "gold"}), "'gold' does not exist"),
    (dict(row_set_id="a/b"), "set_id"),
    (dict(row_source_fbx="nope.fbx"), "source_fbx"),
    (dict(row_height_rule="up"), "height_rule"),
    (dict(row_colour="red"), "unknown key"),
])
def test_spec_fails_closed_naming_the_key(tmp_path, over, match):
    path = _spec(tmp_path, **over)
    with pytest.raises(light.SpecError, match=match):
        light.load_spec(path)


def test_spec_rejects_duplicate_ids_and_clashing_source_names(tmp_path):
    path = _spec(tmp_path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["positions"].append(dict(spec["positions"][0], set_id="syn_01"))
    path.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(light.SpecError, match="duplicate"):
        light.load_spec(path)
    other = tmp_path / "in" / "sub"
    other.mkdir()
    (other / "a.fbx").write_bytes(b"other content")
    spec["positions"][1] = dict(spec["positions"][0], set_id="SYN_02", source_fbx="sub/a.fbx")
    path.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(light.SpecError, match="other content"):
        light.load_spec(path)


def test_output_that_is_or_contains_an_input_exits_2_and_writes_nothing(tmp_path):
    path = _spec(tmp_path)
    before = sorted(p.name for p in (tmp_path / "in").rglob("*"))
    for out in (tmp_path / "in", tmp_path / "in" / "a.fbx", tmp_path, tmp_path / "in" / "spec.json"):
        with pytest.raises(light.SpecError, match="--out"):
            light.run(path, out, dcc=lambda *a: pytest.fail("dcc must not run"))
    assert light.main([str(path), "--out", str(tmp_path / "in")]) == 2
    assert sorted(p.name for p in (tmp_path / "in").rglob("*")) == before


# ---------------------------------------------------------------- gates
def _box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    q = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return np.array([[v[a], v[b], v[c]] for a, b, c, d in q for a, b, c in ((a, b, c), (a, c, d))], dtype=float)


def test_silhouette_iou_values_and_fail_closed():
    a = _box((0, 0, 0), (1, 1, 1))
    assert light.silhouette_iou(a, a)["min"] == 1.0
    half = light.silhouette_iou(a, _box((0, 0, 0), (1, 1, 0.5)))
    assert half["z"] == 1.0 and abs(half["x"] - 0.5) < 0.02 and abs(half["min"] - 0.5) < 0.02
    assert light.silhouette_iou(a, _box((5, 5, 5), (6, 6, 6)))["min"] == 0.0
    for bad in (np.zeros((0, 3, 3)), np.full((1, 3, 3), np.nan)):
        with pytest.raises(ValueError):
            light.silhouette_iou(a, bad)


def _entry(npm_size=(1.0, 1.0, 1.0), outside=0, light_kind="decimated", tris=(12, 12)):
    def role(size, t, kind):
        return {"light": kind, "decimate_ratio": 0.5, "fbx": "x.fbx",
                "readback": {"size_m": list(size), "triangles": t, "uv_slots": {"faces_outside": outside}}}
    return {"set_id": "S", "full": role((1.0, 1.0, 1.0), tris[0], "kept"), "npm": role(npm_size, tris[1], light_kind)}


def test_gate_row_thresholds_exact_and_fail_closed():
    box = _box((0, 0, 0), (1, 1, 1))
    iou = light.silhouette_iou(box, box)["min"]
    assert light.gate_row(_entry(), box, box, iou)["passed"]                           # exactly at threshold: pass
    at_tol = _entry(npm_size=(1.0 + mss.DIMENSION_TOL_M, 1.0, 1.0))
    assert light.gate_row(at_tol, box, box, 0.95)["passed"]                            # D094: 0.1 m passes
    over = light.gate_row(_entry(npm_size=(1.11, 1.0, 1.0)), box, box, 0.95)
    assert not over["passed"] and "dims" in over["reasons"][0]
    nan = light.gate_row(_entry(npm_size=(float("nan"), 1.0, 1.0)), box, box, 0.95)
    assert not nan["passed"]
    uv = light.gate_row(_entry(outside=1), box, box, 0.95)
    assert not uv["passed"] and any("uv" in r for r in uv["reasons"])
    shrunk = light.gate_row(_entry(), box, _box((0, 0, 0), (1, 1, 0.5)), 0.95)
    assert not shrunk["passed"] and any("silhouette" in r for r in shrunk["reasons"])
    floor = light.gate_row(_entry(light_kind="refused_floor", tris=(12, 10)), box, box, 0.95)
    assert not floor["passed"] and any("floor" in r for r in floor["reasons"])


# ---------------------------------------------------------------- run() with a fake DCC (Max adapter protocol)
def _fake_dcc(npm_box=((0, 0, 0), (1, 1, 1)), drop=False, touch_source=None):
    def dcc(config, atlas_json, atlas_png, out):
        cfg = json.loads(Path(config).read_text(encoding="utf-8"))
        assert cfg["roles"] == ["full", "npm"] and cfg["dump_triangles"] and cfg["npm_floor_tris"] == 400
        positions = []
        for pos in cfg["positions"][: (0 if drop else None)]:
            entry = {"set_id": pos["set_id"]}
            for role, box in (("full", ((0, 0, 0), (1, 1, 1))), ("npm", npm_box)):
                tri = _box(*box)
                (out / "readback" / role).mkdir(parents=True, exist_ok=True)
                np.save(out / "readback" / role / (pos["set_id"] + ".npy"), tri)
                size = [b - a for a, b in zip(*box)]
                entry[role] = {"light": "decimated" if role == "npm" else "kept", "decimate_ratio": 0.5,
                               "fbx": str(out / role / "x.fbx"),
                               "readback": {"size_m": size, "triangles": len(tri),
                                            "uv_slots": {"faces_outside": 0}}}
            positions.append(entry)
        if touch_source:
            Path(touch_source).write_bytes(b"changed")
        (out / "build-report.json").write_text(json.dumps({"positions": positions}), encoding="utf-8")
    return dcc


def test_run_pass_fail_drop_error_and_source_guard(tmp_path):
    path = _spec(tmp_path)
    code, rep = light.run(path, tmp_path / "o1", dcc=_fake_dcc())
    assert code == 0 and rep["passed"] and rep["sources_unchanged"] and len(rep["rows"]) == 1
    assert (tmp_path / "o1" / "src" / "a.fbx").read_bytes() == b"fbx-a"
    assert json.loads((tmp_path / "o1" / "npm-light-report.json").read_text(encoding="utf-8"))["status"] == "pass"
    code, rep = light.run(path, tmp_path / "o2", dcc=_fake_dcc(npm_box=((0, 0, 0), (1, 1, 0.5))))
    assert code == 3 and not rep["passed"]
    code, rep = light.run(path, tmp_path / "o3", dcc=_fake_dcc(drop=True))
    assert code == 3 and rep["dropped"] == [{"set_id": "SYN_01", "reason": "missing from the build report"}]

    def boom(*a):
        raise RuntimeError("blender died")
    code, rep = light.run(path, tmp_path / "o4", dcc=boom)
    assert code == 1 and "blender died" in rep["error"] and rep["status"] == "error"
    code, rep = light.run(path, tmp_path / "o5", dcc=_fake_dcc(touch_source=tmp_path / "in" / "a.fbx"))
    assert code == 1 and rep["sources_unchanged"] is False


# ---------------------------------------------------------------- CLI: one command, fresh process
def test_cli_dt_derive_and_agr_alias_route_to_the_tool(tmp_path):
    from dt_ai.cli import agr, shared_tools
    assert agr.ALIASES["npm-light"] == ["derive", "maf-npm-light"]
    argv = shared_tools.command(ROOT, "derive", "maf-npm-light", ["spec.json", "--out", "x"])
    assert Path(argv[1]).resolve() == (ROOT / "tools/library/maf_npm_light.py").resolve()
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    proc = subprocess.run([sys.executable, "-m", "dt_ai.cli.main", "derive", "maf-npm-light", str(bad),
                           "--out", str(tmp_path / "out")], capture_output=True, text=True, env=env, cwd=str(ROOT))
    assert proc.returncode == 2 and "schema" in proc.stderr
    assert not (tmp_path / "out").exists()


def test_route_map_npm_stage_has_the_command():
    import yaml
    events = yaml.safe_load((ROOT / "docs/architecture/maf-route.events.yaml").read_text(encoding="utf-8"))
    npm = next(s for s in events["stages"] if s["id"] == "npm")
    assert npm["commands"] == ["dt derive maf-npm-light", "agr npm-light"]
    assert {"npm-light-tool", "uv-remap"}.isdisjoint({h["id"] for h in events["hotspots"]})


# ---------------------------------------------------------------- real Blender (opt-in when Blender is installed)
from twinqa.scene import find_blender  # noqa: E402

BLENDER = find_blender()
_SYNTH = """
import bpy, sys
fbx, png = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.5)
o = bpy.context.active_object
o.data.materials.append(bpy.data.materials.new('src_wood'))
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True)
img = bpy.data.images.new('atlas', 8, 8)
img.filepath_raw = png
img.file_format = 'PNG'
img.save()
"""


@pytest.mark.skipif(not BLENDER or not Path(BLENDER).is_file(), reason="Blender not installed")
def test_real_blender_one_command_builds_light_npm_on_atlas(tmp_path, monkeypatch):
    path = _spec(tmp_path)
    src = tmp_path / "in"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr", _SYNTH,
                    "--", str(src / "a.fbx"), str(src / "atlas.png")], check=True, capture_output=True, timeout=300)
    monkeypatch.setenv("TWINQA_BLENDER", BLENDER)
    code, rep = light.run(path, tmp_path / "out")
    row = rep["rows"][0]
    assert code == 0, rep
    assert row["light"] == "decimated" and row["tris_npm"] < row["tris_full"] and row["uv_faces_outside"] == 0
    assert row["silhouette_iou"]["min"] >= 0.95 and max(row["dims_dev_m"]) <= mss.DIMENSION_TOL_M
    assert (tmp_path / "out" / "npm" / "SYN_01.fbx").is_file()
    assert math.isclose(sum(1 for _ in (tmp_path / "out" / "src").iterdir()), 1)
    shutil.rmtree(tmp_path / "out")
