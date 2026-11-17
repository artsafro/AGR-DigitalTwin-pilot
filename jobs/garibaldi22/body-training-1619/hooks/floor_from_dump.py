"""Hook `before` stage `body` (#1619 training polygon): typical-floor spec from a Revit crop (stdlib + numpy/shapely).

Pattern: n/a | new-case: typical-floor contour, jamb rings, sill/head loops and inset boxes read from a Revit crop.

uv run python floor_from_dump.py CROP.npz FLOOR.json [--keys keys.json] [--ref K] [--snap 0.03]
    [--clip CLIP.json] [--seal windows] [--fill FILL.json] [--openings]

--openings (stage 1 «бадик с проемами», Artem 2026-11-17): every window becomes an OPENING cut through the body
with its reveal (откос) depth read from Revit: the depth from the facade line to the outer face of the window
frame (`reveal_depth`); the window entry is [ring, s0, s1, 0, 1, depth]. Window fills and baskets are stage 2;
with --openings the baskets go to `deferred` (reason "stage 2"), not to `insets`. A window whose frame is not
behind the facade line (depth < 0.02 m) or whose depth is not finite is an error naming the object.

--fill takes envelope_check.py's repair list (recesses at or below the texture depth, D341) and closes those pockets
into the ring; a pocket that does not touch the contour or lies inside it is an error naming its index.

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


def reveal_depth(xy, ring_poly, share=0.15):
    """Reveal depth of one window: the shallowest 1 cm depth layer holding >= `share` of its vertices.

    The window family holds the frame (a dense layer behind the facade line: its outer face is the back of the
    откос) and the flashing (a few vertices out to the facade line, stage 2 inset). Depth = -(signed outward
    distance) rounded to 1 cm; a sparse layer (the flashing) is skipped. NaN when no point is given, a point is
    not finite or no layer is dense enough. Round 5 probe on G22 body 2: 1-sash 0.10, 2-sash 0.15, 3-sash 0.10 m
    (a P90 rule read 0.01 on a 1-sash window: the flashing share varies by family)."""
    pts = [(float(x), float(y)) for x, y in xy]
    if not pts or not all(math.isfinite(v) for p in pts for v in p):
        return float("nan")
    ext = ring_poly.exterior
    # depth is measured along the WINDOW's own plan normal (principal axis of its vertices) from the facade line at
    # its centre: a window set a few degrees off the simplified contour (G22 k2 [3529335], 3 deg) keeps its frame
    # in one layer instead of smearing it over 0.04..-0.19 m.
    arr = np.array(pts)
    c = arr.mean(0)
    s = ext.project(Point(*c))
    foot = ext.interpolate(s)
    p0, p1 = ext.interpolate(max(0.0, s - 0.05)), ext.interpolate(min(ext.length, s + 0.05))
    out_n = np.array([p1.y - p0.y, -(p1.x - p0.x)])  # outward normal of the CCW ring at the foot
    if len(arr) > 1 and np.ptp(arr, 0).max() > 1e-6:
        w, v = np.linalg.eigh(np.cov((arr - c).T))
        n = v[:, 0]  # minor axis = the window's plan normal
    else:
        n = out_n
    nn = np.linalg.norm(n)
    if not nn or not np.linalg.norm(out_n):
        return float("nan")
    n = n / nn * (1.0 if n @ out_n >= 0 else -1.0)
    sd = (arr - np.array([foot.x, foot.y])) @ n
    layers = collections.Counter(round(-float(v), 2) + 0.0 for v in sd)
    dense = [dep for dep, k in layers.items() if k >= share * len(sd)]
    return min(dense) if dense else float("nan")


def _turn(a, b, c):
    """Signed turn at b of the path a -> b -> c, degrees (CCW positive)."""
    t = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0])
    return math.degrees((t + math.pi) % (2 * math.pi) - math.pi)


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


def load_fill(path):
    """envelope_check.py --fill repair list -> source-frame polygons; anything malformed is an error naming it."""
    d = json.load(open(path, encoding="utf-8"))
    if not isinstance(d, dict) or d.get("frame") != "source":
        sys.exit("refused: --fill frame must be 'source' (got %r)" % (d.get("frame") if isinstance(d, dict) else d))
    polys = d.get("polygons") or []
    if not polys:
        sys.exit("refused: --fill has no polygons")
    out = []
    for i, p in enumerate(polys):
        try:
            arr = np.array(p, float)
            ok = arr.ndim == 2 and arr.shape[0] >= 3 and arr.shape[1] == 2 and np.isfinite(arr).all()
            poly = Polygon(arr) if ok else None
        except (ValueError, TypeError):
            poly = None
        if poly is None or not poly.is_valid or poly.area <= 0:
            sys.exit("refused: fill polygon %d is not a valid finite polygon" % i)
        out.append(poly)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("crop")
    ap.add_argument("out")
    ap.add_argument("--keys")
    ap.add_argument("--ref", type=int, default=None, help="index of the reference floor in the typical run")
    ap.add_argument("--snap", type=float, default=0.03, help="merge cuts closer than this (BM-09)")
    ap.add_argument("--edge-dist", type=float, default=0.8, help="max window distance to the contour")
    ap.add_argument("--close", type=float, default=0.5, help="closing radius bridging wall-object joints, m")
    ap.add_argument("--jog", type=float, default=0.06, help="contour simplify tolerance: jogs below it are relief, texture (BM-08/BM-09)")
    ap.add_argument("--pre-simplify", type=float, default=0.0,
                    help="simplify the dilated ring before erosion, m (rounded corners: 0.03; 0 = off, G22 rounds)")
    ap.add_argument("--start-corner", action="store_true",
                    help="start the ring at its sharpest corner, so no window spans the ring start (site 63)")
    ap.add_argument("--clip", help="JSON [[x,y],...]: keep only objects whose plan centroid is inside")
    ap.add_argument("--seal", nargs="*", default=[],
                    help="object classes whose cut joins the wall cut (round 3: windows - openings closed by their filling)")
    ap.add_argument("--fill", help="JSON from envelope_check.py --fill: texture pockets closed into the ring (D341)")
    ap.add_argument("--openings", action="store_true",
                    help="stage 1: windows are openings with the Revit reveal depth; baskets deferred to stage 2")
    a = ap.parse_args(argv)
    ins = [os.path.realpath(p) for p in (a.crop, a.fill, a.clip, a.keys) if p]
    if os.path.realpath(a.out) in ins or not a.out.endswith(".json"):
        sys.exit("refused: output must be a new .json, not an input")
    fills = load_fill(a.fill) if a.fill else []
    keys = json.load(open(a.keys, encoding="utf-8")) if a.keys else KEYS
    d = np.load(a.crop)
    tri, obj, names = d["tri"], d["obj"], [str(n) for n in d["names"]]
    clipped = 0
    if a.clip:  # keep objects whose plan centroid lies inside the polygon (a neighbour body inside the crop box)
        poly = Polygon(json.load(open(a.clip, encoding="utf-8")))
        if not poly.is_valid or poly.area <= 0:
            sys.exit("refused: --clip polygon is empty or invalid")
        cnt = np.bincount(obj, minlength=len(names)).astype(float)
        cx = np.bincount(obj, weights=tri[:, :, 0].mean(1), minlength=len(names)) / np.maximum(cnt, 1)
        cy = np.bincount(obj, weights=tri[:, :, 1].mean(1), minlength=len(names)) / np.maximum(cnt, 1)
        keep_obj = np.array([poly.contains(Point(x, y)) for x, y in zip(cx, cy)])
        clipped = int((~keep_obj & (cnt > 0)).sum())
        m = keep_obj[obj]
        tri, obj = tri[m], obj[m]
        if not len(tri):
            sys.exit("refused: --clip leaves no triangles")
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
    modal = max(n for _, n in sills)  # the busiest sill level; typical floors hold >= 80 % of it
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
    # BM-01 outer envelope: an opening is closed by its own filling. Off-typical openings (stair windows at the
    # landing levels, doors) gap the wall at the cut height and the ring would dive through them into the shaft
    # (round 2: six stair cores, up to 8 m inside). The cut therefore unions the walls with the `--seal` classes.
    seal = set(a.seal)
    unknown = seal - set(keys)
    if unknown:
        sys.exit("refused: --seal names unknown classes %s (known: %s)" % (sorted(unknown), sorted(keys)))
    wall_tris = np.array([t for o in by_obj if cls[o] == "walls" or cls[o] in seal for t in tri[by_obj[o]]])
    segs = section(wall_tris, zc)
    # morphological closing (+r, -r, mitre) bridges the joints between separate wall objects without moving
    # straight faces or convex corners; the outer ring of the largest piece is the facade line.
    r = a.close
    blob = unary_union([LineString(s).buffer(0.05, cap_style="flat") for s in segs]).buffer(r, join_style="mitre")
    polys = list(getattr(blob, "geoms", [blob]))
    outer = max(polys, key=lambda p: Polygon(p.exterior).area)
    outer_ring = Polygon(outer.exterior)
    if a.pre_simplify > 0:
        # site 63 tower A: a rounded corner cut from short flat-capped strips leaves a 1-5 cm staircase on the
        # dilated ring; the mitre erosion turns it into a wedge 1.5 m into the building. Smoothing the staircase
        # first keeps the eroded ring on the arc.
        outer_ring = outer_ring.simplify(a.pre_simplify)
    ring_poly = outer_ring.buffer(-r - 0.05, join_style="mitre").simplify(a.jog)
    if ring_poly.geom_type != "Polygon":
        ring_poly = max(ring_poly.geoms, key=lambda p: p.area)
    ring_poly = Polygon([c for c in ring_poly.exterior.coords])
    filled = []
    if fills:  # D341: recesses shallower than the texture depth are closed (the gate's repair list)
        ext0 = ring_poly.exterior
        for i, fp in enumerate(fills):
            if fp.distance(ext0) > 0.05:
                sys.exit("refused: fill polygon %d does not touch the contour (%.2f m away)" % (i, fp.distance(ext0)))
            if fp.difference(ring_poly).area < 0.5 * fp.area:
                sys.exit("refused: fill polygon %d lies inside the contour, not in a recess" % i)
            filled.append({"index": i, "area_m2": round(fp.difference(ring_poly).area, 3)})
        # union, then a 0.1 m closing only around the pockets: the ring's 5 cm mouth chamfers leave slivers that a
        # pocket polygon from another cut does not cover exactly; elsewhere the ring is untouched
        joined = unary_union([ring_poly] + fills)
        near = unary_union(fills).buffer(0.3)
        closed = unary_union([joined, joined.buffer(0.1, join_style="mitre").buffer(-0.1, join_style="mitre")
                              .intersection(near)]).buffer(0.005, join_style="mitre").buffer(-0.005, join_style="mitre")
        if closed.geom_type != "Polygon":
            sys.exit("refused: the filled contour is not one polygon")
        ring_poly = Polygon(closed.exterior.coords).simplify(a.jog)
    if not ring_poly.exterior.is_ccw:
        ring_poly = Polygon(list(ring_poly.exterior.coords)[::-1])
    if a.start_corner:  # a window must not span the ring start (it is dropped): start at the sharpest corner
        cs = list(ring_poly.exterior.coords)[:-1]
        k = max(range(len(cs)), key=lambda i: abs(_turn(cs[i - 1], cs[i], cs[(i + 1) % len(cs)])))
        ring_poly = Polygon(cs[k:] + cs[:k])
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
        if a.openings:
            depth = reveal_depth([tuple(p) for p in pts[:, :2]], ring_poly)
            if not math.isfinite(depth) or depth < 0.02:
                sys.exit("refused: window %s has no reveal (frame %.3f m behind the facade line)" % (names[o], depth))
            windows.append([0, round(s0, 3), round(s1, 3), 0, 1, depth])
        else:
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
    windows = [[w[0], round(snap(w[1]), 4), round(snap(w[2]), 4)] + w[3:] for w in windows]
    # baskets -> inset boxes in the frame of the nearest contour edge
    insets, deferred = [], []
    for o in by_obj:
        if cls[o] != "baskets":
            continue
        pts = tri[by_obj[o]].reshape(-1, 3)
        z0, z1 = float(pts[:, 2].min()), float(pts[:, 2].max())
        if not (ref - 1.0 < z0 < ref + step - 1.0):
            continue
        if a.openings:
            deferred.append({"object": names[o], "reason": "stage 2: AC box inset without back face (Artem 2026-11-17)"})
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
        "deferred": deferred,
        "stage": "body+openings" if a.openings else "body",
        "filled": filled,
        "counts": {"contour_vertices": len(xy), "cuts": len(merged), "windows_ref": len(ref_wins),
                   "windows_used": len(windows), "insets": len(insets), "perimeter_m": round(perim, 3),
                   "objects_clipped": clipped, "deferred": len(deferred),
                   "reveal_m": sorted({w[5] for w in windows if len(w) > 5})},
    }
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps(spec["counts"]), "step", step, "floors", len(best), "head", round(head, 3))


if __name__ == "__main__":
    main()
