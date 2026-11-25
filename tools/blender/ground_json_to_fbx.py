"""Blender headless: Ground mesh JSON (dt_ai.geometry.ground_cake.mesh_to_dict) -> FBX, and FBX readback.

Pattern: n/a | new-case: Ground master JSON to FBX with GND-11 names and GND-12 pivot (issue #295).

  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- build <mesh.json> <out.fbx> <Address> [<crs> [<source_id>]] [--profile npm|vpm]
  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- readback <in.fbx> <mesh.json> <report.json> [<tex_px> <lo> <hi>]
  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- render <in.fbx> <out_dir> <report.json>

build: object SM_<Address>_Ground, materials M_<Address>_Ground_<Slot> in the JSON slot order, one UV set,
GND-12 / V013 placement: object origin at FBX zero, the mesh is shifted so that its X/Y bounding-box centre is the
origin (Z unchanged: absolute heights, project zero = 0); the MSK-77 offset of that origin is written by code to
<out.fbx>.placement.json ([D126]) and added back by readback. It also writes the export-time derivation record
<out.fbx>.derivation.json (#1525, [D328]): role `ground`, master = the mesh JSON (its own source, hashed before it is
read; a change during the build is refused); `agr build-manifest build --master ground=<mesh.json>` reads it.
The stable source_id defaults to <Address>.ground.mesh, independent of source filename/revision.
For independent meshes use build <json> <fbx> <Address> <crs> <source_id>; preserve the id on revisions.
Profile (#1844): `--profile npm|vpm` is recorded in <out.fbx>.export_meta.json (the sidecar beside the FBX, with
its SHA-256; nothing is embedded in the FBX). A declared npm/vpm in <out dir>/export_meta.json that differs is
refused before any write. Legacy calls without --profile keep the previous 'vpm' and its provenance says it is a
legacy default; the NPM ZIP (tools/derive/package_npm.py) never binds such a record, so NPM needs --profile npm.
readback: in a clean process, imports the FBX and compares triangles, per-face material index (raw
material_index layer mapped through slot names; by face order and, via ground_readback_match.py, by the face centre
over the face's own degree with explicit match coverage, #1837), world vertex positions (sorted), unit scale, open edges
and normals facing down on the surface; with <tex_px lo hi> also the texel density (px per linear metre) of every
surface face (non-Skirt material) measured on the imported mesh.
For an explicit, hash-bound VPM export record, compares tiles by exact material name against the supplied
source mesh JSON (its original slots and UVs), independently of the optional density measurement. Missing
evidence is not_measured. Readback reports must be written to a new path.
render: Face Orientation equivalent (Cycles emission: front green, back red via the Backfacing attribute) from fixed
cameras (top orthographic + four 45 degree obliques around the bounding box); counts red pixels per PNG.
"""
import math
import json
import sys
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "udimtile_core_ground_readback", Path(__file__).resolve().parents[2] / "adapters/max/agr_tools/udimtile_core.py")
assert _spec is not None and _spec.loader is not None
_udimtile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_udimtile)
_mspec = importlib.util.spec_from_file_location("ground_readback_match", Path(__file__).resolve().with_name(
    "ground_readback_match.py"))
assert _mspec is not None and _mspec.loader is not None
_match = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(_match)

import bpy
import bmesh
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]


def clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 1.0


