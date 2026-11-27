"""D171 panel binding regressions: synthetic geometry and retained AC08 exports."""
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
AC08 = ROOT / "jobs/TEC26-OKS/AC08"
sys.path.insert(0, str(AC08.parent / "scripts"))
import compare_facades  # noqa: E402
import qa_packages  # noqa: E402

DRIVE = Path("G:/Мой диск/AGR-evidence")
WITNESS = DRIVE / "127-ac08-joint-gate"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def synthetic_mesh(width, bottom):
    return {"vertices": [[0, 0, bottom], [width, 0, bottom], [width, 0, bottom + 1], [0, 0, bottom + 1]],
            "faces": [[0, 1, 2], [0, 2, 3]],
            "face_uvs": [[[0, 0.25], [1, 0.25], [1, 0.75]], [[0, 0.25], [1, 0.75], [0, 0.75]]]}


def synthetic_spec(tmp_path):
    sheet = {"facades": {"wall": {"field_width_mm": 1000, "plinth": [{"bbox_mm": [0, 0, 1000, 20]}]}}}
    path = dump(tmp_path / "sheet.json", sheet)
    return {"facades": {"wall": {"normal": "-y", "finish": "panel", "ribs": 2}},
            "finishes": {"panel": {"udim": 1001}}, "sheet": {"facades_json": path}}


@pytest.mark.parametrize("width,bottom,refuse", [
    (0.99, 0, False), (1.01, 0, False), (0.98999, 0, True), (1.01001, 0, True),
    (1, -0.00001, True), (1, 0, False), (1, 0.00001, False),
])
def test_package_qa_checks_both_fields_before_counting(tmp_path, width, bottom, refuse):
    spec = synthetic_spec(tmp_path)
    mesh = synthetic_mesh(width, bottom)
    img = np.full((16, 1000, 3), 220, np.uint8)
    img[:, 496:504] = 10
    atlas = {"finishes": {"panel": {"u0": 0, "v0": 0, "size": 1}}}
    reports = qa_packages.facade_joint_checks(spec, mesh, mesh, {1001: img}, img, atlas)
    for tag, selector in (("vpm", "spec UDIM 1001"), ("npm", "atlas region panel")):
        row = reports[tag]["wall"]
        if refuse:
            assert not row["ok"] and "rows" not in row
            assert f"{selector} is not the panel field of wall" in row["reason"]
        else:
            assert row["ok"] and [r["joints_found"] for r in row["rows"].values()] == [1, 1]


def test_package_qa_names_missing_panel_row(tmp_path):
    spec = synthetic_spec(tmp_path)
    mesh = synthetic_mesh(1, 0)
    img = np.full((16, 16, 3), 220, np.uint8)
    atlas = {"finishes": {"panel": {"u0": 0, "v0": 0, "size": 1}}}
    row = qa_packages.facade_joint_checks(spec, mesh, mesh, {}, img, atlas)["vpm"]["wall"]
    assert not row["ok"] and "VPM wall" in row["reason"] and "no panel samples" in row["reason"]


@pytest.mark.parametrize("profile", ["vpm", "npm"])
@pytest.mark.parametrize("frac,blank_y", [(0.2, 83), (0.95, 35)])
def test_compare_names_no_panel_samples_without_publishing(tmp_path, monkeypatch, capsys, profile, frac, blank_y):
    spec = synthetic_spec(tmp_path)
    image = tmp_path / "blank.png"
    Image.new("RGB", (16, 16), "white").save(image)
    spec["presentation"] = {"image": str(image), "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                            "quadrants": ["wall"], "slide": 0}
    sheet = load(Path(spec["sheet"]["facades_json"]))
    sheet["facades"]["wall"].update(size_mm=[1200, 1000], frame_bands_mm={"left": 100, "right": 100}, joints=1)
    view = {"center": [0.5, 0, 0.5], "right": [1, 0, 0], "up": [0, 0, 1], "ortho_scale": 2, "res": [128, 128]}
    for tag in ("vpm", "npm"):
        render = np.full((128, 128, 3), [0, 120, 180], np.uint8)
        if tag == profile:
            render[blank_y, :] = [255, 255, 255]
        Image.fromarray(render).save(tmp_path / f"{tag}.png")
    dump(tmp_path / "renders.json", {tag: {"views": {"south": dict(view, png=f"{tag}.png")}} for tag in ("vpm", "npm")})
    monkeypatch.setattr(compare_facades.finish_map, "validate_legend", lambda *_: None)
    monkeypatch.setattr(compare_facades, "slide_boxes", lambda _: [(2, 2, 14, 14)])
    monkeypatch.setattr(compare_facades, "slide_count", lambda *_: {
        "joints": 1, "step_mm": 500, "field_mm": 1000, "height_scale_ratio": 1})
    out = tmp_path / "report"
    assert compare_facades.main([dump(tmp_path / "spec.json", spec), dump(tmp_path / "sheet.json", sheet),
                                 str(tmp_path), dump(tmp_path / "fbx.json", {"objects": [
                                     dict(synthetic_mesh(1, 0), name="Main")]}), str(out)]) == 2
    err = capsys.readouterr().err
    assert f"{profile.upper()} wall, z={frac:.3f}: no panel samples" in err
    assert not out.exists()


@pytest.mark.job
@pytest.mark.parametrize("version,finish,udim,rejected", [
    ("v007", None, None, {"А-Б", "Б-А"}),
    ("v010", "PanelVJ12_RAL5015", 1003, {"А-Б", "Б-А"}),
    ("v010", "PanelVJ30_RAL5015", 1004, {"1-2", "2-1"}),
    ("v010", None, None, set()),
])
def test_compare_on_retained_ac08(tmp_path, capsys, version, finish, udim, rejected):
    pilot = WITNESS / f"pilot-{version}"
    slide = DRIVE / "559-tec26-oks-ac08-pilot-v010/slide49.png"
    if not pilot.is_dir() or not slide.is_file():
        pytest.skip("retained #127 AC08 readback, renders or slide not available")
    spec = copy.deepcopy(load(AC08 / "vpm_textures.json"))
    spec["presentation"]["image"] = str(slide)
    if finish:
        spec["finishes"][finish]["udim"] = udim
    out = tmp_path / "report"
    rc = compare_facades.main([dump(tmp_path / "spec.json", spec), str(AC08 / "sheet-facades.json"),
                               str(pilot / "renders_r127"), str(pilot / "vpm.readback.json"), str(out)])
    if rejected:
        assert rc == 2
        err = capsys.readouterr().err
        expected = udim or 1002
        for name in spec["facades"]:
            assert (f"spec UDIM {expected} is not the panel field of {name}" in err) == (name in rejected)
        assert not out.exists()
    else:
        assert rc == 0
        report = load(out / "compare.json")
        assert report == load(pilot / "fcmp_r1/compare.json") | {"slide": str(slide)}
        assert all(p.read_bytes() == (pilot / "fcmp_r1" / p.name).read_bytes() for p in out.glob("*.png"))
