"""TOW02 small facade parts the body does not have: AC baskets + glass railings, E-recess louvre, soffit (in Blender).

Engine gap: EG6 (panelised curtain-wall source: parts built from measurements, docs/backlog.md).

Reuses scripts/build_body_blender.py (exec into a namespace): Builder (1 cm weld, quads), to_world (building-local ->
world, rotation 56.7 deg), material(), _to_object(). Geometry is measured here from the source arrays
(outputs/measure-v001/source_npz, building-local frame of scripts/inspect_sections.py) and from the open scene.

Parts (one object each, collection cfg["collection"]):
- TOW02_ac_baskets: every #217 unit of typical_floor.json `f_ac_baskets` (37). Frame = the unit's back plate (normal
  out, v = 0 on the plate). Plan profile = outer envelope of the #217 section at top - 8 cm, mirrored about the unit
  axis (units are symmetric), Douglas-Peucker `dp_tol_m`. Front and sides = one-sided planes from the sloped #210
  bottom (plane fitted per unit) to the top, material TOW02_ac_perforated (perforation by opacity, no solidify);
  bottom = the sloped soffit (TOW02_facade, faces down); floor at the top (TOW02_ac_floor, faces up; user
  2026-10-20, replaces "no top"). Sides and floor end `embed_m` inside the wall (ray cast).
- TOW02_ac_railing_glass: the curved railing above each unit (#198 panes of height ~1.2 m), same envelope method,
  one plane per profile segment; ends stop `embed_m` past the attach surfaces (ray cast).
- Ray casts for ends use cfg["attach_names"] (body, body glass, top, top glass) + fins: attach + embed.
- Balconies of the bend zone (bend.json `balconies_cut_S+1.0`) are these same units (checked: every one matches a
  unit centre) -> no separate object; build() reports the match.
- TOW02_louvre (solid, user 2026-10-20): one box per #216 vertical blade per storey (15; 17 in the screen above
  64.7), in the frame of the mouth line; the outermost blades reach the slot walls + embed. TOW02_louvre_plates:
  one box per slat-grid level, sides and deep end to the walls + embed, bottom lifted `plate_lift_m`.
- TOW02_soffit: closes the body's open bottom loop at z 6.9 with EXACTLY its vertices (read from the scene):
  ring underside 6.9 (quad strip to an inner loop `ring_w_m` inside: corner polygon mitred, collinear points
  projected or spaced proportionally), vertical step 6.9 -> `z_slab` on the inner loop, slab underside at `z_slab`
  (paving strips inward with 3:1 quad transitions to thin the 257-point loop, then constrained Delaunay with a
  Steiner grid joined to quads; the remaining triangles are reported - an odd boundary cannot be all quads).

    ns = {}; exec(open(path).read(), ns); info = ns["build"](cfg)   # from the Blender MCP / Python console
cfg: see DEFAULTS. Existing part objects raise unless cfg["replace"] is True (then they are removed first).
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils import geometry as mgeo
from mathutils.bvhtree import BVHTree

MAX_EDGE_M = 3.8
PART_NAMES = ["TOW02_ac_baskets", "TOW02_ac_railing_glass", "TOW02_louvre", "TOW02_louvre_plates", "TOW02_soffit"]

DEFAULTS = dict(
    collection="TOW02_master",
    body_name="TOW02_body",
    glass_name="TOW02_body_glass",
    attach_names=["TOW02_body", "TOW02_body_glass", "TOW02_top", "TOW02_top_glass"],  # ends reach these (+ fins)
    end_gap_m=0.06,          # louvre blade / plate ends: close gaps to a wall up to this (half the 0.10 clear gap
                             # between blades; a larger gap reads as a normal blade gap and is left)
    plate_lift_m=0.01,       # plate box bottom above the slat level (no coplanar faces with body / soffit)
    fin_prefix="TOW02_fin_",  # ray casts for part ends also stop at fins (attach + embed, never pass through)
    body_script="scripts/build_body_blender.py",
    typical_json="outputs/measure-v001/typical/typical_floor.json",
    bend_json="outputs/measure-v001/bend_top/bend.json",
    soffit_json="outputs/measure-v001/bend_top/soffit.json",
    source_npz_dir="outputs/measure-v001/source_npz",
    dp_tol_m=0.012,          # profile simplification (user: <= 1 cm is skipped)
    embed_m=0.012,           # >= 10 mm into the receiving part
    ray_max_m=0.4,           # farther than this from the body: keep the measured end, report
    ring_w_m=1.0,            # soffit ring underside width (soffit.json: median 1.0 on all sides)
    z_slab=7.3,              # slab underside inside the ring (soffit.json)
    grid_m=1.9,              # Steiner grid of the residual slab fill
    pave_m=[0.5, 0.6, 0.7, 0.8, 1.0, 1.2],   # slab paving strips (3:1 transitions reduce the 257-point loop)
    pave_lmax_m=3.6,         # longest inner segment a transition may create
    fill_edge_m=3.3,         # residual fill: interior triangle edges longer than this get a Steiner midpoint
    pave_turn_deg=95.0,      # strips after the first may merge across corners up to this turn (convex quads only)
    replace=False,
)


# ------------------------------------------------------------------------------------------------ helpers
def _ns(cfg):
    ns = {"__name__": "tow02_body"}
    exec(open(cfg["body_script"], encoding="utf-8").read(), ns)
    return ns


def _abs(cfg, key):
    p = cfg[key]
    return p if os.path.isabs(p) else os.path.join(cfg["job_dir"], p)


def load_src(cfg, name, angle_deg):
    """(co_world, co_local, tri, short material per triangle) of a source object."""
    d = np.load(os.path.join(cfg["source_npz_dir"], name + ".npz"))
    a = math.radians(angle_deg)
    R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    mat = np.array([str(m).split()[-1] for m in d["mat"]])
    return d["co"], d["co"] @ R, d["tri"], mat


def tri_info(co, tri):
    T = co[tri]
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    a = np.linalg.norm(n, axis=1)
    return T, T.mean(1), n / np.maximum(a, 1e-12)[:, None], a / 2


def hcut_points(T, z, step=0.01):
    """Points every `step` along the section of triangles T (k,3,3) with plane Z = z -> (m, 2)."""
    s = T[:, :, 2] - z
    T, s = T[(s.min(1) < 0) & (s.max(1) > 0)], s[(s.min(1) < 0) & (s.max(1) > 0)]
    out = []
    for i in range(len(T)):
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if s[i, a] * s[i, b] < 0:
                t = s[i, a] / (s[i, a] - s[i, b])
                pts.append(T[i, a, :2] + (T[i, b, :2] - T[i, a, :2]) * t)
        if len(pts) == 2:
            n = max(1, int(np.linalg.norm(pts[1] - pts[0]) / step))
            out.append(pts[0] + (pts[1] - pts[0]) * np.linspace(0, 1, n + 1)[:, None])
    return np.concatenate(out) if out else np.zeros((0, 2))


def douglas_peucker(P, tol):
    P = np.asarray(P, float)
    if len(P) < 3:
        return P
    a, b = P[0], P[-1]
    ab = b - a
    L = np.linalg.norm(ab)
    if L < 1e-12:
        d = np.linalg.norm(P - a, axis=1)
    else:
        d = np.abs(np.cross(ab, P - a)) / L
    i = int(np.argmax(d))
    if d[i] <= tol:
        return np.array([a, b])
    left = douglas_peucker(P[:i + 1], tol)
    return np.concatenate([left[:-1], douglas_peucker(P[i:], tol)])


def half_profile(uv, v_centre, tol, bin_deg=0.5):
    """Outer envelope of mirrored points (|u|, v) seen from (0, v_centre): polyline from the axis (u = 0) to the
    end at the wall, simplified. uv already centred on the unit axis."""
    uu, vv = np.abs(uv[:, 0]), uv[:, 1]
    th = np.degrees(np.arctan2(uu, vv - v_centre))
    r = np.hypot(uu, vv - v_centre)
    b = np.floor(th / bin_deg).astype(int)
    pts = []
    for k in np.unique(b):
        idx = np.where(b == k)[0]
        j = idx[np.argmax(r[idx])]
        pts.append((th[j], uu[j], vv[j]))
    pts.sort()
    P = np.array([(p[1], p[2]) for p in pts])
    P[0, 0] = 0.0                                   # the front starts on the axis
    return douglas_peucker(P, tol)


def mirror_profile(H):
    """Half profile (axis -> wall end) -> full U from the +u wall end to the -u wall end, axis point dropped
    (even vertex count, so the bottom pairs into quads)."""
    right = [(u, v) for u, v in H[1:]][::-1]
    left = [(-u, v) for u, v in H[1:]]
    return right + left


class Mesh:
    """Plain vertex/face list in world coordinates (exact vertices, e.g. the body loop)."""

    def __init__(self):
        self.co, self.faces, self.mats = [], [], []

    def v(self, p):
        self.co.append(Vector(p))
        return len(self.co) - 1

    def face(self, idx, mat=0, want=None):
        if len(set(idx)) < len(idx):
            return None
        if want is not None:
            n = Vector((0, 0, 0))
            for i in range(len(idx)):              # Newell normal
                a, b = self.co[idx[i]], self.co[idx[(i + 1) % len(idx)]]
                n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
            if n.dot(want) < 0:
                idx = list(reversed(idx))
        self.faces.append(tuple(idx))
        self.mats.append(mat)
        return len(self.faces) - 1

    def to_object(self, name, coll):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(c) for c in self.co], [], self.faces)
        for p, m in zip(me.polygons, self.mats):
            p.material_index = m
        me.update()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def _bvh(objs):
    verts, polys = [], []
    for ob in objs:
        mw = ob.matrix_world
        off = len(verts)
        verts += [mw @ v.co for v in ob.data.vertices]
        polys += [tuple(off + i for i in p.vertices) for p in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0)


class Caster:
    """Ray casts in building-local coordinates against world BVHs."""

    def __init__(self, ns, bvhs):
        self.W, self.bvhs = ns["to_world"], bvhs

    def hit(self, p, d, maxd):
        """Distance to the first hit along local direction d from local point p, or None."""
        o = self.W(*p)
        dv = self.W(*d).normalized()
        best = None
        for t in self.bvhs:
            loc, nrm, idx, dist = t.ray_cast(o, dv, maxd)
            if loc is not None and (best is None or dist < best):
                best = dist
        return best


# ------------------------------------------------------------------------------------------------ (a) AC
def build_ac(cfg, ns, src, caster, coll):
    co_w, co, tri, mat = src
    T, cen, nrm, ar = tri_info(co, tri)
    lo, hi = T.min(1)[:, 2], T.max(1)[:, 2]
    units = json.load(open(cfg["typical_json"], encoding="utf-8"))["f_ac_baskets"]["units"]
    B, G = ns["Builder"](), ns["Builder"]()
    W = ns["to_world"]
    E = cfg["embed_m"]
    report, floors = [], 0
    for k, un in enumerate(units):
        c = np.array(un["centre_xy"])
        z0, z1 = un["z"]
        near = np.linalg.norm(cen[:, :2] - c, axis=1) < 2.2
        s217 = near & (mat == "#217") & (cen[:, 2] > z0 - 0.05) & (cen[:, 2] < z1 + 0.05)
        vert = np.where(s217 & (np.abs(nrm[:, 2]) < 0.2))[0]
        ang = np.round(np.degrees(np.arctan2(nrm[vert, 1], nrm[vert, 0])) / 5).astype(int)
        best = max(np.unique(ang), key=lambda b: ar[vert][ang == b].sum())
        sv = vert[ang == best]                                   # back plate = largest vertical facet group
        n2 = (nrm[sv, :2] * ar[sv, None]).sum(0)
        n2 /= np.linalg.norm(n2)
        w0 = (cen[sv, :2] * ar[sv, None]).sum(0) / ar[sv].sum()
        Q = T[s217].reshape(-1, 3)
        if (Q[:, :2].mean(0) - w0) @ n2 < 0:
            n2 = -n2                                             # source normals are mirrored: orient outward
        t2 = np.array([-n2[1], n2[0]])
        to_uv = lambda P: np.c_[(P - w0) @ t2, (P - w0) @ n2]
        z_top = float(Q[:, 2].max())
        uv = to_uv(hcut_points(T[s217], z_top - 0.08))
        uv = uv[uv[:, 1] > 0.02]
        uc = 0.5 * (uv[:, 0].min() + uv[:, 0].max())
        uv[:, 0] -= uc
        H = half_profile(uv, -0.3, cfg["dp_tol_m"])
        # sloped bottom (#210 under the unit): z = a*v + b
        s210 = near & (mat == "#210") & (np.abs(nrm[:, 2]) > 0.6) & (np.abs(nrm[:, 2]) < 0.995) & \
            (cen[:, 2] > z0 - 0.1) & (cen[:, 2] < z1)
        Bp = T[s210].reshape(-1, 3)
        if len(Bp) >= 3:
            a_s, b_s = np.polyfit(to_uv(Bp[:, :2])[:, 1], Bp[:, 2], 1)
        else:
            a_s, b_s = 0.0, z0
        # wall: ray from 10 cm out, back along -n, at mid band height
        L = lambda u, v: w0 + t2 * (u + uc) + n2 * v
        wall_v = []
        for u in (H[-1][0], -H[-1][0]):
            p = L(u, 0.1)
            h = caster.hit((p[0], p[1], 0.5 * (z0 + z1)), (-n2[0], -n2[1], 0), cfg["ray_max_m"])
            wall_v.append(None if h is None else 0.1 - h)
        found = [w for w in wall_v if w is not None]
        v_end = (min(found) if found else 0.0) - E
        H = H.copy()
        H[-1, 1] = min(H[-1, 1], v_end)
        U = mirror_profile(H)
        P2 = [L(u, v) for u, v in U]
        zb = [a_s * v + b_s for u, v in U]
        ctr = L(0.0, 0.5 * H[0][1])
        nq = 0
        for i in range(len(P2) - 1):
            a, b = P2[i], P2[i + 1]
            mid = 0.5 * (a + b)
            seg = b - a
            out = np.array([seg[1], -seg[0]])
            if out @ (mid - ctr) < 0:
                out = -out
            f = B.quad(((a[0], a[1], zb[i]), (b[0], b[1], zb[i + 1]), (b[0], b[1], z_top), (a[0], a[1], z_top)),
                       0, W(out[0], out[1], 0))
            nq += f is not None
        N = len(P2)
        for i in range(N // 2 - 1):                              # bottom: pair i <-> N-1-i
            idx = (i, i + 1, N - 2 - i, N - 1 - i)
            f = B.quad(tuple((P2[j][0], P2[j][1], zb[j]) for j in idx), 1, Vector((0, 0, -1)))
            nq += f is not None
        fl_unit = 0
        for i in range(N // 2 - 1):                              # floor (user 2026-10-20): top, faces up
            idx = (i, i + 1, N - 2 - i, N - 1 - i)
            f = B.quad(tuple((P2[j][0], P2[j][1], z_top) for j in idx), 2, Vector((0, 0, 1)))
            nq += f is not None
            floors += f is not None
            fl_unit += f is not None
        # railing: #198 panes of height < 1.35 m starting at the unit top
        s198 = near & (mat == "#198") & (lo > z_top - 0.06) & (hi < z_top + 1.35)
        rail = {"panes": int(s198.sum())}
        if s198.sum():
            zr0, zr1 = float(lo[s198].min()), float(hi[s198].max())
            ruv = to_uv(hcut_points(T[s198], 0.5 * (zr0 + zr1)))
            ruv[:, 0] -= uc
            RH = half_profile(ruv, -0.6, cfg["dp_tol_m"])
            RU = mirror_profile(RH)
            R2 = [L(u, v) for u, v in RU]
            ends = []
            for e0, e1 in ((1, 0), (len(R2) - 2, len(R2) - 1)):  # stop at body / body glass + embed
                a, b = R2[e0], R2[e1]
                d = b - a
                Lseg = float(np.linalg.norm(d))
                d /= Lseg
                h = caster.hit((a[0], a[1], 0.5 * (zr0 + zr1)), (d[0], d[1], 0), Lseg + cfg["ray_max_m"])
                if h is not None:
                    R2[e1] = a + d * (h + E)
                ends.append(None if h is None else round(h + E - Lseg, 3))
            rctr = L(0.0, 0.3)
            for i in range(len(R2) - 1):
                a, b = R2[i], R2[i + 1]
                mid, seg = 0.5 * (a + b), b - a
                out = np.array([seg[1], -seg[0]])
                if out @ (mid - rctr) < 0:
                    out = -out
                G.quad(((a[0], a[1], zr0), (b[0], b[1], zr0), (b[0], b[1], zr1), (a[0], a[1], zr1)), 0,
                       W(out[0], out[1], 0))
            rail.update(z=[round(zr0, 3), round(zr1, 3)], segments=len(R2) - 1,
                        end_change_m=ends, depth_v=round(float(RH[0][1]), 3))
        report.append(dict(unit=k, z=[round(min(zb), 3), round(z_top, 3)], centre=[round(float(x), 3) for x in L(0, 0)],
                           normal=[round(float(x), 4) for x in n2], width=round(2 * float(H[-1][0]), 3),
                           depth=round(float(H[0][1]), 3), profile_pts=len(U), slope=round(float(a_s), 4),
                           wall_v=[None if w is None else round(w, 4) for w in wall_v], faces=nq, floor_faces=fl_unit,
                           railing=rail))
    bas = ns["_to_object"](B.bm, "TOW02_ac_baskets", coll)
    bas.data.materials.append(_mat_opacity("TOW02_ac_perforated", (0.55, 0.55, 0.55, 0.6)))
    bas.data.materials.append(ns["material"]("TOW02_facade", (0.12, 0.12, 0.12, 1)))
    bas.data.materials.append(_mat_solid("TOW02_ac_floor", (0.3, 0.3, 0.3, 1.0)))
    gl = ns["_to_object"](G.bm, "TOW02_ac_railing_glass", coll)
    gl.data.materials.append(ns["material"]("TOW02_glass", (0.25, 0.5, 0.9, 1)))
    return dict(units=len(units), floor_faces=floors, basket_faces=len(bas.data.polygons),
                railing_faces=len(gl.data.polygons),
                skipped=dict(baskets=B.skipped, railing=G.skipped), per_unit=report)


def _mat_opacity(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


def balconies_vs_units(cfg):
    """Every bend-zone balcony cut (bend.json) matched to an AC unit (centre inside the cut bbox + 0.3 m)."""
    units = json.load(open(cfg["typical_json"], encoding="utf-8"))["f_ac_baskets"]["units"]
    floors = json.load(open(cfg["bend_json"], encoding="utf-8"))["floors"]
    rows = []
    for f in floors:
        for b in f["balconies_cut_S+1.0"]:
            x0, y0, x1, y1 = b["bbox"]
            hit = [k for k, u in enumerate(units)
                   if x0 - 0.3 <= u["centre_xy"][0] <= x1 + 0.3 and y0 - 0.3 <= u["centre_xy"][1] <= y1 + 0.3
                   and u["z"][0] <= f["slab_S"] + 1.0 <= u["z"][1] + 1.6]
            rows.append(dict(floor_S=f["slab_S"], side=b["side"], units=hit))
    return dict(cuts=len(rows), matched=sum(1 for r in rows if len(r["units"]) == 1), rows=rows)


# ------------------------------------------------------------------------------------------------ (b) louvre
def _clusters(vals, gap):
    order = np.argsort(vals)
    groups, cur = [], [order[0]]
    for a, b in zip(order[:-1], order[1:]):
        if vals[b] - vals[a] > gap:
            groups.append(cur)
            cur = []
        cur.append(b)
    groups.append(cur)
    return groups


def _box(B, m, d, n, s0, s1, t0, t1, za, zb, W, MAXS, mat=0):
    """Closed box in the frame (m, d along, n across) between s0..s1, t0..t1, za..zb; sides split < MAXS."""
    ns_ = max(1, math.ceil((s1 - s0) / MAXS - 1e-9))
    nt = max(1, math.ceil((t1 - t0) / MAXS - 1e-9))
    nz = max(1, math.ceil((zb - za) / MAXS - 1e-9))
    S = [s0 + (s1 - s0) * i / ns_ for i in range(ns_ + 1)]
    T_ = [t0 + (t1 - t0) * i / nt for i in range(nt + 1)]
    Z = [za + (zb - za) * i / nz for i in range(nz + 1)]
    P = lambda s, t, z: (m[0] + d[0] * s + n[0] * t, m[1] + d[1] * s + n[1] * t, z)
    up, dn = Vector((0, 0, 1)), Vector((0, 0, -1))
    vd, vn = W(d[0], d[1], 0), W(n[0], n[1], 0)
    k = 0
    for i in range(ns_):
        for j in range(nt):
            for z, want in ((zb, up), (za, dn)):
                k += B.quad((P(S[i], T_[j], z), P(S[i + 1], T_[j], z), P(S[i + 1], T_[j + 1], z),
                             P(S[i], T_[j + 1], z)), mat, want) is not None
    for q in range(nz):
        for i in range(ns_):
            for t, want in ((t0, -vn), (t1, vn)):
                k += B.quad((P(S[i], t, Z[q]), P(S[i + 1], t, Z[q]), P(S[i + 1], t, Z[q + 1]),
                             P(S[i], t, Z[q + 1])), mat, want) is not None
        for j in range(nt):
            for s, want in ((s0, -vd), (s1, vd)):
                k += B.quad((P(s, T_[j], Z[q]), P(s, T_[j + 1], Z[q]), P(s, T_[j + 1], Z[q + 1]),
                             P(s, T_[j], Z[q + 1])), mat, want) is not None
    return k


def _reach(caster, m, d, n, face, axis, sgn, others, zs, cfg):
    """Farthest attach-surface hit (body / top / glass / fins) from the frame line beyond an end face, cast along
    sgn*d (axis 's') or sgn*n (axis 't') from sample points (other coordinate in `others`, heights `zs`); limited
    to |face| + end_gap_m. None when nothing is hit."""
    best = None
    dirv = (d if axis == "s" else n) * sgn
    for o in others:
        p = m + (n * o if axis == "s" else d * o)
        for z in zs:
            h = caster.hit((p[0], p[1], z), (dirv[0], dirv[1], 0), abs(face) + cfg["end_gap_m"])
            if h is not None and (best is None or h > best):
                best = h
    return best


def build_louvre(cfg, ns, src, caster, coll):
    """E-recess louvre as solids (user 2026-10-20: geometry, easier to texture). Blades: per storey cluster of #216
    vertical blades, one box per blade in the frame of the mouth line (blades are perpendicular to it); the
    outermost blades of a storey reach the slot walls (body / top / fins) + embed_m when the gap is < end_gap_m.
    Plates: one box per level (slat grid b .. b+0.18, bottom lifted plate_lift_m against coplanar faces), sides
    and deep end ray cast to the walls + embed, mouth end as measured."""
    co_w, co, tri, mat = src
    T, cen, nrm, ar = tri_info(co, tri)
    s = np.where(mat == "#216")[0]
    T, cen, nrm, ar = T[s], cen[s], nrm[s], ar[s]
    lo, hi = T.min(1)[:, 2], T.max(1)[:, 2]
    W = ns["to_world"]
    E, MAXS = cfg["embed_m"], ns["MAX_SIDE_M"]
    Bl, Bp = ns["Builder"](), ns["Builder"]()
    tall = np.where(hi - lo > 1.0)[0]
    groups = [tall[g] for g in _clusters(lo[tall], 0.3)]
    merged = []
    for g in groups:                                   # pieces < 0.1 m apart in z are one blade (top screen)
        if merged and lo[g].min() - hi[merged[-1]].max() < 0.1:
            merged[-1] = np.concatenate([merged[-1], g])
        else:
            merged.append(g)
    floors, nblades = [], 0
    for g in merged:
        P = T[g].reshape(-1, 3)
        za, zb = float(P[:, 2].min()), float(P[:, 2].max())
        m = P[:, :2].mean(0)
        _, _, vt = np.linalg.svd(P[:, :2] - m)
        d = vt[0] if vt[0][1] >= 0 else -vt[0]          # along the mouth (+Y)
        n = np.array([d[1], -d[0]])
        if n[0] < 0:
            n = -n                                      # out of the recess (+X)
        comps = _components(tri[s][g])                  # one source blade = connected triangles
        cs = [((T[g][c].reshape(-1, 3)[:, :2] - m) @ d) for c in comps]
        ct = [((T[g][c].reshape(-1, 3)[:, :2] - m) @ n) for c in comps]
        mids = np.array([0.5 * (a.min() + a.max()) for a in cs])
        blades = []
        for grp in _clusters(mids, 0.03):               # pieces of one blade at different heights
            a = np.concatenate([cs[i] for i in grp])
            b = np.concatenate([ct[i] for i in grp])
            blades.append([float(a.min()), float(a.max()), float(b.min()), float(b.max())])
        blades.sort()
        zs = [za + (zb - za) * f for f in (0.05, 0.25, 0.5, 0.75, 0.95)]
        ends = []
        for sgn in (-1, 1):                              # outermost blade on each side reaches the wall
            dropped = 0
            while blades:
                k = 0 if sgn < 0 else len(blades) - 1
                s0, s1, t0, t1 = blades[k]
                face, inner = (s0, s1) if sgn < 0 else (s1, s0)
                h = _reach(caster, m, d, n, face, "s", sgn, [t0 + f * (t1 - t0) for f in (0.1, 0.5, 0.9)], zs, cfg)
                if h is None:
                    ends.append(dict(gap_closed_m=None, embed_m=None, dropped=dropped, note="no wall within end_gap_m"))
                    break
                if h + E - sgn * inner < 0.01:          # blade lies inside the wall (fin): drop, try the next one
                    blades.pop(k)
                    dropped += 1
                    continue
                blades[k][0 if sgn < 0 else 1] = sgn * (h + E)
                ends.append(dict(gap_closed_m=round(h - abs(face), 4), embed_m=E, dropped=dropped))
                break
        touching = sum(1 for a, b in zip(blades, blades[1:]) if b[0] - a[1] < 0.01)
        for s0, s1, t0, t1 in blades:
            _box(Bl, m, d, n, s0, s1, t0, t1, za, zb, W, MAXS)
        nblades += len(blades)
        mids = [0.5 * (b[0] + b[1]) for b in blades]
        floors.append(dict(z=[round(za, 3), round(zb, 3)], blades=len(blades), touching_pairs=touching,
                           pitch_m=round(float(np.median(np.diff(mids))), 4),
                           blade_depth_thick_m=[round(float(np.median([b[3] - b[2] for b in blades])), 3),
                                                round(float(np.median([b[1] - b[0] for b in blades[1:-1]])), 3)],
                           ends=ends, centre=[round(float(x), 3) for x in m]))
    # plates
    hor = np.where(np.abs(nrm[:, 2]) > 0.99)[0]
    lev = [hor[g] for g in _clusters(cen[hor, 2], 0.005) if ar[hor[g]].sum() > 1.0]
    lev.sort(key=lambda g: cen[g, 2].mean())
    pairs = []
    for g in lev:
        if pairs and cen[g, 2].mean() - cen[pairs[-1][-1], 2].mean() < 0.25 and len(pairs[-1]) == 1:
            pairs[-1].append(g)
        else:
            pairs.append([g])
    plates = []
    for pr in pairs:
        g = np.concatenate(pr)
        zl = [float(cen[x, 2].mean()) for x in pr]
        z_lo, z_hi = min(zl) + cfg["plate_lift_m"], max(zl)
        if z_hi - z_lo < 0.02:
            z_lo = z_hi - 0.05
        xy = T[g].reshape(-1, 3)[:, :2]
        m = xy.mean(0)
        _, _, vt = np.linalg.svd(xy - m)
        d = vt[0] if vt[0][0] >= 0 else -vt[0]          # along the slot, towards the mouth (+X)
        q = np.array([-d[1], d[0]])
        t, w = (xy - m) @ d, (xy - m) @ q
        ext = {"deep": float(t.min()), "side-": float(w.min()), "side+": float(w.max())}
        t1 = float(t.max())
        zs = [0.5 * (z_lo + z_hi)]
        ends = {}
        for key, axis, sgn in (("deep", "s", -1), ("side-", "t", -1), ("side+", "t", 1)):
            face = ext[key]
            if axis == "s":
                others = [ext["side-"] + f * (ext["side+"] - ext["side-"]) for f in (0.1, 0.5, 0.9)]
            else:
                others = [ext["deep"] + f * (t1 - ext["deep"]) for f in (0.05, 0.3, 0.55, 0.8)]
            h = _reach(caster, m, d, q, face, axis, sgn, others, zs, cfg)
            if h is not None:
                ext[key] = sgn * (h + E)
                ends[key] = dict(gap_closed_m=round(h - abs(face), 4), embed_m=E)
            else:                                       # nothing within reach: measured edge + embed
                ext[key] = face + sgn * E
                ends[key] = dict(gap_closed_m=None, embed_m=None)
        _box(Bp, m, d, q, ext["deep"], t1, ext["side-"], ext["side+"], z_lo, z_hi, W, MAXS)
        plates.append(dict(z=[round(z_lo, 3), round(z_hi, 3)],
                           size=[round(t1 - ext["deep"], 3), round(ext["side+"] - ext["side-"], 3)],
                           source_z=[round(x, 3) for x in zl], ends=ends))
    lou = ns["_to_object"](Bl.bm, "TOW02_louvre", coll)
    lou.data.materials.append(_mat_solid("TOW02_louvre", (0.45, 0.45, 0.42, 1.0)))
    pl = ns["_to_object"](Bp.bm, "TOW02_louvre_plates", coll)
    pl.data.materials.append(_mat_solid("TOW02_louvre", (0.45, 0.45, 0.42, 1.0)))
    return dict(blades=nblades, storeys=floors, plates=plates, louvre_faces=len(lou.data.polygons),
                plate_faces=len(pl.data.polygons), skipped=dict(louvre=Bl.skipped, plates=Bp.skipped))


def _components(tris):
    """Connected components of triangles (vertex-index rows) -> list of row-index arrays."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in tris:
        ra = find(int(a))
        for v in (b, c):
            rv = find(int(v))
            if rv != ra:
                parent[rv] = ra
    lab = {}
    for i, t in enumerate(tris):
        lab.setdefault(find(int(t[0])), []).append(i)
    return [np.array(v) for v in lab.values()]


