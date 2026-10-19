"""Read-only Blender inventory of a MAF NPM .blend copy.

Run:
    blender --background <copy.blend> --factory-startup --python tools/library/maf_blender_inventory.py

AGR_MAF_BLEND_INVENTORY must be a new output path. This script never saves the
.blend.
"""

import bpy
import json
import os
import time
from mathutils import Vector
from pathlib import Path

output = os.environ.get("AGR_MAF_BLEND_INVENTORY")
if not output:
    raise RuntimeError("AGR_MAF_BLEND_INVENTORY is required")
out_path = Path(output)
if out_path.exists():
    raise RuntimeError("refusing to overwrite existing inventory: " + str(out_path))

t0 = time.time()
rows = []
for obj in bpy.data.objects:
    row = {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "collections": [col.name for col in obj.users_collection],
        "data": obj.data.name if obj.data else None,
    }
    if obj.type == "MESH":
        mesh = obj.data
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        row["bbox"] = [
            [min(corner[axis] for corner in corners) for axis in range(3)],
            [max(corner[axis] for corner in corners) for axis in range(3)],
        ]
        mesh.calc_loop_triangles()
        row["tris"] = len(mesh.loop_triangles)
        row["verts"] = len(mesh.vertices)
        row["materials"] = [mat.name if mat else None for mat in mesh.materials]
        row["dims"] = list(obj.dimensions)
    rows.append(row)

result = {
    "file": bpy.data.filepath,
    "unit_system": bpy.context.scene.unit_settings.system,
    "scale_length": bpy.context.scene.unit_settings.scale_length,
    "count": len(rows),
    "objects": rows,
    "collections": {col.name: [obj.name for obj in col.objects] for col in bpy.data.collections},
    "s": time.time() - t0,
}
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
print("AGR_BINV", len(rows))
