"""#1619 polygon stage 2 (G22 body 2): window frame/glass/flashing, D205 capsule and AC box geometry helpers.

Pattern: n/a | new-case: tests of the stage-2 inset-element hooks (stage2_from_dump / stage2_build / stage2_readback).
Pure helpers only - Blender is not needed.
"""
import collections
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "jobs" / "garibaldi22" / "body-training-1619" / "hooks"


def _load(path, name):
    sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fd_mod = _load(HOOKS / "stage2_from_dump.py", "stage2_from_dump_1619")
bd = _load(HOOKS / "stage2_build.py", "stage2_build_1619")
rb = _load(HOOKS / "stage2_readback.py", "stage2_readback_1619")

PANES_2SASH = [[0.1, 0.825, 0.085, 0.34], [0.975, 1.7, 0.085, 0.34], [0.1, 0.825, 0.49, 1.635], [0.975, 1.7, 0.49, 1.635]]


def _edges(m):
    return rb.mesh_edges([list(f) for f in m.faces])


def _normal(m, f):
    P = [m.verts[i] for i in f]
    n = [0.0, 0.0, 0.0]
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return np.array(n), np.mean(P, 0)


def test_frame_shell_is_closed_all_quad_with_holes_for_every_pane():
    m = bd.frame_shell(1.8, 1.75, PANES_2SASH, 0.15, 0.22)
    assert all(len(f) == 4 for f in m.faces)
    ec = _edges(m)
    assert set(ec.values()) == {2}  # closed manifold shell
    # Euler characteristic of a closed surface with g holes: V - E + F = 2 - 2g; 4 panes -> genus 4
    assert len(m.verts) - len(ec) + len(m.faces) == 2 - 2 * 4
    # front faces look out (-d), back faces in (+d)
    fronts = [f for f in m.faces if all(abs(m.verts[i][1] - 0.15) < 1e-9 for i in f)]
    assert fronts and all(_normal(m, f)[0][1] < 0 for f in fronts)
    backs = [f for f in m.faces if all(abs(m.verts[i][1] - 0.22) < 1e-9 for i in f)]
    assert backs and all(_normal(m, f)[0][1] > 0 for f in backs)
    # area of the front = opening minus panes (bars are geometry)
    area = sum(np.linalg.norm(_normal(m, f)[0]) / 2 for f in fronts)
    assert area == pytest.approx(1.8 * 1.75 - sum((p[1] - p[0]) * (p[3] - p[2]) for p in PANES_2SASH), abs=1e-6)


def test_frame_shell_side_faces_point_away_from_the_solid():
    m = bd.frame_shell(1.0, 1.0, [[0.2, 0.8, 0.2, 0.8]], 0.1, 0.2)
    c = np.mean(m.verts, 0)
    for f in m.faces:
        n, fc = _normal(m, f)
        if abs(n[1]) > 1e-9:
            continue
        inner = 0.2 - 1e-9 <= fc[0] <= 0.8 + 1e-9 and 0.2 - 1e-9 <= fc[2] <= 0.8 + 1e-9
        # outer sides look away from the centre, hole sides look into the hole (towards the centre)
        assert (n @ (fc - c) > 0) != inner


@pytest.mark.parametrize("panes, msg", [
    ([[0.0, 0.5, 0.1, 0.5]], "not inside"),
    ([[0.1, 0.5, 0.1, 0.5], [0.4, 0.8, 0.2, 0.6]], "overlap"),
])
def test_frame_shell_refuses_bad_panes(panes, msg):
    with pytest.raises(ValueError, match=msg):
        bd.frame_shell(1.0, 1.0, panes, 0.1, 0.2)


