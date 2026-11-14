"""new-case: checked FBX export for AGR Tools 0.4.0.

Pattern: new-case. Gates run in a fixed order on the export copy description:
hygiene (every render mesh and every UCX piece), MatID, xView, UCX audit when
pieces exist, then a texel readout that is reported and does not by itself
refuse the file. A failing gate writes nothing. This module has no geometry
writer: commit without an injected writer raises "unsupported writer" and
creates no file. The native exporter is injected by the Max button. Readback
uses twinqa.fbx_header; object, triangle, material, unit-scale and model-name
counts must equal the dry-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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
PIECE_KEYS = {'name', 'handle', 'verts', 'tris', 'hygiene'}
PLAN_KEYS = {'target', 'report', 'units', 'axis', 'unit_scale_factor', 'object_count',
             'triangle_count', 'material_count', 'object_names', 'triangles_by_name',
             'gates', 'dropped', 'texel', 'readback', 'stopped', 'digest'}
GATE_ORDER = ('cleanup', 'matid', 'xview', 'ucx', 'texel')
EARLY_GATES = ('cleanup', 'matid', 'xview', 'ucx')


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
        handle = piece['handle']
        if isinstance(handle, bool) or type(handle) is not int or handle <= 0:
            raise ValueError(f'invalid handle {handle!r}')
        if handle in handles:
            raise ValueError(f'duplicate handle {handle}')
        handles.append(handle)
        piece_names.append(name)
        if not isinstance(piece['hygiene'], dict):
            raise ValueError(f'partial hygiene {name}')
        verts = piece['verts']
        if isinstance(verts, (str, bytes)) or not isinstance(verts, (list, tuple)) or not verts:
            raise ValueError(f'empty mesh: {name}')
        points = [_finite_point(point, name, index) for index, point in enumerate(verts)]
        tris = _triangles(piece['tris'], len(points), name)
        validated_pieces.append({
            'name': name, 'handle': handle, 'verts': points, 'tris': tris, 'hygiene': piece['hygiene'],
        })
    return validated, validated_pieces


def _session_core():
    """Shared helpers (session_core.py next to this file), loaded by path like the other sibling cores."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('agr_tools_session_core', Path(__file__).with_name('session_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_same = _session_core().same


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


CLEANUP_OPTIONS = ('channels', 'keys')  # 0.9 (#979): opt-in cleanup passes on export copies; off by default


def cleanup_options(options=None):
    """Validated cleanup options: only `channels` and `keys`, both booleans, both off unless switched on.

    0.9 base (#979, branch 0) only carries them from runtime.cleanup_preview/cleanup_apply to
    _cleanup_channels; what an option does is written by branch E3. Unknown keys / non-bools are errors."""
    out = {key: False for key in CLEANUP_OPTIONS}
    if options is None:
        return out
    if not isinstance(options, dict):
        raise ValueError('cleanup options must be a JSON object')
    unknown = sorted(set(options) - set(CLEANUP_OPTIONS))
    if unknown:
        raise ValueError('unknown cleanup option(s): ' + ', '.join(map(str, unknown)))
    for key, value in options.items():
        if type(value) is not bool:
            raise ValueError('cleanup option {} must be true or false'.format(key))
        out[key] = value
    return out


def _cleanup_channels(actions, options=None):
    """Channel ids the cleanup removes on the export copy: map channels named by the repair plan and, only with
    the opt-in `channels`, the vertex channels 0/-1/-2 of a `delete_vertex_channels` action (#979).
    `options` (cleanup_options): validated here; with both off (the default) the result is the 0.8 one."""
    opts = cleanup_options(options)
    ids = []
    for action in actions:
        vertex = action.get('action') == 'delete_vertex_channels'
        if vertex and not opts['channels']:
            raise ValueError('delete_vertex_channels without the opt-in option channels')
        for channel in action.get('channels') or []:
            ok = channel in VERTEX_CHANNELS if vertex else (type(channel) is int and channel > 0)
            if type(channel) is int and ok and channel not in ids:
                ids.append(channel)
    return ids


