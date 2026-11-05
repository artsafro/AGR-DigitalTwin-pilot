"""elv-tc-vpm: facade light housings (parts/lighting_layout_v001.json) as Main geometry (runs inside Blender: mathutils).

Housings are ID 27 (attachments; the 6 Arktos stay ID 27 too), the glowing face(s) get one working ID per colour
group (GLOW_ID). Placement:
- lines (Range LINE): one continuous strip per drawn run along its outline (U / L / W, light_paths.py), section
  30 x 40 (h x depth), z band by level: parapet -> 3 cm under the cap underside (13.92 / 15.42 top of the high wall),
  belt +4.72 -> 4.715..4.745, canopy +3.08 -> 3.11..3.14; the strip is cut where anything stands proud of the wall
  (> 6 cm: ribs, Arktos, frames) with 2 cm clearance; pieces < 0.30 m dropped;
- points (TUBE M, DECO, FOCUS bars, PLAT-A4): one box at the fixture; if its footprint hits something proud the box
  is moved along the wall (<= 0.30 m), DECO also upward (<= 0.50 m, over the dock-shelter hoods); else skipped.
Every housing is open-backed and stands 8 mm in front of the outermost wall point under it (no contact, no coplanar
face); boxes are closed on the other five sides. Wall points come from a BVH raycast on the already built Main.
"""
import math
from mathutils import Vector
from light_paths import runs_and_points, POLYS

PART = "P42_Lights"
HOUSING = 27
GLOW_ID = {"LINE_PURPLE": 28, "LINE_2700K": 29, "LINE_2000K": 30, "LINE_4000K": 31, "DECO": 31, "FOCUS": 32,
           "PLAT_A4": 32, "TUBE_M": 33}
# (width along the wall, height, depth) m; glow faces: 'front' / 'top' / 'bottom'
POINT = {"TUBE_M": ((0.08, 0.20, 0.10), ("top", "bottom")), "DECO": ((0.22, 0.20, 0.14), ("front",)),
         "PLAT_A4": ((0.10, 0.10, 0.06), ("front",)), "FOCUS": ((None, 0.035, 0.06), ("front",))}
LINE_H, LINE_D = 0.03, 0.04
GAP, PROUD, CLEAR = 0.008, 0.06, 0.02          # GAP > xView face threshold 5 mm


class Prober:
    def __init__(self, bvh):
        self.bvh = bvh
        self.rays = 0

    def off(self, pk, u, z):
        """surface offset (m, + = proud of the outline) at (u, z), None when nothing within 1 m behind"""
        poly = POLYS[pk]
        b, n = poly.base(u), poly.unit_normal(u)
        self.rays += 1
        loc, nrm, fi, d = self.bvh.ray_cast(Vector((b[0] + n[0], b[1] + n[1], z)), Vector((-n[0], -n[1], 0)), 2.0)
        return None if loc is None else 1.0 - d

    def footprint(self, pk, u0, u1, z0, z1, step=0.02):
        """max offset over the rectangle, or None if any sample misses / is blocked (> PROUD)"""
        k = max(1, int(math.ceil((u1 - u0) / step)))
        mx = -9.0
        for i in range(k + 1):
            u = u0 + (u1 - u0) * i / k
            for z in (z0 + 0.003, 0.5 * (z0 + z1), z1 - 0.003):
                o = self.off(pk, u, z)
                if o is None or o > PROUD:
                    return None
                mx = max(mx, o)
        return mx


def _pt(poly, u, h, z):
    b, m = poly.base(u), poly.normal(u)
    return (b[0] + m[0] * h, b[1] + m[1] * h, z)


def strip(mb, pk, u0, u1, z0, z1, inner, depth, glow, glow_faces=("front",)):
    """open-backed box over the outline from u0 to u1 (breaks at outline vertices and <= 3.9 m)"""
    poly = POLYS[pk]
    us = [u0] + [c for c in poly.cum if u0 + 1e-6 < c < u1 - 1e-6] + [u1]
    fine = [us[0]]
    for a, b in zip(us, us[1:]):
        k = max(1, math.ceil((b - a) / 3.9))
        fine += [a + (b - a) * i / k for i in range(1, k + 1)]
    ho = inner + depth
    n_f = 0
    for a, b in zip(fine, fine[1:]):
        t = poly.tangent(0.5 * (a + b))
        nrm = poly.unit_normal(0.5 * (a + b))
        out = (nrm[0], nrm[1], 0.0)
        mb.face([_pt(poly, a, ho, z0), _pt(poly, b, ho, z0), _pt(poly, b, ho, z1), _pt(poly, a, ho, z1)],
                glow if "front" in glow_faces else HOUSING, PART, out)
        mb.face([_pt(poly, a, inner, z1), _pt(poly, b, inner, z1), _pt(poly, b, ho, z1), _pt(poly, a, ho, z1)],
                glow if "top" in glow_faces else HOUSING, PART, (0, 0, 1))
        mb.face([_pt(poly, a, inner, z0), _pt(poly, a, ho, z0), _pt(poly, b, ho, z0), _pt(poly, b, inner, z0)],
                glow if "bottom" in glow_faces else HOUSING, PART, (0, 0, -1))
        n_f += 3
    for u, sgn in ((u0, -1), (u1, 1)):
        t = poly.tangent(u)
        mb.face([_pt(poly, u, inner, z0), _pt(poly, u, ho, z0), _pt(poly, u, ho, z1), _pt(poly, u, inner, z1)],
                HOUSING, PART, (t[0] * sgn, t[1] * sgn, 0.0))
        n_f += 2 - 1
    return n_f


