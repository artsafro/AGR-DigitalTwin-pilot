"""new-case: NPM export refuses cross-tile faces and a readback check measures NPM UVs vs atlas cells (#1580).

Synthetic layouts and faces only (not a real object). The layout mirrors tools/derive/npm_atlas.py:
2048 px atlas, 409 px cells, 16 px padding per side, region (u0, v0, size) per finish.
"""
import importlib
import importlib.util
import json
import math
import random
from pathlib import Path
from unittest.mock import Mock

import pytest

import validate_package as vp
from test_scene import PROFILES, mesh, rb
from twinqa import npm_uv

ROOT = Path(__file__).resolve().parents[2]
A, CELL, PAD = 2048, 409, 16
REGION = CELL - 2 * PAD
OKS = "0000_Test_K_1_01.fbx"


def export_npm():
    spec = importlib.util.spec_from_file_location("export_npm_1580", ROOT / "tools/derive/export_npm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # no bpy at import time (#1580): pure face classification is testable
    return module


def layout(n=3, cell=CELL, pad=PAD):
    cols = A // cell
    finishes = {}
    for k in range(n):
        cx, cy = (k % cols) * cell, (k // cols) * cell
        region = cell - 2 * pad
        finishes[f"F{k}"] = {"udim": 1001 + k, "u0": (cx + pad) / A, "v0": 1 - (cy + pad + region) / A,
                             "size": region / A}
    return {"atlas": A, "cell": cell, "pad": pad, "region": cell - 2 * pad, "finishes": finishes}


def remap(atlas, finish, u, v):
    """Tile-local (u, v) in [0, 1] -> atlas UV, the export_npm remap."""
    r = atlas["finishes"][finish]
    return [r["u0"] + u * r["size"], r["v0"] + v * r["size"]]


def npm_mesh(faces, name="SM_Test_K_1_001_Main"):
    m = mesh(name=name, materials=("M_Test_K_1_001_Main_1",))
    m["face_geometry"] = {"vertices": [], "polygons": [list(range(len(f))) for f in faces], "polygon_uv": faces}
    return m


def npm_rb(*meshes, images=((A, A),)):
    out = rb(*meshes)
    out["images"] = [{"name": f"T_{i}", "size": list(s), "packed": True} for i, s in enumerate(images)]
    return out


def status(findings):
    assert len(findings) == 1 and findings[0].name == "UV atlas padding"
    return findings[0].status


# ---- export_npm: strict shared face_tile ---------------------------------------------------------------------

def test_straddling_face_is_an_error_naming_object_face_and_tiles():
    mod = export_npm()
    faces = [(0, [(0.2, 0.2), (0.4, 0.2), (0.4, 0.4)]), (7, [(0.9, 0.5), (1.3, 0.5), (1.3, 0.7)])]
    tiles, crossing = mod.classify_faces(faces, "SM_Kpp_1_Main")
    assert [t[:2] for t in tiles] == [(0, 1001)]
    assert crossing == [{"object": "SM_Kpp_1_Main", "face": 7, "tile": 1002, "corner_tiles": [1001, 1002]}]
    text = mod.cross_tile_error(crossing)
    assert "SM_Kpp_1_Main face 7" in text and "1001" in text and "1002" in text


def test_allow_cross_tile_keeps_legacy_move_and_lists_it():
    mod = export_npm()
    faces = [(3, [(0.9, 0.5), (1.3, 0.5), (1.3, 0.7)])]
    tiles, crossing = mod.classify_faces(faces, "M", allow_cross_tile=True)
    assert tiles == [(3, 1002, 1, 0)] and len(crossing) == 1


@pytest.mark.parametrize("du, crosses", [(0.0, False), (1e-6, False), (3e-6, True), (1e-3, True)])
def test_face_tol_threshold(du, crosses):
    mod = export_npm()
    _, crossing = mod.classify_faces([(0, [(0.5, 0.1), (1.0 + du, 0.1), (1.0 + du, 0.3)])], "M")
    assert bool(crossing) is crosses


@pytest.mark.parametrize("corners", [[(math.nan, 0.1), (0.2, 0.1), (0.2, 0.2)], [(0.1, 0.1), (0.2, 0.1)],
                                     [(10.1, 0.1), (10.2, 0.1), (10.2, 0.2)], [(0.1, -0.5), (0.2, -0.5), (0.2, -0.4)],
                                     [(math.inf, 0.1), (0.2, 0.1), (0.2, 0.2)], [("x", 0.1), (0.2, 0.1), (0.2, 0.2)]])
def test_domain_errors_name_object_and_face(corners):
    with pytest.raises(ValueError, match="SM_X_Main face 4"):
        export_npm().classify_faces([(4, corners)], "SM_X_Main")


def test_export_uses_shared_face_tile_not_centroid_arithmetic():
    text = (ROOT / "tools/derive/export_npm.py").read_text(encoding="utf-8")
    main = text[text.index("def main(argv):"):]
    assert "face_udim(" not in main and "calc_center_median() - c" not in main
    assert "_udimtile.face_tile(corners, strict=True)" in text


def test_generated_tile_faces_never_cross():
    """Probe: 2000 random faces fully inside one random tile -> no crossing, tile = the drawn tile."""
    mod, rnd = export_npm(), random.Random(1580)
    for i in range(2000):
        tu, tv = rnd.randrange(10), rnd.randrange(10)
        corners = [(tu + rnd.random(), tv + rnd.random()) for _ in range(rnd.choice((3, 4, 5)))]
        tiles, crossing = mod.classify_faces([(i, corners)], "M")
        assert not crossing and tiles[0][1] == 1001 + tu + 10 * tv


# ---- twinqa.npm_uv readback check -----------------------------------------------------------------------------

def clean_faces(atlas):
    return [[remap(atlas, f, 0, 0), remap(atlas, f, 1, 0), remap(atlas, f, 1, 1), remap(atlas, f, 0, 1)]
            for f in atlas["finishes"]]


def test_clean_layout_passes():
    atlas = layout()
    found = npm_uv.npm_uv_findings(npm_rb(npm_mesh(clean_faces(atlas))), atlas, OKS)
    assert status(found) == "pass"
    assert found[0].data["faces"] == 3 and found[0].measured == pytest.approx(PAD)


def test_face_inside_padding_band_fails():
    atlas = layout()
    faces = clean_faces(atlas)
    faces[1][0][0] -= 8 / A  # one corner 8 px into the 16 px padding band, still inside the cell
    found = npm_uv.npm_uv_findings(npm_rb(npm_mesh(faces)), atlas, OKS)
    assert status(found) == "fail"
    bad = found[0].data["bad"]
    assert bad == [{"mesh": "SM_Test_K_1_001_Main", "face": 1, "finish": "F1", "reason": "padding band",
                    "outside_region_px": 8.0}]


def test_face_crossing_cells_and_outside_every_cell_fail():
    atlas = layout(n=2)
    faces = clean_faces(atlas)
    faces[0][1][0] += 40 / A                     # into the neighbouring cell
    faces.append([[0.99, 0.01], [0.995, 0.01], [0.995, 0.02]])  # no cell holds its centroid
    data = npm_uv.npm_uv_findings(npm_rb(npm_mesh(faces)), atlas, OKS)[0].data
    assert [b["reason"] for b in data["bad"]] == ["crosses cell", "outside every atlas cell"]


@pytest.mark.parametrize("px, expected", [(0.0, "pass"), (0.01, "pass"), (0.05, "fail"), (1.0, "fail")])
def test_exactly_at_region_edge(px, expected):
    atlas = layout(n=1)
    faces = clean_faces(atlas)
    faces[0][2][0] += px / A
    assert status(npm_uv.npm_uv_findings(npm_rb(npm_mesh(faces)), atlas, OKS)) == expected


@pytest.mark.parametrize("case", ["empty", "glass_only", "ucx_only", "no_uv", "partial_uv", "no_faces",
                                  "nan_uv", "two_corners", "readback_failed", "no_atlas_image", "wrong_image"])
def test_fail_closed_inputs(case):
    atlas = layout()
    good = npm_mesh(clean_faces(atlas))
    meshes, images, ok = [good], ((A, A),), True
    if case == "empty":
        meshes = []
    elif case == "glass_only":
        meshes = [npm_mesh(clean_faces(atlas), name="SM_Test_K_1_001_MainGlass")]
    elif case == "ucx_only":
        meshes = [npm_mesh(clean_faces(atlas), name="UCX_SM_Test_K_1_001_Main_001")]
    elif case == "no_uv":
        del good["face_geometry"]["polygon_uv"]
    elif case == "partial_uv":
        good["face_geometry"]["polygon_uv"] = good["face_geometry"]["polygon_uv"][:1]
    elif case == "no_faces":
        good["face_geometry"] = {"vertices": [], "polygons": [], "polygon_uv": []}
    elif case == "nan_uv":
        good["face_geometry"]["polygon_uv"][0][0] = [math.nan, 0.5]
    elif case == "two_corners":
        good["face_geometry"]["polygon_uv"][0] = good["face_geometry"]["polygon_uv"][0][:2]
    elif case == "no_atlas_image":
        images = ()
    elif case == "wrong_image":
        images = ((1024, 1024),)
    r = npm_rb(*meshes, images=images)
    if case == "readback_failed":
        r = {"source": OKS, "readback_ok": False, "error": "boom"}
    assert status(npm_uv.npm_uv_findings(r, atlas, OKS)) == "fail"


@pytest.mark.parametrize("mutate", [
    lambda a: a.update(pad=3), lambda a: a.update(pad=True), lambda a: a.update(atlas=2048.0),
    lambda a: a.update(finishes={}), lambda a: a["finishes"]["F0"].update(u0=math.nan),
    lambda a: a["finishes"]["F0"].update(u0=a["finishes"]["F0"]["u0"] - 13 / A),   # 3 px from its cell edge
    lambda a: a["finishes"]["F1"].update(u0=a["finishes"]["F0"]["u0"], v0=a["finishes"]["F0"]["v0"]),  # same cell
    lambda a: a["finishes"]["F0"].update(size=0.0), lambda a: a["finishes"]["F0"].update(size=1.5),
    lambda a: a.update(cell=1), lambda a: a.pop("finishes"),
])
def test_unusable_layout_fails(mutate):
    atlas = layout()
    faces = clean_faces(atlas)
    mutate(atlas)
    assert status(npm_uv.npm_uv_findings(npm_rb(npm_mesh(faces)), atlas, OKS)) == "fail"


def test_r1_layout_512_8_passes():
    """The approved R1 job layout (512 / 8 [D280]) keeps 8 px per side: a clean face passes."""
    atlas = layout(n=4, cell=512, pad=8)
    assert status(npm_uv.npm_uv_findings(npm_rb(npm_mesh(clean_faces(atlas))), atlas, OKS)) == "pass"


def test_generated_remapped_faces_pass_and_pushed_corners_fail():
    """Probe: 1000 random tile-local faces remapped like export_npm pass; pushing one corner >= 0.1 px past
    its region fails, every time."""
    atlas, rnd = layout(n=20), random.Random(1580)
    names = list(atlas["finishes"])
    for _ in range(1000):
        f = rnd.choice(names)
        face = [remap(atlas, f, rnd.random(), rnd.random()) for _ in range(rnd.choice((3, 4)))]
        assert status(npm_uv.npm_uv_findings(npm_rb(npm_mesh([face])), atlas, OKS)) == "pass"
        r, k = atlas["finishes"][f], rnd.randrange(len(face))
        side, push = rnd.randrange(4), (0.1 + rnd.random() * 30) / A
        face[k] = [[r["u0"] - push, face[k][1]], [r["u0"] + r["size"] + push, face[k][1]],
                   [face[k][0], r["v0"] - push], [face[k][0], r["v0"] + r["size"] + push]][side]
        assert status(npm_uv.npm_uv_findings(npm_rb(npm_mesh([face])), atlas, OKS)) == "fail"


# ---- validate_package --scene: V006 padding never dropped ------------------------------------------------------

def run_validate(tmp_path, monkeypatch, capsys, faces, extra=()):
    fbx = tmp_path / OKS
    fbx.write_bytes(b"synthetic FBX bytes (#1580 test, not a real object)")
    monkeypatch.setattr(vp, "readback", lambda p: npm_rb(npm_mesh(faces)))
    code = vp.main([str(fbx), "--profile", "npm", "--scene", "--json", *extra])
    out = capsys.readouterr()
    report = json.loads(out.out) if out.out.strip() else None
    padding = None if report is None else [f["status"] for s in report["stages"] for f in s["findings"]
                                           if f["name"] == "UV atlas padding"]
    return code, padding, out.err


def test_validate_package_scene_without_atlas_keeps_padding_not_run(tmp_path, monkeypatch, capsys):
    _, padding, _ = run_validate(tmp_path, monkeypatch, capsys, clean_faces(layout()))
    assert padding == ["not_run"]


@pytest.mark.parametrize("push, expected", [(0, "pass"), (8, "fail")])
def test_validate_package_scene_with_atlas(tmp_path, monkeypatch, capsys, push, expected):
    atlas = layout()
    path = tmp_path / "npm_atlas.json"
    path.write_text(json.dumps(atlas), encoding="utf-8")
    faces = clean_faces(atlas)
    faces[0][0][0] -= push / A
    for arg in (str(path), f"{OKS}={path}"):
        _, padding, _ = run_validate(tmp_path, monkeypatch, capsys, faces, ["--npm-atlas", arg])
        assert padding == [expected]


@pytest.mark.parametrize("arg", ["Other_01.fbx={atlas}", "{missing}", "{bad}"])
def test_validate_package_unmapped_or_bad_atlas_is_an_error(tmp_path, monkeypatch, capsys, arg):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(dict(layout(), pad=2)), encoding="utf-8")
    good = tmp_path / "npm_atlas.json"
    good.write_text(json.dumps(layout()), encoding="utf-8")
    arg = arg.format(atlas=good, missing=tmp_path / "missing.json", bad=bad)
    code, padding, err = run_validate(tmp_path, monkeypatch, capsys, clean_faces(layout()), ["--npm-atlas", arg])
    assert code == 2 and padding is None and "--npm-atlas" in err


def test_validate_package_atlas_given_twice_is_an_error(tmp_path, monkeypatch, capsys):
    good = tmp_path / "npm_atlas.json"
    good.write_text(json.dumps(layout()), encoding="utf-8")
    code, _, err = run_validate(tmp_path, monkeypatch, capsys, clean_faces(layout()),
                                ["--npm-atlas", str(good), "--npm-atlas", f"{OKS}={good}"])
    assert code == 2 and "twice" in err


# ---- agr vpm-to-npm: readback after export_npm -----------------------------------------------------------------

def test_vpm_to_npm_runs_uv_readback_after_export(tmp_path, monkeypatch):
    agr = importlib.import_module("dt_ai.cli.agr")
    export = tmp_path / "export" / "fbx"
    export.mkdir(parents=True)
    fbx = export / "0000_Test_01.fbx"
    fbx.write_bytes(b"x")
    (tmp_path / "export" / "export_npm_meta.json").write_text(json.dumps({"fbx": str(fbx)}), encoding="utf-8")
    run = Mock(side_effect=[Mock(returncode=0), Mock(returncode=0), Mock(returncode=1)])
    monkeypatch.setattr(agr.subprocess, "run", run)
    npm = ["m.blend", "spec.json", str(tmp_path / "atlas"), "--index", "2", str(export), "0000"]
    assert agr.main(["vpm-to-npm", "--blender", "b.exe", "s", "a", "--then-npm", *npm]) == 1
    third = run.call_args_list[2].args[0]
    assert third[1:] == ["-m", "twinqa.npm_uv", str(fbx.resolve()), str(tmp_path / "atlas" / "npm_atlas.json"),
                         "--blender", "b.exe"]


def test_vpm_to_npm_without_export_meta_fails_closed(tmp_path, monkeypatch, capsys):
    agr = importlib.import_module("dt_ai.cli.agr")
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(agr.subprocess, "run", run)
    assert agr.main(["vpm-to-npm", "s", "a", "--then-npm", "m", "s", "a", str(tmp_path / "o"), "p"]) == 2
    assert run.call_count == 2 and "NPM UV readback" in capsys.readouterr().err
