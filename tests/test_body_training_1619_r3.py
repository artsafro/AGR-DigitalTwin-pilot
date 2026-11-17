"""#1619 round 3 (Artem: "polygons go into the building"): outer-envelope contour, envelope gate, inset side.

All geometry here is SYNTHETIC (rectangles and an L block), not customer data.
"""
import importlib.util
import json
import math
import random
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "jobs" / "garibaldi22" / "body-training-1619" / "hooks"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


floor_mod = _load(HOOKS / "floor_from_dump.py", "floor_from_dump_1619r3")
env_mod = _load(HOOKS / "envelope_check.py", "envelope_check_1619r3")
inset_mod = _load(HOOKS / "module_build.py", "module_build_1619r3")  # pure helpers only; bpy is imported in _run()

L_XY = [[0, 0], [30, 0], [30, 10], [12, 10], [12, 25], [0, 25]]  # CCW, asymmetric


# ---------- inset boxes sit on the OUTWARD side of a CCW ring ----------

def test_inset_box_outward_on_every_edge_of_a_ccw_ring():
    ring = Polygon(L_XY)
    for a, b in zip(L_XY, L_XY[1:] + L_XY[:1]):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        rot = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        cs = inset_mod.box_corners(mx, my, 0.0, 1.0, 0.5, 0.6, rot)
        far = cs[2:4]  # (w/2, d), (-w/2, d): the outer face of the basket
        assert all(not ring.contains(Point(p[0], p[1])) and ring.exterior.distance(Point(p[0], p[1])) > 0.49 for p in far)


def test_inset_box_generated_angles_all_outward():
    rnd = random.Random(1619)
    for _ in range(500):
        rot = rnd.uniform(-360, 360)
        cx, cy, d = rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(0.05, 2)
        nx, ny = math.sin(math.radians(rot)), -math.cos(math.radians(rot))  # right of the tangent
        for p in inset_mod.box_corners(cx, cy, 0.0, 1.0, d, 1.0, rot):
            assert (p[0] - cx) * nx + (p[1] - cy) * ny >= -1e-9


@pytest.mark.parametrize("bad", [(0, 0, 0, 1, float("nan"), 1, 0), (0, 0, 0, 1, 0, 1, 0), (0, 0, 0, -1, 1, 1, 0),
                                 (0, 0, 0, 1, 1, 1, float("inf"))])
def test_inset_box_fails_closed(bad):
    with pytest.raises(ValueError):
        inset_mod.box_corners(*bad)


# ---------- floor_from_dump --seal: openings closed by their filling ----------

def _quad(x0, y0, x1, y1, z0, z1):
    a, b, c, d = [x0, y0, z0], [x1, y1, z0], [x1, y1, z1], [x0, y0, z1]
    return [[a, b, c], [a, c, d]]


def _slot_crop(tmp):
    """20 x 10 block, front wall y=0 with a 2 m opening at x 9..11 leading into a 4 m deep shaft; a stair window
    (off the typical sill levels) fills the opening at the cut height; 2 typical windows on 3 floors."""
    objs = []
    walls = [(0, 0, 9, 0), (11, 0, 20, 0), (20, 0, 20, 10), (20, 10, 0, 10), (0, 10, 0, 0),
             (9, 0, 9, 4), (9, 4, 11, 4), (11, 4, 11, 0)]
    for k, w in enumerate(walls):
        objs.append(("Базовая стена w%d" % k, _quad(*w, 0, 10)))
    for f, z in enumerate((1.0, 4.0, 7.0)):
        for x0 in (2, 14):
            objs.append(("Окно typ f%d x%d" % (f, x0), _quad(x0, 0, x0 + 2, 0, z, z + 1.5)))
    objs.append(("Окно stair", _quad(9, 0, 11, 0, 2.5, 3.9)))
    tri, obj, names = [], [], []
    for i, (n, ts) in enumerate(objs):
        tri += ts
        obj += [i] * len(ts)
        names.append(n)
    p = tmp / "crop.npz"
    np.savez(p, tri=np.array(tri, float), obj=np.array(obj), mat=np.zeros(len(obj), int), names=np.array(names),
             mats=np.array([""]))
    return p


def test_seal_keeps_contour_out_of_the_shaft(tmp_path):
    crop = _slot_crop(tmp_path)
    floor_mod.main([str(crop), str(tmp_path / "open.json")])
    floor_mod.main([str(crop), str(tmp_path / "seal.json"), "--seal", "windows"])
    rect = Polygon([[0, 0], [20, 0], [20, 10], [0, 10]])
    dive = lambda f: max(rect.exterior.distance(Point(p)) for p in json.loads((tmp_path / f).read_text("utf-8"))["rings"][0]["xy"])
    assert dive("open.json") > 3.5  # without sealing the ring follows the shaft (round 2 defect, witness)
    assert dive("seal.json") < 0.1  # sealed: the outer envelope only
    spec = json.loads((tmp_path / "seal.json").read_text("utf-8"))
    assert abs(Polygon(spec["rings"][0]["xy"]).area - 200) < 3.0 and spec["counts"]["windows_used"] == 2


def test_seal_unknown_class_is_an_error(tmp_path):
    out = tmp_path / "f.json"
    with pytest.raises(SystemExit) as e:
        floor_mod.main([str(_slot_crop(tmp_path)), str(out), "--seal", "doors"])
    assert "doors" in str(e.value) and not out.exists()


# ---------- envelope_check gate ----------

