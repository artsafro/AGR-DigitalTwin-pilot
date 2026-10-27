"""Blender (bpy) side of the building-body variants (#727): write a kernel mesh as FBX, or build the body with
Geometry Nodes from the shared level contours and write it as FBX.

Pattern: new-case: Blender writer + Geometry Nodes extrude/union for the building-body methods class.

    blender --background --factory-startup --python-exit-code 1 --python body_blender.py -- \\
        <mode: export-mesh | gn-union> <input .json> <out .fbx> <object name>

export-mesh: <input> = {"vertices": [[x,y,z]...], "triangles": [[a,b,c]...]} (our kernel's prisms).
gn-union:    <input> = contours.json (tools/methods/body/contours.py); every band polygon becomes a cap face
             at z0 (mathutils polyfill, holes kept), a Geometry Nodes tree extrudes each cap by its band
             height (Extrude Mesh, offset = named face attribute), joins the flipped caps as bottoms, and unions all prisms (Mesh Boolean, Exact,
             self intersection), the modifier is applied, the result triangulated.
Writes <out>.variant.json {ok, wall_time_s (build + export, after the inputs are read), triangles, blender}.
Never writes next to an input: the caller passes a new path.
"""
import json
import sys
import time
import traceback
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon


def _clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _material(obj, name):
    mat = bpy.data.materials.new(name)
    obj.data.materials.append(mat)


def _export(obj, out: Path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE",
                             use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False)


def export_mesh(data: dict, out: Path, name: str) -> int:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in data["vertices"]], [], [tuple(t) for t in data["triangles"]])
    me.validate()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    _material(obj, f"M_{name}_1")
    _export(obj, out)
    return len(me.polygons)


def _gn_tree():
    ng = bpy.data.node_groups.new("BodyExtrudeUnion", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    attr = n.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = "band_h"
    comb = n.new("ShaderNodeCombineXYZ")
    ext = n.new("GeometryNodeExtrudeMesh")
    ext.mode = "FACES"
    ext.inputs["Individual"].default_value = False
    boo = n.new("GeometryNodeMeshBoolean")
    boo.operation = "UNION"
    boo.solver = "EXACT"
    if "Self Intersection" in boo.inputs:
        boo.inputs["Self Intersection"].default_value = True
    flip, join = n.new("GeometryNodeFlipFaces"), n.new("GeometryNodeJoinGeometry")
    weld = n.new("GeometryNodeMergeByDistance")
    weld.inputs["Distance"].default_value = 1e-5
    merge = n.new("GeometryNodeMergeByDistance")
    merge.inputs["Distance"].default_value = 0.001
    links = ng.links
    links.new(attr.outputs[0], comb.inputs["Z"])
    links.new(gin.outputs[0], ext.inputs["Mesh"])
    links.new(comb.outputs[0], ext.inputs["Offset"])
    links.new(gin.outputs[0], flip.inputs["Mesh"])  # the bottom cap: Extrude Mesh moves the caps up, open below
    links.new(flip.outputs[0], join.inputs[0])
    links.new(ext.outputs["Mesh"], join.inputs[0])
    links.new(join.outputs[0], weld.inputs[0])
    links.new(weld.outputs[0], boo.inputs["Mesh 2"] if "Mesh 2" in boo.inputs else boo.inputs[0])
    links.new(boo.outputs[0], merge.inputs[0])
    links.new(merge.outputs[0], gout.inputs[0])
    return ng


def gn_union(contours: dict, out: Path, name: str) -> int:
    bm = bmesh.new()
    heights = []
    for band in contours["bands"]:
        z0, h = float(band["z0"]), float(band["z1"]) - float(band["z0"])
        for poly in band["polygons"]:
            rings = [[Vector((x, y, z0)) for x, y in ring] for ring in [poly["exterior"], *poly["holes"]]]
            flat = [v for ring in rings for v in ring]
            verts = [bm.verts.new(v) for v in flat]
            for tri in tessellate_polygon(rings):
                face = bm.faces.new([verts[i] for i in tri])
                heights.append(h)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)  # caps of one polygon share their ring vertices
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:  # cap normal up: Extrude Mesh moves the caps to the top (+Z offset), the flipped copy is the bottom
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if len(me.polygons) != len(heights):
        raise RuntimeError(f"{len(me.polygons)} cap faces for {len(heights)} heights")
    a = me.attributes.new("band_h", "FLOAT", "FACE")
    a.data.foreach_set("value", heights)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("BodyExtrudeUnion", "NODES")
    mod.node_group = _gn_tree()
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for key in list(obj.data.attributes.keys()):
        if key == "band_h":
            obj.data.attributes.remove(obj.data.attributes[key])
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=0.0017, verts=bm.verts, edges=bm.edges)  # coplanar boolean seams
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.materials.clear()
    _material(obj, f"M_{name}_1")
    _export(obj, out)
    return len(obj.data.polygons)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    mode, src, out, name = argv[0], Path(argv[1]), Path(argv[2]), argv[3]
    report = {"ok": False, "mode": mode, "blender": bpy.app.version_string}
    rep = out.with_name(out.name + ".variant.json")
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
        _clear()
        t0 = time.perf_counter()
        tris = export_mesh(data, out, name) if mode == "export-mesh" else gn_union(data, out, name)
        report.update(ok=out.is_file(), wall_time_s=round(time.perf_counter() - t0, 3), triangles=tris)
        if mode == "export-mesh" and "kernel_s" in data:
            report["wall_time_s"] = round(report["wall_time_s"] + float(data["kernel_s"]), 3)
            report["kernel_s"] = data["kernel_s"]
    except Exception as exc:  # noqa: BLE001 - reported, the caller appends no row
        report["error"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    rep.write_text(json.dumps(report), encoding="utf-8")
    print("BODY_BLENDER", json.dumps(report))
    sys.exit(0 if report["ok"] else 1)


main()
