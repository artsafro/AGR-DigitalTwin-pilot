"""new-case: read-only pymxs glue for the AGR Tools 0.5.0 diagnostics (checks_core.py holds the logic).

Nothing here edits the scene: triangles and UVs come from snapshotAsMesh copies in memory, maps from
usedMaps, PNG headers from the files on disk. No copy/convert/ResetXForm/collapse (GeoAGR defect D6).
"""
import json
import os


def _rt():
    from pymxs import runtime
    return runtime


def _materials(mat):
    """The material and every sub-material, depth first, each once."""
    rt = _rt()
    out, stack, seen = [], [mat], set()
    while stack:
        m = stack.pop()
        if m is None or m == rt.undefined:
            continue
        key = int(rt.getHandleByAnim(m))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
        for i in range(int(rt.getNumSubMtls(m))):
            stack.append(rt.getSubMtl(m, i + 1))
    return out


def _used_maps(n):
    """All bitmap file names of the node's material. usedMaps returns an ARRAY; an empty array is
    "no maps" (GeoAGR defect D3 tested it against undefined, which is never true)."""
    rt = _rt()
    if n.material is None or n.material == rt.undefined:
        return []
    maps = rt.usedMaps(n.material)
    return [str(maps[i]) for i in range(int(maps.count))] if maps is not None else []


def _resolve(path):
    rt = _rt()
    if os.path.isfile(path):
        return path
    try:
        full = str(rt.mapPaths.getFullFilePath(path))
    except Exception:  # noqa: BLE001 - unresolved stays missing
        full = ''
    return full if full and os.path.isfile(full) else path


def _read(path):
    path = _resolve(path)
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        return f.read()


def _snapshot(n):
    rt = _rt()
    return rt.snapshotAsMesh(n)


def _free(mesh):
    try:
        _rt().delete(mesh)
    except Exception:  # noqa: BLE001 - a TriMesh value may already be collected
        pass


def _slots(n):
    """{matID: [map paths]} of a Multimaterial (materialIDList -> materialList[i] -> usedMaps), or None
    for a single material (every face uses all maps). An empty sub-material slot maps to [].
    A matID repeated in materialIDList maps to None (the core reports it as tex_unmeasurable)."""
    rt = _rt()
    m = n.material
    if m is None or m == rt.undefined or rt.classOf(m) != rt.Multimaterial:
        return None
    out, dup = {}, set()
    ids, subs = m.materialIDList, m.materialList
    for i in range(int(ids.count)):
        sub = subs[i]
        paths = []
        if sub is not None and sub != rt.undefined:
            maps = rt.usedMaps(sub)
            paths = [str(maps[j]) for j in range(int(maps.count))] if maps is not None else []
        mid = int(ids[i])
        out[mid] = None if mid in out else paths  # a repeated ID is ambiguous: None, never last-wins
        if out[mid] is None:
            dup.add(mid)
    for mid in dup:
        out[mid] = None
    return out


def _uv_faces(n):
    """(uvs, faces) of map channel 1 from an in-memory snapshot; faces are (snapshot triangle id,
    [uv indices], face matID) so the core can send each face to its sub-material's atlas."""
    rt = _rt()
    m = _snapshot(n)
    try:
        if not rt.meshop.getMapSupport(m, 1):
            return [], []
        uvs = []
        for i in range(int(rt.meshop.getNumMapVerts(m, 1))):
            p = rt.meshop.getMapVert(m, 1, i + 1)
            uvs.append((float(p.x), float(p.y)))
        faces = []
        for f in range(int(rt.meshop.getNumMapFaces(m, 1))):
            p = rt.meshop.getMapFace(m, 1, f + 1)
            faces.append((f + 1, [int(p.x) - 1, int(p.y) - 1, int(p.z) - 1], int(rt.getFaceMatID(m, f + 1))))
        return uvs, faces
    finally:
        _free(m)


def _rows(agr, nodes):
    return [{'node': n, 'key': int(_rt().getHandleByAnim(n)), 'name': str(n.name),
             'fbx': agr._prop(n, 'AGR_EXPORT_PATH')} for n in nodes]