# ---- export.cleanup rework (#979): CA & UDP Cleaner v010 (ClearCustomAttributesAndObjProp_010.ms
# sha256 c1c52e21cf5adf67e6c35a5719669754a7511335573f778128f2a0c26904e53c, T06/clear_ca_udp_010, measured Max 2026):
# by default it erased vertex channels 0/-1/-2 and every animation key, deleted AGR_EXPORT_PATH and worked on the
# originals. Here: vertex channels and keys only as opt-in actions on the export copy; pipeline UDP stays.
VERTEX_CHANNELS = (0, -1, -2)  # vertex colour, illumination, alpha
# Tool instructions of the AGR pipeline (runtime._HELD_OFF holds the same keys off the export hygiene gate).
PIPELINE_UDP = frozenset({'AGR_EXPORT_PATH', 'AGR_ZERO_M', 'AGR_TEXEL_PROFILE', 'AGR_TEXEL_MAP', 'AGR_UV_PERIODS',
                          'AGR_UV_TARGET', 'AGR_ATLAS_MODE', 'AGR_ATLAS_SIZE', 'AGR_UCX_KIND'})
# 1.0.1 (KPP1 e2e 20261106-075555-c179f5f0): the lower-case working keys of the 1.0 buttons (contract_core К1
# `agr_role`, `agr_window_type`, `agr_face_axis`, `agr_udim_table`, `agr_npm_source`, `agr_intake_source`, ...) are
# pipeline data as well: held off the hygiene gate and off the delivered copy, never a `clear_user_defined_lines`.
PIPELINE_UDP_PREFIX = 'agr_'


def pipeline_key(key):
    """True for a user-prop key of the AGR pipeline (kept on the working object, not delivered)."""
    key = str(key).strip()
    return key in PIPELINE_UDP or key.startswith(PIPELINE_UDP_PREFIX)
CLEANUP_FACT_KEYS = ('vertex_channels', 'keys')


def udp_key(line):
    return str(line).split('=', 1)[0].strip()


def cleanup_facts(fact):
    """Validated scene facts of one node: vertex channels present among 0/-1/-2, animation key count (node + material).
    A missing or mistyped fact is an error, never `nothing to clean`."""
    if not isinstance(fact, dict) or set(fact) != set(CLEANUP_FACT_KEYS):
        raise ValueError('cleanup facts need exactly {}: {!r}'.format(list(CLEANUP_FACT_KEYS), fact))
    chans = fact['vertex_channels']
    if not isinstance(chans, list) or any(type(c) is not int or c not in VERTEX_CHANNELS for c in chans) \
            or len(set(chans)) != len(chans):
        raise ValueError('vertex_channels must be distinct ids of {}: {!r}'.format(VERTEX_CHANNELS, chans))
    if type(fact['keys']) is not int or fact['keys'] < 0:
        raise ValueError('keys must be a count >= 0: {!r}'.format(fact['keys']))
    return {'vertex_channels': sorted(chans, reverse=True), 'keys': fact['keys']}


def cleanup_plan(plan, facts, options=None):
    """The export.cleanup plan of 0.9: the hygiene repair plan with the pipeline UDP kept, plus the opt-in actions.

    plan: hygiene repair_plan (never modified); facts: one cleanup_facts dict per plan object, same order.
    - `clear_user_defined_lines` drops the PIPELINE_UDP lines (they stay in `cleaned.user_props`; listed in
      `kept_udp`); an action left without lines disappears.
    - options.channels (opt-in) adds `delete_vertex_channels` for the vertex channels the node has.
    - options.keys (opt-in) adds `delete_animation_keys` with the key count (node, stack and material keys).
    With both options off nothing about channels 0/-1/-2 or keys is planned: they stay on the copy."""
    import copy as _copy
    opts = cleanup_options(options)
    if not isinstance(plan, dict) or not isinstance(plan.get('objects'), list):
        raise ValueError('cleanup plan without objects')
    if not isinstance(facts, list) or len(facts) != len(plan['objects']):
        raise ValueError('one cleanup fact per object is needed')
    out = _copy.deepcopy(plan)
    for item, fact in zip(out['objects'], facts):
        fact = cleanup_facts(fact)
        actions, kept = [], []
        for action in item['actions']:
            if action.get('action') == 'clear_user_defined_lines':
                kept += [line for line in action['lines'] if pipeline_key(udp_key(line))]
                lines = [line for line in action['lines'] if not pipeline_key(udp_key(line))]
                if lines:
                    actions.append(dict(action, lines=lines))
                continue
            actions.append(action)
        if opts['channels'] and fact['vertex_channels']:
            actions.append({'action': 'delete_vertex_channels', 'channels': list(fact['vertex_channels'])})
        if opts['keys'] and fact['keys']:
            actions.append({'action': 'delete_animation_keys', 'keys': fact['keys']})
        item['actions'] = actions
        item['kept_udp'] = kept
        item['cleaned']['user_props'] = item['cleaned']['user_props'] + ''.join(line + '\r\n' for line in kept)
    return out


