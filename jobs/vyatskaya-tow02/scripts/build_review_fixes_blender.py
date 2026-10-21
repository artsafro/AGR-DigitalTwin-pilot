"""TOW02 review fixes (user 2026-10-21) on the mid-poly master: AC basket coping/posts/glass shell, louvre, roof boxes,
dark ledge 72.2 (runs inside Blender, headless).

Engine gap: EG6 (panelised curtain-wall source: parts built from measurements, docs/backlog.md).

    blender -b outputs/build-v013/tow02_master.blend --python scripts/build_review_fixes_blender.py -- <out_dir> [box_mode]

Saves ONLY <out_dir>/tow02_master.blend (save_as, never over the input) and <out_dir>/review_fixes_info.json.
Inputs (measured, outputs/review-v001/decor/): basket_source_units_measured.json (per AC unit: origin_local, u_dir_deg,
coping_u_extent -> unit frame u along the wall, v = perp(u) outward, v = 0 wall face, h = half width) and the spec
decor_spec_proposal.json. Coordinates are building-local (rotation 56.7 deg, scripts/build_body_blender.py to_world).
Not touched: TOW02_body, TOW02_body_glass, TOW02_top_glass, fins, source objects, helper empties.

1. AC baskets (37 units)
   - TOW02_ac_coping (new object, material TOW02_ac_coping #303031): coping = closed 4-quad section (top, bottom, outer,
     inner) swept along the measured outer/inner lines (#215), z0+1.200 .. z0+1.250, 7 segments per unit, stub ends
     `wall_embed_m` inside the wall (ray cast to TOW02_body), no end caps. Posts = 4 per unit at the 4 bends (measured
     quads, #215), side quads only, z0-0.005 .. z0+1.205 (5 mm into floor and coping). Posts are a separate element (not
     welded to the coping: their top sits 5 mm inside it).
     Overlap rules (user 2026-10-21, xView Overlapping Faces 5 mm / Vertices 2 mm): the coping outer line is offset
     `coping_out_m` (7 mm) outward, so the glass top embedded in the coping is 7 mm off its outer face (F5); every post
     edge parallel (< 5 deg) to the glass outer / inner face or to the coping inner line is moved into the post until
     it is >= `post_clear_m` (7 mm) from it (F3, F4, V4: the glass runs through the post, posts stay behind the glass
     outer face and inside the coping outline). Built after the glass shell, which gives the glass lines.
   - TOW02_ac_railing_glass (rebuilt in place): the existing outer planes (one polyline per unit) keep their plan
     position; top raised to z0+1.205 (5 mm into the coping), bottom lowered to z0-0.005 (5 mm into the floor);
     an inner face set `glass_t_m` = 0.020 inward (mitred offset; source 0.030 front / 0.015 sides, within 1 cm).
     No top, bottom, end or stub caps (stubs keep their 12 mm embed into the wall).
     Our glass is continuous through the bends, so there are no end caps at the posts.
2. Louvre (E recess, #216), object TOW02_louvre rebuilt in place, TOW02_louvre_plates deleted. Frame: c0 local
   (376.870, 185.218), s along the mouth, d into the recess. Mouth offset per storey zone (spec). Elements, each its
   own vertex set (no welding between elements):
   - blades 0.051 x 0.268, s0 = -1.0984 + 0.15332 k (k 0..14; top storey 64.7-69.317 +0.0027 and two extra 0.0417
     blades at 1.1949 / 1.3199), one box per blade per storey from rail top - 0.01 to next rail bottom + 0.01, 4 side
     quads (ends inside the rails), split < 3.8 m. Blades inside a fin stay there (as in the source).
   - crossbars 18 (bottom = slab top - 0.848), 0.048 high, d +-(0.134 + proud_m) (proud_m = 7 mm: faces >= 6 mm from
     the blade faces, xView Overlapping Faces 5 mm, F2), ends `embed_m` into the side walls (ray cast to body/top;
     fins ignored), 4 quads, blades pass through.
   - rails 0.183 high at 19 levels (bottom = slab top - 0.700), one per blade, width blade + 2 x proud_m (blade ends
     inside the rail, rail sides 7 mm proud, F1), front cap proud_m in front of the mouth face, back end `embed_m`
     into the back wall (ray cast, deepest hit over the rail width), top/bottom/sides split < 3.8 m, no back cap.
   Elements lying wholly inside our wall (beyond the ray hit) are dropped and reported.
3. Roof boxes (TOW02_top faces tow02_part 9). Measured: RC_TOW_02 box = walls 76.25-79.25 with a 0.25 m rim at 79.25,
   open top; SLAB_TOW_02 roof slab 78.45-78.75 (#194, light) inside the rim -> the source box is hollow with a 0.5 m
   upstand, like ours. box_mode "material" (default): geometry kept, the box roof faces at 78.75 get TOW02_shaft_cap
   (#a3a3a3). box_mode "close": inner walls, rim and the 78.75 roof are removed and the outer ring is capped at the
   wall top 79.25 (TOW02_shaft_cap) - only on the user's word, it departs from the source.
4. Ledge 72.2 between the band 71.5-72.2 and the upper volume: present in the source (#210 horizontal at 72.2, dark;
   walls above/below match ours median 2-3 mm) -> geometry kept, its up faces (tow02_part 5, z 72.2) get
   TOW02_ledge_dark (#303031).
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

MAX_SIDE_M = 3.8


def _job_dir():
    f = globals().get("__file__")
    if f:
        return os.path.dirname(os.path.dirname(os.path.abspath(f)))
    return os.getcwd()


JOB = _job_dir()
CFG = dict(
    body_script=os.path.join(JOB, "scripts", "build_body_blender.py"),
    units_json=os.path.join(JOB, "outputs", "review-v001", "decor", "basket_source_units_measured.json"),
    wall_embed_m=0.010,      # coping stubs into the wall
    embed_m=0.012,           # louvre crossbar / rail ends into the walls
    glass_t_m=0.020,         # glass shell thickness (inward)
    glass_top_dz=1.205,      # glass top above the basket floor (5 mm into the coping)
    glass_bottom_dz=-0.005,  # glass bottom 5 mm into the basket floor (no edge lying on the floor outline)
    coping_z=(1.200, 1.250),
    post_z=(-0.005, 1.205),
    proud_m=0.007,           # rails / crossbars proud of the blade faces (>= 6 mm: xView Overlapping Faces 5 mm)
    coping_out_m=0.007,      # AC coping outer line moved out of the glass outer face (F5)
    post_clear_m=0.007,      # AC post faces from parallel glass / coping faces (F3, F4, V4)
    box_mode="material",
)
SRGB = lambda h: (int(h[1:3], 16) / 255, int(h[3:5], 16) / 255, int(h[5:7], 16) / 255, 1.0)
UP = Vector((0, 0, 1))
H = {}


def load_helpers():
    ns = {"__name__": "tow02_body_helpers", "__file__": CFG["body_script"]}
    exec(compile(open(CFG["body_script"], encoding="utf-8").read(), CFG["body_script"], "exec"), ns)
    H.update(ns)


def W(x, y, z):
    return H["to_world"](x, y, z)


def mat(name, hexcol):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = SRGB(hexcol)
    return m


def slot(ob, m):
    for i, s in enumerate(ob.data.materials):
        if s is not None and s.name == m.name:
            return i
    ob.data.materials.append(m)
    return len(ob.data.materials) - 1


def bvh_of(names):
    verts, polys = [], []
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is None:
            continue
        mw = ob.matrix_world
        off = len(verts)
        verts += [mw @ v.co for v in ob.data.vertices]
        polys += [tuple(off + i for i in p.vertices) for p in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0)


def ray(bvh, p_loc, d_loc, maxd):
    """Distance along local direction d from local point p to the first hit, or None."""
    o = W(*p_loc)
    dv = (W(d_loc[0], d_loc[1], 0.0)).normalized()
    loc, nrm, idx, dist = bvh.ray_cast(o, dv, maxd)
    return dist


class Parts:
    """bmesh where every element has its own vertices; quads oriented by a wanted normal (world)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.n = 0

    def v(self, p_loc):
        return self.bm.verts.new(W(*p_loc))

    def quad(self, vs, want=None, mat_index=0):
        f = self.bm.faces.new(vs)
        f.material_index = mat_index
        if want is not None:
            f.normal_update()
            if f.normal.dot(want) < 0:
                f.normal_flip()
        self.n += 1
        return f


