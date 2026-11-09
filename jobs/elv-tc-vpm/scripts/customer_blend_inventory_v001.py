"""elv-tc-vpm: read-only inventory of the customer's blend (customer-blank-v001).

blender -b --disable-autoexec <copy.blend> --python customer_blend_inventory_v001.py -- <out.json>
Never saves. Text datablocks are listed (name, lines), never executed.
"""
import bpy, sys, os, json

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)


def r(v, n=4):
    return [round(x, n) for x in v]


def coll_tree(c, depth=0):
    vl = bpy.context.view_layer
    return {"name": c.name, "objects": [o.name for o in c.objects], "children": [coll_tree(ch, depth + 1) for ch in c.children],
            "hide_viewport": c.hide_viewport, "hide_render": c.hide_render}


def layer_excl(lc, acc):
    acc[lc.name] = {"exclude": lc.exclude, "hide_viewport": lc.hide_viewport}
    for ch in lc.children:
        layer_excl(ch, acc)
    return acc


rep = {"file": bpy.data.filepath, "blender_version_file": list(bpy.data.version), "blender_running": bpy.app.version_string,
       "scenes": [], "libraries": [], "images": [], "materials": [], "texts": [], "objects": {}, "node_groups": []}
for sc in bpy.data.scenes:
    us = sc.unit_settings
    rep["scenes"].append({"name": sc.name, "unit_system": us.system, "scale_length": us.scale_length, "length_unit": us.length_unit,
                          "camera": sc.camera.name if sc.camera else None, "frame": sc.frame_current,
                          "render_engine": sc.render.engine, "props": {k: str(sc[k])[:300] for k in sc.keys()},
                          "collections": coll_tree(sc.collection),
                          "view_layers": {vl.name: layer_excl(vl.layer_collection, {}) for vl in sc.view_layers}})
for lib in bpy.data.libraries:
    rep["libraries"].append({"name": lib.name, "filepath": lib.filepath})
for im in bpy.data.images:
    d = {"name": im.name, "filepath": im.filepath, "source": im.source, "packed": im.packed_file is not None,
         "size": list(im.size), "users": im.users, "colorspace": im.colorspace_settings.name}
    if im.source == "TILED":
        d["tiles"] = [t.number for t in im.tiles]
    try:
        d["abs_exists"] = os.path.exists(bpy.path.abspath(im.filepath)) if im.filepath else None
    except Exception:
        d["abs_exists"] = None
    rep["images"].append(d)
for m in bpy.data.materials:
    d = {"name": m.name, "users": m.users, "pass_index": m.pass_index, "diffuse": r(m.diffuse_color, 3),
         "library": m.library.filepath if m.library else None, "props": {k: str(m[k])[:200] for k in m.keys()}}
    if m.use_nodes and m.node_tree:
        nodes = []
        for n in m.node_tree.nodes:
            nd = {"type": n.type, "name": n.name}
            if n.type == "TEX_IMAGE" and n.image:
                nd["image"] = n.image.name
            if n.type == "BSDF_PRINCIPLED":
                try:
                    nd["base_color"] = r(n.inputs["Base Color"].default_value, 3)
                    nd["roughness"] = round(n.inputs["Roughness"].default_value, 3)
                    nd["metallic"] = round(n.inputs["Metallic"].default_value, 3)
                    nd["alpha"] = round(n.inputs["Alpha"].default_value, 3)
                    nd["ior"] = round(n.inputs["IOR"].default_value, 3)
                    nd["transmission"] = round(n.inputs["Transmission Weight"].default_value, 3)
                except Exception as e:
                    nd["err"] = str(e)
            if n.type == "GROUP" and n.node_tree:
                nd["group"] = n.node_tree.name
            nodes.append(nd)
        d["nodes"] = nodes
    rep["materials"].append(d)
for t in bpy.data.texts:
    rep["texts"].append({"name": t.name, "lines": len(t.lines), "is_in_memory": t.is_in_memory, "filepath": t.filepath,
                         "use_module": t.use_module, "head": [l.body[:120] for l in t.lines[:5]]})
for ng in bpy.data.node_groups:
    rep["node_groups"].append({"name": ng.name, "type": ng.bl_idname, "users": ng.users})
dg = bpy.context.evaluated_depsgraph_get()
tot = {"tris_eval": 0, "tris_base": 0}
for o in bpy.data.objects:
    d = {"type": o.type, "collections": [c.name for c in o.users_collection], "parent": o.parent.name if o.parent else None,
         "loc": r(o.location), "rot_deg": r([x * 57.2957795 for x in o.rotation_euler], 3), "scale": r(o.scale),
         "hide_viewport": o.hide_viewport, "hide_render": o.hide_render, "hide_get": None,
         "data": o.data.name if o.data else None, "library": o.library.filepath if o.library else None,
         "instance_collection": o.instance_collection.name if o.instance_collection else None,
         "modifiers": [(m.type, m.name, getattr(m, "node_group", None) and m.node_group.name) for m in o.modifiers],
         "props": {k: str(o[k])[:200] for k in o.keys()}}
    try:
        d["hide_get"] = o.hide_get()
    except Exception:
        pass
    if o.type == "MESH":
        me = o.data
        me.calc_loop_triangles()
        d.update(verts=len(me.vertices), faces=len(me.polygons), tris=len(me.loop_triangles),
                 slots=[(s.material.name if s.material else None) for s in o.material_slots],
                 uv=[u.name for u in me.uv_layers], attrs=[(a.name, a.domain, a.data_type) for a in me.attributes
                                                           if not a.name.startswith(".")],
                 mesh_users=me.users)
        cnt = {}
        for p in me.polygons:
            cnt[p.material_index] = cnt.get(p.material_index, 0) + 1
        d["faces_per_slot_index"] = {str(k + 1): v for k, v in sorted(cnt.items())}
        ws = [o.matrix_world @ v.co for v in me.vertices]
        if ws:
            d["bbox_world"] = [r([min(v[i] for v in ws) for i in range(3)], 3), r([max(v[i] for v in ws) for i in range(3)], 3)]
        tot["tris_base"] += len(me.loop_triangles)
        try:
            oe = o.evaluated_get(dg)
            me2 = oe.to_mesh()
            me2.calc_loop_triangles()
            d["tris_eval"] = len(me2.loop_triangles)
            tot["tris_eval"] += d["tris_eval"]
            oe.to_mesh_clear()
        except Exception as e:
            d["eval_err"] = str(e)
    rep["objects"][o.name] = d
rep["totals"] = tot
rep["counts"] = {k: len(getattr(bpy.data, k)) for k in ("objects", "meshes", "materials", "images", "collections", "cameras",
                                                         "lights", "texts", "node_groups", "libraries", "worlds", "scenes")}
json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", out, rep["counts"], tot)