def line_band(r, cap_z):
    z = r["z"]
    if z > 13.5:
        top = (15.42 if z > 15.0 else (cap_z or 13.92)) - 0.03
        return top - LINE_H, top
    if 4.5 < z < 4.9:
        return 4.715, 4.745
    if 2.9 < z < 3.3:
        return 3.11, 3.14
    return z - LINE_H / 2, z + LINE_H / 2


def build(mb, layout, bvh, wl_trim):
    """wl_trim: {outline: (u_min, u_max)} limits (e.g. the void sliver of W at the pilot joint)."""
    pr = Prober(bvh)
    runs, pts = runs_and_points(layout)
    rep = {"runs": [], "points": [], "skipped": [], "moved": []}
    for r in runs:
        lo, hi = wl_trim.get(r["poly"], (0.0, POLYS[r["poly"]].length))
        u0, u1 = max(r["u0"], lo), min(r["u1"], hi)
        z0, z1 = line_band(r, None)
        # free intervals along u (2 cm samples), sampled CLEAR beyond both ends so a proud face next to an end
        # (rib / frame end face) also trims the strip by CLEAR
        e0, e1 = u0 - CLEAR, u1 + CLEAR
        k = max(1, int(math.ceil((e1 - e0) / 0.02)))
        us = [e0 + (e1 - e0) * i / k for i in range(k + 1)]
        offs = []
        for u in us:
            o = [pr.off(r["poly"], u, z) for z in (z0 + 0.003, 0.5 * (z0 + z1), z1 - 0.003)]
            offs.append(None if any(x is None or x > PROUD for x in o) else max(o))
        pieces, cur = [], None
        for u, o in zip(us, offs):
            if o is not None:
                cur = [u, u, o] if cur is None else [cur[0], u, max(cur[2], o)]
            elif cur is not None:
                pieces.append(cur)
                cur = None
        if cur is not None:
            pieces.append(cur)
        made, dropped = [], []
        for i, (a, b, o) in enumerate(pieces):
            a2 = max(u0, a + (CLEAR if a > e0 + 1e-6 else 0.0))
            b2 = min(u1, b - (CLEAR if b < e1 - 1e-6 else 0.0))
            if b2 - a2 < 0.30:
                dropped.append([round(a, 2), round(b, 2)])
                continue
            strip(mb, r["poly"], a2, b2, z0, z1, o + GAP, LINE_D, GLOW_ID[r["type"]])
            made.append([round(a2, 3), round(b2, 3), round(o + GAP, 3)])
        rep["runs"].append({"id": r["id"], "type": r["type"], "outline": r["poly"], "u": [round(u0, 3), round(u1, 3)],
                            "z": [round(z0, 3), round(z1, 3)], "pieces": made, "dropped": dropped,
                            "length_m": round(sum(p[1] - p[0] for p in made), 2), "split": r["split"],
                            "glow_id": GLOW_ID[r["type"]]})
    for p in pts:
        (w, h, d), glow_faces = POINT[p["type"]]
        if w is None:
            w = p["len"]
        cand = [(0.0, 0.0)]
        for s in range(1, 16):
            cand += [(s * 0.02, 0.0), (-s * 0.02, 0.0)]
        if p["type"] == "DECO":
            cand += [(du, s * 0.02) for s in range(1, 26) for du in (0.0,)]
        placed = None
        for du, dz in cand:
            u, zc = p["u"] + du, p["z"] + dz
            o = pr.footprint(p["poly"], u - w / 2 - CLEAR, u + w / 2 + CLEAR, zc - h / 2 - CLEAR,
                               zc + h / 2 + CLEAR, step=0.01)
            if o is not None:
                placed = (u, zc, o, du, dz)
                break
        if placed is None:
            rep["skipped"].append({"id": p["id"], "type": p["type"], "reason": "no free wall within 0.30 m"})
            continue
        u, zc, o, du, dz = placed
        strip(mb, p["poly"], u - w / 2, u + w / 2, zc - h / 2, zc + h / 2, o + GAP, d, GLOW_ID[p["type"]], glow_faces)
        if du or dz:
            rep["moved"].append({"id": p["id"], "du": round(du, 2), "dz": round(dz, 2)})
        rep["points"].append({"id": p["id"], "type": p["type"], "outline": p["poly"], "u": round(u, 3),
                              "z": round(zc, 3), "inner": round(o + GAP, 3), "glow_id": GLOW_ID[p["type"]]})
    rep["rays"] = pr.rays
    return rep
