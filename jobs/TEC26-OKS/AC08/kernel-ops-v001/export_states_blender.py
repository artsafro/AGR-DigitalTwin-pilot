"""Write kernel-op states (polygons + per-corner UV + material ids) to one FBX each (#752).

    blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
        --python export_states_blender.py -- <states.json> <out_dir>

states.json: {"<label>": [{"name", "vertices", "polygons", "uv" (per corner, or null per polygon),
"material_ids"}]}. One FBX `<label>.fbx` per state; an existing FBX is refused (new versioned output).
A polygon without UV gets no UV layer entry only when the whole object has none; mixed objects are refused,
because a default UV would hide a lost one. Units metres, scale 1, polygons as given (no triangulation).
Pattern: none | new-case: job-local FBX writer for kernel-op evidence states (#752).
"""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 2:
    raise SystemExit("usage: ... -- <states.json> <out_dir>")
source, out_dir = Path(args[0]).resolve(), Path(args[1]).resolve()
states = json.loads(source.read_text(encoding="utf-8"))
targets = {label: out_dir / f"{label}.fbx" for label in states}
for path in targets.values():
    if path.exists():
        raise SystemExit(f"{path} exists; write a new versioned output")
out_dir.mkdir(parents=True, exist_ok=True)
for label, objects in states.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
    for o in objects:
        polys = [list(p) for p in o["polygons"]]
        data = bpy.data.meshes.new(o["name"])
        data.from_pydata([tuple(v) for v in o["vertices"]], [], polys)
        if data.validate(clean_customdata=False) or len(data.polygons) != len(polys):
            raise SystemExit(f"{label}/{o['name']}: Blender rejected or changed polygons")
        mids = o["material_ids"]
        if len(mids) != len(polys) or min(mids) < 1:
            raise SystemExit(f"{label}/{o['name']}: material ids {len(mids)} for {len(polys)} polygons or id < 1")
        for n in range(1, max(mids) + 1):
            data.materials.append(bpy.data.materials.get(f"ID_{n:02d}") or bpy.data.materials.new(f"ID_{n:02d}"))
        for poly, mid in zip(data.polygons, mids):
            poly.material_index = mid - 1
        uv = o["uv"]
        has = [c is not None for c in uv]
        if any(has) and not all(has):
            raise SystemExit(f"{label}/{o['name']}: {has.count(False)} polygons without UV in a UV object")
        if all(has):
            layer = data.uv_layers.new(name="UVMap")
            for poly, corners in zip(data.polygons, uv):
                if len(corners) != poly.loop_total:
                    raise SystemExit(f"{label}/{o['name']}: polygon {poly.index} UV corners mismatch")
                for k, (u, w) in enumerate(corners):
                    layer.data[poly.loop_start + k].uv = (u, w)
        data.update()
        obj = bpy.data.objects.new(o["name"], data)
        scene.collection.objects.link(obj)
    bpy.ops.export_scene.fbx(filepath=str(targets[label]), use_selection=False, object_types={"MESH"},
                             apply_unit_scale=True, use_mesh_modifiers=False, add_leaf_bones=False,
                             mesh_smooth_type="FACE")
print(json.dumps({"exported": {k: str(v) for k, v in targets.items()}}))
