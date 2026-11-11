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


def test_bleed_rgb_fills_transparent_pixels_with_plant_colour():
    """[D246] pale crossing plane: the maps carried white (252) RGB under opacity 0, so texture filtering and
    mipmaps mixed white into the foliage (worst on the near edge-on plane and on distant site views)."""
    rgb, op = _plant(size=64, box=(20, 10, 40, 60))
    rgb[op == 0] = 252                       # white background of the source map
    rgb[op > 0] = (60, 120, 40)
    out = job.bleed_rgb(rgb, op)
    assert out.dtype == np.uint8 and out.shape == rgb.shape
    assert (out[op > 0] == rgb[op > 0]).all()                       # plant pixels unchanged
    assert np.abs(out[op == 0].astype(int) - (60, 120, 40)).max() <= 1  # background takes the plant colour
    from PIL import Image
    small = np.asarray(Image.fromarray(out).resize((16, 16), Image.Resampling.LANCZOS)).astype(int)
    assert np.abs(small - (60, 120, 40)).max() <= 2                    # no white halo after downscale


def test_bleed_rgb_keeps_an_empty_mask_and_a_full_mask():
    rgb, op = _plant(size=16, box=(0, 0, 16, 16))
    assert (job.bleed_rgb(rgb, op) == rgb).all()
    assert job.bleed_rgb(rgb, np.zeros_like(op)).shape == rgb.shape


def test_stage_maps_bleeds_the_cropped_map():
    import inspect
    src = inspect.getsource(job.stage_maps)
    assert "bleed_rgb(" in src and src.index("square_crop(") < src.index("bleed_rgb(")


def test_review_material_has_no_grazing_specular():
    """[D246] Principled specular at grazing angles washed the crossing plane out in the review renders."""
    src = (ROOT / "jobs/VATUTINO-SITE/flora_v007_blender.py").read_text(encoding="utf-8")
    body = src[src.index("def _atlas_material"):src.index("def _engine")]
    assert 'bsdf.inputs["Specular IOR Level"].default_value = 0.0' in body


def test_vpm_atlas_is_4096_and_npm_stays_2048():
    assert job.ATLAS_PROFILES == {"npm": ("atlas", 2048), "vpm": ("atlas-vpm", 4096)}


def test_texel_table_splits_below_and_above_the_vpm_range(tmp_path):
    """[D246] only rows below 520 px/m are accepted; a row above 1706 is a separate gate item."""
    import json
    (tmp_path / "stars").mkdir()
    sp = [{"key": k, "atlas": {"texel_px_per_m": t / 2, "texel_ok": False},
           "vpm_atlas": {"texel_px_per_m": t, "texel_ok": 520 <= t <= 1706}} for k, t in (("a", 160), ("b", 900), ("c", 2100))]
    (tmp_path / "stars" / "report.json").write_text(json.dumps({"species": sp}), encoding="utf-8")
    job.texel_table(tmp_path, tmp_path)
    out = json.loads((tmp_path / "texel-vpm.json").read_text(encoding="utf-8"))
    assert out["below_range_accepted_D246"] == ["a"] and out["above_range"] == ["c"]
    md = (tmp_path / "texel-vpm.md").read_text(encoding="utf-8")
    assert "Above range (open, not covered by [D246]): c" in md
