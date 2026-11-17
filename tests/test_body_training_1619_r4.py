"""Round 4 of the #1619 body training polygon (G22 body 2): floor_from_dump --fill applies the envelope gate's
repair list (texture pockets shallower than 0.4 m are closed, D341).

Pattern: n/a | new-case: tests of #1619 --fill pockets.
"""

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

HOOKS = Path(__file__).resolve().parents[1] / "jobs" / "garibaldi22" / "body-training-1619" / "hooks"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


floor_mod = _load(HOOKS / "floor_from_dump.py", "floor_from_dump_1619r4")


def _quad(x0, y0, x1, y1, z0, z1):
    a, b, c, d = [x0, y0, z0], [x1, y1, z0], [x1, y1, z1], [x0, y0, z1]
    return [[a, b, c], [a, c, d]]


POCKET = [[9, 0], [10.5, 0], [10.5, 0.1], [9, 0.1]]  # 1.5 m wide, 0.1 m deep recess of the front wall


def _pocket_crop(tmp, x0=9.0, d=0.1):
    """20 x 10 block whose front wall has a 1.5 m x d recess at x0 (relief, texture by D341); 2 windows on 3 floors."""
    x1 = x0 + 1.5
    walls = [(0, 0, x0, 0), (x0, 0, x0, d), (x0, d, x1, d), (x1, d, x1, 0), (x1, 0, 20, 0),
             (20, 0, 20, 10), (20, 10, 0, 10), (0, 10, 0, 0)]
    objs = [("Базовая стена w%d" % k, _quad(*w, 0, 10)) for k, w in enumerate(walls)]
    for f, z in enumerate((1.0, 4.0, 7.0)):
        for x0 in (2, 14):
            objs.append(("Окно typ f%d x%d" % (f, x0), _quad(x0, 0, x0 + 2, 0, z, z + 1.5)))
    tri, obj, names = [], [], []
    for i, (n, ts) in enumerate(objs):
        tri += ts
        obj += [i] * len(ts)
        names.append(n)
    p = tmp / "crop.npz"
    np.savez(p, tri=np.array(tri, float), obj=np.array(obj), mat=np.zeros(len(obj), int), names=np.array(names),
             mats=np.array([""]))
    return p


def _fill(tmp, polys, frame="source", name="fill.json"):
    p = tmp / name
    p.write_text(json.dumps({"frame": frame, "polygons": polys}), encoding="utf-8")
    return p


def _ring(tmp, name):
    return json.loads((tmp / name).read_text("utf-8"))["rings"][0]["xy"]


def test_fill_closes_the_texture_pocket(tmp_path):
    crop = _pocket_crop(tmp_path)
    floor_mod.main([str(crop), str(tmp_path / "open.json")])
    assert any(abs(p[1] - 0.1) < 0.02 for p in _ring(tmp_path, "open.json"))  # witness: the pocket survives
    floor_mod.main([str(crop), str(tmp_path / "fill.json"), "--fill", str(_fill(tmp_path, [POCKET + POCKET[:1]],
                                                                                name="rep.json"))])
    xy = _ring(tmp_path, "fill.json")
    assert len(xy) == 4 and all(min(abs(p[1]), abs(p[1] - 10)) < 0.06 for p in xy)  # 5 cm corner joints
    spec = json.loads((tmp_path / "fill.json").read_text("utf-8"))
    grow = Polygon(xy).area - Polygon(_ring(tmp_path, "open.json")).area
    assert 0.1 < grow < 0.25 and spec["counts"]["windows_used"] == 2  # only the 1.5 x 0.1 pocket was added
    assert [f["index"] for f in spec["filled"]] == [0]


@pytest.mark.parametrize("x0", [4.5, 9.0, 11.3, 15.0])
@pytest.mark.parametrize("d", [0.1, 0.2, 0.35])
def test_fill_generated_pockets_along_the_wall(tmp_path, x0, d):
    """Probe (12 cases): pockets at generated positions/depths; with their repair polygon the ring never bulges
    outward and keeps no vertex inside the block deeper than 0.02 m."""
    crop = _pocket_crop(tmp_path, x0, d)
    poly = [[x0, 0], [x0 + 1.5, 0], [x0 + 1.5, d], [x0, d]]
    floor_mod.main([str(crop), str(tmp_path / "f.json"), "--fill", str(_fill(tmp_path, [poly]))])
    xy = _ring(tmp_path, "f.json")
    assert all(-0.02 < p[1] < 10.02 and -0.02 < p[0] < 20.02 for p in xy)
    assert all(min(p[1], 10 - p[1], p[0], 20 - p[0]) < 0.02 for p in xy)


@pytest.mark.parametrize("payload,msg", [
    ({"frame": "etalon", "polygons": [POCKET]}, "frame"),
    ({"frame": "source", "polygons": []}, "no polygons"),
    ({"frame": "source", "polygons": [[[50, 50], [51, 50], [51, 51]]]}, "polygon 0"),
    ({"frame": "source", "polygons": [[[2, 2], [5, 2], [5, 5], [2, 5]]]}, "polygon 0"),
    ({"frame": "source", "polygons": [[[9, 0], [math.nan, 0], [10.5, 0.1]]]}, "polygon 0"),
    ({"frame": "source", "polygons": [[[9, 0], [10, 0]]]}, "polygon 0"),
])
def test_fill_fails_closed(tmp_path, payload, msg):
    rep = tmp_path / "rep.json"
    rep.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "f.json"
    with pytest.raises(SystemExit) as e:
        floor_mod.main([str(_pocket_crop(tmp_path)), str(out), "--fill", str(rep)])
    assert msg in str(e.value) and not out.exists()


def test_fill_refuses_output_aliasing_the_repair_list(tmp_path):
    rep = _fill(tmp_path, [POCKET])
    before = rep.read_bytes()
    with pytest.raises(SystemExit) as e:
        floor_mod.main([str(_pocket_crop(tmp_path)), str(rep), "--fill", str(rep)])
    assert "refused" in str(e.value) and rep.read_bytes() == before
