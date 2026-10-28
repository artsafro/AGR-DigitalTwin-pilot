"""new-case: checked FBX export for AGR Tools 0.4.0.

Pattern: new-case. Gates run in a fixed order on the export copy description:
hygiene, MatID, xView, UCX audit when pieces exist, then a texel readout that
is reported and does not by itself refuse the file. A failing gate writes
nothing. The written FBX is read back with twinqa.fbx_header; object,
triangle, material and unit-scale counts must equal the dry-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import zlib
from pathlib import Path

UNIT_SCALE = 100.0  # centimetres per file unit; 100 means 1 file unit = 1 m
UP_AXIS = 2  # Z-up
AXIS_NAME = {0: 'X-up', 1: 'Y-up', 2: 'Z-up'}
SCENE_KEYS = {'objects', 'ucx', 'units', 'axis'}
OBJECT_KEYS = {'name', 'handle', 'material', 'material_ids', 'vertices', 'faces',
               'hygiene', 'slot_gaps', 'texel'}
PIECE_KEYS = {'name', 'verts', 'tris'}
PLAN_KEYS = {'target', 'report', 'units', 'axis', 'unit_scale_factor', 'object_count',
             'triangle_count', 'material_count', 'object_names', 'triangles_by_name',
             'gates', 'dropped', 'texel', 'readback', 'stopped', 'digest'}
GATE_ORDER = ('cleanup', 'matid', 'xview', 'ucx', 'texel')


def _plain(value):
    """JSON-safe copy. numpy scalars become Python numbers; equality with the tool is kept."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    module = type(value).__module__
    if module == 'numpy':
        name = type(value).__name__
        if 'float' in name:
            return float(value)
        if 'int' in name or 'uint' in name:
            return int(value)
    raise ValueError('unsupported value ' + type(value).__name__)


def _finite_point(point, label, index):
    if isinstance(point, (str, bytes)) or not isinstance(point, (list, tuple)) or len(point) != 3:
        raise ValueError(f'partial {label} {index}')
    out = []
    for coord in point:
        if isinstance(coord, bool) or not isinstance(coord, (int, float)):
            raise ValueError(f'partial {label} {index}')
        number = float(coord)
        if not math.isfinite(number):
            raise ValueError(f'non-finite {label} {index}')
        out.append(number)
    return out


def _triangles(faces, vertex_count, label):
    if isinstance(faces, (str, bytes)) or not isinstance(faces, (list, tuple)) or not faces:
        raise ValueError(f'empty {label}')
    out = []
    for index, face in enumerate(faces):
        if isinstance(face, (str, bytes)) or not isinstance(face, (list, tuple)) or len(face) != 3:
            raise ValueError(f'unsupported polygon {label} {index}')
        tri = []
        for corner in face:
            if isinstance(corner, bool) or type(corner) is not int:
                raise ValueError(f'partial {label} {index}')
            if corner < 0 or corner >= vertex_count:
                raise ValueError(f'partial {label} {index}')
            tri.append(corner)
        out.append(tri)
    return out


def _require_keys(mapping, allowed, label):
    if not isinstance(mapping, dict):
        raise ValueError(f'partial {label}')
    missing = sorted(allowed - set(mapping))
    extra = sorted(set(mapping) - allowed)
    if missing:
        raise ValueError('unmapped key ' + missing[0])
    if extra:
        raise ValueError('unmapped key ' + extra[0])


