"""new-case: native AGR Tools button cores, no team implementation source.

Native xView uses 0.002 m vertices and 0.005 m faces.
"""
import json

VERSION = "0.1.0"
CODES = {'xview': {'overlap_vertices', 'overlap_faces'},
         'matid': {'udim_id', 'empty_id', 'empty_slot', 'missing_material'},
         'cleanup': {'remove_custom_attributes', 'clear_user_defined_lines',
                     'delete_map_channels', 'rename_map_channel_1'}}


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate key: ' + k)
        result[k] = v
    return result


def _reject(value):
    raise ValueError('non-finite JSON: ' + value)


def parse_report(text):
    """Strict complete report; derive status rather than trusting a claimed pass."""
    r = json.loads(text, object_pairs_hook=_unique, parse_constant=_reject)
    if not isinstance(r, dict) or set(r) != {'schema', 'tool', 'status', 'objects'}:
        raise ValueError('incomplete report')
    if type(r['schema']) is not int or r['schema'] != 1 or not isinstance(r['tool'], str) or r['tool'] not in CODES:
        raise ValueError('unsupported schema/tool')
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


def _report(tool, entries, nodes, select=True):
    report = {'schema': 1, 'tool': tool,
              'status': 'fail' if any(o['findings'] for o in entries) else 'pass', 'objects': entries}
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
        #(rv, rf)
    )''')
    previous = (rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance)
    entries = []
    try:
        for n in nodes:
            copy = _poly_copy(n)
            try:
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


_preview = None
_preview_nodes = None


def ui(tool):
    """Macro seam: errors propagate and never print a successful report."""
    global _preview, _preview_nodes
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
    elif tool in ('xview', 'matid'):
        report = {'xview': xview, 'matid': matid}[tool]()
    else:
        raise ValueError('unsupported tool: ' + str(tool))
    print(json.dumps(report, ensure_ascii=True, allow_nan=False))
    return report