def splits(a, b, maxs=MAX_SIDE_M):
    n = max(1, math.ceil((b - a) / maxs - 1e-9))
    return [a + (b - a) * i / n for i in range(n + 1)]


# ------------------------------------------------------------------------------------------------ 1. AC baskets
def unit_frames():
    out = []
    for k, u in enumerate(json.load(open(CFG["units_json"], encoding="utf-8"))):
        a = math.radians(u["u_dir_deg"])
        uu = np.array([math.cos(a), math.sin(a)])
        vv = np.array([-uu[1], uu[0]])
        o = np.array(u["origin_local"])
        if (np.array(u["centre_xy"]) - o) @ vv < 0:
            vv = -vv
        h = float(u["coping_u_extent"][1]) + 0.020
        out.append(dict(i=k, o=o, u=uu, v=vv, h=h, z0=float(u["zt"])))
    return out


def coping_lines(h, v_end):
    """Left half (wall -> axis) of the outer / inner coping lines and the left post quads, (u, v)."""
    outer = [(-(h - 0.020), v_end), (-(h - 0.023), 0.229), (-(h - 0.258), 1.0565), (-(h - 0.3234), 1.127)]
    inner = [(-(h - 0.085), v_end), (-(h - 0.0875), 0.198), (-(h - 0.301), 0.955), (-(h - 0.351), 1.0093)]
    posts = [[(-(h - 0.258), 1.0565), (-(h - 0.294), 1.0996), (-(h - 0.324), 0.9845), (-(h - 0.301), 0.9554)],
             [(-(h - 0.023), 0.229), (-(h - 0.038), 0.2865), (-(h - 0.0953), 0.2282), (-(h - 0.0875), 0.1984)]]
    return outer, inner, posts


