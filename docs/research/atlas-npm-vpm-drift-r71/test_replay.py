"""Synthetic unit checks for the #71 replay (no Drive inputs)."""
import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("r71", Path(__file__).with_name("replay.py"))
r71 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r71)

PLAN = {"atlas": 64, "cell": 20, "pad": 2, "region": 16,
        "finishes": {"A": {"udim": 1001, "u0": 2 / 64, "v0": 1 - 18 / 64, "size": 16 / 64, "px_per_m": 1.0},
                     "B": {"udim": 1002, "u0": 22 / 64, "v0": 1 - 18 / 64, "size": 16 / 64, "px_per_m": None}}}


def build(tile):
    atlas = np.zeros((64, 64, 3), np.uint8)
    reg = r71.reference(PLAN, tile)
    atlas[0:20, 0:20] = np.pad(reg, ((2, 2), (2, 2), (0, 0)), mode="edge")
    atlas[0:20, 20:40] = 77
    return atlas


def tiles():
    t = np.full((4096, 4096, 3), 40, np.uint8)
    t[:, ::1024] = 230  # joints ~4 px apart at 16 px, like panel joints on a 397 px region
    t[:, 1::1024] = 230
    t[:, 512:1024] = 120
    return {1001: t, 1002: np.full((256, 256, 3), 77, np.uint8)}


def test_identical_region_scores_zero_and_side_checks_clean():
    t = tiles()
    atlas = build(t[1001])
    m, per = r71.score(PLAN, atlas, t)
    assert m == 0.0 and list(per) == ["A"]
    side = r71.side_checks(PLAN, atlas, t)
    assert side["pad_band_mismatch_px"] == {"A": 0, "B": 0}
    assert side["solid_mean_level_diff"] == {"B": 0}
    assert side["inter_region_gap_px"] == 4


def test_region_box_is_top_origin():
    assert r71.region_box(PLAN, PLAN["finishes"]["A"]) == (2, 2)


def test_shift_witness_fires():
    t = tiles()
    atlas = build(t[1001])
    w = r71.witnesses(PLAN, atlas, t, 0.0)
    assert w["shift_u_5px"]["ok"] and w["shift_u_5px"]["changed_px"]["B"] == "not_exercised"
    assert w["p2_brightness_8"]["delta"] > 0


def test_lanczos_matches_make_npm_atlas_kernel():
    t = np.zeros((4096, 4096, 3), np.uint8)
    t[:, ::64] = 255
    assert (r71.reference(PLAN, t) == np.asarray(Image.fromarray(t).resize((16, 16), Image.LANCZOS))).all()