def cleanup_scene_ops(item, options=None):
    """Scene operations of one plan object on its export copy, beyond the 0.8 ones (CA, UDP, map channels 2+):
    [('vertex_channel', id), ...] and ('keys',) — only from opt-in actions; ValueError for an action without its
    option (a preview edited by hand)."""
    opts = cleanup_options(options)
    ops = []
    for action in item['actions']:
        if action.get('action') == 'delete_vertex_channels':
            if not opts['channels']:
                raise ValueError('delete_vertex_channels without the opt-in option channels')
            ops += [('vertex_channel', ch) for ch in _cleanup_channels([action], opts)]
        elif action.get('action') == 'delete_animation_keys':
            if not opts['keys']:
                raise ValueError('delete_animation_keys without the opt-in option keys')
            ops.append(('keys',))
    return ops


def _gate_cleanup(subjects):
    from twinqa.export_hygiene import hygiene_findings, repair_plan
    dumps = [obj['hygiene'] for obj in subjects]
    plan = repair_plan(dumps)
    findings = hygiene_findings(dumps, 'export-copy')
    by_name = {item['name']: item for item in plan['objects']}
    named = set()
    for item in findings:
        if item.status != 'pass':
            named.update((item.data or {}).get('objects') or {})
    failed = bool(named) or any(item['actions'] or item['unrepairable'] for item in plan['objects'])
    counts = {
        'actions': plan['objects'][0]['actions'] if len(plan['objects']) == 1 else [item['actions'] for item in plan['objects']],
        'unrepairable': [item['unrepairable'] for item in plan['objects']],
        'finding_status': {item.name: item.status for item in findings},
    }
    per_object = []
    for obj in subjects:
        item = by_name[obj['name']]
        offender = bool(item['actions'] or item['unrepairable'] or obj['name'] in named)
        if not offender:
            per_object.append([])
            continue
        ids = _cleanup_channels(item['actions']) or [1]
        per_object.append([_finding('cleanup', ids, obj['name'])])
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


def _install_texel(objects, produced):
    """Replace render-mesh texel payloads. A partial map is an error, never a pass."""
    if not isinstance(produced, dict):
        raise ValueError('partial texel')
    for obj in objects:
        payload = produced.get(obj['name'])
        if not isinstance(payload, dict):
            raise ValueError('partial texel ' + obj['name'])
        obj['texel'] = payload


def dry_run(scene, target, source=None, report_path=None, texel_fn=None, defer_texel=False):
    """Evaluate the gates. Does not create or modify any file.

    ``texel_fn`` is called only after cleanup, MatID, xView and UCX passed.
    ``defer_texel`` stops before that call so a host can read texel itself.
    """
    objects, pieces = _validate_scene(scene)
    target, report, partial = _paths(target, source, report_path)
    digest = _digest(scene)
    gates = []
    stopped = None
    per = {obj['name']: [] for obj in objects}
    for piece in pieces:
        per[piece['name']] = []
    dropped = []
    texel = None
    subjects = [*objects, *pieces]

    status, counts, findings = _gate_cleanup(subjects)
    gates.append({'name': 'cleanup', 'status': status, 'counts': counts})
    if status == 'fail':
        stopped = 'cleanup'
        for obj, found in zip(subjects, findings):
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
    if stopped is None and not defer_texel:
        if texel_fn is not None:
            _install_texel(objects, texel_fn(objects))
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
    rows.extend(_entry(piece, per[piece['name']]) for piece in pieces)
    return _blank(objects, pieces, target, report, digest, gates, stopped, rows, dropped, texel)


