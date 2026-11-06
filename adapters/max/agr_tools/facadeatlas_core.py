"""new-case: AGR Tools 1.0 (#1024) facade strip atlas logic, stdlib only; owned by branch P (improve/issue-1024-npm).

Pure logic for `atlas_facade_strip` (atlas.facade_strip, plan mode copy + file, station 1.0.23); no pymxs.
Port of the accepted run-strip method D156 (TOW02 OKS 013; pilot tools/remap_facades_atlas.py and
jobs/FACADES-ATLAS/, tag archive/2026-11) onto atlas_core (packing, NPM limits, 24 bit + separate opacity):
  * strip IDs (a repeating material with a period): every planar region is projected in its own plane (horizontal
    tangent, vertical up; a horizontal face takes its longest edge) from the common grid zero, in units of the
    period, and folded by a WHOLE number of periods into one strip per ID - the phase between neighbours is kept and
    nothing is stretched (pilot: `shift = floor(lo / period) * period`);
  * unique IDs (no period: a sign, a one-off panel): their own unwrap moves rigidly into a cell (atlas_core);
  * the strip texel is the target (default 39 px/m, one for every ID), padding >= 8 px of the same texture continued
    (pilot: 16 px, notes `docs/backlog.md:158`: own-colour padding < 8 px);
  * the pilot's fixed 2048 atlas and fixed band rectangles are replaced by the packing of atlas_core (smallest
    square 256..2048 that holds the strips); letters / labels in the atlas are off (Q05) and never drawn here.
Input mesh as npm_core plus 'faces' are triangles; options.period_by_id gives [pu, pv] metres per ID.
"""
import importlib.util
import math
import os

TOOL = 'atlas.facade_strip'
OPTION_KEYS = {'texel_px_per_m', 'max_size', 'pad', 'period_by_id', 'grid_zero_m', 'labels', 'out_dir', 'name'}
TEXEL_TOL = 0.01


def _sibling(name, alias):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


npm = _sibling('npm_core.py', 'agr_tools_npm_core_facade')
atlas = npm.atlas
files_of = npm.files_of


def options(opts):
    opts = dict(opts or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown atlas.facade_strip options: ' + ', '.join(sorted(unknown)))
    base = npm.options({k: opts[k] for k in ('texel_px_per_m', 'max_size', 'pad', 'out_dir', 'name') if k in opts})
    out = {k: base[k] for k in ('texel_px_per_m', 'max_size', 'pad', 'out_dir', 'name')}
    if opts.get('labels', False) is not False:
        raise ValueError('options.labels: letters in the facade atlas are off (Q05); not supported')
    out['labels'] = False
    zero = opts.get('grid_zero_m', [0.0, 0.0, 0.0])
    if not isinstance(zero, list) or len(zero) != 3 or any(
            isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) for c in zero):
        raise ValueError('options.grid_zero_m must be [x, y, z] metres')
    out['grid_zero_m'] = [float(c) for c in zero]
    per = opts.get('period_by_id', {})
    if not isinstance(per, dict) or not per:
        raise ValueError('options.period_by_id must name the strip ids: {library id: [pu, pv] metres}')
    out['period_by_id'] = {}
    for k, v in sorted(per.items(), key=lambda kv: str(kv[0])):
        if not str(k).isdigit() or int(k) <= 0:
            raise ValueError('options.period_by_id key must be a library id: {!r}'.format(k))
        pair = [v, v] if isinstance(v, (int, float)) and not isinstance(v, bool) else v
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError('options.period_by_id[{}] must be metres or [pu, pv]'.format(k))
        out['period_by_id'][str(int(k))] = [npm._num(c, 'options.period_by_id[{}]'.format(k)) for c in pair]
    return out


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return [c / n for c in a] if n > 1e-12 else None


