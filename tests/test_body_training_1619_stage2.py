"""#1619 polygon stage 2 (G22 body 2): window frame/glass (windowgen_core), D205 capsule (capsule_core), flashing and AC box.

Pattern: n/a | new-case: tests of the stage-2 inset elements (floor_from_dump `stage2`, module_build `stage2` / `stage2-readback`).
Pure helpers only - Blender is not needed.
"""
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


fd_mod = _load(HOOKS / "floor_from_dump.py", "floor_from_dump_1619s2")  # subcommand `stage2`
bd = _load(HOOKS / "module_build.py", "module_build_1619s2")  # mode `stage2`; bpy only inside _run_*
rb = bd  # mode `stage2-readback` lives in module_build too (#1546: <= 5 hooks)

# k2 typical floor, Revit «102_Окно_2Створки1 1800(900)х1750h» as read by floor_from_dump stage2 (C:/x/ev_1619/s2/v001)
PANES_2SASH = [[0.1, 0.825, 0.085, 0.34, 0.185], [0.975, 1.7001, 0.085, 0.34, 0.185],
               [0.1, 0.825, 0.49, 1.635, 0.205], [0.975, 1.7001, 0.49, 1.635, 0.205]]
TYPE_2SASH = "102_Окно_2Створки1 1800(900)х1750h"
CAP = {"depth": 1.0, "outline": 0.1}


@pytest.fixture(scope="module")
def cores():
    return bd.load_core("windowgen_core"), bd.load_core("capsule_core"), bd.load_standard()


@pytest.fixture(scope="module")
def win():
    return {"type": TYPE_2SASH, "w": 1.8001, "h": 1.75, "r": 0.15, "fd": 0.07, "panes": PANES_2SASH,
            "flashing": {"top": 0.03, "front": -0.01},
            "entry": bd.window_entry(TYPE_2SASH, 1.8001, 1.75, 0.07, PANES_2SASH)}


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


def test_hooks_no_longer_reimplement_the_cores():
    # review r1 P1 (#1670): frame/glass/capsule geometry belongs to windowgen_core / capsule_core (SKELETONS oks-vpm)
    for fn in ("frame_shell", "glass_quads", "capsule_box"):
        assert not hasattr(bd, fn)


def test_window_entry_carries_the_revit_profile_of_the_k2_2sash(win):
    e = win["entry"]
    assert e["role"] == "window" and e["width_m"] == 1.8001 and e["height_m"] == 1.75
    assert e["panes_m"][0] == [0.1, 0.085, 0.825, 0.34]  # [x0, z0, x1, z1]
    assert e["frame_profile_m"] == {"face_m": 0.1, "face_bottom_m": 0.085, "face_top_m": 0.115, "impost_m": 0.15,
                                    "depth_m": 0.07}
    one = bd.window_entry("1sash", 1.1505, 1.75, 0.07, [[0.085, 1.0655, 0.085, 0.34], [0.085, 1.0655, 0.46, 1.665]])
    assert one["frame_profile_m"]["impost_m"] == pytest.approx(0.12)  # the transom of the 1-sash type
    with pytest.raises(ValueError, match="no pane edge"):
        bd.window_entry("x", 2.0, 2.0, 0.07, [[0.5, 1.5, 0.5, 1.5]])


def test_k2_2sash_window_mesh_comes_from_windowgen_build_type(cores, win):
    wg, _, std = cores
    fr, gl, info = bd.window_module(win, std, wg)
    core = wg.build_type(win["entry"], std)
    for got, part in ((fr, "frame"), (gl, "glass")):
        want = wg.part_mesh(core, part)
        assert [list(f) for f in got.faces] == want["faces"]
        assert np.allclose(got.verts, np.array(want["verts"]) + [0.0, 0.15, 0.0])  # frame face on the reveal back r
    assert all(len(f) == 4 for f in fr.faces + gl.faces)
    ec = _edges(fr)
    assert set(ec.values()) == {2}  # closed frame shell
    assert len(fr.verts) - len(ec) + len(fr.faces) == 2 - 2 * 4  # 4 panes -> genus 4: mullion and transom are bars
    assert len(gl.faces) == 4 and all(_normal(gl, f)[0][1] < 0 for f in gl.faces)  # glass looks out
    assert info["family"] == "F100" and info["status"] == "ok"
    assert info["field_deviation_m"] == pytest.approx(0.0, abs=1e-6)  # core standardize keeps the Revit panes
    assert info["glass_d_m"] == pytest.approx(0.185)  # D322 frame middle r + fd / 2
    assert info["glass_depth_shift_m"] == pytest.approx(0.02)  # Revit sash glass 0.205 -> named deviation


