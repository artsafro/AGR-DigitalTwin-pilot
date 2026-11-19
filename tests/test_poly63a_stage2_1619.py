"""#1619 polygon stage 2, site-63 tower A (jobs/POLY63-A/stage2-1619): windows + glazing capsules on the accepted
body through the stage owners (openings_core, windowgen_core, winplace_core, capsule_core). Synthetic geometry only.

Pattern: n/a | new-case: tests/test_poly63a_stage2_1619.py - stage-2 inset plan hook of the training polygon.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from adapters.max.agr_tools import capsule_core

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "jobs" / "POLY63-A" / "stage2-1619" / "hooks"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s2 = _load(HOOKS / "stage2_plan.py", "stage2_plan_63a")

X0, Z0, W, H, REVEAL, FD = 1.0, 0.6, 1.0, 1.95, 0.25, 0.068
LOWER = [0.078, 0.088, 0.922, 0.422]
UPPER = [0.078, 0.538, 0.922, 1.872]


def _rect_tris(x0, x1, z0, z1, y):
    a, b, c, d = (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)
    return [[a, b, c], [a, c, d]]


def _window_tris(x=X0, z=Z0, y=REVEAL):
    """A Revit-like window: frame face front/back (68 mm) and two glass panes (two faces 28 mm apart)."""
    t = _rect_tris(x, x + W, z, z + H, y) + _rect_tris(x, x + W, z, z + H, y + FD)
    for r in (LOWER, UPPER):
        for dy in (0.02, 0.048):
            t += _rect_tris(x + r[0], x + r[2], z + r[1], z + r[3], y + dy)
    return np.array(t, dtype=float)


def _oriented(quad, want):
    a, b, c = (np.array(quad[i], float) for i in range(3))
    return quad if np.dot(np.cross(b - a, c - a), want) > 0 else quad[::-1]


def _body():
    """A 3 x 3.15 m wall at y = 0 (street -y) with one opening and a 0.25 m reveal (stage-1 style)."""
    xs, zs = [0.0, X0, X0 + W, 3.0], [0.0, Z0, Z0 + H, 3.15]
    verts, idx, faces = [], {}, []

    def v(p):
        k = tuple(round(c, 6) for c in p)
        if k not in idx:
            idx[k] = len(verts)
            verts.append(list(k))
        return idx[k]
    for i in range(3):
        for j in range(3):
            if (i, j) == (1, 1):
                continue
            q = [(xs[i], 0, zs[j]), (xs[i + 1], 0, zs[j]), (xs[i + 1], 0, zs[j + 1]), (xs[i], 0, zs[j + 1])]
            faces.append([v(p) for p in _oriented(q, (0, -1, 0))])
    x1, z1 = X0 + W, Z0 + H
    for q, want in (([(X0, 0, Z0), (X0, REVEAL, Z0), (X0, REVEAL, z1), (X0, 0, z1)], (1, 0, 0)),
                    ([(x1, 0, Z0), (x1, REVEAL, Z0), (x1, REVEAL, z1), (x1, 0, z1)], (-1, 0, 0)),
                    ([(X0, 0, Z0), (x1, 0, Z0), (x1, REVEAL, Z0), (X0, REVEAL, Z0)], (0, 0, 1)),
                    ([(X0, 0, z1), (x1, 0, z1), (x1, REVEAL, z1), (X0, REVEAL, z1)], (0, 0, -1))):
        faces.append([v(p) for p in _oriented(q, want)])
    fn = [len(f) for f in faces]
    return np.array(verts, float), np.array(fn, np.int32), np.array([i for f in faces for i in f], np.int64)


def _write_inputs(tmp_path, basket_z=None):
    verts, fn, fi = _body()
    np.savez(tmp_path / "body.npz", verts=verts, fn=fn, fi=fi)
    tri = [_window_tris()]
    names = ["Окн_Окн_1 Ств Комфорт_abc"]
    if basket_z is not None:
        tri.append(np.array(_rect_tris(0.2, 0.8, basket_z, basket_z + 0.7, -0.5), float))
        names.append("ОбщМд_Корзина для кондиционер_x")
    obj = np.concatenate([np.full(len(t), k, np.int32) for k, t in enumerate(tri)])
    np.savez(tmp_path / "crop.npz", tri=np.concatenate(tri), obj=obj, mat=np.zeros(len(obj), np.int32),
             names=np.array(names), mats=np.array([""]))


def test_revit_window_glass_is_the_pane_pair_not_the_frame():
    w = s2.revit_window(_window_tris())
    assert w["W"] == pytest.approx(W) and w["H"] == pytest.approx(H) and w["D"] == pytest.approx(FD)
    assert w["glass"] == [tuple(LOWER), tuple(UPPER)]


def test_profile_and_frame_grid_from_revit_glass():
    w = s2.revit_window(_window_tris())
    prof = s2.measure_profile([w])
    assert (prof["face_m"], prof["face_bottom_m"], prof["face_top_m"]) == (0.078, 0.088, 0.078)
    assert prof["transom_m"] == pytest.approx(0.116) and prof["impost_m"] == pytest.approx(0.116)
    fields, lower = s2.frame_grid(w, prof["transom_m"], prof["face_top_m"])
    assert fields == [LOWER, UPPER] and len(lower) == 1


def test_scale_fields_keeps_frame_and_scales_mullions():
    f = [[0.078, 0.088, 0.797, 0.422], [0.913, 0.088, 1.587, 0.422], [1.703, 0.088, 2.422, 0.422]]
    out = s2.scale_fields(f, 2.5, 2.4, 0.078)
    assert out[0][0] == 0.078 and out[-1][2] == pytest.approx(2.4 - 0.078)
    assert out[1][2] - out[1][0] < f[1][2] - f[1][0]
    assert s2.scale_fields(f, 2.5, 2.5, 0.078) == f


def test_quad_back_keeps_a_valid_inward_capsule():
    op = {"id": 1, "border": [[0, 0, 0], [1, 0, 0], [1, 0, 1.95], [0, 0, 1.95]],
          "frame": {"z": [0, -1, 0], "x": [1, 0, 0]}, "depth": 0.3}
    row = capsule_core.planar_capsule(op, capsule_core.options({"frame_depth_m": FD}))
    assert sum(1 for f in row["faces"] if len(f) == 3) == 2
    q = s2.quad_back(row)
    assert all(len(f) == 4 for f in q["faces"]) and len(q["faces"]) == len(row["faces"]) - 1
    chk = capsule_core.check_capsule(q)
    assert chk["inward"] and chk["open_off_rim"] == 0 and chk["bad_edges"] == 0


def test_plan_end_to_end_window_glass_capsule_on_untouched_body(tmp_path):
    _write_inputs(tmp_path, basket_z=4.0)
    out = tmp_path / "stage2.json"
    assert s2.main([str(tmp_path / "body.npz"), str(tmp_path / "crop.npz"), str(out), "--band", "0", "3.15"]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    rep, els = doc["report"], doc["elements"]
    assert rep["openings"]["ok"] == 1 and rep["capsules"]["made"] == 1
    assert sorted(e["collection"] for e in els) == ["Stage2_Capsules", "Stage2_Glass", "Stage2_Windows"]
    assert rep["faces"]["tris"] == 0 and rep["faces"]["ngons"] == 0
    row = rep["rows"][0]
    assert row["fit_corner_mm"] < 0.5 and row["dw_m"] == 0 and rep["misfit"] == []
    frame = next(e for e in els if e["collection"] == "Stage2_Windows")
    ys = [p[1] for p in frame["verts"]]
    assert min(ys) == pytest.approx(REVEAL, abs=1e-6) and max(ys) == pytest.approx(REVEAL + FD, abs=1e-6)
    cap = next(e for e in els if e["collection"] == "Stage2_Capsules")
    assert max(p[1] for p in cap["verts"]) == pytest.approx(REVEAL + FD + 1.0, abs=1e-6)
    assert rep["baskets"] == {"status": "none_in_band", "in_band": 0, "outside_band_by_zmin": [[4.0, 1]]}


def test_plan_refuses_output_equal_to_input(tmp_path):
    _write_inputs(tmp_path)
    with pytest.raises(SystemExit):
        s2.main([str(tmp_path / "body.npz"), str(tmp_path / "crop.npz"), str(tmp_path / "body.npz")])
