"""Build the NPM and VPM FBX of one site MAF set in a factory Blender, then read every export back (#313).

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/maf_site_set_build.py -- <config.json> <atlas_uv.json> <atlas.png> <out_dir>

Pattern: new-case: site MAF set build - join, optional Decimate light version, material remap into the shared
512 atlas slots, hard edges by angle, NPM/VPM FBX export and readback. Pure rules live in
tools/library/maf_site_set.py. Inputs are COPIES under <out_dir>/src (the config's source FBX are copied
first by the caller); sources are never written. Writes <out_dir>/{npm,vpm}/<set_id>.fbx and
<out_dir>/build-report.json. Exit 2 when an output exists already (new versioned folder required); exit 3,
before any export, when a material_map misses a source material without an explicit "*" or names a
material outside the atlas.
"""

import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("maf_site_set", ROOT / "tools/library/maf_site_set.py")
mss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mss)

args = sys.argv[sys.argv.index("--") + 1:]
cfg = json.loads(Path(args[0]).read_text(encoding="utf-8"))
atlas = json.loads(Path(args[1]).read_text(encoding="utf-8"))
atlas_png = Path(args[2])
out_dir = Path(args[3])
rects = {name: m["uv"] for name, m in atlas["materials"].items()}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def set_materials():
    image = bpy.data.images.load(str(atlas_png))
    mats = {}
    for name in rects:
        mat = bpy.data.materials.new("MAF_" + name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mats[name] = mat
    return mats


def cleanup(obj, orient=True):
    """Weld coincident vertices (1e-5 m, the readback weld), drop zero-area faces, triangulate (MAF-18).

    Without this a sliver face links two faces into one smooth fan, so Blender's angle smoothing leaves a
    soft edge the welded readback sees as sharper than the threshold.
    """
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    zero = [f for f in bm.faces if f.calc_area() <= 1e-12]
    if zero:
        bmesh.ops.delete(bm, geom=zero, context="FACES")
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    flipped = 0
    if orient:
        bm.verts.index_update()
        bm.faces.ensure_lookup_table()
        coords = [tuple(v.co) for v in bm.verts]
        polys = [[v.index for v in f.verts] for f in bm.faces]
        flips = mss.orient_outward(coords, polys)
        if flips:
            bmesh.ops.reverse_faces(bm, faces=[bm.faces[i] for i in sorted(flips)])
        flipped = len(flips)
    bm.to_mesh(obj.data)
    bm.free()
    return flipped


def flatten_soft_violations(obj, threshold_deg, split_tol_deg=1.0):
    """Flat-shade both faces of any edge sharper than the threshold that still shares corner normals.

    A sharp edge that ends in a vertex with no other sharp edge keeps one smooth fan, so smoothing by angle
    alone leaves it soft; a flat face only turns its edges into split edges, it never adds a soft one.
    """
    me = obj.data
    flat = 0
    for _ in range(5):
        cn = [c.vector.copy() for c in me.corner_normals]
        corner = {}
        edge_faces = {}
        for p in me.polygons:
            for li in p.loop_indices:
                corner[(p.index, me.loops[li].vertex_index)] = cn[li]
                edge_faces.setdefault(me.loops[li].edge_index, []).append(p.index)
        bad = set()
        for ei, faces in edge_faces.items():
            if len(faces) != 2:
                continue
            f0, f1 = faces
            n0, n1 = me.polygons[f0].normal, me.polygons[f1].normal
            if n0.length == 0 or n1.length == 0:
                continue
            dihedral = math.degrees(n0.angle(n1))
            if dihedral <= threshold_deg - 0.5:
                continue
            soft = all(math.degrees(corner[(f0, v)].angle(corner[(f1, v)], 0.0)) <= split_tol_deg
                       for v in me.edges[ei].vertices)
            if soft and (me.polygons[f0].use_smooth or me.polygons[f1].use_smooth):
                bad.update((f0, f1))
        if not bad:
            break
        for f in bad:
            me.polygons[f].use_smooth = False
        flat += len(bad)
        me.update()
    return flat


def slot_names(o):
    return [s.material.name if s.material else "None" for s in o.material_slots] or ["None"]


def preflight(positions):
    """Before any export: refuse existing outputs (exit 2) and incomplete material maps (exit 3)."""
    errors = []
    for pos in positions:
        for role in ("vpm", "npm"):
            fbx_out = out_dir / role / (pos["set_id"] + ".fbx")
            if fbx_out.exists():
                print("refusing to overwrite", fbx_out, file=sys.stderr)
                sys.exit(2)
        reset()
        bpy.ops.import_scene.fbx(filepath=str(out_dir / "src" / Path(pos["source_fbx"]).name))
        names = []
        for o in bpy.data.objects:
            if o.type == "MESH":
                used = {p.material_index for p in o.data.polygons}
                slots = slot_names(o)
                names += [slots[i] if i < len(slots) else "None" for i in sorted(used)]
        try:
            mss.resolve_material_map(names, pos["material_map"], rects)
        except mss.MaterialMapError as err:
            errors.append(pos["set_id"] + ": " + str(err))
    if errors:
        for line in errors:
            print("material_map error:", line, file=sys.stderr)
        sys.exit(3)


def build(pos, ratio, fbx_in, fbx_out):
    reset()
    bpy.ops.import_scene.fbx(filepath=str(fbx_in))
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("no mesh in " + str(fbx_in))
    # source material name per polygon, before joining; the map must cover every name (no silent fallback)
    seen = []
    for o in meshes:
        names = slot_names(o)
        attr = o.data.attributes.new("src_mat", "INT", "FACE")
        for p in o.data.polygons:
            n = names[p.material_index] if p.material_index < len(names) else "None"
            if n not in seen:
                seen.append(n)
            attr.data[p.index].value = seen.index(n)
    resolved = mss.resolve_material_map(seen, pos["material_map"], rects)
    for o in bpy.data.objects:
        o.select_set(o.type == "MESH")
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    for o in list(bpy.data.objects):
        if o is not obj:
            bpy.data.objects.remove(o, do_unlink=True)
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except RuntimeError:
        pass
    tris_before = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    flipped = cleanup(obj)
    if ratio < 1.0:
        mod = obj.modifiers.new("light", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        flipped += cleanup(obj)
    mesh = obj.data
    # material remap into atlas materials
    mats = set_materials()
    order = list(rects)
    mesh.materials.clear()
    for name in order:
        mesh.materials.append(mats[name])
    src = mesh.attributes["src_mat"].data
    wildcard = 0
    for p in mesh.polygons:
        name = seen[src[p.index].value]
        wildcard += name not in pos["material_map"]
        p.material_index = order.index(resolved[name])
    mesh.attributes.remove(mesh.attributes["src_mat"])
    # UV: box projection per face, normalised by the object bounds, mapped inside the slot rect
    while mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[0])
    uv = mesh.uv_layers.new(name="UVMap")
    co = [v.co for v in mesh.vertices]
    lo = [min(c[i] for c in co) for i in range(3)]
    span = [max(max(c[i] for c in co) - lo[i], 1e-9) for i in range(3)]
    for p in mesh.polygons:
        n = p.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        a, b = [i for i in range(3) if i != axis]
        rect = rects[order[p.material_index]]
        for li in p.loop_indices:
            c = co[mesh.loops[li].vertex_index]
            s = min(1.0, max(0.0, (c[a] - lo[a]) / span[a]))
            t = min(1.0, max(0.0, (c[b] - lo[b]) / span[b]))
            uv.data[li].uv = mss.remap_into_rect((s, t), rect, inset=0.02)
    # hard edges by angle
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(pos["smoothing_deg"]), keep_sharp_edges=False)
    flat = flatten_soft_violations(obj, pos["smoothing_deg"])
    obj.name = pos["set_id"] + "_GroundEl"
    mesh.name = obj.name
    fbx_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(fbx_out), use_selection=True, object_types={"MESH"},
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, path_mode="COPY",
                             embed_textures=True, bake_anim=False, add_leaf_bones=False)
    return {"tris_source": tris_before, "source_materials": resolved, "wildcard_faces": wildcard,
            "faces_reversed_outward": flipped,
            "faces_flat_shaded": flat}


