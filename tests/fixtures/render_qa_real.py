"""new-case: read-only delivered Vatutino FBX -> local render-QA scene/camera fixture.

Blender --background --factory-startup --python-exit-code 1 --python <this> -- <NEW directory>
No source is saved or changed; cameras follow ground_json_to_fbx.py render conventions.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

SOURCE = Path("C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx")
EXPECTED = "94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef"
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED, "Delivered source hash changed"
out = Path(sys.argv[sys.argv.index("--") + 1])
out.mkdir(parents=True, exist_ok=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(SOURCE))
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 1
objects = [o for o in sc.objects if o.type == "MESH"]
points = [o.matrix_world @ v.co for o in objects for v in o.data.vertices]
low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
centre = (low + high) / 2
size = max(high.x - low.x, high.y - low.y)
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x = sc.render.resolution_y = 256
sc.render.resolution_percentage = 100
sc.display.shading.background_type = "WORLD"
sc.world = bpy.data.worlds.new("QAWorld")
sc.world.color = (0, 0, 0)
sc.view_settings.view_transform = "Standard"
views = {"top": (centre + Vector((0, 0, size)), "ORTHO")}
for az in (45, 135, 225, 315):
    radians = math.radians(az)
    views[f"oblique{az}"] = (centre + Vector((math.cos(radians) * size, math.sin(radians) * size, size)), "PERSP")
for name, (position, kind) in views.items():
    data = bpy.data.cameras.new(name)
    data.type = kind
    data.ortho_scale = size * 1.05
    data.clip_end = size * 10
    camera = bpy.data.objects.new(name, data)
    sc.collection.objects.link(camera)
    camera.location = position
    camera.rotation_euler = (centre - position).to_track_quat("-Z", "Y").to_euler()
sc.camera = sc.objects["top"]
bpy.context.view_layer.update()
sc["render_qa_source"] = json.dumps({"path": str(SOURCE), "sha256": EXPECTED,
                                      "note": "Delivered Ground only, no ground-resting parts; no added geometry"})
bpy.ops.wm.save_as_mainfile(filepath=str(out / "preview.blend"))
(out / "config.json").write_text(json.dumps({"targets": [o.name for o in objects],
    "cameras": list(views), "ground_resting": [], "ground_objects": []}, indent=2), encoding="utf-8")
(out / "source.json").write_text(json.dumps({"source": str(SOURCE), "sha256": EXPECTED,
    "objects": [o.name for o in objects], "vertices": len(points), "bounds": [list(low), list(high)],
    "camera_convention": "tools/blender/ground_json_to_fbx.py:render",
    "resolution": [256, 256], "engine": "BLENDER_WORKBENCH",
    "limits": "Numerical framing only; not material, aesthetics or delivery acceptance"}, indent=2), encoding="utf-8")
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
print("REAL_SCENE", bpy.app.version_string, sc.unit_settings.scale_length, len(points), out)