def mesh_model_name(props):
    """Planned mesh name from an FBX Model property list.

    3ds Max writes ``Name\\x00\\x01Model``. A ``Model::Name`` string is accepted too.
    """
    if isinstance(props, (str, bytes)) or not isinstance(props, (list, tuple)):
        return None
    for item in props:
        if not isinstance(item, str) or item == 'Mesh':
            continue
        text = item.split('\x00', 1)[0]
        if text.startswith('Model::'):
            text = text[len('Model::'):]
        text = text.strip()
        if text and text != 'Mesh':
            return text
    return None


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
        'unit_scale_factor': units.get('unit_scale_factor'), 'axis': None,
        'object_names': None, 'error': None,
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
        model_names = []
        for node in nodes:
            props = _read_props(data, node['props_at'], node['props_end'], node['num_props'])
            if node['name'] == 'Model' and 'Mesh' in props:
                objects += 1
                label = mesh_model_name(props)
                if not label:
                    raise ValueError('partial model name')
                model_names.append(label)
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
                       'material_count': materials, 'axis': axis, 'object_names': model_names})
    except (ValueError, struct.error, zlib.error) as exc:
        result['error'] = str(exc)
    return result


def _array(data, node):
    """Decoded numeric arrays ('d', 'f', 'i', 'l') of one binary node, in property order."""
    out, offset, end = [], node['props_at'], node['props_end']
    for _ in range(node['num_props']):
        code = chr(data[offset])
        offset += 1
        if code in ('d', 'f', 'i', 'l', 'b'):
            n, encoding, size = struct.unpack_from('<III', data, offset)
            offset += 12
            raw = data[offset:offset + size]
            offset += size
            raw = zlib.decompress(raw) if encoding == 1 else raw
            fmt = {'d': 'd', 'f': 'f', 'i': 'i', 'l': 'q', 'b': 'B'}[code]
            if len(raw) != n * struct.calcsize(fmt):
                raise ValueError('partial array')
            out.append(list(struct.unpack('<' + fmt * n, raw)))
        elif code in ('S', 'R'):
            offset += 4 + struct.unpack_from('<I', data, offset)[0]
        else:
            offset += {'Y': 2, 'C': 1, 'I': 4, 'F': 4, 'D': 8, 'L': 8}[code]
        if offset > end:
            raise ValueError('truncated node')
    return out


def _polygons(index):
    polys, cur = [], []
    for raw in index:
        if raw < 0:
            cur.append(~raw)
            polys.append(cur)
            cur = []
        else:
            cur.append(raw)
    if cur:
        raise ValueError('partial polygon')
    return polys


def _binary_meshes(data):
    from twinqa import fbx_header as header
    _kind, version = header.fbx_header(data)
    top = {n['name']: n for n in header._iter_nodes(data, 27, len(data), version)}
    geoms, models, links = {}, {}, []
    for node in header._iter_nodes(data, top['Objects']['props_end'], top['Objects']['end_offset'], version) \
            if 'Objects' in top else []:
        props = [v for _c, v in header._parse_props(data, node['props_at'], node['props_end'], node['num_props'])]
        if node['name'] == 'Geometry' and 'Mesh' in props:
            verts = index = None
            for child in header._iter_nodes(data, node['props_end'], node['end_offset'], version):
                if child['name'] == 'Vertices':
                    verts = _array(data, child)[0]
                elif child['name'] == 'PolygonVertexIndex':
                    index = _array(data, child)[0]
            if verts is None or index is None:
                raise ValueError('geometry without Vertices/PolygonVertexIndex')
            geoms[props[0]] = (verts, index)
        elif node['name'] == 'Model' and 'Mesh' in props:
            models[props[0]] = mesh_model_name(props)
    if 'Connections' in top:
        for node in header._iter_nodes(data, top['Connections']['props_end'], top['Connections']['end_offset'],
                                       version):
            props = [v for _c, v in header._parse_props(data, node['props_at'], node['props_end'],
                                                         node['num_props'])]
            if len(props) >= 3 and props[0] == 'OO':
                links.append((props[1], props[2]))
    return geoms, models, links


