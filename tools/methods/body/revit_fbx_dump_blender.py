"""Blender side of the Revit-FBX openings step (#1784): one read-only object dump of a Revit FBX export.

Pattern: n/a | new-case: per-object world XY convex hull + z range of a Revit FBX (no materials, baked transforms),
the only input of openings_from_revit_fbx.py.

blender -b --factory-startup --python tools/methods/body/revit_fbx_dump_blender.py -- SRC.fbx NEW_DUMP.json

Imports SRC.fbx into an empty scene (never saves a .blend), writes NEW_DUMP.json with schema `revit-fbx-dump/1`:
{"schema", "source", "sha256", "objects": [{"name", "verts", "tris", "materials", "z": [zmin, zmax], "hull": [[x, y], ...]}]}.
`materials` (sorted slot material names) was added for `agr scene prepare` (#1867); older dumps lack it.
Hull = 2D convex hull of the world-space vertices (metres after import), CCW. Objects without vertices are kept
with "hull": [] so the extractor reports them. NEW_DUMP.json must not exist and must not be SRC.fbx.
Blender 5.1.2 crashes on some Revit FBX imports; run this with Blender 4.4 (#1784 intake).
"""
import hashlib
import json
import os
import sys

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.geometry import convex_hull_2d  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 2:
        print("usage (inside Blender 4.4): revit_fbx_dump_blender.py -- SRC.fbx NEW_DUMP.json", file=sys.stderr)
        sys.exit(2)
    src, out = argv
    if os.path.exists(out) or os.path.realpath(out) == os.path.realpath(src):
        print("refused: NEW_DUMP.json exists or is the input", file=sys.stderr)
        sys.exit(2)
    h = hashlib.sha256()
    with open(src, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    objs = []
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        me, mw = ob.data, ob.matrix_world
        n = len(me.vertices)
        rec = {"name": ob.name, "verts": n, "tris": sum(len(p.vertices) - 2 for p in me.polygons),
               "materials": sorted({s.material.name for s in ob.material_slots if s.material})}
        if n:
            co = np.empty(n * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3)
            m = np.array(mw, dtype=np.float64)
            w = co @ m[:3, :3].T + m[:3, 3]
            xy = [Vector((x, y)) for x, y in np.unique(np.round(w[:, :2], 4), axis=0)]
            idx = convex_hull_2d(xy)
            rec["z"] = [round(float(w[:, 2].min()), 4), round(float(w[:, 2].max()), 4)]
            rec["hull"] = [[round(xy[i][0], 4), round(xy[i][1], 4)] for i in idx]
        else:
            rec["z"], rec["hull"] = None, []
        objs.append(rec)
    doc = {"schema": "revit-fbx-dump/1", "source": os.path.realpath(src), "sha256": h.hexdigest(), "objects": objs}
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    print("DUMP_OK", len(objs), out)


main()