def _mat_solid(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


# ------------------------------------------------------------------------------------------------ (d) soffit
def body_bottom_loop(body, z_tol=1e-3):
    """Ordered vertex indices and world coordinates of the body's open boundary loop at its lowest z."""
    me = body.data
    zmin = min(v.co.z for v in me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bnd = [e for e in bm.edges if e.is_boundary and all(abs(v.co.z - zmin) < z_tol for v in e.verts)]
    adj = {}
    for e in bnd:
        a, b = (v.index for v in e.verts)
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    if any(len(x) != 2 for x in adj.values()):
        raise ValueError("bottom boundary is not a simple loop")
    start = min(adj)
    loop, prev = [start], None
    while True:
        cur = loop[-1]
        nxt = adj[cur][0] if adj[cur][0] != prev else adj[cur][1]
        if nxt == start:
            break
        prev = cur
        loop.append(nxt)
    if len(loop) != len(adj):
        raise ValueError(f"bottom boundary has several loops ({len(loop)} of {len(adj)} vertices in the first)")
    bm.free()
    mw = body.matrix_world
    return loop, [mw @ me.vertices[i].co for i in loop]


def _local(ns, p):
    a = math.radians(ns["LOCAL_ANGLE_DEG"])
    c, s = math.cos(a), math.sin(a)
    return np.array([p.x * c + p.y * s, -p.x * s + p.y * c])


def inner_loop(P, w):
    """Inner loop `w` inside the CCW loop P (n,2), one point per point. Corners (turn > 1 deg) = intersections of
    the offset corner-polygon edges; an offset edge that inverts (feature smaller than the offset) is dropped and
    its points share one inner point (shortest first, repeated). Collinear points: perpendicular projection onto
    their offset edge, or proportional spacing where projections leave the edge (< 1.2 cm apart)."""
    n = len(P)
    E = np.roll(P, -1, 0) - P
    D = E / np.linalg.norm(E, axis=1)[:, None]
    Dp = np.roll(D, 1, 0)
    turn = np.degrees(np.arcsin(np.clip(Dp[:, 0] * D[:, 1] - Dp[:, 1] * D[:, 0], -1, 1)))
    ci = np.where(np.abs(turn) > 1.0)[0]
    C = P[ci]
    m = len(ci)
    EC = np.roll(C, -1, 0) - C
    DC = EC / np.linalg.norm(EC, axis=1)[:, None]
    NC = np.c_[-DC[:, 1], DC[:, 0]]                   # left = inward for CCW
    alive = [True] * m

    def isect(k1, k2):
        p0, p1 = C[k1] + NC[k1] * w, C[k2] + NC[k2] * w
        A = np.array([DC[k1], -DC[k2]]).T
        if abs(np.linalg.det(A)) < 1e-9:
            return p1
        return p0 + DC[k1] * np.linalg.solve(A, p1 - p0)[0]

    def left(k):                                       # last alive edge ending at corner k
        j = (k - 1) % m
        while not alive[j]:
            j = (j - 1) % m
        return j

    def right(k):                                      # first alive edge starting at corner k
        j = k
        while not alive[j]:
            j = (j + 1) % m
        return j

    collapsed = []
    for _ in range(m):
        IC = [isect(left(k), right(k)) for k in range(m)]
        bad = [k for k in range(m) if alive[k] and (IC[(k + 1) % m] - IC[k]) @ DC[k] <= 1e-6]
        if not bad:
            break
        k = min(bad, key=lambda q: np.linalg.norm(EC[q]))
        alive[k] = False
        collapsed.append(int(k))
    I = np.zeros_like(P)
    mode = {"perpendicular": 0, "proportional": 0, "collapsed": len(collapsed)}
    for k in range(m):
        a, b = ci[k], ci[(k + 1) % m]
        idx = [(a + j) % n for j in range(1, (b - a) % n)]
        I[a] = IC[k]
        if not idx:
            continue
        if not alive[k]:
            for j in idx:
                I[j] = IC[k]
            continue
        EI = IC[(k + 1) % m] - IC[k]
        Li = np.linalg.norm(EI)
        dI = EI / Li
        tp = np.array([((P[j] + NC[k] * w) - IC[k]) @ dI / Li for j in idx])
        if not np.all(np.diff(np.r_[0.0, tp, 1.0]) > 0.012 / Li):
            Lo = np.linalg.norm(EC[k])
            tp = np.array([np.linalg.norm(P[j] - C[k]) / Lo for j in idx])
            mode["proportional"] += 1
        else:
            mode["perpendicular"] += 1
        for j, t in zip(idx, tp):
            I[j] = IC[k] + EI * t
    bad_left = [k for k in range(m) if alive[k] and (IC[(k + 1) % m] - IC[k]) @ DC[k] <= 1e-6]
    return I, dict(corners=int(m), collapsed_edges=collapsed, inverted_left=bad_left, edge_modes=mode)


def _inside(poly, pts):
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), bool)
    for (x0, y0), (x1, y1) in zip(poly, np.roll(poly, -1, 0)):
        c = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-300) + x0)
        inside ^= c
    return inside


