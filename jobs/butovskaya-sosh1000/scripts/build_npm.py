"""NPM of the Butovskaya school (object `butovskaya-sosh1000`, #118): a low-poly massing with flush opening planes,
built from the step-0 Revit snapshot only (pattern `primitive-first`: the body is one stack of extruded plan
regions; openings are planes of the opening group on the facade faces).

Method. Every snapshot box of the BODY categories is a plan rectangle with a z range. The height range is cut into
layers at a set of thresholds; the plan region of a layer is the union of the rectangles whose z range covers at
least COVER_F of that layer. The body is the union of region x layer prisms, meshed directly: side walls on every
region ring, an up face where a layer ends and a down face where one starts. All plan coordinates are integers on
a SNAP_M grid, every ring is split at every vertex of every other ring lying on it, so faces meet edge to edge (no
T-junctions) and the mesh is closed. Opening planes: a window / door box at a side wall, inside one wall quad,
becomes a flush rectangle of the opening id cut into that quad.

    uv run python jobs/butovskaya-sosh1000/scripts/build_npm.py --out C:/x/butovskaya-npm/model_dump.json

The autoresearch loop (#118) edits only this file; the parameters below are the first build (setup).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import etalon_boxes, snapshot_levels  # noqa: E402  (same snapshot, same zone)

# --- parameters (the loop changes these and the code below) ---------------------------------------------------
SNAP_M = 0.05                       # plan grid
BODY = ["OST_Walls", "OST_CurtainWallPanels", "OST_CurtainWallMullions", "OST_Roofs", "OST_Floors",
        "OST_Windows", "OST_Doors"]
OPENINGS = {"OST_Windows": 11, "OST_Doors": 12}
THRESHOLDS = "levels+tops"  # "levels": level elevations + body bottom and top
COVER_F = 0.5                       # a box joins a layer's region when it covers this share of the layer's height
CLOSE_M = 0.0                       # closing radius of a region (fills slots), 0 = off
OPEN_M = 0.0                        # opening radius (drops slivers), 0 = off
MIN_PART_M2 = 0.0                   # region parts smaller than this are dropped
OPENING_DEPTH_M = 0.8               # an opening box this close to a wall line belongs to it
OPENING_MARGIN_M = 0.02             # an opening plane keeps this clear of its wall quad's edges
Z_Q = 0.1
K_EXTRA = 44
FACADE_ID, ROOF_ID, SOFFIT_ID = 1, 21, 1
# ---------------------------------------------------------------------------------------------------------------


def g(v):
    """metres -> grid units (int)."""
    return int(round(v / SNAP_M))


def thresholds(rows, levels):
    zs = [z for r in rows for z in (r["box"][0][2], r["box"][1][2])]
    lo, hi = min(zs), max(zs)
    if THRESHOLDS == "levels":
        t = [lo, hi] + [z for z in levels.values() if lo < z < hi]
    elif THRESHOLDS == "levels+tops":           # + the box tops / bottoms carrying the most plan area
        weight = {}
        for r in rows:
            (x0, y0, z0), (x1, y1, z1) = r["box"]
            for z in (z0, z1):
                zq = round(round(z / Z_Q) * Z_Q, 4)
                weight[zq] = weight.get(zq, 0.0) + (x1 - x0) * (y1 - y0)
        base = [lo, hi] + [z for z in levels.values() if lo < z < hi]
        extra = [z for z, _ in sorted(weight.items(), key=lambda kv: -kv[1])
                 if lo < z < hi and all(abs(z - b) > Z_Q / 2 for b in base)][:K_EXTRA]
        t = base + extra
    else:
        raise ValueError(THRESHOLDS)
    return sorted(set(round(z, 4) for z in t))


def clean(region):
    s = 1.0 / SNAP_M
    if CLOSE_M > 0:
        region = region.buffer(CLOSE_M * s, join_style="mitre").buffer(-CLOSE_M * s, join_style="mitre")
    if OPEN_M > 0:
        region = region.buffer(-OPEN_M * s, join_style="mitre").buffer(OPEN_M * s, join_style="mitre")
    region = shapely.set_precision(shapely.make_valid(region), 1.0)
    parts = [p for p in shapely.get_parts(region) if p.geom_type == "Polygon" and p.area * SNAP_M ** 2 > MIN_PART_M2]
    return shapely.union_all(parts) if parts else Polygon()


def polys(geom):
    """The polygonal part of a geometry (a difference can leave lines and points in a collection)."""
    parts = [p for p in shapely.get_parts(geom) if p.geom_type in ("Polygon", "MultiPolygon") and not p.is_empty]
    return shapely.union_all(parts) if parts else Polygon()


def unpinch(region):
    """A plan region whose outline touches itself at a point (two parts at a corner, a hole at the outline) gives a
    non-manifold vertex: a one-unit square fills every such point."""
    for _ in range(5):
        seen, pinch = {}, set()
        for ring in rings_of(region):
            for c in ring:
                if c in seen:
                    pinch.add(c)
                seen[c] = 1
        if not pinch:
            return region
        region = polys(shapely.set_precision(shapely.union_all([region] + [box(x - 1, y - 1, x + 1, y + 1) for x, y in pinch]), 1.0))
    return region


def uncontact(regions):
    """Where the region of a layer and the one above touch along a line or at a point from opposite sides (a down
    face meets an up face edge to edge), the upper region takes a one-unit strip of the lower one there: solids
    meeting along an edge are non-manifold."""
    for _ in range(6):
        changed = False
        for k in range(1, len(regions)):
            lo, hi = regions[k - 1], regions[k]
            a, b = polys(lo.difference(hi)), polys(hi.difference(lo))
            if a.is_empty or b.is_empty:
                continue
            touch = shapely.intersection(shapely.boundary(a), shapely.boundary(b))
            if touch is None or touch.is_empty:
                continue
            strip = touch.buffer(1, cap_style="square", join_style="mitre").intersection(lo)
            regions[k] = unpinch(polys(shapely.set_precision(shapely.union_all([hi, polys(strip)]), 1.0)))
            changed = True
        if not changed:
            break
    return regions


def layer_regions(rows, t):
    rects = [(box(g(r["box"][0][0]), g(r["box"][0][1]), g(r["box"][1][0]), g(r["box"][1][1])),
              r["box"][0][2], r["box"][1][2]) for r in rows]
    rects = [x for x in rects if x[0].area > 0]
    out = []
    for z0, z1 in zip(t, t[1:]):
        h = z1 - z0
        sel = [rc for rc, b, top in rects if min(top, z1) - max(b, z0) >= COVER_F * h - 1e-9]
        out.append(unpinch(clean(shapely.union_all(sel))) if sel else Polygon())
    return uncontact(out)


def rings_of(geom):
    out = []
    for p in shapely.get_parts(geom):
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        p = shapely.geometry.polygon.orient(p, 1.0)
        out.append([tuple(map(int, map(round, c))) for c in p.exterior.coords[:-1]])
        out += [[tuple(map(int, map(round, c))) for c in h.coords[:-1]] for h in p.interiors]
    return out


class Points:
    """Every vertex of every ring; split(ring) inserts those lying on its segments (integer exact)."""

    def __init__(self, pts):
        a = np.array(sorted(set(pts)), dtype=np.int64).reshape(-1, 2)
        self.a = a
        self.by_x, self.by_y = {}, {}
        for x, y in a:
            self.by_x.setdefault(int(x), []).append(int(y))
            self.by_y.setdefault(int(y), []).append(int(x))
        self.by_x = {k: np.array(sorted(v)) for k, v in self.by_x.items()}
        self.by_y = {k: np.array(sorted(v)) for k, v in self.by_y.items()}

    def on(self, p, q):
        (x0, y0), (x1, y1) = p, q
        if x0 == x1:
            ys = self.by_x.get(x0, np.zeros(0, int))
            lo, hi = min(y0, y1), max(y0, y1)
            m = ys[(ys > lo) & (ys < hi)]
            m = m if y1 > y0 else m[::-1]
            return [(x0, int(y)) for y in m]
        if y0 == y1:
            xs = self.by_y.get(y0, np.zeros(0, int))
            lo, hi = min(x0, x1), max(x0, x1)
            m = xs[(xs > lo) & (xs < hi)]
            m = m if x1 > x0 else m[::-1]
            return [(int(x), y0) for x in m]
        a, d = self.a, np.array([x1 - x0, y1 - y0])
        rel = a - np.array([x0, y0])
        cross = rel[:, 0] * d[1] - rel[:, 1] * d[0]
        s = rel @ d
        hit = (cross == 0) & (s > 0) & (s < d @ d)
        order = np.argsort(s[hit])
        return [tuple(map(int, c)) for c in a[hit][order]]

    def split(self, ring):
        out = []
        for i, p in enumerate(ring):
            q = ring[(i + 1) % len(ring)]
            out.append(p)
            out += self.on(p, q)
        return out


class Mesh:
    def __init__(self):
        self.v, self.index, self.t, self.mid = [], {}, [], []

    def vid(self, x, y, z):
        key = (x, y, round(z, 6))
        if key not in self.index:
            self.index[key] = len(self.v)
            self.v.append([x * SNAP_M, y * SNAP_M, z])
        return self.index[key]

    def tri(self, a, b, c, mid):
        if len({a, b, c}) == 3:
            self.t.append([a, b, c])
            self.mid.append(mid)


def triangulate(poly, pts):
    """CDT of a polygon whose rings are split at pts; returns triangles of int (x, y) corners, CCW."""
    rings = rings_of(poly)
    if not rings:
        return []
    ext = pts.split(rings[0])
    holes = [pts.split(h) for h in rings[1:]]
    tris = shapely.constrained_delaunay_triangles(Polygon(ext, holes))
    out = []
    for tr in shapely.get_parts(tris):
        c = [tuple(map(int, map(round, xy))) for xy in tr.exterior.coords[:3]]
        area2 = (c[1][0] - c[0][0]) * (c[2][1] - c[0][1]) - (c[1][1] - c[0][1]) * (c[2][0] - c[0][0])
        if area2 < 0:
            c = [c[0], c[2], c[1]]
        if area2 != 0:
            out.append(c)
    return out


def wall_openings(p, q, z0, z1, openings):
    """Opening rectangles (u0, u1, zb, zt) in metres along the wall p -> q, kept clear of the quad's edges."""
    P, Q = np.array(p, float) * SNAP_M, np.array(q, float) * SNAP_M
    L = float(np.linalg.norm(Q - P))
    if L <= 0:
        return []
    u = (Q - P) / L
    n = np.array([u[1], -u[0]])
    out = []
    for (lo, hi, mid) in openings:
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        if abs(float((np.array([cx, cy]) - P) @ n)) > OPENING_DEPTH_M:
            continue
        cs = [(np.array([x, y]) - P) @ u for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]
        a, b = max(min(cs), OPENING_MARGIN_M), min(max(cs), L - OPENING_MARGIN_M)
        zb, zt = max(lo[2], z0 + OPENING_MARGIN_M), min(hi[2], z1 - OPENING_MARGIN_M)
        if b - a > 0.1 and zt - zb > 0.1 and min(cs) >= 0 and max(cs) <= L:
            out.append((a, b, zb, zt, mid))
    keep = []
    for o in sorted(out, key=lambda o: -(o[1] - o[0]) * (o[3] - o[2])):   # no two planes overlap
        if all(o[1] <= k[0] or o[0] >= k[1] or o[3] <= k[2] or o[2] >= k[3] for k in keep):
            keep.append(o)
    return keep


