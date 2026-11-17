"""Hook `before` stage `body` (#1619 training polygon): typical-floor spec from a Revit crop (stdlib + numpy/shapely).

Pattern: n/a | new-case: typical-floor contour, jamb rings, sill/head loops and inset boxes read from a Revit crop.

uv run python floor_from_dump.py CROP.npz FLOOR.json [--keys keys.json] [--ref K] [--snap 0.03]

CROP.npz is revit_floor_dump.py output. Object classes by name keys (defaults below, override with --keys):
walls -> outer contour (section at mid-spandrel, union, exterior ring, simplified 2 cm: BM-01); windows -> jamb
rings and the WINDOW faces (BM-03); baskets -> inset boxes (BM-04/BM-08). Typical floors = the longest run of
window-sill levels with one step and the same window count. Every window and basket of the reference floor ends
in the spec or in `dropped` with its reason. Refuses FLOOR.json equal to the input.
"""
import argparse
import collections
import json
import math
import os
import sys

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

KEYS = {"walls": ["Базовая стена"], "windows": ["Окно", "балконная дверь"], "baskets": ["Корзина для кондиционера"]}


def classify(names, keys):
    cls = []
    for n in names:
        c = next((k for k, ws in keys.items() if any(w in n for w in ws)), None)
        cls.append(c)
    return cls


def section(tris, z):
    """Segments where the plane z cuts each triangle (xy)."""
    segs = []
    for t in tris:
        d = t[:, 2] - z
        if d.min() > 0 or d.max() < 0:
            continue
        pts = []
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            da, db = a[2] - z, b[2] - z
            if (da < 0) != (db < 0) and da != db:
                u = da / (da - db)
                pts.append((a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1])))
        if len(pts) == 2 and math.dist(*pts) > 1e-4:
            segs.append(pts)
    return segs