def build(src, out, address, crs="MSK-77", source_id=None, *, profile=None):
    if crs not in ("SYNTHETIC_LOCAL", "MSK-77"):
        raise ValueError(f"unsupported crs {crs!r}; expected SYNTHETIC_LOCAL or MSK-77")
    import os
    root = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, root)
    from adapters.max.agr_tools import build_manifest as bm
    from adapters.max.agr_tools.export_meta import record_export, resolve_export_profile
    # #1844: the delivery profile is the caller's explicit choice, checked against the package record
    # <out dir>/export_meta.json before any write; without --profile the legacy 'vpm' is kept and labelled as such.
    try:
        profile, profile_why = resolve_export_profile(profile, out, legacy_default="vpm", source=str(src))
    except ValueError as exc:
        raise SystemExit(f"refused: {exc}")
    # [D328] / #1525: the Ground FBX keeps its own master = this mesh JSON. Hash it before reading; the derivation
    # record <out>.derivation.json (beside the FBX, like .placement.json) is refused before any write if it exists.
    bm._source_id(address + '.ground.mesh' if source_id is None else source_id)
    src_sha = bm.sha256_file(src)
    if os.path.normcase(os.path.realpath(out)) == os.path.normcase(os.path.realpath(src)):
        raise SystemExit(f"output {out} is the input mesh JSON")
    record = os.path.abspath(out) + bm.DERIVATION_SUFFIX
    if os.path.lexists(record) or os.path.lexists(record + ".partial"):
        raise SystemExit(f"derivation record {record} already exists; build into a new version")
    d = json.load(open(src, encoding="utf-8"))
    clean()
    vs = d["verts"]
    xs = [v[0] for v in vs]
    ys = [v[1] for v in vs]
    piv = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0)
    me = bpy.data.meshes.new(f"SM_{address}_Ground")
    me.from_pydata([(x - piv[0], y - piv[1], z) for x, y, z in vs], [], d["faces"])
    for s in d["slots"]:
        me.materials.append(bpy.data.materials.new(f"M_{address}_Ground_{s}"))
    me.polygons.foreach_set("material_index", d["mat"])
    uvl = me.uv_layers.new(name="UVMap")
    flat = [c for f in d["uv"] for corner in f for c in corner]
    uvl.data.foreach_set("uv", flat)
    me.update()
    ob = bpy.data.objects.new(f"SM_{address}_Ground", me)
    bpy.context.scene.collection.objects.link(ob)
    json.dump({"fbx": out, "crs": crs,
               "origin_msk77_xyz": list(piv), "mesh_xyz = msk77_xyz - origin_msk77_xyz": True,
               "object_location": [0.0, 0.0, 0.0]}, open(out + ".placement.json", "w", encoding="utf-8"), indent=1)
    bpy.ops.export_scene.fbx(filepath=out, use_selection=False, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="Y", axis_up="Z",
                             mesh_smooth_type="SMOOTH_GROUP", use_mesh_modifiers=False, bake_space_transform=False,
                             add_leaf_bones=False, path_mode="AUTO")
    record_export(out, source=str(src), top=float(max(v[2] for v in vs)), address=address + '_Ground', profile=profile,
                  profile_provenance=profile_why)
    record = bm.write_export_derivation([out], src, os.path.dirname(os.path.abspath(out)), bm.git_commit(root),
                                        master_sha256=src_sha, inputs=[src], role="ground",
                                        source_id=address + '.ground.mesh' if source_id is None else source_id)
    print(json.dumps({"built": out, "pivot": piv, "verts": len(vs), "faces": len(d["faces"]),
                      "derivation": record, "master_sha256": src_sha}))


