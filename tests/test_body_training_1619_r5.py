"""Round 5 of the #1619 body training polygon (stage 1 «бадик с проемами», Artem 2026-11-17): windows become
openings with the Revit reveal depth (floor_from_dump --openings, module_build.inner_offset); baskets are deferred
to stage 2.

Pattern: n/a | new-case: tests of #1619 stage-1 openings.
"""

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString, Polygon

HOOKS = Path(__file__).resolve().parents[1] / "jobs" / "garibaldi22" / "body-training-1619" / "hooks"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


floor_mod = _load(HOOKS / "floor_from_dump.py", "floor_from_dump_1619r5")
build_mod = _load(HOOKS / "module_build.py", "module_build_1619r5")  # pure helpers only


def _quad(x0, y0, x1, y1, z0, z1):
    a, b, c, d = [x0, y0, z0], [x1, y1, z0], [x1, y1, z1], [x0, y0, z1]
    return [[a, b, c], [a, c, d]]


def _crop(tmp, depth=0.15, basket=True):
    """20 x 10 block; front wall y=0 (outside is y<0). Two windows per floor on 3 floors: frame planes at y=depth
    and y=depth+0.06 (behind the facade line), one flashing triangle on the facade line; one AC basket per floor."""
    walls = [(0, 0, 20, 0), (20, 0, 20, 10), (20, 10, 0, 10), (0, 10, 0, 0)]
    objs = [("Базовая стена w%d" % k, _quad(*w, 0, 10)) for k, w in enumerate(walls)]
    for f, z in enumerate((1.0, 4.0, 7.0)):
        for x0 in (2, 14):
            t = _quad(x0, depth, x0 + 2, depth, z, z + 1.5) + _quad(x0, depth + 0.06, x0 + 2, depth + 0.06, z, z + 1.5)
            t += _quad(x0 + 0.1, depth + 0.03, x0 + 1.9, depth + 0.03, z + 0.1, z + 1.4)
            t.append([[x0, 0.0, z], [x0 + 2, 0.0, z], [x0 + 1, depth, z]])  # flashing to the facade line
            objs.append(("Окно typ f%d x%d" % (f, x0), t))
        if basket:
            objs.append(("Корзина для кондиционера f%d" % f, _quad(8, -0.6, 10, -0.6, z + 1.9, z + 2.9)
                         + _quad(8, -0.01, 10, -0.01, z + 1.9, z + 2.9)))
    tri, obj, names = [], [], []
    for i, (n, ts) in enumerate(objs):
        tri += ts
        obj += [i] * len(ts)
        names.append(n)
    p = tmp / ("crop_%s.npz" % str(depth).replace(".", "_"))
    np.savez(p, tri=np.array(tri, float), obj=np.array(obj), mat=np.zeros(len(obj), int), names=np.array(names),
             mats=np.array([""]))
    return p


def _spec(tmp, crop, *extra, name="floor.json"):
    floor_mod.main([str(crop), str(tmp / name), *extra])
    return json.loads((tmp / name).read_text("utf-8"))


def test_openings_carry_the_revit_reveal_and_defer_baskets(tmp_path):
    spec = _spec(tmp_path, _crop(tmp_path), "--openings")
    assert spec["stage"] == "body+openings"
    assert [len(w) for w in spec["windows"]] == [6, 6]
    assert all(w[3:5] == [0, 1] and abs(w[5] - 0.15) <= 0.01 for w in spec["windows"])
    assert spec["insets"] == [] and len(spec["deferred"]) == 1  # the reference floor's basket, with its reason
    assert "stage 2" in spec["deferred"][0]["reason"]
    assert spec["counts"]["reveal_m"] == [w[5] for w in spec["windows"]][:1]


def test_without_openings_the_spec_is_unchanged(tmp_path):
    spec = _spec(tmp_path, _crop(tmp_path))
    assert [len(w) for w in spec["windows"]] == [3, 3] and len(spec["insets"]) == 1 and spec["deferred"] == []


@pytest.mark.parametrize("depth", [0.05, 0.1, 0.18, 0.25, 0.32])
def test_reveal_depth_generated(tmp_path, depth):
    spec = _spec(tmp_path, _crop(tmp_path, depth, basket=False), "--openings")
    assert all(abs(w[5] - depth) <= 0.011 for w in spec["windows"]), spec["windows"]


@pytest.mark.parametrize("depth", [0.0, 0.01])
def test_window_without_reveal_is_an_error_naming_it(tmp_path, depth):
    with pytest.raises(SystemExit, match="refused: window Окно typ f1 x"):
        _spec(tmp_path, _crop(tmp_path, depth, basket=False), "--openings")