def levels(vals, tol=0.05):
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [(float(np.median(g)), len(g)) for g in out]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("crop")
    ap.add_argument("out")
    ap.add_argument("--keys")
    ap.add_argument("--ref", type=int, default=None, help="index of the reference floor in the typical run")
    ap.add_argument("--snap", type=float, default=0.03, help="merge cuts closer than this (BM-09)")
    ap.add_argument("--edge-dist", type=float, default=0.8, help="max window distance to the contour")
    a = ap.parse_args(argv)
    if os.path.realpath(a.out) == os.path.realpath(a.crop) or not a.out.endswith(".json"):
        sys.exit("refused: output must be a new .json, not the input")
    keys = json.load(open(a.keys, encoding="utf-8")) if a.keys else KEYS
    d = np.load(a.crop)
    tri, obj, names = d["tri"], d["obj"], [str(n) for n in d["names"]]
    cls = classify(names, keys)
    by_obj = collections.defaultdict(list)
    for i, o in enumerate(obj):
        by_obj[int(o)].append(i)
    win_objs = [o for o in by_obj if cls[o] == "windows"]
    if not win_objs:
        sys.exit("no window objects: check --keys")
    wz = {o: (float(tri[by_obj[o]][:, :, 2].min()), float(tri[by_obj[o]][:, :, 2].max())) for o in win_objs}
    sills = levels([z[0] for z in wz.values()])
    # typical run: consecutive sill levels with a constant step and the modal window count
    modal = collections.Counter(n for _, n in sills).most_common(1)[0][0]
    cand = [s for s in sills if s[1] >= 0.8 * modal]
    best, run = [], []
    for s in cand:
        if run and abs((s[0] - run[-1][0]) - (run[-1][0] - run[-2][0] if len(run) > 1 else s[0] - run[-1][0])) < 0.05 \
                and 2.5 < s[0] - run[-1][0] < 4.5:
            run.append(s)
        else:
            run = [run[-1], s] if run and 2.5 < s[0] - run[-1][0] < 4.5 else [s]
        if len(run) > len(best):
            best = list(run)
    if len(best) < 3:
        sys.exit("no typical run of >= 3 floors found: %s" % sills)
    step = round((best[-1][0] - best[0][0]) / (len(best) - 1), 3)
    ref = best[a.ref if a.ref is not None else len(best) // 2][0]
    ref_wins = [o for o in win_objs if abs(wz[o][0] - ref) < 0.05]
    head = float(np.median([wz[o][1] - wz[o][0] for o in ref_wins]))
    # contour (BM-01): wall section at mid-spandrel of the reference floor
    zc = ref - 0.45
    wall_tris = np.array([t for o in by_obj if cls[o] == "walls" for t in tri[by_obj[o]]])
    segs = section(wall_tris, zc)
    blob = unary_union([LineString(s).buffer(0.05, cap_style="flat") for s in segs])
    polys = list(getattr(blob, "geoms", [blob]))
    outer = max(polys, key=lambda p: Polygon(p.exterior).area)
    ring_poly = Polygon(outer.exterior).buffer(-0.05, join_style="mitre").simplify(0.02)
    if ring_poly.geom_type != "Polygon":
        ring_poly = max(ring_poly.geoms, key=lambda p: p.area)
    ring_poly = Polygon([c for c in ring_poly.exterior.coords])
    if not ring_poly.exterior.is_ccw:
        ring_poly = Polygon(list(ring_poly.exterior.coords)[::-1])
    xy = [list(map(float, c)) for c in ring_poly.exterior.coords[:-1]]
    ext = ring_poly.exterior
    perim = ext.length
    # windows -> perimeter intervals (BM-03 jamb rings)
    windows, dropped, cuts = [], [], []
    for o in sorted(ref_wins):
        pts = tri[by_obj[o]].reshape(-1, 3)
        c = Point(pts[:, 0].mean(), pts[:, 1].mean())
        dist = ext.distance(c)
        if dist > a.edge_dist:
            dropped.append({"object": names[o], "reason": "window %.2f m off the outer contour (recessed)" % dist})
            continue
        s = [ext.project(Point(p[0], p[1])) for p in pts[:: max(1, len(pts) // 200)]]
        s0, s1 = min(s), max(s)
        if s1 - s0 > perim / 2:
            dropped.append({"object": names[o], "reason": "window spans the ring start; unsupported in round 1"})
            continue
        windows.append([0, round(s0, 3), round(s1, 3)])
        cuts += [s0, s1]
    cuts.sort()
    merged = []
    for s in cuts:
        if merged and s - merged[-1] < a.snap:
            continue
        merged.append(s)
    # snap window ends to the merged cuts
    def snap(v):
        return min(merged, key=lambda m: abs(m - v))
    windows = [[w[0], round(snap(w[1]), 4), round(snap(w[2]), 4)] for w in windows]
    # baskets -> inset boxes in the frame of the nearest contour edge
    insets = []
    for o in by_obj:
        if cls[o] != "baskets":
            continue
        pts = tri[by_obj[o]].reshape(-1, 3)
        z0, z1 = float(pts[:, 2].min()), float(pts[:, 2].max())
        if not (ref - 1.0 < z0 < ref + step - 1.0):
            continue
        c = Point(pts[:, 0].mean(), pts[:, 1].mean())
        sc = ext.project(c)
        p0, p1 = ext.interpolate(max(0, sc - 0.05)), ext.interpolate(min(perim, sc + 0.05))
        ang = math.degrees(math.atan2(p1.y - p0.y, p1.x - p0.x))
        tx, ty = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        nx, ny = ty, -tx  # outward for a CCW ring
        foot = ext.interpolate(sc)
        u = [(p[0] - foot.x) * tx + (p[1] - foot.y) * ty for p in pts]
        v = [(p[0] - foot.x) * nx + (p[1] - foot.y) * ny for p in pts]
        if max(v) < 0.05:
            dropped.append({"object": names[o], "reason": "basket not outside the contour (in a loggia)"})
            continue
        w = max(u) - min(u)
        cu = (max(u) + min(u)) / 2
        insets.append({"object": names[o], "box": [round(foot.x + tx * cu, 4), round(foot.y + ty * cu, 4),
                                                   round(z0 - ref, 4), round(w, 4), round(max(v), 4),
                                                   round(z1 - z0, 4), round(ang, 3)]})
    spec = {
        "units": "m", "source_crop": os.path.basename(a.crop), "step": step, "z0": round(best[0][0], 4),
        "floors": len(best), "sills": [round(s[0], 3) for s in best], "ref_sill": round(ref, 3),
        "loops": [0.0, round(head, 3)], "contour_section_z": round(zc, 3),
        "rings": [{"xy": [[round(x, 4), round(y, 4)] for x, y in xy], "cuts": [round(s, 4) for s in merged]}],
        "windows": windows, "insets": [{"box": i["box"]} for i in insets],
        "materials": {"WALL_A": [0.75, 0.73, 0.70], "WINDOW": [0.15, 0.2, 0.3], "INSET": [0.3, 0.3, 0.3]},
        "dropped": dropped,
        "counts": {"contour_vertices": len(xy), "cuts": len(merged), "windows_ref": len(ref_wins),
                   "windows_used": len(windows), "insets": len(insets), "perimeter_m": round(perim, 3)},
    }
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps(spec["counts"]), "step", step, "floors", len(best), "head", round(head, 3))


if __name__ == "__main__":
    main()
