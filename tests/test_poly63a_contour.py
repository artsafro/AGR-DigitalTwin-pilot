"""#1619 polygon stage 1, site-63 tower A (jobs/POLY63-A): rounded corners (D337), relief steps (D341),
finish zones from Revit wall types, and the floor_from_dump fixes found on tower A (wedge at a rounded corner,
window across the ring start). Synthetic geometry only.

Pattern: n/a | new-case: tests/test_poly63a_contour.py - site-63 tower A contour, fillet and zone hooks.
"""

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "jobs" / "POLY63-A" / "hooks"
G22 = ROOT / "jobs" / "garibaldi22" / "body-training-1619" / "hooks"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


c337 = _load(HOOKS / "contour_d337.py", "contour_d337_63a")
pockets = _load(HOOKS / "pockets_self.py", "pockets_self_63a")
zones = _load(HOOKS / "zones_from_types.py", "zones_from_types_63a")
floor_mod = _load(G22 / "floor_from_dump.py", "floor_from_dump_63a")


# --- D337 segment count -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("R,n", [(0.5, 3), (1.0, 4), (2.0, 6), (3.0, 7), (5.0, 9), (10.0, 13), (20.0, 18)])
def test_n_per_90_matches_the_bm07_table(R, n):
    assert c337.n_per_90(R, 0.02) == n


@pytest.mark.parametrize("R", [0.3, 1.4, 1.8, 7.5])
def test_n_per_90_is_the_smallest_count_within_the_sagitta(R):
    n = c337.n_per_90(R, 0.02)
    assert R * (1 - math.cos(math.radians(45 / n))) <= 0.02 + 1e-12
    if n > 1:
        assert R * (1 - math.cos(math.radians(45 / (n - 1)))) > 0.02


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_n_per_90_fails_closed(bad):
    with pytest.raises(ValueError):
        c337.n_per_90(bad, 0.02)
    with pytest.raises(ValueError):
        c337.n_per_90(1.0, bad)


def test_arc_segments_snap_never_below_the_sagitta_and_lands_near_the_texture_step():
    n0, n1, seg = c337.arc_segments(1.793, 70.0, 0.02, 0.6)
    assert n0 == 5 and n1 >= n0
    k = round(0.6 / seg)
    assert abs(seg - 0.6 / k) / seg <= 0.05
    assert c337.arc_segments(1.793, 70.0, 0.02, 0.0)[1] == n0


# --- fillets ------------------------------------------------------------------------------------------------------

def _rounded_rect(w=20.0, h=10.0, R=1.5, k=4, jitter=0.0):
    """CCW rectangle whose corner (w, 0) is an arc of radius R cut into k chords (a coarse Revit cut)."""
    pts = [(0.0, 0.0), (w - R, 0.0)]
    cx, cy = w - R, R
    for j in range(1, k):
        t = -math.pi / 2 + (math.pi / 2) * j / k
        pts.append((cx + R * math.cos(t) + jitter * (-1) ** j, cy + R * math.sin(t)))
    pts += [(w, R), (w, h), (0.0, h)]
    return pts


def test_fillet_rebuilds_the_arc_from_its_radius_with_the_sagitta_count():
    xy = _rounded_rect(R=1.5, k=3)
    out, rows = c337.fillets(xy, 0.02, 0.0)
    assert len(rows) == 1
    r = rows[0]
    assert abs(r["radius_m"] - 1.5) < 1e-6 and abs(r["angle_deg"] - 90.0) < 1e-6
    assert r["n"] == c337.n_per_90(1.5, 0.02)
    arc = [p for p in out if p[0] > 18.5 + 1e-9 and p[1] < 1.5 - 1e-9]
    assert len(arc) == r["n"] - 1  # inner arc points; the tangency points sit on the walls
    for p in arc:
        assert abs(math.dist(p, (18.5, 1.5)) - 1.5) < 1e-9
    assert Polygon(out).is_valid and Polygon(out).exterior.is_ccw


