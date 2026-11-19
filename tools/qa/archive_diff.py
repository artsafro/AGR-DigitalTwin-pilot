"""new-case: read-only, index-corresponding binary FBX/ZIP version gate.

Coordinates/tolerance are in raw FBX file units; bbox is object-local. Model properties
(including transforms) and global settings are separately protected. This is a version
invariant, not a surface correspondence solver or a SINTEZ/delivery certification.
"""
import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path
import sys
import zipfile
import zlib
from pathlib import PurePosixPath

# Also supports direct `python tools/qa/archive_diff.py` outside an editable install.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from adapters.max.agr_tools import export_core
from twinqa import fbx_header as header


def read_tree(data):
    kind, version = header.fbx_header(data)
    if kind != 'binary' or version not in (7400, 7500):
        raise ValueError('unsupported FBX: require binary 7400 or 7500')

    def walk(start, end):
        out = []
        for n in header._iter_nodes(data, start, end, version):
            props = header._parse_props(data, n['props_at'], n['props_end'], n['num_props'])
            if any(code in 'dfilb' for code, _ in props):
                if len(props) != 1 or struct.unpack_from('<I', data, n['props_at'] + 5)[0] not in (0, 1):
                    raise ValueError(f'{n["name"]}: unsupported array encoding/property layout')
            arrays = iter(export_core._array(data, n))
            values = [next(arrays) if code in 'dfilb' else value for code, value in props]
            out.append((n['name'], values, walk(n['props_end'], n['end_offset'])))
        return out

    return walk(27, len(data))


def child(n, label):
    matches = [c for c in n[2] if c[0] == label]
    if len(matches) != 1:
        raise ValueError(f'{n[0]}: require exactly one {label}')
    return matches[0]


def array(n, label):
    values = child(n, label)[1]
    if len(values) != 1 or not isinstance(values[0], list):
        raise ValueError(f'{label}: require an array')
    return values[0]


