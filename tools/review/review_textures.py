"""new-case: read-only native review-texture gate, not regulatory delivery QA (#1365).

Explicit object/1-based ID scope prevents guessing which finishes are textured.
Unsupported shader routes fail closed; no DCC settings or scene data are changed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


def positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')
    return value


def validate_manifest(value):
    if not isinstance(value, dict) or set(value) != {'ids'} or not isinstance(value['ids'], list) or not value['ids']:
        raise ValueError('scope must contain a nonempty ids list only')
    seen = set()
    for row in value['ids']:
        if not isinstance(row, dict) or not {'object', 'id'} <= set(row) or set(row) - {'object', 'id', 'joint_m', 'tile_m'}:
            raise ValueError(f'unsupported or partial reviewed ID: {row!r}')
        if not isinstance(row['object'], str) or not row['object'].strip() or type(row['id']) is not int or row['id'] < 1:
            raise ValueError(f'invalid object/ID: {row!r}')
        key = row['object'], row['id']
        if key in seen:
            raise ValueError(f'duplicate reviewed ID: {key}')
        seen.add(key)
        if ('joint_m' in row) != ('tile_m' in row):
            raise ValueError(f'joint_m and tile_m must be supplied together: {key}')
        for name in ('joint_m', 'tile_m'):
            if name in row:
                positive(row[name], name)
        if 'joint_m' in row and row['joint_m'] >= row['tile_m']:
            raise ValueError(f'joint must be smaller than tile: {key}')
    return value['ids']


def joint_sampling(row, viewport_limit):
    positive(viewport_limit, 'viewport texture limit')
    positive(row['joint_m'], 'joint_m')
    positive(row['tile_m'], 'tile_m')
    texels = row['joint_m'] / row['tile_m'] * viewport_limit
    # Equality is deliberately review, not an automatic readability guarantee.
    return {'texels': texels, 'status': 'pass' if texels > 2 else 'review',
            'reason': 'joint at/below 2 viewport texels' if texels <= 2 else ''}


def summarize(rows):
    return {'status': 'fail' if any(r['status'] == 'fail' for r in rows) else
            'review' if any(r['status'] == 'review' for r in rows) else 'pass', 'ids': rows}


def image_evidence(bpy, image):
    if image is None:
        raise ValueError('Image Texture has no image')
    packed = bool(image.packed_file) or bool(image.packed_files)
    if image.source not in ('FILE', 'TILED'):
        raise ValueError(f'unsupported image source: {image.source}; save/pack a file image')
    paths = []
    if not packed:
        raw = bpy.path.abspath(image.filepath, library=image.library)
        if not raw:
            raise ValueError(f'empty image path: {image.name}')
        if image.source == 'TILED':
            if '<UDIM>' not in raw or not image.tiles:
                raise ValueError(f'unsupported/empty UDIM image: {image.name}')
            paths = [raw.replace('<UDIM>', str(t.number)) for t in image.tiles]
        else:
            paths = [raw]
        for path in paths:
            if not Path(path).is_file():
                raise ValueError(f'missing image: {path}')
    return {'image': image.name, 'packed': packed, 'files': paths}


def incoming(socket):
    if not socket.is_linked or len(socket.links) != 1:
        raise ValueError(f'{socket.name} needs exactly one link')
    link = socket.links[0]
    node = link.from_node
    visited = set()
    while node.type == 'REROUTE':
        if node.as_pointer() in visited or not node.inputs[0].is_linked:
            raise ValueError('cyclic/empty reroute')
        visited.add(node.as_pointer())
        link = node.inputs[0].links[0]
        node = link.from_node
    if node.mute:
        raise ValueError(f'muted node: {node.name}')
    return node, link.from_socket.name


def check_blender(bpy, manifest):
    rows = []
    for declaration in validate_manifest(manifest):
        row = dict(declaration, status='fail')
        try:
            obj = bpy.context.scene.objects.get(row['object'])
            if obj is None or obj.type != 'MESH':
                raise ValueError(f'unknown/non-mesh object: {row["object"]}')
            index = row['id'] - 1
            if index not in {p.material_index for p in obj.data.polygons}:
                raise ValueError(f'ID {row["id"]} has no faces')
            if index >= len(obj.material_slots) or obj.material_slots[index].material is None:
                raise ValueError(f'unmapped material ID {row["id"]}')
            material = obj.material_slots[index].material
            row['material'] = material.name
            if not material.use_nodes or material.node_tree is None:
                raise ValueError('material has no shader nodes')
            outputs = [n for n in material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
            if len(outputs) != 1:
                raise ValueError('expected one active Material Output')
            shader, output = incoming(outputs[0].inputs['Surface'])
            if shader.type != 'BSDF_PRINCIPLED' or output != 'BSDF':
                raise ValueError('unsupported Surface route; expected Principled BSDF')
            texture, output = incoming(shader.inputs['Base Color'])
            if texture.type != 'TEX_IMAGE' or output != 'Color':
                raise ValueError('Base Color must be linked to Image Texture Color')
            row.update(image_evidence(bpy, texture.image), status='pass')
        except (ValueError, RuntimeError, KeyError, IndexError) as exc:
            row['reason'] = str(exc)
        rows.append(row)
    return summarize(rows)


def max_material(rt, material):
    """Inspect native materials without modifying or activating viewport maps."""
    cls = str(rt.classOf(material))
    properties = {
        'Standardmaterial': ('diffuseMap', 'diffuseMapEnable', 'diffuseMapAmount'),
        'PhysicalMaterial': ('base_color_map', 'base_color_map_on', 'base_weight'),
    }
    if cls not in properties:
        raise ValueError(f'unsupported material class: {cls}')
    slot, enabled, amount = properties[cls]
    for prop in (enabled, amount, 'showInViewport'):
        try:
            value = rt.getProperty(material, prop)
        except (RuntimeError, AttributeError, TypeError) as exc:
            raise ValueError(f'{prop} unavailable on {cls}') from exc
        if prop == amount:
            positive(value, prop)
        elif value is not True:
            raise ValueError(f'{prop} must be true on {cls}')
    tex = rt.getProperty(material, slot)
    map_class = str(rt.classOf(tex))
    if map_class != 'Bitmaptexture':
        raise ValueError(f'diffuse requires plain Bitmaptexture, found {map_class} (MultiTile-only is not viewport reviewable)')
    path = str(tex.filename)
    if not path or not Path(path).is_file():
        raise ValueError(f'missing Bitmap: {path}')
    return {'material': str(material.name), 'file': path, 'width': int(tex.bitmap.width), 'height': int(tex.bitmap.height)}


def check_max(rt, manifest):
    rows = []
    # Getter only. Never SetTextureSizeLimit or other global-setting mutations.
    limit = rt.NitrousGraphicsManager.GetActiveViewportSetting().TextureSizeLimit
    positive(limit, 'viewport texture limit')
    for declaration in validate_manifest(manifest):
        row = dict(declaration, status='fail')
        try:
            obj = rt.getNodeByName(row['object'], exact=True)
            if obj is None:
                raise ValueError(f'unknown object: {row["object"]}')
            mesh = rt.snapshotAsMesh(obj)
            ids = {int(rt.getFaceMatID(mesh, f)) for f in range(1, int(mesh.numfaces) + 1)}
            if row['id'] not in ids:
                raise ValueError(f'ID {row["id"]} has no faces')
            mat = obj.material
            if str(rt.classOf(mat)) == 'Multimaterial':
                mapping = [int(i) for i in mat.materialIDList]
                if mapping.count(row['id']) != 1:
                    raise ValueError(f'unmapped/duplicate material ID {row["id"]}')
                mat = mat.materialList[mapping.index(row['id'])]
            elif ids != {row['id']}:
                raise ValueError(f'multiple reviewed face IDs without Multi/Sub: {sorted(ids)}')
            row.update(max_material(rt, mat), status='pass')
            if 'joint_m' in row:
                effective = min(limit, row['width'], row['height'])
                row['joint'] = joint_sampling(row, effective)
                row['status'] = row['joint']['status']
            else:
                row.update(status='review', reason='joint sampling not measured; declare joint_m/tile_m if applicable')
        except (ValueError, RuntimeError, AttributeError, TypeError) as exc:
            row['reason'] = str(exc)
        rows.append(row)
    result = summarize(rows)
    result['viewport_limit'] = limit
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_report(path, result, inputs):
    path = Path(path).resolve()
    for source in inputs:
        source = Path(source).resolve()
        if path == source or (path.exists() and source.exists() and path.samefile(source)):
            raise ValueError(f'report aliases input: {source}')
    data = json.dumps(result, indent=2, allow_nan=False) + '\n'
    # Exclusive create: occupied/stale/foreign reports are never reused or deleted.
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(data)


def run_max(manifest_path, report_path):
    """Run inside Max's Python; read current scene only, return non-pass as nonzero."""
    from pymxs import runtime as rt
    manifest = Path(manifest_path)
    before = digest(manifest)
    result = check_max(rt, json.loads(manifest.read_text(encoding='utf-8')))
    result.update(application='3ds Max', version=str(rt.maxVersion()), scene=str(rt.maxFilePath) + str(rt.maxFileName),
                  units=str(rt.units.SystemType), dirty=bool(rt.getSaveRequired()), scope_sha256=before)
    if digest(manifest) != before:
        raise ValueError('scope changed during check')
    write_report(report_path, result, [manifest, result['scene']] if result['scene'] else [manifest])
    return 0 if result['status'] == 'pass' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--scope', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    import bpy
    if bpy.app.version < (5, 1, 2):
        raise ValueError('Blender 5.1.2+ required')
    if args.scene.suffix.lower() != '.blend':
        raise ValueError('expected .blend file')
    if args.report.exists() or args.report.resolve() in (args.scene.resolve(), args.scope.resolve()):
        raise ValueError('report must be a new path distinct from scene and scope')
    hashes = [digest(p) for p in (args.scene, args.scope)]
    manifest = json.loads(args.scope.read_text(encoding='utf-8'))
    validate_manifest(manifest)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    result = check_blender(bpy, manifest)
    result.update(application='Blender', version=bpy.app.version_string, scene=str(args.scene.resolve()),
                  units=bpy.context.scene.unit_settings.system, scene_sha256=hashes[0], scope_sha256=hashes[1])
    if hashes != [digest(p) for p in (args.scene, args.scope)]:
        raise ValueError('input changed during check')
    write_report(args.report, result, [args.scene, args.scope])
    print(json.dumps(result))
    if result['status'] != 'pass':
        # Blender --python-exit-code propagates Python errors, not sys.exit().
        raise RuntimeError('review textures: ' + result['status'])
    return 0


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
