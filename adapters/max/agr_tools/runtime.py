"""new-case: native AGR Tools button cores, no team implementation source.

Native xView uses 0.002 m vertices and 0.005 m faces.
"""
import json

VERSION = "0.4.0"
CODES = {'xview': {'overlap_vertices', 'overlap_faces'},
         'matid': {'udim_id', 'empty_id', 'empty_slot', 'missing_material'},
         'cleanup': {'remove_custom_attributes', 'clear_user_defined_lines',
                     'delete_map_channels', 'rename_map_channel_1'},
         'nudge': {'tile_move'},
         'atlas': {'atlas_cell'},
         'ucx': {'ucx_audit', 'ucx_unmeasurable', 'at_threshold'},
         'texel': {'texel_outside', 'texel_dropped'},
         'export': {'cleanup', 'udim_id', 'empty_id', 'empty_slot', 'missing_material',
                    'out_of_range', 'overlap_vertices', 'overlap_faces', 'ucx_audit',
                    'ucx_unmeasurable', 'existing_target', 'readback_mismatch'}}
EXPORT_PLAN = {'target', 'report', 'units', 'axis', 'unit_scale_factor', 'object_count',
               'triangle_count', 'material_count', 'object_names', 'triangles_by_name',
               'gates', 'dropped', 'texel', 'readback', 'stopped', 'digest'}
UV_TOL = 1e-6


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate key: ' + k)
        result[k] = v
    return result


def _reject(value):
    raise ValueError('non-finite JSON: ' + value)


def assert_uv_close(a, b, tol=UV_TOL):
    """Fail closed. A difference of exactly ``tol`` is an error, never a pass."""
    import math
    if not a or not b:
        raise ValueError('empty UV readback')
    if isinstance(a[0], (int, float)):
        pairs = [(a, b)]
    else:
        if len(a) != len(b):
            raise ValueError('UV count mismatch')
        pairs = list(zip(a, b))
    for left, right in pairs:
        if len(left) < 2 or len(right) < 2:
            raise ValueError('partial UV readback')
        for c in (left[0], left[1], right[0], right[1]):
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(float(c)):
                raise ValueError('non-finite UV readback')
        dist = math.dist((float(left[0]), float(left[1])), (float(right[0]), float(right[1])))
        if math.isclose(dist, tol, rel_tol=0.0, abs_tol=0.0) or abs(dist - tol) <= tol * 2e-7:
            raise ValueError('UV difference exactly at threshold; no clean verdict')
        if dist > tol:
            raise ValueError(f'UV readback differs by {dist}')


def _validate_plan(tool, plan):
    if not isinstance(plan, dict):
        raise ValueError('incomplete plan')
    if tool == 'nudge':
        if set(plan) != {'islands', 'dropped'}:
            raise ValueError('incomplete plan')
        if not isinstance(plan['islands'], list) or not isinstance(plan['dropped'], list):
            raise ValueError('incomplete plan')
        for island in plan['islands']:
            if not isinstance(island, dict) or set(island) != {'faces', 'steps', 'shift', 'materials', 'reason'}:
                raise ValueError('incomplete island')
            if island['reason'] not in ('repeating', 'non-repeating'):
                raise ValueError('unmapped island reason: ' + str(island['reason']))
    elif tool == 'atlas':
        if set(plan) != {'tiles', 'cells', 'dropped'}:
            raise ValueError('incomplete plan')
        if not isinstance(plan['tiles'], list) or not isinstance(plan['cells'], dict) or not isinstance(plan['dropped'], list):
            raise ValueError('incomplete plan')
    elif tool == 'ucx':
        if set(plan) != {'variant', 'kind', 'pieces', 'triangles', 'limit', 'names', 'audit', 'dropped'}:
            raise ValueError('incomplete plan')
        if not isinstance(plan['variant'], str) or not plan['variant'] or not isinstance(plan['kind'], str) or not plan['kind']:
            raise ValueError('incomplete plan')
        for key in ('pieces', 'triangles', 'limit'):
            if type(plan[key]) is not int or plan[key] < 1:
                raise ValueError('incomplete plan')
        if not isinstance(plan['names'], list) or not plan['names'] or any(not isinstance(n, str) or not n for n in plan['names']):
            raise ValueError('incomplete plan')
        audit = plan['audit']
        if not isinstance(audit, dict) or set(audit) != {'collision', 'unmeasurable', 'mask_bad_count', 'closed'}:
            raise ValueError('incomplete plan')
        if not isinstance(audit['collision'], list) or not isinstance(audit['unmeasurable'], list):
            raise ValueError('incomplete plan')
        if type(audit['mask_bad_count']) is not int or not isinstance(audit['closed'], bool):
            raise ValueError('incomplete plan')
    elif tool == 'export':
        if set(plan) != EXPORT_PLAN:
            raise ValueError('incomplete plan')
        if plan['units'] != 'm':
            raise ValueError('unmapped units ' + str(plan['units']))
        if plan['axis'] != 'Z-up':
            raise ValueError('unmapped axis ' + str(plan['axis']))
        if plan['unit_scale_factor'] != 100.0 and plan['unit_scale_factor'] != 100:
            raise ValueError('unmapped unit scale')
        for key in ('object_count', 'triangle_count', 'material_count'):
            if type(plan[key]) is not int or plan[key] < 0:
                raise ValueError('incomplete plan')
        if not isinstance(plan['object_names'], list) or not isinstance(plan['triangles_by_name'], dict):
            raise ValueError('incomplete plan')
        if not isinstance(plan['target'], str) or not plan['target'] or not isinstance(plan['report'], str) or not plan['report']:
            raise ValueError('incomplete plan')
        if not isinstance(plan['digest'], str) or len(plan['digest']) != 64:
            raise ValueError('incomplete plan')
        if plan['stopped'] is not None and (not isinstance(plan['stopped'], str) or not plan['stopped']):
            raise ValueError('incomplete plan')
        if plan['readback'] is not None and not isinstance(plan['readback'], dict):
            raise ValueError('incomplete plan')
        if plan['texel'] is not None and not isinstance(plan['texel'], (dict, list)):
            raise ValueError('incomplete plan')
        if not isinstance(plan['gates'], list) or not plan['gates']:
            raise ValueError('incomplete plan')
        for gate in plan['gates']:
            if not isinstance(gate, dict) or set(gate) != {'name', 'status', 'counts'}:
                raise ValueError('incomplete plan')
            if gate['name'] not in ('cleanup', 'matid', 'xview', 'ucx', 'texel'):
                raise ValueError('unmapped gate ' + str(gate['name']))
            if gate['status'] not in ('pass', 'fail', 'report', 'absent'):
                raise ValueError('unmapped gate status ' + str(gate['status']))
        if not isinstance(plan['dropped'], list):
            raise ValueError('incomplete plan')
        for item in plan['dropped']:
            if not isinstance(item, dict) or set(item) != {'name', 'reason'}:
                raise ValueError('incomplete drop')
            if not isinstance(item['name'], str) or not item['name'] or not isinstance(item['reason'], str) or not item['reason']:
                raise ValueError('drop without a reason')
    elif tool == 'texel':
        if set(plan) != {'meshes', 'materials', 'dropped'}:
            raise ValueError('incomplete plan')
        for key in ('meshes', 'materials'):
            if not isinstance(plan[key], list):
                raise ValueError('incomplete plan')
            for row in plan[key]:
                if not isinstance(row, dict) or set(row) != {'name', 'min_px_per_m', 'median_px_per_m'}:
                    raise ValueError('incomplete plan')
                if not isinstance(row['name'], str) or not row['name']:
                    raise ValueError('unmapped mesh or material')
    else:
        raise ValueError('incomplete plan')
    if tool == 'export':
        return
    for item in plan['dropped']:
        if not isinstance(item, dict) or 'face' not in item or 'reason' not in item:
            raise ValueError('incomplete drop')
        if not isinstance(item['reason'], str) or not item['reason']:
            raise ValueError('drop without a reason')


def parse_report(text):
    """Strict complete report; derive status rather than trusting a claimed pass."""
    r = json.loads(text, object_pairs_hook=_unique, parse_constant=_reject)
    if not isinstance(r, dict) or 'tool' not in r or not isinstance(r.get('tool'), str) or r['tool'] not in CODES:
        raise ValueError('unsupported schema/tool')
    expected_keys = {'schema', 'tool', 'status', 'objects'}
    if r['tool'] in ('nudge', 'atlas', 'ucx', 'texel', 'export'):
        expected_keys = expected_keys | {'plan'}
    if set(r) != expected_keys:
        raise ValueError('incomplete report')
    if type(r['schema']) is not int or r['schema'] != 1:
        raise ValueError('unsupported schema/tool')
    if r['tool'] in ('nudge', 'atlas', 'ucx', 'texel', 'export'):
        _validate_plan(r['tool'], r['plan'])
    if not isinstance(r['objects'], list) or not r['objects']:
        raise ValueError('empty objects')
    seen = set()
    for obj in r['objects']:
        if not isinstance(obj, dict) or set(obj) != {'handle', 'name', 'findings'}:
            raise ValueError('incomplete object')
        h = obj['handle']
        if type(h) is not int or h <= 0 or h in seen:
            raise ValueError('invalid/duplicate handle')
        seen.add(h)
        if not isinstance(obj['name'], str) or not obj['name'].strip() or not isinstance(obj['findings'], list):
            raise ValueError('invalid object')
        for f in obj['findings']:
            if not isinstance(f, dict) or set(f) != {'code', 'ids', 'detail'}:
                raise ValueError('incomplete finding')
            if not isinstance(f['code'], str) or f['code'] not in CODES[r['tool']] or not isinstance(f['detail'], str):
                raise ValueError('unmapped finding')
            ids = f['ids']
            if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
                raise ValueError('invalid component IDs')
    expected = 'fail' if any(o['findings'] for o in r['objects']) else 'pass'
    if r['status'] != expected:
        raise ValueError('inconsistent status')
    return r


