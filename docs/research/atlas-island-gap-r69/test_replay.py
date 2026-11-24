"""Synthetic checks of the #69 island-gap census (no Blender)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("r69", Path(__file__).with_name("replay.py"))
r69 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r69)

S = 4096


def _quad(u, v, w):
    return [(u, v), (u + w, v), (u + w, v + w), (u, v + w)]


def _rb(*uvs):
    polys, verts, puv = [], [], []
    for uv in uvs:
        base = len(verts)
        verts += [[0.0, 0.0, 0.0]] * len(uv)
        polys.append(list(range(base, base + len(uv))))
        puv.append([list(p) for p in uv])
    return {"meshes": [{"name": "m", "face_geometry": {"vertices": verts, "polygons": polys, "polygon_uv": puv}}]}


def test_shared_edge_joins_and_gap_counts():
    a = _quad(0.1, 0.1, 0.1)
    b = _quad(0.2, 0.1, 0.1)  # shares an edge with a -> same island
    c = _quad(0.3 + 4 / S, 0.1, 0.1)  # 4 px from b -> sub-floor
    d = _quad(0.6, 0.6, 0.1)  # far
    out = r69.census(r69.islands(_rb(a, b, c, d)), {1001: S})
    t = out["tiles"]["1001"]
    assert t["islands"] == 3 and out["N69"] == 1 and abs(out["min_gap_px_textured"] - 4) < 1e-6


def test_overlap_is_separate_and_solid_tiles_not_counted():
    a, b = _quad(0.1, 0.1, 0.2), _quad(0.2, 0.2, 0.2)
    out = r69.census(r69.islands(_rb(a, b)), {1001: S})
    assert out["N69"] == 0 and out["overlap_pairs_textured"] == 1
    solid = [(u + 1, v) for u, v in _quad(0.1, 0.1, 0.1)], [(u + 1, v) for u, v in _quad(0.2 + 1 / 256, 0.1, 0.1)]
    out = r69.census(r69.islands(_rb(*solid)), {1002: 256})
    assert out["N69"] == 0 and out["tiles"]["1002"]["sub_floor_pairs"] == 1


def test_witness_moves_one_island_to_target():
    isl = r69.islands(_rb(_quad(0.1, 0.1, 0.1), _quad(0.3, 0.1, 0.2)))
    w4, w9 = r69.witness(isl, {1001: S}, 4.0), r69.witness(isl, {1001: S}, 9.0)
    assert w4["result"]["N69"] == 1 and abs(w4["result"]["min_gap_px_textured"] - 4) < 1e-6
    assert w9["result"]["N69"] == 0 and abs(w9["result"]["min_gap_px_textured"] - 9) < 1e-6