def _validate_scene(scene):
    _require_keys(scene, SCENE_KEYS, 'scene')
    if scene['units'] != 'm':
        raise ValueError(f"unmapped units {scene['units']!r}")
    if scene['axis'] != 'Z-up':
        raise ValueError(f"unmapped axis {scene['axis']!r}")
    objects = scene['objects']
    pieces = scene['ucx']
    if not isinstance(objects, list) or not isinstance(pieces, list):
        raise ValueError('partial scene')
    if not objects and not pieces:
        raise ValueError('empty target set')
    if not objects:
        raise ValueError('empty render set')
    names, handles = [], []
    validated = []
    for obj in objects:
        _require_keys(obj, OBJECT_KEYS, 'object')
        name = obj['name']
        if not isinstance(name, str) or not name.strip():
            raise ValueError('partial object name')
        handle = obj['handle']
        if isinstance(handle, bool) or type(handle) is not int or handle <= 0:
            raise ValueError(f'invalid handle {handle!r}')
        if name in names:
            raise ValueError(f'duplicate name {name}')
        if handle in handles:
            raise ValueError(f'duplicate handle {handle}')
        names.append(name)
        handles.append(handle)
        vertices = obj['vertices']
        if isinstance(vertices, (str, bytes)) or not isinstance(vertices, (list, tuple)) or not vertices:
            raise ValueError(f'empty mesh: {name}')
        points = [_finite_point(point, name, index) for index, point in enumerate(vertices)]
        faces = _triangles(obj['faces'], len(points), name)
        ids = obj['material_ids']
        if isinstance(ids, (str, bytes)) or not isinstance(ids, (list, tuple)) or len(ids) != len(faces):
            raise ValueError(f'partial material_ids {name}')
        plain_ids = []
        for mid in ids:
            if isinstance(mid, bool) or type(mid) is not int:
                raise ValueError(f'non-finite material id {name}')
            plain_ids.append(mid)
        material = obj['material']
        if material is not None and (not isinstance(material, str) or not material.strip()):
            raise ValueError(f"unmapped material {material!r}")
        gaps = obj['slot_gaps']
        if isinstance(gaps, (str, bytes)) or not isinstance(gaps, (list, tuple)):
            raise ValueError(f'partial slot_gaps {name}')
        gap_ids = []
        for gap in gaps:
            if isinstance(gap, bool) or type(gap) is not int or gap <= 0:
                raise ValueError(f'partial slot_gaps {name}')
            gap_ids.append(gap)
        if not isinstance(obj['hygiene'], dict):
            raise ValueError(f'partial hygiene {name}')
        if not isinstance(obj['texel'], dict):
            raise ValueError(f'partial texel {name}')
        validated.append({
            'name': name, 'handle': handle, 'material': material, 'material_ids': plain_ids,
            'vertices': points, 'faces': faces, 'hygiene': obj['hygiene'],
            'slot_gaps': gap_ids, 'texel': obj['texel'],
        })
    validated_pieces = []
    piece_names = []
    for piece in pieces:
        _require_keys(piece, PIECE_KEYS, 'ucx')
        name = piece['name']
        if not isinstance(name, str) or not name.strip():
            raise ValueError('partial ucx name')
        if name in piece_names or name in names:
            raise ValueError(f'duplicate name {name}')
        piece_names.append(name)
        verts = piece['verts']
        if isinstance(verts, (str, bytes)) or not isinstance(verts, (list, tuple)) or not verts:
            raise ValueError(f'empty mesh: {name}')
        points = [_finite_point(point, name, index) for index, point in enumerate(verts)]
        tris = _triangles(piece['tris'], len(points), name)
        validated_pieces.append({'name': name, 'verts': points, 'tris': tris})
    return validated, validated_pieces


def _same(a, b):
    a, b = Path(a), Path(b)
    try:
        if os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve())):
            return True
    except OSError as exc:
        raise ValueError(f'cannot resolve paths: {exc}') from exc
    if a.exists() and b.exists():
        try:
            return os.path.samefile(a, b)
        except OSError as exc:
            raise ValueError(f'cannot compare input and output identity: {exc}') from exc
    return False


def _paths(target, source, report_path):
    target = Path(target)
    report = Path(report_path) if report_path else target.with_suffix('.report.json')
    partial = Path(str(target) + '.partial')
    roles = []
    if source:
        roles.append(('input', Path(source)))
    roles.extend((('output', target), ('report', report), ('partial', partial)))
    for index, (left, path_a) in enumerate(roles):
        for right, path_b in roles[index + 1:]:
            if _same(path_a, path_b):
                raise ValueError(f'{right} path is the same file as the {left} path: {path_b}')
    return target, report, partial


def _occupied(paths):
    return [path for path in paths if path.exists()]


