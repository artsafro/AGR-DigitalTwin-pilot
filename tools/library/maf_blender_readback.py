"""Independent Blender 5.1.2 readback of the MAF library FBX files (#183).

Pattern: verify actual artifacts, not exporter return codes. Bounds of referenced
vertices are separate from all-vertex bounds: legacy assets can carry loose verts.
No files are saved and no user scene is opened. Run Blender --background
--factory-startup --python this_file; AGR_MAF_LIB/AGR_MAF_READBACK select paths.
"""
import json
import os
import time
from pathlib import Path

import bpy

lib = Path(os.environ.get("AGR_MAF_LIB", "C:/x/t_3e6ff1b3/library"))
output = Path(os.environ.get("AGR_MAF_READBACK", "C:/x/t_3e6ff1b3/fbx_readback_v003.json"))
if output.exists():
    raise RuntimeError("refusing readback overwrite: " + str(output))


def bounds(points):
    if not points:
        return None
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return {"bbox_m": [lo, hi], "dims_m": [hi[i] - lo[i] for i in range(3)]}


rows = []
t0 = time.time()
for path in sorted((lib / "fbx").glob("*.fbx")):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    row = {"fbx": path.as_posix()}
    try:
        bpy.ops.import_scene.fbx(filepath=str(path))
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        points, used_points, objects = [], [], []
        tris = 0
        for obj in meshes:
            mesh = obj.data
            mesh.calc_loop_triangles()
            tris += len(mesh.loop_triangles)
            referenced = {v for face in mesh.polygons for v in face.vertices}
            world = [obj.matrix_world @ v.co for v in mesh.vertices]
            points.extend(world)
            used_points.extend(world[i] for i in referenced)
            objects.append({
                "name": obj.name, "triangles": len(mesh.loop_triangles),
                "loose_vertices": len(mesh.vertices) - len(referenced),
                "non_triangle_faces": sum(len(p.vertices) != 3 for p in mesh.polygons),
                "zero_area_triangles": sum(t.area <= 1e-12 for t in mesh.loop_triangles),
                "uv_layers": [layer.name for layer in mesh.uv_layers],
                "materials": [m.name if m else None for m in mesh.materials],
                "unassigned_faces": sum(p.material_index >= len(mesh.materials) for p in mesh.polygons),
                "matrix_world": [list(r) for r in obj.matrix_world],
            })
        row.update(meshes=len(meshes), tris=tris, all_vertices=bounds(points),
                   referenced_vertices=bounds(used_points), objects=objects)
    except Exception as exc:
        row["error"] = str(exc)
    rows.append(row)
result = {"blender": bpy.app.version_string, "seconds": round(time.time() - t0, 2), "files": rows}
with output.open("x", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False)
print("AGR_READBACK", len(rows), result["seconds"])