def frame(pts):
    """(tangent, vertical, normal) of a planar polygon, canonical as the pilot: horizontal tangent with its largest
    component positive, vertical up; a horizontal face takes its longest edge."""
    nrm = [0.0, 0.0, 0.0]
    c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    for i in range(len(pts)):
        nrm = [nrm[k] + v for k, v in enumerate(_cross(_sub(pts[i], c), _sub(pts[(i + 1) % len(pts)], c)))]
    n = _unit(nrm)
    if n is None:
        return None
    if abs(n[2]) < 0.999:
        t = _unit(_cross([0.0, 0.0, 1.0], n))
        if t[max(range(3), key=lambda k: abs(t[k]))] < 0:
            t = [-x for x in t]
        v = _cross(n, t)
        if v[2] < 0:
            v = [-x for x in v]
    else:
        edges = [_sub(pts[(i + 1) % len(pts)], pts[i]) for i in range(len(pts))]
        t = _unit(max(edges, key=lambda e: _dot(e, e)))
        if t[max(range(3), key=lambda k: abs(t[k]))] < 0:
            t = [-x for x in t]
        v = _cross(n, t)
        if v[max(range(3), key=lambda k: abs(v[k]))] < 0:
            v = [-x for x in v]
    return t, v, n


def regions(mesh, faces):
    """Planar connected regions of one ID: union of triangles sharing an edge with the same plane (1e-6)."""
    parent = {f: f for f in faces}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    planes = {}
    for f in faces:
        fr = frame([mesh['verts'][i] for i in mesh['tris'][f]])
        planes[f] = None if fr is None else (fr[2], _dot(fr[2], mesh['verts'][mesh['tris'][f][0]]))
    edge = {}
    for f in faces:
        t = mesh['tris'][f]
        for e in range(3):
            k = tuple(sorted((t[e], t[(e + 1) % 3])))
            g = edge.setdefault(k, f)
            if g != f and planes[f] and planes[g] and all(
                    abs(a - b) < 1e-6 for a, b in zip(planes[f][0], planes[g][0])) and abs(
                    planes[f][1] - planes[g][1]) < 1e-6:
                parent[find(f)] = find(g)
    out = {}
    for f in faces:
        out.setdefault(find(f), []).append(f)
    return [sorted(v) for _k, v in sorted(out.items())]


def strip_uv(mesh, faces, zero, period):
    """{(face, corner): [u, v]} pattern UV of the folded regions of one strip ID and the per-region records."""
    uv, recs = {}, []
    for reg in regions(mesh, faces):
        vids = sorted({i for f in reg for i in mesh['tris'][f]})
        pts = [mesh['verts'][i] for i in vids]
        fr = frame([mesh['verts'][i] for i in mesh['tris'][reg[0]]])
        if fr is None:
            continue
        t, v, _n = fr
        local = {i: [_dot(_sub(mesh['verts'][i], zero), t) / period[0],
                     _dot(_sub(mesh['verts'][i], zero), v) / period[1]] for i in vids}
        lo = [min(p[0] for p in local.values()), min(p[1] for p in local.values())]
        shift = [math.floor(lo[0] + 1e-9), math.floor(lo[1] + 1e-9)]
        for i in vids:
            local[i] = [local[i][0] - shift[0], local[i][1] - shift[1]]
        for f in reg:
            for c, i in enumerate(mesh['tris'][f]):
                uv[(f, c)] = local[i]
        recs.append({'faces': len(reg), 'shift_periods': shift, 'tangent': [round(x, 9) for x in t],
                     'extent_periods': [round(max(p[0] for p in local.values()), 6),
                                        round(max(p[1] for p in local.values()), 6)], 'verts': len(pts)})
    return uv, recs