def test_reveal_depth_fail_closed_on_empty_and_nan():
    ring = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
    assert math.isnan(floor_mod.reveal_depth([], ring))
    assert math.isnan(floor_mod.reveal_depth([(1.0, float("nan")), (1.0, 0.2)], ring))
    assert floor_mod.reveal_depth([(1.0 + 0.2 * k, 0.2) for k in range(9)] + [(1.5, -0.1)], ring) \
        == pytest.approx(0.2, abs=0.031)


def test_reveal_depth_skips_the_flashing_layer_real_1_sash_histogram():
    """Regression (G22 body 2, window [4259780]): the P90 rule read 0.01 m because the flashing on the facade line
    is 13 % of this family's vertices; the frame's outer face (0.10 m, 41 %) is the reveal."""
    ring = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
    hist = {0.01: 42, 0.0: 18, 0.12: 36, 0.15: 36, 0.17: 138, 0.10: 186}
    xy = [(1.0 + 0.1 * (k % 18), dep) for dep, n in hist.items() for k in range(n)]
    assert floor_mod.reveal_depth(xy, ring) == pytest.approx(0.10)
    assert math.isnan(floor_mod.reveal_depth([(1.0 + 0.05 * ((k * 17) % 40), 0.01 * k) for k in range(40)], ring))


@pytest.mark.parametrize("skew_deg", [0.0, 1.5, 3.0, -3.0, 5.0])
def test_reveal_depth_follows_the_window_plane_when_skewed(skew_deg):
    """Regression (G22 k2 [3529335]): a window 3 deg off the contour smeared its frame over 0.04..-0.19 m -> NaN;
    depth is taken along the window's own plan normal from the facade point at its centre."""
    ring = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
    t = math.radians(skew_deg)
    xy = []
    for dep, n in {0.15: 300, 0.21: 200, 0.18: 150, 0.0: 60}.items():
        for k in range(n):
            u = -0.9 + 1.8 * (k % 30) / 29
            xy.append((5.0 + u * math.cos(t) - dep * math.sin(t), u * math.sin(t) + dep * math.cos(t)))
    assert floor_mod.reveal_depth(xy, ring) == pytest.approx(0.15, abs=0.011)


def _depth_to(line, p):
    return LineString(line).distance(__import__("shapely.geometry", fromlist=["Point"]).Point(p))


@pytest.mark.parametrize("r", [0.05, 0.12, 0.2, 0.35])
@pytest.mark.parametrize("ang", [0, 37, 90, 143, 215, 300])
def test_inner_offset_straight_run_is_r_inside(r, ang):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    run = [(10 + c * t, 5 + s * t) for t in (0.0, 0.7, 1.8)]
    inner = build_mod.inner_offset(run, r)
    for (x, y), (ix, iy) in zip(run, inner):
        assert abs(math.dist((x, y), (ix, iy)) - r) < 1e-9
        assert (c * (iy - y) - s * (ix - x)) > 0  # left of the CCW direction = into the body


@pytest.mark.parametrize("r", [0.08, 0.15, 0.3])
@pytest.mark.parametrize("turn", [30, 60, 90, 120])
def test_inner_offset_corner_run_keeps_r_from_both_walls(r, turn):
    """A corner window spanning a convex CCW corner: the mitre point is r from BOTH walls."""
    t = math.radians(turn)
    a, b, c = (0.0, 0.0), (2.0, 0.0), (2.0 + 2 * math.cos(t), 2 * math.sin(t))
    inner = build_mod.inner_offset([a, b, c], r)
    assert abs(_depth_to([a, (9, 0)], inner[1]) - r) < 1e-9
    far = (b[0] + 9 * math.cos(t), b[1] + 9 * math.sin(t))
    assert abs(_depth_to([(b[0] - 9 * math.cos(t), b[1] - 9 * math.sin(t)), far], inner[1]) - r) < 1e-9


@pytest.mark.parametrize("xy,r,msg", [
    ([(0, 0), (1, 0)], 0.0, "reveal depth"),
    ([(0, 0), (1, 0)], -0.1, "reveal depth"),
    ([(0, 0), (1, 0)], 1.0, "reveal depth"),
    ([(0, 0), (1, 0)], float("nan"), "reveal depth"),
    ([(0, 0), (1, 0)], float("inf"), "reveal depth"),
    ([(0, 0)], 0.1, ">= 2 finite"),
    ([], 0.1, ">= 2 finite"),
    ([(0, 0), (float("nan"), 0)], 0.1, ">= 2 finite"),
    ([(0, 0), (0, 0)], 0.1, "zero-length"),
    ([(0, 0), (1, 0), (0, 0)], 0.1, "folds back"),
])
def test_inner_offset_fails_closed(xy, r, msg):
    with pytest.raises(ValueError, match=msg):
        build_mod.inner_offset(xy, r)
