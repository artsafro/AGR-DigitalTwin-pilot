"""Blender headless: build the placed Flora mesh from the engine report (moskovsky-sosh1200, work version).

Pattern: n/a | new-case: A101 low objects (FBX exported from a FLORIO_221 copy, pivot at origin) instanced by the
engine matrices and merged into one object SM_<Address>_Flora with one material per species (A101 maps, pre-atlas
preview). Writes .blend + work FBX + flora-placed-v1 JSON (faces: material_id + UVs) for the #217 atlas tool, then
reads the FBX back. Run:
blender -b --factory-startup --python flora_build_blender.py -- PLAN.json REPORT.json FBX_DIR TEX_DIR OUT_DIR ADDRESS VERSION
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
plan_p, rep_p, fbx_dir, tex_dir, out_dir, address, ver = argv
plan = json.loads(Path(plan_p).read_text(encoding="utf-8"))
rep = json.loads(Path(rep_p).read_text(encoding="utf-8"))
out = Path(out_dir)
bpy.ops.wm.read_factory_settings(use_empty=True)

species = {}
for row in plan["positions"]:
    if row.get("status") != "place":
        continue
    lid = f"pos{row['pos']}_{row['a101_object']}"
    bpy.ops.import_scene.fbx(filepath=str(Path(fbx_dir) / (row["a101_object"] + ".fbx")))
    objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    assert len(objs) == 1, (row["a101_object"], [o.name for o in objs])
    o = objs[0]
    me = o.data.copy()
    me.transform(o.matrix_world)  # bake FBX axis/unit conversion; pivot stays at origin
    V = np.array([v.co[:] for v in me.vertices])
    uvl = me.uv_layers.active.data
    faces = [(list(p.vertices), [tuple(uvl[li].uv) for li in p.loop_indices]) for p in me.polygons]
    species[lid] = {"row": row, "V": V, "faces": faces, "bbmin": V.min(0).tolist(), "bbmax": V.max(0).tolist()}
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)

verts, polys, uvs, mats, mat_index = [], [], [], [], {}
for lid in species:
    mat_index[lid] = len(mat_index)
for inst in rep["instances"]:
    sp = species[inst["library_id"]]
    M = np.array(inst["matrix"])
    W = sp["V"] @ M[:3, :3].T + M[:3, 3]
    base = len(verts)
    verts.extend(W.tolist())
    for vi, uv in sp["faces"]:
        polys.append([base + i for i in vi])
        uvs.append(uv)
        mats.append(mat_index[inst["library_id"]])

name = f"SM_{address}_Flora"
me = bpy.data.meshes.new(name)
me.from_pydata(verts, [], polys)
me.update()
uvlay = me.uv_layers.new(name="UVMap")
k = 0
for p, uv in zip(me.polygons, uvs):
    for li, c in zip(p.loop_indices, uv):
        uvlay.data[li].uv = c
    p.material_index = mats[k]
    k += 1
ob = bpy.data.objects.new(name, me)
bpy.context.scene.collection.objects.link(ob)
for lid, idx in mat_index.items():
    row = species[lid]["row"]
    m = bpy.data.materials.new(f"{row['latin'].replace(' ', '_').replace(chr(39), '')}_ID{row['material_id']}")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    img = bpy.data.images.load(str(Path(tex_dir) / (row["a101_object"] + ".png")))
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    m.blend_method = "CLIP" if hasattr(m, "blend_method") else None
    ob.data.materials.append(m)

blend = out / f"{name}_work_{ver}.blend"
fbx = out / f"{name}_work_{ver}.fbx"
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, axis_forward="-Z", axis_up="Y",
                         apply_unit_scale=True, mesh_smooth_type="FACE", path_mode="ABSOLUTE")

placed = {"schema": "flora-placed-v1", "address": address, "source": str(rep_p),
          "objects": [{"name": name, "faces": [{"material_id": species[lid]["row"]["material_id"], "uvs": [list(c) for c in uv]}
                                              for uv, lid in zip(uvs, [list(mat_index)[i] for i in mats])]}]}
(out / f"flora_placed_{ver}.json").write_text(json.dumps(placed), encoding="utf-8")

# readback of the exported FBX
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
rb = {}
for o in bpy.context.scene.objects:
    if o.type != "MESH":
        continue
    d = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    tris = sum(len(p.vertices) - 2 for p in d.polygons)
    W = np.array([(o.matrix_world @ v.co)[:] for v in d.vertices])
    U = np.array([l.uv[:] for l in d.uv_layers.active.data]) if d.uv_layers else np.zeros((0, 2))
    per_mat = {}
    for p in d.polygons:
        mn = d.materials[p.material_index].name if d.materials else None
        per_mat[mn] = per_mat.get(mn, 0) + len(p.vertices) - 2
    rb[o.name] = {"polygons": len(d.polygons), "tris": tris, "verts": len(d.vertices),
                  "bbmin": W.min(0).round(3).tolist(), "bbmax": W.max(0).round(3).tolist(),
                  "uv_min": U.min(0).round(4).tolist() if len(U) else None, "uv_max": U.max(0).round(4).tolist() if len(U) else None,
                  "tris_by_material": per_mat, "rotation": list(o.rotation_euler), "scale": list(o.scale)}
summary = {"species_bbox_m": {k: {"bbmin": [round(x, 3) for x in v["bbmin"]], "bbmax": [round(x, 3) for x in v["bbmax"]],
                                   "faces": len(v["faces"])} for k, v in species.items()},
           "instances": len(rep["instances"]), "readback": rb, "blend": str(blend), "fbx": str(fbx)}
(out / f"flora_build_readback_{ver}.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
print("FLORA_BUILD", json.dumps(summary, ensure_ascii=False))
