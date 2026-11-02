"""ground-terrain variant `bgrid` in factory Blender (bpy + mathutils): regular grid, plan cut, relief raycast.

Pattern: new-case: Ground surface as a Blender grid projected onto a mathutils CDT relief (#733).

    blender --background --factory-startup --python-exit-code 1 \\
        --python tools/methods/ground/build_grid_blender.py -- <prep.json> <mesh_local.json>

prep.json (written by build_variant.py, local metres around an origin so float32 keeps millimetres):
{"cell": c, "rings": [[[x, y], ...], ...], "relief": [[x, y, z], ...]}.
Steps: a cell x cell grid over the plan bbox (anchored on floor(min / cell)); a quad is kept when its centre is
inside the plan rings (even-odd; the plan holes and the boundary are therefore cut on the grid, stair-stepped);
loose vertices removed, quads triangulated (BEAUTY); relief = mathutils.geometry.delaunay_2d_cdt over the
elevation points; every vertex Z by a downward BVH raycast on that relief; a miss takes the nearest relief
point's Z (KDTree, XY) and is counted. Writes {"verts", "faces", "misses", ...} in local coordinates.
"""
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_variants import inside_even_odd  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) != 2:
    raise SystemExit("usage: ... -- <prep.json> <mesh_local.json>")
src, out = Path(args[0]).resolve(), Path(args[1]).resolve()
if src == out:
    raise SystemExit("output aliases the input")
t0 = time.perf_counter()
prep = json.loads(src.read_text(encoding="utf-8"))
cell = float(prep["cell"])
if not math.isfinite(cell) or cell <= 0:
    raise SystemExit(f"bad cell {cell!r}")
rings = prep["rings"]
pts = np.concatenate([np.asarray(r, float).reshape(-1, 2) for r in rings])
x0, y0 = math.floor(pts[:, 0].min() / cell) * cell, math.floor(pts[:, 1].min() / cell) * cell
nx, ny = math.ceil((pts[:, 0].max() - x0) / cell), math.ceil((pts[:, 1].max() - y0) / cell)
gi, gj = np.meshgrid(np.arange(nx), np.arange(ny))
gi, gj = gi.ravel(), gj.ravel()
centres = np.stack([x0 + (gi + 0.5) * cell, y0 + (gj + 0.5) * cell], axis=1)
keep = inside_even_odd(centres, rings)
w = nx + 1
quads = [(j * w + i, j * w + i + 1, (j + 1) * w + i + 1, (j + 1) * w + i) for i, j in zip(gi[keep], gj[keep])]
grid = [(x0 + i * cell, y0 + j * cell, 0.0) for j in range(ny + 1) for i in range(nx + 1)]

bpy.ops.wm.read_factory_settings(use_empty=True)
me = bpy.data.meshes.new("grid")
me.from_pydata(grid, [], quads)
bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")

relief = np.asarray(prep["relief"], float).reshape(-1, 3)
cdt = delaunay_2d_cdt([Vector((x, y)) for x, y, _ in relief], [], [], 0, 1e-6)
rv, rf, rorig = cdt[0], cdt[2], cdt[3]
rz = [float(relief[o[0], 2]) if o else math.nan for o in rorig]
rverts = [Vector((v.x, v.y, z)) for v, z in zip(rv, rz)]
bvh = BVHTree.FromPolygons(rverts, [tuple(f) for f in rf])
kd = KDTree(len(relief))
for i, (x, y, _) in enumerate(relief):
    kd.insert(Vector((x, y, 0.0)), i)
kd.balance()
top = float(relief[:, 2].max()) + 100.0
misses = 0
for v in bm.verts:
    loc, _, _, _ = bvh.ray_cast(Vector((v.co.x, v.co.y, top)), Vector((0.0, 0.0, -1.0)))
    if loc is None:
        _, idx, _ = kd.find(Vector((v.co.x, v.co.y, 0.0)))
        v.co.z = float(relief[idx, 2])
        misses += 1
    else:
        v.co.z = loc.z
bm.verts.index_update()
verts = [[v.co.x, v.co.y, v.co.z] for v in bm.verts]
faces = [[v.index for v in f.verts] for f in bm.faces]
report = {"cell": cell, "grid_cells": int(nx * ny), "cells_kept": int(keep.sum()), "relief_points": len(relief),
          "relief_triangles": len(rf), "relief_misses": misses, "blender": bpy.app.version_string,
          "seconds": round(time.perf_counter() - t0, 3)}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"verts": verts, "faces": faces, "report": report}), encoding="utf-8")
print("GROUND_BGRID", json.dumps(report))