def _rt():
    from pymxs import runtime
    return runtime


def _targets(nodes):
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection) or list(rt.geometry)
    nodes = list(nodes)
    if not nodes:
        raise ValueError('empty target set')
    handles = []
    for n in nodes:
        if not rt.isValidNode(n) or not rt.canConvertTo(n, rt.Editable_Poly):
            raise ValueError('unsupported geometry: ' + str(n))
        handles.append(int(rt.getHandleByAnim(n)))
    if len(set(handles)) != len(handles):
        raise ValueError('duplicate target handle')
    return nodes


def _entry(n, findings):
    return {'handle': int(_rt().getHandleByAnim(n)), 'name': str(n.name), 'findings': findings}


def _finding(code, ids=(), detail=''):
    return {'code': code, 'ids': sorted(set(int(i) for i in ids)), 'detail': detail}


def _report(tool, entries, nodes, select=True, extra=None):
    report = {'schema': 1, 'tool': tool,
              'status': 'fail' if any(o['findings'] for o in entries) else 'pass', 'objects': entries}
    if extra:
        report.update(extra)
    parse_report(json.dumps(report, allow_nan=False))
    if select:
        _rt().select([n for n, o in zip(nodes, entries) if o['findings']])
    return report


def _poly_copy(n):
    import math
    rt = _rt()
    copy = rt.copy(n)
    try:
        rt.convertToPoly(copy)
        nv, nf = int(rt.polyop.getNumVerts(copy)), int(rt.polyop.getNumFaces(copy))
        if not nv or not nf:
            raise ValueError('empty mesh: ' + str(n.name))
        for i in range(1, nv + 1):
            p = rt.polyop.getVert(copy, i)
            if not all(math.isfinite(float(v)) for v in (p.x, p.y, p.z)):
                raise ValueError('non-finite vertex: ' + str(n.name))
        return copy
    except Exception:
        rt.delete(copy)
        raise


def _reject_vertex_boundary(points, tolerance):
    """Reject the native float32 ambiguity band, without changing checker tolerance."""
    import itertools
    import math
    cells = {}
    width = tolerance * (1 + 2e-7)
    for p in points:
        key = tuple(math.floor(x / width) for x in p)
        for offset in itertools.product((-1, 0, 1), repeat=3):
            for q in cells.get(tuple(k + d for k, d in zip(key, offset)), ()):
                if math.isclose(math.dist(p, q), tolerance, rel_tol=2e-7, abs_tol=0):
                    raise ValueError('vertex exactly at threshold (float32 ambiguity); no clean verdict')
        cells.setdefault(key, []).append(p)


def xview(nodes=None):
    """Native checker on evaluated temporary copies; original geometry is untouched."""
    rt = _rt()
    nodes = _targets(nodes)
    scale = float(rt.units.decodeValue('1m'))
    import math
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('invalid system units')
    rt.execute('''fn agrNativeXView n vt ft = (
        local rv = #(); local rf = #()
        OverlappingVertices.tolerance = vt
        OverlappingFaces.tolerance = ft
        local tv = OverlappingVertices.Check currentTime n &rv
        local tf = OverlappingFaces.Check currentTime n &rf
        if tv != #vertices do throw ("OverlappingVertices failed: " + tv as string)
        if tf != #faces do throw ("OverlappingFaces failed: " + tf as string)
        -- A wider float32 ambiguity probe may reject, never supply findings.
        -- The reported findings above always use the unchanged 5 mm threshold.
        local guard = #()
        OverlappingFaces.tolerance = ft * (1 + 2e-7)
        local tg = OverlappingFaces.Check currentTime n &guard
        if tg != #faces do throw ("OverlappingFaces guard failed: " + tg as string)
        for id in guard where findItem rf id == 0 do
            throw "face exactly at threshold (float32 ambiguity); no clean verdict"
        #(rv, rf)
    )''')
    previous = (rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance)
    entries = []
    try:
        for n in nodes:
            copy = _poly_copy(n)
            try:
                # Native xView reads object-space vertices. Detach the disposable
                # copy (Max preserves its world transform), then bake scale/shear
                # into its mesh. Both native checkers and the boundary guard now
                # measure physical system-unit distances, including parent scale.
                # Never reset transforms on the original or its shared base.
                copy.parent = None
                rt.resetXForm(copy)
                rt.collapseStack(copy)
                rt.convertToPoly(copy)
                _reject_vertex_boundary([tuple(float(v) for v in rt.polyop.getVert(copy, i))
                                         for i in range(1, int(rt.polyop.getNumVerts(copy)) + 1)], 0.002 * scale)
                result = rt.agrNativeXView(copy, 0.002 * scale, 0.005 * scale)
                findings = []
                for ids, code in zip(result, ('overlap_vertices', 'overlap_faces')):
                    if len(ids):
                        findings.append(_finding(code, ids))
                entries.append(_entry(n, findings))
            finally:
                rt.delete(copy)
    finally:
        rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance = previous
    return _report('xview', entries, nodes)


def matid(nodes=None):
    """Native per-face IDs, no material-slot fallback or remapping."""
    rt = _rt()
    nodes = _targets(nodes)
    entries = []
    for n in nodes:
        copy = _poly_copy(n)
        try:
            bad, empty, slots = [], [], []
            material = n.material
            for face in range(1, int(rt.polyop.getNumFaces(copy)) + 1):
                mid = int(rt.polyop.getFaceMatID(copy, face))
                if mid >= 1001:  # same working-ID ceiling as geometry.checks [D030]
                    bad.append(face)
                if mid <= 0:
                    empty.append(face)
                if material is not None and rt.classOf(material) == rt.MultiMaterial:
                    resolved = [material.materialList[i] for i in range(len(material.materialIDList))
                                if int(material.materialIDList[i]) == mid]
                    if len(resolved) != 1 or resolved[0] is None:
                        slots.append(face)
            fs = []
            for code, ids in (('udim_id', bad), ('empty_id', empty), ('empty_slot', slots)):
                if ids:
                    fs.append(_finding(code, ids))
            if material is None:
                fs.append(_finding('missing_material', range(1, int(rt.polyop.getNumFaces(copy)) + 1)))
            entries.append(_entry(n, fs))
        finally:
            rt.delete(copy)
    return _report('matid', entries, nodes)


def _owners(n):
    rt = _rt()
    materials, seen = [], set()

    def visit(m):
        if m is None:
            return
        handle = int(rt.getHandleByAnim(m))
        if handle in seen:
            return
        seen.add(handle)
        materials.append(m)
        for i in range(1, int(rt.getNumSubMtls(m)) + 1):
            visit(rt.getSubMtl(m, i))
    visit(n.material)
    return {'base': [n.baseObject], 'node': [n], 'modifiers': list(n.modifiers), 'materials': materials}


def _attributes(owner):
    rt = _rt()
    return [rt.custAttributes.get(owner, i, baseObject=False)
            for i in range(1, int(rt.custAttributes.count(owner, baseObject=False)) + 1)]


def snapshot(nodes=None):
    """Read-only scene fingerprint and the exact existing hygiene checker schema."""
    rt = _rt()
    nodes = _targets(nodes)
    result = []
    for n in nodes:
        if rt.classOf(n.baseObject) not in (rt.Editable_Poly, rt.Editable_Mesh):
            raise ValueError('unsupported cleanup base class: ' + str(n.name))
        mesh = rt.snapshotAsMesh(n)
        if not int(mesh.numfaces) or not int(mesh.numverts):
            raise ValueError('empty mesh: ' + str(n.name))
        owners = _owners(n)
        attributes = {k: [str(rt.classOf(a)) for owner in values for a in _attributes(owner)]
                      for k, values in owners.items()}
        values = {k: [[str(rt.getProperty(a, p)) for p in rt.getPropNames(a)]
                      for owner in group for a in _attributes(owner)] for k, group in owners.items()}
        channels = [ch for ch in range(1, 100) if rt.meshop.getMapSupport(mesh, ch)]
        geometry = {'vertices': [[float(v) for v in rt.getVert(mesh, i)] for i in range(1, int(mesh.numverts) + 1)],
                    'faces': [str(rt.getFace(mesh, i)) for i in range(1, int(mesh.numfaces) + 1)],
                    'ids': [int(rt.getFaceMatID(mesh, i)) for i in range(1, int(mesh.numfaces) + 1)],
                    'maps': {str(ch): {'vertices': [str(rt.meshop.getMapVert(mesh, ch, i))
                              for i in range(1, int(rt.meshop.getNumMapVerts(mesh, ch)) + 1)],
                              'faces': [str(rt.meshop.getMapFace(mesh, ch, i))
                              for i in range(1, int(rt.meshop.getNumMapFaces(mesh, ch)) + 1)]} for ch in channels}}
        # Numeric coordinates must not serialize as NaN/Infinity.
        json.dumps(geometry, allow_nan=False)
        result.append({'handle': int(rt.getHandleByAnim(n)), 'name': str(n.name),
                       'geometry': geometry, 'attribute_values': values,
                       'material': str(n.material),
                       'hygiene': {'name': str(rt.getHandleByAnim(n)), 'custom_attributes': attributes,
                                   'user_props': str(rt.getUserPropBuffer(n)), 'map_channels': channels}})
    return result


