"""Curved-body census of a Revit FBX (#1618). new-case: read-only rounded-corner finder for the research doc.

blender -b --factory-startup --python curve_census.py -- IN.fbx OUT.json
For each mesh object: vertical faces (|nz| < 0.2) binned by normal azimuth (1 deg). A rounded corner shows
as a run of consecutive small bins between the main wall azimuths; we report per object the off-main
facade area, the number of occupied bins and the median angular step between occupied bins
(= Revit tessellation step: segments = 90 / step for a quarter circle). Never saves the scene.
"""
import json
import math
import sys

import bpy

src, out = sys.argv[sys.argv.index("--") + 1:]
if out.lower().endswith(".fbx"):
    sys.exit("output must be a .json report")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
rows = []
for ob in bpy.context.scene.objects:
    if ob.type != "MESH" or not ob.data.polygons:
        continue
    mw3 = ob.matrix_world.to_3x3()
    bins = {}
    total = 0.0
    for p in ob.data.polygons:
        n = (mw3 @ p.normal).normalized()
        if abs(n.z) >= 0.2:
            continue
        az = math.degrees(math.atan2(n.y, n.x)) % 360
        b = int(round(az * 4)) % 1440  # 0.25 deg bins
        bins[b] = bins.get(b, 0.0) + p.area
        total += p.area
    if total < 1.0:
        continue
    main = sorted(bins.items(), key=lambda kv: -kv[1])
    keep = [b for b, a in main if a >= 0.05 * total]
    off = [(b, a) for b, a in bins.items() if all(min(abs(b - k), 1440 - abs(b - k)) > 4 for k in keep)]
    off_area = sum(a for _, a in off)
    occ = sorted(b for b, _ in off)
    steps = [(occ[i + 1] - occ[i]) / 4 for i in range(len(occ) - 1) if 0 < occ[i + 1] - occ[i] <= 60]
    steps.sort()
    rows.append({"name": ob.name, "faces": len(ob.data.polygons), "facade_m2": round(total, 1),
                 "off_main_m2": round(off_area, 1), "off_main_share": round(off_area / total, 3),
                 "off_bins": len(occ), "median_step_deg": steps[len(steps) // 2] if steps else None,
                 "dims": [round(x, 2) for x in ob.dimensions]})
rows.sort(key=lambda r: -r["off_main_m2"])
with open(out, "w", encoding="utf-8") as fh:
    json.dump({"source": src, "objects": len(rows), "top": rows[:60]}, fh, ensure_ascii=False, indent=1)
print("CENSUS", len(rows))
