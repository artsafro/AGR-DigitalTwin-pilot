"""elv-tc-vpm build-v007: interior capsules («фальшпомещения», user 2026-11-05) and horizontal joint cover strips
(«накладки», booklet item 14, Revit Batten_FS-8P 165 x 22 mm). Used by build_full_v007.py after the lights.

Capsule = a box behind a glazed opening with the opening side removed (open rim), normals inward so that it is seen
from outside through the glass. Rim rule (user): the open-edge contour lies inside the opening at the depth of the
MIDDLE OF THE FRAME, i.e. half-way between the frame face in front of the glass and the glass plane:
  windows W72 frame plate 0.110 / glass 0.125 -> 0.1175; doors 0.200 / 0.215 -> 0.2075; F50 curtain walls: base plane
  0 / glass 0.015 -> 0.0075 behind the base plane (the F50 caps stand 0.02 in front of it).
Every case: rim = glass plane + RIM (7.5 mm) towards the outside, so any ray that passes the glass is already inside
the capsule (no open edge or void visible at a grazing view). The rim rectangle = glass extents + MARGIN (25 mm, the
middle of the 50 mm F50 rail / inside the frame plate), so the rim edges sit behind opaque frame.
Depth D 0.80 m (customer reference; 0.92 m on the slanted NW wall); less where other geometry is in the way (each
candidate is tested against the model and the capsules already placed: triangle overlap and 5 mm proximity).
Pure helpers + mathutils BVH; no bpy.
"""
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pilot_geom import Poly
from full_geom import lin

RIM, MARGIN, NEAR = 0.0075, 0.025, 0.005


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    L = math.sqrt(sum(c * c for c in n)) or 1.0
    return [c / L for c in n]