def wall(mesh, p, q, z0, z1, openings, stats):
    a, b = mesh.vid(*p, z0), mesh.vid(*q, z0)
    c, d = mesh.vid(*q, z1), mesh.vid(*p, z1)
    ops = wall_openings(p, q, z0, z1, openings) if openings else []
    if not ops:
        mesh.tri(a, b, c, FACADE_ID)
        mesh.tri(a, c, d, FACADE_ID)
        return
    P, Q = np.array(p, float) * SNAP_M, np.array(q, float) * SNAP_M
    L = float(np.linalg.norm(Q - P))
    outer = Polygon([(0, z0), (L, z0), (L, z1), (0, z1)])
    holes = [box(o[0], o[2], o[1], o[3]) for o in ops]
    face = outer.difference(shapely.union_all(holes))
    to3 = lambda uu, zz: (P + (Q - P) * (uu / L), zz)  # noqa: E731

    def vid_uv(uu, zz):
        if abs(uu) < 1e-9:
            return mesh.vid(*p, zz) if abs(zz - z0) > 1e-9 and abs(zz - z1) > 1e-9 else (d if zz > z0 else a)
        if abs(uu - L) < 1e-9:
            return mesh.vid(*q, zz) if abs(zz - z0) > 1e-9 and abs(zz - z1) > 1e-9 else (c if zz > z0 else b)
        xy, zz = to3(uu, zz)
        key = ("w", round(float(xy[0]), 6), round(float(xy[1]), 6), round(zz, 6))
        if key not in mesh.index:
            mesh.index[key] = len(mesh.v)
            mesh.v.append([float(xy[0]), float(xy[1]), zz])
        return mesh.index[key]

    for tr in shapely.get_parts(shapely.constrained_delaunay_triangles(face)):
        cc = tr.exterior.coords[:3]
        ids = [vid_uv(*xy) for xy in cc]
        e1 = (cc[1][0] - cc[0][0], cc[1][1] - cc[0][1])
        e2 = (cc[2][0] - cc[0][0], cc[2][1] - cc[0][1])
        if e1[0] * e2[1] - e1[1] * e2[0] < 0:
            ids = [ids[0], ids[2], ids[1]]
        mesh.tri(*ids, FACADE_ID)
    for o in ops:
        i = [vid_uv(o[0], o[2]), vid_uv(o[1], o[2]), vid_uv(o[1], o[3]), vid_uv(o[0], o[3])]
        mesh.tri(i[0], i[1], i[2], o[4])
        mesh.tri(i[0], i[2], i[3], o[4])
        stats[o[4]] = stats.get(o[4], 0) + 1


