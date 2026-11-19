"""Hook `before` stage `body` (#1619 training polygon): dump the Revit objects of one building, read-only.

Pattern: n/a | new-case: read-only Revit FBX crop for a typical-floor module (body training polygon).

blender -b --factory-startup --python revit_floor_dump.py -- SRC.(fbx|blend) OUT.npz X0,Y0,X1,Y1 [--save-blend COPY.blend]

Writes world-space triangles of every mesh object whose plan bbox lies inside the box (object centre inside
and bbox overlapping), with the object name and per-triangle material name. `--save-blend` keeps a .blend copy
of the whole imported source for fast re-reads (a new path; refused if it exists or equals the source).
Never saves over the source; refuses an output that resolves to the input.
"""
import os
import sys

import bmesh
import bpy
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]
src, out, box = args[0], args[1], [float(x) for x in args[2].split(",")]
save = args[args.index("--save-blend") + 1] if "--save-blend" in args else None
real = os.path.realpath
if not out.endswith(".npz") or real(out) == real(src) or (save and (real(save) == real(src) or os.path.exists(save))):
    sys.exit("refused: output must be a new .npz / .blend path, never the source")
if src.lower().endswith(".blend"):
    bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=save, copy=True)
x0, y0, x1, y1 = box
names, tri, obj_of_tri, mat_of_tri, mats = [], [], [], [], {}
for ob in bpy.context.scene.objects:
    if ob.type != "MESH" or not ob.data.polygons:
        continue
    mw = ob.matrix_world
    cs = [mw @ v.co for v in ob.data.vertices]
    xs = [c.x for c in cs]
    ys = [c.y for c in cs]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    if not (x0 <= cx <= x1 and y0 <= cy <= y1):
        continue
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(mw)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    slots = [m.name if m else "" for m in ob.data.materials]
    oi = len(names)
    names.append(ob.name)
    for f in bm.faces:
        tri.append([tuple(v.co) for v in f.verts])
        mn = slots[f.material_index] if f.material_index < len(slots) else ""
        mat_of_tri.append(mats.setdefault(mn, len(mats)))
        obj_of_tri.append(oi)
    bm.free()
np.savez_compressed(out, tri=np.array(tri, dtype=np.float64).reshape(-1, 3, 3),
                    obj=np.array(obj_of_tri, dtype=np.int32), mat=np.array(mat_of_tri, dtype=np.int32),
                    names=np.array(names), mats=np.array(list(mats)))
print("DUMPED objects", len(names), "tris", len(tri))
