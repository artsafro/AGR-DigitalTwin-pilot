"""Synthetic checks of the #65 UDIM fold / shift / verdict (no Blender, no real package)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[2] / "src")]

from r65 import TARGET, fold, margin_px, shift, target_faces, verdict  # noqa: E402

ATLAS = {"atlas": 2048, "cell": 409, "pad": 6, "finishes": {
    TARGET: {"udim": 1001, "u0": 6 / 2048, "v0": 0.80322265625, "size": 397 / 2048},
    "B": {"udim": 1002, "u0": 415 / 2048, "v0": 0.80322265625, "size": 397 / 2048}}}
PX = {1001: [2048, 2048], 1002: [2048, 2048]}


def quad(u0, v0, w, h, tile_u=0):
    return [[tile_u + u0, v0], [tile_u + u0 + w, v0], [tile_u + u0 + w, v0 + h], [tile_u + u0, v0 + h]]


def meshes():
    a = quad(10 / 2048, 0.81, 380 / 2048, 0.1)            # 13 px from U-max edge of TARGET (403 px)
    b = quad(420 / 2048, 0.81, 100 / 2048, 0.1, tile_u=1)  # tile 1002, region B
    return [{"name": "M", "face_geometry": {"polygons": [[0, 1, 2, 3], [4, 5, 6, 7]], "polygon_uv": [a, b]}}]


def test_fold_clean_and_tile_routing():
    out = fold(meshes(), ATLAS, PX)
    assert out["faces"] == 2 and out["bad"] == [] and set(out["tiles"]) == {1001, 1002}


def test_unchanged_check_without_fold_rejects_tile_1002():
    from twinqa.npm_uv import check_meshes, load_layout
    res = check_meshes(meshes(), load_layout(ATLAS))  # one-atlas reading: tile 1002 face has no cell
    assert [b["reason"] for b in res["bad"]] == ["outside every atlas cell"]


def test_shift_margin_and_reasons():
    m = meshes()
    hits = target_faces(m, ATLAS)
    assert hits == [(0, 0)]
    assert abs(margin_px(m, ATLAS, hits) - 13) < 1e-6
    assert fold(shift(m, hits, 5, 2048), ATLAS, PX)["bad"] == []
    assert [b["reason"] for b in fold(shift(m, hits, 14, 2048), ATLAS, PX)["bad"]] == ["padding band"]
    assert fold(shift(m, hits, 20, 2048), ATLAS, PX)["bad"][0]["reason"] in ("crosses cell", "outside every atlas cell")


def test_orphan_tile_and_missing_png():
    m = meshes()
    m[0]["face_geometry"]["polygon_uv"][1] = quad(0.1, 0.1, 0.01, 0.01, tile_u=4)
    assert fold(m, ATLAS, PX)["bad"][0]["reason"] == "no region tile"
    try:
        fold(meshes(), ATLAS, {1001: [2048, 2048], 1002: [1024, 1024]})
    except ValueError:
        pass
    else:
        raise AssertionError("missing 2048 PNG must refuse")


def test_verdict():
    assert verdict(True, 3, 0, {1: (0, False), 9: (2, True)}) == "confirmed"
    assert verdict(False, 3, 0, {1: (0, False)}) == "refuted"
    assert verdict(True, 0, 0, {1: (0, False)}) == "refuted"
    assert verdict(True, 3, 0, {1: (1, False)}) == "refuted"
