"""Blender side of the Vatutino Flora route A run (#1146): export + readback of placement v007, review renders.

Job script, run only by flora_route_a.py (Blender 5.1 headless):
  -- export   <placement.blend> <out.fbx>                    instances collection -> one FBX (scene read-only)
  -- readback <in.fbx> <out.json> <udim tile>                 fresh-scene import: counts, tris, materials, UV, transforms
  -- site     <placement.blend> <atlas diffuse> <atlas opacity> <out dir>   6 site views (NPM)
  -- species  <stars meshes.json> <atlas diffuse> <atlas opacity> <out dir>  one render per star NPM / VPM
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Vector


def _args():
    return sys.argv[sys.argv.index("--") + 1:]


def cmd_export(blend, fbx):
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    inst = bpy.data.collections["instances"]
    # every star FBX was imported on its own, so Blender suffixed the shared atlas material (.001 ...):
    # bind every slot back to the one atlas material before export (one atlas = one material)
    base = bpy.data.materials.get("M_VATUTINO_Flora_1")
    if base is None:
        raise SystemExit("atlas material M_VATUTINO_Flora_1 not in the scene")
    merged = 0
    for me in {o.data for o in inst.objects}:
        for i, m in enumerate(me.materials):
            if m is not None and m is not base and m.name.split(".")[0] == base.name:
                me.materials[i] = base
                merged += 1
    print(f"export: {merged} mesh slots rebound to {base.name}")
    bpy.ops.object.select_all(action="DESELECT")
    for ob in inst.objects:
        ob.hide_set(False)
        ob.select_set(True)
    if Path(fbx).exists():
        raise SystemExit(f"{fbx} exists")
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, path_mode="COPY", embed_textures=False,
                             axis_forward="-Z", axis_up="Y", object_types={"MESH"}, use_custom_props=True)
    print(f"export: {len(inst.objects)} objects -> {fbx}")


def cmd_readback(fbx, out_json, tile):
    tile = int(tile)
    du, dv = (tile - 1001) % 10, (tile - 1001) // 10
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    meshes = {o.data.name: o.data for o in objs}
    uv_out, uv_layers, tris_mesh = 0, set(), {}
    for name, me in meshes.items():
        uv_layers.add(len(me.uv_layers))
        tris_mesh[name] = sum(len(p.vertices) - 2 for p in me.polygons)
        uvl = me.uv_layers.active
        for p in me.polygons:
            if uvl is None or any(not (du - 1e-5 <= uvl.data[li].uv[0] <= du + 1 + 1e-5
                                       and dv - 1e-5 <= uvl.data[li].uv[1] <= dv + 1 + 1e-5) for li in p.loop_indices):
                uv_out += 1
    tris = sum(tris_mesh[o.data.name] for o in objs)
    mats = Counter(s.material.name for o in objs for s in o.material_slots if s.material)
    bad_tf, scales, lowest = [], [], []
    for o in objs:
        M = o.matrix_world
        if not all(math.isfinite(x) for row in M for x in row):
            bad_tf.append(o.name)
        scales.append(tuple(round(s, 4) for s in M.to_scale()))
        lowest.append(min((M @ v.co).z for v in o.data.vertices))
    lib = Counter(o.name.split(".")[0].rsplit("_", 1)[0] for o in objs)
    lo = [min((o.matrix_world @ Vector(c))[i] for o in objs for c in o.bound_box) for i in range(3)]
    hi = [max((o.matrix_world @ Vector(c))[i] for o in objs for c in o.bound_box) for i in range(3)]
    Path(out_json).write_text(json.dumps({
        "fbx": str(fbx), "objects": len(objs), "unique_meshes": len(meshes), "triangles": tris,
        "materials": dict(mats), "uv_layers_per_mesh": sorted(uv_layers), "udim_tile": tile, "uv_faces_outside_tile": uv_out,
        "non_finite_transforms": bad_tf, "scale_values": sorted({s for s in scales})[:10],
        "names_by_prefix": dict(lib), "bbox_min": lo, "bbox_max": hi,
        "unit_scale": bpy.context.scene.unit_settings.scale_length}, indent=1), encoding="utf-8")
    print(f"readback: {len(objs)} objects, {tris} tris, materials {dict(mats)}, uv outside {uv_out}")


def _atlas_material(diffuse, opacity):
    mat = bpy.data.materials.new("M_VATUTINO_Flora_1_review")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(diffuse))
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    op = nt.nodes.new("ShaderNodeTexImage")
    op.image = bpy.data.images.load(str(opacity))
    op.image.colorspace_settings.name = "Non-Color"
    op.interpolation = "Closest"
    nt.links.new(op.outputs["Color"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.9
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    if hasattr(mat, "blend_method"):
        try:
            mat.blend_method = "CLIP"
        except TypeError:
            pass
    return mat


def _engine(scene, res):
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("W") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.78, 0.84, 0.92, 1.0)
        bg.inputs["Strength"].default_value = 0.8
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.5
    so = bpy.data.objects.new("Sun", sun)
    so.rotation_euler = (math.radians(50), 0, math.radians(35))
    scene.collection.objects.link(so)


def _camera(scene, loc, target, ortho=None, lens=35):
    cam = bpy.data.cameras.new("Cam")
    cam.lens = lens
    cam.clip_end = 5000
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    co = bpy.data.objects.new("Cam", cam)
    scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = co
    return co


def cmd_site(blend, diffuse, opacity, out_dir):
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    mat = _atlas_material(diffuse, opacity)
    inst = bpy.data.collections["instances"].objects
    for me in {o.data for o in inst}:
        me.materials.clear()
        me.materials.append(mat)
    _engine(scene, (1600, 1000))
    pts = [o.matrix_world.translation for o in inst]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (lo + hi) / 2
    span = max(hi.x - lo.x, hi.y - lo.y)
    out = Path(out_dir)
    views = {}
    for name, (ax, ay) in {"oblique_SW": (-1, -1), "oblique_SE": (1, -1), "oblique_NE": (1, 1), "oblique_NW": (-1, 1)}.items():
        views[name] = (c + Vector((ax * 0.55 * span, ay * 0.55 * span, 0.45 * span)), c, None, 30)
    views["top"] = (c + Vector((0, 0, 2 * span)), c, 1.08 * span, 35)
    # eye level: 1.7 m above the local plant pivots (= ground - sink), 22 m from the densest 10 m cell, on the first
    # bearing with no plant within 4 m of the lens (v002 put the lens inside a hedge)
    dense = Counter((round(p.x / 10), round(p.y / 10)) for p in pts).most_common(1)[0][0]
    tgt = Vector((dense[0] * 10, dense[1] * 10, 0))
    near = sorted(p.z for p in pts if (p.xy - tgt.xy).length < 25) or [c.z]
    tgt.z = near[len(near) // 2]
    loc = None
    for deg in range(-90, 270, 15):
        a = math.radians(deg)
        cand = tgt + Vector((22 * math.cos(a), 22 * math.sin(a), 1.7))
        if min((p.xy - cand.xy).length for p in pts) > 4.0:
            loc = cand
            break
    views["eye_level"] = (loc or tgt + Vector((0, -22, 1.7)), tgt + Vector((0, 0, 1.0)), None, 28)
    for name, (loc, tgt, ortho, lens) in views.items():
        _camera(scene, loc, tgt, ortho, lens)
        scene.render.filepath = str(out / f"site_{name}.png")
        bpy.ops.render.render(write_still=True)
    print(f"site: {len(views)} views, {len(inst)} plants")


def cmd_species(meshes_json, diffuse, opacity, out_dir):
    data = json.loads(Path(meshes_json).read_text(encoding="utf-8"))
    out = Path(out_dir)
    for key, m in data.items():
        for prof in ("npm", "vpm"):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            scene = bpy.context.scene
            mat = _atlas_material(diffuse, opacity)
            mesh = m[prof]
            du = 1.0 if prof == "vpm" else 0.0  # UDIM 1002 -> 0-1 to sample the single atlas image
            uvs = [(u - du, v) for tri in mesh["uvs"] for u, v in tri]
            me = bpy.data.meshes.new(key)
            me.from_pydata(mesh["verts"], [], mesh["tris"])
            uvl = me.uv_layers.new(name="UVMap")
            for i, loop in enumerate(uvl.data):
                loop.uv = uvs[i]
            me.materials.append(mat)
            ob = bpy.data.objects.new(key, me)
            scene.collection.objects.link(ob)
            ob.rotation_euler = (0, 0, math.radians(20))
            _engine(scene, (400, 400))
            zs = [v[2] for v in mesh["verts"]]
            h = max(zs) - min(zs)
            mid = (max(zs) + min(zs)) / 2
            _camera(scene, (0, -3.0 * h, mid + 0.35 * h), (0, 0, mid), ortho=1.25 * h)
            ground = bpy.data.meshes.new("g")
            r = 0.8 * h
            ground.from_pydata([(-r, -r, -0.1), (r, -r, -0.1), (r, r, -0.1), (-r, r, -0.1)], [], [(0, 1, 2, 3)])
            scene.collection.objects.link(bpy.data.objects.new("g", ground))
            scene.render.filepath = str(out / f"sp_{key}_{prof}.png")
            bpy.ops.render.render(write_still=True)
    print(f"species: {len(data)} x 2 renders")


def main():
    a = _args()
    cmds = {"export": (cmd_export, 2), "readback": (cmd_readback, 3), "site": (cmd_site, 4), "species": (cmd_species, 4)}
    if not a or a[0] not in cmds or len(a) - 1 != cmds[a[0]][1]:
        raise SystemExit(f"usage: -- {{{'|'.join(cmds)}}} ... ; got {a}")
    cmds[a[0]][0](*a[1:])


main()
