"""Per-object world bbox census of a Revit FBX (#1619 gate 1). new-case: read-only building splitter input.

blender -b --factory-startup --python site_census.py -- IN.fbx OUT.json
For each mesh object: name, faces, world bbox (min/max xyz), vertical facade area and the area of vertical
faces off the 4 main azimuths of that object (rounded/angled walls). Never saves the scene; refuses an
output that is not a .json or that resolves to the input.
"""
import json
import math
import os
import sys

import bpy

src, out = sys.argv[sys.argv.index("--") + 1:]
if not out.lower().endswith(".json") or os.path.realpath(out) == os.path.realpath(src):
    sys.exit("output must be a separate .json report")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
rows = []
for ob in bpy.context.scene.objects:
    if ob.type != "MESH" or not ob.data.polygons:
        continue
    mw = ob.matrix_world
    mw3 = mw.to_3x3()
    xs, ys, zs = [], [], []
    for v in ob.data.vertices:
        p = mw @ v.co
        xs.append(p.x)
        ys.append(p.y)
        zs.append(p.z)
    bins = {}
    fac = 0.0
    for p in ob.data.polygons:
        n = (mw3 @ p.normal)
        if n.length == 0:
            continue
        n.normalize()
        if abs(n.z) >= 0.2:
            continue
        a = p.area * (mw3.determinant() ** (2 / 3) if mw3.determinant() > 0 else 1.0)
        fac += a
        az = math.degrees(math.atan2(n.y, n.x)) % 90.0
        b = int(round(az)) % 90
        bins[b] = bins.get(b, 0.0) + a
    off = 0.0
    if bins:
        main = max(bins, key=bins.get)
        off = sum(a for b, a in bins.items() if min((b - main) % 90, (main - b) % 90) > 2)
    rows.append({
        "name": ob.name, "faces": len(ob.data.polygons),
        "min": [round(min(xs), 2), round(min(ys), 2), round(min(zs), 2)],
        "max": [round(max(xs), 2), round(max(ys), 2), round(max(zs), 2)],
        "facade_m2": round(fac, 1), "off_main_m2": round(off, 1),
    })
with open(out, "w", encoding="utf-8") as f:
    json.dump({"source": os.path.basename(src), "objects": rows}, f, ensure_ascii=False)
print("objects", len(rows))