def _seg_dist(poly, pts):
    A, B = poly, np.roll(poly, -1, 0)
    d = np.full(len(pts), np.inf)
    for a, b in zip(A, B):
        ab = b - a
        t = np.clip(((pts - a) @ ab) / (ab @ ab), 0, 1)
        d = np.minimum(d, np.linalg.norm(pts - (a + t[:, None] * ab), axis=1))
    return d


def build_soffit(cfg, ns, body, coll):
    loop_idx, Pw = body_bottom_loop(body)
    P = np.array([_local(ns, p) for p in Pw])
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    if area < 0:                                       # work CCW
        loop_idx, Pw, P = loop_idx[::-1], Pw[::-1], P[::-1]
    n = len(P)
    z0 = float(np.median([p.z for p in Pw]))
    z1 = cfg["z_slab"]
    I, info = inner_loop(P, cfg["ring_w_m"])
    if info["inverted_left"]:
        raise ValueError(f"soffit inner loop inverted at corner edges {info['inverted_left']}")
    W = ns["to_world"]
    M = Mesh()
    o = [M.v(p.copy()) for p in Pw]                    # EXACTLY the body loop vertices
    # merge inner points closer than 1.2 cm (keep quads elsewhere)
    keep = [0]
    for i in range(1, n):
        if np.linalg.norm(I[i] - I[keep[-1]]) >= 0.012:
            keep.append(i)
    if np.linalg.norm(I[keep[-1]] - I[keep[0]]) < 0.012 and len(keep) > 1:
        keep.pop()
    rep = {}
    for k_i, i in enumerate(keep):
        j = keep[(k_i + 1) % len(keep)]
        for q in range(i, i + ((j - i) % n or n)):
            rep[q % n] = i
    il = {i: M.v(W(I[i][0], I[i][1], z0)) for i in keep}
    iu = {i: M.v(W(I[i][0], I[i][1], z1)) for i in keep}
    down, tris = Vector((0, 0, -1)), {"ring": 0, "slab": 0}
    for i in range(n):
        j = (i + 1) % n
        a, b = rep[i], rep[j]
        if a == b:
            M.face((o[i], o[j], il[a]), 0, down)
            tris["ring"] += 1
        else:
            M.face((o[i], o[j], il[b], il[a]), 0, down)
    for k_i, i in enumerate(keep):                     # vertical step: faces the recess (inward = left of CCW)
        j = keep[(k_i + 1) % len(keep)]
        d = I[j] - I[i]
        inward = W(-d[1], d[0], 0)
        M.face((il[i], il[j], iu[j], iu[i]), 0, inward)
    # slab underside: paving strips with 3:1 transitions, then CDT + Steiner grid joined into quads
    X = [np.array(I[i]) for i in keep]
    loop = list(range(len(keep)))
    faces2d, strips = [], []
    for k, depth in enumerate(cfg["pave_m"]):
        res = pave_strip(loop, X, depth, cfg["pave_lmax_m"], 30.0 if k == 0 else cfg["pave_turn_deg"])
        if res is None:
            break
        loop, fs, st = res
        faces2d += fs
        strips.append(st)
    poly = np.array([X[i] for i in loop])
    g = cfg["grid_m"]
    xs = np.arange(poly[:, 0].min() + g / 2, poly[:, 0].max(), g)
    ys = np.arange(poly[:, 1].min() + g / 2, poly[:, 1].max(), g)
    grid = np.array([(x, y) for x in xs for y in ys])
    grid = grid[_inside(poly, grid)]
    grid = grid[_seg_dist(poly, grid) > 0.55 * g]
    for _ in range(8):                                 # refine: midpoints of interior edges longer than limit
        coords = [Vector((float(p[0]), float(p[1]))) for p in poly] +             [Vector((float(p[0]), float(p[1]))) for p in grid]
        vo, eo, fo, ov, oe, of = mgeo.delaunay_2d_cdt(coords, [], [list(range(len(poly)))], 1, 1e-7, True)
        npoly = len(poly)
        isb = lambda k: any(x < npoly for x in ov[k])
        add = []
        for f in fo:
            for a_, b_ in zip(f, f[1:] + f[:1]):
                if (vo[a_] - vo[b_]).length > cfg["fill_edge_m"]:
                    nb = (isb(a_) and isb(b_) and
                          min(abs(min(x for x in ov[a_] if x < npoly) - min(x for x in ov[b_] if x < npoly)),
                              npoly - abs(min(x for x in ov[a_] if x < npoly) - min(x for x in ov[b_] if x < npoly))) == 1)
                    if not nb:
                        add.append(0.5 * (np.array(vo[a_]) + np.array(vo[b_])))
        add = np.array(add).reshape(-1, 2)
        add = add[_inside(poly, add)] if len(add) else add
        add = add[_seg_dist(poly, add) > 0.3] if len(add) else add
        if not len(add):
            break
        add = np.unique(np.round(add, 4), axis=0)
        grid = np.vstack([grid.reshape(-1, 2), add])
    cdt_ids = {}
    for k in range(len(vo)):
        src = [x for x in ov[k] if x < len(coords)]
        if src and src[0] < len(poly):
            cdt_ids[k] = loop[src[0]]
        else:
            X.append(np.array((vo[k].x, vo[k].y)))
            cdt_ids[k] = len(X) - 1
    cdt_faces = [tuple(cdt_ids[k] for k in f) for f in fo]
    vmap = {i: iu[keep[i]] for i in range(len(keep))}

    def vid(i):
        if i not in vmap:
            vmap[i] = M.v(W(X[i][0], X[i][1], z1))
        return vmap[i]

    for f in faces2d:
        M.face(tuple(vid(i) for i in f), 0, down)
    slab_first = len(M.faces)
    for f in cdt_faces:
        M.face(tuple(vid(i) for i in f), 0, down)
    ob = M.to_object("TOW02_soffit", coll)
    # join the CDT triangles into quads; quads with a corner > 170 deg (collinear points) go back to triangles
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    tri_faces = [bm.faces[i] for i in range(slab_first, len(bm.faces))]
    bmesh.ops.join_triangles(bm, faces=tri_faces, angle_face_threshold=math.radians(5),
                             angle_shape_threshold=math.radians(180))
    flat = [f for f in bm.faces if len(f.verts) == 4 and max(_corner_angles(f)) > 170.0]
    if flat:
        bmesh.ops.triangulate(bm, faces=flat)
    for f in bm.faces:
        if f.normal.z > 0.5:
            f.normal_flip()
    bm.normal_update()
    tris["slab"] = sum(1 for f in bm.faces if len(f.verts) == 3) - tris["ring"]
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.materials.append(ns["material"]("TOW02_facade", (0.12, 0.12, 0.12, 1)))
    info.update(body_loop_vertices=n, inner_vertices=len(keep), z_ring=round(z0, 4), z_slab=z1, strips=strips,
                residual_loop=len(loop), steiner=len(grid), joined_back_to_tris=len(flat), triangles=tris,
                faces=len(ob.data.polygons))
    return info