# ------------------------------------------------------------------ glass clusters (one per glazed opening plane)
def glass_clusters(mb, part_ids_skip=()):
    faces = []
    for idx, mat, part, kind in mb.faces:
        if part in part_ids_skip:
            continue
        pts = [mb.verts[i] for i in idx]
        n = newell(pts)
        if abs(n[2]) > 0.3:
            continue
        hn = math.hypot(n[0], n[1])
        n = (n[0] / hn, n[1] / hn)
        faces.append({"pts": pts, "n": n, "part": part})
    groups = {}
    for f in faces:
        groups.setdefault((round(f["n"][0], 2), round(f["n"][1], 2)), []).append(f)
    out = []
    for key, fs in groups.items():
        n = (key[0], key[1])
        L = math.hypot(*n)
        n = (n[0] / L, n[1] / L)
        r = (-n[1], n[0])
        for f in fs:
            us = [p[0] * r[0] + p[1] * r[1] for p in f["pts"]]
            zs = [p[2] for p in f["pts"]]
            f["d"] = sum(p[0] * n[0] + p[1] * n[1] for p in f["pts"]) / len(f["pts"])
            f["box"] = (min(us), max(us), min(zs), max(zs))
        par = list(range(len(fs)))

        def find(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                a, b = fs[i], fs[j]
                if abs(a["d"] - b["d"]) > 0.03:
                    continue
                if a["box"][0] > b["box"][1] + 0.35 or b["box"][0] > a["box"][1] + 0.35:
                    continue
                if a["box"][2] > b["box"][3] + 0.35 or b["box"][2] > a["box"][3] + 0.35:
                    continue
                par[find(i)] = find(j)
        comp = {}
        for i in range(len(fs)):
            comp.setdefault(find(i), []).append(fs[i])
        for cs in comp.values():
            area = 0.0
            for c in cs:
                p = c["pts"]
                area += 0.5 * abs(sum((p[k][0] * r[0] + p[k][1] * r[1]) * p[(k + 1) % len(p)][2] -
                                      (p[(k + 1) % len(p)][0] * r[0] + p[(k + 1) % len(p)][1] * r[1]) * p[k][2]
                                      for k in range(len(p))))
            pts = [q for c in cs for q in c["pts"]]
            out.append({"n": n, "r": r, "d": sum(c["d"] for c in cs) / len(cs), "faces": len(cs), "area": round(area, 3),
                        "u": (min(c["box"][0] for c in cs), max(c["box"][1] for c in cs)),
                        "z": (min(c["box"][2] for c in cs), max(c["box"][3] for c in cs)),
                        "c": tuple(sum(q[k] for q in pts) / len(pts) for k in range(3)),
                        "parts": sorted({c["part"] for c in cs})})
    return out


def straight_rim(cl):
    """rim polyline (outward = right) of a straight cluster"""
    n, r, dr = cl["n"], cl["r"], cl["d"] + RIM
    u0, u1 = cl["u"][0] - MARGIN, cl["u"][1] + MARGIN
    return [(n[0] * dr + r[0] * u0, n[1] * dr + r[1] * u0), (n[0] * dr + r[0] * u1, n[1] * dr + r[1] * u1)]


# ------------------------------------------------------------------ capsule geometry
class Capsule:
    def __init__(self, rim, zb, zt, D, name, maxlen=3.9):
        self.rim, self.zb, self.zt, self.D, self.name = rim, zb, zt, D, name
        self.P = Poly(rim)
        us = [0.0]
        for a, b in zip(self.P.cum, self.P.cum[1:]):
            us += lin(a, b, maxlen)[1:]
        self.us = us
        self.front = [self.P.base(u) for u in us]
        self.back = []
        for u in us:
            b, m = self.P.base(u), self.P.normal(u)
            self.back.append((b[0] - D * m[0], b[1] - D * m[1]))

    def faces(self):
        """[(pts, normal)] normals into the capsule (visible from the opening)"""
        out = []
        zs = lin(self.zb, self.zt, 3.9)
        F, B = self.front, self.back
        for k in range(len(self.us) - 1):
            n = self.P.n[self.P.seg(0.5 * (self.us[k] + self.us[k + 1]))]
            for za, zb in zip(zs, zs[1:]):
                out.append(([(B[k][0], B[k][1], za), (B[k + 1][0], B[k + 1][1], za), (B[k + 1][0], B[k + 1][1], zb),
                             (B[k][0], B[k][1], zb)], (n[0], n[1], 0.0)))
            out.append(([(F[k][0], F[k][1], self.zb), (F[k + 1][0], F[k + 1][1], self.zb),
                         (B[k + 1][0], B[k + 1][1], self.zb), (B[k][0], B[k][1], self.zb)], (0.0, 0.0, 1.0)))
            out.append(([(F[k][0], F[k][1], self.zt), (F[k + 1][0], F[k + 1][1], self.zt),
                         (B[k + 1][0], B[k + 1][1], self.zt), (B[k][0], B[k][1], self.zt)], (0.0, 0.0, -1.0)))
        t0, t1 = self.P.t[0], self.P.t[-1]
        for i, t in ((0, t0), (len(F) - 1, (-t1[0], -t1[1]))):
            for za, zb in zip(zs, zs[1:]):
                out.append(([(F[i][0], F[i][1], za), (B[i][0], B[i][1], za), (B[i][0], B[i][1], zb),
                             (F[i][0], F[i][1], zb)], (t[0], t[1], 0.0)))
        return out

    def inside(self, p, tol=0.0):
        if not (self.zb - tol <= p[2] <= self.zt + tol):
            return False
        u = self.P.project((p[0], p[1]))
        if u < -tol or u > self.P.length + tol:
            return False
        b, m = self.P.base(u), self.P.unit_normal(u)
        depth = (b[0] - p[0]) * m[0] + (b[1] - p[1]) * m[1]
        # Poly.project clamps to the ends: the point must lie on the normal through base(u), not beside the rim
        lat = math.hypot(b[0] - depth * m[0] - p[0], b[1] - depth * m[1] - p[1])
        return -tol <= depth <= self.D + tol and lat <= tol + 0.01 + depth * 0.02

    def record(self, off):
        c = self.P.base(self.P.length / 2)
        return {"name": self.name, "rim_len_m": round(self.P.length, 3), "z": [round(self.zb, 4), round(self.zt, 4)],
                "depth_m": round(self.D, 3), "rim_build": [[round(p[0], 4), round(p[1], 4)] for p in self.rim],
                "centre_rim_delivered": [round(c[0] - off[0], 3), round(c[1] - off[1], 3)]}


# ------------------------------------------------------------------ collision tests
class Scene:
    """existing triangles (model) + accepted additions; conflict = triangle overlap or vertex within NEAR"""

    def __init__(self, verts, polys):
        self.base = BVHTree.FromPolygons([Vector(v) for v in verts], polys)
        self.base_verts = [Vector(v) for v in verts]
        self.grid = {}
        for i, v in enumerate(self.base_verts):
            self.grid.setdefault((math.floor(v.x), math.floor(v.y), math.floor(v.z)), []).append(i)
        self.add_v, self.add_f = [], []
        self.add_bvh = None

    def verts_in(self, lo, hi):
        out = []
        for x in range(math.floor(lo[0]), math.floor(hi[0]) + 1):
            for y in range(math.floor(lo[1]), math.floor(hi[1]) + 1):
                for z in range(math.floor(lo[2]), math.floor(hi[2]) + 1):
                    for i in self.grid.get((x, y, z), ()):
                        v = self.base_verts[i]
                        if all(lo[k] <= v[k] <= hi[k] for k in range(3)):
                            out.append(v)
        return out

    def conflicts(self, faces, ignore_near_base=False):
        vs, ps = [], []
        for pts, _ in faces:
            ps.append(list(range(len(vs), len(vs) + len(pts))))
            vs += [Vector(p) for p in pts]
        cand = BVHTree.FromPolygons(vs, ps)
        hits = len(self.base.overlap(cand))
        near = 0
        if not ignore_near_base:
            for v in vs:
                if self.base.find_nearest(v, NEAR)[0] is not None:
                    near += 1
            lo = [min(v[k] for v in vs) - NEAR for k in range(3)]
            hi = [max(v[k] for v in vs) + NEAR for k in range(3)]
            for v in self.verts_in(lo, hi):
                if cand.find_nearest(v, NEAR)[0] is not None:
                    near += 1
        add = 0
        if self.add_bvh is not None:
            add = len(self.add_bvh.overlap(cand))
            for v in vs:
                if self.add_bvh.find_nearest(v, NEAR)[0] is not None:
                    add += 1
        return {"overlap": hits, "near": near, "added": add}

    def accept(self, faces):
        for pts, _ in faces:
            self.add_f.append(list(range(len(self.add_v), len(self.add_v) + len(pts))))
            self.add_v += [Vector(p) for p in pts]
        self.add_bvh = BVHTree.FromPolygons(self.add_v, self.add_f)


# ------------------------------------------------------------------ cover strips
def strip_box(B0, B1, out, z0, z1, g, t, maxlen=3.9):
    """box on the facade line B0 -> B1 (plan), from g to g + t off the facade (outward 'out'), z0..z1;
    returns [(pts, normal)], closed"""
    ax = (B1[0] - B0[0], B1[1] - B0[1])
    L = math.hypot(*ax)
    a = (ax[0] / L, ax[1] / L)
    ss = lin(0.0, L, maxlen)
    P = lambda s, h, z: (B0[0] + a[0] * s + out[0] * h, B0[1] + a[1] * s + out[1] * h, z)  # noqa: E731
    f = []
    gb, gf = g, g + t
    for s0, s1 in zip(ss, ss[1:]):
        f.append(([P(s0, gf, z0), P(s1, gf, z0), P(s1, gf, z1), P(s0, gf, z1)], (out[0], out[1], 0.0)))
        f.append(([P(s0, gb, z0), P(s1, gb, z0), P(s1, gb, z1), P(s0, gb, z1)], (-out[0], -out[1], 0.0)))
        f.append(([P(s0, gb, z1), P(s1, gb, z1), P(s1, gf, z1), P(s0, gf, z1)], (0.0, 0.0, 1.0)))
        f.append(([P(s0, gb, z0), P(s1, gb, z0), P(s1, gf, z0), P(s0, gf, z0)], (0.0, 0.0, -1.0)))
    for s, sg in ((0.0, -1), (L, 1)):
        f.append(([P(s, gb, z0), P(s, gf, z0), P(s, gf, z1), P(s, gb, z1)], (a[0] * sg, a[1] * sg, 0.0)))
    return f
