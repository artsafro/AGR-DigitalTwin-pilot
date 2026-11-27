"""Blender headless: orthographic ray-cast depth+normal maps of a model from N horizontal directions.

OBSERVE research harness #139 (view<->face). No saves, no exports of the model.
Usage: blender -b --factory-startup -P rays.py -- <model.fbx> <out.npz> <m_per_px> <az_deg,az_deg,...>
Direction az = outward facade normal azimuth in the model frame (0 = +X, 90 = +Y). Screen right = (-n) x Z.
UCX_/collision objects are skipped.
"""
import sys, math
import bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
src, out, res, azs = argv[0], argv[1], float(argv[2]), [float(a) for a in argv[3].split(",")]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
dg = bpy.context.evaluated_depsgraph_get()
verts, tris, names, tri_uv = [], [], [], []
for ob in bpy.context.scene.objects:
    if ob.type != "MESH" or ob.name.upper().startswith(("UCX_", "UBX_", "USP_", "UCP_", "COLIZ")):
        continue
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    off = len(verts)
    mw = ob.matrix_world
    verts += [tuple(mw @ v.co) for v in me.vertices]
    tris += [tuple(off + i for i in t.vertices) for t in me.loop_triangles]
    uvl = me.uv_layers.active
    for t in me.loop_triangles:  # R3: per-triangle UVs for texture sampling at hits
        tri_uv.append([tuple(uvl.data[li].uv) for li in t.loops] if uvl else [(np.nan, np.nan)] * 3)
    names.append(ob.name)
    if len(me.vertices):
        cv = np.array([tuple(mw @ v.co) for v in me.vertices])
        print("RAYS obj", ob.name, cv.min(0).round(2).tolist(), cv.max(0).round(2).tolist())
    ev.to_mesh_clear()
V = np.array(verts)
bvh = BVHTree.FromPolygons([Vector(v) for v in verts], tris)
lo, hi = V.min(0), V.max(0)
print("RAYS objects", len(names), "verts", len(V), "tris", len(tris), "bbox", lo.round(3).tolist(), hi.round(3).tolist())
result = {"bbox": np.array([lo, hi]), "res": np.array(res), "az": np.array(azs)}
# R3: UDIM diffuse set next to the model (T_*_Diffuse_*.<tile>.png), downscaled to 512 px per tile; none -> luma NaN
import glob, os, re as _re
TUV = np.array(tri_uv, float)
TV = np.array(tris, int)
tiles = {}
for pth in glob.glob(os.path.join(os.path.dirname(src), "*Diffuse*.1[0-9][0-9][0-9].png")):
    tiles[int(_re.search(r"\.(1\d{3})\.png$", pth).group(1))] = pth
print("RAYS tiles", len(tiles))
cache = {}


def luma_at(fi, loc):
    if not tiles or not np.isfinite(TUV[fi]).all():
        return np.nan
    a, b, c = (V[k] for k in TV[fi])
    p = np.array(loc)
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-12:
        return np.nan
    w1 = (d11 * d20 - d01 * d21) / den
    w2 = (d00 * d21 - d01 * d20) / den
    uv = (1 - w1 - w2) * TUV[fi][0] + w1 * TUV[fi][1] + w2 * TUV[fi][2]
    tile = 1001 + int(math.floor(uv[0])) + 10 * int(math.floor(uv[1]))
    if tile not in tiles:
        return np.nan
    if tile not in cache:
        im = bpy.data.images.load(tiles[tile])
        im.scale(512, 512)
        px = np.array(im.pixels[:], np.float32).reshape(512, 512, -1)
        cache[tile] = 0.299 * px[..., 0] + 0.587 * px[..., 1] + 0.114 * px[..., 2]
    fu, fv = uv[0] - math.floor(uv[0]), uv[1] - math.floor(uv[1])
    return float(cache[tile][min(511, int(fv * 512)), min(511, int(fu * 512))])
for az in azs:
    n = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0])
    right = np.cross(-n, [0, 0, 1.0])
    us = V @ right
    ds = V @ n
    u0, u1 = us.min(), us.max()
    z0, z1 = lo[2], hi[2]
    W, H = int(math.ceil((u1 - u0) / res)) + 1, int(math.ceil((z1 - z0) / res)) + 1
    depth = np.full((H, W), np.nan, np.float32)
    nrm = np.zeros((H, W, 3), np.float32)
    luma = np.full((H, W), np.nan, np.float32)
    start = ds.max() + 1.0
    d = Vector(tuple(-n))
    for j in range(H):
        z = z1 - (j + 0.5) * res
        for i in range(W):
            u = u0 + (i + 0.5) * res
            p = n * start + right * u
            hit = bvh.ray_cast(Vector((p[0], p[1], z)), d)
            if hit[0] is not None:
                depth[j, i] = hit[3]
                luma[j, i] = luma_at(hit[2], hit[0])
                nn = hit[1]
                if nn.dot(d) > 0:
                    nn = -nn
                nrm[j, i] = tuple(nn)
    key = f"az{int(round(az)) % 360:03d}"
    result[key + "_luma"] = luma
    result[key + "_depth"] = depth
    result[key + "_normal"] = nrm
    result[key + "_origin"] = np.array([u0, z1])
    print("RAYS", key, W, H, "hit%", round(float(np.isfinite(depth).mean() * 100), 1))
np.savez_compressed(out, **result)
print("RAYS saved", out)