def _digest(scene):
    payload = {'objects': scene['objects'], 'ucx': scene['ucx'], 'units': scene['units'], 'axis': scene['axis']}
    raw = json.dumps(payload, sort_keys=True, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _entry(obj, findings):
    return {'handle': obj['handle'], 'name': obj['name'], 'findings': findings}


def _finding(code, ids, detail=''):
    clean = sorted({int(i) for i in ids if type(i) is int and i > 0})
    if not clean:
        clean = [1]
    return {'code': code, 'ids': clean, 'detail': detail}


def _drop_all(objects, pieces, reason):
    rows = [{'name': obj['name'], 'reason': reason} for obj in objects]
    rows.extend({'name': piece['name'], 'reason': reason} for piece in pieces)
    return rows


def _gate_cleanup(objects):
    from twinqa.export_hygiene import hygiene_findings, repair_plan
    dumps = [obj['hygiene'] for obj in objects]
    plan = repair_plan(dumps)
    findings = hygiene_findings(dumps, 'export-copy')
    by_name = {}
    for item in plan['objects']:
        ids = []
        for action in item['actions']:
            channels = action.get('channels') or []
            if channels:
                ids.extend(int(ch) for ch in channels if type(ch) is int and ch > 0)
            else:
                ids.append(1)
        if item['unrepairable'] and not ids:
            ids = [1]
        by_name[item['name']] = ids
    failed = any(item['actions'] or item['unrepairable'] for item in plan['objects'])
    failed = failed or any(item.status != 'pass' for item in findings)
    counts = {
        'actions': plan['objects'][0]['actions'] if len(plan['objects']) == 1 else [item['actions'] for item in plan['objects']],
        'unrepairable': [item['unrepairable'] for item in plan['objects']],
        'finding_status': {item.name: item.status for item in findings},
    }
    per_object = []
    for obj in objects:
        if failed:
            per_object.append([_finding('cleanup', by_name.get(obj['name'], [1]), obj['name'])])
        else:
            per_object.append([])
    return ('fail' if failed else 'pass'), _plain(counts), per_object


def _gate_matid(objects):
    import numpy as np
    from twinqa.geometry.checks import check_material_ids, load_ranges
    from twinqa.geometry.mesh import Soup
    ranges = load_ranges()
    per_object = []
    stored = []
    failed = False
    for obj in objects:
        soup = Soup(np.asarray(obj['vertices'], float), np.asarray(obj['faces'], np.int64),
                    np.asarray(obj['material_ids'], np.int64), None, {})
        verdict = check_material_ids(soup, {'unassigned_ids_max': 0}, ranges)
        stored.append(verdict)
        ids = obj['material_ids']
        udim = set(verdict['details'].get('udim_as_material_id') or [])
        out = set(verdict['details'].get('out_of_range') or [])
        findings = []
        udim_faces = [index for index, mid in enumerate(ids, 1) if mid >= 1001 or mid in udim]
        empty_faces = [index for index, mid in enumerate(ids, 1) if mid <= 0]
        other_faces = [index for index, mid in enumerate(ids, 1) if mid in out and mid not in udim and mid > 0]
        if udim_faces:
            findings.append(_finding('udim_id', udim_faces, obj['name']))
        if empty_faces:
            findings.append(_finding('empty_id', empty_faces, obj['name']))
        if other_faces:
            findings.append(_finding('out_of_range', other_faces, obj['name']))
        if obj['material'] is None:
            findings.append(_finding('missing_material', range(1, len(ids) + 1), obj['name']))
        if obj['slot_gaps']:
            findings.append(_finding('empty_slot', obj['slot_gaps'], obj['name']))
        if verdict['status'] != 'pass' or obj['material'] is None or obj['slot_gaps']:
            failed = True
            if not findings:
                findings.append(_finding('out_of_range', [1], verdict['status']))
        per_object.append(findings)
    counts = stored[0] if len(stored) == 1 else stored
    return ('fail' if failed else 'pass'), _plain(counts), per_object


def _gate_xview(objects):
    import numpy as np
    from dt_ai.ops.xview_gate import Part, gate_report
    parts = [Part(obj['name'], np.asarray(obj['vertices'], np.float64),
                  tuple(tuple(face) for face in obj['faces']), None) for obj in objects]
    report = gate_report(parts, coords='as-stored')
    by_name = {part['part']: part for part in report['parts']}
    per_object = []
    failed = not report['passed']
    for obj in objects:
        part = by_name[obj['name']]
        findings = []
        verts = sorted({pair['a'] for pair in part['vertex_pairs']} | {pair['b'] for pair in part['vertex_pairs']})
        bowtie = [item['vertex'] for item in part['bowtie_vertices']]
        faces = list(part['xview_faces'])
        if verts or bowtie:
            findings.append(_finding('overlap_vertices', verts or bowtie, obj['name']))
        if faces:
            findings.append(_finding('overlap_faces', faces, obj['name']))
        if not part['passed'] and not findings:
            findings.append(_finding('overlap_faces', [1], 'no faces' if not part['faces_count'] else 'xview'))
        per_object.append(findings)
    counts = {'passed': report['passed'], 'totals': report['totals']}
    return ('fail' if failed else 'pass'), _plain(counts), per_object


def _gate_ucx(pieces):
    from twinqa.geometry.ucx_audit import classify, collision_findings
    if not pieces:
        return 'absent', {'collision': [], 'classify': []}, []
    kinds = [classify(piece['verts'], piece['tris']) for piece in pieces]
    collision = collision_findings(pieces)
    bad_classify = []
    for index, kind in enumerate(kinds, 1):
        if kind.get('status') == 'review' or kind.get('closed') is not True or kind.get('convex') is not True:
            bad_classify.append(index)
    failed = bool(collision) or bool(bad_classify)
    counts = {'collision': collision, 'classify': kinds}
    return ('fail' if failed else 'pass'), _plain(counts), bad_classify


def _gate_texel(objects):
    core_path = Path(__file__).with_name('texel_core.py')
    import importlib.util
    spec = importlib.util.spec_from_file_location('agr_tools_texel_export', core_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    summaries = [module.summarize(obj['texel']) for obj in objects]
    counts = summaries[0] if len(summaries) == 1 else summaries
    return 'report', _plain(counts)


def _counts(objects, pieces):
    names = [obj['name'] for obj in objects] + [piece['name'] for piece in pieces]
    triangles = {}
    for obj in objects:
        triangles[obj['name']] = len(obj['faces'])
    for piece in pieces:
        triangles[piece['name']] = len(piece['tris'])
    materials = []
    for obj in objects:
        if obj['material'] and obj['material'] not in materials:
            materials.append(obj['material'])
    return names, triangles, len(materials), sum(triangles.values())


def _blank(objects, pieces, target, report, digest, gates, stopped, findings, dropped, texel):
    names, triangles, materials, total = _counts(objects, pieces)
    if stopped is not None:
        names, triangles, materials, total = [], {}, 0, 0
    return {
        'schema': 1,
        'tool': 'export',
        'status': 'fail' if any(item['findings'] for item in findings) or stopped not in (None, 'texel') else 'pass',
        'objects': findings,
        'plan': {
            'target': str(target),
            'report': str(report),
            'units': 'm',
            'axis': 'Z-up',
            'unit_scale_factor': UNIT_SCALE,
            'object_count': len(names),
            'triangle_count': total,
            'material_count': materials,
            'object_names': names,
            'triangles_by_name': triangles,
            'gates': gates,
            'dropped': dropped,
            'texel': texel,
            'readback': None,
            'stopped': stopped,
            'digest': digest,
        },
    }


def dry_run(scene, target, source=None, report_path=None):
    """Evaluate the gates. Does not create or modify any file."""
    objects, pieces = _validate_scene(scene)
    target, report, partial = _paths(target, source, report_path)
    digest = _digest(scene)
    gates = []
    stopped = None
    per = {obj['name']: [] for obj in objects}
    dropped = []
    texel = None

    status, counts, findings = _gate_cleanup(objects)
    gates.append({'name': 'cleanup', 'status': status, 'counts': counts})
    if status == 'fail':
        stopped = 'cleanup'
        for obj, found in zip(objects, findings):
            per[obj['name']].extend(found)
    if stopped is None:
        status, counts, findings = _gate_matid(objects)
        gates.append({'name': 'matid', 'status': status, 'counts': counts})
        if status == 'fail':
            stopped = 'matid'
            for obj, found in zip(objects, findings):
                per[obj['name']].extend(found)
    if stopped is None:
        status, counts, findings = _gate_xview(objects)
        gates.append({'name': 'xview', 'status': status, 'counts': counts})
        if status == 'fail':
            stopped = 'xview'
            for obj, found in zip(objects, findings):
                per[obj['name']].extend(found)
    if stopped is None:
        status, counts, bad_ids = _gate_ucx(pieces)
        gates.append({'name': 'ucx', 'status': status, 'counts': counts})
        if status == 'fail':
            stopped = 'ucx'
            per[objects[0]['name']].append(_finding(
                'ucx_unmeasurable' if bad_ids and not counts['collision'] else 'ucx_audit',
                bad_ids or list(range(1, len(pieces) + 1)),
                ','.join(piece['name'] for piece in pieces)))
    if stopped is None:
        texel = _gate_texel(objects)[1]
        gates.append({'name': 'texel', 'status': 'report', 'counts': texel})
    occupied = _occupied((target, report, partial))
    if occupied and stopped is None:
        stopped = 'path'
        per[objects[0]['name']].append(_finding(
            'existing_target', [1], ','.join(str(path) for path in occupied)))
    if stopped is not None:
        dropped = _drop_all(objects, pieces, 'stopped: ' + stopped)
    rows = [_entry(obj, per[obj['name']]) for obj in objects]
    return _blank(objects, pieces, target, report, digest, gates, stopped, rows, dropped, texel)


def _prop_s(text):
    raw = str(text).encode('latin-1')
    return b'S' + struct.pack('<I', len(raw)) + raw


def _prop_d(value):
    return b'D' + struct.pack('<d', float(value))


def _prop_i(value):
    return b'I' + struct.pack('<i', int(value))


def _prop_ints(values):
    raw = struct.pack('<' + 'i' * len(values), *[int(v) for v in values])
    return b'i' + struct.pack('<III', len(values), 0, len(raw)) + raw


def _emit(name, props, children, start):
    name_b = name.encode('ascii')
    prop_blob = b''.join(props)
    header_len = 13 + len(name_b)
    cursor = start + header_len + len(prop_blob)
    chunks = []
    for child_name, child_props, child_children in children:
        blob, cursor = _emit(child_name, child_props, child_children, cursor)
        chunks.append(blob)
    end = cursor + 13
    header = struct.pack('<III', end, len(props), len(prop_blob)) + bytes([len(name_b)]) + name_b
    return header + prop_blob + b''.join(chunks) + (b'\x00' * 13), end


def _p(name, type_name, label, value):
    return ('P', [_prop_s(name), _prop_s(type_name), _prop_s(label), _prop_s(''), value], [])


def _polygon(faces):
    values = []
    for a, b, c in faces:
        values.extend((a, b, ~c))
    return values


def encode_fbx(objects, pieces):
    """Binary FBX 7.4, metres, Z-up. One Mesh model per render object and per UCX piece."""
    from twinqa.fbx_header import MAGIC, REQUIRED_VERSION
    props70 = [
        _p('UnitScaleFactor', 'double', 'Number', _prop_d(UNIT_SCALE)),
        _p('OriginalUnitScaleFactor', 'double', 'Number', _prop_d(UNIT_SCALE)),
        _p('UpAxis', 'int', 'Integer', _prop_i(UP_AXIS)),
        _p('UpAxisSign', 'int', 'Integer', _prop_i(1)),
        _p('FrontAxis', 'int', 'Integer', _prop_i(1)),
        _p('CoordAxis', 'int', 'Integer', _prop_i(0)),
    ]
    children = []
    materials = []
    for obj in objects:
        if obj['material'] and obj['material'] not in materials:
            materials.append(obj['material'])
    for name in materials:
        children.append(('Material', [_prop_s('Material::' + name), _prop_s('')], []))
    for obj in objects:
        children.append(('Geometry', [_prop_s('Geometry::' + obj['name']), _prop_s('Mesh')], [
            ('PolygonVertexIndex', [_prop_ints(_polygon(obj['faces']))], []),
        ]))
        children.append(('Model', [_prop_s('Model::' + obj['name']), _prop_s('Mesh')], []))
    for piece in pieces:
        children.append(('Geometry', [_prop_s('Geometry::' + piece['name']), _prop_s('Mesh')], [
            ('PolygonVertexIndex', [_prop_ints(_polygon(piece['tris']))], []),
        ]))
        children.append(('Model', [_prop_s('Model::' + piece['name']), _prop_s('Mesh')], []))
    top = [
        ('GlobalSettings', [], [('Properties70', [], props70)]),
        ('Objects', [], children),
    ]
    cursor = 27
    blobs = []
    for name, props, kids in top:
        blob, cursor = _emit(name, props, kids, cursor)
        blobs.append(blob)
    return MAGIC + struct.pack('<I', REQUIRED_VERSION) + b''.join(blobs) + (b'\x00' * 13)


def _read_props(data, start, end, count):
    if count == 0:
        return []
    offset = start
    props = []
    for _ in range(count):
        if offset >= end:
            raise ValueError(f'truncated node at offset {offset}')
        code = chr(data[offset])
        offset += 1
        if code in ('S', 'R'):
            length = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            raw = data[offset:offset + length]
            offset += length
            props.append(raw.decode('latin-1') if code == 'S' else None)
        elif code == 'D':
            props.append(struct.unpack_from('<d', data, offset)[0])
            offset += 8
        elif code == 'I':
            props.append(struct.unpack_from('<i', data, offset)[0])
            offset += 4
        elif code == 'i':
            array_len, encoding, compressed = struct.unpack_from('<III', data, offset)
            offset += 12
            raw = data[offset:offset + compressed]
            offset += compressed
            if encoding == 0:
                decoded = raw
            elif encoding == 1:
                decoded = zlib.decompress(raw)
            else:
                raise ValueError(f'unsupported polygon encoding {encoding}')
            if len(decoded) != array_len * 4:
                raise ValueError('partial polygon array')
            props.append(list(struct.unpack('<' + 'i' * array_len, decoded)))
        elif code in ('Y', 'C', 'F', 'L'):
            size = {'Y': 2, 'C': 1, 'F': 4, 'L': 8}[code]
            offset += size
            props.append(None)
        elif code in ('f', 'd', 'l', 'b'):
            _array_len, _encoding, compressed = struct.unpack_from('<III', data, offset)
            offset += 12 + compressed
            props.append(None)
        else:
            raise ValueError(f'unsupported FBX property {code!r}')
    return props


def _walk(data, start, end, version):
    from twinqa import fbx_header as header
    nodes = []
    for node in header._iter_nodes(data, start, end, version):
        nodes.append(node)
        nodes.extend(_walk(data, node['props_end'], node['end_offset'], version))
    return nodes


def _triangles_of(values):
    polygon = []
    count = 0
    for raw in values:
        if raw < 0:
            polygon.append(~raw)
            if len(polygon) != 3:
                raise ValueError('unsupported polygon')
            count += 1
            polygon = []
        else:
            polygon.append(raw)
    if polygon:
        raise ValueError('partial polygon')
    return count


def readback(data):
    """Object, triangle and material counts plus the unit scale from fbx_header."""
    from twinqa.fbx_header import check_fbx_header, fbx_header, fbx_units
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError('partial FBX')
    ok, reason = check_fbx_header(bytes(data))
    units = fbx_units(bytes(data))
    result = {
        'object_count': None, 'triangle_count': None, 'material_count': None,
        'unit_scale_factor': units.get('unit_scale_factor'), 'axis': None, 'error': None,
    }
    if not ok:
        result['error'] = reason
        return result
    if units.get('error') or units.get('unit_scale_factor') is None:
        result['error'] = units.get('error') or 'UnitScaleFactor missing'
        return result
    scale = units['unit_scale_factor']
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(float(scale)):
        result['error'] = 'non-finite UnitScaleFactor'
        return result
    try:
        _kind, version = fbx_header(bytes(data))
        nodes = _walk(bytes(data), 27, len(data), version)
        objects = materials = 0
        triangles = 0
        axis = None
        for node in nodes:
            props = _read_props(data, node['props_at'], node['props_end'], node['num_props'])
            if node['name'] == 'Model' and 'Mesh' in props:
                objects += 1
            elif node['name'] == 'Material':
                materials += 1
            elif node['name'] == 'PolygonVertexIndex':
                arrays = [item for item in props if isinstance(item, list)]
                if len(arrays) != 1:
                    raise ValueError('partial PolygonVertexIndex')
                triangles += _triangles_of(arrays[0])
            elif node['name'] == 'P' and props and props[0] == 'UpAxis':
                ints = [item for item in props if type(item) is int]
                if len(ints) != 1:
                    raise ValueError('partial UpAxis')
                if ints[0] not in AXIS_NAME:
                    raise ValueError(f'unmapped axis {ints[0]!r}')
                axis = AXIS_NAME[ints[0]]
        if axis is None:
            raise ValueError('unmapped axis UpAxis')
        result.update({'object_count': objects, 'triangle_count': triangles,
                       'material_count': materials, 'axis': axis})
    except (ValueError, struct.error, zlib.error) as exc:
        result['error'] = str(exc)
    return result


def _matches(plan, got):
    if not isinstance(got, dict) or got.get('error'):
        return False
    return (got.get('object_count') == plan['object_count']
            and got.get('triangle_count') == plan['triangle_count']
            and got.get('material_count') == plan['material_count']
            and got.get('unit_scale_factor') == plan['unit_scale_factor']
            and got.get('axis') == plan['axis'])


def finish(preview, target, report_path=None, readback_fn=None):
    """Read an FBX that was just written and write the JSON report beside it."""
    target = Path(target)
    report_path = Path(report_path) if report_path else Path(preview['plan']['report'])
    if not target.is_file():
        raise ValueError('writer wrote nothing')
    got = (readback_fn or readback)(target.read_bytes())
    report = json.loads(json.dumps(preview, allow_nan=False))
    report['plan']['readback'] = _plain(got)
    if not _matches(report['plan'], got):
        report['objects'][0]['findings'].append(_finding(
            'readback_mismatch', [1],
            json.dumps({'expected': {
                'object_count': report['plan']['object_count'],
                'triangle_count': report['plan']['triangle_count'],
                'material_count': report['plan']['material_count'],
                'unit_scale_factor': report['plan']['unit_scale_factor'],
            }, 'got': _plain(got)}, allow_nan=False)))
        report['status'] = 'fail'
    text = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    with report_path.open('xb') as handle:
        handle.write(text.encode('utf-8'))
    return report


def commit(scene, target, source, preview, readback_fn=None, report_path=None, writer=None):
    """Write the FBX and the JSON report, or raise before creating either file."""
    current = dry_run(scene, target, source, report_path)
    if preview != current:
        raise ValueError('stale preview')
    if current['status'] != 'pass':
        raise ValueError('gate failed: ' + str(current['plan']['stopped']))
    target_path, report_file, _partial = _paths(target, source, report_path)
    objects, pieces = _validate_scene(scene)
    if writer is None:
        data = encode_fbx(objects, pieces)
        with target_path.open('xb') as handle:
            handle.write(data)
    else:
        writer(target_path, current)
        if not target_path.is_file():
            raise ValueError('writer wrote nothing')
    return finish(current, target_path, report_file, readback_fn)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Checked FBX export. A failing gate writes nothing.')
    parser.add_argument('--scene', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--source')
    parser.add_argument('--report')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        source = args.source or args.scene
        _paths(args.target, source, args.report)
        scene = json.loads(Path(args.scene).read_text(encoding='utf-8'))
        preview = dry_run(scene, args.target, source, args.report)
        if args.dry_run or preview['status'] != 'pass':
            print(json.dumps(preview, allow_nan=False))
            return 0 if preview['status'] == 'pass' else 1
        report = commit(scene, args.target, source, preview, report_path=args.report)
        print(json.dumps(report, allow_nan=False))
        return 0 if report['status'] == 'pass' else 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