def plan(meshes, opts, maps):
    """Plan of atlas.facade_strip over the selected facade meshes (one atlas). Same shape as npm_core.plan plus
    'strips' (regions per strip ID)."""
    o = options(opts)
    if not meshes:
        raise ValueError('nothing to build: select the facade meshes')
    cm = npm.combine(meshes)
    findings, groups, strips = [], [], {}
    by_id = {}
    for f, mid in enumerate(cm['mat_ids']):
        by_id.setdefault(mid, []).append(f)
    mats = {}
    for m in meshes:
        for k, spec in (m.get('materials') or {}).items():
            mats[int(k)] = spec
    corner_uv = {}
    unique = {}
    for mid in sorted(by_id):
        faces = by_id[mid]
        spec = mats.get(mid) or {}
        per = o['period_by_id'].get(str(mid))
        kind = 'texture' if spec.get('map') else 'plug'
        g = {'key': str(mid), 'library_id': mid, 'kind': kind, 'part': 'body', 'material': spec.get('name'),
             'map': spec.get('map') if kind == 'texture' else None, 'color': list(spec.get('color') or [128] * 3),
             'faces': len(faces), 'udim': None, 'udim_source': None}
        if per is not None:
            uv, recs = strip_uv(cm, faces, o['grid_zero_m'], per)
            strips[str(mid)] = recs
            corner_uv.update(uv)
            g['uv_box'] = [0.0, 0.0, max(p[0] for p in uv.values()), max(p[1] for p in uv.values())]
            g['m_per_uv'] = list(per)
            g['mode'] = 'strip'
        else:
            if any(cm['uv_tris'][f] is None for f in faces):
                findings.append(('no_uv', faces, 'ID {}: no period and no UV channel 1'.format(mid)))
                continue
            uv_a = sum(npm._tri_area2(*[cm['uvs'][t] for t in cm['uv_tris'][f]]) for f in faces)
            geo_a = sum(npm._tri_area3(*[cm['verts'][i] for i in cm['tris'][f]]) for f in faces)
            if kind == 'texture' and (uv_a <= 1e-15 or geo_a <= 1e-12):
                findings.append(('no_uv', faces, 'ID {}: no UV area'.format(mid)))
                continue
            for f in faces:
                for c, t in enumerate(cm['uv_tris'][f]):
                    corner_uv[(f, c)] = list(cm['uvs'][t])
                    unique[(f, c)] = t
            pts = [corner_uv[(f, c)] for f in faces for c in range(3)]
            g['uv_box'] = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts),
                           max(p[1] for p in pts)]
            mpu = math.sqrt(geo_a / uv_a) if uv_a > 1e-15 else 1.0
            g['m_per_uv'] = [mpu, mpu]
            g['mode'] = 'unique'
        if kind == 'texture':
            info = maps.get(g['map']) or {'error': 'not read'}
            if info.get('error'):
                findings.append(('map_missing', faces, 'ID {}: map {} {} - no atlas is written'.format(
                    mid, g['map'], info['error'])))
                continue
            g['map_px'] = [info['w'], info['h']]
            g['source_texel_px_per_m'] = round(info['w'] / g['m_per_uv'][0], 4)
        groups.append(g)
    lay = None
    if not findings:
        try:
            lay = atlas.rigid_plan(groups, o['texel_px_per_m'], o['pad'], o['max_size'])
        except atlas.AtlasFitError as exc:
            findings.append(('atlas_overflow', [], '{}: {}'.format(exc, exc.calc)))
    out = {'options': o, 'findings': findings, 'groups': groups, 'atlas': lay, 'combined': cm, 'strips': strips,
           'pattern_uv': None, 'uvs': None, 'uv_tris': None, 'table': None, 'summary': None}
    if lay is None:
        return out
    new_uv, new_tris, key, pattern = [], [], {}, []
    for f in range(len(cm['tris'])):
        mid = cm['mat_ids'][f]
        cell = lay['cells'][str(mid)]
        ids, pat = [], []
        for c in range(3):
            src = corner_uv[(f, c)]
            k = (mid, 'u', unique[(f, c)]) if (f, c) in unique else (mid, 'v', cm['tris'][f][c], tuple(src))
            if k not in key:
                key[k] = len(new_uv)
                new_uv.append(list(atlas.to_atlas(cell, src)))
            ids.append(key[k])
            pat.append(src)
        new_tris.append(ids)
        pattern.append(pat)
    out.update(uvs=new_uv, uv_tris=new_tris, pattern_uv=pattern,
               table=atlas.correspondence_table({'size': lay['size'], 'texel': lay['texel'], 'cells': lay['cells'],
                                                 'groups': groups}))
    out['summary'] = {'atlas_px': lay['size'], 'fill': lay['fill'], 'texel_px_per_m': lay['texel'],
                      'pad_px': lay['pad'], 'faces': len(cm['tris']),
                      'strip_ids': sorted(int(k) for k in strips), 'unique_ids': sorted(
                          g['library_id'] for g in groups if g['mode'] == 'unique'),
                      'regions': {k: len(v) for k, v in sorted(strips.items())}, 'labels': False}
    return out