def _etalon(tmp, xy=L_XY):
    verts, fi = [], []
    for a, b in zip(xy, xy[1:] + xy[:1]):
        base = len(verts)
        verts += [[a[0], a[1], 0], [b[0], b[1], 0], [b[0], b[1], 10], [a[0], a[1], 10]]
        fi += [base + i for i in (0, 1, 2, 0, 2, 3)]
    p = tmp / "etalon.npz"
    np.savez(p, verts=np.array(verts, float), fn=np.full(len(fi) // 3, 3), fi=np.array(fi), uvf=np.zeros((len(fi), 2)))
    return p


def _spec(tmp, xy, name):
    p = tmp / name
    p.write_text(json.dumps({"contour_section_z": 5.0, "rings": [{"xy": xy, "cuts": []}]}), encoding="utf-8")
    return p


SLOT = [[0, 0], [9, 0], [9, 4], [11, 4], [11, 0], [30, 0], [30, 10], [12, 10], [12, 25], [0, 25]]
SHALLOW = [[0, 0], [9, 0], [9, 0.2], [12, 0.2], [12, 0], [30, 0], [30, 10], [12, 10], [12, 25], [0, 25]]


@pytest.mark.parametrize("xy,verdict", [(L_XY, "pass"), (SLOT, "fail"), (SHALLOW, "fail")])
def test_envelope_gate(tmp_path, xy, verdict):
    et = _etalon(tmp_path)
    fl = _spec(tmp_path, xy, "floor.json")
    out = tmp_path / "env.json"
    args = [str(fl), str(et), str(out), "--dz", "0", "--png", str(tmp_path / "top.png")]
    if verdict == "pass":
        env_mod.main(args)
    else:
        with pytest.raises(SystemExit) as e:
            env_mod.main(args)
        assert e.value.code == 2
    rep = json.loads(out.read_text("utf-8"))
    assert rep["verdict"] == verdict
    if xy is SLOT:
        assert rep["inward"] and abs(rep["inward_max_depth_m"] - 4.0) < 0.3
    if xy is SHALLOW:  # 0.2 m recess: not "inside" past the threshold, but a texture pocket to fill
        assert not rep["inward"] and rep["pockets_fill"] == 1 and "texture" in rep["pockets"][0]["reason"]


@pytest.mark.parametrize("extra,msg", [(["--texture-depth", "nan"], "finite"), (["--texture-depth", "0"], "finite"),
                                       (["--pocket-close", "inf"], "finite")])
def test_envelope_fails_closed_on_bad_thresholds(tmp_path, extra, msg):
    out = tmp_path / "env.json"
    with pytest.raises(SystemExit) as e:
        env_mod.main([str(_spec(tmp_path, L_XY, "f.json")), str(_etalon(tmp_path)), str(out), "--dz", "0"] + extra)
    assert msg in str(e.value) and not out.exists()


def test_envelope_refuses_output_aliasing_an_input(tmp_path):
    fl = _spec(tmp_path, L_XY, "f.json")
    before = fl.read_bytes()
    with pytest.raises(SystemExit) as e:
        env_mod.main([str(fl), str(_etalon(tmp_path)), str(fl), "--dz", "0"])
    assert "refused" in str(e.value) and fl.read_bytes() == before
    out = tmp_path / "a.json"
    with pytest.raises(SystemExit):
        env_mod.main([str(fl), str(_etalon(tmp_path)), str(out), "--dz", "0", "--png", str(out)])
    assert not out.exists()


# ---------- wire_sheet --backfaces: an open body's far wall hides what lies behind it ----------

wire_mod = _load(ROOT / "docs" / "research" / "body-modelling-1618" / "wire_sheet.py", "wire_sheet_1619r3")


def _two_quads(tmp):
    """View ny looks along +y. Wall at y=1 seen from its back (normal +y); a small red quad at y=2 behind it,
    facing the camera (normal -y); a coplanar quad ON the wall (an inset back face) must not z-fight through."""
    v = np.array([[0, 1, 0], [0, 1, 4], [4, 1, 4], [4, 1, 0],          # wall, normal +y (back face for ny)
                  [1, 2, 1], [3, 2, 1], [3, 2, 3], [1, 2, 3],          # behind, normal -y (front face)
                  [1.5, 1, 1.5], [2.5, 1, 1.5], [2.5, 1, 2.5], [1.5, 1, 2.5]], float)  # coplanar, normal -y
    p = tmp / "dump.npz"
    np.savez(p, verts=v, jverts=v, jn=np.array([4, 4, 4]), ji=np.arange(12), jmats=np.array([0, 1, 1]),
             fi=np.array([0, 1, 2, 0, 2, 3]), uvf=np.zeros((6, 2)))
    return p


def test_wire_sheet_backfaces_hide_shells_behind_the_far_wall(tmp_path):
    rgb = tmp_path / "rgb.json"
    rgb.write_text(json.dumps([[100, 100, 100], [220, 0, 0]]), encoding="utf-8")
    def red(png):
        px = np.asarray(Image.open(png).convert("RGB"))
        return int(((px[:, :, 0] > 150) & (px[:, :, 1] < 60)).sum())
    a, b = tmp_path / "cull.png", tmp_path / "bf.png"
    base = [str(_two_quads(tmp_path)), "--view", "ny", "--ppm", "40", "--mat-rgb", str(rgb)]
    wire_mod.main(base + ["--out", str(a)])
    wire_mod.main(base + ["--backfaces", "--out", str(b)])
    assert red(a) > 1000  # culled wall: the shell behind it shows through (round 2 "baskets above the body")
    assert red(b) == 0  # the wall's back face occludes it; the coplanar face does not z-fight through