def full(half):
    """Left half + mirrored right half (u -> -u), wall to wall."""
    return half + [(-u, v) for u, v in reversed(half)]


def offset_line(P, t):
    """Mitred offset of an open (u, v) polyline by t away from the unit axis point (0, 0.5)."""
    P = [np.array(p, float) for p in P]
    ctr = np.array([0.0, 0.5])
    n = []
    for a, b in zip(P[:-1], P[1:]):
        d = (b - a) / np.linalg.norm(b - a)
        m = np.array([d[1], -d[0]])
        n.append(m if m @ (0.5 * (a + b) - ctr) > 0 else -m)
    out = []
    for j, p in enumerate(P):
        if j == 0:
            out.append(p + n[0] * t)
        elif j == len(P) - 1:
            out.append(p + n[-1] * t)
        else:
            out.append(p + (n[j - 1] + n[j]) * (t / (1.0 + n[j - 1] @ n[j])))
    return [tuple(p) for p in out]


def clear_post(q, refs, clear, par_deg=8.0):
    """Move every edge of the post quad q (u, v) into the post until it is >= clear from every near-parallel reference
    segment whose span overlaps it (xView Overlapping Faces 5 mm). Returns the new quad and the moves (mm)."""
    Q = [np.array(p, float) for p in q]
    c = sum(Q) / 4
    lines, moves = [], []
    segs = [(np.array(a, float), np.array(b, float)) for R in refs for a, b in zip(R[:-1], R[1:])]
    cosmin = math.cos(math.radians(par_deg))
    for k in range(4):
        a, b = Q[k], Q[(k + 1) % 4]
        d = (b - a) / np.linalg.norm(b - a)
        n_in = np.array([-d[1], d[0]])
        if n_in @ (c - a) < 0:
            n_in = -n_in
        ds = []
        for p0, p1 in segs:
            e = p1 - p0
            L = np.linalg.norm(e)
            if L < 1e-6 or abs((e / L) @ d) < cosmin:
                continue
            t = sorted(((p0 - a) @ d, (p1 - a) @ d))
            if t[1] < 0.0 or t[0] > np.linalg.norm(b - a):   # no common span along the edge
                continue
            mid = 0.5 * (a + b)
            foot = p0 + (e / L) * ((mid - p0) @ (e / L))
            ds.append(float((foot - mid) @ n_in))              # reference line at the edge middle, + = inside the post
        m = 0.0
        while any(abs(x - m) < clear for x in ds) and m < 0.05:
            m += 0.0005
        lines.append((a + n_in * m, d))
        moves.append(round(m * 1000, 1))
    out = []
    for k in range(4):
        (p, d), (r, e) = lines[k - 1], lines[k]
        A = np.array([[d[0], -e[0]], [d[1], -e[1]]])
        s_ = np.linalg.solve(A, r - p)
        out.append(tuple(p + d * s_[0]))
    return out, moves


