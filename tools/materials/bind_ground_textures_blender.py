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
The plan may supply a thumbnail path (relative to the plan or absolute) sourced for
this output; omission records unknown. This does not validate a GeoJSON or preview.
"""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

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
    if Path(out_json).exists():
        raise ValueError("refuse overwrite of existing fingerprint output")
    clean()
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    meshes = sorted((obj for obj in bpy.context.scene.objects if obj.type == "MESH"), key=lambda obj: obj.name)
    if not meshes:
        print("no mesh", file=sys.stderr)
        sys.exit(2)
    payload = {"triangles": 0, "material_ids": [], "vertices": [], "uvs": [], "faces": []}
    payload["raw_material_layers"] = raw_material_layers(fbx)
    payload["polygons"] = []
    payload["collision_geometry"] = []
    for obj in meshes:
        if obj.name.startswith("UCX_"):
            mesh = obj.data
            mesh.calc_loop_triangles()
            payload["collision_geometry"].append({
                "name": obj.name,
                "vertices": [list(obj.matrix_world @ vertex.co) for vertex in mesh.vertices],
                "polygons": [list(poly.vertices) for poly in mesh.polygons],
                "material_ids": [poly.material_index for poly in mesh.polygons],
                "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
                "uv_layers": [[list(item.uv) for item in layer.data] for layer in mesh.uv_layers],
                "triangles": len(mesh.loop_triangles),
            })
            continue
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
            payload["material_ids"].append(int(poly.material_index))
        # Measure the importer's actual tessellation, including concave/nonplanar
        # polygons, without mutating the polygon mesh or its material-ID layer.
        # One density witness per loop triangle prevents polygon-area averaging
        # from hiding an out-of-band half of a quad.
        for triangle in mesh.loop_triangles:
            poly = mesh.polygons[triangle.polygon_index]
            material = mesh.materials[poly.material_index] if mesh.materials else None
            name = material.name if material else ""
            slot = name.split("_Ground_", 1)[-1] if "_Ground_" in name else name
            corners = [world @ mesh.vertices[index].co for index in triangle.vertices]
            uvs = [layer[index].uv for index in triangle.loops]
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
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.blender import ground_fbx_provenance as prov

    fbx, spec_path, out_fbx = map(Path, (fbx, spec_path, out_fbx))
    outputs = [out_fbx, prov.sidecar(out_fbx, prov.EXPORT), prov.sidecar(out_fbx, prov.PLACEMENT)]
    prov.refuse_outputs([fbx, spec_path], outputs)
    plan_bytes = spec_path.read_bytes()
    spec = json.loads(plan_bytes, object_pairs_hook=prov.export_meta.unique_object)
    if not isinstance(spec, dict) or not isinstance(spec.get('bindings'), list) or not spec['bindings']:
        raise ValueError('binding plan needs a nonempty bindings list')
    evidence = prov.GroundEvidence(fbx)
    profile, _ = evidence.check_binder_profile(spec.get('profile'), out_fbx, spec_path)
    thumbnail = evidence.supplied_thumbnail(spec_path, spec['thumbnail']) if 'thumbnail' in spec else None
    thumbnail_digest = prov.export_meta._sha256(thumbnail) if thumbnail is not None else None
    root = Path(spec['texture_root'])
    bindings = {}
    for binding in spec['bindings']:
        name = binding['material']
        if name in bindings:
            raise ValueError(f'duplicate binding for material {name}')
        bindings[name] = root / binding['file']
    inputs = [*bindings.values(), *evidence.paths, spec_path, fbx, out_fbx.resolve().parent / 'export_meta.json']
    if thumbnail is not None:
        inputs.append(thumbnail)
    prov.refuse_outputs(inputs, outputs)
    clean()
    prov.require_finished(bpy.ops.import_scene.fbx(filepath=str(fbx)), 'Ground FBX input import')
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.upper().startswith('UCX')]
    top = prov.render_top(meshes)
    ground = prov.ground_object(meshes)
    address = ground.name[3:] if ground is not None else None
    capture = evidence.capture(ground, top)
    by_name = {material.name: material for material in bpy.data.materials}
    for name, path in bindings.items():
        material = by_name.get(name)
        if material is None:
            print(f"missing material {name}", file=sys.stderr)
            sys.exit(2)
        if not path.is_file():
            print(f"missing map {path}", file=sys.stderr)
            sys.exit(2)
        attach(material, path, profile)
    embed = profile == 'npm'
    # Keep the output basename for export records and embedded media. VPM paths
    # are absolute; NPM media are embedded, so neither route depends on staging.
    with TemporaryDirectory(prefix='.ground-bind-export-', dir=out_fbx.parent) as folder:
        staged = Path(folder) / out_fbx.name
        status = bpy.ops.export_scene.fbx(
            filepath=str(staged), use_selection=False, apply_unit_scale=True, global_scale=1.0,
            apply_scale_options='FBX_SCALE_UNITS', axis_forward='Y', axis_up='Z', mesh_smooth_type='SMOOTH_GROUP',
            use_mesh_modifiers=False, bake_space_transform=False, add_leaf_bones=False,
            path_mode='COPY' if embed else 'ABSOLUTE', embed_textures=embed,
        )
        prov.require_finished(status, 'Ground FBX export')
        reason, top = evidence.readback_placement(capture, staged, out_fbx, bpy)
        _, profile_why = evidence.check_binder_profile(profile, out_fbx, spec_path)
        if plan_bytes != spec_path.read_bytes():
            raise ValueError(f'binding plan changed during export: {spec_path}')
        if thumbnail is not None and prov.export_meta._sha256(thumbnail) != thumbnail_digest:
            raise ValueError(f'supplied thumbnail changed during export: {thumbnail}')
        meta = prov.export_meta.record_export(staged, source=f'{fbx}; binding plan {spec_path}', top=top,
                                             address=address,
                                             profile=profile, profile_provenance=profile_why,
                                             thumbnail=thumbnail if thumbnail is not None else 'unknown',
                                             master=fbx, master_sha256=evidence.digest)
        pairs = [(meta, outputs[1])]
        if reason is None:
            pairs.append((prov.sidecar(staged, prov.PLACEMENT), outputs[2]))
        evidence.assert_unchanged()
        prov.refuse_outputs(inputs, outputs)
        prov.publish([*pairs, (staged, out_fbx)])
    print('GROUND_BIND placement:', 'preserved' if reason is None else f'unknown: {reason}')


if not args:
    sys.exit(2)
if args[0] == "fingerprint":
    fingerprint(args[1], args[2])
elif args[0] == "bind":
    bind(args[1], args[2], args[3])
else:
    print("usage: fingerprint <fbx> <json> | bind <fbx> <plan.json> <out.fbx>", file=sys.stderr)
    sys.exit(2)
