"""Blender headless: exterior wall table + window centres for #157 (OBSERVE, research only).

new-case: docs/research/autoresearch-view-face-signature/walls.py - #157 wall/window extraction

Frozen rules: ../autoresearch-view-face-signature.md ("Walls", "Windows"). No saves, no exports.
Usage: blender -b --factory-startup -P walls.py -- <model.fbx> <out.json> <fwd|rev>
"""
import json
import math
import re
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
src, out, order = argv[0], argv[1], argv[2]
SKIP = ("UCX_", "UBX_", "USP_", "UCP_", "COLIZ")
WIN = re.compile(r"окно|window|витраж", re.IGNORECASE)
NZ_MAX, MIN_AREA, PROBE, NICHE = 0.1, 0.02, 0.6, 2.0
AZ_BIN, D_GAP, U_GAP, MIN_WH = 2.0, 0.5, 0.5, 3.0

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
dg = bpy.context.evaluated_depsgraph_get()
objs = sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name)
if order == "rev":
    objs = objs[::-1]

verts, tris, windows = [], [], []
for ob in objs:
    if ob.name.upper().startswith(SKIP):
        continue
    mw = ob.matrix_world
    wv = [mw @ v.co for v in ob.data.vertices]
    if not wv or max(v.z for v in wv) > 30.0:
        continue
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    off = len(verts)
    verts += [tuple(mw @ v.co) for v in me.vertices]
    tris += [tuple(off + i for i in t.vertices) for t in me.loop_triangles]
    if WIN.search(ob.name):
        a = np.array([tuple(v) for v in wv])
        windows.append(((a.min(0) + a.max(0)) / 2).round(4).tolist())
    ev.to_mesh_clear()

V = np.array(verts, float)
T = np.array(tris, np.int64)
bvh = BVHTree.FromPolygons([Vector(v) for v in verts], [tuple(t) for t in tris])
p0, p1, p2 = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
cr = np.cross(p1 - p0, p2 - p0)
area = np.linalg.norm(cr, axis=1) / 2
nrm = cr / np.maximum(np.linalg.norm(cr, axis=1, keepdims=True), 1e-12)
cen = (p0 + p1 + p2) / 3
sel = np.where((np.abs(nrm[:, 2]) < NZ_MAX) & (area >= MIN_AREA))[0]
UP = Vector((0, 0, 1))


def exterior(c, s):
    if bvh.ray_cast(c + s * 0.001, s, PROBE)[0] is not None:
        return False
    return bvh.ray_cast(c + s * PROBE, UP, 1.0e4)[0] is None


rows = []  # (tri, sx, sy, cls)
for i in sel:
    n = Vector(nrm[i])
    n.z = 0.0
    n.normalize()
    c = Vector(cen[i])
    ext = [s for s in (n, -n) if exterior(c, s)]
    if len(ext) != 1:
        continue
    s = ext[0]
    hit = bvh.ray_cast(c + s * 0.02, s, 1.0e4)
    if hit[0] is None:
        cls = 0  # open
    elif hit[3] >= NICHE:
        cls = 1  # inner
    else:
        continue
    rows.append((int(i), s.x, s.y, cls))

walls = []
if rows:
    R = np.array(rows, float)
    ti, sx, sy, cls = R[:, 0].astype(np.int64), R[:, 1], R[:, 2], R[:, 3].astype(int)
    az = (np.round(np.degrees(np.arctan2(sy, sx)) / AZ_BIN) * AZ_BIN) % 360.0
    for a in sorted(set(az.tolist())):
        m = np.where(az == a)[0]
        sa = np.array([math.cos(math.radians(a)), math.sin(math.radians(a)), 0.0])
        ta = np.array([-sa[1], sa[0], 0.0])
        d = cen[ti[m]] @ sa
        o = np.argsort(d, kind="stable")
        groups, cur = [], [o[0]]
        for k in o[1:]:
            if d[k] - d[cur[-1]] > D_GAP:
                groups.append(cur)
                cur = []
            cur.append(k)
        groups.append(cur)
        for g in groups:
            g = m[np.array(g)]
            tv = T[ti[g]]
            u = V[tv] @ ta  # (n,3)
            z = V[tv][:, :, 2]
            u0, u1 = u.min(1), u.max(1)
            oo = np.argsort(u0, kind="stable")
            segs, cs = [], [oo[0]]
            hi = u1[oo[0]]
            for k in oo[1:]:
                if u0[k] - hi > U_GAP:
                    segs.append(cs)
                    cs = []
                cs.append(k)
                hi = max(hi, u1[k])
            segs.append(cs)
            for sg in segs:
                sg = np.array(sg)
                gg = g[sg]
                W = float(u1[sg].max() - u0[sg].min())
                H = float(z[sg].max() - z[sg].min())
                if W < MIN_WH or H < MIN_WH:
                    continue
                ar = area[ti[gg]]
                inner = float(ar[cls[gg] == 1].sum())
                dd = cen[ti[gg]] @ sa
                walls.append({
                    "az": a, "d0": round(float(dd.min()), 3), "d1": round(float(dd.max()), 3),
                    "u0": round(float(u0[sg].min()), 3), "u1": round(float(u1[sg].max()), 3),
                    "z0": round(float(z[sg].min()), 3), "z1": round(float(z[sg].max()), 3),
                    "W": round(W, 3), "H": round(H, 3), "area": round(float(ar.sum()), 2),
                    "cls": "inner" if inner > ar.sum() / 2 else "open", "tris": int(len(gg)),
                })

walls.sort(key=lambda w: (w["az"], w["d0"], w["u0"]))
json.dump({"src": src, "order": order, "tris": int(len(T)), "vertical_sel": int(len(sel)),
           "classified": len(rows), "windows": sorted(windows), "walls": walls},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
print("WALLS", len(walls), "inner", sum(w["cls"] == "inner" for w in walls), "windows", len(windows))