def build_coping(units, body_bvh, info):
    C, P = Parts(), Parts()
    rep = []
    for un in units:
        o, uu, vv, h, z0 = un["o"], un["u"], un["v"], un["h"], un["z0"]
        L = lambda u, v: o + uu * u + vv * v
        # wall position at the coping stubs: ray from v = 0.1 back along -v
        zc = z0 + 1.225
        walls = []
        for su in (-1, 1):
            for uo in (h - 0.020, h - 0.085):
                p = L(su * uo, 0.1)
                d = ray(body_bvh, (p[0], p[1], zc), (-vv[0], -vv[1]), 0.5)
                walls.append(None if d is None else 0.1 - d)
        found = [w for w in walls if w is not None]
        v_end = (min(found) if found else 0.0) - CFG["wall_embed_m"]
        outer, inner, posts = coping_lines(h, v_end)
        O0, I = full(outer), full(inner)
        O = offset_line(O0, CFG["coping_out_m"])
        refs = un.get("glass_lines", [O0]) + [I]
        za, zb = z0 + CFG["coping_z"][0], z0 + CFG["coping_z"][1]
        cv = lambda q, z: C.v((L(*q)[0], L(*q)[1], z))
        Ob, Ot = [cv(q, za) for q in O], [cv(q, zb) for q in O]
        Ib, It = [cv(q, za) for q in I], [cv(q, zb) for q in I]
        ctr = L(0.0, 0.5)
        nq = 0
        for i in range(len(O) - 1):
            out2 = 0.5 * (L(*O[i]) + L(*O[i + 1])) - ctr
            C.quad((Ot[i], Ot[i + 1], It[i + 1], It[i]), UP)
            C.quad((Ob[i], Ob[i + 1], Ib[i + 1], Ib[i]), -UP)
            seg = L(*O[i + 1]) - L(*O[i])
            n2 = np.array([seg[1], -seg[0]])
            n2 = n2 if n2 @ out2 > 0 else -n2
            C.quad((Ob[i], Ob[i + 1], Ot[i + 1], Ot[i]), W(n2[0], n2[1], 0))
            C.quad((Ib[i], Ib[i + 1], It[i + 1], It[i]), -W(n2[0], n2[1], 0))
            nq += 4
        np_ = 0
        pa, pb = z0 + CFG["post_z"][0], z0 + CFG["post_z"][1]
        moved = []
        for q in posts + [[(-u, v) for u, v in reversed(pq)] for pq in posts]:
            q, m = clear_post(q, refs, CFG["post_clear_m"])
            moved.append(m)
            Q = [L(*x) for x in q]
            c = sum(Q) / 4
            vb = [P.v((x[0], x[1], pa)) for x in Q]
            vt = [P.v((x[0], x[1], pb)) for x in Q]
            for i in range(4):
                j = (i + 1) % 4
                m2 = 0.5 * (Q[i] + Q[j]) - c
                P.quad((vb[i], vb[j], vt[j], vt[i]), W(m2[0], m2[1], 0))
                np_ += 1
        rep.append(dict(unit=un["i"], h=round(h, 4), z0=z0, v_end=round(v_end, 4),
                        wall_v=[None if w is None else round(w, 4) for w in walls], coping_quads=nq, post_quads=np_,
                        post_edge_moves_mm=moved))
    me_p = bpy.data.meshes.new("tmp_posts")
    P.bm.to_mesh(me_p)
    P.bm.free()
    C.bm.from_mesh(me_p)
    bpy.data.meshes.remove(me_p)
    coll = bpy.data.objects["TOW02_ac_railing_glass"].users_collection[0]
    ob = H["_to_object"](C.bm, "TOW02_ac_coping", coll)
    ob.data.materials.append(mat("TOW02_ac_coping", "#303031"))
    info["ac_coping"] = dict(faces=len(ob.data.polygons), per_unit=rep)