def _fbx_table(core, rows, tri_table=None):
    if tri_table is not None:
        return tri_table
    out = {}
    for r in rows:
        kind = core.fbx_kind(r['fbx'])
        if kind is None:
            continue
        row = out.setdefault(r['fbx'], {'fbx': r['fbx'], 'model': kind[0], 'role': kind[1], 'objects': 0,
                                         'render_triangles': None, 'ucx_triangles': None, 'limit': None,
                                         'ucx_limit': None})
        row['objects'] += 1
    return [out[k] for k in sorted(out)]


def _finish(agr, core, tool, rows, found, dropped=(), tri_table=None):
    entries = []
    for r in rows:
        fs = []
        for item in found.get(r['key'], []):
            code, detail = item[0], item[1]
            ids = item[2] if len(item) > 2 else ()
            fs.append(agr._finding(code, ids, detail))
        entries.append(agr._entry(r['node'], fs))
    plan = {'fbx': _fbx_table(core, rows, tri_table), 'dropped': list(dropped)}
    return agr._report(tool, entries, [r['node'] for r in rows], extra={'plan': plan})


def names(agr, core, nodes):
    rows = _rows(agr, nodes)
    rt = _rt()
    for r in rows:
        r['materials'] = [str(m.name) for m in _materials(r['node'].material) if rt.classOf(m) != rt.Multimaterial]
        r['maps'] = _used_maps(r['node'])
    return _finish(agr, core, 'names', rows, core.names_scene(rows))


def triangles(agr, core, nodes):
    rows = _rows(agr, nodes)
    for r in rows:
        m = _snapshot(r['node'])
        try:
            r['triangles'] = int(m.numfaces)
        finally:
            _free(m)
        raw = agr._prop(r['node'], 'AGR_SITE_AREA_HA')
        try:
            r['site_area_ha'] = float(raw) if raw is not None else None
        except ValueError:
            r['site_area_ha'] = raw
    found, table = core.triangle_limits(rows)
    return _finish(agr, core, 'tris', rows, found, tri_table=table)


def textures(agr, core, nodes):
    rows = _rows(agr, nodes)
    for r in rows:
        paths = _used_maps(r['node'])
        r['slots'] = _slots(r['node'])
        for sub in (r['slots'] or {}).values():
            paths += [p for p in (sub or []) if p not in paths]
        r['maps'] = [(path, _read(path)) for path in paths]
        r['uv'] = (lambda node: lambda: _uv_faces(node))(r['node'])
    found, dropped = core.textures_scene(rows)
    return _finish(agr, core, 'textures', rows, found, dropped)


def pivot(agr, core, nodes):
    rows = _rows(agr, nodes)
    scale = agr._unit_m()
    for r in rows:
        p = r['node'].pivot
        r['pivot'] = (float(p.x) * scale, float(p.y) * scale, float(p.z) * scale)
    found, dropped = core.pivot_findings(rows)
    return _finish(agr, core, 'pivot', rows, found, dropped)


def geojson(agr, core, path=None):
    """Runs the pilot twinqa checker in the project interpreter; a broken file is a finding."""
    import subprocess
    rt = _rt()
    if path is None:
        chosen = rt.getOpenFileName(caption='GeoJSON check', types='GeoJSON (*.geojson)|*.geojson|All|*.*|')
        path = '' if chosen is None or chosen == rt.undefined else str(chosen)

    def runner(p):
        if not os.path.isfile(p):
            raise ValueError('file not found: ' + p)
        root = agr._repo_root()
        python = os.environ.get('AGR_PYTHON') or str(root / '.venv' / 'Scripts' / 'python.exe')
        if not os.path.isfile(python):
            raise ValueError('unmapped python ' + python)
        proc = subprocess.run([python, '-c', core.GEOJSON_CODE, str(root), p], capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode('utf-8', errors='replace')[-400:] or 'checker failed')
        return json.loads(proc.stdout.decode('utf-8'))

    return core.geojson_report(path, runner)


def run(agr, core, tool, nodes=None, path=None):
    if tool == 'geojson':
        return geojson(agr, core, path)
    nodes = agr._targets(nodes)
    fn = {'names': names, 'tris': triangles, 'textures': textures, 'pivot': pivot}[tool]
    return fn(agr, core, nodes)
