"""Bind a planned diffuse map onto each Ground material of an FBX copy.

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/materials/bind_ground_textures_blender.py -- \
        fingerprint <in.fbx> <out.json>
    blender --background --factory-startup --python-exit-code 1 \
        --python tools/materials/bind_ground_textures_blender.py -- \
        bind <in.fbx> <plan.json> <out.fbx>

new-case: headless Ground binding and exact imported/raw FBX geometry evidence.

The mesh is not edited. fingerprint records triangle count, the raw material_index
layer, world vertex positions and the UV layer. bind only adds a Base Color image.
"""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]


def clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def area3(points):
    a, b, c = points
    return float((b - a).cross(c - a).length) * 0.5


def area2(points):
    a, b, c = points
    return abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) * 0.5


def raw_material_layers(fbx):
    from io_scene_fbx import parse_fbx

    root, _version = parse_fbx.parse(str(fbx))
    layers = []
    objects = next(item for item in root.elems if item.id == b"Objects")
    for geometry in objects.elems:
        if geometry.id != b"Geometry":
            continue
        for layer in geometry.elems:
            if layer.id != b"LayerElementMaterial":
                continue
            fields = {item.id: item for item in layer.elems}
            layers.append({
                "mapping": fields[b"MappingInformationType"].props[0].decode(),
                "reference": fields[b"ReferenceInformationType"].props[0].decode(),
                "ids": list(fields[b"Materials"].props[0]),
            })
    if not layers:
        raise ValueError("raw FBX material layers missing")
    return layers


def fingerprint(fbx, out_json):
    clean()
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    meshes = sorted((obj for obj in bpy.context.scene.objects if obj.type == "MESH"), key=lambda obj: obj.name)
    if not meshes:
        print("no mesh", file=sys.stderr)
        sys.exit(2)
    payload = {"triangles": 0, "material_ids": [], "vertices": [], "uvs": [], "faces": []}
    payload["raw_material_layers"] = raw_material_layers(fbx)
    payload["polygons"] = []
    for obj in meshes:
        mesh = obj.data
        mesh.calc_loop_triangles()
        payload["triangles"] += len(mesh.loop_triangles)
        world = obj.matrix_world
        for vertex in mesh.vertices:
            co = world @ vertex.co
            payload["vertices"].append([co.x, co.y, co.z])
        if not mesh.uv_layers:
            print("no uv", file=sys.stderr)
            sys.exit(2)
        layer = mesh.uv_layers.active.data
        for item in layer:
            payload["uvs"].append([item.uv.x, item.uv.y])
        for poly in mesh.polygons:
            payload["polygons"].append(list(poly.vertices))
            if len(poly.vertices) != 3:
                print("non-triangle face", file=sys.stderr)
                sys.exit(2)
            payload["material_ids"].append(int(poly.material_index))
            material = mesh.materials[poly.material_index] if mesh.materials else None
            name = material.name if material else ""
            slot = name.split("_Ground_", 1)[-1] if "_Ground_" in name else name
            corners = [world @ mesh.vertices[index].co for index in poly.vertices]
            uvs = [layer[index].uv for index in poly.loop_indices]
            payload["faces"].append({"slot": slot, "world_area_m2": area3(corners), "uv_area": area2(uvs)})
    Path(out_json).write_text(json.dumps(payload), encoding="utf-8")


def attach(material, image_path, profile):
    material.use_nodes = True
    tree = material.node_tree
    bsdf = next((node for node in tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
        output = next(node for node in tree.nodes if node.type == "OUTPUT_MATERIAL")
        tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    image = bpy.data.images.load(str(image_path))
    image.name = Path(image_path).name
    image.colorspace_settings.name = "sRGB"
    if profile == "npm":
        image.pack()
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    socket = bsdf.inputs["Base Color"]
    for link in list(socket.links):
        tree.links.remove(link)
    tree.links.new(tex.outputs["Color"], socket)


def bind(fbx, spec_path, out_fbx):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    clean()
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    root = Path(spec["texture_root"])
    by_name = {material.name: material for material in bpy.data.materials}
    for binding in spec["bindings"]:
        material = by_name.get(binding["material"])
        if material is None:
            print(f"missing material {binding['material']}", file=sys.stderr)
            sys.exit(2)
        path = root / binding["file"]
        if not path.is_file():
            print(f"missing map {path}", file=sys.stderr)
            sys.exit(2)
        attach(material, path, spec["profile"])
    embed = spec["profile"] == "npm"
    bpy.ops.export_scene.fbx(
        filepath=str(out_fbx),
        use_selection=False,
        apply_unit_scale=True,
        global_scale=1.0,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="Y",
        axis_up="Z",
        mesh_smooth_type="FACE",
        use_mesh_modifiers=False,
        bake_space_transform=False,
        add_leaf_bones=False,
        path_mode="COPY" if embed else "ABSOLUTE",
        embed_textures=embed,
    )


if not args:
    sys.exit(2)
if args[0] == "fingerprint":
    fingerprint(args[1], args[2])
elif args[0] == "bind":
    bind(args[1], args[2], args[3])
else:
    print("usage: fingerprint <fbx> <json> | bind <fbx> <plan.json> <out.fbx>", file=sys.stderr)
    sys.exit(2)