def _corner_angles(f):
    out = []
    vs = [v.co for v in f.verts]
    for i in range(len(vs)):
        a, b = vs[i - 1] - vs[i], vs[(i + 1) % len(vs)] - vs[i]
        out.append(math.degrees(a.angle(b, 0.0)))
    return out


def _convex(q):
    q = np.asarray(q)
    s = np.array([np.cross(q[(i + 1) % 4] - q[i], q[(i + 2) % 4] - q[(i + 1) % 4]) for i in range(4)])
    return bool(np.all(s > 1e-7) or np.all(s < -1e-7))


def pave_strip(loop, X, depth, lmax, max_turn=30.0):
    """One quad strip `depth` inside the CCW loop (ids into X). Triples of segments with no corner > max_turn
    inside and total length <= lmax become one inner segment through the 3:1 transition
    (a,b,m1,e) (b,c,m2,m1) (c,d,f,m2) (e,m1,m2,f), m = half depth; greedy, shortest first, convex only. A kept
    segment whose inner edge would exceed MAX_EDGE_M (growth at concave corners) gets the inverse 1:3 transition.
    Returns (new loop, faces, stats) or None when the offset inverts or nothing merges."""
    P = np.array([X[i] for i in loop])
    n = len(P)
    Q, inf = inner_loop(P, depth)
    if inf["inverted_left"]:
        return None
    E = np.roll(P, -1, 0) - P
    L = np.linalg.norm(E, axis=1)
    D = E / L[:, None]
    Dp = np.roll(D, 1, 0)
    turn = np.abs(np.degrees(np.arcsin(np.clip(Dp[:, 0] * D[:, 1] - Dp[:, 1] * D[:, 0], -1, 1))))
    cands = sorted((L[i] + L[(i + 1) % n] + L[(i + 2) % n], i) for i in range(n)
                   if turn[(i + 1) % n] < max_turn and turn[(i + 2) % n] < max_turn and
                   L[i] + L[(i + 1) % n] + L[(i + 2) % n] <= lmax)
    used, groups = set(), {}
    for tot, i in cands:
        segs = {i, (i + 1) % n, (i + 2) % n}
        if segs & used:
            continue
        a, b, c, d = i, (i + 1) % n, (i + 2) % n, (i + 3) % n
        if np.linalg.norm(Q[d] - Q[a]) > lmax:
            continue
        m1, m2 = 0.5 * (P[b] + Q[b]), 0.5 * (P[c] + Q[c])
        quads = [(P[a], P[b], m1, Q[a]), (P[b], P[c], m2, m1), (P[c], P[d], Q[d], m2), (Q[a], m1, m2, Q[d])]
        if all(_convex(q) for q in quads):
            used |= segs
            groups[i] = (m1, m2)
    if not groups:
        return None
    skip = {(i + 1) % n for i in groups} | {(i + 2) % n for i in groups}
    kept = [i for i in range(n) if i not in skip]
    # 1:3 transition where a kept segment's inner edge would exceed the side limit (concave corners grow edges)
    split = {}
    for i in range(n):
        j = (i + 1) % n
        if i in used or np.linalg.norm(Q[j] - Q[i]) <= MAX_EDGE_M:
            continue
        g, h = Q[i] + (Q[j] - Q[i]) / 3, Q[i] + 2 * (Q[j] - Q[i]) / 3
        m1, m2 = 0.5 * (P[i] + (P[j] - P[i]) / 3 + g), 0.5 * (P[i] + 2 * (P[j] - P[i]) / 3 + h)
        quads = [(P[i], P[j], m2, m1), (P[i], m1, g, Q[i]), (m1, m2, h, g), (m2, P[j], Q[j], h)]
        if not all(_convex(q) for q in quads):
            return None
        split[i] = (g, h, m1, m2)
    x_start = len(X)
    qid = {}
    for i in kept:                                     # inner points < 1.2 cm apart are one vertex
        prev = qid.get(kept[kept.index(i) - 1]) if qid else None
        if prev is not None and np.linalg.norm(X[prev] - Q[i]) < 0.012:
            qid[i] = prev
            continue
        X.append(Q[i].copy())
        qid[i] = len(X) - 1
    if len(kept) > 1 and qid[kept[-1]] != qid[kept[0]] and np.linalg.norm(X[qid[kept[-1]]] - X[qid[kept[0]]]) < 0.012:
        last = qid[kept[-1]]
        for i in kept:
            if qid[i] == last:
                qid[i] = qid[kept[0]]
    sid = {}
    for i, pts in split.items():
        sid[i] = []
        for p in pts:
            X.append(p)
            sid[i].append(len(X) - 1)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        if i in split:
            g, h, m1, m2 = sid[i]
            a, b, e, f = loop[i], loop[j], qid[i], qid[j]
            faces += [(a, b, m2, m1), (a, m1, g, e), (m1, m2, h, g), (m2, b, f, h)]
        elif i in groups:
            X.append(groups[i][0])
            X.append(groups[i][1])
            m1, m2 = len(X) - 2, len(X) - 1
            a, b, c, d = loop[i], loop[j], loop[(i + 2) % n], loop[(i + 3) % n]
            e, f = qid[i], qid[(i + 3) % n]
            faces += [(a, b, m1, e), (b, c, m2, m1), (c, d, f, m2), (e, m1, m2, f)]
        elif i not in used:
            faces.append((loop[i], loop[j], qid[j], qid[i]))
    faces = [_dedup(f) for f in faces]
    faces = [f for f in faces if len(f) >= 3]
    concave = sum(1 for f in faces if len(f) == 4 and not _convex([X[k] for k in f]))
    new_loop = []
    for i in range(n):
        if i in qid:
            new_loop.append(qid[i])
        if i in split:
            new_loop += sid[i][:2]
    new_loop = _dedup(new_loop)
    if len(inf["collapsed_edges"]) > 3 or not _simple_ccw(np.array([X[k] for k in new_loop])):
        del X[x_start:]
        return None                                    # strip would fold: stop paving, fill the rest
    return new_loop, faces, dict(depth=depth, loop_in=n, loop_out=len(new_loop), transitions=len(groups), splits=len(split),
                                 quads=sum(1 for f in faces if len(f) == 4), triangles=sum(1 for f in faces if len(f) == 3),
                                 concave=concave, collapsed_edges=len(inf["collapsed_edges"]))