def readback(fbx, pos):
    reset()
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    faces, up, tris = [], [], 0
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    names = []
    for o in meshes:
        names.append(o.name)
        me = o.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        uvl = me.uv_layers.active
        m = o.matrix_world
        nm = m.to_3x3().inverted_safe().transposed()
        for p in me.polygons:
            slot = o.material_slots[p.material_index].material if o.material_slots else None
            name = slot.name[4:] if slot and slot.name.startswith("MAF_") else (slot.name if slot else None)
            name = name.split(".")[0] if name else None
            faces.append((name, [tuple(uvl.data[li].uv) for li in p.loop_indices] if uvl else []))
            wn = (nm @ p.normal).normalized()
            pts = [m @ me.vertices[v].co for v in p.vertices]
            for c in pts:
                for i in range(3):
                    lo[i], hi[i] = min(lo[i], c[i]), max(hi[i], c[i])
            up.append((sum(c.z for c in pts) / len(pts), p.area, wn.z))
    size = [hi[i] - lo[i] for i in range(3)]
    out = {"objects": names, "triangles": tris, "bounds_m": [lo, hi], "size_m": size,
           "uv_slots": mss.uv_slot_report(faces, rects), "images": [i.name for i in bpy.data.images]}
    if pos["height_rule"] == "table_top":
        out["table_top_height_m"] = mss.dominant_up_plane([(z - lo[2], a, n) for z, a, n in up])
    return out


preflight(cfg["positions"])
report = {"blender": bpy.app.version_string, "smoothing_deg": cfg["smoothing_deg"], "positions": []}
for pos in cfg["positions"]:
    fbx_in = out_dir / "src" / Path(pos["source_fbx"]).name
    entry = {"set_id": pos["set_id"], "catalogue_id": pos["catalogue_id"]}
    for role, ratio in (("vpm", 1.0), ("npm", pos["decimate_ratio"])):
        fbx_out = out_dir / role / (pos["set_id"] + ".fbx")
        if fbx_out.exists():
            print("refusing to overwrite", fbx_out, file=sys.stderr)
            sys.exit(2)
        entry[role] = build(pos, ratio, fbx_in, fbx_out)
        entry[role]["fbx"] = str(fbx_out).replace("\\", "/")
        entry[role]["readback"] = readback(fbx_out, pos)
    report["positions"].append(entry)
    print("built", pos["set_id"], entry["npm"]["readback"]["triangles"], entry["vpm"]["readback"]["triangles"])
(out_dir / "build-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