def measure(back, p):
    """Read-back of the copy: geometry and IDs unchanged, texel per texture ID = target +-1 %, every UV inside the
    cell of its ID, UV = rigid map of the planned pattern UV (<= 1e-5)."""
    cm, lay = p['combined'], p['atlas']
    size, target = lay['size'], lay['texel']
    if len(back['tris']) != len(cm['tris']) or back['mat_ids'] != cm['mat_ids']:
        raise RuntimeError('copy faces / material ids differ from the plan')
    kinds = {g['library_id']: g['kind'] for g in p['groups']}
    areas, rigid, outside = {}, 0.0, set()
    for f, mid in enumerate(back['mat_ids']):
        cell = lay['cells'][str(mid)]
        q = [back['uvs'][i] for i in back['uv_tris'][f]]
        for a, s in zip(q, p['pattern_uv'][f]):
            w = atlas.to_atlas(cell, s)
            rigid = max(rigid, abs(a[0] - w[0]), abs(a[1] - w[1]))
            u0, v0, u1, v1 = cell['region']
            e = 0.5 / size
            if kinds[mid] == 'texture' and not (u0 - e <= a[0] <= u1 + e and v0 - e <= a[1] <= v1 + e):
                outside.add(f)
        if kinds[mid] == 'texture':
            acc = areas.setdefault(mid, [0.0, 0.0])
            acc[0] += npm._tri_area2(*q) * size * size
            acc[1] += npm._tri_area3(*[back['verts'][i] for i in back['tris'][f]])
    texel = {m: math.sqrt(a / g) for m, (a, g) in areas.items() if g > 1e-12}
    findings = []
    bad = sorted(m for m, t in texel.items() if abs(t / target - 1) > TEXEL_TOL)
    if bad:
        findings.append(('texel', [f + 1 for f, m in enumerate(back['mat_ids']) if m in bad],
                         'texel {} off the target {}'.format({m: round(texel[m], 3) for m in bad}, target)))
    if rigid > 1e-5:
        findings.append(('rigid', [], 'UV differs from the planned strip UV by {:.2e}'.format(rigid)))
    if outside:
        findings.append(('cell', sorted(f + 1 for f in outside), 'UV outside the cell of its ID'))
    return findings, {'texel_px_per_m': {str(m): round(t, 4) for m, t in sorted(texel.items())},
                      'rigid_max_uv': rigid, 'outside_cell': len(outside)}


def table_json(p, scene, version, files):
    return {'schema': 1, 'tool': TOOL, 'issue': '#1024', 'scene': scene, 'core': version, 'options': p['options'],
            'method': 'D156 run-strip (pilot tools/remap_facades_atlas.py, tag archive/2026-11)',
            'atlas_px': p['atlas']['size'], 'texel_px_per_m': p['atlas']['texel'], 'files': files,
            'strips': p['strips'], 'table': p['table']}
