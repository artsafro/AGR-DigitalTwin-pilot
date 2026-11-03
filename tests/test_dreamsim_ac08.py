"""new-case: pure helpers for the AC08 DreamSim advisory experiment.

Shift, planted defects, and fail-closed checks. DreamSim weights are not loaded.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "experiments"))

import dreamsim_ac08 as ds  # noqa: E402


def _rgb(h=20, w=30, fill=0.2):
    img = np.full((h, w, 3), fill, dtype=np.float64)
    if h > 5 and w > 10:
        img[5, 10] = (0.1, 0.8, 0.3)
    return img


def test_shift_moves_content_and_fills_vacated_edge_white():
    src = _rgb()
    out = ds.shift_pixels(src, 2, -1)
    assert out.shape == src.shape
    assert np.allclose(out[4, 12], (0.1, 0.8, 0.3))
    assert np.allclose(out[:, :2], 1.0)
    assert np.allclose(out[-1, :], 1.0)
    assert np.allclose(src[5, 10], (0.1, 0.8, 0.3))


@pytest.mark.parametrize("dx", [1, 2, 3])
def test_shift_one_to_three_pixels_keeps_shape(dx):
    src = _rgb()
    out = ds.shift_pixels(src, dx, 0)
    assert out.shape == src.shape
    assert np.allclose(out[5, 10 + dx], src[5, 10])
    assert np.allclose(out[:, :dx], 1.0)


def test_shifted_band_moves_only_the_band_by_0_1_m():
    src = _rgb(h=40, w=80)
    src[:, :] = 0.4
    src[20, 10] = (0.0, 0.0, 1.0)
    src[5, 10] = (1.0, 0.0, 0.0)
    out = ds.plant_shifted_band(src, px_per_m=200, metres=0.1, band_frac=(0.4, 0.7))
    assert int(round(0.1 * 200)) == 20
    assert np.allclose(out[20, 30], (0.0, 0.0, 1.0))
    assert np.allclose(out[5, 10], (1.0, 0.0, 0.0))
    assert np.allclose(out[20, :20], 1.0)
    assert np.allclose(src[20, 10], (0.0, 0.0, 1.0))


def test_wrong_colour_zone_overwrites_only_that_rectangle():
    src = _rgb(h=20, w=20, fill=0.2)
    out = ds.plant_wrong_colour(src, zone_frac=(0.25, 0.75, 0.25, 0.75), colour=(0.9, 0.1, 0.1))
    assert np.allclose(out[10, 10], (0.9, 0.1, 0.1))
    assert np.allclose(out[0, 0], 0.2)
    assert np.allclose(src[10, 10], 0.2)


def test_missing_rib_replaces_the_dark_column_with_the_neighbour():
    src = np.full((16, 24, 3), 0.7, dtype=np.float64)
    src[:, 12] = 0.05
    out = ds.plant_missing_rib(src)
    assert out[:, 12, 0].mean() > 0.5
    assert np.allclose(out[:, 11], src[:, 11])
    assert np.allclose(src[:, 12], 0.05)


def test_fail_closed_empty_nan_inf_and_shape_mismatch():
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.zeros((0, 4, 3)))
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.array([]))
    bad = _rgb()
    bad[0, 0, 0] = np.nan
    with pytest.raises(ds.InputError):
        ds.require_rgb(bad)
    bad = _rgb()
    bad[0, 0, 1] = np.inf
    with pytest.raises(ds.InputError):
        ds.require_rgb(bad)
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.zeros((4, 4)))
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.zeros((4, 4, 4)))
    with pytest.raises(ds.InputError):
        ds.require_same_shape(_rgb(h=8, w=8), _rgb(h=8, w=9))


def test_output_path_equal_to_input_exits_nonzero_and_writes_nothing(tmp_path: Path):
    src = tmp_path / "in.png"
    Image.fromarray(np.full((6, 6, 3), 40, dtype=np.uint8)).save(src)
    before = src.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    with pytest.raises(SystemExit) as exc:
        ds.main(["write-array", "--input", str(src), "--output", str(src)])
    assert exc.value.code not in (0, None)
    assert src.read_bytes() == before
    assert hashlib.sha256(src.read_bytes()).hexdigest() == digest
    assert list(tmp_path.iterdir()) == [src]


def test_partial_and_unsupported_files_exit_nonzero(tmp_path: Path):
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    out = tmp_path / "out.json"
    with pytest.raises(SystemExit) as exc:
        ds.main(["write-array", "--input", str(empty), "--output", str(out)])
    assert exc.value.code not in (0, None)
    assert not out.exists()
    text = tmp_path / "note.txt"
    text.write_text("nope", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ds.main(["write-array", "--input", str(text), "--output", str(out)])
    assert exc.value.code not in (0, None)
    assert not out.exists()
    assert text.read_text(encoding="utf-8") == "nope"