def test_capsule_d205_open_front_faces_inward_and_dimensions():
    m = bd.capsule_box(1.8, 1.75, 0.185, 1.0, 0.1)
    assert len(m.faces) == 5 and all(len(f) == 4 for f in m.faces)
    ec = _edges(m)
    boundary = [e for e, c in ec.items() if c == 1]
    assert len(boundary) == 4
    assert all(abs(m.verts[v][1] - 0.185) < 1e-9 for e in boundary for v in e)  # open at the frame middle
    V = np.array(m.verts)
    assert V[:, 0].min() == pytest.approx(-0.1) and V[:, 0].max() == pytest.approx(1.9)
    assert V[:, 2].min() == pytest.approx(-0.1) and V[:, 2].max() == pytest.approx(1.85)
    assert V[:, 1].max() - V[:, 1].min() == pytest.approx(1.0)
    c = V.mean(0)
    for f in m.faces:
        n, fc = _normal(m, f)
        assert n @ (c - fc) > 0  # interior is seen from the window side


def test_basket_box_has_no_back_face_and_sinks_into_the_wall():
    m = bd.basket_box(1.82, 0.61, 0.05, 1.945, 2.99)
    assert len(m.faces) == 5
    V = np.array(m.verts)
    assert V[:, 1].max() == pytest.approx(0.05) and V[:, 1].min() == pytest.approx(-0.61)
    # no face lies in the back plane d = embed
    assert not any(all(abs(m.verts[i][1] - 0.05) < 1e-9 for i in f) for f in m.faces)
    boundary = [e for e, c in _edges(m).items() if c == 1]
    assert len(boundary) == 4 and all(abs(m.verts[v][1] - 0.05) < 1e-9 for e in boundary for v in e)
    c = V.mean(0)
    for f in m.faces:
        n, fc = _normal(m, f)
        assert n @ (fc - c) > 0
    with pytest.raises(ValueError):
        bd.basket_box(1.82, 0.61, 0.0, 1.9, 2.9)  # flush box = stuck on the facade, not inset


def test_glass_and_flashing_orientation():
    g = bd.glass_quads([[0.1, 0.8, 0.1, 0.9, 0.2]])
    assert _normal(g, g.faces[0])[0][1] < 0
    fl = bd.flashing_sheet(1.8, 0.03, -0.01, 0.15)
    top, lip = fl.faces
    assert _normal(fl, top)[0][2] > 0 and _normal(fl, lip)[0][1] < 0
    with pytest.raises(ValueError):
        bd.flashing_sheet(1.8, 0.03, 0.2, 0.15)


def test_to_world_inward_normal_is_left_of_the_ccw_ring():
    # ring edge along +x (CCW square): the body is on the left (+y)
    assert bd.to_world((1.0, 0.5, 2.0), (10.0, 20.0), (1.0, 0.0), 5.0) == pytest.approx((11.0, 20.5, 7.0))


def test_snap_edges_merges_three_cm_sash_offsets_and_reports_shift():
    mp, shift = fd_mod.snap_edges([0.1, 0.13, 0.825, 0.855, 1.0], 0.04)
    assert mp[0.1] == mp[0.13] == pytest.approx(0.115)
    assert mp[1.0] == 1.0
    assert shift == pytest.approx(0.015)


def _box(u0, u1, d0, d1, z0, z1):
    c = [(u, d, z) for u in (u0, u1) for d in (d0, d1) for z in (z0, z1)]
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    out = []
    for a, b, cc, d in q:
        out += [[c[a], c[b], c[cc]], [c[a], c[cc], c[d]]]
    return out