def test_capsule_module_is_capsule_core_planar_capsule(cores, win):
    m, row = bd.capsule_module(win, CAP, cores[1])
    assert row["kind"] == "planar" and [list(f) for f in m.faces] == row["faces"]
    assert sorted(len(f) for f in m.faces) == [3, 3, 4, 4, 4, 4]  # core back = ear_clip, 2 triangles
    boundary = [e for e, c in _edges(m).items() if c == 1]
    assert len(boundary) == 4
    assert all(m.verts[v][1] == pytest.approx(0.185) for e in boundary for v in e)  # rim at the frame middle
    V = np.array(m.verts)
    assert V[:, 0].min() == pytest.approx(-0.1) and V[:, 0].max() == pytest.approx(1.9001)
    assert V[:, 2].min() == pytest.approx(-0.1) and V[:, 2].max() == pytest.approx(1.85)
    assert V[:, 1].max() == pytest.approx(0.22 + 1.0)  # 1.0 m behind the border plane (frame back)
    c = V.mean(0)
    for f in m.faces:
        n, fc = _normal(m, f)
        assert n @ (c - fc) > 0  # every face looks into the capsule


def test_build_modules_reports_core_deviations_per_type(cores, win):
    mods, types = bd.build_modules({"windows": [win, win], "capsule": CAP}, cores[2])
    assert len(mods) == 2 and mods[0][4] is not None
    t = types[TYPE_2SASH]
    assert t["count"] == 2 and t["capsule_faces"] == 6 and t["glass_faces"] == 4


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


def test_flashing_orientation():
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
    for a, b, k, d in q:
        out += [[c[a], c[b], c[k]], [c[a], c[k], c[d]]]
    return out


def test_window_parts_reads_panes_frame_depth_and_flashing():
    tris = []
    tris += _box(0.0, 1.0, 0.15, 0.22, 0.0, 1.0)  # frame volume
    tris += _box(0.0, 1.0, -0.01, 0.15, 0.0, 0.03)  # flashing touching the frame front (shares the d=0.15 plane)
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


def test_capsule_plan_is_the_capsule_core_footprint():
    pts = fd_mod.capsule_plan((0.0, 0.0), (1.0, 0.0), 1.8, 1.75, 0.15, 0.07)
    ys = sorted({round(p[1], 6) for p in pts})
    assert ys == [pytest.approx(0.185), pytest.approx(1.22)]  # rim at the frame middle .. 1.0 m behind the frame back
    assert min(p[0] for p in pts) == pytest.approx(-0.1) and max(p[0] for p in pts) == pytest.approx(1.9)


def test_skeleton_wires_stage2_through_existing_hooks():
    """#1546 D324: stage 2 is a subcommand/mode of listed hooks, not three extra hooks (<= 5 per job)."""
    sk = json.loads((HOOKS.parent / "skeleton.json").read_text(encoding="utf-8"))
    scripts = [h["script"] for h in sk["hooks"]]
    assert len(scripts) <= 5 and "hooks/floor_from_dump.py" in scripts and "hooks/module_build.py" in scripts
    assert sorted(p.name for p in HOOKS.glob("*.py")) == sorted(s.split("/")[-1] for s in scripts)
    assert callable(fd_mod.stage2_main)
    assert set(bd.MODES) == {"stage2", "stage2-readback"}


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
