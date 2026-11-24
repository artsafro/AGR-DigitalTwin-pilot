"""#1315: Ground site binds every cover ID to a library diffuse map (V005 needs a bound diffuse per material).

Pattern: n/a | new-case: tests/test_ground_site_materials_1315.py - Ground cover -> library diffuse binding.

Synthetic DXF + synthetic textures (tmp library); the real SIL13 spec runs only as a ``job`` test when its
G: drive inputs are present.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dt_ai.geometry import ground_site as gs
from test_ground_site_1406 import ROOT, SITE, make_spec, run

SIL13 = ROOT / "tests/fixtures/ground_1315/sil13-materials.json"


def _library(tmp_path):
    lib = tmp_path / "lib"
    (lib / "42").mkdir(parents=True)
    (lib / "27").mkdir()
    rng = np.random.default_rng(7)
    grass = rng.integers(40, 200, (32, 32, 3), dtype=np.uint8)
    Image.fromarray(grass).save(lib / "42/42_lawn_d_npm_32.png")
    crumb = np.dstack([rng.integers(60, 220, (32, 32), dtype=np.uint8)] * 3)
    crumb[..., 2] //= 2  # yellow-green crumb, nothing like the hatch colour
    Image.fromarray(crumb).convert("RGBA").save(lib / "27/27_crumb_d_npm_32.png")
    return lib


def _materials(lib, **over):
    m = {"library": str(lib), "decision": "synthetic test decision",
         "by_cover": {"1": {"diffuse": "42/42_lawn_d_npm_32.png"},
                      "2": {"diffuse": "27/27_crumb_d_npm_32.png", "recolour": "cover-colour"}}}
    m.update(over)
    return m


def test_cli_binds_library_diffuse_per_cover(tmp_path):
    lib = _library(tmp_path)
    spec, _ = make_spec(tmp_path, materials=_materials(lib))
    r = run(SITE, spec, tmp_path / "out")
    assert r.returncode == 0, r.stderr
    out = tmp_path / "out"
    obj = (out / "SM_SYN_Ground.obj").read_text(encoding="utf-8")
    assert "mtllib SM_SYN_Ground.mtl" in obj
    assert "mtllib SM_SYN_Ground.mtl" in (out / "ground-flat.obj").read_text(encoding="utf-8")
    mtl = gs.read_mtl(out / "SM_SYN_Ground.mtl")
    assert mtl == {"M_SYN_Ground_ID01_Lawn": "T_SYN_Ground_Diffuse_ID01_Lawn.png",
                   "M_SYN_Ground_ID02_Rubber": "T_SYN_Ground_Diffuse_ID02_Rubber.png"}
    # plain map: byte-equal pixels of the library file; recoloured map: mean = hatch background colour
    lawn = np.asarray(Image.open(out / mtl["M_SYN_Ground_ID01_Lawn"]))
    assert np.array_equal(lawn, np.asarray(Image.open(lib / "42/42_lawn_d_npm_32.png").convert("RGB")))
    rubber = np.asarray(Image.open(out / mtl["M_SYN_Ground_ID02_Rubber"]))
    assert rubber.shape == (32, 32, 3)
    assert np.abs(rubber.reshape(-1, 3).mean(0) - (246, 115, 44)).max() < 3
    assert rubber.reshape(-1, 3).std(0).min() > 1  # texture variation kept, not a flat fill
    rep = json.loads((out / "ground-report.json").read_text(encoding="utf-8"))
    mats = {m["slot"]: m for m in rep["stages"]["textures"]["materials"]["slots"]}
    assert mats["ID02_Rubber"]["recolour"] == "cover-colour" and mats["ID02_Rubber"]["target_rgb"] == [246, 115, 44]
    assert mats["ID01_Lawn"]["library_sha256"] == gs.sha256(lib / "42/42_lawn_d_npm_32.png")
    assert rep["stages"]["textures"]["materials"]["decision"] == "synthetic test decision"


@pytest.mark.parametrize("target", [(0, 124, 176), (246, 115, 44), (233, 224, 210), (255, 255, 255)])
def test_recolour_keeps_pattern_when_a_channel_is_at_a_bound(target):
    rng = np.random.default_rng(3)
    src = np.dstack([rng.integers(60, 220, (64, 64), dtype=np.uint8)] * 3)
    out = gs._recoloured(src, target)
    assert np.abs(out.reshape(-1, 3).mean(0) - target).max() < 1.5
    for c in range(3):
        if target[c] in (0, 255):
            assert (out[..., c] == target[c]).all()  # a channel at a bound stays exactly the hatch colour
    free = [c for c in range(3) if 0 < target[c] < 255]
    assert max(out[..., c].std() for c in free) > 3 if free else True  # pattern kept: no flat fill


def test_without_materials_no_mtl_is_written(tmp_path):
    spec, _ = make_spec(tmp_path)
    assert run(SITE, spec, tmp_path / "out").returncode == 0
    assert "mtllib" not in (tmp_path / "out/SM_SYN_Ground.obj").read_text(encoding="utf-8")


@pytest.mark.parametrize("over, msg", [
    ({"by_cover": {"1": {"diffuse": "42/42_lawn_d_npm_32.png"}}}, "cover 2"),
    ({"by_cover": {"1": {"diffuse": "42/missing.png"}, "2": {"diffuse": "42/42_lawn_d_npm_32.png"}}}, "missing.png"),
    ({"by_cover": {"1": {"diffuse": "42/42_lawn_d_npm_32.png", "recolour": "guess"},
                   "2": {"diffuse": "42/42_lawn_d_npm_32.png"}}}, "recolour"),
    ({"by_cover": {"1": {"diffuse": "../42/42_lawn_d_npm_32.png"},
                   "2": {"diffuse": "42/42_lawn_d_npm_32.png"}}}, "inside the library"),
    ({"decision": ""}, "decision"),
])
def test_material_binding_fails_closed(tmp_path, over, msg):
    lib = _library(tmp_path)
    spec, _ = make_spec(tmp_path, materials=_materials(lib, **over))
    r = run(SITE, spec, tmp_path / "out")
    assert r.returncode == 2 and msg in r.stderr, r.stderr
    assert not (tmp_path / "out").exists()


def _sil13_inputs():
    spec = json.loads(SIL13.read_text(encoding="utf-8"))
    return spec, Path(spec["adapter"]["path"]), Path(spec["materials"]["library"])


@pytest.mark.job
@pytest.mark.skipif(not (_sil13_inputs()[1].exists() and _sil13_inputs()[2].is_dir()),
                    reason="SIL13 typed input / material library (Google Drive) not on this PC")
def test_sil13_ground_binds_artem_materials_and_has_no_contacts(tmp_path):
    """SIL13 (#1315 cold run v003 inputs): before, 10 slots without a diffuse (V005) and 2 skirt contact pairs."""
    r = run(SITE, SIL13, tmp_path / "out")
    assert r.returncode == 0, r.stderr
    rep = json.loads((tmp_path / "out/ground-report.json").read_text(encoding="utf-8"))
    assert (rep["xview"]["vertex_pairs"], rep["xview"]["face_pairs"]) == (0, 0)
    assert rep["skirt_export_check"]["status"] == "pass"
    mats = {m["slot"]: m for m in rep["stages"]["textures"]["materials"]["slots"]}
    assert len(mats) == 10 and set(gs.read_mtl(tmp_path / "out/SM_SIL13_Ground.mtl")) == {
        m["material"] for m in mats.values()} == set(rep["readback"]["tiles"])
    lib = {s: m["library_file"].split("/")[0] for s, m in mats.items()}
    assert lib == {"ID01_Rubber1": "27", "ID02_Drive2": "19", "ID03_SeededLawn": "42", "ID04_Perennials": "25",
                   "ID05_Asphalt": "22", "ID06_Rubber6": "27", "ID07_Drive7": "19", "ID08_Rubber8": "27",
                   "ID09_Rubber9": "27", "ID10_RolledLawn": "42"}
    for m in mats.values():
        assert max(m["size_px"]) <= 2048  # NPM map side
        if m["recolour"]:
            assert np.abs(np.subtract(m["mean_rgb"], m["target_rgb"])).max() < 1.5
