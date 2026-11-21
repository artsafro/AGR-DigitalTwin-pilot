"""Headless Blender glue of the `vpm-to-npm` cell (#1737); driven by tools/derive/vpm_to_npm.py only.

Pattern: n/a | new-case: FBX I/O for the vpm-to-npm driver (dump VPM render meshes; build the NPM FBX from the atlas
OBJ + merged glass). No decisions here: interiors, atlas and glass are decided by vpm_npm_core / npm_atlas_udim.
  dump  <vpm.fbx> <out.json>                                  world-space faces + UV of every non-UCX mesh
  build <atlas.obj> <glass.json> <atlas_d.png> <main> <outdir> SM_..._Main + SM_..._MainGlass, triangulated FBX,
                                                              embedded atlas, glass M_Glass_01 alpha 0.5 without a
                                                              texture (its UVs still sit on the white atlas cell)
"""
import json
import os
import sys

import bmesh
import bpy


def dump(src, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    objs = {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o.name.startswith("UCX_"):
            continue
        me = o.data
        uv = me.uv_layers.active
        if uv is None:
            raise SystemExit(f"{o.name}: no UV layer")
        mw = o.matrix_world
        faces = []
        for p in me.polygons:
            faces.append({"object": o.name, "verts": [list(mw @ me.vertices[v].co) for v in p.vertices],
                          "uv": [list(uv.data[li].uv) for li in p.loop_indices]})
        objs[o.name] = faces
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"source": src, "objects": objs}, fh)


def build(obj_path, glass_json, atlas_png, main, outdir):
    if os.path.exists(outdir):
        raise SystemExit(f"{outdir} exists")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=obj_path, forward_axis="Y", up_axis="Z")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(meshes) != 1:
        raise SystemExit(f"atlas OBJ gave {len(meshes)} meshes")
    m = meshes[0]
    m.name = m.data.name = main
    wb = bmesh.new()
    wb.from_mesh(m.data)
    bmesh.ops.remove_doubles(wb, verts=wb.verts, dist=1e-5)  # OBJ rows are per face; weld coincident corners
    wb.to_mesh(m.data)
    wb.free()
    img = bpy.data.images.load(atlas_png)
    mat = bpy.data.materials.new(f"M_{main[3:]}_1")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    m.data.materials.clear()
    m.data.materials.append(mat)
    g = json.load(open(glass_json, encoding="utf-8"))
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in g["faces"]:
        vs = [bm.verts.new(p) for p in f["verts"]]
        face = bm.faces.new(vs)
        for loop, t in zip(face.loops, f["uv"]):
            loop[uvl].uv = t
    gme = bpy.data.meshes.new(g["name"])
    bm.to_mesh(gme)
    gob = bpy.data.objects.new(g["name"], gme)
    bpy.context.scene.collection.objects.link(gob)
    gmat = bpy.data.materials.new("M_Glass_01")
    gmat.use_nodes = True
    gb = gmat.node_tree.nodes["Principled BSDF"]
    gb.inputs["Base Color"].default_value = (1, 1, 1, 1)  # glass carries no texture (SINTEZ «Glass без текстур»)
    gb.inputs["Alpha"].default_value = 0.5
    gme.materials.append(gmat)
    gbm = bmesh.new()
    gbm.from_mesh(gme)
    bmesh.ops.remove_doubles(gbm, verts=gbm.verts, dist=1e-5)
    gbm.to_mesh(gme)
    gbm.free()
    for o in (m, gob):
        bpy.context.view_layer.objects.active = o
        for s in bpy.context.scene.objects:
            s.select_set(s == o)
        mod = o.modifiers.new("tri", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=mod.name)
    os.makedirs(outdir)
    for s in bpy.context.scene.objects:
        s.select_set(True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(outdir, f"{main}.fbx"), use_selection=True,
                             path_mode="COPY", embed_textures=True, axis_forward="-Z", axis_up="Y",
                             apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    mode, args = argv[0], argv[1:]
    {"dump": dump, "build": build}[mode](*args)
    print("VPM2NPM-OK", mode)


main()
