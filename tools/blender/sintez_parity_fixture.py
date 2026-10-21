"""new-case: Blender synthetic FBX threshold fixture export/readback (#432).

Factory background process only. No real scene/asset is opened. Version/provenance
is checked before creating geometry; outputs must not already exist. No vendor
source is copied. The readback is from the exported FBX, not the in-memory seed.
"""
import importlib.util
import json
import math
import sys
import tomllib
from pathlib import Path

import bpy


def main():
    seed, output = [Path(p).resolve() for p in sys.argv[sys.argv.index("--")+1:]]
    if bpy.app.version_string != "5.1.2":
        raise ValueError("Blender 5.1.2 required")
    spec = importlib.util.find_spec("bl_ext.user_default.sintez_agr_checker")
    manifest = Path(spec.origin).with_name("blender_manifest.toml")
    version = tomllib.loads(manifest.read_text(encoding="utf-8"))["version"]
    if version != "1.6.1":
        raise ValueError("SINTEZ 1.6.1 required")
    doc = json.loads(seed.read_text(encoding="utf-8"))
    case, initial = doc["case"], doc["mesh"]
    if case.get("synthetic") is not True or Path(doc["source"]).name != doc["source"]:
        raise ValueError("synthetic fixture with basename-only source required")
    target, report = output/doc["source"], output/"readback.json"
    if target.exists() or report.exists() or target == seed or report == seed:
        raise ValueError("output already exists or aliases input")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    mesh = bpy.data.meshes.new("Synthetic")
    if "polycount" in case["group"]:
        # Connected grid, no coincident vertices or million-fold duplicate faces.
        n = initial["triangles"]
        width = 1000
        rows = (n+2*width-1)//(2*width)
        vertices = [(x,y,120) for y in range(rows+1) for x in range(width+1)]
        faces = []
        for y in range(rows):
            for x in range(width):
                a = y*(width+1)+x
                faces.extend(((a,a+1,a+width+2),(a,a+width+2,a+width+1)))
        faces = faces[:n]
    else:
        offset = case["value"] if "pivot" in case["group"] else 0
        vertices = [(-1+offset,-1,120),(1+offset,-1,120),(offset,1,120),(offset,0,122)]
        faces = [(0,2,1),(0,1,3),(1,2,3),(2,0,3)]
        if "duplicates" in case["group"] and case["value"]:
            vertices.append((10,10,120))
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    obj = bpy.data.objects.new(initial["name"],mesh)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler.x = math.radians(initial["rotation_euler_deg"][0])
    uv = mesh.uv_layers.new(name="UVMap")
    # All tetra faces have one positive UV triangle unless intentionally degenerate.
    import numpy as np
    coords = np.tile(np.array(doc["uv"], dtype=np.float32), (len(faces),1)).reshape(-1)
    uv.data.foreach_set("uv", coords)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(target), use_selection=True, object_types={"MESH"},
        add_leaf_bones=False, bake_anim=False, axis_forward="-Z", axis_up="Y")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(target), use_anim=False)
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(objects) != 1:
        raise ValueError("expected exactly one imported synthetic mesh")
    obj = objects[0]
    mesh = obj.data
    points = [obj.matrix_world @ __import__('mathutils').Vector(c) for c in obj.bound_box]
    rb = dict(source=doc["source"], readback_ok=True, other_objects=[], images=[],
              fbx_units=dict(unit_scale_factor=100,original_unit_scale_factor=100))
    measured = dict(name=obj.name, triangles=sum(len(p.vertices)-2 for p in mesh.polygons),
        polygon_degrees={str(d):sum(len(p.vertices)==d for p in mesh.polygons)
                         for d in set(len(p.vertices) for p in mesh.polygons)},
        location=list(obj.location), scale=list(obj.scale),
        rotation_euler_deg=[math.degrees(v) for v in obj.rotation_euler],
        uv_channels=len(mesh.uv_layers), udim_tiles=[1001], mirrored_uv_triangles=0,
        materials=[], bounds_m=[[min(p[i] for p in points) for i in range(3)],
                               [max(p[i] for p in points) for i in range(3)]])
    if "duplicates" in case["group"]:
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("parity_topology",root/"src/twinqa/geometry/topology.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        measured["topology"] = module.count_defects(
            [list(obj.matrix_world @ v.co) for v in mesh.vertices],
            [list(p.vertices) for p in mesh.polygons], [list(e.vertices) for e in mesh.edges])
    rb["meshes"] = [measured]
    first = mesh.polygons[0]
    read_uv = [list(mesh.uv_layers.active.data[i].uv) for i in first.loop_indices]
    with report.open("x",encoding="utf-8") as f:
        json.dump(dict(blender=bpy.app.version_string, extension_version=version,
                       readback=rb, uv=read_uv),f,allow_nan=False)


if __name__ == "__main__":
    main()
