"""TEC26 OKS 3 truba texture normaliser. Desktop maps_truba is never opened."""
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "jobs" / "tec26-oks" / "make_textures.py"
MATERIALS = ROOT / "jobs" / "tec26-oks" / "materials.json"
PLANNED_D1 = "T_Truba_1_003_Main_d_1.png"

# Measured on the source swatches (card census). Independent of materials.json.
MEASURED = {
    "blu.png": (0, 124, 176),
    "dark_gray.png": (173, 173, 173),
    "dark_gray2.png": (128, 128, 128),
    "gray.png": (208, 208, 208),
    "red.png": (195, 65, 65),
}
RAILING = "railing_10mx1_2m_8posts_RGBA_2048.png"
STUB = 256  # solid diffuse/opacity plate and VPM ERM/Normal stub
NPM_RM = 128  # constant NPM roughness/metallic placeholder
RAIL_PX = 64  # smaller than the stub so a resized-to-stub railing fails this test
NPM_SUFFIXES = ("d", "r", "m", "o")


def load_module():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    spec = importlib.util.spec_from_file_location("tec26_oks_make_textures", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.assert_finite)
    assert callable(module.main)
    return module


def write_solid(path, rgb, size=8):
    Image.new("RGB", (size, size), rgb).save(path)


def write_railing(path, size=RAIL_PX):
    rgb = np.zeros((size, size, 3), np.uint8)
    rgb[..., 0] = 40
    rgb[..., 1] = 80
    # uint32: a uint8/uint16 ramp overflows once size > 256 and would flatten the witness.
    column = (np.arange(size, dtype=np.uint32) % 256).astype(np.uint8)
    rgb[..., 2] = column[None, :]
    alpha = (np.arange(size, dtype=np.uint32) * 255 // (size - 1)).astype(np.uint8)
    alpha = np.broadcast_to(alpha[:, None], (size, size)).copy()
    Image.fromarray(np.dstack([rgb, alpha]), "RGBA").save(path)
    return rgb, alpha


def write_sources(src: Path):
    src.mkdir(parents=True, exist_ok=True)
    for name, rgb in MEASURED.items():
        write_solid(src / name, rgb)
    rgb, alpha = write_railing(src / RAILING)
    return rgb, alpha


def run_cli(src: Path, out: Path, sums: Path, materials: Path | None = None):
    command = [sys.executable, str(SCRIPT), "--src", str(src), "--out", str(out), "--sums", str(sums)]
    if materials is not None:
        command.extend(["--materials", str(materials)])
    return subprocess.run(command, capture_output=True, text=True)


def pngs(out: Path):
    return sorted(p for p in out.glob("*.png") if p.is_file()) if out.exists() else []


def assert_rgb24(path: Path):
    with Image.open(path) as im:
        assert im.mode == "RGB", path.name
        assert im.getbands() == ("R", "G", "B"), path.name
        assert "A" not in im.getbands()
        return im.size, np.array(im)


def test_normalised_set_rgb_names_sizes_and_colours(tmp_path):
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    sums = tmp_path / "SHA256SUMS.txt"
    rail_rgb, rail_alpha = write_sources(src)
    proc = run_cli(src, out, sums)
    assert proc.returncode == 0, proc.stderr
    produced = pngs(out)
    assert produced, "no png written"
    assert list(out.glob("T_*_n_*.png")) == []
    for path in produced:
        with Image.open(path) as image:
            if image.mode == "RGBA":
                assert "_Diffuse_" in path.name
            else:
                assert_rgb24(path)

    by_suffix = {suffix: sorted(out.glob(f"T_*_{suffix}_*.png")) for suffix in NPM_SUFFIXES}
    for suffix, files in by_suffix.items():
        assert len(files) == 6, suffix
        for path in files:
            assert path.name.startswith("T_")
            assert f"_{suffix}_" in path.name

    for kind in ("Diffuse", "ERM", "Normal"):
        files = sorted(out.glob(f"T_*_{kind}_1.10*.png"))
        assert len(files) == 6, kind
        for path in files:
            assert path.match(f"T_*_{kind}_1.10??.png") or path.name.split("_1.")[-1][:4].isdigit()
            stem = path.stem
            udim = stem.rsplit(".", 1)[-1]
            assert udim.startswith("10") and len(udim) == 4

    solids = []
    railing_d = []
    for path in by_suffix["d"]:
        size, arr = assert_rgb24(path)
        if arr.reshape(-1, 3).std(axis=0).sum() == 0:
            solids.append((size, tuple(int(v) for v in arr[0, 0])))
        else:
            railing_d.append((path, size, arr))
    assert {rgb for _size, rgb in solids} == set(MEASURED.values())
    assert {size for size, _rgb in solids} == {(STUB, STUB)}
    assert len(railing_d) == 1
    _path, size, arr = railing_d[0]
    assert size == (RAIL_PX, RAIL_PX)
    assert np.array_equal(arr, rail_rgb)

    opacity = []
    for path in by_suffix["o"]:
        size, arr = assert_rgb24(path)
        opacity.append((size, arr))
    full_opacity = [arr for size, arr in opacity if size == (RAIL_PX, RAIL_PX)]
    stub_opacity = [arr for size, arr in opacity if size == (STUB, STUB)]
    assert len(full_opacity) == 1
    assert len(stub_opacity) == 5
    rail_o = full_opacity[0]
    assert np.array_equal(rail_o[..., 0], rail_alpha)
    assert np.array_equal(rail_o[..., 1], rail_alpha)
    assert np.array_equal(rail_o[..., 2], rail_alpha)
    for arr in stub_opacity:
        assert set(np.unique(arr)) == {255}

    for suffix in ("r", "m"):
        assert len(by_suffix[suffix]) == 6
        for path in by_suffix[suffix]:
            size, _arr = assert_rgb24(path)
            assert size == (NPM_RM, NPM_RM)

    # Solids: VPM Diffuse is the same RGB plate. The railing keeps source alpha.
    vpm_solids = []
    vpm_rail = []
    for path in sorted(out.glob("T_*_Diffuse_1.10*.png")):
        with Image.open(path) as image:
            image.load()
            arr = np.array(image)
            if image.mode == "RGBA":
                vpm_rail.append((image.size, arr))
            else:
                assert image.mode == "RGB"
                vpm_solids.append((image.size, tuple(int(v) for v in arr[0, 0])))
    assert len(vpm_rail) == 1
    size, arr = vpm_rail[0]
    assert size == (RAIL_PX, RAIL_PX)
    assert np.array_equal(arr[..., :3], rail_rgb)
    assert np.array_equal(arr[..., 3], rail_alpha)
    assert {rgb for _size, rgb in vpm_solids} == set(MEASURED.values())
    assert {size for size, _rgb in vpm_solids} == {(STUB, STUB)}
    for path in list(out.glob("T_*_Normal_1.10*.png")) + list(out.glob("T_*_ERM_1.10*.png")):
        size, _arr = assert_rgb24(path)
        assert size == (STUB, STUB)
    assert sums.is_file()


@pytest.mark.parametrize("kind", ["empty", "partial", "mode_l"])
def test_fail_closed_bad_input_writes_nothing(tmp_path, kind):
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    sums = tmp_path / "SHA256SUMS.txt"
    write_sources(src)
    target = src / "blu.png"
    before = target.read_bytes()
    if kind == "empty":
        target.write_bytes(b"")
    elif kind == "partial":
        target.write_bytes(b"\x89PNG\r\n\x1a\n")
    else:
        Image.new("L", (16, 16), 40).save(target)
    proc = run_cli(src, out, sums)
    assert proc.returncode != 0
    assert pngs(out) == []
    assert not sums.exists()
    assert not list(src.glob("T_*"))
    assert (src / "red.png").is_file()
    assert target.read_bytes() != before or kind == "empty"


def test_fail_closed_output_path_equal_to_input_writes_nothing(tmp_path):
    load_module()
    src = tmp_path / "src"
    write_sources(src)
    victim = src / "red.png"
    digest = hashlib.sha256(victim.read_bytes()).hexdigest()
    sums = tmp_path / "SHA256SUMS.txt"
    proc = run_cli(src, victim, sums)
    assert proc.returncode != 0, proc.stderr
    assert hashlib.sha256(victim.read_bytes()).hexdigest() == digest
    assert sorted(p.name for p in pngs(src)) == sorted([*MEASURED, RAILING])
    assert not list(src.glob("T_*"))
    assert not sums.exists()
    assert not (tmp_path / "out").exists()


def test_nan_and_inf_samples_are_errors():
    module = load_module()
    nan = np.zeros((2, 2, 3), np.float64)
    nan[0, 0, 0] = np.nan
    inf = np.zeros((2, 2, 3), np.float64)
    inf[1, 1, 2] = np.inf
    with pytest.raises(ValueError):
        module.assert_finite(nan)
    with pytest.raises(ValueError):
        module.assert_finite(inf)


def _copy_materials(path: Path) -> bytes:
    payload = MATERIALS.read_bytes()
    path.write_bytes(payload)
    return payload


def test_sums_equal_to_planned_png_preserves_bytes(tmp_path):
    """--sums alias of a planned NPM diffuse must not replace that PNG."""
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    write_sources(src)
    out.mkdir()
    victim = out / PLANNED_D1
    sentinel = b"\x89PNG-sentinel-not-rewritten"
    victim.write_bytes(sentinel)
    proc = run_cli(src, out, victim)
    assert proc.returncode != 0, proc.stderr
    assert victim.read_bytes() == sentinel
    assert sorted(p.name for p in pngs(out)) == [PLANNED_D1]


def test_resolved_sums_alias_of_planned_png_writes_nothing(tmp_path):
    """A not-yet-created planned PNG reached through '..' is still an alias."""
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    write_sources(src)
    sums = out / "nested" / ".." / PLANNED_D1
    proc = run_cli(src, out, sums)
    assert proc.returncode != 0, proc.stderr
    assert not out.exists() or pngs(out) == []
    assert not (out / PLANNED_D1).exists()


def test_sums_equal_to_materials_preserves_json(tmp_path):
    """--sums and --materials as the same JSON path must not rewrite that file."""
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    write_sources(src)
    materials = tmp_path / "materials.json"
    before = _copy_materials(materials)
    proc = run_cli(src, out, materials, materials=materials)
    assert proc.returncode != 0, proc.stderr
    assert materials.read_bytes() == before
    assert pngs(out) == []


def test_hardlink_materials_alias_preserves_bytes(tmp_path):
    """A hard link of the materials JSON passed as --sums is the same file."""
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    write_sources(src)
    materials = tmp_path / "materials.json"
    before = _copy_materials(materials)
    link = tmp_path / "materials-hardlink.json"
    os.link(materials, link)
    proc = run_cli(src, out, link, materials=materials)
    assert proc.returncode != 0, proc.stderr
    assert materials.read_bytes() == before
    assert link.read_bytes() == before
    assert pngs(out) == []


def _open_png(path: Path):
    with Image.open(path) as image:
        image.load()
        return image.mode, image.size, np.array(image)


def _write_profile_sources(src: Path, rail_px: int):
    src.mkdir(parents=True, exist_ok=True)
    for name, rgb in MEASURED.items():
        write_solid(src / name, rgb, size=256)
    return write_railing(src / RAILING, size=rail_px)


def test_railing_4096_npm_capped_and_vpm_alpha_kept(tmp_path):
    """4096 RGBA railing: NPM d/o at 2048 RGB, VPM Diffuse keeps source alpha."""
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    sums = tmp_path / "SHA256SUMS.txt"
    rail_rgb, rail_alpha = _write_profile_sources(src, 4096)
    proc = run_cli(src, out, sums)
    assert proc.returncode == 0, proc.stderr

    railing_d = []
    for path in sorted(out.glob("T_*_d_*.png")):
        mode, size, arr = _open_png(path)
        if arr[..., 0].std() + arr[..., 1].std() + arr[..., 2].std() != 0:
            railing_d.append((mode, size, arr))
    assert len(railing_d) == 1
    mode, size, _arr = railing_d[0]
    assert mode == "RGB"
    assert size == (2048, 2048)

    railing_o = []
    for path in sorted(out.glob("T_*_o_*.png")):
        mode, size, arr = _open_png(path)
        if size == (2048, 2048):
            railing_o.append((mode, arr))
    assert len(railing_o) == 1
    mode, arr = railing_o[0]
    assert mode == "RGB"
    assert arr.shape[2] == 3

    vpm_rgba = []
    for path in sorted(out.glob("T_*_Diffuse_1.10*.png")):
        mode, size, arr = _open_png(path)
        if mode == "RGBA":
            vpm_rgba.append((size, arr))
    assert len(vpm_rgba) == 1
    size, arr = vpm_rgba[0]
    assert size == (4096, 4096)
    assert np.array_equal(arr[..., :3], rail_rgb)
    assert np.array_equal(arr[..., 3], rail_alpha)
    assert list(out.glob("T_*_n_*.png")) == []


def test_mixed_solid_256_and_railing_4096_follow_separate_profiles(tmp_path):
    """One run: 256 RGB swatches and a 4096 RGBA cutout each keep their profile."""
    load_module()
    src = tmp_path / "src"
    out = tmp_path / "out"
    sums = tmp_path / "SHA256SUMS.txt"
    rail_rgb, rail_alpha = _write_profile_sources(src, 4096)
    proc = run_cli(src, out, sums)
    assert proc.returncode == 0, proc.stderr
    assert list(out.glob("T_*_n_*.png")) == []

    solid_d = []
    rail_d = []
    for path in sorted(out.glob("T_*_d_*.png")):
        mode, size, arr = _open_png(path)
        assert mode == "RGB"
        assert arr.shape[2] == 3
        if arr.reshape(-1, 3).std(axis=0).sum() == 0:
            solid_d.append((size, tuple(int(v) for v in arr[0, 0])))
        else:
            rail_d.append(size)
    assert {rgb for _size, rgb in solid_d} == set(MEASURED.values())
    assert {size for size, _rgb in solid_d} == {(256, 256)}
    assert rail_d == [(2048, 2048)]

    solid_o = []
    rail_o = []
    for path in sorted(out.glob("T_*_o_*.png")):
        mode, size, arr = _open_png(path)
        assert mode == "RGB"
        if size == (256, 256):
            solid_o.append(arr)
        else:
            rail_o.append(size)
    assert len(solid_o) == 5
    for arr in solid_o:
        assert set(np.unique(arr)) == {255}
    assert rail_o == [(2048, 2048)]

    for suffix in ("r", "m"):
        files = sorted(out.glob(f"T_*_{suffix}_*.png"))
        assert len(files) == 6
        for path in files:
            mode, size, _arr = _open_png(path)
            assert mode == "RGB"
            assert size == (128, 128)

    vpm_solid = []
    vpm_rail = []
    for path in sorted(out.glob("T_*_Diffuse_1.10*.png")):
        mode, size, arr = _open_png(path)
        if mode == "RGBA":
            vpm_rail.append((size, arr))
        else:
            assert mode == "RGB"
            vpm_solid.append((size, tuple(int(v) for v in arr[0, 0])))
    assert {rgb for _size, rgb in vpm_solid} == set(MEASURED.values())
    assert {size for size, _rgb in vpm_solid} == {(256, 256)}
    assert len(vpm_rail) == 1
    size, arr = vpm_rail[0]
    assert size == (4096, 4096)
    assert np.array_equal(arr[..., :3], rail_rgb)
    assert np.array_equal(arr[..., 3], rail_alpha)

    for path in list(out.glob("T_*_Normal_1.10*.png")) + list(out.glob("T_*_ERM_1.10*.png")):
        mode, size, arr = _open_png(path)
        assert mode == "RGB"
        assert arr.shape[2] == 3
        assert size == (256, 256)