def _readback_profile(fbx, sidecar):
    """Use only an explicit export profile bound to the imported FBX, never the filename grammar."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from adapters.max.agr_tools.export_meta import _sha256, load_meta

    try:
        meta = load_meta(sidecar)
    except ValueError as exc:
        return {}, str(exc)
    if (meta.get('profile') not in ('npm', 'vpm') or
            ': explicit exporter profile argument' not in meta.get('provenance', {}).get('profile', '')):
        return {}, 'no explicit FBX export profile'
    if meta.get('exported_sha256', {}).get(Path(fbx).name) != _sha256(fbx):
        return {}, 'export profile record does not match the FBX bytes'
    return meta, None


def _ground_face_tile(uv):
    # Keep the reader's existing lower-bound containment and float32 tolerance (not a new UV policy).
    if len(uv) < 3 or any(len(c) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in c)
                          for c in uv):
        raise ValueError('expected finite (u, v) corners')
    eps = _udimtile.FACE_TOL
    tu, tv = (math.floor(min(c[axis] for c in uv) + eps) for axis in (0, 1))
    if any(max(c[axis] for c in uv) > cell + 1 + eps for axis, cell in enumerate((tu, tv))):
        raise _udimtile.UdimCrossTileError('face crosses a UDIM tile boundary')
    return _udimtile.udim_of_cell(tu, tv)


def _expected_tiles(d, address):
    """Master UV coverage by exporter material name; never infer it from the candidate UV or FBX filename."""
    uv = d.get('uv')
    if uv is None or uv == []:
        return {}, 'source mesh JSON has no UV evidence'
    if not address or address == 'unknown':
        return {}, 'no recorded material address'
    if len(d['slots']) != len(set(d['slots'])):
        raise ValueError('duplicate source slots: ' + repr(d['slots']))
    if not isinstance(uv, list) or len(uv) != len(d['faces']) or len(d['mat']) != len(d['faces']):
        raise ValueError('source needs one UV row and one material slot per face')
    by_material = {}
    for i, (face, slot_index, corners) in enumerate(zip(d['faces'], d['mat'], uv)):
        if type(slot_index) is not int or not 0 <= slot_index < len(d['slots']):
            raise ValueError(f'unmapped source slot {slot_index!r} on face {i}')
        slot = d['slots'][slot_index]
        if slot == 'Skirt':
            continue
        name = f'M_{address}_{slot}'
        try:
            if not isinstance(corners, list) or len(corners) != len(face):
                raise ValueError('one UV pair required per corner')
            tile = _ground_face_tile(corners)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f'source {name}, face {i}: {exc}') from exc
        by_material.setdefault(name, set()).add(tile)
    return {name: sorted(tiles) for name, tiles in sorted(by_material.items())}, None


def _readback_uv(o, d, meta, profile_reason, tex, mesh_count):
    me = o.data
    npm = meta.get('profile') == 'npm'
    if npm and not tex:
        return {}
    active = me.uv_layers.active
    dens, by_material, invalid = [], {}, {}
    straddle = mirrored = 0
    px, lo, hi = map(float, tex) if tex else (0.0, 0.0, 0.0)
    address = meta.get('address')
    if active is not None:
        for p in me.polygons:
            name = me.materials[p.material_index].name
            if (name == f'M_{address}_Skirt' if address else name.endswith('_Skirt')):
                continue
            seen = by_material.setdefault(name, set())
            li = list(p.loop_indices)
            try:
                u = [tuple(active.data[i].uv) for i in li]
            except IndexError as exc:
                invalid.setdefault(name, {})[p.index] = str(exc)
                continue
            try:
                seen.add(_ground_face_tile(u))
            except _udimtile.UdimCrossTileError as exc:
                straddle += 1
                invalid.setdefault(name, {})[p.index] = str(exc)
                # Keep measuring winding and density of straddlers, as before.
            except (ValueError, OverflowError) as exc:
                invalid.setdefault(name, {})[p.index] = str(exc)
                continue
            w = [o.matrix_world @ me.vertices[me.loops[i].vertex_index].co for i in li]
            sa = sum((u[k][0] - u[0][0]) * (u[k + 1][1] - u[0][1]) - (u[k][1] - u[0][1]) * (u[k + 1][0] - u[0][0])
                     for k in range(1, len(u) - 1))
            crosses = [(w[k] - w[0]).cross(w[k + 1] - w[0]) for k in range(1, len(w) - 1)]
            fa = sum(c.dot(p.normal) for c in crosses)
            if sa * fa < 0 and abs(sa) > 1e-14:
                mirrored += 1
            a3 = sum(c.length for c in crosses) / 2
            a2 = abs(sa) / 2
            if tex and a3 > 1e-12 and a2 > 1e-16:
                dens.append(px * math.sqrt(a2 / a3))
    observed = {name: sorted(tiles) for name, tiles in sorted(by_material.items())}
    uv_report = {'straddling': straddle, 'tiles': sorted({tile for ts in observed.values() for tile in ts}),
                 'mirrored_faces': mirrored}
    out = {'uv_tiles': uv_report}
    if tex and active is not None:
        out['density'] = {'tex_px': px, 'band': [lo, hi], 'faces': len(dens),
                          'min': min(dens, default=None), 'max': max(dens, default=None),
                          'faces_below': sum(v < lo for v in dens), 'faces_above': sum(v > hi for v in dens)}
    if npm:
        return out

    expected, differences = {}, {}
    reason = profile_reason
    status = 'not_measured'
    if reason is None:
        try:
            expected, reason = _expected_tiles(d, meta.get('address'))
        except ValueError as exc:
            status, reason = 'fail', str(exc)
    if reason is None and not observed:
        reason = 'imported Ground has no applicable UV evidence'
    if expected and observed:
        differences = {name: {'expected': expected.get(name, []), 'observed': observed.get(name, [])}
                       for name in sorted(expected.keys() | observed.keys()) if expected.get(name) != observed.get(name)}
        status = 'fail' if differences or invalid else 'pass'
    if meta.get('profile') == 'vpm' and mesh_count != 1:
        status, reason = 'fail', f'expected one Ground mesh, imported {mesh_count}'
    if status == 'not_measured' and reason is None:
        reason = 'source mesh JSON has no applicable UV evidence'
    uv_report['by_material'] = observed
    uv_report['udim_assignment'] = {'status': status, 'reason': reason, 'expected': expected,
                                    'differences': differences, 'invalid_imported_faces_by_material': invalid}
    return out


def readback(fbx, src, rep, *tex):
    import os
    pl = fbx + '.placement.json'
    meta_path = fbx + '.export_meta.json'
    if os.path.lexists(rep) or any(Path(rep).resolve() == Path(path).resolve()
                                    for path in (fbx, src, pl, meta_path)):
        raise ValueError(f'readback report must be a new path: {rep}')
    d = json.load(open(src, encoding="utf-8"))
    off = Vector(json.load(open(pl, encoding="utf-8"))["origin_msk77_xyz"]) if os.path.exists(pl) else Vector((0, 0, 0))
    clean()
    meta, profile_reason = _readback_profile(fbx, meta_path)
    bpy.ops.import_scene.fbx(filepath=fbx)
    if meta:
        from adapters.max.agr_tools.export_meta import _sha256
        if meta['exported_sha256'][Path(fbx).name] != _sha256(fbx):
            raise ValueError(f'FBX changed during Ground readback: {fbx}')
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    out = {"fbx": fbx, "objects": [o.name for o in obs], "unit_scale_length": bpy.context.scene.unit_settings.scale_length}
    o = obs[0]
    out["object_scale"] = list(o.scale)
    out["object_location"] = [round(c, 4) for c in o.location]
    out["object_rotation"] = [round(c, 6) for c in o.rotation_euler]
    me = o.data
    from mathutils import Matrix
    mw = Matrix.Translation(off) @ o.matrix_world  # back to MSK-77 for the comparison with the master JSON
    out["placement_offset"] = list(off)
    out["materials"] = [m.name for m in me.materials]
    out["triangles"] = sum(len(p.vertices) - 2 for p in me.polygons)
    out["faces_expected"] = len(d["faces"])
    # raw material index per face -> slot name; compare against the JSON by face centre (FBX may reorder).
    # #1837: the source centre divides by the face's own degree (quad /4); coverage is reported, not inferred.
    imported = [(tuple(round(v, _match.NDIGITS) for v in (mw @ p.center)),
                 me.materials[p.material_index].name.split("_Ground_", 1)[-1], (mw.to_3x3() @ p.normal).z)
                for p in me.polygons]
    out.update(_match.match_by_centre(d, imported))
    # by face order (the FBX importer keeps polygon order): raw material_index -> slot name vs JSON
    names = [m.name.split("_Ground_", 1)[-1] for m in me.materials]
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get("material_index", idx)
    out["material_mismatch_by_order"] = (sum(1 for i, mi in zip(idx, d["mat"]) if names[i] != d["slots"][mi])
                                         if len(idx) == len(d["mat"]) else "count differs")
    bm = bmesh.new()
    bm.from_mesh(me)
    out["open_edges"] = sum(1 for e in bm.edges if e.is_boundary)
    out["nonmanifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    zs = [(mw @ v.co).z for v in me.vertices]
    xs = [(mw @ v.co).x for v in me.vertices]
    out["world_bbox"] = {"x": [min(xs), max(xs)], "z": [min(zs), max(zs)]}
    out["uv_layers"] = [u.name for u in me.uv_layers]
    out.update(_readback_uv(o, d, meta, profile_reason, tex, len(obs)))
    with open(rep, 'x', encoding='utf-8') as stream:
        json.dump(out, stream, indent=1)
    print(json.dumps(out))


def render(fbx, out_dir, rep):
    import os
    clean()
    bpy.ops.import_scene.fbx(filepath=fbx)
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    mat = bpy.data.materials.new("FaceOrientation")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.inputs[1].default_value = (0, 1, 0, 1)  # front
    mix.inputs[2].default_value = (1, 0, 0, 1)  # back
    em = nt.nodes.new("ShaderNodeEmission")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
    nt.links.new(mix.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], outn.inputs[0])
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for o in obs:
        for i in range(len(o.material_slots)):
            o.material_slots[i].material = mat
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = [min(a, b) for a, b in zip(lo, w)]
            hi = [max(a, b) for a, b in zip(hi, w)]
    c = Vector([(a + b) / 2 for a, b in zip(lo, hi)])
    size = max(hi[0] - lo[0], hi[1] - lo[1])
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 1024
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("W")
    sc.world.color = (0, 0, 0)
    cam_d = bpy.data.cameras.new("C")
    cam = bpy.data.objects.new("C", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    views = {"top": (c + Vector((0, 0, size)), True)}
    for k, az in enumerate((45, 135, 225, 315)):
        r = math.radians(az)
        views[f"oblique{az}"] = (c + Vector((math.cos(r) * size, math.sin(r) * size, size)), False)
    os.makedirs(out_dir, exist_ok=True)
    res = {"fbx": fbx, "views": {}}
    for name, (pos, ortho) in views.items():
        cam.location = pos
        cam_d.type = "ORTHO" if ortho else "PERSP"
        cam_d.ortho_scale = size * 1.05
        cam_d.clip_end = size * 10
        d = c - pos
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(out_dir, f"face_orientation_{name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path)
        px = list(img.pixels)
        red = green = 0
        for i in range(0, len(px), 4):
            r, g = px[i], px[i + 1]
            if r > 0.5 and g < 0.2:
                red += 1
            elif g > 0.5 and r < 0.2:
                green += 1
        res["views"][name] = {"png": path, "back_px": red, "front_px": green, "pixels": len(px) // 4}
        bpy.data.images.remove(img)
    json.dump(res, open(rep, "w", encoding="utf-8"), indent=1)
    print(json.dumps(res))


if args[0] == "build":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from adapters.max.agr_tools.export_meta import pop_profile_option
    try:
        _rest, _profile = pop_profile_option(args[1:])
    except ValueError as exc:
        raise SystemExit(f"refused: {exc}")
    build(*_rest, profile=_profile)
elif args[0] == "readback":
    readback(*args[1:])
elif args[0] == "render":
    render(*args[1:4])
else:
    raise SystemExit("usage: build <json> <fbx> <Address> | readback <fbx> <json> <report> [px lo hi] | render <fbx> <dir> <report>")
