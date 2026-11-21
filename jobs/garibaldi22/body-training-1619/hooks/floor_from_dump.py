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

Stage 2 (#1619 polygon stage 2, subcommand `stage2`): window fills, capsules and AC baskets read from the Revit
crop for an ACCEPTED stage-1 body (spec for `module_build.py -- stage2`).

Pattern: n/a | new-case: stage-2 inset spec (frame + glass + flashing + capsule per opening, AC box) for an accepted
stage-1 body.

uv run python floor_from_dump.py stage2 CROP.npz FLOOR.json STAGE2.json [--clip CLIP.json] [--embed 0.05]

FLOOR.json is the stage-1 spec the accepted body was built from (floor_from_dump.py --openings + zones); the body
itself is never rebuilt here. For every opening [ring, s0, s1, wl, wh, r] of FLOOR.json the Revit window of the
reference floor whose centre projects into it is read in its own frame (u along the opening, d = depth behind the
facade line, z from its sill):
- glass panes = the thin (<= 4 cm) 12-triangle boxes of the family; pane edges closer than --snap are snapped to
  their mean (one bar line instead of a 3 cm sliver row, BM-09) and the largest shift is reported;
- frame depth = the back of the frame part (largest component) minus the opening's reveal r; bars (frame, mullions,
  transoms) = the opening minus the panes (mullions/transoms are geometry because they are geometry in Revit);
- flashing (отлив) = the frame part's horizontal top face in front of the frame (height, front depth);
- `entry` = the windowgen_core record (module_build.window_entry: Revit panes_m + frame_profile_m) that
  module_build stage2 passes to windowgen_core.build_type.