def scene(data):
    top = ('FBX', [], read_tree(data))
    objs = child(top, 'Objects')[2]
    # Reject NaN/inf anywhere, including transforms, normals and unused material data.
    json.dumps(top, allow_nan=False)
    links = child(top, 'Connections')[2]
    ids = {}
    for n in objs:
        if n[0] not in ('Geometry', 'Model', 'Material', 'Texture', 'Video'):
            raise ValueError(f'unsupported FBX object: {n[0]} {n[1]}')
        if len(n[1]) < 3 or n[1][0] in ids:
            raise ValueError('missing or duplicate FBX object ID')
        ids[n[1][0]] = n
    for c in links:
        if (c[0] != 'C' or len(c[1]) not in (3, 4) or c[1][0] not in ('OO', 'OP') or
                c[1][1] not in ids or (c[1][2] != 0 and c[1][2] not in ids)):
            raise ValueError(f'unsupported/dangling connection: {c[1]}')
    meshes, used = {}, set()
    for model in [n for n in objs if n[0] == 'Model']:
        name = model[1][1].split('\x00', 1)[0].removeprefix('Model::')
        if name in meshes:
            raise ValueError(f'duplicate object name: {name}')
        geoms = [ids[c[1][1]] for c in links if c[1][0] == 'OO' and c[1][2] == model[1][0]
                 and c[1][1] in ids and ids[c[1][1]][0] == 'Geometry']
        if len(geoms) != 1 or model[1][-1] != 'Mesh':
            raise ValueError(f'{name}: unsupported/non-mesh model or geometry connection')
        geom = geoms[0]
        used.add(geom[1][0])
        flat = array(geom, 'Vertices')
        if not flat or len(flat) % 3 or not all(math.isfinite(x) for x in flat):
            raise ValueError(f'{name}: empty, partial or nonfinite vertices')
        verts = [flat[i:i+3] for i in range(0, len(flat), 3)]
        polys = export_core._polygons(array(geom, 'PolygonVertexIndex'))
        if not polys or any(len(p) < 3 or any(i < 0 or i >= len(verts) for i in p) for p in polys):
            raise ValueError(f'{name}: empty or invalid polygons')
        uv = [c for c in geom[2] if c[0] == 'LayerElementUV']
        for layer in [c for c in geom[2] if c[0] == 'Layer']:
            for element in [c for c in layer[2] if c[0] == 'LayerElement']:
                kind = child(element, 'Type')[1][0]
                index = child(element, 'TypedIndex')[1][0]
                if not any(c[0] == kind and c[1] == [index] for c in geom[2]):
                    raise ValueError(f'{name}: unmapped layer {kind}:{index}')
        selections = [(layer[1], element) for layer in geom[2] if layer[0] == 'Layer'
                      for element in layer[2] if element[0] == 'LayerElement']
        uv_names = []
        corners = sum(map(len, polys))
        for layer in uv:
            label = child(layer, 'Name')[1][0]
            coords = array(layer, 'UV')
            mapping = child(layer, 'MappingInformationType')[1][0]
            reference = child(layer, 'ReferenceInformationType')[1][0]
            if mapping not in ('ByPolygonVertex', 'ByVertice', 'ByVertex', 'AllSame'):
                raise ValueError(f'{name}: unsupported UV mapping {mapping}')
            count = {'ByPolygonVertex': corners, 'ByVertice': len(verts), 'ByVertex': len(verts), 'AllSame': 1}[mapping]
            if not coords or len(coords) % 2 or not all(math.isfinite(x) for x in coords):
                raise ValueError(f'{name}: invalid UV coordinates')
            if reference == 'IndexToDirect':
                indices = array(layer, 'UVIndex')
                if len(indices) != count or any(not isinstance(i, int) or i < 0 or i >= len(coords)//2 for i in indices):
                    raise ValueError(f'{name}: invalid UVIndex')
            elif reference != 'Direct' or len(coords) != count * 2:
                raise ValueError(f'{name}: unsupported/partial UV reference {reference}')
            if not isinstance(label, str) or not label or label in uv_names:
                raise ValueError(f'{name}: missing/duplicate UV layer name')
            uv_names.append(label)
        materials = [ids[c[1][1]] for c in links if c[1][0] == 'OO' and c[1][2] == model[1][0]
                     and c[1][1] in ids and ids[c[1][1]][0] == 'Material']
        material_names = [m[1][1].split('\x00', 1)[0].removeprefix('Material::') for m in materials]
        slots = [c for c in geom[2] if c[0] == 'LayerElementMaterial']
        for slot in slots:
            mapping = child(slot, 'MappingInformationType')[1][0]
            ref = child(slot, 'ReferenceInformationType')[1][0]
            values = array(slot, 'Materials')
            if mapping not in ('AllSame', 'ByPolygon') or ref != 'IndexToDirect':
                raise ValueError(f'{name}: unsupported material mapping/reference {mapping}/{ref}')
            if len(values) != (1 if mapping == 'AllSame' else len(polys)):
                raise ValueError(f'{name}: partial material assignment')
            if any(not isinstance(i, int) or i < 0 or i >= len(materials) for i in values):
                raise ValueError(f'{name}: unmapped material slot {values}')
        parents = [ids[c[1][2]][1][1] for c in links if c[1][0] == 'OO' and c[1][1] == model[1][0] and c[1][2] in ids]
        meshes[name] = {'verts': verts, 'polygons': polys, 'uv': uv, 'uv_layers': uv_names,
                        'uv_selection': [s for s in selections if child(s[1], 'Type')[1] == ['LayerElementUV']],
                        'materials': material_names, 'material_data': [(m[1][1:], m[2]) for m in materials],
                        'slots': (slots, [s for s in selections if child(s[1], 'Type')[1] == ['LayerElementMaterial']]),
                        'transforms': (model[2], parents),
                        'other_geometry': [c for c in geom[2] if c[0] not in
                                           ('Vertices', 'PolygonVertexIndex', 'LayerElementUV', 'LayerElementMaterial', 'Layer')]
                        + [s for s in selections if child(s[1], 'Type')[1][0] not in ('LayerElementUV', 'LayerElementMaterial')]}
    if not meshes or any(n[0] == 'Geometry' and n[1][0] not in used for n in objs):
        raise ValueError('empty scene or unconsumed geometry')
    attached = {c[1][1] for c in links if c[1][2] in ids and ids[c[1][2]][0] == 'Model'}
    auxiliary = [(n[0], n[1][1:], n[2]) for n in objs if n[0] in ('Texture', 'Video') or
                 (n[0] == 'Material' and n[1][0] not in attached)]
    for kind, values, _ in auxiliary:
        if kind == 'Material' and re.search(r'\.[0-9]{3,}$', values[0].split('\x00', 1)[0]):
            raise ValueError(f'duplicate suffix: {values[0]}')
    aux_links = [(c[1][0], ids[c[1][1]][1][1], ids[c[1][2]][1][1] if c[1][2] else 'ROOT', c[1][3:])
                 for c in links if ids[c[1][1]][0] in ('Texture', 'Video')]
    metadata = ([n for n in top[2] if n[0] == 'GlobalSettings'], auxiliary, aux_links)
    for m in meshes.values():
        m['scene_metadata'] = hashlib.sha256(json.dumps(metadata, allow_nan=False).encode()).hexdigest()
    return meshes


def summary(m):
    if m is None:
        return None
    return {'vertex_count': len(m['verts']), 'face_count': len(m['polygons']),
            'uv_layers': m['uv_layers'], 'materials': m['materials'], 'scene_metadata_sha256': m['scene_metadata'],
            'uv_sha256': hashlib.sha256(json.dumps(m['uv'], allow_nan=False).encode()).hexdigest(),
            'bbox': [[min(v[k] for v in m['verts']) for k in range(3)],
                     [max(v[k] for v in m['verts']) for k in range(3)]]}


def compare(before, after, tolerance=1e-6, expected=()):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('tolerance must be finite and nonnegative')
    a, b = before, after
    allowed = {}
    for token in expected:
        name, sep, category = token.rpartition(':')
        if not sep:
            name, category = token, 'all'
        if name not in a.keys() | b.keys() or category not in ('all', 'geometry', 'uv'):
            raise ValueError(f'unknown declaration: {token}')
        allowed.setdefault(name, set()).add(category)
    rows, errors = {}, []
    if ({m['scene_metadata'] for m in a.values()} != {m['scene_metadata'] for m in b.values()} or
            any(a[n]['scene_metadata'] != b[n]['scene_metadata'] for n in a.keys() & b.keys())):
        errors.append('scene metadata changed (settings/auxiliary objects/connections)')
    for name in sorted(a.keys() | b.keys()):
        old, new = a.get(name), b.get(name)
        row = {'before': summary(old), 'after': summary(new), 'moved_count': None,
               'above_tolerance_count': None, 'max_displacement': None}
        changed = []
        if old is None or new is None:
            changed.append('inventory')
        else:
            if len(old['verts']) == len(new['verts']):
                distances = [math.dist(x, y) for x, y in zip(old['verts'], new['verts'])]
                if not all(math.isfinite(d) for d in distances):
                    raise ValueError(f'{name}: nonfinite displacement')
                row.update(moved_count=sum(d > 0 and d >= tolerance for d in distances),
                           above_tolerance_count=sum(d > tolerance for d in distances), max_displacement=max(distances))
            if (row['moved_count'] is None or row['moved_count'] or old['polygons'] != new['polygons']
                    or old['other_geometry'] != new['other_geometry']):
                changed.append('geometry')
            if old['uv'] != new['uv'] or old['uv_selection'] != new['uv_selection']:
                changed.append('uv')
            if old['material_data'] != new['material_data'] or old['slots'] != new['slots']:
                changed.append('materials')
            if old['transforms'] != new['transforms']:
                changed.append('transforms')
        for m in (old, new):
            if m:
                for label in [name, *m['materials']]:
                    error = f'duplicate suffix: {label}'
                    if re.search(r'\.[0-9]{3,}$', label) and error not in errors:
                        errors.append(error)
        row['uv_changed'] = 'uv' in changed
        row['displacement_status'] = 'index_corresponding' if row['moved_count'] is not None else 'unmeasured: object/vertex inventory changed'
        row['changes'] = changed
        rows[name] = row
        for category in changed:
            if not ({'all', category} & allowed.get(name, set())):
                errors.append(f'{name}:{category}')
    return {'status': 'fail' if errors else 'pass', 'tolerance': tolerance, 'expected': list(expected), 'objects': rows, 'errors': errors}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    if path.suffix.lower() == '.fbx':
        return {path.name: path.read_bytes()}, {path.name: digest(path)}
    if path.suffix.lower() != '.zip':
        raise ValueError(f'unsupported input: {path}')
    fbxs, members, seen = {}, {}, set()
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 1024**3:
            raise ValueError('archive exceeds 1 GiB uncompressed read budget')
        for entry in archive.infolist():
            name = entry.filename
            parts = PurePosixPath(name).parts
            if (not name or '\\' in name or ':' in name or name.startswith('/') or '..' in parts
                    or name.casefold() in seen or entry.is_dir()):
                raise ValueError(f'unsafe/duplicate/unsupported ZIP member: {name}')
            seen.add(name.casefold())
            with archive.open(entry) as stream:
                members[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
            if name.lower().endswith('.fbx'):
                fbxs[name] = archive.read(entry)
    if not fbxs:
        raise ValueError('archive contains no FBX')
    return fbxs, members


def compare_paths(previous, new, tolerance=1e-6, expected=()):
    previous, new = Path(previous), Path(new)
    if previous.resolve() == new.resolve() or previous.samefile(new):
        raise ValueError('duplicate/aliased input paths')
    hashes = [digest(p) for p in (previous, new)]
    old, old_members = load(previous)
    fresh, new_members = load(new)
    # Combine scenes without losing any object or silently selecting one FBX.
    def collect(files):
        result = {}
        for member, data in files.items():
            for name, m in scene(data).items():
                if name in result:
                    raise ValueError(f'duplicate object across FBXs: {name} in {member}')
                result[name] = m
        return result
    r = compare(collect(old), collect(fresh), tolerance, expected)
    if previous.suffix.lower() == '.zip' or new.suffix.lower() == '.zip':
        for member in sorted(old_members.keys() | new_members.keys()):
            if (member not in old_members or member not in new_members or
                    (not member.lower().endswith('.fbx') and old_members[member] != new_members[member])):
                r['errors'].append(f'member:{member}')
    r['members'] = {'before': old_members, 'after': new_members}
    if hashes != [digest(p) for p in (previous, new)]:
        raise ValueError('input changed during comparison')
    r['inputs'] = {key: {'path': str(p.resolve()), 'sha256': h} for key, p, h in
                   zip(('previous', 'new'), (previous, new), hashes)}
    r['status'] = 'fail' if r['errors'] else 'pass'
    return r


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    parser.add_argument('new', type=Path)
    parser.add_argument('--expect-changed', action='append', default=[])
    parser.add_argument('--tolerance', type=float, default=1e-6)
    parser.add_argument('--report', type=Path, help='New JSON report; never overwrite an existing path')
    args = parser.parse_args(argv)
    try:
        if args.report and (args.report.exists() or args.report.is_symlink() or
                            args.report.resolve() in (args.previous.resolve(), args.new.resolve())):
            raise ValueError('report exists or aliases an input')
        r = compare_paths(args.previous, args.new, args.tolerance, args.expect_changed)
        text = json.dumps(r, allow_nan=False)
        if args.report:
            with args.report.open('x', encoding='utf-8') as stream:
                stream.write(text + '\n')
        print(text)
        return 0 if r['status'] == 'pass' else 1
    except (ValueError, OSError, header._FbxError, zipfile.BadZipFile, struct.error, zlib.error,
            IndexError, KeyError, TypeError, OverflowError, RecursionError) as exc:
        print(json.dumps({'status': 'error', 'errors': [str(exc)]}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