def test_fillet_refuses_a_radius_longer_than_its_walls():
    xy = _rounded_rect(w=2.0, h=1.52, R=1.5, k=4)  # the right wall above the arc is 2 cm long
    with pytest.raises(ValueError, match="walls are shorter"):
        c337.fillets(xy, 0.02, 0.0, min_wall=0.01)


def test_straight_polygon_has_no_arcs():
    out, rows = c337.fillets([(0, 0), (10, 0), (10, 5), (0, 5)])
    assert rows == [] and len(out) == 4


# --- D341 relief steps --------------------------------------------------------------------------------------------

def test_relief_step_moves_the_inner_run_out_onto_the_outer_line():
    # bottom facade y=0 from x=0..6, then a 0.1 m recess (y=0.1) from x=6..14, back to y=0 to x=20
    xy = [(0, 0), (6, 0), (6, 0.1), (14, 0.1), (14, 0), (20, 0), (20, 10), (0, 10)]
    # a pocket on both sides is closed by pockets_self; here one side opens into a corner: a one-sided step
    xy1 = [(0, 0.1), (14, 0.1), (14, 0), (20, 0), (20, 10), (0, 10)]
    out, rows = c337.flatten_steps(xy1, 0.4)
    assert len(rows) == 1 and rows[0]["moved"] == "out" and abs(rows[0]["step_m"] - 0.1) < 1e-9
    assert len(out) == 4 and min(p[1] for p in out) == pytest.approx(0.0)
    assert Polygon(out).contains(Polygon(xy1).buffer(-1e-6))  # nothing moved inward
    assert len(c337.flatten_steps(xy, 0.4)[1]) >= 1


def test_deep_step_is_kept():
    xy = [(0, 0.6), (14, 0.6), (14, 0), (20, 0), (20, 10), (0, 10)]  # 0.6 m > 0.4 m: geometry
    out, rows = c337.flatten_steps(xy, 0.4)
    assert rows == [] and len(out) == 6


def test_a_near_parallel_neighbour_does_not_throw_the_vertex_far_away():
    # the run before the inner one turns by 1.5 deg: the line intersection would be metres away
    xy = [(0, 0.1), (6, 0.1 + 6 * math.tan(math.radians(1.5))), (14, 0.1 + 6 * math.tan(math.radians(1.5))),
          (14, 0), (20, 0), (20, 10), (0, 10)]
    out, _ = c337.flatten_steps(xy, 0.4)
    assert Polygon(out).length < Polygon(xy).length + 0.5


# --- pockets without an etalon ------------------------------------------------------------------------------------

def test_pockets_fill_shallow_and_keep_deep_niches():
    xy = [(0, 0), (5, 0), (5, 0.1), (7, 0.1), (7, 0), (12, 0), (12, 1.1), (13.3, 1.1), (13.3, 0), (20, 0),
          (20, 10), (0, 10)]
    rows, fills = pockets.census(xy, 0.4, 3.0)
    dec = sorted((r["decision"], round(r["depth_m"], 1)) for r in rows)
    assert dec == [("fill", 0.1), ("keep", 1.1)]
    assert len(fills) == 1 and Polygon(fills[0]).is_valid


# --- zones from wall types ----------------------------------------------------------------------------------------

def test_type_of_strips_the_instance_hash():
    assert zones.type_of("Базовая стена Вентфасад +100 100 _a3ca9a4") == "Базовая стена Вентфасад +100 100 "
    assert zones.type_of("Базовая стена X") == "Базовая стена X"


def test_runs_merge_short_panels_into_a_neighbour():
    cls = ["A"] * 30 + ["B"] * 3 + ["A"] * 30 + ["C"] * 10
    runs = zones.runs_of(cls, 0.1, 0.6)
    assert [r[2] for r in runs] == ["A", "C"]