def wall_chain(mesh, p, q, bot, top, z0, z1, openings, stats):
    """Side wall p -> q over [z0, z1] whose bottom edge is split at bot and top edge at top (int points between p
    and q, in order): the faces at z0 and z1 split it there and nowhere else. No openings: a zipper strip;
    openings: a CDT of the strip less the opening rectangles, plus the opening planes."""
    P, Q = np.array(p, float), np.array(q, float)
    L2 = float((Q - P) @ (Q - P))
    uu = lambda c: float((np.array(c, float) - P) @ (Q - P)) / L2   # noqa: E731  0..1 along the wall
    B = [(p, 0.0)] + [(c, uu(c)) for c in bot] + [(q, 1.0)]
    T = [(p, 0.0)] + [(c, uu(c)) for c in top] + [(q, 1.0)]
    ops = wall_openings(p, q, z0, z1, openings) if openings else []
    if not ops:
        bi, ti = [mesh.vid(*c, z0) for c, _ in B], [mesh.vid(*c, z1) for c, _ in T]
        i = j = 0
        while i < len(B) - 1 or j < len(T) - 1:      # advance the chain whose next point comes first
            if j == len(T) - 1 or (i < len(B) - 1 and B[i + 1][1] <= T[j + 1][1]):
                mesh.tri(bi[i], bi[i + 1], ti[j], FACADE_ID)
                i += 1
            else:
                mesh.tri(bi[i], ti[j + 1], ti[j], FACADE_ID)
                j += 1
        return
    L = float(np.sqrt(L2)) * SNAP_M
    ring = [(u * L, z0) for _, u in B] + [(u * L, z1) for _, u in reversed(T)]
    look = {(round(u * L, 9), z0): mesh.vid(*c, z0) for c, u in B}
    look.update({(round(u * L, 9), z1): mesh.vid(*c, z1) for c, u in T})
    face = Polygon(ring).difference(shapely.union_all([box(o[0], o[2], o[1], o[3]) for o in ops]))
    Pm, Qm = P * SNAP_M, Q * SNAP_M

    def vid_uv(u, z):
        k = (round(u, 9), z)
        if k in look:
            return look[k]
        xy = Pm + (Qm - Pm) * (u / L)
        key = ("w", round(float(xy[0]), 6), round(float(xy[1]), 6), round(z, 6))
        if key not in mesh.index:
            mesh.index[key] = len(mesh.v)
            mesh.v.append([float(xy[0]), float(xy[1]), z])
        return mesh.index[key]

    for tr in shapely.get_parts(shapely.constrained_delaunay_triangles(face)):
        cc = tr.exterior.coords[:3]
        ids = [vid_uv(*xy) for xy in cc]
        e1 = (cc[1][0] - cc[0][0], cc[1][1] - cc[0][1])
        e2 = (cc[2][0] - cc[0][0], cc[2][1] - cc[0][1])
        if e1[0] * e2[1] - e1[1] * e2[0] < 0:
            ids = [ids[0], ids[2], ids[1]]
        mesh.tri(*ids, FACADE_ID)
    for o in ops:
        i = [vid_uv(o[0], o[2]), vid_uv(o[1], o[2]), vid_uv(o[1], o[3]), vid_uv(o[0], o[3])]
        mesh.tri(i[0], i[1], i[2], o[4])
        mesh.tri(i[0], i[2], i[3], o[4])
        stats[o[4]] = stats.get(o[4], 0) + 1


