"""#1619 polygon stage 1, site-63 tower B v007 (jobs/POLY63-B): two rings on the 63A module builder.

The belt caps are quad ladders between the shared stations of the typical ring A and the belt ring B
(stack63b.sync). Fixtures: tests/fixtures/poly63b/floor_{A,B}.json = the 63A chain output for tower B
(floor_from_dump -> pockets_self -> contour_d337 -> zones_from_types, FBX world metres).

Pattern: n/a | new-case: two-ring tower on the 63A module builder (tests).
"""
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "poly63b"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stack = _load(ROOT / "jobs" / "POLY63-B" / "hooks" / "stack63b.py", "stack63b")
floor_mod = _load(ROOT / "jobs" / "garibaldi22" / "body-training-1619" / "hooks" / "floor_from_dump.py", "ffd_63b")


def _cells(pa, pb):
    n = len(pa)
    out = []
    for i in range(n):
        j = (i + 1) % n
        u = []
        for p in (pa[i], pa[j], pb[j], pb[i]):
            if not any(math.dist(p, q) < 1e-3 for q in u):
                u.append(p)
        out.append(u)
    return out


def _area(u):
    return 0.5 * sum(u[k][0] * u[(k + 1) % len(u)][1] - u[(k + 1) % len(u)][0] * u[k][1] for k in range(len(u)))


def _rounded_rect(w, h, r, n, inset=0.0):
    """CCW rectangle [inset, w-inset] x [inset, h-inset] with arc corners of radius r (n segments each)."""
    x0, y0, x1, y1 = inset, inset, w - inset, h - inset
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


@pytest.fixture(scope="module")
def real():
    fa = json.load(open(FIX / "floor_A.json", encoding="utf-8"))
    fb = json.load(open(FIX / "floor_B.json", encoding="utf-8"))
    ra, rb = fa["rings"][0], fb["rings"][0]
    return fa, fb, stack.sync(ra["xy"], ra["cuts"], rb["xy"], rb["cuts"], 3.6, 0.03)


def test_real_rings_cap_is_a_pure_quad_ladder(real):
    _, _, (merged, pa, pb, rep) = real
    cells = _cells(pa, pb)
    tris = [c for c in cells if len(c) == 3 and abs(_area(c)) > 1e-6]
    assert not tris, "cap triangles at %s" % [c[0] for c in tris][:5]
    assert rep["pairs"] == len(pa) == len(pb)
    # no cell folds over itself or a neighbour (bow-tie / crossed rungs): every cell is a simple polygon and the
    # cells tile the cap without overlap (rings that cross share the crossing point, so the sign may flip there)
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(c) for c in cells if len(c) >= 3 and abs(_area(c)) > 1e-6]
    assert all(p.is_valid for p in polys), [list(p.exterior.coords)[0] for p in polys if not p.is_valid]
    assert abs(sum(p.area for p in polys) - unary_union(polys).area) < 1e-3


def test_real_rings_keep_every_window_end_and_corner(real):
    """Regression (v007 run 7): an "AB" pair dropped by the plain LIS lost the B window end s=9.4996."""
    fa, fb, (merged, pa, pb, rep) = real
    for f, pts in ((fa, pa), (fb, pb)):
        xy = f["rings"][0]["xy"]
        cum = stack.perim_s(xy)
        ends = {w[1] for w in f["windows"]} | {w[2] for w in f["windows"]}
        for s in ends:
            p = stack.point_at(xy, cum, s)
            assert min(math.dist(p, q) for q in pts) < 0.015, "window end s=%.4f lost" % s
        for c in xy:
            assert min(math.dist(c, q) for q in pts) < 0.015, "corner %r lost" % (c,)


def test_real_rings_no_sliver_strips_except_listed(real):
    _, _, (merged, pa, pb, rep) = real
    short = []
    for pts in (pa, pb):
        n = len(pts)
        short += [i for i in range(n) if 1e-3 < math.dist(pts[i], pts[(i + 1) % n]) < 0.01]
    assert not short, "ring edges under 1 cm (full-height sliver strips): %s" % short[:8]


def test_synthetic_arc_corners_map_without_fans():
    a = _rounded_rect(20.0, 12.0, 1.5, 10)
    b = _rounded_rect(20.0, 12.0, 0.8, 5, inset=1.0)
    merged, pa, pb, rep = stack.sync(a, [], b, [], 3.6, 0.03)
    cells = _cells(pa, pb)
    assert all(len(c) == 4 for c in cells)
    for pts in (pa, pb):
        n = len(pts)
        assert min(math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)) > 0.02


assemble = _load(ROOT / "jobs" / "POLY63-B" / "hooks" / "assemble63b.py", "assemble63b")


def test_overhang_cells_face_the_other_way(real):
    """Regression (v007 build 14): where ring B pokes out past ring A (N pilaster step, E step) the cap at +23.55
    is the UNDERSIDE of the belt storey; forcing every +23.55 cell to +Z gave 56 edges with inverted winding."""
    fa, _, (merged, pa, pb, rep) = real
    ccw = stack.ring_ccw(fa["rings"][0]["xy"])
    cells = [c for c in _cells(pa, pb) if len(c) >= 3 and abs(_area(c)) > 1e-6]
    over = [c for c in cells if (_area(c) > 0) != ccw]
    assert over, "fixture lost the B-outside-A cells"
    for c in over:
        assert assemble.cap_faces_up(c, top=True, a_ccw=ccw) is False
        assert assemble.cap_faces_up(c, top=False, a_ccw=ccw) is True
    inner = next(c for c in cells if (_area(c) > 0) == ccw)
    assert assemble.cap_faces_up(inner, top=True, a_ccw=ccw) is True
    assert assemble.cap_faces_up(inner, top=False, a_ccw=ccw) is False


def test_floor_from_dump_has_belt_options():
    import argparse
    import inspect
    src = inspect.getsource(floor_mod.main)
    for flag in ("--deslit", "--section-z", "--sill-band"):
        assert flag in src
    assert isinstance(argparse, object)
