"""#1737 skeleton cell `vpm-to-npm`: interiors, glass on white, budget ladder, skeleton entries.

Fixture = a synthetic VPM-shaped mesh (synthetic, not a real object): an outer box on UDIM 1001, an inner capsule wall on
UDIM 1011 (interior) and two glass panes in two objects.
"""
import json
import math
import random
from pathlib import Path

import pytest

from tools.derive import vpm_npm_core as core

ROOT = Path(__file__).resolve().parents[1]
SK = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))


def _quad(z, tile_u=0, tile_v=0):
    verts = [(0, 0, z), (1, 0, z), (1, 1, z), (0, 1, z)]
    uv = [(tile_u + 0.1, tile_v + 0.1), (tile_u + 0.9, tile_v + 0.1), (tile_u + 0.9, tile_v + 0.9),
          (tile_u + 0.1, tile_v + 0.9)]
    return verts, uv


def _fixture():
    faces = []
    for z in range(4):
        v, uv = _quad(z)               # outer, 1001
        faces.append({"object": "SM_X_Main", "verts": v, "uv": uv})
    for z in range(2):
        v, uv = _quad(z, 0, 1)         # inner capsule wall, 1011
        faces.append({"object": "SM_X_Main", "verts": v, "uv": uv})
    v, uv = _quad(9, 1, 0)             # interior object
    faces.append({"object": "SM_X_Interior", "verts": v, "uv": uv})
    return faces


# --- skeleton -------------------------------------------------------------------------------------------------------

def test_cell_vpm_to_npm_has_the_ordered_stages():
    assert SK["cells"]["vpm-to-npm"]["stages"] == [
        "tris-count", "remove-interiors", "atlas", "glass-merge", "budget-ladder", "master-qa", "readback", "verifier",
        "package-npm", "validate", "checker", "review-scene"]
    for sid in ("tris-count", "remove-interiors", "atlas", "glass-merge", "budget-ladder"):
        assert SK["stages"][sid]["gap"] is None, sid


def test_optimise_gap_text_has_no_prooptimizer():
    gap = SK["stages"]["optimise"]["gap"]
    assert "ProOptimizer in Max by hand" not in gap and "no ProOptimizer step" in gap
    assert "D167" in gap and "budget-ladder" in gap
    doc = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    assert "ProOptimizer в Max вручную" not in doc
    assert "`vpm-to-npm`" in doc


# --- tris count -----------------------------------------------------------------------------------------------------

def test_tris_count_fan_and_fail_closed():
    assert core.count_tris([[0, 1, 2], [0, 1, 2, 3], list(range(6))]) == 1 + 2 + 4
    with pytest.raises(core.VpmNpmError, match="face 0"):
        core.count_tris([[0, 1]])
    with pytest.raises(core.VpmNpmError, match="empty"):
        core.count_tris([])


# --- interiors ------------------------------------------------------------------------------------------------------

def test_remove_interiors_by_udim_and_object_reports_every_drop():
    faces = _fixture()
    res = core.remove_interiors(faces, {"udims": [1011], "objects": ["SM_X_Interior"]})
    assert res["kept"] == [0, 1, 2, 3]
    dropped = {d["face"]: d["reason"] for d in res["dropped"]}
    assert dropped == {4: "interior_udim 1011", 5: "interior_udim 1011", 6: "interior_object SM_X_Interior"}
    assert sorted(res["kept"] + list(dropped)) == list(range(len(faces)))  # every face kept or reported
    assert res["tris_before"] == 14 and res["tris_after"] == 8


def test_remove_interiors_fail_closed():
    faces = _fixture()
    with pytest.raises(core.VpmNpmError, match="interiors config"):
        core.remove_interiors(faces, None)          # explicit config is required, never a default
    with pytest.raises(core.VpmNpmError, match="unknown key 'udim'"):
        core.remove_interiors(faces, {"udim": [1011], "objects": []})
    with pytest.raises(core.VpmNpmError, match="1099"):
        core.remove_interiors(faces, {"udims": [1099], "objects": []})   # names a tile absent from the mesh
    with pytest.raises(core.VpmNpmError, match="SM_Nope"):
        core.remove_interiors(faces, {"udims": [], "objects": ["SM_Nope"]})
    with pytest.raises(core.VpmNpmError, match="every face"):
        core.remove_interiors(faces, {"udims": [1001, 1011, 1002], "objects": []})
    with pytest.raises(core.VpmNpmError, match="integer"):
        core.remove_interiors(faces, {"udims": [1011.0], "objects": []})
    bad = _fixture()
    bad[0]["uv"][0] = (math.nan, 0.1)
    with pytest.raises(core.VpmNpmError):
        core.remove_interiors(bad, {"udims": [1011], "objects": []})
    # empty lists are an explicit "no interiors": nothing dropped
    assert core.remove_interiors(faces, {"udims": [], "objects": []})["dropped"] == []