def test_window_parts_reads_panes_frame_depth_and_flashing():
    tris = []
    # frame part: one big connected shell (outer box with a front lip) - 3 boxes sharing vertices are enough here:
    tris += _box(0.0, 1.0, 0.15, 0.22, 0.0, 1.0)  # frame volume
    tris += _box(0.0, 1.0, -0.01, 0.15, 0.0, 0.03)  # flashing touching the frame front (shares the d=0.15 plane)
    # make them one component: reuse corner vertices (box 2 back face corners == box 1 front bottom corners at z=0)
    tris += _box(0.2, 0.8, 0.19, 0.22, 0.2, 0.8)  # glass pane, its own 12-triangle component
    L = np.array(tris, dtype=float)
    out = fd_mod.window_parts(L, 0.15)
    assert out["panes"] == [[pytest.approx(0.2), pytest.approx(0.8), pytest.approx(0.2), pytest.approx(0.8), pytest.approx(0.205)]]
    assert out["fd"] == pytest.approx(0.07)
    assert out["width"] == pytest.approx(1.0) and out["height"] == pytest.approx(1.0)
    assert out["flashing"] == {"top": pytest.approx(0.03), "front": pytest.approx(-0.01)}


def test_window_parts_refuses_a_family_without_glass():
    with pytest.raises(ValueError, match="no glass"):
        fd_mod.window_parts(np.array(_box(0, 1, 0.15, 0.22, 0, 1), dtype=float), 0.15)


def test_coplanar_overlaps_finds_stacked_faces_but_not_touching_ones():
    a = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    b = [[0.1, 0.1, 0.001], [0.6, 0.1, 0.001], [0.1, 0.6, 0.001]]  # 1 mm above, inside a -> overlap
    c = [[1, 0, 0], [2, 0, 0], [1, 1, 0]]  # shares an edge only -> no overlap
    ov = rb.coplanar_overlaps(np.array([a, b, c], dtype=float), [0, 1, 2])
    assert (1, 0) in ov and all(2 not in p for p in ov)
    assert rb.coplanar_overlaps(np.array([a, b], dtype=float), [0, 0]) == []  # same owner is not an overlap


def test_ring_depth_sign():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert rb.ring_depth((5, 0.05), sq) == pytest.approx(0.05)
    assert rb.ring_depth((5, -0.61), sq) == pytest.approx(-0.61)


def test_capsule_plan_is_behind_the_frame_middle():
    pts = fd_mod.capsule_plan((0.0, 0.0), (1.0, 0.0), 1.8, 0.15, 0.07)
    ys = sorted({round(p[1], 6) for p in pts})
    assert ys == [pytest.approx(0.185), pytest.approx(1.185)]
    assert min(p[0] for p in pts) == pytest.approx(-0.1) and max(p[0] for p in pts) == pytest.approx(1.9)


def test_skeleton_lists_the_stage2_hooks():
    sk = json.loads((HOOKS.parent / "skeleton.json").read_text(encoding="utf-8"))
    scripts = [h["script"] for h in sk["hooks"]]
    for s in ("hooks/stage2_from_dump.py", "hooks/stage2_build.py", "hooks/stage2_readback.py"):
        assert s in scripts


def test_crop_dump_keeps_faces_inside_and_reindexes(tmp_path):
    crop = _load(ROOT / "docs" / "research" / "body-training-1619" / "crop_dump.py", "crop_dump_1619")
    V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [10, 10, 10], [11, 10, 10], [10, 11, 10]], dtype=float)
    src = tmp_path / "d.npz"
    np.savez(src, verts=V, fn=np.array([3, 3]), fi=np.array([0, 1, 2, 3, 4, 5]), mats=np.array([0, 1]),
             jverts=V, jn=np.array([3, 3]), ji=np.array([3, 4, 5, 0, 1, 2]), jmats=np.array([1, 0]),
             uvn=np.array([3, 3]), uvf=np.zeros((6, 2)), names=np.array(["x"]))
    out = tmp_path / "c.npz"
    crop.main([str(src), str(out), "9", "9", "9", "12", "12", "12"])
    d = np.load(out)
    assert d["verts"].tolist() == V[3:].tolist() and d["fi"].tolist() == [0, 1, 2]
    assert d["jmats"].tolist() == [1] and d["mats"].tolist() == [1] and len(d["uvf"]) == 3
    with pytest.raises(SystemExit):
        crop.main([str(src), str(tmp_path / "e.npz"), "50", "50", "50", "60", "60", "60"])
