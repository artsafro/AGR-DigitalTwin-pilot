"""Blender headless: move the placed Flora UVs into the #217 atlas cells, one material, export + readback.

Pattern: n/a | new-case: applies flora-atlas.json (tools/library/flora_atlas_from_scene.py) to the work .blend of
flora_build_blender.py: each face's UVs -> its species cell (u0 + u*(u1-u0)), all faces on M_<Address>_Flora_1
(diffuse T_..._Flora_d_1 + separate opacity T_..._Flora_o_1, D020). Readback of the exported FBX: tris, materials,
every face's UVs inside its cell. Run:
blender -b --factory-startup WORK.blend --python flora_atlas_apply_blender.py -- ATLAS.json OUT_DIR ADDRESS VERSION
"""
import json
import re
import sys
from pathlib import Path

import bpy

atlas_p, out_dir, address, ver = sys.argv[sys.argv.index("--") + 1:]
atlas = json.loads(Path(atlas_p).read_text(encoding="utf-8"))
cells = {d["material_id"]: d["uv"] for d in atlas["ids"]}
out = Path(out_dir)
name = f"SM_{address}_Flora"
ob = bpy.data.objects[name]
me = ob.data
slot_id = [int(re.search(r"_ID(\d+)$", m.name).group(1)) for m in me.materials]
uvl = me.uv_layers.active.data
face_id = []
for p in me.polygons:
    mid = slot_id[p.material_index]
    u0, v0, u1, v1 = cells[mid]
    for li in p.loop_indices:
        u, v = uvl[li].uv
        uvl[li].uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))
    face_id.append(mid)
mat = bpy.data.materials.new(f"M_{address}_Flora_1")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
td = nt.nodes.new("ShaderNodeTexImage")
td.image = bpy.data.images.load(atlas["material"]["diffuse"])
to = nt.nodes.new("ShaderNodeTexImage")
to.image = bpy.data.images.load(atlas["material"]["opacity"])
to.image.colorspace_settings.name = "Non-Color"
nt.links.new(td.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(to.outputs["Color"], bsdf.inputs["Alpha"])
me.materials.clear()
me.materials.append(mat)
for p in me.polygons:
    p.material_index = 0
for o in list(bpy.data.objects):
    if o is not ob:
        bpy.data.objects.remove(o)
blend = out / f"{name}_review_{ver}.blend"
fbx = out / f"{name}_{ver}.fbx"
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
                         mesh_smooth_type="FACE", path_mode="COPY", embed_textures=True)

# readback (face order is kept by the FBX round trip; checked by the face count)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
r = meshes[0].data
uvr = r.uv_layers.active.data
eps = 1e-6
outside, by_id = 0, {}
same_count = len(r.polygons) == len(face_id)
for p, mid in zip(r.polygons, face_id):
    u0, v0, u1, v1 = cells[mid]
    by_id[mid] = by_id.get(mid, 0) + len(p.vertices) - 2
    for li in p.loop_indices:
        u, v = uvr[li].uv
        if not (u0 - eps <= u <= u1 + eps and v0 - eps <= v <= v1 + eps):
            outside += 1
tris = sum(len(p.vertices) - 2 for p in r.polygons)
res = {"fbx": str(fbx), "blend": str(blend), "objects": [o.name for o in meshes], "materials": [m.name for m in r.materials],
       "images": sorted(i.name for i in bpy.data.images), "polygons": len(r.polygons), "tris": tris,
       "budget_flora": 70000, "within_budget": tris <= 70000, "face_count_matches_build": same_count,
       "uv_loops_outside_cell": outside, "tris_by_material_id": by_id,
       "object_scale": list(meshes[0].scale), "atlas_size": atlas["atlas_size"], "atlas_count": atlas["atlas_count"]}
(out / f"flora_readback_{ver}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
print("FLORA_ATLAS_READBACK", json.dumps(res, ensure_ascii=False))