def test_remove_interiors_probe_random_meshes():
    rng = random.Random(1737)
    for _ in range(200):
        faces = []
        for i in range(rng.randint(2, 30)):
            v, uv = _quad(i, rng.randint(0, 2), rng.randint(0, 1))
            faces.append({"object": rng.choice(["A", "B"]), "verts": v, "uv": uv})
        tiles = sorted({core.face_udim(f["uv"]) for f in faces})
        interior = [t for t in tiles if rng.random() < 0.4]
        try:
            res = core.remove_interiors(faces, {"udims": interior, "objects": []})
        except core.VpmNpmError as exc:
            assert "every face" in str(exc)
            continue
        assert all(core.face_udim(faces[i]["uv"]) not in interior for i in res["kept"])
        assert len(res["kept"]) + len(res["dropped"]) == len(faces)


# --- glass on white -------------------------------------------------------------------------------------------------

def _atlas(size=64, white=None):
    px = [[(90, 90, 90)] * size for _ in range(size)]
    if white:
        x0, y0, n = white
        for y in range(y0, y0 + n):
            for x in range(x0, x0 + n):
                px[y][x] = (255, 255, 255)
    return px


def _glass():
    return [{"object": "SM_X_MainGlass", "verts": [(0, 0, 0), (1, 0, 0), (1, 1, 0)], "uv": [(0, 0), (1, 0), (1, 1)]},
            {"object": "SM_X_Glass_2", "verts": [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
             "uv": [(0, 0), (1, 0), (1, 1), (0, 1)]}]


def test_glass_merge_one_object_and_every_uv_on_pure_white():
    px = _atlas(64, white=(40, 8, 8))
    cell = core.find_white(px, min_px=4)
    assert cell == (40, 8, 8, 8)
    res = core.glass_merge(_glass(), px, name="SM_X_MainGlass", cell=cell)
    assert res["object"] == "SM_X_MainGlass" and res["merged_from"] == ["SM_X_MainGlass", "SM_X_Glass_2"]
    assert len(res["faces"]) == 2 and all(f["object"] == "SM_X_MainGlass" for f in res["faces"])
    for f in res["faces"]:
        for u, v in f["uv"]:
            assert core.sample(px, u, v) == (255, 255, 255)
    assert res["white_samples"] == res["uv_samples"] == 7


def test_glass_merge_reserves_white_when_absent_and_fails_closed():
    px = _atlas(64)
    assert core.find_white(px, min_px=4) is None
    cell = core.reserve_white(px, occupied=[(0, 0, 32, 64)], size_px=8, pad=4)
    assert cell[0] >= 36 and core.find_white(px, min_px=8) is not None
    with pytest.raises(core.VpmNpmError, match="no free"):
        core.reserve_white(_atlas(16), occupied=[(0, 0, 16, 16)], size_px=8, pad=4)
    with pytest.raises(core.VpmNpmError, match="glass"):
        core.glass_merge([], px, name="G", cell=cell)
    # a cell that is not pure white (one off-white pixel) is refused, never accepted
    px2 = _atlas(64, white=(40, 8, 8))
    px2[11][43] = (254, 255, 255)
    with pytest.raises(core.VpmNpmError, match="not pure white"):
        core.glass_merge(_glass(), px2, name="G", cell=(40, 8, 8, 8))


# --- budget ladder --------------------------------------------------------------------------------------------------

def test_budget_ladder_order_and_only_while_over_budget():
    calls = []

    def step(name, saves):
        def run(tris):
            calls.append(name)
            return tris - saves
        return run

    steps = {"cylinder-segments": step("cyl", 50), "opacity-planes": step("opa", 50), "window-planes": step("win", 50)}
    rep = core.budget_ladder(100, 150, steps)
    assert rep["ran"] == [] and rep["within"] and calls == []
    rep = core.budget_ladder(150, 150, steps)                       # exactly at the budget = within, no step
    assert rep["ran"] == [] and rep["within"]
    rep = core.budget_ladder(220, 150, steps)
    assert rep["ran"] == ["cylinder-segments", "opacity-planes"] and rep["skipped"] == ["window-planes"]
    assert calls == ["cyl", "opa"] and rep["final"] == 120 and rep["within"]


def test_budget_ladder_fail_closed():
    with pytest.raises(core.VpmNpmError, match="budget"):
        core.budget_ladder(10, math.nan, {})
    with pytest.raises(core.VpmNpmError, match="budget"):
        core.budget_ladder(10, 0, {})
    with pytest.raises(core.VpmNpmError, match="unknown ladder step 'pro-optimizer'"):
        core.budget_ladder(10, 100, {"pro-optimizer": lambda t: t})
    rep = core.budget_ladder(300, 150, {"cylinder-segments": lambda t: t - 10})
    assert not rep["within"] and rep["missing"] == ["opacity-planes", "window-planes"]
    with pytest.raises(core.VpmNpmError, match="did not reduce"):
        core.budget_ladder(300, 150, {"cylinder-segments": lambda t: t})
