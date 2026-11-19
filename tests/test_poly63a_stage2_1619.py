"""#1619 polygon stage 2, site-63 tower A (jobs/POLY63-A/stage2-1619): windows + glazing capsules on the accepted
body through the stage owners (openings_core, windowgen_core, winplace_core, capsule_core). Synthetic geometry only.

Pattern: n/a | new-case: tests/test_poly63a_stage2_1619.py - stage-2 inset plan hook of the training polygon.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

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


def _argv(path, out=None):
    return [str(path / "body.npz"), str(path / "crop.npz"), str(out or path / "stage2.json"), "--band", "0", "3.15"]


def _stop(path, *messages):
    with pytest.raises(SystemExit) as exc:
        s2.main(_argv(path))
    diagnostic = str(exc.value)
    assert "STOP" in diagnostic
    for message in messages:
        assert message in diagnostic
    assert not (path / "stage2.json").exists()


def _opening(dx=0.0, **extra):
    verts, fn, fi = _body()
    verts[:, 0] += dx
    faces = np.split(fi, np.cumsum(fn)[:-1])
    row, = s2.openings_core.find_openings_report({"verts": verts.tolist(),
                                               "faces": [f.tolist() for f in faces]})["openings"]
    return dict(row, **extra)


def _inject_openings(monkeypatch, rows):
    monkeypatch.setattr(s2.openings_core, "find_openings_report", lambda mesh: {"openings": rows, "rejected": []})


def test_cli_stops_for_opening_moved_one_metre(tmp_path):
    _write_inputs(tmp_path)
    verts, fn, fi = _body()
    verts[:, 0] += 1.0
    np.savez(tmp_path / "body.npz", verts=verts, fn=fn, fi=fi)
    result = subprocess.run([sys.executable, str(HOOKS / "stage2_plan.py"), *_argv(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
                            env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=60)
    assert result.returncode == 1
    assert "STOP" in result.stderr and "opening 1" in result.stderr and "0.6 m" in result.stderr
    assert not (tmp_path / "stage2.json").exists()


@pytest.mark.parametrize("count", [2, 3, 5])
@pytest.mark.parametrize("reverse", [False, True])
def test_repeated_match_lists_every_claimant(tmp_path, monkeypatch, count, reverse):
    _write_inputs(tmp_path)
    rows = [_opening(float(dx), id=i) for i, dx in enumerate(np.linspace(-0.1, 0.1, count), 1)]
    if count > 2:
        rows.append(_opening(1.0, id=99))
    _inject_openings(monkeypatch, rows[::-1] if reverse else rows)
    monkeypatch.setattr(s2.windowgen_core, "build_type", lambda *a: pytest.fail("geometry built before preflight"))
    messages = ["matched more than once", *(f"opening {i} " for i in range(1, count + 1))]
    _stop(tmp_path, *messages, *(["opening 99 ", "0.6 m"] if count > 2 else []))


@pytest.mark.parametrize("status", ["ambiguous", "unsupported", "empty", "capsule ambiguous", "capsule missing"])
def test_owner_failure_blocks_output(tmp_path, monkeypatch, status):
    _write_inputs(tmp_path)
    if status == "capsule ambiguous":
        monkeypatch.setattr(s2.capsule_core, "plan", lambda *a: {"rows": [], "ambiguous": ["63A opening 1: synthetic"]})
        _stop(tmp_path, "capsule", "opening 1", "synthetic")
    elif status == "capsule missing":
        monkeypatch.setattr(s2.capsule_core, "plan", lambda *a: {"rows": [], "ambiguous": []})
        _stop(tmp_path, "capsule opening 1", "expected one row")
    else:
        _inject_openings(monkeypatch, [] if status == "empty" else [_opening(status=status, why=["nonrect"])])
        _stop(tmp_path, *(["no openings"] if status == "empty" else ["opening 1", status, "nonrect"]))


@pytest.mark.parametrize("check", [{"bad_edges": 1}, {"open_off_rim": 1}, {"inward": False}, {"closed_open_edges": 1}])
def test_bad_capsule_blocks_output(tmp_path, monkeypatch, check):
    _write_inputs(tmp_path)
    original = s2.capsule_core.check_capsule
    monkeypatch.setattr(s2.capsule_core, "check_capsule", lambda row: dict(original(row), **check))
    _stop(tmp_path, "capsule", "opening 1", next(iter(check)))


def test_refusal_preserves_previous_plan_then_clean_retry(tmp_path):
    _write_inputs(tmp_path)
    out, body = tmp_path / "stage2.json", tmp_path / "body.npz"
    out.write_bytes(b"previous plan")
    partial = tmp_path / "stage2.json.partial"
    os.link(body, partial)
    clean = body.read_bytes()
    verts, fn, fi = _body()
    verts[:, 0] += 1.0
    np.savez(body, verts=verts, fn=fn, fi=fi)
    errors = []
    for _ in range(2):
        with pytest.raises(SystemExit, match="opening 1") as exc:
            s2.main(_argv(tmp_path))
        errors.append(str(exc.value))
        assert out.read_bytes() == b"previous plan"
    assert errors[0] == errors[1]
    body.write_bytes(clean)
    assert s2.main(_argv(tmp_path)) == 0
    assert json.loads(out.read_bytes())["report"]["openings"]["ok"] == 1
    assert partial.read_bytes() == body.read_bytes() == clean


@pytest.mark.parametrize("d", [0.59, np.nextafter(0.6, 0), 0.6, np.nextafter(0.6, 1), 0.61])
def test_match_distance_boundary(tmp_path, monkeypatch, d):
    _write_inputs(tmp_path)
    op = _opening()
    centre = np.mean(op["border"], axis=0)
    # Put the opening at the exact origin so subtraction introduces no boundary roundoff.
    _inject_openings(monkeypatch, [dict(op, border=(np.array(op["border"]) - centre).tolist())])
    original = s2.revit_window
    monkeypatch.setattr(s2, "revit_window", lambda tri: dict(original(tri), centre=np.array([d, 0, 0])))
    if d < 0.6:
        monkeypatch.setattr(s2.windowgen_core, "build_type", lambda *a: pytest.fail("accepted match reached build"))
        with pytest.raises(pytest.fail.Exception, match="accepted match reached build"):
            s2.main(_argv(tmp_path))
    else:
        _stop(tmp_path, "opening 1", "0.6 m")


@pytest.mark.parametrize("case", ["no windows", "unused", "tie", "no glass"])
def test_incomplete_source_stops(tmp_path, monkeypatch, case):
    _write_inputs(tmp_path)
    orig = s2.crop_objects

    def objects(path, prefixes, band):
        rows = orig(path, prefixes, band)
        if not rows:
            return rows
        if case == "no windows":
            return []
        if case == "no glass":
            return [dict(rows[0], tri=rows[0]["tri"][:4])]
        offset = [1, 0, 0] if case == "unused" else [0, 0, 0]
        return rows + [dict(rows[0], name="second window", tri=rows[0]["tri"] + offset)]

    monkeypatch.setattr(s2, "crop_objects", objects)
    expected = {"no windows": ("opening 1", "no Revit window"), "unused": ("unused", "second window"),
                "tie": ("opening 1", "tied", "second window"), "no glass": ("opening 1", "glass")}
    _stop(tmp_path, *expected[case])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("target", ["opening", "Revit", "band"])
def test_invalid_geometry_stops(tmp_path, monkeypatch, value, target):
    _write_inputs(tmp_path)
    if target == "opening":
        op = _opening()
        op["border"][0][0] = value
        _inject_openings(monkeypatch, [op])
        _stop(tmp_path, "opening 1", "non-finite")
    elif target == "Revit":
        tri = _window_tris()
        tri[0, 0, 2] = value
        np.savez(tmp_path / "crop.npz", tri=tri, obj=np.zeros(len(tri), int), names=["Окн_Окн_invalid"])
        _stop(tmp_path, "Окн_Окн_invalid", "non-finite")
    else:
        with pytest.raises(SystemExit, match="band"):
            s2.main([*_argv(tmp_path)[:-2], str(value), "3.15"])
        assert not (tmp_path / "stage2.json").exists()


@pytest.mark.parametrize("name", ["body.npz", "crop.npz", "keys.json", "standard.json"])
def test_output_alias_refused(tmp_path, name):
    _write_inputs(tmp_path)
    (tmp_path / "keys.json").write_text("{}", encoding="utf-8")
    (tmp_path / "standard.json").write_bytes((ROOT / "library/windows/standard.json").read_bytes())
    source, alias = tmp_path / name, tmp_path / "alias.json"
    before = source.read_bytes()
    os.link(source, alias)
    with pytest.raises(SystemExit, match="must not be an input"):
        s2.main([*_argv(tmp_path, alias), "--keys", str(tmp_path / "keys.json"),
                 "--standard", str(tmp_path / "standard.json")])
    assert source.read_bytes() == alias.read_bytes() == before


def test_output_rebound_before_write(tmp_path, monkeypatch):
    _write_inputs(tmp_path)
    source, out = tmp_path / "body.npz", tmp_path / "stage2.json"
    before = source.read_bytes()
    original = s2.capsule_core.plan

    def rebind(*args):
        os.link(source, out)
        return original(*args)

    monkeypatch.setattr(s2.capsule_core, "plan", rebind)
    with pytest.raises(SystemExit, match="must not be an input"):
        s2.main(_argv(tmp_path))
    assert source.read_bytes() == out.read_bytes() == before