def _crop_types(tmp):
    """20 x 10 block, walls 0.3 m thick at y in [-0.3, 0]: front x 0..8 type A, 8..20 type B, others type A."""
    def slab(x0, y0, x1, y1, z0=0.0, z1=6.0):
        out = []
        for (a, b) in (((x0, y0), (x1, y1)),):
            p = [a[0], a[1], z0]; q = [b[0], b[1], z0]; r = [b[0], b[1], z1]; s = [a[0], a[1], z1]
            out += [[p, q, r], [p, r, s]]
        return out
    objs = [("Базовая стена Тип A_1111111", slab(0, 0, 8, 0)), ("Базовая стена Тип B_2222222", slab(8, 0, 20, 0)),
            ("Базовая стена Тип A_3333333", slab(20, 0, 20, 10) + slab(20, 10, 0, 10) + slab(0, 10, 0, 0)),
            ("Базовая стена ОБЩИЙ - ВНУТРЕННИЙ_4444444", slab(1, 1, 19, 1))]
    tri, obj, names = [], [], []
    for i, (n, ts) in enumerate(objs):
        tri += ts; obj += [i] * len(ts); names.append(n)
    p = tmp / "crop_types.npz"
    np.savez(p, tri=np.array(tri, float), obj=np.array(obj), mat=np.zeros(len(obj), int), names=np.array(names),
             mats=np.array([""]))
    return p


def _floor(tmp, windows=()):
    spec = {"contour_section_z": 3.0, "rings": [{"xy": [[0, 0], [20, 0], [20, 10], [0, 10]], "cuts": [2.0, 4.0]}],
            "windows": [list(w) for w in windows], "materials": {"WALL_A": [1, 1, 1], "WINDOW": [0, 0, 1],
                                                                 "INSET": [0, 0, 0]}}
    p = tmp / "floor.json"
    p.write_text(json.dumps(spec), "utf-8")
    return p


def _zmap(tmp, skip=("ОБЩИЙ",), with_b=True):
    m = {"zones": {"Тип A": ["WALL_TA", [1, 0, 0]]}, "skip": list(skip)}
    if with_b:
        m["zones"]["Тип B"] = ["WALL_TB", [0, 1, 0]]
    p = tmp / "zmap.json"
    p.write_text(json.dumps(m, ensure_ascii=False), "utf-8")
    return p


def test_zones_follow_the_wall_type_with_a_vertical_at_the_joint(tmp_path):
    zones.main([str(_floor(tmp_path)), str(_crop_types(tmp_path)), str(_zmap(tmp_path)), str(tmp_path / "o.json")])
    o = json.loads((tmp_path / "o.json").read_text("utf-8"))
    z = o["rings"][0]["zones"]
    assert [q[2] for q in z] == ["WALL_TA", "WALL_TB", "WALL_TA"]
    assert z[0][1] == pytest.approx(8.0, abs=0.06) and z[1][1] == pytest.approx(20.0, abs=0.06)
    assert any(abs(c - 8.0) < 0.06 for c in o["rings"][0]["cuts"])
    assert "WALL_A" not in o["materials"] and {"WALL_TA", "WALL_TB"} <= set(o["materials"])


def test_zone_border_never_splits_an_opening(tmp_path):
    zones.main([str(_floor(tmp_path, windows=[(0, 7.5, 8.7, 0, 1, 0.2)])), str(_crop_types(tmp_path)),
                str(_zmap(tmp_path)), str(tmp_path / "o.json")])
    z = json.loads((tmp_path / "o.json").read_text("utf-8"))["rings"][0]["zones"]
    assert z[0][1] in (7.5, 8.7)


def test_unmapped_wall_type_is_an_error_naming_it(tmp_path):
    with pytest.raises(SystemExit, match="Тип B"):
        zones.main([str(_floor(tmp_path)), str(_crop_types(tmp_path)), str(_zmap(tmp_path, with_b=False)),
                    str(tmp_path / "o.json")])


# --- floor_from_dump on tower A: rounded corner wedge, ring start --------------------------------------------------