def glass_components(ob):
    me = ob.data
    adj = {}
    for e in me.edges:
        a, b = e.vertices
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, comps = set(), []
    for s in range(len(me.vertices)):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj.get(x, []):
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        comps.append(comp)
    return comps, adj


def build_glass(units, info):
    ob = bpy.data.objects["TOW02_ac_railing_glass"]
    me = ob.data
    mw = ob.matrix_world
    co = [mw @ v.co for v in me.vertices]
    comps, adj = glass_components(ob)
    a = math.radians(H["LOCAL_ANGLE_DEG"])
    to_loc = lambda p: np.array([p.x * math.cos(a) + p.y * math.sin(a), -p.x * math.sin(a) + p.y * math.cos(a)])
    bm = bmesh.new()
    t = CFG["glass_t_m"]
    rep = []
    for comp in comps:
        zmin = min(co[i].z for i in comp)
        bot = [i for i in comp if abs(co[i].z - zmin) < 1e-4]
        bset = set(bot)
        badj = {i: [j for j in adj[i] if j in bset] for i in bot}
        ends = [i for i in bot if len(badj[i]) == 1]
        chain, prev = [ends[0]], None
        while len(chain) < len(bot):
            nx = [j for j in badj[chain[-1]] if j != prev]
            prev = chain[-1]
            chain.append(nx[0])
        pts = [Vector((co[i].x, co[i].y)) for i in chain]
        cl = to_loc(sum(pts, Vector((0, 0))) / len(pts))
        same = [u for u in units if abs(u["z0"] - zmin) < 0.05]        # units are stacked: match the level first
        un = min(same, key=lambda u: np.linalg.norm(u["o"] + u["v"] * 0.73 - cl))
        cw = W(*(un["o"] + un["v"] * 0.5), 0.0)
        ctr = Vector((cw.x, cw.y))
        z0, z1 = un["z0"] + CFG["glass_bottom_dz"], un["z0"] + CFG["glass_top_dz"]
        n = []
        for i in range(len(pts) - 1):
            d = (pts[i + 1] - pts[i]).normalized()
            m = Vector((d.y, -d.x))
            if m.dot(0.5 * (pts[i] + pts[i + 1]) - ctr) < 0:
                m = -m
            n.append(m)
        inner = []
        for j, p in enumerate(pts):
            if j == 0:
                q = p - n[0] * t
            elif j == len(pts) - 1:
                q = p - n[-1] * t
            else:
                na, nb = n[j - 1], n[j]
                q = p - (na + nb) * (t / (1.0 + na.dot(nb)))
            inner.append(q)
        for ring, sgn in ((pts, 1), (inner, -1)):
            vb = [bm.verts.new((p.x, p.y, z0)) for p in ring]
            vt = [bm.verts.new((p.x, p.y, z1)) for p in ring]
            for i in range(len(ring) - 1):
                f = bm.faces.new((vb[i], vb[i + 1], vt[i + 1], vt[i]))
                f.normal_update()
                want = Vector((n[i].x, n[i].y, 0)) * sgn
                if f.normal.dot(want) < 0:
                    f.normal_flip()
        to_uv = lambda q: tuple(((to_loc(q) - un["o"]) @ un["u"], (to_loc(q) - un["o"]) @ un["v"]))
        un["glass_lines"] = [[to_uv(q) for q in pts], [to_uv(q) for q in inner]]
        rep.append(dict(unit=un["i"], segments=len(pts) - 1, z=[round(z0, 3), round(z1, 3)],
                        unit_match_m=round(float(np.linalg.norm(un["o"] + un["v"] * 0.73 - cl)), 3)))
    before = len(me.polygons)
    bm.to_mesh(me)
    bm.free()
    me.update()
    info["ac_glass"] = dict(faces_before=before, faces=len(me.polygons), units=len(comps), per_unit=rep)


