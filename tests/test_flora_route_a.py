"""Tests for the pure parts of jobs/VATUTINO-SITE/flora_route_a.py (#1146 route A run v002)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("flora_route_a", ROOT / "jobs/VATUTINO-SITE/flora_route_a.py")
job = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(job)


def _plant(size=200, box=(40, 20, 90, 180)):
    op = np.zeros((size, size), np.uint8)
    x0, y0, x1, y1 = box
    op[y0:y1, x0:x1] = 255
    rgb = np.zeros((size, size, 3), np.uint8)
    rgb[..., 1] = 120
    return rgb, op


def test_square_crop_keeps_every_plant_pixel_and_is_square():
    rgb, op = _plant()
    c_rgb, c_op, box = job.square_crop(rgb, op, margin=0.015)
    assert c_op.shape[0] == c_op.shape[1] == c_rgb.shape[0] == c_rgb.shape[1]
    assert np.count_nonzero(c_op) == np.count_nonzero(op)
    assert box["bbox"] == [40, 20, 90, 180] and box["window"][2] == 160 + 2 * 3


def test_square_crop_pads_outside_the_source_transparent():
    rgb, op = _plant(box=(0, 0, 200, 60))  # wide plant at the top edge: window leaves the image
    _, c_op, box = job.square_crop(rgb, op)
    assert box["window"][1] < 0 and np.count_nonzero(c_op) == np.count_nonzero(op)


def test_square_crop_rejects_empty_opacity():
    rgb, op = _plant()
    with pytest.raises(SystemExit):
        job.square_crop(rgb, np.zeros_like(op))


def test_a101_side_view_drops_the_top_view_of_the_sheet():
    # A101 map = side view (upper right) + top view (lower left) on one sheet; the star needs the side view only
    op = np.zeros((256, 256), np.uint8)
    op[20:120, 140:240] = 255            # side view crown
    op[120:140, 185:190] = 255           # its stem, reaching down
    op[142:240, 10:120] = 255            # top view, separated by a 2 px gap
    rgb = np.zeros((256, 256, 3), np.uint8)
    rgb[op > 0] = 90
    s_rgb, s_op, info = job.a101_side_view(rgb, op)
    assert np.count_nonzero(s_op) == 100 * 100 + 20 * 5
    assert not s_op[142:240, 10:120].any() and not s_rgb[142:240, 10:120].any()
    assert info["dropped_px"] == 98 * 110 and info["kept_bbox"] == [140, 20, 240, 140]


def test_uv_sample_check_detects_a_wrong_cell():
    rgb, op = _plant(size=64, box=(10, 5, 30, 60))
    atlas_op = np.zeros((128, 128), np.uint8)
    atlas_rgb = np.zeros((128, 128, 3), np.uint8)
    atlas_op[0:64, 64:128] = op          # cell u 0.5-1, v 0.5-1 (top-right, y down)
    atlas_rgb[0:64, 64:128] = rgb
    good = job.uv_sample_check(rgb, op, atlas_rgb, atlas_op, [0.5, 0.5, 1.0, 1.0])
    bad = job.uv_sample_check(rgb, op, atlas_rgb, atlas_op, [0.0, 0.0, 0.5, 0.5])
    assert good["opacity_mismatch_pct"] == 0 and good["colour_mean_abs_diff"] == 0
    assert bad["opacity_mismatch_pct"] > 10


def test_rows_cover_all_plants_and_iva_band_is_assumed():
    recs = job.rows()
    assert len(recs) == 18 and sum(r["plants_in_plot"] for r in recs) == 4915
    iva = next(r for r in recs if r["pos"] == "Ива")
    assert iva["key"] == "iva_244" and iva["assumed_cm"] == [60, 100] and iva["schedule_cm"] is None
    assert len({r["key"] for r in recs}) == 18