def _simple_ccw(poly):
    """True for a simple counter-clockwise polygon (no two non-adjacent edges intersect)."""
    n = len(poly)
    if n < 3 or 0.5 * np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1]) <= 0:
        return False
    A, B = poly, np.roll(poly, -1, 0)
    cr = lambda o, a, b: (a[..., 0] - o[..., 0]) * (b[..., 1] - o[..., 1]) - (a[..., 1] - o[..., 1]) * (b[..., 0] - o[..., 0])
    for i in range(n):
        j = np.arange(i + 2, n if i > 0 else n - 1)
        if not len(j):
            continue
        d1, d2 = cr(A[i], B[i], A[j]), cr(A[i], B[i], B[j])
        d3, d4 = cr(A[j], B[j], A[i][None]), cr(A[j], B[j], B[i][None])
        if np.any((d1 * d2 < 0) & (d3 * d4 < 0)):
            return False
    return True


def _dedup(ids):
    """Drop cyclically repeated consecutive ids."""
    out = []
    for i in ids:
        if not out or out[-1] != i:
            out.append(i)
    while len(out) > 1 and out[-1] == out[0]:
        out.pop()
    return tuple(out) if isinstance(ids, tuple) else out


# ------------------------------------------------------------------------------------------------ entry
def build(cfg):
    cfg = dict(DEFAULTS, **cfg)
    for key in ("body_script", "typical_json", "bend_json", "soffit_json", "source_npz_dir"):
        cfg[key] = _abs(cfg, key)
    coll = bpy.data.collections.get(cfg["collection"])
    if coll is None:
        raise ValueError(f"collection {cfg['collection']} not found")
    existing = [n for n in PART_NAMES if n in bpy.data.objects]
    if existing:
        if not cfg["replace"]:
            raise ValueError(f"objects exist: {existing}; pass replace=True to rebuild them")
        for n in existing:
            ob = bpy.data.objects[n]
            me = ob.data
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
    ns = _ns(cfg)
    body, glass = bpy.data.objects[cfg["body_name"]], bpy.data.objects[cfg["glass_name"]]
    fins = [o for o in bpy.data.objects if o.name.startswith(cfg["fin_prefix"]) and o.type == "MESH"]
    attach = [bpy.data.objects[n] for n in cfg["attach_names"] if n in bpy.data.objects]
    caster = Caster(ns, [_bvh([o]) for o in attach] + ([_bvh(fins)] if fins else []))
    src = load_src(cfg, "RC_TOW_02", ns["LOCAL_ANGLE_DEG"])
    info = dict(fins_in_scene=len(fins), attach=[o.name for o in attach], ac=build_ac(cfg, ns, src, caster, coll))
    info["balconies"] = dict(built=False, reason="bend-zone balconies are the AC units of (a) (basket + railing)",
                             **balconies_vs_units(cfg))
    info["louvre"] = build_louvre(cfg, ns, src, caster, coll)
    info["soffit"] = build_soffit(cfg, ns, body, coll)
    return info