# ------------------------------------------------------------------------------------------------ 2. louvre
C0 = np.array([376.870, 185.218])
SD = np.array([-0.0924, 0.9957])
DD = np.array([-0.9957, -0.0924])
ZONES = [(6.9, 10.3, 2.425), (10.3, 13.7, 2.275), (13.7, 17.1, 2.010), (17.1, 23.9, 1.350), (23.9, 30.7, 0.750),
         (30.7, 99.0, 0.0)]
RAIL_H, CROSS_H, BLADE_W, BLADE_D = 0.183, 0.048, 0.0511, 0.268


def zone_off(z):
    return next(off for a, b, off in ZONES if a - 1e-6 <= z < b - 1e-6)


def blade_cols(top):
    """[(s0, s1)] of the blades of a storey (top = the screen 64.7-69.317)."""
    sh = 0.0027 if top else 0.0
    cols = [(-1.0984 + 0.15332 * k + sh, -1.0984 + 0.15332 * k + sh + BLADE_W) for k in range(15)]
    if top:
        cols += [(1.1949, 1.2366), (1.3199, 1.3616)]
    return cols


def build_louvre(info):
    for n in ("TOW02_louvre_plates",):
        ob = bpy.data.objects.get(n)
        if ob is not None:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
    walls = bvh_of(["TOW02_body", "TOW02_top", "TOW02_soffit"])
    E, pr = CFG["embed_m"], CFG["proud_m"]
    B = Parts()
    P = lambda s, d, z: (C0[0] + SD[0] * s + DD[0] * d, C0[1] + SD[1] * s + DD[1] * d, z)
    ws, wd = W(SD[0], SD[1], 0), W(DD[0], DD[1], 0)
    rails_z = [round(6.9 + 3.4 * i, 3) for i in range(18)] + [69.317]
    cross_z = [round(10.152 + 3.4 * i, 3) for i in range(17)] + [67.952]
    rep = dict(blades=[], crossbars=[], rails=[], dropped=[])

    def side_hits(z, d):
        hs = {}
        for sgn in (-1, 1):
            h = ray(walls, P(0.0, d, z), tuple(SD * sgn), 3.0)
            hs[sgn] = h
        return hs

    def box4(s0, s1, d0, d1, z0, z1, caps_sd=(), long_axis="z"):
        """Open box: the 4 faces parallel to long_axis ('z', 'd' or 's'), split < 3.8 m; caps listed in caps_sd."""
        if long_axis == "z":
            ring = lambda t: [B.v(P(s, d, t)) for s, d in ((s0, d0), (s1, d0), (s1, d1), (s0, d1))]
            wants, ts = (-wd, ws, wd, -ws), splits(z0, z1)
        elif long_axis == "s":
            ring = lambda t: [B.v(P(t, d, z)) for d, z in ((d0, z0), (d1, z0), (d1, z1), (d0, z1))]
            wants, ts = (-UP, wd, UP, -wd), splits(s0, s1)
        else:   # long along d
            ring = lambda t: [B.v(P(s, t, z)) for s, z in ((s0, z0), (s1, z0), (s1, z1), (s0, z1))]
            wants, ts = (-UP, ws, UP, -ws), splits(d0, d1)
        rings = [ring(t) for t in ts]                      # stations shared by consecutive segments
        for a, b in zip(rings[:-1], rings[1:]):
            for i, want in enumerate(wants):
                j = (i + 1) % 4
                B.quad((a[i], a[j], b[j], b[i]), want)
        if "front" in caps_sd:                             # cap at the first station (mouth end of a rail)
            B.quad(rings[0], -wd)

    # walls per level (side walls along s at the element height and zone d)
    def wall_s(z, d):
        hs = side_hits(z, d)
        return (-hs[-1] if hs[-1] is not None else None), (hs[1] if hs[1] is not None else None)

    # blades
    for k in range(len(rails_z) - 1):
        za, zb = rails_z[k] + RAIL_H - 0.01, rails_z[k + 1] + 0.01
        top = rails_z[k] >= 64.7 - 1e-6
        off = zone_off(rails_z[k] + 0.1)
        lo_w, hi_w = wall_s(0.5 * (za + zb), off)
        n = 0
        for s0, s1 in blade_cols(top):
            if (hi_w is not None and s0 >= hi_w) or (lo_w is not None and s1 <= lo_w):
                rep["dropped"].append(dict(kind="blade", z=[round(za, 3), round(zb, 3)], s=[s0, s1],
                                           wall=[lo_w and round(lo_w, 3), hi_w and round(hi_w, 3)]))
                continue
            box4(s0, s1, off - BLADE_D / 2, off + BLADE_D / 2, za, zb, long_axis="z")
            n += 1
        rep["blades"].append(dict(z=[round(za, 3), round(zb, 3)], d_off=off, count=n,
                                  walls_s=[lo_w and round(lo_w, 4), hi_w and round(hi_w, 4)]))
    # crossbars
    for zc in cross_z:
        off = zone_off(zc)
        lo_w, hi_w = wall_s(zc + CROSS_H / 2, off)
        s0 = (lo_w if lo_w is not None else -1.149) - E
        s1 = (hi_w if hi_w is not None else (1.401 if zc > 65 else 1.149)) + E
        box4(s0, s1, off - BLADE_D / 2 - pr, off + BLADE_D / 2 + pr, zc, zc + CROSS_H, long_axis="s")
        rep["crossbars"].append(dict(z=[zc, round(zc + CROSS_H, 3)], d_off=off, s=[round(s0, 4), round(s1, 4)],
                                     wall_hit=[lo_w is not None, hi_w is not None]))
    # rails
    for zr in rails_z:
        top = zr >= 64.7 - 1e-6
        off = zone_off(zr + 0.1)
        d0 = off - BLADE_D / 2 - pr
        lo_w, hi_w = wall_s(zr + RAIL_H / 2, off)
        n, ends = 0, []
        for s0, s1 in blade_cols(top):
            if (hi_w is not None and s0 >= hi_w) or (lo_w is not None and s1 <= lo_w):
                rep["dropped"].append(dict(kind="rail", z=zr, s=[s0, s1]))
                continue
            hits = [ray(walls, P(s, off, zr + RAIL_H / 2), tuple(DD), 9.0) for s in (s0 + 0.003, s1 - 0.003)]
            hits = [h for h in hits if h is not None]
            d1 = off + max(hits) + E if hits else 6.141
            box4(s0 - pr, s1 + pr, d0, d1, zr, zr + RAIL_H, caps_sd=("front",), long_axis="d")
            ends.append(round(d1, 3))
            n += 1
        rep["rails"].append(dict(z=[zr, round(zr + RAIL_H, 3)], d_off=off, count=n, d0=round(d0, 3),
                                 d1=[min(ends), max(ends)] if ends else None))
    ob = bpy.data.objects["TOW02_louvre"]
    me = ob.data
    before = len(me.polygons)
    B.bm.to_mesh(me)
    B.bm.free()
    me.update()
    rep.update(faces_before=before, faces=len(me.polygons))
    info["louvre"] = rep


