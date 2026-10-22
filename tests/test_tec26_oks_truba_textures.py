"""TEC26 OKS 3 truba texture normaliser. Desktop maps_truba is never opened."""
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "jobs" / "tec26-oks" / "make_textures.py"

# Measured on the source swatches (card census). Independent of materials.json.
MEASURED = {
    "blu.png": (0, 124, 176),
    "dark_gray.png": (173, 173, 173),
    "dark_gray2.png": (128, 128, 128),
    "gray.png": (208, 208, 208),
    "red.png": (195, 65, 65),
}
RAILING = "railing_10mx1_2m_8posts_RGBA_2048.png"
STUB = 256  # KPP1 size_placeholder
RAIL_PX = 64  # smaller than the stub so a resized-to-stub railing fails this test
NPM_SUFFIXES = ("d", "r", "m", "n", "o")


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
    rgb[..., 2] = np.arange(size, dtype=np.uint8)[None, :]
    alpha = (np.arange(size, dtype=np.uint16)[:, None] * 255 // (size - 1)).astype(np.uint8)
    alpha = np.broadcast_to(alpha, (size, size)).copy()
    Image.fromarray(np.dstack([rgb, alpha]), "RGBA").save(path)
    return rgb, alpha


def write_sources(src: Path):
    src.mkdir(parents=True, exist_ok=True)
    for name, rgb in MEASURED.items():
        write_solid(src / name, rgb)
    rgb, alpha = write_railing(src / RAILING)
    return rgb, alpha


def run_cli(src: Path, out: Path, sums: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--src", str(src), "--out", str(out), "--sums", str(sums)],
        capture_output=True,
        text=True,
    )


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
    for path in produced:
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

    for suffix in ("r", "m", "n"):
        for path in by_suffix[suffix]:
            size, _arr = assert_rgb24(path)
            assert size == (STUB, STUB)

    # VPM diffuse matches the NPM diffuse set (same sizes and colours).
    vpm_d = []
    for path in sorted(out.glob("T_*_Diffuse_1.10*.png")):
        size, arr = assert_rgb24(path)
        vpm_d.append((size, arr))
    assert any(size == (RAIL_PX, RAIL_PX) and np.array_equal(arr, rail_rgb) for size, arr in vpm_d)
    vpm_solids = {tuple(int(v) for v in arr[0, 0]) for size, arr in vpm_d if size == (STUB, STUB)}
    assert vpm_solids == set(MEASURED.values())
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