def _arc_crop(tmp, R=1.5, n_arc=40, gap=0.0):
    """15 x 10 block, wall 0.15 m: the (15, 0) corner rounded with radius R, cut into n_arc thin panels (a Revit
    curtain of short wall pieces, `gap` m between them); one window per floor on 3 floors on the left wall."""
    def quad(a, b, z0, z1):
        if gap:
            L = math.dist(a, b)
            u = ((b[0] - a[0]) / L * gap / 2, (b[1] - a[1]) / L * gap / 2)
            a, b = (a[0] + u[0], a[1] + u[1]), (b[0] - u[0], b[1] - u[1])
        p = [a[0], a[1], z0]; q = [b[0], b[1], z0]; r = [b[0], b[1], z1]; s = [a[0], a[1], z1]
        return [[p, q, r], [p, r, s]]
    t = 0.15
    out = []
    for off in (0.0, t):  # outer and inner face of each wall
        cx, cy, rr = 15 - R, R, R - off
        seq = [(0 + off, 0 + off), (cx, 0 + off)]
        seq += [(cx + rr * math.cos(-math.pi / 2 + math.pi / 2 * j / n_arc), cy + rr * math.sin(-math.pi / 2 + math.pi / 2 * j / n_arc))
                for j in range(1, n_arc)]
        seq += [(15 - off, cy), (15 - off, 10 - off), (0 + off, 10 - off), (0 + off, 0 + off)]
        for a, b in zip(seq, seq[1:]):
            out.append(("Базовая стена Наружная", quad(a, b, 0, 10)))
    for f, z in enumerate((1.0, 4.0, 7.0)):
        y0 = 4.0
        tri = quad((0.05, y0), (0.05, y0 + 1.2), z, z + 1.5) + quad((0.08, y0), (0.08, y0 + 1.2), z, z + 1.5)
        out.append(("Окно f%d" % f, tri))
    tri, obj, names = [], [], []
    for i, (n, ts) in enumerate(out):
        tri += ts; obj += [i] * len(ts); names.append(n + "_%07x" % i)
    p = tmp / "arc_crop.npz"
    np.savez(p, tri=np.array(tri, float), obj=np.array(obj), mat=np.zeros(len(obj), int), names=np.array(names),
             mats=np.array([""]))
    return p


def _inside_depth(xy, R=1.5):
    """Max depth of the contour inside the true outer envelope (rounded rectangle 15 x 10), at the rounded corner."""
    env = Polygon([(0, 0), (15, 0), (15, 10), (0, 10)]).difference(
        Polygon([(15 - R, 0), (15, 0), (15, R)]).difference(Point(15 - R, R).buffer(R, 256)))
    ring = LineString(list(xy) + [xy[0]])
    pts = [ring.interpolate(s) for s in np.arange(0, ring.length, 0.02)]
    near = [p for p in pts if p.x > 15 - R - 1.0 and p.y < R + 1.0]
    return max([env.exterior.distance(p) for p in near if env.contains(p)] + [0.0])


def test_rounded_corner_wedge_reproduces_without_pre_simplify(tmp_path):
    """Tower A 2026-11-17: the mitre erosion of the staircase left by flat-capped short panels dug a wedge into the
    building at the rounded corner (1.5 m on the real cut). Documents why --pre-simplify exists."""
    floor_mod.main([str(_arc_crop(tmp_path, n_arc=90, gap=0.01)), str(tmp_path / "f0.json")])
    xy = json.loads((tmp_path / "f0.json").read_text("utf-8"))["rings"][0]["xy"]
    assert _inside_depth(xy) > 1.0


def test_rounded_corner_contour_stays_on_the_envelope_with_pre_simplify(tmp_path):
    crop = _arc_crop(tmp_path, n_arc=90, gap=0.01)
    floor_mod.main([str(crop), str(tmp_path / "f.json"), "--pre-simplify", "0.03"])
    xy = json.loads((tmp_path / "f.json").read_text("utf-8"))["rings"][0]["xy"]
    assert _inside_depth(xy) < 0.05


def test_ring_starts_at_the_sharpest_corner(tmp_path):
    crop = _arc_crop(tmp_path, n_arc=90, gap=0.01)
    floor_mod.main([str(crop), str(tmp_path / "f.json"), "--pre-simplify", "0.03", "--start-corner"])
    xy = json.loads((tmp_path / "f.json").read_text("utf-8"))["rings"][0]["xy"]
    t = abs(floor_mod._turn(xy[-1], xy[0], xy[1]))
    assert t > 80
