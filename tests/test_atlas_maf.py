"""Packer tests for the shared 512 MAF atlas."""

import ast
import importlib.util
import json
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]
RAL_CODES = {
    "1013", "1015", "1018", "1021", "2004", "3000", "3005", "3020",
    "5002", "5005", "5010", "5015", "6005", "6009", "6018", "6029",
    "7001", "7004", "7016", "7024", "7035", "7040", "7044", "8014",
    "8017", "9001", "9003", "9005", "9006", "9007", "9010", "9016",
    "9017",
}


@pytest.fixture(scope="module")
def atlas():
    path = ROOT / "tools" / "materials" / "atlas_maf.py"
    spec = importlib.util.spec_from_file_location("atlas_maf", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checker(path: Path, color_a: tuple[int, int, int], color_b: tuple[int, int, int]) -> None:
    image = Image.new("RGB", (32, 32))
    pixels = image.load()
    for y in range(32):
        for x in range(32):
            pixels[x, y] = color_a if (x // 4 + y // 4) % 2 == 0 else color_b
    image.save(path)


def _write_list(path: Path, materials: list[dict], **extra) -> Path:
    payload = {"materials": materials, **extra}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def fifteen_list(tmp_path: Path) -> Path:
    textures = {
        "paving": ((180, 40, 40), (240, 210, 180)),
        "timber": ((120, 70, 30), (190, 140, 80)),
        "tile": ((40, 80, 160), (220, 220, 230)),
        "mesh": ((30, 30, 30), (180, 180, 180)),
    }
    for name, (color_a, color_b) in textures.items():
        _checker(tmp_path / f"{name}.png", color_a, color_b)
    solids = [
        {"name": "plaster", "kind": "solid", "color": "#E8E4DA"},
        {"name": "brick", "kind": "solid", "color": "#8C3A2F"},
        {"name": "glass", "kind": "solid", "color": "#c5d8e8"},
        {"name": "metal", "kind": "solid", "color": "RAL 9006"},
        {"name": "frame", "kind": "solid", "color": "RAL 7016"},
        {"name": "leaf", "kind": "solid", "color": "RAL 6018"},
        {"name": "signal", "kind": "solid", "color": "RAL 3020"},
        {"name": "sky", "kind": "solid", "color": "RAL5015"},
        {"name": "paper", "kind": "solid", "color": "#F4F1EA"},
        {"name": "coping", "kind": "solid", "color": "RAL 9016"},
        {"name": "post", "kind": "solid", "color": "RAL 9005", "size": 128},
    ]
    patterned = [
        {"name": name, "kind": "patterned", "texture": f"{name}.png"}
        for name in textures
    ]
    return _write_list(tmp_path / "fifteen.json", solids + patterned)


def test_ral_table_covers_the_required_codes():
    payload = json.loads((ROOT / "tools" / "materials" / "ral_classic.json").read_text(encoding="utf-8"))
    assert "screen approximations of RAL Classic" in payload["note"]
    colors = payload["colors"]
    assert RAL_CODES <= set(colors)
    assert colors["9005"] == "#0A0A0A"
    for code, hex_value in colors.items():
        assert len(code) == 4 and code.isdigit()
        assert hex_value.startswith("#") and len(hex_value) == 7


def test_fifteen_materials_pack(atlas, fifteen_list, tmp_path):
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    code = atlas.main([str(fifteen_list), "--out-png", str(png), "--out-json", str(uv_path)])
    assert code == 0
    image = Image.open(png)
    assert image.mode == "RGB"
    assert image.size == (512, 512)
    data = json.loads(uv_path.read_text(encoding="utf-8"))
    assert data["atlas_size"] == 512
    assert data["padding_px"] == 8
    assert data["v_origin"] == "bottom"
    assert len(data["materials"]) == 15

    materials, atlas_size, padding_px = atlas.load_material_list(fifteen_list)
    assert atlas_size == 512 and padding_px == 8
    by_name = {material.name: material for material in materials}
    assert by_name["plaster"].color == (0xE8, 0xE4, 0xDA)
    assert by_name["glass"].color == (0xC5, 0xD8, 0xE8)
    assert by_name["post"].color == (0x0A, 0x0A, 0x0A)
    assert by_name["post"].size == 128

    expected = {
        "plaster": 64, "brick": 64, "glass": 64, "metal": 64, "frame": 64,
        "leaf": 64, "signal": 64, "sky": 64, "paper": 64, "coping": 64, "post": 128,
        "paving": 256, "timber": 256, "tile": 128, "mesh": 128,
    }
    for name, entry in data["materials"].items():
        size = entry["slot_px"][2]
        assert entry["slot_px"][3] == size
        assert size == expected[name]
        if entry["kind"] == "solid":
            assert size == by_name[name].size
        else:
            assert size >= 128
            assert size >= by_name[name].size


def test_patterned_remaining_space_is_maximal(atlas, fifteen_list):
    materials, atlas_size, padding_px = atlas.load_material_list(fifteen_list)
    slots = atlas.plan_atlas(materials, atlas_size, padding_px)
    used = sum(slot.size * slot.size for slot in slots)
    patterned = [slot for slot in slots if slot.kind == "patterned"]
    assert patterned
    assert any(slot.size > 128 for slot in patterned)
    atlas_area = atlas_size * atlas_size
    for slot in patterned:
        doubled = slot.size * 2
        grown = used + 3 * slot.size * slot.size
        assert doubled > atlas_size or grown > atlas_area


def test_oversized_list_fails_and_cli(atlas, tmp_path, capsys):
    textures = tmp_path / "textures"
    textures.mkdir()
    Image.new("RGB", (4, 4), (20, 40, 60)).save(textures / "swatch.png")
    names = [f"pat{index:02d}" for index in range(1, 18)]
    materials = [
        {"name": name, "kind": "patterned", "texture": "swatch.png", "size": 128}
        for name in names
    ]
    list_path = _write_list(textures / "too-many.json", materials)
    with pytest.raises(atlas.AtlasDoesNotFit) as caught:
        loaded, atlas_size, padding_px = atlas.load_material_list(list_path)
        atlas.plan_atlas(loaded, atlas_size, padding_px)
    message = str(caught.value)
    assert "needed 68" in message
    assert "available 64" in message
    assert "overflow 4" in message
    assert "shrink" in message
    assert "identical colour" in message
    assert "half" not in message
    for name in names:
        assert name in message

    png = tmp_path / "out.png"
    uv_path = tmp_path / "out.json"
    code = atlas.main([str(list_path), "--out-png", str(png), "--out-json", str(uv_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "shrink" in captured.err
    assert not png.exists()
    assert not uv_path.exists()

    wide = [
        atlas.Material(name=f"fill{index:02d}", kind="solid", size=64, index=index)
        for index in range(60)
    ]
    wide.append(atlas.Material(name="cap_a", kind="solid", size=128, index=60))
    wide.append(atlas.Material(name="cap_b", kind="solid", size=128, index=61))
    with pytest.raises(atlas.AtlasDoesNotFit) as wide_caught:
        atlas.plan_atlas(wide)
    wide_message = str(wide_caught.value)
    assert "shrink" in wide_message
    assert "cap_a -> 64 frees 3 cells" in wide_message
    assert "cap_b -> 64 frees 3 cells" in wide_message
    assert "needed 68" in wide_message and "overflow 4" in wide_message

    mixed = [
        atlas.Material(name="big0", kind="patterned", size=256, index=0),
        atlas.Material(name="big1", kind="patterned", size=256, index=1),
        atlas.Material(name="big2", kind="patterned", size=256, index=2),
        atlas.Material(name="cap", kind="solid", size=128, index=3),
    ]
    mixed.extend(
        atlas.Material(name=f"dot{index:02d}", kind="solid", size=64, index=4 + index)
        for index in range(13)
    )
    with pytest.raises(atlas.AtlasDoesNotFit) as mixed_caught:
        atlas.plan_atlas(mixed)
    mixed_message = str(mixed_caught.value)
    assert "shrink" in mixed_message
    assert "cap -> 64 frees 3 cells" in mixed_message
    assert "big0 256 -> 128 (half)" in mixed_message
    assert "big1 256 -> 128 (half)" in mixed_message
    assert "big2 256 -> 128 (half)" in mixed_message


def test_uv_rects_do_not_overlap(atlas, fifteen_list, tmp_path):
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    atlas.build_atlas(fifteen_list, png, uv_path)
    data = json.loads(uv_path.read_text(encoding="utf-8"))
    entries = list(data["materials"].values())
    pad = data["padding_px"]
    size = data["atlas_size"]
    for entry in entries:
        u0, v0, u1, v1 = entry["uv"]
        assert 0 <= u0 < u1 <= 1
        assert 0 <= v0 < v1 <= 1
        cx, cy, cw, ch = entry["content_px"]
        assert entry["uv"] == [
            cx / size,
            1 - (cy + ch) / size,
            (cx + cw) / size,
            1 - cy / size,
        ]
        x, y, side, side_h = entry["slot_px"]
        assert side == side_h
        assert [cx, cy, cw, ch] == [x + pad // 2, y + pad // 2, side - pad, side - pad]
        assert cx >= 0 and cy >= 0 and cx + cw <= size and cy + ch <= size

    for index, left in enumerate(entries):
        for right in entries[index + 1:]:
            assert not _positive_overlap(left["uv"], right["uv"])
            assert _separated(left["content_px"], right["content_px"], pad)


def test_random_lists_pack_when_area_fits(atlas):
    rng = random.Random(184)
    atlas_area = 512 * 512
    for _ in range(300):
        count = rng.randint(1, 40)
        materials = []
        for index in range(count):
            kind = rng.choice(("solid", "patterned"))
            if kind == "solid":
                size = rng.choice((64, 128))
            else:
                size = rng.choice((128, 256, 512))
            materials.append(atlas.Material(name=f"m{index}", kind=kind, size=size, index=index))
        minimum = sum(material.size * material.size for material in materials)
        try:
            slots = atlas.plan_atlas(materials)
        except atlas.AtlasDoesNotFit:
            assert minimum > atlas_area
            continue
        assert minimum <= atlas_area
        assert [slot.name for slot in slots] == [material.name for material in materials]
        by_name = {material.name: material for material in materials}
        for slot in slots:
            material = by_name[slot.name]
            assert slot.kind == material.kind
            assert 0 <= slot.x and 0 <= slot.y
            assert slot.x + slot.size <= 512 and slot.y + slot.size <= 512
            assert slot.size > 0 and slot.size & (slot.size - 1) == 0
            if material.kind == "solid":
                assert slot.size == material.size
            else:
                assert slot.size >= 128
                assert slot.size >= material.size
        for index, left in enumerate(slots):
            for right in slots[index + 1:]:
                assert not _slots_overlap(left, right)


def test_solid_and_pattern_pixels(atlas, fifteen_list, tmp_path):
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    atlas.build_atlas(fifteen_list, png, uv_path)
    image = Image.open(png)
    pixels = np.asarray(image)
    assert pixels.shape == (512, 512, 3)
    data = json.loads(uv_path.read_text(encoding="utf-8"))
    materials, _, padding_px = atlas.load_material_list(fifteen_list)
    by_name = {material.name: material for material in materials}
    covered = np.zeros((512, 512), dtype=bool)
    inset = padding_px // 2
    for name, entry in data["materials"].items():
        x, y, side, _ = entry["slot_px"]
        covered[y:y + side, x:x + side] = True
        material = by_name[name]
        if material.kind == "solid":
            region = pixels[y:y + side, x:x + side]
            color = np.array(material.color, dtype=np.uint8)
            assert np.all(region == color)
            centre = pixels[y + side // 2, x + side // 2]
            assert tuple(int(channel) for channel in centre) == material.color
            continue
        cx, cy, cw, ch = entry["content_px"]
        assert (cx, cy, cw, ch) == (x + inset, y + inset, side - padding_px, side - padding_px)
        assert np.array_equal(pixels[cy - 1, cx:cx + cw], pixels[cy, cx:cx + cw])
        assert np.array_equal(pixels[cy + ch, cx:cx + cw], pixels[cy + ch - 1, cx:cx + cw])
        assert np.array_equal(pixels[cy:cy + ch, cx - 1], pixels[cy:cy + ch, cx])
        assert np.array_equal(pixels[cy:cy + ch, cx + cw], pixels[cy:cy + ch, cx + cw - 1])
    assert not covered.all()
    assert np.all(pixels[~covered] == 128)


def test_unknown_ral_names_the_code(atlas, tmp_path):
    path = _write_list(tmp_path / "list.json", [
        {"name": "door", "kind": "solid", "color": "RAL 9999"},
    ])
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(path)
    message = str(caught.value)
    assert type(caught.value) is atlas.AtlasError
    assert "door" in message
    assert "9999" in message
    assert "hex" in message


def test_bad_hex_names_the_material(atlas, tmp_path):
    path = _write_list(tmp_path / "list.json", [
        {"name": "trim", "kind": "solid", "color": "#12GG56"},
    ])
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(path)
    message = str(caught.value)
    assert "trim" in message
    assert "bad hex" in message


def test_duplicate_name(atlas, tmp_path):
    path = _write_list(tmp_path / "list.json", [
        {"name": "bench", "kind": "solid", "color": "#112233"},
        {"name": "bench", "kind": "solid", "color": "#445566"},
    ])
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(path)
    assert "bench" in str(caught.value)


def test_solid_size_96(atlas, tmp_path):
    path = _write_list(tmp_path / "list.json", [
        {"name": "plaque", "kind": "solid", "color": "#112233", "size": 96},
    ])
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(path)
    message = str(caught.value)
    assert "plaque" in message
    assert "96" in message


def test_patterned_size_64(atlas, tmp_path):
    _checker(tmp_path / "swatch.png", (1, 2, 3), (4, 5, 6))
    path = _write_list(tmp_path / "list.json", [
        {"name": "grate", "kind": "patterned", "texture": "swatch.png", "size": 64},
    ])
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(path)
    message = str(caught.value)
    assert "grate" in message
    assert "64" in message


def test_missing_texture_file(atlas, tmp_path):
    path = _write_list(tmp_path / "list.json", [
        {"name": "decal", "kind": "patterned", "texture": "no-such.png"},
    ])
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(path)
    message = str(caught.value)
    assert "decal" in message
    assert "not found" in message


def test_empty_list(atlas, tmp_path):
    path = _write_list(tmp_path / "list.json", [])
    with pytest.raises(atlas.AtlasError) as caught:
        atlas.load_material_list(path)
    assert "empty" in str(caught.value)


def test_cli_refuses_overwrite(atlas, fifteen_list, tmp_path, capsys):
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    png.write_bytes(b"keep-png")
    code = atlas.main([str(fifteen_list), "--out-png", str(png), "--out-json", str(uv_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "overwrite" in captured.err
    assert png.read_bytes() == b"keep-png"
    assert not uv_path.exists()

    uv_path.write_text("keep-json", encoding="utf-8")
    png.unlink()
    code = atlas.main([str(fifteen_list), "--out-png", str(png), "--out-json", str(uv_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert "overwrite" in captured.err
    assert uv_path.read_text(encoding="utf-8") == "keep-json"
    assert not png.exists()

    code = atlas.main([
        str(fifteen_list), "--out-png", str(png), "--out-json", str(uv_path), "--force",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert png.read_bytes() != b"keep-png"
    assert Image.open(png).size == (512, 512)


def test_deterministic_bytes(atlas, fifteen_list, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    atlas.build_atlas(fifteen_list, first / "atlas.png", first / "atlas.json")
    atlas.build_atlas(fifteen_list, second / "atlas.png", second / "atlas.json")
    assert (first / "atlas.png").read_bytes() == (second / "atlas.png").read_bytes()
    assert (first / "atlas.json").read_bytes() == (second / "atlas.json").read_bytes()


def _two_solids(path: Path, **extra) -> Path:
    return _write_list(path, [
        {"name": "red", "kind": "solid", "color": "#FF0000"},
        {"name": "blue", "kind": "solid", "color": "#0000FF"},
    ], **extra)


@pytest.mark.parametrize("atlas_size", [1024, 256])
def test_rejects_non_512_atlas(atlas, tmp_path, capsys, atlas_size):
    list_path = _two_solids(tmp_path / "list.json", atlas_size=atlas_size)
    out_dir = tmp_path / "missing"
    png = out_dir / "atlas.png"
    uv_path = out_dir / "atlas.json"
    code = atlas.main([str(list_path), "--out-png", str(png), "--out-json", str(uv_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "512" in captured.err
    assert not png.exists()
    assert not uv_path.exists()
    assert not out_dir.exists()


@pytest.mark.parametrize("padding_px", [0, 2, 6])
def test_rejects_padding_below_8(atlas, tmp_path, capsys, padding_px):
    list_path = _two_solids(tmp_path / "list.json", padding_px=padding_px)
    out_dir = tmp_path / "missing"
    png = out_dir / "atlas.png"
    uv_path = out_dir / "atlas.json"
    code = atlas.main([str(list_path), "--out-png", str(png), "--out-json", str(uv_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert ">= 8" in captured.err
    assert not png.exists()
    assert not uv_path.exists()
    assert not out_dir.exists()


@pytest.mark.parametrize("extra", [{}, {"atlas_size": 512, "padding_px": 8}])
def test_default_and_explicit_512_succeed(atlas, tmp_path, extra):
    list_path = _two_solids(tmp_path / "list.json", **extra)
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    code = atlas.main([str(list_path), "--out-png", str(png), "--out-json", str(uv_path)])
    assert code == 0
    raw = png.read_bytes()
    assert raw.startswith(b"\x89PNG")
    image = Image.open(png)
    assert image.mode == "RGB"
    assert image.size == (512, 512)
    data = json.loads(uv_path.read_text(encoding="utf-8"))
    assert data["atlas_size"] == 512
    assert data["padding_px"] == 8
    assert set(data["materials"]) == {"red", "blue"}


@pytest.mark.parametrize("force", [False, True])
def test_same_output_path_is_rejected(atlas, tmp_path, capsys, force):
    list_path = _two_solids(tmp_path / "list.json")
    target = tmp_path / "same.png"
    argv = [str(list_path), "--out-png", str(target), "--out-json", str(target)]
    if force:
        argv.append("--force")
    code = atlas.main(argv)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert not target.exists()


def test_normalised_output_alias_is_rejected(atlas, tmp_path, capsys):
    list_path = _two_solids(tmp_path / "list.json")
    png = tmp_path / "x" / ".." / "atlas.png"
    uv_path = tmp_path / "atlas.png"
    code = atlas.main([str(list_path), "--out-png", str(png), "--out-json", str(uv_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert not uv_path.exists()
    assert not (tmp_path / "x").exists()


@pytest.mark.skipif(os.name != "nt", reason="case-only aliases are Windows paths")
def test_windows_case_alias_is_rejected(atlas, tmp_path, capsys):
    list_path = _two_solids(tmp_path / "list.json")
    png = tmp_path / "Atlas.PNG"
    uv_path = tmp_path / "atlas.png"
    code = atlas.main([str(list_path), "--out-png", str(png), "--out-json", str(uv_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert not png.exists()
    assert not uv_path.exists()


@pytest.mark.parametrize("force", [False, True])
def test_output_equals_material_list(atlas, tmp_path, capsys, force):
    list_path = _two_solids(tmp_path / "list.json")
    before = list_path.read_bytes()
    mtime = list_path.stat().st_mtime_ns
    other = tmp_path / "missing" / "atlas.png"
    argv = [str(list_path), "--out-png", str(other), "--out-json", str(list_path)]
    if force:
        argv.append("--force")
    code = atlas.main(argv)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert list_path.read_bytes() == before
    assert list_path.stat().st_mtime_ns == mtime
    assert not other.exists()
    assert not other.parent.exists()


def test_output_equals_source_texture(atlas, fifteen_list, tmp_path, capsys):
    texture = fifteen_list.parent / "paving.png"
    before = texture.read_bytes()
    mtime = texture.stat().st_mtime_ns
    other = tmp_path / "missing" / "atlas.json"
    code = atlas.main([
        str(fifteen_list),
        "--out-png", str(texture),
        "--out-json", str(other),
        "--force",
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "paving" in captured.err
    assert texture.read_bytes() == before
    assert texture.stat().st_mtime_ns == mtime
    assert not other.exists()
    assert not other.parent.exists()


def test_force_replaces_distinct_outputs(atlas, tmp_path):
    list_path = _two_solids(tmp_path / "list.json")
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    png.write_bytes(b"old-png")
    uv_path.write_text("old-json", encoding="utf-8")
    code = atlas.main([
        str(list_path), "--out-png", str(png), "--out-json", str(uv_path), "--force",
    ])
    assert code == 0
    assert png.read_bytes().startswith(b"\x89PNG")
    image = Image.open(png)
    assert image.mode == "RGB"
    assert image.size == (512, 512)
    data = json.loads(uv_path.read_text(encoding="utf-8"))
    assert data["atlas_size"] == 512
    assert set(data["materials"]) == {"red", "blue"}


def test_pack_shrink_and_layout_rejections(atlas, fifteen_list, tmp_path):
    png = tmp_path / "atlas.png"
    uv_path = tmp_path / "atlas.json"
    assert atlas.main([str(fifteen_list), "--out-png", str(png), "--out-json", str(uv_path)]) == 0
    data = json.loads(uv_path.read_text(encoding="utf-8"))
    entries = list(data["materials"].values())
    assert data["padding_px"] >= 8
    for index, left in enumerate(entries):
        for right in entries[index + 1:]:
            assert not _positive_overlap(left["uv"], right["uv"])
            assert _separated(left["content_px"], right["content_px"], 8)

    solids = [
        {"name": f"s{index:02d}", "kind": "solid", "color": "#112233", "size": 128}
        for index in range(17)
    ]
    crowded = _write_list(tmp_path / "crowded.json", solids)
    with pytest.raises(atlas.AtlasDoesNotFit) as crowded_caught:
        loaded, atlas_size, padding_px = atlas.load_material_list(crowded)
        atlas.plan_atlas(loaded, atlas_size, padding_px)
    crowded_message = str(crowded_caught.value)
    assert "does not fit" in crowded_message
    assert "shrink" in crowded_message

    payload = json.loads(fifteen_list.read_text(encoding="utf-8"))
    payload["atlas_size"] = 1024
    wide = tmp_path / "wide.json"
    wide.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(atlas.AtlasError) as wide_caught:
        loaded, atlas_size, padding_px = atlas.load_material_list(wide)
        atlas.plan_atlas(loaded, atlas_size, padding_px)
    assert type(wide_caught.value) is atlas.AtlasError
    assert "512" in str(wide_caught.value)

    payload["atlas_size"] = 512
    payload["padding_px"] = 2
    tight = tmp_path / "tight.json"
    tight.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(atlas.AtlasError) as tight_caught:
        loaded, atlas_size, padding_px = atlas.load_material_list(tight)
        atlas.plan_atlas(loaded, atlas_size, padding_px)
    assert type(tight_caught.value) is atlas.AtlasError
    assert ">= 8" in str(tight_caught.value)


def test_build_atlas_rejects_identical_outputs(atlas, tmp_path):
    list_path = _two_solids(tmp_path / "list.json")
    target = tmp_path / "absent" / "same.png"
    with pytest.raises(atlas.AtlasError):
        atlas.build_atlas(list_path, target, target)
    assert not target.exists()
    assert not target.parent.exists()


def _positive_overlap(left: list[float], right: list[float]) -> bool:
    lu0, lv0, lu1, lv1 = left
    ru0, rv0, ru1, rv1 = right
    width = min(lu1, ru1) - max(lu0, ru0)
    height = min(lv1, rv1) - max(lv0, rv0)
    return width > 0 and height > 0


def _separated(left: list[int], right: list[int], pad: int) -> bool:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    x_apart = lx + lw + pad <= rx or rx + rw + pad <= lx
    y_apart = ly + lh + pad <= ry or ry + rh + pad <= ly
    return x_apart or y_apart


def _slots_overlap(left, right) -> bool:
    return (
        min(left.x + left.size, right.x + right.size) > max(left.x, right.x)
        and min(left.y + left.size, right.y + right.size) > max(left.y, right.y)
    )


@pytest.mark.parametrize(
    "reference",
    [
        "new-case",
        "docs/domain/patterns/INDEX.md",
        "docs/domain/uv-textures.md",
        "§5.12",
        "§5.4",
    ],
)
def test_documentation_normative_references(reference: str) -> None:
    """Verify atlas_maf.py docstring and tools/materials/README.md contain required references (Issue #197)."""
    module_path = ROOT / "tools" / "materials" / "atlas_maf.py"
    docstring = ast.get_docstring(ast.parse(module_path.read_text(encoding="utf-8")))
    readme_text = (ROOT / "tools" / "materials" / "README.md").read_text(encoding="utf-8")

    assert docstring is not None, "atlas_maf.py must have a module docstring"
    assert reference in docstring, f"atlas_maf.py docstring missing required reference {reference!r}"
    assert reference in readme_text, f"tools/materials/README.md missing required reference {reference!r}"