def _ascii_meshes(text):
    import re
    geoms, models, links = {}, {}, []
    numbers = r'([-+0-9.eE,\s]*)'
    for m in re.finditer(r'Geometry:\s*(-?\d+)\s*,\s*"(?:Geometry::)?[^"]*"\s*,\s*"Mesh"\s*\{', text):
        body = text[m.end():]
        stop = re.search(r'\n\s*(?:Geometry|Model|Material|Deformer|NodeAttribute):', body)
        body = body[:stop.start()] if stop else body
        vm = re.search(r'Vertices:\s*\*\d+\s*\{\s*a:' + numbers + r'\}', body)
        im = re.search(r'PolygonVertexIndex:\s*\*\d+\s*\{\s*a:' + numbers + r'\}', body)
        if not vm or not im:
            raise ValueError('geometry without Vertices/PolygonVertexIndex')
        verts = [float(x) for x in vm.group(1).replace('\n', ' ').split(',') if x.strip()]
        index = [int(x) for x in im.group(1).replace('\n', ' ').split(',') if x.strip()]
        geoms[int(m.group(1))] = (verts, index)
    for m in re.finditer(r'Model:\s*(-?\d+)\s*,\s*"(?:Model::)?([^"]*)"\s*,\s*"Mesh"', text):
        models[int(m.group(1))] = m.group(2).split('\x00', 1)[0]
    for m in re.finditer(r'C:\s*"OO"\s*,\s*(-?\d+)\s*,\s*(-?\d+)', text):
        links.append((int(m.group(1)), int(m.group(2))))
    return geoms, models, links


def header_error():
    from twinqa.fbx_header import _FbxError
    return _FbxError


def fbx_meshes(data):
    """[{'name', 'verts': [(x, y, z)], 'polygons': [[i, ...]]}] of every mesh Model of a binary (7.4/7.5) or ASCII
    FBX, by object NAME (Geometry -> Model through the OO connections). Stdlib only, no Max, no Blender.
    fbx_polygon_count.py (sha256 9b4136621c4417d24fa1069adb06edcbe22585612e7ddb52f26889158a41441d, T04, idea only):
    geometries by index only and ASCII refused. Coordinates stay in file units."""
    from twinqa.fbx_header import fbx_header
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError('FBX bytes expected')
    kind, _version = fbx_header(bytes(data))
    try:
        if kind == 'binary':
            geoms, models, links = _binary_meshes(bytes(data))
        elif kind == 'ascii':
            geoms, models, links = _ascii_meshes(bytes(data).decode('utf-8', errors='replace'))
        else:
            raise ValueError('not an FBX')
    except (KeyError, IndexError, struct.error, zlib.error, header_error()) as exc:
        raise ValueError('unreadable FBX: {}'.format(exc)) from exc
    out = []
    for child, parent in links:
        if child in geoms and parent in models:
            verts, index = geoms[child]
            if len(verts) % 3:
                raise ValueError('vertex array not a multiple of 3')
            pts = [tuple(verts[i:i + 3]) for i in range(0, len(verts), 3)]
            out.append({'name': models[parent], 'verts': pts, 'polygons': _polygons(index)})
    if not out and geoms:
        raise ValueError('geometry without a mesh Model connection')
    return sorted(out, key=lambda m: m['name'])


def _matches(plan, got):
    if not isinstance(got, dict) or got.get('error'):
        return False
    names = got.get('object_names')
    if names is not None and sorted(names) != sorted(plan['object_names']):
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


def commit(scene, target, source, preview, readback_fn=None, report_path=None, writer=None, texel_fn=None):
    """Write the FBX and the JSON report, or raise before creating either file."""
    current = dry_run(scene, target, source, report_path, texel_fn=texel_fn)
    if preview != current:
        raise ValueError('stale preview')
    if current['status'] != 'pass':
        raise ValueError('gate failed: ' + str(current['plan']['stopped']))
    target_path, report_file, _partial = _paths(target, source, report_path)
    _validate_scene(scene)
    if writer is None:
        raise ValueError('unsupported writer')
    writer(target_path, current)
    if not target_path.is_file():
        raise ValueError('writer wrote nothing')
    # Metadata owner is dependency-free and distributed with this module in the MZP.
    import importlib.util
    spec = importlib.util.spec_from_file_location('_agr_export_metadata', Path(__file__).with_name('export_meta.py'))
    assert spec is not None and spec.loader is not None
    metadata = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metadata)
    metadata.record_export(target_path, source=str(source))
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
