"""Tests for tools/flora/build_flora_star.py and jobs/VATUTINO-SITE/flora_species.py (#1146)."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import random
import subprocess
import sys

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


star = _load("build_flora_star", "tools/flora/build_flora_star.py")
sheet = _load("flora_species", "jobs/VATUTINO-SITE/flora_species.py")


def _maps(tmp, name="p", size=64, box=(16, 8, 48, 60), opacity=None):
    a = np.zeros((size, size), np.uint8) if opacity is None else opacity
    if opacity is None:
        x0, y0, x1, y1 = box
        a[y0:y1, x0:x1] = 255
    op, df = tmp / f"{name}_o.png", tmp / f"{name}_d.png"
    Image.fromarray(a).save(op)
    Image.new("RGB", (a.shape[1], a.shape[0]), (40, 120, 40)).save(df)
    return df, op


@pytest.mark.parametrize("kind,tris", [("tree", 8), ("bush", 6)])
def test_star_triangles_height_and_uv(kind, tris):
    m = star.star_mesh(kind, 2.0, (64, 16, 8, 48, 60))
    assert len(m["tris"]) == tris and m["planes"] == tris // 2
    met = star.metrics(m)
    assert met["uv_faces_outside_tile"] == 0
    zs = [v[2] for v in m["verts"]]
    # plant base (bbox bottom) at -SINK; plant height = target; plane only margin-larger
    assert min(zs) <= -star.SINK and abs(met["height_m"] - 2.0) <= 0.2 * 2.0  # FLO-04 readback measure


def test_vpm_shell_closed_and_in_tile():
    npm = star.star_mesh("tree", 5.0, (64, 16, 8, 48, 60))
    vpm = star.vpm_shell(npm, 1012)
    assert len(vpm["tris"]) == 48 and star.closed_planes(vpm) == 4
    assert star.metrics(vpm, 1012)["uv_faces_outside_tile"] == 0
    assert star.metrics(vpm, 1001)["uv_faces_outside_tile"] == 48


@pytest.mark.parametrize("tile", [1000, 1101, True, 1002.0, None, "1002"])
def test_udim_tile_rejected(tile):
    with pytest.raises(star.StarError):
        star.udim_offset(tile)


@pytest.mark.parametrize("h", [0, -1, float("nan"), float("inf"), "2", True])
def test_bad_height_rejected(h):
    with pytest.raises(star.StarError):
        star.star_mesh("bush", h, (64, 16, 8, 48, 60))


def test_unknown_kind_and_bbox_rejected():
    with pytest.raises(star.StarError, match="hedge"):
        star.star_mesh("hedge", 1.0, (64, 16, 8, 48, 60))
    with pytest.raises(star.StarError):
        star.star_mesh("bush", 1.0, (64, 16, 8, 80, 60))


@pytest.mark.parametrize("t", [0.0029, 0.0101, float("nan")])
def test_shell_thickness_outside_flo11_rejected(t):
    with pytest.raises(star.StarError):
        star.vpm_shell(star.star_mesh("bush", 1.0, (64, 16, 8, 48, 60)), 1002, t)


def test_shell_thickness_at_threshold_accepted():
    m = star.star_mesh("bush", 1.0, (64, 16, 8, 48, 60))
    for t in (0.003, 0.01):
        assert star.closed_planes(star.vpm_shell(m, 1002, t)) == 3


def test_plant_bbox_fail_closed(tmp_path):
    _, op = _maps(tmp_path)
    assert star.plant_bbox(op) == (64, 16, 8, 48, 60)
    grey = np.full((64, 64), 128, np.uint8)
    with pytest.raises(star.StarError, match="not binary"):
        star.plant_bbox(_maps(tmp_path, "g", opacity=grey)[1])
    with pytest.raises(star.StarError, match="both"):
        star.plant_bbox(_maps(tmp_path, "e", opacity=np.zeros((64, 64), np.uint8))[1])
    with pytest.raises(star.StarError, match="both"):
        star.plant_bbox(_maps(tmp_path, "f", opacity=np.full((64, 64), 255, np.uint8))[1])
    Image.new("RGBA", (64, 64)).save(tmp_path / "rgba.png")
    with pytest.raises(star.StarError, match="mode"):
        star.plant_bbox(tmp_path / "rgba.png")


def test_probe_star_invariants_bruteforce():
    rng = random.Random(1146)
    n = 0
    for _ in range(500):
        size = rng.choice([64, 512, 2048])
        x0, y0 = rng.randrange(size - 2), rng.randrange(size - 2)
        x1, y1 = rng.randrange(x0 + 1, size + 1), rng.randrange(y0 + 1, size + 1)
        kind, h = rng.choice(["tree", "bush"]), rng.uniform(0.1, 12)
        m = star.star_mesh(kind, h, (size, x0, y0, x1, y1))
        tile = rng.randrange(1001, 1101)
        v = star.vpm_shell(m, tile)
        zs = [p[2] for p in m["verts"]]
        assert len(m["tris"]) == star.PLANES[kind] * 2 and len(v["tris"]) == star.PLANES[kind] * 12
        assert star.metrics(m)["uv_faces_outside_tile"] == 0 and star.metrics(v, tile)["uv_faces_outside_tile"] == 0
        assert star.closed_planes(v) == v["planes"]
        assert min(zs) <= -star.SINK + 1e-9 and max(zs) - min(zs) >= h - 1e-9
        n += 1
    assert n == 500


def _spec(tmp, species, tile=1002):
    p = tmp / "spec.json"
    body = {"species": species}
    if tile is not None:
        body["udim_tile"] = tile
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


def _item(tmp, key="a", **kw):
    df, op = _maps(tmp, key)
    item = {"key": key, "latin": "Synthetica", "kind": "bush", "height_m": 1.0, "band_m": [0.8, 1.2],
            "diffuse": str(df), "opacity": str(op), "material_id": 299}
    item.update(kw)
    return item


def test_cli_geometry_run_and_report(tmp_path):
    out = tmp_path / "out"
    assert star.main(["--spec", str(_spec(tmp_path, [_item(tmp_path)])), "--out", str(out)]) == 0
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["geometry_passed"] is True and rep["passed"] is False
    assert not (tmp_path / "out.partial").exists()


def test_cli_height_out_of_band_fails(tmp_path):
    out = tmp_path / "out"
    assert star.main(["--spec", str(_spec(tmp_path, [_item(tmp_path, height_m=2.0)])), "--out", str(out)]) == 1


@pytest.mark.parametrize("case", ["no_tile", "empty", "dup", "missing_map", "missing_field", "out_exists", "out_alias"])
def test_cli_fail_closed(tmp_path, case):
    items = [_item(tmp_path)]
    tile = 1002
    out = tmp_path / "out"
    if case == "no_tile":
        tile = None
    elif case == "empty":
        items = []
    elif case == "dup":
        items = [_item(tmp_path), _item(tmp_path)]
    elif case == "missing_map":
        items[0]["opacity"] = str(tmp_path / "nope.png")
    elif case == "missing_field":
        del items[0]["material_id"]
    elif case == "out_exists":
        out.mkdir()
    spec = _spec(tmp_path, items, tile)
    if case == "out_alias":
        out = tmp_path  # contains the inputs
    before = sorted(p.name for p in tmp_path.iterdir())
    with pytest.raises(SystemExit) as err:
        star.main(["--spec", str(spec), "--out", str(out)])
    assert err.value.code not in (0, None)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_cli_fresh_process_rejects_existing_out(tmp_path):
    spec = _spec(tmp_path, [_item(tmp_path)])
    (tmp_path / "out").mkdir()
    run = subprocess.run([sys.executable, str(ROOT / "tools/flora/build_flora_star.py"), "--spec", str(spec),
                          "--out", str(tmp_path / "out")], capture_output=True, text=True)
    assert run.returncode != 0 and "refusing" in run.stderr


@pytest.mark.parametrize("key,ok", [
    ("pos03_birch", True), ("a_b-c.d", True), ("tree.01", True),
    ("../escaped", False), ("a/b", False), ("a\\b", False), ("..", False), ("a..b", False),
    ("", False), (None, False), (7, False), ("a b", False), ("кириллица", False),
])
def test_valid_key(key, ok):
    assert star.valid_key(key) is ok


def _raw_item(df, op, key):
    return {"key": key, "latin": "Synthetica", "kind": "bush", "height_m": 1.0, "band_m": [0.8, 1.2],
            "diffuse": str(df), "opacity": str(op), "material_id": 299}


@pytest.mark.parametrize("key", ["../escaped", "a/b"])
def test_cli_rejects_path_escaping_key(tmp_path, key):
    df, op = _maps(tmp_path, "safe")  # real maps inside tmp, key never used to name a file
    spec = _spec(tmp_path, [_raw_item(df, op, key)])
    out = tmp_path / "out"
    before = sorted(p.name for p in tmp_path.iterdir())
    run = subprocess.run([sys.executable, str(ROOT / "tools/flora/build_flora_star.py"), "--spec", str(spec),
                          "--out", str(out)], capture_output=True, text=True)
    assert run.returncode == 2
    assert key in run.stderr
    assert not out.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == before  # nothing written inside or outside --out


def test_cli_accepts_safe_key(tmp_path):
    out = tmp_path / "out"
    assert star.main(["--spec", str(_spec(tmp_path, [_item(tmp_path, "pos03_birch")])), "--out", str(out)]) == 0
    assert (out / "report.json").exists()


def test_species_sheet_numbers_and_fresh():
    recs = sheet.records()
    s = sheet.summary(recs)
    assert (s["rows"], s["plants"], s["trees"], s["bushes"], s["npm_tris_estimate"]) == (18, 4915, 105, 4810, 29700)
    assert s["npm_tris_estimate"] <= 70000
    assert sheet.main(["--check"]) == 0


def test_species_sheet_rejects_bad_rows(monkeypatch):
    orig = list(sheet.ROWS)
    bad = list(orig)
    bad[0] = bad[0][:8] + (None, "approved-exact", 101)
    monkeypatch.setattr(sheet, "ROWS", bad)
    with pytest.raises(ValueError, match="inconsistent"):
        sheet.records()
    bad = list(orig)
    bad[0] = bad[0][:7] + (24,) + bad[0][8:]
    monkeypatch.setattr(sheet, "ROWS", bad)
    with pytest.raises(ValueError, match="4915"):
        sheet.records()


def test_species_sheet_route_a_d237_sources():
    """D245: A101 for 9 and 16; every other non-exact row is a named stand-in from an approved map pair."""
    recs = {r["pos"]: r for r in sheet.records()}
    by = {}
    for pos, r in recs.items():
        by.setdefault(r["route_a"]["source"], set()).add(pos)
    assert by["a101"] == {9, 16}
    assert by["stand-in"] == {2, 4, 5, 6, 7, 8, 10, 13, "Ива"}
    assert by["approved"] == {1, 3, 11, 12, 14, 15, 17}
    maps = json.loads((ROOT / "library/flora/maps-v003-snapshot.json").read_text(encoding="utf-8"))
    for pos in by["stand-in"] | by["approved"]:
        key = recs[pos]["route_a"]["map_key"]
        assert maps[key]["review_status"] == "approved", pos
    assert recs[9]["route_a"]["a101_file"] == "puzyreplodnik_kalinolistnyj_t2_h150_high.png"
    assert recs[16]["route_a"]["a101_file"] == "el_nidiformis_t1_h60_high.png"
    md = (ROOT / "jobs/VATUTINO-SITE/flora-species.md").read_text(encoding="utf-8")
    assert md.count("| stand-in:") == 9 and "D245" in md


def test_species_sheet_route_a_rejects_unapproved_stand_in(monkeypatch):
    bad = dict(sheet.ROUTE_A)
    bad[2] = ("stand-in", "Alnus imaginaria", None)
    monkeypatch.setattr(sheet, "ROUTE_A", bad)
    with pytest.raises(ValueError, match="not an approved"):
        sheet.records()


def _atlas_spec(tmp, items, cells, tile=1002):
    ad, ao = _maps(tmp, "atlas", size=128)
    for it, cell in zip(items, cells):
        it["atlas_cell"] = cell
    spec = {"udim_tile": tile, "atlas": {"diffuse": str(ad), "opacity": str(ao), "size": 128,
                                         "material": "M_TEST_Flora_1"}, "species": items}
    p = tmp / "spec_atlas.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return p


def test_atlas_mode_uv_inside_cell_and_atlas_texel(tmp_path):
    cell = [0.5, 0.25, 0.75, 0.5]
    out = tmp_path / "out"
    spec = _atlas_spec(tmp_path, [_item(tmp_path, "a")], [cell])
    assert star.main(["--spec", str(spec), "--out", str(out)]) == 0
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    sp = rep["species"][0]
    assert sp["atlas"]["uv_faces_outside_cell"] == {"npm": 0, "vpm": 0}
    assert rep["atlas"]["material"] == "M_TEST_Flora_1" and rep["atlas"]["count"] == 1
    meshes = json.loads((out / "meshes.json").read_text(encoding="utf-8"))["a"]
    us = [u for tri in meshes["npm"]["uvs"] for u, _ in tri]
    vs = [v for tri in meshes["npm"]["uvs"] for _, v in tri]
    assert min(us) >= 0.5 - 1e-9 and max(us) <= 0.75 + 1e-9 and min(vs) >= 0.25 - 1e-9 and max(vs) <= 0.5 + 1e-9
    vus = [u for tri in meshes["vpm"]["uvs"] for u, _ in tri]
    assert min(vus) >= 1.5 - 1e-9 and max(vus) <= 1.75 + 1e-9  # tile 1002 = u + 1
    # atlas texel = source px/m x (cell px / source px): 64 px source, cell 0.25 x 128 = 32 px -> half
    assert math.isclose(sp["atlas"]["texel_px_per_m"], sp["vpm"]["texel_px_per_m"] * 32 / 64, rel_tol=1e-3)
    assert meshes["diffuse"] == str(Path(tmp_path / "atlas_d.png").resolve())


@pytest.mark.parametrize("cell", [[0.5, 0.5, 0.4, 0.9], [-0.1, 0, 0.5, 0.5], [0, 0, 1.2, 1], None])
def test_atlas_mode_bad_cell_fails_closed(tmp_path, cell):
    item = _item(tmp_path, "a")
    spec = _atlas_spec(tmp_path, [item], [cell])
    if cell is None:
        data = json.loads(spec.read_text(encoding="utf-8"))
        del data["species"][0]["atlas_cell"]
        spec.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SystemExit) as err:
        star.main(["--spec", str(spec), "--out", str(tmp_path / "out")])
    assert err.value.code not in (0, None) and not (tmp_path / "out").exists()


BLENDER = Path(star.BLENDER)


@pytest.mark.blender
@pytest.mark.skipif(not BLENDER.is_file(), reason="Blender 5.1 not installed")
def test_fbx_readback_blender(tmp_path):
    out = tmp_path / "out"
    spec = _spec(tmp_path, [_item(tmp_path, "a"), _item(tmp_path, "b", kind="tree", material_id=199)])
    assert star.main(["--spec", str(spec), "--out", str(out), "--fbx"]) == 0
    rb = json.loads((out / "report.json").read_text(encoding="utf-8"))["fbx_readback"]
    assert rb["a"]["npm_tris"] == 6 and rb["a"]["vpm_tris"] == 36
    assert rb["b"]["npm_tris"] == 8 and rb["b"]["vpm_tris"] == 48
    assert all(r[f"{p}_uv_outside"] == 0 and r[f"{p}_materials"] == 1 for r in rb.values() for p in ("npm", "vpm"))
    assert math.isclose(rb["a"]["npm_height_m"], 1.0 + star.SINK, rel_tol=0.2)


def test_vpm_atlas_moves_the_shell_into_its_own_cell(tmp_path):
    """[D246] VPM shell samples its own 4096 atlas cell (UDIM 1002); NPM keeps the 2048 atlas cell."""
    item = _item(tmp_path, "a")
    item["vpm_atlas_cell"] = [0.0, 0.5, 0.25, 0.75]
    spec = _atlas_spec(tmp_path, [item], [[0.5, 0.25, 0.75, 0.5]])
    data = json.loads(spec.read_text(encoding="utf-8"))
    vd, vo = _maps(tmp_path, "vatlas", size=256)
    data["vpm_atlas"] = {"diffuse": str(vd), "opacity": str(vo), "size": 256, "material": "M_TEST_Flora_1"}
    spec.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "out"
    assert star.main(["--spec", str(spec), "--out", str(out)]) == 0
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    sp = rep["species"][0]
    meshes = json.loads((out / "meshes.json").read_text(encoding="utf-8"))["a"]
    nus = [u for tri in meshes["npm"]["uvs"] for u, _ in tri]
    vus = [u for tri in meshes["vpm"]["uvs"] for u, _ in tri]
    vvs = [v for tri in meshes["vpm"]["uvs"] for _, v in tri]
    assert min(nus) >= 0.5 - 1e-9 and max(nus) <= 0.75 + 1e-9
    assert min(vus) >= 1.0 - 1e-9 and max(vus) <= 1.25 + 1e-9 and min(vvs) >= 0.5 - 1e-9 and max(vvs) <= 0.75 + 1e-9
    assert sp["vpm_atlas"]["uv_faces_outside_cell"] == 0
    # 0.25 x 256 = 64 px cell vs 0.25 x 128 = 32 px NPM cell -> twice the texel
    assert math.isclose(sp["vpm_atlas"]["texel_px_per_m"], 2 * sp["atlas"]["texel_px_per_m"], rel_tol=1e-3)
    assert meshes["vpm_diffuse"] == str(Path(vd).resolve()) and meshes["diffuse"] == str(Path(tmp_path / "atlas_d.png").resolve())
    assert rep["vpm_atlas"]["size"] == 256
    assert rep["texel_vpm_failures"] == [k for k in ["a"] if not sp["vpm_atlas"]["texel_ok"]]