def build(rows, levels):
    body = [r for r in rows if r["category"] in BODY]
    t = thresholds(body, levels)
    regions = layer_regions(body, t)
    openings = [(r["box"][0], r["box"][1], OPENINGS[r["category"]]) for r in rows if r["category"] in OPENINGS]
    empty = Polygon()
    horiz = []                                      # (z, polygon, up?)
    for k, z in enumerate(t):
        below = regions[k - 1] if k > 0 else empty
        above = regions[k] if k < len(regions) else empty
        up, down = polys(below.difference(above)), polys(above.difference(below))
        horiz += [(z, polys(shapely.set_precision(up, 1.0)), True), (z, polys(shapely.set_precision(down, 1.0)), False)]
    # the points of each threshold height: vertices of the regions below and above it and of its faces
    at = []
    for k in range(len(t)):
        near = [regions[j] for j in (k - 1, k) if 0 <= j < len(regions)]
        near += [poly for z, poly, _ in horiz[2 * k:2 * k + 2]]
        at.append(Points([c for gm in near for ring in rings_of(gm) for c in ring]))
    mesh, stats = Mesh(), {}
    for j, ((z0, z1), reg) in enumerate(zip(zip(t, t[1:]), regions)):
        for ring in rings_of(reg):
            for i, p in enumerate(ring):
                q = ring[(i + 1) % len(ring)]
                wall_chain(mesh, p, q, at[j].on(p, q), at[j + 1].on(p, q), z0, z1, openings, stats)
    for k, (z, poly, up) in enumerate(horiz):
        if poly.is_empty:
            continue
        for part in shapely.get_parts(poly):
            if part.geom_type != "Polygon" or part.area == 0:
                continue
            for c in triangulate(part, at[k // 2]):
                ids = [mesh.vid(x, y, z) for x, y in c]
                if not up:
                    ids = [ids[0], ids[2], ids[1]]
                mesh.tri(*ids, ROOF_ID if up else SOFFIT_ID)
    return mesh, {"thresholds": t, "layers": len(regions), "openings_placed": stats,
                  "openings_in_snapshot": len(openings)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="C:/x/butovskaya-npm/model_dump.json")
    a = ap.parse_args()
    rows, _ = etalon_boxes()
    levels = snapshot_levels()
    mesh, info = build(rows, levels)
    dump = {"meshes": [{"name": "SM_butovskaya_sosh1000_body", "vertices": mesh.v, "triangles": mesh.t,
                        "material_ids": mesh.mid, "polygon_sizes": [3] * len(mesh.t)}],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in levels.items()],
            "synthetic": False, "source": "C:/x/butovskaya-snapshot (Revit read-only boxes, #118 step 0)"}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dump), encoding="utf-8")
    print(json.dumps({**info, "thresholds": len(info["thresholds"]), "vertices": len(mesh.v),
                      "triangles": len(mesh.t)}))


if __name__ == "__main__":
    main()