def cleanup_preview(nodes=None):
    """No mutation; use our already-tested repair planner, shipped as an AST slice."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('agr_tools_hygiene', Path(__file__).with_name('hygiene_core.py'))
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    repair_plan = core.repair_plan
    nodes = _targets(nodes)
    state = snapshot(nodes)
    plan = repair_plan([o['hygiene'] for o in state])
    entries = []
    for n, item in zip(nodes, plan['objects']):
        if item['unrepairable']:
            raise ValueError(str(n.name) + ': ' + '; '.join(item['unrepairable']))
        entries.append(_entry(n, [_finding(a['action'], detail=json.dumps(a, sort_keys=True))
                                  for a in item['actions']]))
    return {'state': state, 'plan': plan, 'report': _report('cleanup', entries, nodes, select=False)}


def cleanup_apply(nodes, preview):
    """Apply only a current, unaltered preview to fresh deep export-copy nodes."""
    rt = _rt()
    nodes = _targets(nodes)
    current = cleanup_preview(nodes)
    if preview != current:
        raise ValueError('stale or altered cleanup preview; run dry-run again')
    copies = []
    try:
        for n, item in zip(nodes, current['plan']['objects']):
            c = rt.copy(n)
            copies.append(c)
            c.name = rt.uniqueName(str(n.name) + '_AGR_export_')
            if n.material is not None:
                c.material = rt.copy(n.material)
            for group in _owners(c).values():
                for owner in group:
                    for i in range(len(_attributes(owner)), 0, -1):
                        rt.custAttributes.delete(owner, i, baseObject=False)
            for ch in item['cleaned']['map_channels']:
                if ch != 1:
                    raise ValueError('unmapped cleaned map channel: ' + str(ch))
            for ch in current['state'][len(copies) - 1]['hygiene']['map_channels']:
                if ch > 1:
                    api = rt.polyop if rt.classOf(c.baseObject) == rt.Editable_Poly else rt.meshop
                    api.setMapSupport(c.baseObject, ch, False)
            rt.setUserPropBuffer(c, item['cleaned']['user_props'])
        after = cleanup_preview(copies)['report']
        if after['status'] != 'pass':
            raise RuntimeError('cleanup verification failed: ' + json.dumps(after))
        if snapshot(nodes) != current['state']:
            raise RuntimeError('originals changed during cleanup')
        rt.select(copies)
        return copies, after
    except Exception:
        if copies:
            rt.delete(copies)
        raise


def _load_core(filename, module_name):
    import importlib.util
    import sys
    from pathlib import Path
    path = Path(__file__).with_name(filename)
    if not path.is_file():
        raise ValueError('missing bundled core: ' + filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    core = importlib.util.module_from_spec(spec)
    # dataclasses resolve the class module through sys.modules during class creation.
    sys.modules[module_name] = core
    spec.loader.exec_module(core)
    return core


def _max_array(values):
    return _rt().execute('#(' + ','.join(str(int(v)) for v in values) + ')')


def _as_indices(face):
    if hasattr(face, 'count'):
        return [int(face[i]) for i in range(int(face.count))]
    return [int(face.x), int(face.y), int(face.z)]


def _edit_target(n):
    rt = _rt()
    kind = rt.classOf(n.baseObject)
    if kind == rt.Editable_Poly:
        return rt.polyop, n
    if kind == rt.Editable_Mesh:
        return rt.meshop, n.baseObject
    raise ValueError('unsupported geometry: ' + str(n.name))


def _read_channel(n):
    """Base-object channel 1. Missing, empty and non-finite data are errors."""
    import math
    rt = _rt()
    api, target = _edit_target(n)
    if not api.getMapSupport(target, 1):
        raise ValueError('missing UV channel 1: ' + str(n.name))
    nv = int(api.getNumVerts(target))
    nf = int(api.getNumFaces(target))
    nu = int(api.getNumMapVerts(target, 1))
    if not nv or not nf or not nu:
        raise ValueError('empty mesh: ' + str(n.name))
    vertices, uvs, faces, fuv, ids = [], [], [], [], []
    for i in range(1, nv + 1):
        p = api.getVert(target, i)
        point = (float(p.x), float(p.y), float(p.z))
        if not all(math.isfinite(c) for c in point):
            raise ValueError('non-finite vertex: ' + str(n.name))
        vertices.append(point)
    for i in range(1, nu + 1):
        p = api.getMapVert(target, 1, i)
        point = (float(p.x), float(p.y))
        if not all(math.isfinite(c) for c in point):
            raise ValueError('non-finite UV: ' + str(n.name))
        uvs.append(point)
    for i in range(1, nf + 1):
        faces.append([int(v) - 1 for v in _as_indices(api.getFaceVerts(target, i))])
        fuv.append([int(v) - 1 for v in _as_indices(api.getMapFace(target, 1, i))])
        ids.append(int(api.getFaceMatID(target, i)))
    return {'vertices': vertices, 'uvs': uvs, 'faces': faces, 'face_uvs': fuv, 'ids': ids}


def _write_channel(n, uvs, face_uvs):
    rt = _rt()
    api, target = _edit_target(n)
    api.setMapSupport(target, 1, True)
    api.setNumMapVerts(target, 1, len(uvs))
    for i, (u, v) in enumerate(uvs, 1):
        api.setMapVert(target, 1, i, rt.point3(float(u), float(v), 0.0))
    for face, indices in enumerate(face_uvs, 1):
        api.setMapFace(target, 1, face, _max_array([i + 1 for i in indices]))


def _prop(n, key):
    raw = _rt().getUserProp(n, key)
    if raw is None:
        return None
    text = str(raw).strip()
    if text in ('', 'undefined', 'None'):
        return None
    return text


def _material_names(n, face_ids):
    rt = _rt()
    mat = n.material
    if mat is None:
        raise ValueError('missing material: ' + str(n.name))
    if rt.classOf(mat) == rt.MultiMaterial:
        names = []
        for mid in face_ids:
            resolved = [(i, mat.materialList[i]) for i in range(len(mat.materialIDList))
                        if int(mat.materialIDList[i]) == int(mid)]
            if len(resolved) != 1 or resolved[0][1] is None:
                raise ValueError(f'material slot {mid} has no definition')
            names.append(str(resolved[0][1].name))
        return names
    return [str(mat.name)] * len(face_ids)


def _submaterials(n):
    rt = _rt()
    mat = n.material
    if mat is None:
        raise ValueError('missing material: ' + str(n.name))
    if rt.classOf(mat) == rt.MultiMaterial:
        found = {}
        for i in range(len(mat.materialIDList)):
            sub = mat.materialList[i]
            if sub is None:
                raise ValueError(f"material slot {int(mat.materialIDList[i])} has no definition")
            name = str(sub.name)
            if name in found and found[name] is not sub:
                raise ValueError('duplicate material name: ' + name)
            found[name] = sub
        return found
    return {str(mat.name): mat}


def _period_map(n, names):
    text = _prop(n, 'AGR_UV_PERIODS')
    if text is None:
        raise ValueError(f"material {next(iter(dict.fromkeys(names)))!r} has no period entry (repeating or None)")
    mapping = {}
    for part in text.split(';'):
        part = part.strip()
        if not part:
            continue
        if '=' not in part:
            raise ValueError('partial UV period entry: ' + part)
        name, val = (piece.strip() for piece in part.split('=', 1))
        if name in mapping:
            raise ValueError('duplicate key: ' + name)
        if val.lower() == 'none':
            mapping[name] = None
            continue
        bits = [b.strip() for b in val.split(',')]
        if len(bits) != 2:
            raise ValueError(f"material {name!r}: period must be (pu, pv) or None, got {val!r}")
        try:
            mapping[name] = (float(bits[0]), float(bits[1]))
        except ValueError:
            raise ValueError(f"material {name!r}: period must be (pu, pv) or None, got {val!r}") from None
    return mapping


def _target_tile(n):
    text = _prop(n, 'AGR_UV_TARGET')
    if text is None:
        return 1001
    try:
        value = float(text)
    except ValueError:
        raise ValueError('unmapped target tile: ' + text) from None
    if not value.is_integer():
        raise ValueError('unmapped target tile: ' + text)
    return int(value)


def _nudge_plan(result):
    islands, findings = [], []
    for island in result.islands:
        entry = {'faces': [f + 1 for f in island['faces']],
                 'steps': [int(island['steps'][0]), int(island['steps'][1])],
                 'shift': [float(island['shift'][0]), float(island['shift'][1])],
                 'materials': [str(m) for m in island['materials']],
                 'reason': island['reason']}
        islands.append(entry)
        if entry['steps'] != [0, 0]:
            findings.append(_finding('tile_move', entry['faces'], json.dumps(
                {'materials': entry['materials'], 'reason': entry['reason'],
                 'shift': entry['shift'], 'steps': entry['steps']}, sort_keys=True)))
    return islands, findings


def nudge_preview(nodes=None):
    """Dry-run. Channel-1 islands move by the bundled uv_nudge slice; the scene is unchanged."""
    core = _load_core('uv_nudge_core.py', 'agr_tools_uv_nudge')
    nodes = _targets(nodes)
    state, plans, entries = [], [], []
    for n in nodes:
        mesh = _read_channel(n)
        names = _material_names(n, mesh['ids'])
        result = core.nudge_repeating_islands(
            mesh['uvs'], mesh['face_uvs'], names, _period_map(n, names), target_tile=_target_tile(n))
        islands, findings = _nudge_plan(result)
        covered = sorted(f for island in islands for f in island['faces'])
        if covered != list(range(1, len(mesh['faces']) + 1)):
            raise ValueError('nudge dropped a face without a reason')
        state.append(mesh)
        plans.append({'uvs': result.uv, 'face_uvs': mesh['face_uvs'], 'islands': islands})
        entries.append(_entry(n, findings))
    report = _report('nudge', entries, nodes, select=False, extra={
        'plan': {'islands': [i for plan in plans for i in plan['islands']], 'dropped': []}})
    return {'state': state, 'plans': plans, 'report': report}


def _apply_uv(nodes, preview, current, label):
    rt = _rt()
    copies = []
    try:
        for n, plan in zip(nodes, current['plans']):
            c = rt.copy(n)
            copies.append(c)
            c.name = rt.uniqueName(str(n.name) + label)
            # Node user properties carry the explicit period and atlas settings.
            rt.setUserPropBuffer(c, rt.getUserPropBuffer(n))
            if n.material is not None:
                c.material = rt.copy(n.material)
            _write_channel(c, plan['uvs'], plan['face_uvs'])
            written = _read_channel(c)
            for got, exp in zip(written['uvs'], plan['uvs']):
                assert_uv_close(got, exp)
            if written['vertices'] != current['state'][len(copies) - 1]['vertices']:
                raise RuntimeError('export copy geometry changed')
        if [ _read_channel(n)['uvs'] for n in nodes ] != [item['uvs'] for item in preview['state']]:
            raise RuntimeError('originals changed during apply')
        rt.select(copies)
        return copies
    except Exception:
        if copies:
            rt.delete(copies)
        raise


def nudge_apply(nodes, preview):
    """Apply a current nudge preview to new export copies only."""
    nodes = _targets(nodes)
    current = nudge_preview(nodes)
    if preview['report'] != current['report'] or preview['plans'] != current['plans']:
        raise ValueError('stale or altered nudge preview; run dry-run again')
    copies = _apply_uv(nodes, preview, current, '_AGR_nudge_')
    after = nudge_preview(copies)['report']
    return copies, after


def _channels(color):
    if isinstance(color, (tuple, list)):
        if len(color) < 4:
            raise ValueError('partial material bitmap')
        return tuple(int(round(float(c))) for c in color[:4])
    return (int(round(float(color.r))), int(round(float(color.g))), int(round(float(color.b))),
            int(round(float(color.a))))


def bitmap_rows(width, height, read_span):
    """Read one scanline per row. A single ``width * height`` span stops at the first row."""
    if width <= 0 or height <= 0:
        raise ValueError('material bitmap has no pixels')
    rgb, alpha = [], []
    for y in range(height):
        pixels = list(read_span(0, y, width))
        if len(pixels) != width:
            raise ValueError('partial material bitmap')
        row, arow = [], []
        for color in pixels:
            r, g, b, a = _channels(color)
            row.append((r, g, b))
            arow.append(a)
        rgb.append(row)
        alpha.append(arow)
    return rgb, alpha


# Bitmaptexture coordinates the atlas can consume. Anything else is rejected by name
# before a copy, an atlas file or a replacement material exists.
MAP_COORD_TOL = 1e-9
NEUTRAL_MAP_COORDINATES = (
    ('U_Tiling', 1.0, 'float'),
    ('V_Tiling', 1.0, 'float'),
    ('U_Offset', 0.0, 'float'),
    ('V_Offset', 0.0, 'float'),
    ('U_Angle', 0.0, 'float'),
    ('V_Angle', 0.0, 'float'),
    ('W_Angle', 0.0, 'float'),
    ('U_Mirror', False, 'bool'),
    ('V_Mirror', False, 'bool'),
    ('U_Tile', True, 'bool'),
    ('V_Tile', True, 'bool'),
    ('mapChannel', 1, 'int'),
)


def format_map_coordinate_value(value):
    """Stable `<setting>=<value>` text. Non-finite floats stay visible as nan/inf."""
    import math
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return 'nan'
        if math.isinf(value):
            return 'inf' if value > 0 else '-inf'
        nearest = round(value)
        if abs(value - nearest) <= MAP_COORD_TOL:
            return str(int(nearest))
        return format(value, '.12g')
    return 'unreadable'


def unsupported_map_coordinate(material, slot, setting, value):
    shown = 'unreadable' if value == 'unreadable' else format_map_coordinate_value(value)
    return f'unsupported map coordinate: {material} {slot} {setting}={shown}'


def assert_neutral_map_coordinates(material, slot, values):
    """Accept only the neutral coordinate contract. Missing and non-finite values are errors."""
    import math
    if not isinstance(values, dict):
        raise ValueError(unsupported_map_coordinate(material, slot, 'coords', 'unreadable'))
    for setting, expected, kind in NEUTRAL_MAP_COORDINATES:
        if setting not in values:
            raise ValueError(unsupported_map_coordinate(material, slot, setting, 'unreadable'))
        value = values[setting]
        if kind == 'float':
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(unsupported_map_coordinate(material, slot, setting, 'unreadable'))
            number = float(value)
            if not math.isfinite(number) or abs(number - float(expected)) > MAP_COORD_TOL:
                raise ValueError(unsupported_map_coordinate(material, slot, setting, number))
        elif kind == 'bool':
            if not isinstance(value, bool) or value != expected:
                shown = value if isinstance(value, bool) else 'unreadable'
                raise ValueError(unsupported_map_coordinate(material, slot, setting, shown))
        elif kind == 'int':
            if isinstance(value, bool) or not isinstance(value, int) or int(value) != expected:
                shown = value if isinstance(value, int) and not isinstance(value, bool) else 'unreadable'
                raise ValueError(unsupported_map_coordinate(material, slot, setting, shown))
        else:
            raise ValueError(unsupported_map_coordinate(material, slot, setting, 'unreadable'))


def _coerce_map_coordinate(raw, kind):
    import math
    if kind == 'float':
        if isinstance(raw, bool):
            raise TypeError('coordinate is not a float')
        return float(raw)
    if kind == 'bool':
        if isinstance(raw, bool):
            return bool(raw)
        raise TypeError('coordinate is not a bool')
    if kind == 'int':
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise TypeError('coordinate is not an int')
        return int(raw)
    raise TypeError('unknown coordinate kind')


def _read_map_coordinates(tex):
    """Read supported StandardUVGen fields. A failure is unreadable, never neutral."""
    rt = _rt()
    try:
        coords = tex.coords
        coords_class = str(rt.classOf(coords))
    except Exception:
        raise ValueError('unreadable:coords')
    if coords is None or coords_class in ('undefined', 'UndefinedClass', 'None', ''):
        raise ValueError('unreadable:coords')
    values = {}
    for setting, _expected, kind in NEUTRAL_MAP_COORDINATES:
        try:
            raw = getattr(coords, setting)
        except Exception:
            raise ValueError('unreadable:' + setting)
        try:
            values[setting] = _coerce_map_coordinate(raw, kind)
        except (TypeError, ValueError):
            raise ValueError('unreadable:' + setting)
    return values


def _require_neutral_bitmap_coordinates(material, slot, tex):
    try:
        values = _read_map_coordinates(tex)
    except ValueError as exc:
        text = str(exc)
        if text.startswith('unreadable:'):
            raise ValueError(unsupported_map_coordinate(material, slot, text.split(':', 1)[1], 'unreadable')) from exc
        raise
    assert_neutral_map_coordinates(material, slot, values)


def _bitmap_texture(tex):
    return _map_assigned(tex) and _rt().classOf(tex) == _rt().Bitmaptexture


def _live_bitmap(tex):
    rt = _rt()
    try:
        live = tex.bitmap
    except Exception:
        live = None
    if live is None:
        return None, False
    try:
        width = int(live.width)
    except Exception:
        return None, False
    if width <= 0:
        return None, False
    return live, False


def _bitmap_rgb(tex, material=None, slot=None):
    rt = _rt()
    if rt.classOf(tex) != rt.Bitmaptexture:
        raise ValueError('unmapped material map class: ' + str(rt.classOf(tex)))
    # Coordinate rejection happens before any pixel read, copy or atlas file.
    if material is not None and slot is not None:
        _require_neutral_bitmap_coordinates(material, slot, tex)
    bm, opened = _live_bitmap(tex)
    filename = str(getattr(tex, 'filename', '') or '')
    if filename not in ('', 'undefined', 'None'):
        from pathlib import Path
        if Path(filename).is_file():
            bm = rt.openBitMap(filename)
            opened = True
            if bm is None:
                raise ValueError('material bitmap cannot be opened: ' + filename)
    if bm is None:
        raise ValueError('material bitmap cannot be opened: ' + filename)
    try:
        w, h = int(bm.width), int(bm.height)
        if w <= 0 or h <= 0:
            raise ValueError('material bitmap has no pixels: ' + filename)

        def read_span(x, y, count, bm=bm):
            return rt.getPixels(bm, rt.point2(x, y), count)

        try:
            return bitmap_rows(w, h, read_span)
        except ValueError as exc:
            if str(exc) == 'partial material bitmap':
                raise ValueError('partial material bitmap: ' + filename) from exc
            raise
    finally:
        if opened:
            rt.close(bm)


def _map_assigned(tex):
    if tex is None:
        return False
    kind = str(_rt().classOf(tex))
    return kind not in ('undefined', 'UndefinedClass', 'None')


def _atlas_materials(n):
    import math
    specs = {}
    for name, mat in _submaterials(n).items():
        diffuse_map = mat.diffuseMap if hasattr(mat, 'diffuseMap') else None
        opacity_map = mat.opacityMap if hasattr(mat, 'opacityMap') else None
        has_diffuse = _map_assigned(diffuse_map)
        has_opacity = _map_assigned(opacity_map)
        # Reject before any bitmap read or export copy. Unsupported opacity is not opaque Kd.
        if has_opacity and not has_diffuse:
            raise ValueError(f"material {name!r}: map_d without map_Kd is not supported")
        if has_diffuse and _bitmap_texture(diffuse_map):
            _require_neutral_bitmap_coordinates(name, 'diffuse', diffuse_map)
        if has_opacity and _bitmap_texture(opacity_map):
            _require_neutral_bitmap_coordinates(name, 'opacity', opacity_map)
        dis = float(mat.opacity) / 100.0
        if not math.isfinite(dis):
            raise ValueError(f"material {name!r}: dissolve {dis} outside 0..1")
        if has_diffuse:
            rgb, alpha = _bitmap_rgb(diffuse_map, name, 'diffuse')
            spec = {'rgb': rgb, 'dissolve': dis}
            if any(a < 255 for row in alpha for a in row):
                spec['alpha'] = alpha
            if has_opacity:
                orgb, oalpha = _bitmap_rgb(opacity_map, name, 'opacity')
                if any(a < 255 for row in oalpha for a in row):
                    spec['opacity_alpha'] = True
                spec['opacity'] = [[px[0] for px in row] for row in orgb]
            specs[name] = spec
        else:
            color = mat.diffuse
            specs[name] = {'color': (int(round(float(color.r))), int(round(float(color.g))),
                                     int(round(float(color.b)))),
                           'dissolve': dis}
    return specs


def _atlas_settings(n):
    mode = _prop(n, 'AGR_ATLAS_MODE')
    if mode not in ('ground', 'oks'):
        raise ValueError('unmapped atlas mode: ' + str(mode))
    size_text = _prop(n, 'AGR_ATLAS_SIZE')
    if size_text not in ('1024', '2048'):
        raise ValueError('unmapped atlas size: ' + str(size_text))
    return mode, int(size_text)


def _unit_m():
    import math
    scale = float(_rt().units.decodeValue('1m'))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('invalid system units')
    return 1.0 / scale


def atlas_preview(nodes=None):
    """Dry-run the bundled atlas layout. Reports tiles and cells; the scene is unchanged."""
    core = _load_core('atlas_core.py', 'agr_tools_atlas')
    nodes = _targets(nodes)
    state, plans, entries, images = [], [], [], []
    tiles, cells = [], {}
    for n in nodes:
        mesh = _read_channel(n)
        names = _material_names(n, mesh['ids'])
        mode, size = _atlas_settings(n)
        specs = _atlas_materials(n)
        try:
            laid = core.pack(mesh['vertices'], mesh['uvs'], mesh['faces'], mesh['face_uvs'], names,
                             specs, mode=mode, size=size, pad=8, unit_m=_unit_m())
        except core.AtlasError as exc:
            raise ValueError(str(exc)) from exc
        if laid['dropped']:
            raise ValueError('atlas dropped a face: ' + json.dumps(laid['dropped']))
        if len(laid['face_uvs']) != len(mesh['faces']):
            raise ValueError('atlas face count differs from the input')
        changed = []
        for face, (old, new) in enumerate(zip(mesh['face_uvs'], laid['face_uvs']), 1):
            old_pts = [mesh['uvs'][i] for i in old]
            new_pts = [laid['uvs'][i] for i in new]
            moved = len(old_pts) != len(new_pts)
            if not moved:
                for a, b in zip(old_pts, new_pts):
                    try:
                        assert_uv_close(a, b)
                    except ValueError:
                        moved = True
                        break
            if moved:
                changed.append(face)
        findings = [_finding('atlas_cell', changed, json.dumps(
            {'tiles': laid['tiles'], 'cells': laid['cells']}, sort_keys=True))] if changed else []
        state.append(mesh)
        plans.append({'uvs': laid['uvs'], 'face_uvs': laid['face_uvs'], 'tiles': laid['tiles'],
                      'cells': laid['cells']})
        images.append({'rgb': laid['rgb'], 'alpha': laid['alpha'], 'size': laid['size'],
                       'cells': laid['cells'], 'kinds': laid['kinds'], 'materials': specs})
        tiles.extend(laid['tiles'])
        for name, box in laid['cells'].items():
            if name in cells and cells[name] != box:
                raise ValueError('duplicate material name: ' + name)
            cells[name] = box
        entries.append(_entry(n, findings))
    report = _report('atlas', entries, nodes, select=False, extra={
        'plan': {'tiles': sorted(set(tiles)), 'cells': cells, 'dropped': []}})
    return {'state': state, 'plans': plans, 'report': report, 'images': images}


def _write_bitmap(size, fill, rows):
    """rows(y) -> sequence of colors for one full scanline. The bitmap stays in memory."""
    rt = _rt()
    bm = rt.bitmap(size, size, color=fill)
    for y, colors in rows:
        rt.setPixels(bm, rt.point2(0, y), colors)
    return bm


def save_bitmap(bm):
    """Write the stored 8-bit pixels. PNG alpha is kept, and OCIO does not re-encode them."""
    rt = _rt()
    previous_alpha = rt.execute('pngio.getAlpha()')
    rt.execute('pngio.setAlpha true')
    try:
        try:
            # Max 2026 OCIO converts on save unless this override is set. Gamma 1 is the
            # 2024 path and the fallback where the keyword is absent.
            rt.save(bm, gamma=1.0, outputColorConversion=rt.name('noConversion'))
        except Exception:
            rt.save(bm, gamma=1.0)
    finally:
        rt.execute('pngio.setAlpha ' + ('true' if previous_alpha else 'false'))


def _publish_bitmap(bm, label):
    """Save a new PNG, then bind it. Max refuses an unsaved bitmap on Bitmaptexture."""
    import os
    import uuid
    from pathlib import Path
    rt = _rt()
    root = os.environ.get('AGR_TEST_OUTPUT')
    if root:
        folder = Path(root) / 'atlases'
    else:
        folder = Path(str(rt.getDir(rt.name('temp')))) / 'agr-tools-atlases'
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f'{label}-{uuid.uuid4().hex}.png'
    if dest.exists():
        raise RuntimeError('atlas bitmap already exists: ' + str(dest))
    bm.filename = str(dest)
    save_bitmap(bm)
    if not dest.is_file():
        raise RuntimeError('atlas bitmap was not saved: ' + str(dest))
    tex = rt.Bitmaptexture()
    tex.name = label
    tex.filename = str(dest)
    return tex


def _bind_atlas(node, image):
    """Point bitmap materials at the generated atlas. Flat Kd plugs keep their colour."""
    specs = image['materials']
    if not any('rgb' in spec for spec in specs.values()):
        return
    rt = _rt()
    # Re-check the copy before any atlas PNG or Bitmaptexture is created.
    for name, mat in _submaterials(node).items():
        if name not in specs or 'rgb' not in specs[name]:
            continue
        diffuse_map = mat.diffuseMap if hasattr(mat, 'diffuseMap') else None
        opacity_map = mat.opacityMap if hasattr(mat, 'opacityMap') else None
        if _bitmap_texture(diffuse_map):
            _require_neutral_bitmap_coordinates(name, 'diffuse', diffuse_map)
        if _bitmap_texture(opacity_map):
            _require_neutral_bitmap_coordinates(name, 'opacity', opacity_map)
    size = image['size']
    rgb, alpha = image['rgb'], image['alpha']
    dirty = set()
    for box in image['cells'].values():
        y, h = box[1], box[3]
        dirty.update(range(y, y + h))

    def diffuse_rows():
        for y in sorted(dirty):
            base = y * size * 3
            colors = []
            for x in range(size):
                o = base + x * 3
                colors.append(rt.color(int(rgb[o]), int(rgb[o + 1]), int(rgb[o + 2])))
            yield y, colors

    diffuse = _publish_bitmap(_write_bitmap(size, rt.color(90, 90, 90), diffuse_rows()), 'AGR_atlas_diffuse')
    opacity = None
    if alpha is not None:
        def opacity_rows():
            for y in sorted(dirty):
                base = y * size
                colors = []
                for x in range(size):
                    v = int(alpha[base + x])
                    colors.append(rt.color(v, v, v))
                yield y, colors

        opacity = _publish_bitmap(_write_bitmap(size, rt.color(255, 255, 255), opacity_rows()), 'AGR_atlas_opacity')
    for name, mat in _submaterials(node).items():
        if name not in specs or 'rgb' not in specs[name]:
            continue
        mat.diffuse = rt.color(255, 255, 255)
        mat.opacity = 100.0
        mat.diffuseMap = diffuse
        if opacity is not None:
            mat.opacityMap = opacity


def _applied_atlas_report(copies, current):
    """Read back the written UVs. Flat Kd copies are previewed again; a bound atlas is not repacked."""
    entries = []
    tiles, cells = [], {}
    for copy, plan, image in zip(copies, current['plans'], current['images']):
        written = _read_channel(copy)
        for got, exp in zip(written['uvs'], plan['uvs']):
            assert_uv_close(got, exp)
        if written['face_uvs'] != [list(face) for face in plan['face_uvs']]:
            raise RuntimeError('atlas face UVs do not match the preview')
        bound = any('rgb' in spec for spec in image['materials'].values())
        if bound:
            entries.append(_entry(copy, []))
        else:
            again = atlas_preview([copy])
            if again['report']['objects'][0]['findings']:
                raise RuntimeError('flat atlas copy is not a fixed point')
            entries.append(again['report']['objects'][0])
        tiles.extend(plan['tiles'])
        for name, box in plan['cells'].items():
            if name in cells and cells[name] != box:
                raise ValueError('duplicate material name: ' + name)
            cells[name] = box
    return _report('atlas', entries, copies, select=False, extra={
        'plan': {'tiles': sorted(set(tiles)), 'cells': cells, 'dropped': []}})


def atlas_apply(nodes, preview):
    """Remap UVs on new export copies and bind the matching atlas. Sources stay unchanged."""
    rt = _rt()
    nodes = _targets(nodes)
    current = atlas_preview(nodes)
    if preview['report'] != current['report'] or preview['plans'] != current['plans']:
        raise ValueError('stale or altered atlas preview; run dry-run again')
    copies = _apply_uv(nodes, preview, current, '_AGR_atlas_')
    try:
        for copy, image in zip(copies, current['images']):
            _bind_atlas(copy, image)
        after = _applied_atlas_report(copies, current)
    except Exception:
        if copies:
            rt.delete(copies)
        raise
    return copies, after


def _matrix_rows(tm):
    """Max Matrix3 exposes row1..row4. A test double may expose ``rows`` instead."""
    if all(hasattr(tm, name) for name in ('row1', 'row2', 'row3', 'row4')):
        rows = []
        for attr in ('row1', 'row2', 'row3', 'row4'):
            row = getattr(tm, attr)
            rows.append((float(row.x), float(row.y), float(row.z)))
        return tuple(rows)
    if hasattr(tm, 'rows'):
        rows = []
        for row in tm.rows:
            if len(row) != 3:
                raise ValueError('partial transform')
            rows.append(tuple(float(c) for c in row))
        if len(rows) != 4:
            raise ValueError('partial transform')
        return tuple(rows)
    raise ValueError('partial transform')


def _bounds_of(points):
    if not points:
        raise ValueError('empty bounds')
    return (
        tuple(min(point[axis] for point in points) for axis in range(3)),
        tuple(max(point[axis] for point in points) for axis in range(3)),
    )


def _read_world(n):
    """Evaluated world-space triangles in metres. Empty and non-finite geometry are errors.

    ``snapshotAsMesh`` is the world-state mesh (modifiers and the node transform).
    With no modifiers, that result must match object-space vertices times ``objectTransform``.
    """
    import math
    rt = _rt()
    mesh = rt.snapshotAsMesh(n)
    nv = int(mesh.numverts)
    nf = int(mesh.numfaces)
    if not nv or not nf:
        raise ValueError('empty mesh: ' + str(n.name))
    to_m = _unit_m()
    verts = []
    for i in range(1, nv + 1):
        p = rt.getVert(mesh, i)
        point = (float(p.x) * to_m, float(p.y) * to_m, float(p.z) * to_m)
        if not all(math.isfinite(c) for c in point):
            raise ValueError('non-finite vertex: ' + str(n.name))
        verts.append(point)
    tris = []
    for i in range(1, nf + 1):
        raw = rt.getFace(mesh, i)
        face = [int(v) - 1 for v in _as_indices(raw)]
        if len(face) != 3 or any(index < 0 or index >= nv for index in face):
            raise ValueError('partial face: ' + str(n.name))
        tris.append(tuple(face))
    if not list(n.modifiers):
        # Editable Poly's polyop.getVert(node) is already world space on Max 2024.
        # Editable Mesh's meshop.getVert(base) is object space and needs objectTransform.
        core = _load_core('ucx_core.py', 'agr_tools_ucx')
        kind = rt.classOf(n.baseObject)
        predicted = []
        if kind == rt.Editable_Mesh:
            tm = n.objectTransform
            local = []
            count = int(rt.meshop.getNumVerts(n.baseObject))
            for i in range(1, count + 1):
                p = rt.meshop.getVert(n.baseObject, i)
                local.append((float(p.x), float(p.y), float(p.z)))
                world = p * tm
                predicted.append((float(world.x) * to_m, float(world.y) * to_m, float(world.z) * to_m))
            via_rows = core.world_metres(local, _matrix_rows(tm), to_m)
            core.assert_world_bounds(_bounds_of(verts), _bounds_of(via_rows))
        elif kind == rt.Editable_Poly:
            count = int(rt.polyop.getNumVerts(n))
            for i in range(1, count + 1):
                p = rt.polyop.getVert(n, i)
                predicted.append((float(p.x) * to_m, float(p.y) * to_m, float(p.z) * to_m))
        else:
            raise ValueError('unsupported geometry: ' + str(n.name))
        core.assert_world_bounds(_bounds_of(verts), _bounds_of(predicted))
    return verts, tris


def _ucx_record(n, verts, tris):
    rt = _rt()
    parent = n.parent
    material = n.material
    return {
        'handle': int(rt.getHandleByAnim(n)),
        'name': str(n.name),
        'base_class': str(rt.classOf(n.baseObject)),
        'transform': str(n.transform),
        'object_transform': str(n.objectTransform),
        'parent': None if parent is None else int(rt.getHandleByAnim(parent)),
        'properties': str(rt.getUserPropBuffer(n)),
        'material': None if material is None else str(material.name),
        'vertices': [tuple(point) for point in verts],
        'faces': [tuple(face) for face in tris],
    }


def _ucx_kind(n):
    kind = _prop(n, 'AGR_UCX_KIND')
    if kind is None:
        return None
    return kind


def _ucx_plan(results):
    kinds = []
    variants = []
    names = []
    collision = []
    unmeasurable = []
    mask = 0
    closed = True
    for result in results:
        kinds.append(result['kind'])
        variants.append(result['variant'])
        names.extend(result['names'])
        collision.extend(result['audit']['collision'])
        unmeasurable.extend(result['audit']['unmeasurable'])
        mask += result['audit']['mask_bad_count']
        closed = closed and result['audit']['closed']
    return {
        'variant': variants[0] if len(set(variants)) == 1 else ';'.join(variants),
        'kind': kinds[0] if len(set(kinds)) == 1 else ';'.join(kinds),
        'pieces': sum(result['pieces_count'] for result in results),
        'triangles': sum(result['triangles'] for result in results),
        'limit': min(result['limit'] for result in results),
        'names': names,
        'audit': {'collision': collision, 'unmeasurable': unmeasurable,
                  'mask_bad_count': mask, 'closed': closed},
        'dropped': [],
    }


def ucx_preview(nodes=None):
    """Dry-run UCX pieces, triangle budget and the audit verdict. The scene is unchanged."""
    core = _load_core('ucx_core.py', 'agr_tools_ucx')
    nodes = _targets(nodes)
    results, entries, records = [], [], []
    for n in nodes:
        verts, tris = _read_world(n)
        result = core.build(verts, tris, mesh=str(n.name), kind=_ucx_kind(n))
        results.append(result)
        records.append(_ucx_record(n, verts, tris))
        entries.append(_entry(n, [_finding(item['code'], item['ids'], item['detail']) for item in result['findings']]))
    report = _report('ucx', entries, nodes, extra={'plan': _ucx_plan(results)})
    return {'report': report, 'plans': results, 'geometry': records, 'digest': core.geometry_digest(records)}


def _make_ucx_mesh(name, verts_m, tris):
    rt = _rt()
    scale = 1.0 / _unit_m()
    vertices = [rt.point3(*(coord * scale for coord in point)) for point in verts_m]
    faces = [rt.point3(a + 1, b + 1, c + 1) for a, b, c in tris]
    node = rt.mesh(name=name, vertices=vertices, faces=faces)
    rt.convertToPoly(node)
    try:
        node.material = None
    except Exception:
        pass
    return node


def ucx_apply(nodes, preview):
    """Build UCX on new export copies. Source nodes are not edited.

    The preview is bound to evaluated geometry, transform, identity and properties.
    The export name and every UCX name are reserved, and each piece audit must
    pass, before any node is created. A failed audit creates nothing.
    """
    rt = _rt()
    nodes = _targets(nodes)
    if not isinstance(preview, dict):
        raise ValueError('partial ucx preview')
    for key in ('geometry', 'digest', 'report'):
        if key not in preview:
            raise ValueError('unmapped key ' + key)
    core = _load_core('ucx_core.py', 'agr_tools_ucx')
    current = ucx_preview(nodes)
    core.assert_preview_current(preview['geometry'], current['geometry'])
    if preview['digest'] != current['digest'] or preview['report'] != current['report']:
        raise ValueError('stale or altered ucx preview; run dry-run again')
    families = []
    for n, result in zip(nodes, current['plans']):
        families.append(core.assert_ucx_names_bound(str(n.name), result['names']))
    # Reserve the whole corrected family, then refuse a failed piece audit,
    # before copy() or mesh() can touch the scene.
    core.reserve_ucx_names([str(node.name) for node in list(rt.objects)], families)
    for result in current['plans']:
        core.assert_emitted_audit(result['audit'])
    created = []
    try:
        for n, result, (export, pieces) in zip(nodes, current['plans'], families):
            copy = rt.copy(n)
            created.append(copy)
            copy.name = export
            if str(copy.name) != export:
                raise ValueError('occupied name ' + export)
            rt.convertToPoly(copy)
            for (verts, tris), name in zip(result['pieces'], pieces):
                node = _make_ucx_mesh(name, verts, tris)
                created.append(node)
                if str(node.name) != name:
                    raise ValueError('occupied name ' + name)
                core.assert_world_bounds(_bounds_of(_read_world(node)[0]), _bounds_of(verts))
        return created, current['report']
    except Exception:
        if created:
            rt.delete(created)
        raise


def _texel_map(n, names):
    text = _prop(n, 'AGR_TEXEL_MAP')
    if text is None:
        raise ValueError(f"unmapped material {names[0]!r}: no assigned map size")
    mapping = {}
    for part in text.split(';'):
        part = part.strip()
        if not part:
            continue
        if '=' not in part:
            raise ValueError('partial texel map entry: ' + part)
        name, val = (piece.strip() for piece in part.split('=', 1))
        if not name:
            raise ValueError('partial texel map entry: ' + part)
        if name in mapping:
            raise ValueError('duplicate key: ' + name)
        try:
            px = float(val)
        except ValueError:
            raise ValueError(f"unmapped material {name!r}: unsupported map size {val!r}") from None
        mapping[name] = px
    for name in dict.fromkeys(names):
        if name not in mapping:
            raise ValueError(f"unmapped material {name!r}: no assigned map size")
    return mapping


def _texel_payload(n):
    mesh = _read_channel(n)
    names = _material_names(n, mesh['ids'])
    profile = _prop(n, 'AGR_TEXEL_PROFILE')
    if profile not in ('NPM', 'VPM'):
        raise ValueError('unmapped texel profile: ' + str(profile))
    mapping = _texel_map(n, names)
    to_m = _unit_m()
    faces = []
    for index, (face, fuv, material) in enumerate(zip(mesh['faces'], mesh['face_uvs'], names)):
        xyz = [tuple(coord * to_m for coord in mesh['vertices'][i]) for i in face]
        uv = [mesh['uvs'][i] for i in fuv]
        faces.append({'id': str(index + 1), 'mesh': str(n.name), 'material': material, 'xyz': xyz, 'uv': uv})
    materials = [{'name': name, 'map_px': mapping[name]} for name in dict.fromkeys(names)]
    return {'profile': profile, 'materials': materials, 'faces': faces}


def _texel_plan(summaries):
    meshes, materials = [], []
    dropped = []
    for summary in summaries:
        meshes.extend(summary['meshes'])
        materials.extend(summary['materials'])
        dropped.extend(summary['dropped'])
    return {'meshes': meshes, 'materials': materials, 'dropped': dropped}


def texel_preview(nodes=None):
    """Read-only texel min/median. Nothing in the scene is created or edited."""
    core = _load_core('texel_core.py', 'agr_tools_texel')
    nodes = _targets(nodes)
    summaries, entries = [], []
    for n in nodes:
        summary = core.summarize(_texel_payload(n))
        summaries.append(summary)
        findings = []
        outside = [item['face'] + 1 for item in summary['faces'] if item['status'] != 'pass']
        if outside:
            findings.append(_finding('texel_outside', outside, summary['profile']))
        dropped_ids = [item['face'] + 1 for item in summary['dropped']]
        if dropped_ids:
            findings.append(_finding('texel_dropped', dropped_ids, ';'.join(item['reason'] for item in summary['dropped'])))
        entries.append(_entry(n, findings))
    report = _report('texel', entries, nodes, extra={'plan': _texel_plan(summaries)})
    return {'report': report, 'summaries': summaries}


def _tri_mesh(n):
    """Evaluated triangle mesh in metres. The node itself is not edited."""
    rt = _rt()
    mesh = rt.snapshotAsMesh(n)
    to_m = _unit_m()
    count_v, count_f = int(mesh.numverts), int(mesh.numfaces)
    if not count_v or not count_f:
        raise ValueError('empty mesh: ' + str(n.name))
    verts = []
    for index in range(1, count_v + 1):
        point = rt.getVert(mesh, index)
        verts.append([float(point.x) * to_m, float(point.y) * to_m, float(point.z) * to_m])
    faces, ids = [], []
    for index in range(1, count_f + 1):
        face = rt.getFace(mesh, index)
        faces.append([int(face.x) - 1, int(face.y) - 1, int(face.z) - 1])
        ids.append(int(rt.getFaceMatID(mesh, index)))
    json.dumps(verts, allow_nan=False)
    return verts, faces, ids


# Tool instructions, not delivery user-defined properties. They stay on the
# working node and are held off the export copy the hygiene gate reads.
_HELD_OFF = {'AGR_EXPORT_PATH', 'AGR_TEXEL_PROFILE', 'AGR_TEXEL_MAP', 'AGR_UV_PERIODS',
             'AGR_UV_TARGET', 'AGR_ATLAS_MODE', 'AGR_ATLAS_SIZE', 'AGR_UCX_KIND'}


def _delivery_props(buffer):
    kept = []
    for line in str(buffer).splitlines():
        if not line.strip():
            continue
        key = line.split('=', 1)[0].strip()
        if key in _HELD_OFF:
            continue
        kept.append(line)
    return ''.join(line + '\r\n' for line in kept)


def _hygiene_dump(n):
    rt = _rt()
    owners = _owners(n)
    attributes = {key: [str(rt.classOf(attr)) for owner in values for attr in _attributes(owner)]
                  for key, values in owners.items()}
    mesh = rt.snapshotAsMesh(n)
    channels = [ch for ch in range(1, 100) if rt.meshop.getMapSupport(mesh, ch)]
    return {'name': str(n.name), 'custom_attributes': attributes,
            'user_props': _delivery_props(rt.getUserPropBuffer(n)), 'map_channels': channels}


def _slot_gaps(n, ids):
    rt = _rt()
    material = n.material
    if material is None or rt.classOf(material) != rt.MultiMaterial:
        return []
    gaps = []
    for index, mid in enumerate(ids, 1):
        resolved = [material.materialList[i] for i in range(len(material.materialIDList))
                    if int(material.materialIDList[i]) == int(mid)]
        if len(resolved) != 1 or resolved[0] is None:
            gaps.append(index)
    return gaps


def _export_scene(nodes):
    """Read-only scene description. UCX_* nodes are collision pieces, not render meshes."""
    rt = _rt()
    render = [n for n in nodes if not str(n.name).startswith('UCX_')]
    pieces = [n for n in nodes if str(n.name).startswith('UCX_')]
    if not render:
        raise ValueError('empty render set')
    objects = []
    for n in render:
        verts, faces, ids = _tri_mesh(n)
        material = n.material
        objects.append({
            'name': str(n.name),
            'handle': int(rt.getHandleByAnim(n)),
            'material': None if material is None else str(material.name),
            'material_ids': ids,
            'vertices': verts,
            'faces': faces,
            'hygiene': _hygiene_dump(n),
            'slot_gaps': _slot_gaps(n, ids),
            'texel': _texel_payload(n),
        })
    ucx = []
    for n in pieces:
        verts, faces, _ids = _tri_mesh(n)
        ucx.append({'name': str(n.name), 'verts': verts, 'tris': faces})
    return {'objects': objects, 'ucx': ucx, 'units': 'm', 'axis': 'Z-up'}


def _max_source():
    rt = _rt()
    name = str(rt.maxFileName)
    if not name:
        return None
    return str(rt.maxFilePath) + name


def _export_target(nodes, target):
    if target is None:
        target = _prop(nodes[0], 'AGR_EXPORT_PATH')
    if not target:
        raise ValueError('unmapped key AGR_EXPORT_PATH')
    return target


def _repo_root():
    import os
    from pathlib import Path
    env = os.environ.get('AGR_TOOLS_REPO')
    if env:
        return Path(env)
    candidate = Path(__file__).resolve().parents[3]
    if (candidate / 'src' / 'twinqa' / 'fbx_header.py').is_file():
        return candidate
    raise ValueError('unmapped key AGR_TOOLS_REPO')


def _subprocess_export(payload):
    """Run the gate or the readback in the project interpreter when Max lacks numpy."""
    import os
    import subprocess
    root = _repo_root()
    python = os.environ.get('AGR_PYTHON') or str(root / '.venv' / 'Scripts' / 'python.exe')
    if not os.path.isfile(python):
        raise ValueError('unmapped python ' + python)
    code = (
        'import importlib.util, json, sys\n'
        'from pathlib import Path\n'
        'root = Path(sys.argv[1])\n'
        'sys.path[:0] = [str(root / "src"), str(root)]\n'
        'path = root / "adapters" / "max" / "agr_tools" / "export_core.py"\n'
        'spec = importlib.util.spec_from_file_location("agr_tools_export_sub", path)\n'
        'mod = importlib.util.module_from_spec(spec)\n'
        'spec.loader.exec_module(mod)\n'
        'req = json.loads(sys.stdin.read())\n'
        'method = req["method"]\n'
        'if method == "dry_run":\n'
        '    out = mod.dry_run(req["scene"], req["target"], req.get("source"))\n'
        'elif method == "readback":\n'
        '    out = mod.readback(Path(req["target"]).read_bytes())\n'
        'elif method == "finish":\n'
        '    out = mod.finish(req["preview"], req["target"], req.get("report"))\n'
        'else:\n'
        '    raise SystemExit("unmapped method " + str(method))\n'
        'sys.stdout.write(json.dumps(out, allow_nan=False))\n'
    )
    proc = subprocess.run([python, '-c', code, str(root)], input=json.dumps(payload, allow_nan=False).encode('utf-8'),
                          capture_output=True)
    if proc.returncode != 0:
        detail = proc.stderr.decode('utf-8', errors='replace')[-2000:]
        raise RuntimeError(detail or 'export subprocess failed')
    return json.loads(proc.stdout.decode('utf-8'))


def _dry_run_scene(scene, target, source):
    core = _load_core('export_core.py', 'agr_tools_export')
    try:
        return core.dry_run(scene, target, source)
    except (ModuleNotFoundError, ImportError):
        return _subprocess_export({'method': 'dry_run', 'scene': scene, 'target': str(target), 'source': source})


def export_preview(nodes=None, target=None):
    """Dry-run the checked export. The scene and the filesystem are unchanged."""
    nodes = _targets(nodes)
    target = _export_target(nodes, target)
    report = _dry_run_scene(_export_scene(nodes), target, _max_source())
    parse_report(json.dumps(report, allow_nan=False))
    return report


def _write_max_fbx(nodes, path):
    """Export detached copies. Original nodes are read back and must be unchanged."""
    from pathlib import Path
    rt = _rt()
    path = Path(path)
    if path.exists():
        raise FileExistsError(str(path))
    rt.pluginManager.loadClass(rt.FbxExporter)
    params = {'Animation': False, 'EmbedTextures': False, 'ASCII': False,
              'FileVersion': 'FBX201400', 'UpAxis': 'Z', 'Cameras': False,
              'Lights': False, 'Triangulate': True, 'ConvertUnit': 'm'}
    for key, value in params.items():
        rt.FBXExporterSetParam(key, value)
        got = rt.FBXExporterGetParam(key)
        expected = 'false' if value is False else 'true' if value is True else str(value)
        if str(got).lower() != expected.lower():
            raise ValueError(f'unmapped export setting {key}={got!r}')
    before = snapshot(nodes)
    copies = []
    try:
        for n in nodes:
            copy = rt.copy(n)
            rt.setUserPropBuffer(copy, _delivery_props(rt.getUserPropBuffer(n)))
            copies.append(copy)
        rt.select(copies)
        if not rt.exportFile(str(path), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP):
            if path.exists():
                path.unlink()
            raise RuntimeError('FBX export failed')
    finally:
        if copies:
            rt.delete(copies)
    if snapshot(nodes) != before:
        raise RuntimeError('originals changed during export')


def export_commit(nodes, preview, target=None):
    """Write one FBX and the JSON report beside it. A stale preview writes nothing."""
    nodes = _targets(nodes)
    target = _export_target(nodes, target)
    scene = _export_scene(nodes)
    source = _max_source()
    core = _load_core('export_core.py', 'agr_tools_export')

    def writer(path, _plan):
        _write_max_fbx(nodes, path)

    try:
        report = core.commit(scene, target, source, preview, writer=writer)
    except (ModuleNotFoundError, ImportError):
        current = _subprocess_export({'method': 'dry_run', 'scene': scene, 'target': str(target), 'source': source})
        if current != preview:
            raise ValueError('stale preview')
        if current['status'] != 'pass':
            raise ValueError('gate failed: ' + str(current['plan']['stopped']))
        writer(target, current)
        report = _subprocess_export({'method': 'finish', 'preview': current, 'target': str(target),
                                    'report': current['plan']['report']})
    parse_report(json.dumps(report, allow_nan=False))
    return report


_preview = None
_preview_nodes = None
_nudge = None
_nudge_nodes = None
_atlas = None
_atlas_nodes = None
_ucx = None
_ucx_nodes = None
_export = None
_export_key = None


def ui(tool):
    """Macro seam: errors propagate and never print a successful report."""
    global _preview, _preview_nodes, _nudge, _nudge_nodes, _atlas, _atlas_nodes, _ucx, _ucx_nodes
    global _export, _export_key
    if tool == 'cleanup':
        _preview_nodes = _targets(None)
        _preview = cleanup_preview(_preview_nodes)
        report = _preview['report']
    elif tool == 'apply':
        if _preview is None:
            raise ValueError('dry-run required before apply')
        _, report = cleanup_apply(_preview_nodes, _preview)
        _preview = None
        _preview_nodes = None
    elif tool == 'nudge':
        _nudge_nodes = _targets(None)
        _nudge = nudge_preview(_nudge_nodes)
        report = _nudge['report']
    elif tool == 'nudge_apply':
        if _nudge is None:
            raise ValueError('dry-run required before apply')
        _, report = nudge_apply(_nudge_nodes, _nudge)
        _nudge = None
        _nudge_nodes = None
    elif tool == 'atlas':
        _atlas_nodes = _targets(None)
        _atlas = atlas_preview(_atlas_nodes)
        report = _atlas['report']
    elif tool == 'atlas_apply':
        if _atlas is None:
            raise ValueError('dry-run required before apply')
        _, report = atlas_apply(_atlas_nodes, _atlas)
        _atlas = None
        _atlas_nodes = None
    elif tool == 'ucx':
        _ucx_nodes = _targets(None)
        _ucx = ucx_preview(_ucx_nodes)
        report = _ucx['report']
    elif tool == 'ucx_apply':
        if _ucx is None:
            raise ValueError('dry-run required before apply')
        _, report = ucx_apply(_ucx_nodes, _ucx)
        _ucx = None
        _ucx_nodes = None
    elif tool == 'texel':
        report = texel_preview()['report']
    elif tool == 'export':
        nodes = _targets(None)
        key = tuple(int(_rt().getHandleByAnim(n)) for n in nodes)
        target = _export_target(nodes, None)
        if _export is None or _export_key != key:
            _export = export_preview(nodes, target)
            _export_key = key
            report = _export
        else:
            try:
                report = export_commit(nodes, _export, target)
            finally:
                _export = None
                _export_key = None
    elif tool in ('xview', 'matid'):
        report = {'xview': xview, 'matid': matid}[tool]()
    else:
        raise ValueError('unsupported tool: ' + str(tool))
    print(json.dumps(report, ensure_ascii=True, allow_nan=False))
    return report
