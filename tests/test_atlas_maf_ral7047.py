"""Synthetic inputs test the recorded #320 RAL 7047 display approximation."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]
RAL_PATH = ROOT / "tools" / "materials" / "ral_classic.json"
README_PATH = ROOT / "tools" / "materials" / "README.md"
DISCLAIMER = (
    "Values are screen approximations of RAL Classic (sRGB), "
    "for display only, not spectrophotometric matches."
)
TILE = (208, 208, 208)
# Table as it stood before 7047 was added. Every one of these must stay.
PRESERVED = {
    "1013": "#E3D9C6",
    "1015": "#E6D690",
    "1018": "#F8F32B",
    "1021": "#F6B600",
    "2004": "#E25303",
    "3000": "#AF2B1E",
    "3005": "#5E2129",
    "3020": "#CC0605",
    "5002": "#202159",
    "5005": "#1E2460",
    "5010": "#0E294B",
    "5015": "#2271B3",
    "6005": "#114232",
    "6009": "#31372B",
    "6018": "#57A639",
    "6029": "#006F3D",
    "7001": "#8A9597",
    "7004": "#969992",
    "7016": "#383E42",
    "7024": "#474A51",
    "7035": "#D7D7D7",
    "7040": "#989EA1",
    "7044": "#B7B3A8",
    "8014": "#4A3526",
    "8017": "#45322E",
    "9001": "#E9E0D2",
    "9003": "#F4F4F4",
    "9005": "#0A0A0A",
    "9006": "#A5A5A5",
    "9007": "#8F8F8F",
    "9010": "#F1ECE1",
    "9016": "#F6F6F6",
    "9017": "#1C1C1C",
}


@pytest.fixture(scope="module")
def atlas():
    path = ROOT / "tools" / "materials" / "atlas_maf.py"
    spec = importlib.util.spec_from_file_location("atlas_maf_ral7047", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_list(path: Path, color: str, name: str = "screen") -> Path:
    payload = {"materials": [{"name": name, "kind": "solid", "color": color}]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _hex_rgb(value: str) -> tuple[int, int, int]:
    digits = value[1:]
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def _sample_tile(pixels: np.ndarray, entry: dict) -> tuple[int, int, int]:
    """Pixel at the UV-rect centre, checked against the content rect."""

    atlas_size = pixels.shape[0]
    u0, v0, u1, v1 = entry["uv"]
    x = int(((u0 + u1) / 2) * atlas_size)
    y = int((1.0 - (v0 + v1) / 2) * atlas_size)
    cx, cy, cw, ch = entry["content_px"]
    assert cw > 0 and ch > 0
    assert cx <= x < cx + cw
    assert cy <= y < cy + ch
    region = pixels[cy:cy + ch, cx:cx + cw]
    assert np.all(region == region[0, 0])
    sample = tuple(int(channel) for channel in pixels[y, x])
    assert sample == tuple(int(channel) for channel in region[0, 0])
    return sample


def _render(atlas, list_path: Path, png: Path, uv_path: Path):
    code = atlas.main([
        str(list_path),
        "--out-png", str(png),
        "--out-json", str(uv_path),
    ])
    assert code == 0
    with Image.open(png) as image:
        assert image.mode == "RGB"
        assert image.size == (512, 512)
        pixels = np.asarray(image).copy()
    data = json.loads(uv_path.read_text(encoding="utf-8"))
    assert data["atlas_size"] == 512
    assert set(data["materials"]) == {"screen"}
    return pixels, data


def test_ral_7047_forms_match_explicit_hex_tile(atlas, tmp_path):
    images = {}
    samples = {}
    for label, color in (
        ("spaced", "RAL 7047"),
        ("compact", "RAL7047"),
        ("hex", "#D0D0D0"),
    ):
        list_path = _write_list(tmp_path / f"{label}.json", color)
        pixels, data = _render(
            atlas,
            list_path,
            tmp_path / f"{label}.png",
            tmp_path / f"{label}-uv.json",
        )
        images[label] = pixels
        samples[label] = _sample_tile(pixels, data["materials"]["screen"])
        assert samples[label] == TILE
        loaded, atlas_size, _padding = atlas.load_material_list(list_path)
        assert atlas_size == 512
        assert loaded[0].name == "screen"
        assert loaded[0].color == TILE
    assert np.array_equal(images["spaced"], images["hex"])
    assert np.array_equal(images["compact"], images["hex"])


def test_ral_7047_cli_fresh_process(tmp_path):
    source = _write_list(tmp_path / "synthetic.json", "RAL 7047")
    png, uv = tmp_path / "atlas.png", tmp_path / "uv.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/materials/atlas_maf.py"), str(source),
         "--out-png", str(png), "--out-json", str(uv)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "atlas 512x512: 1 materials" in result.stdout
    with Image.open(png) as image:
        assert image.mode == "RGB"
        assert image.size == (512, 512)
        pixels = np.asarray(image).copy()
    mapping = json.loads(uv.read_text(encoding="utf-8"))
    assert set(mapping["materials"]) == {"screen"}
    assert _sample_tile(pixels, mapping["materials"]["screen"]) == TILE


def test_table_records_7047_and_keeps_every_existing_entry():
    payload = json.loads(RAL_PATH.read_text(encoding="utf-8"))
    assert payload["note"] == DISCLAIMER
    assert "screen approximations of RAL Classic" in payload["note"]
    colors = payload["colors"]
    assert colors["7047"] == "#D0D0D0"
    assert set(colors) == set(PRESERVED) | {"7047"}
    for code, hex_value in PRESERVED.items():
        assert colors[code] == hex_value


def test_readme_documents_320_display_approximation():
    text = README_PATH.read_text(encoding="utf-8")
    assert "screen approximations" in text
    assert "7047" in text
    assert "#D0D0D0" in text
    assert "#320" in text
    assert "recorded display approximation" in text
    assert "not an official or spectrophotometric RAL match" in text
    assert "new visual approval" in text


def test_preserved_codes_still_load(atlas, tmp_path):
    list_path = tmp_path / "one.json"
    seen = 0
    for code, hex_value in PRESERVED.items():
        _write_list(list_path, f"RAL {code}")
        loaded, atlas_size, _padding = atlas.load_material_list(list_path)
        assert atlas_size == 512
        assert len(loaded) == 1
        assert loaded[0].color == _hex_rgb(hex_value)
        seen += 1
    assert seen == len(PRESERVED)


def test_ral_0000_is_an_unknown_code_with_no_fallback(atlas, tmp_path, capsys):
    list_path = _write_list(tmp_path / "missing.json", "RAL 0000", name="panel")
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    before = list_path.read_bytes()
    code = atlas.main([
        str(list_path),
        "--out-png", str(png),
        "--out-json", str(uv_path),
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "panel" in captured.err
    assert "unknown RAL code 0000" in captured.err
    assert "#D0D0D0" not in captured.err
    assert not png.exists()
    assert not uv_path.exists()
    assert list_path.read_bytes() == before
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(list_path)
    assert type(caught.value) is atlas.AtlasError
    message = str(caught.value)
    assert "panel" in message
    assert "unknown RAL code 0000" in message


def test_absent_four_digit_codes_never_fall_back(atlas, tmp_path):
    """Synthetic missing codes error by name, with no default colour."""

    list_path = tmp_path / "probe.json"
    checked = 0
    for code in ("0000", "9999"):
        _write_list(list_path, f"RAL{code}", name="probe")
        with pytest.raises(atlas.AtlasError) as caught:
            atlas.load_material_list(list_path)
        assert type(caught.value) is atlas.AtlasError
        message = str(caught.value)
        assert f"unknown RAL code {code}" in message
        assert "probe" in message
        checked += 1
    assert checked == 2


def test_fail_closed_colour_and_paths(atlas, tmp_path, capsys):
    """Empty, partial, non-finite and aliased paths fail and leave the input."""

    raw_cases = {
        "empty": '{ "materials": [] }\n',
        "partial-hex": (
            '{ "materials": [{ "name": "swatch", "kind": "solid", "color": "#D0D0" }] }\n'
        ),
        "blank": (
            '{ "materials": [{ "name": "swatch", "kind": "solid", "color": "" }] }\n'
        ),
        "short-code": (
            '{ "materials": [{ "name": "swatch", "kind": "solid", "color": "RAL 704" }] }\n'
        ),
        "nan": (
            '{ "materials": [{ "name": "swatch", "kind": "solid", "color": NaN }] }\n'
        ),
        "inf": (
            '{ "materials": [{ "name": "swatch", "kind": "solid", "color": Infinity }] }\n'
        ),
        "bool": (
            '{ "materials": [{ "name": "swatch", "kind": "solid", "color": true }] }\n'
        ),
    }
    named = {
        "empty": "empty",
        "partial-hex": "swatch",
        "blank": "swatch",
        "short-code": "swatch",
        "nan": "swatch",
        "inf": "swatch",
        "bool": "swatch",
    }
    for label, body in raw_cases.items():
        list_path = tmp_path / f"{label}.json"
        list_path.write_text(body, encoding="utf-8")
        before = list_path.read_bytes()
        png = tmp_path / f"{label}.png"
        uv_path = tmp_path / f"{label}-uv.json"
        partial = tmp_path / f"{label}.json.partial"
        code = atlas.main([
            str(list_path),
            "--out-png", str(png),
            "--out-json", str(uv_path),
        ])
        captured = capsys.readouterr()
        assert code == 2
        assert captured.err.startswith("error:")
        assert named[label] in captured.err
        assert not png.exists()
        assert not uv_path.exists()
        assert not partial.exists()
        assert list_path.read_bytes() == before

    list_path = _write_list(tmp_path / "alias.json", "#D0D0D0")
    before = list_path.read_bytes()
    partial = tmp_path / "alias.json.partial"
    code = atlas.main([
        str(list_path),
        "--out-png", str(tmp_path / "sub" / ".." / "alias.json"),
        "--out-json", str(partial),
        "--force",
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "alias.json" in captured.err
    assert list_path.read_bytes() == before
    assert not partial.exists()
    assert not (tmp_path / "sub").exists()