# ------------------------------------------------------------------------------------------------ 3./4. TOW02_top
def fix_top(info):
    ob = bpy.data.objects["TOW02_top"]
    me = ob.data
    part = me.attributes["tow02_part"]
    i_cap = slot(ob, mat("TOW02_shaft_cap", "#a3a3a3"))
    i_led = slot(ob, mat("TOW02_ledge_dark", "#303031"))
    mw = ob.matrix_world
    nled = nbox = 0
    for p in me.polygons:
        if (mw.to_3x3() @ p.normal).z < 0.99:
            continue
        z = (mw @ p.center).z
        pv = part.data[p.index].value
        if pv == 5 and abs(z - 72.2) < 0.005:
            p.material_index = i_led
            nled += 1
        elif pv == 9 and abs(z - 78.75) < 0.005:
            p.material_index = i_cap
            nbox += 1
    rep = dict(ledge_faces=nled, box_roof_faces=nbox, box_mode=CFG["box_mode"])
    if CFG["box_mode"] == "close":
        rep.update(close_boxes(ob, i_cap))
    info["top"] = rep


def close_boxes(ob, i_cap):
    """Remove inner walls, rim and roof of the boxes; cap the outer ring at its top (quads)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.get("tow02_part")
    box = [f for f in bm.faces if f[lay] == 9]
    outer = [f for f in box if abs(f.normal.z) < 0.1 and min(v.co.z for v in f.verts) < 77.0]
    kill = [f for f in box if f not in outer]
    bmesh.ops.delete(bm, geom=kill, context="FACES_ONLY")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    ztop = max(v.co.z for f in outer for v in f.verts)
    edges = [e for e in bm.edges if e.is_boundary and all(abs(v.co.z - ztop) < 1e-4 for v in e.verts)
             and any(f in outer for f in e.link_faces)]
    res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    new = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
    bmesh.ops.join_triangles(bm, faces=new, angle_face_threshold=math.radians(5),
                             angle_shape_threshold=math.radians(180))
    caps = [f for f in bm.faces if f[lay] == 0 and abs(f.calc_center_median().z - ztop) < 1e-4]
    for f in caps:
        f[lay] = 9
        f.material_index = i_cap
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    out = dict(removed_faces=len(kill), cap_faces=len(caps), cap_z=round(ztop, 3),
               cap_triangles=sum(1 for f in caps if len(f.verts) == 3))
    bm.to_mesh(ob.data)
    bm.free()
    return out


# ------------------------------------------------------------------------------------------------ main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("usage: ... --python build_review_fixes_blender.py -- <out_dir> [box_mode]")
    out_dir = os.path.abspath(argv[0])
    if len(argv) > 1:
        CFG["box_mode"] = argv[1]
    src = os.path.abspath(bpy.data.filepath)
    out = os.path.join(out_dir, "tow02_master.blend")
    if os.path.normcase(out) == os.path.normcase(src) or os.path.exists(out):
        raise SystemExit(f"refusing to write {out}: input file or existing output")
    os.makedirs(out_dir, exist_ok=True)
    load_helpers()
    counts0 = {n: len(bpy.data.objects[n].data.polygons) for n in
               ("TOW02_ac_railing_glass", "TOW02_louvre", "TOW02_louvre_plates", "TOW02_top")}
    info = dict(input=src, cfg={k: v for k, v in CFG.items()}, faces_before=counts0)
    units = unit_frames()
    body_bvh = bvh_of(["TOW02_body"])
    build_glass(units, info)            # first: the post clearances use the glass lines
    build_coping(units, body_bvh, info)
    build_louvre(info)
    fix_top(info)
    bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=True, copy=False)
    json.dump(info, open(os.path.join(out_dir, "review_fixes_info.json"), "w", encoding="utf-8"), indent=1,
              default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    print("REVIEW_FIXES saved", out)
    print("REVIEW_FIXES faces", {k: info[k].get("faces") for k in ("ac_coping", "ac_glass", "louvre")},
          info["top"])


main()