AC baskets (Artem 2026-11-17: «бокс врезается в стену без заднего полигона»): Revit box size and outward depth; the
back side goes --embed m behind the facade line (no back face, no niche: the wall stays whole). A basket whose top
reaches the sill of an opening above is lowered 1 cm so its in-wall strip never lies in the sill reveal plane.
Capsules (D205, capsule_core.planar_capsule via module_build.capsule_module): each footprint is checked against the
contour and the other capsules.
Refuses an output equal to an input, an opening without exactly one window, a window without panes.
"""
import argparse
import collections
import json
import math
import os
import re
import sys

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from module_build import capsule_module, load_core, window_entry  # noqa: E402  (stage-2 core adapters, pure)

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
    ap.add_argument("--section-z", type=float, default=None,
                    help="cut the contour at this z instead of mid-spandrel of the reference floor (a belt layer)")
    ap.add_argument("--sill-band", type=float, nargs=2, default=None, metavar=("LO", "HI"),
                    help="use the windows whose sill lies in [LO, HI] instead of the reference floor (a belt storey)")
    ap.add_argument("--deslit", type=float, default=0.0,
                    help="closing radius (m) that removes zero-width slits from the dilated ring; 0 = off")
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
    if a.sill_band:  # site 63 tower B belt storey: two sill levels outside the typical run
        ref_wins = [o for o in win_objs if a.sill_band[0] <= wz[o][0] <= a.sill_band[1]]
        if not ref_wins:
            sys.exit("refused: no window sill in --sill-band %s" % a.sill_band)
    head = float(np.median([wz[o][1] - wz[o][0] for o in ref_wins]))
    # contour (BM-01): wall section at mid-spandrel of the reference floor
    zc = ref - 0.45 if a.section_z is None else a.section_z
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
    if a.deslit > 0:
        # site 63 tower B: a vent-facade cassette gap leaves a zero-width slit in the dilated ring; simplify turns
        # it into a self-touching spike and the mitre erosion cuts a 2.3 m notch behind a window. A tiny closing
        # removes the slit and leaves faces and corners in place.
        outer_ring = outer_ring.buffer(a.deslit, join_style="round").buffer(-a.deslit, join_style="round")
        if outer_ring.geom_type != "Polygon":
            outer_ring = max(outer_ring.geoms, key=lambda p: p.area)
        outer_ring = Polygon(outer_ring.exterior)
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


# ---- stage 2 (#1619): inset spec for module_build.py -- stage2 --------------------------------------------
CAPSULE = {"depth": 1.0, "outline": 0.1}  # D205


def components(tris, nd=5):
    """Connected parts of a triangle soup (shared rounded vertices). Returns a list of index arrays."""
    key = np.round(np.asarray(tris, dtype=float).reshape(-1, 3), nd)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 3)
    par = list(range(int(inv.max()) + 1))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for a, b, c in inv:
        for x, y in ((a, b), (b, c)):
            rx, ry = find(int(x)), find(int(y))
            if rx != ry:
                par[rx] = ry
    comp = collections.defaultdict(list)
    for i, (a, _, _) in enumerate(inv):
        comp[find(int(a))].append(i)
    return [np.array(v) for v in comp.values()]


def snap_edges(vals, tol):
    """Cluster sorted values closer than tol (chained) and replace each by its cluster mean.

    Returns (mapping {value: snapped}, max shift)."""
    vs = sorted(set(float(v) for v in vals))
    groups, cur = [], []
    for v in vs:
        if cur and v - cur[-1] > tol:
            groups.append(cur)
            cur = []
        cur.append(v)
    if cur:
        groups.append(cur)
    out, shift = {}, 0.0
    for g in groups:
        m = sum(g) / len(g)
        for v in g:
            out[v] = m
            shift = max(shift, abs(v - m))
    return out, shift


def window_parts(L, r, snap=0.04):
    """Read one Revit window given in local coords L (n, 3, 3): u along the opening, d depth behind the facade line
    (positive into the body), z from the opening sill. Returns a dict with panes [[u0, u1, z0, z1, d_glass]] in the
    frame of the window bbox (u from its left edge), frame depth fd (frame back - r), flashing (or None), width,
    height and the snap shift. Refuses a window without panes or with a frame back not behind r."""
    L = np.asarray(L, dtype=float)
    if L.ndim != 3 or L.shape[1:] != (3, 3) or not np.isfinite(L).all():
        raise ValueError("window triangles must be a finite (n, 3, 3) array")
    P = L.reshape(-1, 3)
    u_lo, u_hi = float(P[:, 0].min()), float(P[:, 0].max())
    z_lo, z_hi = float(P[:, 2].min()), float(P[:, 2].max())
    comps = components(L)
    frame = max(comps, key=len)
    panes = []
    for idx in comps:
        Q = L[idx].reshape(-1, 3)
        lo, hi = Q.min(0), Q.max(0)
        if len(idx) == 12 and hi[1] - lo[1] <= 0.04 and hi[0] - lo[0] > 0.15 and hi[2] - lo[2] > 0.15:
            panes.append([lo[0] - u_lo, hi[0] - u_lo, lo[2] - z_lo, hi[2] - z_lo, (lo[1] + hi[1]) / 2])
    if not panes:
        raise ValueError("window has no glass panes (12-triangle boxes <= 4 cm thick)")
    F = L[frame]
    fd = float(F[:, :, 1].max()) - r
    if not (0.02 <= fd < 0.5):
        raise ValueError("frame back %.3f m is not 2..500 mm behind the reveal %.3f m" % (F[:, :, 1].max(), r))
    umap, us = snap_edges([p[0] for p in panes] + [p[1] for p in panes], snap)
    zmap, zs = snap_edges([p[2] for p in panes] + [p[3] for p in panes], snap)
    panes = [[umap[p[0]], umap[p[1]], zmap[p[2]], zmap[p[3]], p[4]] for p in panes]
    panes.sort(key=lambda p: (p[2], p[0]))
    # flashing: horizontal up-facing triangles of the frame part in front of the frame, low on the window
    n = np.cross(F[:, 1] - F[:, 0], F[:, 2] - F[:, 0])
    nn = np.linalg.norm(n, axis=1)
    up = (n[:, 2] > 0.98 * nn) & (F[:, :, 1].min(1) < r - 0.02) & (F[:, :, 2].max(1) - z_lo < 0.2)
    flashing = None
    if up.any():
        top = float(F[up][:, :, 2].mean() - z_lo)
        low = F[F[:, :, 2].max(1) - z_lo <= top + 1e-4]
        flashing = {"top": round(top, 4), "front": round(float(low[:, :, 1].min()), 4)}
    for p in panes:
        if not (r <= p[4] <= r + fd):
            raise ValueError("glass depth %.3f outside the frame %.3f..%.3f" % (p[4], r, r + fd))
    return {"width": u_hi - u_lo, "height": z_hi - z_lo, "fd": round(fd, 4), "flashing": flashing,
            "panes": [[round(v, 4) for v in p] for p in panes], "snap_shift": round(max(us, zs), 4)}


def run_points(ring, s0, s1):
    """Plan points of the ring run s0..s1 (contour corners included)."""
    return [tuple(c) for c in substring(ring.exterior, s0, s1).coords]


def straight(pts, tol_deg=1.0):
    """True when the run turns less than tol_deg at every inner point."""
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        t1 = math.atan2(b[1] - a[1], b[0] - a[0])
        t2 = math.atan2(c[1] - b[1], c[0] - b[0])
        if abs(math.degrees((t2 - t1 + math.pi) % (2 * math.pi) - math.pi)) > tol_deg:
            return False
    return True


def capsule_plan(a, t, w, h, r, fd, cap=CAPSULE, cc=None):
    """Plan footprint of the D205 capsule that module_build stage2 makes: capsule_core.planar_capsule (via
    module_build.capsule_module) in local (u, d, z), its u/d extent mapped to world plan coordinates."""
    cc = cc or load_core("capsule_core")
    m, _ = capsule_module({"w": w, "h": h, "r": r, "fd": fd}, cap, cc)
    us, ds = [p[0] for p in m.verts], [p[1] for p in m.verts]
    n = (-t[1], t[0])  # left normal of a CCW ring = into the body
    return [(a[0] + t[0] * u + n[0] * d, a[1] + t[1] * u + n[1] * d)
            for u, d in ((min(us), min(ds)), (max(us), min(ds)), (max(us), max(ds)), (min(us), max(ds)))]


def stage2_main(argv=None):
    """`stage2` subcommand: the stage-2 inset spec (see the module docstring)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("crop")
    ap.add_argument("floor")
    ap.add_argument("out")
    ap.add_argument("--clip")
    ap.add_argument("--embed", type=float, default=0.05, help="AC box back side behind the facade line, m")
    ap.add_argument("--snap", type=float, default=0.04, help="merge pane edges closer than this, m")
    a = ap.parse_args(argv)
    ins = {os.path.realpath(p) for p in (a.crop, a.floor, a.clip) if p}
    if os.path.realpath(a.out) in ins or not a.out.endswith(".json"):
        sys.exit("refused: output must be a new .json, not an input")
    if not (0.0 < a.embed < 0.3):
        sys.exit("refused: --embed must be in (0, 0.3) m")
    fl = json.load(open(a.floor, encoding="utf-8"))
    ring = Polygon(fl["rings"][0]["xy"])
    ext = ring.exterior
    ref, step, head = float(fl["ref_sill"]), float(fl["step"]), float(fl["loops"][1])
    d = np.load(a.crop)
    tri, obj, names = d["tri"], d["obj"], [str(n) for n in d["names"]]
    keep = np.ones(len(names), bool)
    if a.clip:
        poly = Polygon(json.load(open(a.clip, encoding="utf-8")))
        cnt = np.bincount(obj, minlength=len(names)).astype(float)
        cx = np.bincount(obj, weights=tri[:, :, 0].mean(1), minlength=len(names)) / np.maximum(cnt, 1)
        cy = np.bincount(obj, weights=tri[:, :, 1].mean(1), minlength=len(names)) / np.maximum(cnt, 1)
        keep = np.array([poly.contains(Point(x, y)) for x, y in zip(cx, cy)])
    cls = classify(names, KEYS)
    by = collections.defaultdict(list)
    for i, o in enumerate(obj):
        if keep[o] and cls[o] in ("windows", "baskets"):
            by[int(o)].append(i)
    openings = [w for w in fl["windows"] if len(w) > 5 and w[5] > 0]
    wins = {}
    for o, idx in by.items():
        if cls[o] != "windows":
            continue
        P = tri[idx].reshape(-1, 3)
        if abs(P[:, 2].min() - ref) > 0.05:
            continue
        sc = ext.project(Point(P[:, 0].mean(), P[:, 1].mean()))
        hit = [k for k, w in enumerate(openings) if w[1] - 0.05 <= sc <= w[2] + 0.05]
        if len(hit) == 1:
            wins.setdefault(hit[0], []).append(o)
    out_w, problems, caps = [], [], []
    cc = load_core("capsule_core")
    for k, w in enumerate(openings):
        if len(wins.get(k, [])) != 1:
            sys.exit("refused: opening %d (s %.2f..%.2f) matches %d Revit windows" % (k, w[1], w[2], len(wins.get(k, []))))
        o = wins[k][0]
        s0, s1, r = float(w[1]), float(w[2]), float(w[5])
        pts = run_points(ring, s0, s1)
        if not straight(pts):
            sys.exit("refused: opening %d runs over a contour corner (unsupported in stage 2)" % k)
        A, B = np.array(pts[0]), np.array(pts[-1])
        W = float(np.linalg.norm(B - A))
        t = (B - A) / W
        nin = np.array([-t[1], t[0]])
        P = tri[by[o]]
        # read the family in its OWN plan frame (PCA, as reveal_depth): a window 3 deg off the contour keeps its
        # frame back and glass in one depth layer; depth from the facade line at its centre
        Q = P.reshape(-1, 3)[:, :2]
        cq = Q.mean(0)
        foot = ext.interpolate(ext.project(Point(*cq)))
        ev, vec = np.linalg.eigh(np.cov((Q - cq).T))
        tw = vec[:, 1] * (1.0 if vec[:, 1] @ t >= 0 else -1.0)
        nw = np.array([-tw[1], tw[0]])
        rel = P[:, :, :2] - [foot.x, foot.y]
        loc = np.stack([rel @ tw, rel @ nw, P[:, :, 2] - ref], 2)
        try:
            part = window_parts(loc, r, a.snap)
        except ValueError as e:
            sys.exit("refused: window %s: %s" % (names[o], e))
        su, sz = W / part["width"], head / part["height"]
        if abs(su - 1) > 0.03 or abs(sz - 1) > 0.03:
            problems.append("window %s: Revit %.3f x %.3f vs opening %.3f x %.3f" % (names[o], part["width"], part["height"], W, head))
        panes = [[p[0] * su, p[1] * su, p[2] * sz, p[3] * sz, p[4]] for p in part["panes"]]
        typ = re.sub(r"\s*\[\d+\].*$|_[0-9a-f]{6,7}$", "", names[o])
        cp = capsule_plan(A, t, W, head, r, part["fd"], cc=cc)
        cap_poly = Polygon(cp)
        inside = ring.buffer(1e-6).contains(cap_poly)
        caps.append(cap_poly)
        panes = [[round(v, 4) for v in p] for p in panes]
        out_w.append({"opening": k, "object": names[o], "type": typ, "a": [round(float(v), 4) for v in A],
                      "t": [round(float(v), 6) for v in t], "w": round(W, 4), "h": head, "r": r, "fd": part["fd"],
                      "panes": panes, "flashing": part["flashing"],
                      "entry": window_entry(typ, W, head, part["fd"], panes),
                      "snap_shift": part["snap_shift"], "capsule_inside_contour": bool(inside)})
    overlaps = sum(1 for i in range(len(caps)) for j in range(i + 1, len(caps)) if caps[i].intersection(caps[j]).area > 1e-6)
    baskets = []
    for o, idx in by.items():
        if cls[o] != "baskets":
            continue
        P = tri[idx].reshape(-1, 3)
        z0, z1 = float(P[:, 2].min()), float(P[:, 2].max())
        if not (ref - 1.0 < z0 < ref + step - 1.0):
            continue
        sc = ext.project(Point(P[:, 0].mean(), P[:, 1].mean()))
        p0, p1 = ext.interpolate(max(0, sc - 0.05)), ext.interpolate(min(ext.length, sc + 0.05))
        t = np.array([p1.x - p0.x, p1.y - p0.y])
        t /= np.linalg.norm(t)
        nout = np.array([t[1], -t[0]])
        foot = ext.interpolate(sc)
        rel = P[:, :2] - [foot.x, foot.y]
        u, v = rel @ t, rel @ nout
        if v.max() < 0.05:
            problems.append("basket %s is not outside the contour" % names[o])
            continue
        su0, su1 = sc + u.min(), sc + u.max()
        if not straight(run_points(ring, max(0, su0), min(ext.length, su1))):
            sys.exit("refused: basket %s spans a contour corner" % names[o])
        top = z1 - ref
        lowered = False
        if top > step - 0.005 and any(w[1] < su1 and w[2] > su0 for w in openings):
            top, lowered = step - 0.01, True
        c = np.array([foot.x, foot.y]) + t * (u.min() + u.max()) / 2
        baskets.append({"object": names[o], "c": [round(float(x), 4) for x in c], "t": [round(float(x), 6) for x in t],
                        "w": round(float(np.ptp(u)), 4), "out": round(float(v.max()), 4), "revit_back": round(float(v.min()), 4),
                        "embed": a.embed, "z0": round(z0 - ref, 4), "z1": round(top, 4), "top_lowered": lowered})
    baskets.sort(key=lambda b: (b["c"][0], b["c"][1]))
    spec = {"units": "m", "stage": "stage2", "source_crop": os.path.basename(a.crop), "floor": os.path.basename(a.floor),
            "z0": fl["z0"], "step": step, "floors": fl["floors"], "ring": fl["rings"][0]["xy"], "capsule": CAPSULE,
            "windows": out_w, "baskets": baskets, "problems": problems,
            "counts": {"openings": len(openings), "windows": len(out_w), "baskets": len(baskets),
                       "types": dict(collections.Counter(w["type"] for w in out_w)),
                       "panes": sum(len(w["panes"]) for w in out_w), "flashings": sum(1 for w in out_w if w["flashing"]),
                       "max_snap_shift_m": max((w["snap_shift"] for w in out_w), default=0.0),
                       "capsules_outside_contour": sum(1 for w in out_w if not w["capsule_inside_contour"]),
                       "capsule_overlaps": overlaps, "baskets_top_lowered": sum(1 for b in baskets if b["top_lowered"])}}
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps(spec["counts"], ensure_ascii=False))
    if problems:
        print("PROBLEMS", json.dumps(problems, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1:2] == ["stage2"]:
        stage2_main(sys.argv[2:])
    else:
        main()
