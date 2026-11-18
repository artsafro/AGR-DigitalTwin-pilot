"""#1619 training polygon hooks: finish zones from an etalon texture, --clip, wire sheet material colours.

Pattern: n/a | new-case: tests of the #1619 zones/clip/wire-sheet hooks.

All geometry here is SYNTHETIC (an L-shaped test block), not customer data.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "jobs" / "garibaldi22" / "body-training-1619" / "hooks"

L_XY = [[0, 0], [30, 0], [30, 10], [12, 10], [12, 25], [0, 25]]  # CCW, asymmetric (registration is unique)
DARK, LIGHT, ODD = (70, 70, 70), (210, 210, 210), (255, 0, 255)
PALETTE = {"tol": 60, "classes": {"DARK": list(DARK), "LIGHT": list(LIGHT)}}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


zones_mod = _load(HOOKS / "zones_from_etalon.py", "zones_from_etalon_1619")
floor_mod = _load(HOOKS / "floor_from_dump.py", "floor_from_dump_1619")
wire_mod = _load(ROOT / "docs" / "research" / "body-modelling-1618" / "wire_sheet.py", "wire_sheet_1619")


def _etalon(tmp, edge_cols, basket=True, scale=1.0, xy=L_XY):
    """Synthetic etalon: one wall quad (2 tris) per L edge, UV into a 3-px atlas [DARK, LIGHT, ODD]."""
    col_u = {DARK: 1 / 6, LIGHT: 3 / 6, ODD: 5 / 6}
    verts, fi, uvf = [], [], []
    xy = [[x * scale, y * scale] for x, y in xy]
    for k, (a, b) in enumerate(zip(xy, xy[1:] + xy[:1])):
        base = len(verts)
        verts += [[a[0], a[1], 0], [b[0], b[1], 0], [b[0], b[1], 10], [a[0], a[1], 10]]
        u = col_u[edge_cols[k]]
        for tri in ((0, 1, 2), (0, 2, 3)):
            fi += [base + i for i in tri]
            uvf += [[u, 0.5]] * 3
    if basket:  # a 1 m inset box hugging edge 0 with an off-palette colour: must be skipped, not unmapped
        base = len(verts)
        box = [[5, -1, 4], [6, -1, 4], [6, 0, 4], [5, 0, 4], [5, -1, 5], [6, -1, 5], [6, 0, 5], [5, 0, 5]]
        verts += box
        for q in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                fi += [base + i for i in tri]
                uvf += [[col_u[ODD], 0.5]] * 3
    p = tmp / "etalon.npz"
    np.savez(p, verts=np.array(verts, float), fn=np.full(len(fi) // 3, 3), fi=np.array(fi),
             uvf=np.array(uvf, float))
    img = tmp / "atlas.png"
    Image.fromarray(np.array([[DARK, LIGHT, ODD]], np.uint8)).save(img)
    return p, img


def _floor(tmp, xy=L_XY):
    spec = {"contour_section_z": 5.0, "rings": [{"xy": xy, "cuts": []}],
            "materials": {"WALL_A": [1, 1, 1], "WINDOW": [0, 0, 1], "INSET": [0, 1, 1]}}
    p = tmp / "floor.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    pal = tmp / "palette.json"
    pal.write_text(json.dumps(PALETTE), encoding="utf-8")
    return p, pal


ALT = [DARK, LIGHT, DARK, LIGHT, DARK, LIGHT]


def test_zones_follow_etalon_colours_and_snap_to_corners(tmp_path):
    et, img = _etalon(tmp_path, ALT)
    fl, pal = _floor(tmp_path)
    out = tmp_path / "out.json"
    zones_mod.main([str(fl), str(et), str(img), str(out), "--dz", "0", "--palette", str(pal)])
    spec = json.loads(out.read_text(encoding="utf-8"))
    z = spec["rings"][0]["zones"]
    assert [n for _, _, n in z] == ["WALL_DARK", "WALL_LIGHT"] * 3
    corners = np.cumsum([0] + [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(L_XY, L_XY[1:] + L_XY[:1])])
    assert np.allclose([s0 for s0, _, _ in z], corners[:6], atol=1e-3)
    rep = spec["zones_report"]
    assert rep["borders_new_cut"] == 0 and rep["borders_snapped_to_existing_cut"] == 5
    assert rep["etalon_inset_tris_skipped"] == 8
    assert "WALL_A" not in spec["materials"] and {"WALL_DARK", "WALL_LIGHT"} <= set(spec["materials"])
    # every perimeter metre is in exactly one zone
    assert z[0][0] == 0 and abs(z[-1][1] - corners[-1]) < 1e-3
    assert all(abs(a[1] - b[0]) < 1e-9 for a, b in zip(z, z[1:]))


def test_zone_border_off_corner_becomes_a_new_cut(tmp_path):
    # the etalon changes colour in the middle of the 30 m edge -> one border off every corner: a new vertical cut
    et, img = _etalon(tmp_path, [DARK, LIGHT, DARK, LIGHT, DARK, LIGHT, DARK],
                      xy=[[0, 0], [15, 0], [30, 0], [30, 10], [12, 10], [12, 25], [0, 25]])
    fl, pal = _floor(tmp_path)
    out = tmp_path / "out.json"
    zones_mod.main([str(fl), str(et), str(img), str(out), "--dz", "0", "--palette", str(pal)])
    spec = json.loads(out.read_text(encoding="utf-8"))
    rep = spec["zones_report"]
    assert (rep["borders_new_cut"], rep["borders_snapped_to_existing_cut"]) == (1, 5)
    assert any(abs(c - 15.0) <= 0.1 for c in spec["rings"][0]["cuts"])


@pytest.mark.parametrize("case", ["unmapped", "out_is_input", "no_register", "empty_palette", "nan", "no_cut"])
def test_zones_fail_closed(tmp_path, case):
    cols = list(ALT)
    if case == "unmapped":
        cols[0] = ODD
    et, img = _etalon(tmp_path, cols, scale=2.0 if case == "no_register" else 1.0)
    xy = [[float("nan"), 0]] + L_XY[1:] if case == "nan" else L_XY
    fl, pal = _floor(tmp_path, xy=xy)
    if case == "empty_palette":
        pal.write_text(json.dumps({"tol": 60, "classes": {}}), encoding="utf-8")
    out = fl if case == "out_is_input" else tmp_path / "out.json"
    dz = "100" if case == "no_cut" else "0"
    before = fl.read_bytes()
    with pytest.raises(SystemExit) as e:
        zones_mod.main([str(fl), str(et), str(img), str(out), "--dz", dz, "--palette", str(pal)])
    assert e.value.code not in (0, None)
    assert fl.read_bytes() == before
    if case != "out_is_input":
        assert not out.exists()
    if case == "unmapped":
        assert "255, 0, 255" in str(e.value)


def _crop(tmp):
    tri = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], float)
    p = tmp / "crop.npz"
    np.savez(p, tri=tri, obj=np.array([0]), mat=np.array([0]), names=np.array(["Окно x"]), mats=np.array([""]))
    return p


@pytest.mark.parametrize("poly,msg", [([[50, 50], [60, 50], [60, 60], [50, 60]], "leaves no triangles"),
                                      ([[0, 0], [1, 1], [2, 2]], "empty or invalid")])
def test_floor_clip_fails_closed(tmp_path, poly, msg):
    crop = _crop(tmp_path)
    clip = tmp_path / "clip.json"
    clip.write_text(json.dumps(poly), encoding="utf-8")
    out = tmp_path / "floor.json"
    with pytest.raises(SystemExit) as e:
        floor_mod.main([str(crop), str(out), "--clip", str(clip)])
    assert msg in str(e.value) and not out.exists()


def _dump(tmp, mats):
    v = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], float)
    p = tmp / "dump.npz"
    np.savez(p, verts=v, jverts=v, jn=np.array([4]), ji=np.array([0, 1, 2, 3]), jmats=np.array(mats),
             fi=np.array([0, 1, 2, 0, 2, 3]), uvf=np.zeros((6, 2)))
    return p


def test_wire_sheet_mat_rgb_colours_and_refuses_unmapped(tmp_path):
    rgb = tmp_path / "rgb.json"
    rgb.write_text(json.dumps([[200, 10, 10]]), encoding="utf-8")
    out = tmp_path / "w.png"
    wire_mod.main([str(_dump(tmp_path, [0])), "--view", "ny", "--ppm", "40", "--mat-rgb", str(rgb), "--out", str(out)])
    px = np.asarray(Image.open(out).convert("RGB"))
    assert ((px[:, :, 0] > 120) & (px[:, :, 1] < 40)).sum() > 500  # quad filled with its material colour
    out2 = tmp_path / "w2.png"
    with pytest.raises(SystemExit) as e:
        wire_mod.main([str(_dump(tmp_path, [1])), "--view", "ny", "--mat-rgb", str(rgb), "--out", str(out2)])
    assert "[1]" in str(e.value) and not out2.exists()
