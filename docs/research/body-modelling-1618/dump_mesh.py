"""Blender headless dump of an FBX for the body-grid study (#1618). new-case: read-only etalon grid census.

Usage (read-only; writes only OUT_DIR):
  blender -b --factory-startup --python dump_mesh.py -- IN.fbx OUT_DIR

Per mesh object writes OUT_DIR/<object>.npz with world-space vertices, triangle/polygon
faces as exported, material index per face, material names and the quad-rejoined faces
(bmesh join_triangles, 1 deg face/shape limits: only coplanar rectangle-like pairs merge,
so remaining triangles are the diagonals the author actually needed). Never saves the scene.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
if os.path.abspath(out).startswith(os.path.abspath(os.path.dirname(src))):
    sys.exit("output dir must not be the input dir")
os.makedirs(out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
summary = []
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        summary.append({"name": ob.name, "type": ob.type})
        continue
    me = ob.data
    mw = ob.matrix_world
    verts = np.array([tuple(mw @ v.co) for v in me.vertices], dtype=np.float64)
    faces = [list(p.vertices) for p in me.polygons]
    mats = np.array([p.material_index for p in me.polygons], dtype=np.int32)
    names = [m.name if m else "" for m in me.materials]
    # UV of each face corner (first UV layer), for module/UV-island study
    uv = me.uv_layers[0].data if me.uv_layers else None
    face_uv = []
    for p in me.polygons:
        face_uv.append([tuple(uv[i].uv) for i in p.loop_indices] if uv else [])
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(mw)
    bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=math.radians(1.0),
                             angle_shape_threshold=math.radians(1.0), cmp_seam=False, cmp_sharp=False,
                             cmp_uvs=False, cmp_vcols=False, cmp_materials=True)
    bm.verts.index_update()
    jverts = np.array([tuple(v.co) for v in bm.verts], dtype=np.float64)
    jfaces = [[v.index for v in f.verts] for f in bm.faces]
    jmats = np.array([f.material_index for f in bm.faces], dtype=np.int32)
    bm.free()

    def pack(fl):
        return np.array([len(f) for f in fl], dtype=np.int32), np.array([i for f in fl for i in f], dtype=np.int64)

    fn, fi = pack(faces)
    jn, ji = pack(jfaces)
    uvn = np.array([len(u) for u in face_uv], dtype=np.int32)
    uvf = np.array([c for u in face_uv for c in u], dtype=np.float64).reshape(-1, 2)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in ob.name)
    np.savez_compressed(os.path.join(out, safe + ".npz"), verts=verts, fn=fn, fi=fi, mats=mats,
                        jverts=jverts, jn=jn, ji=ji, jmats=jmats, uvn=uvn, uvf=uvf,
                        names=np.array(names))
    summary.append({"name": ob.name, "file": safe + ".npz", "verts": len(verts), "faces": len(faces),
                    "tris": int((fn == 3).sum()), "materials": names,
                    "dims": [round(x, 3) for x in ob.dimensions]})
with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:
    json.dump({"source": src, "objects": summary}, fh, ensure_ascii=False, indent=1)
print("DUMPED", len(summary))
