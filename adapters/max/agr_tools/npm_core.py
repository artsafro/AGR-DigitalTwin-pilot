"""new-case: AGR Tools 1.0 (#1024) VPM -> NPM atlas logic, stdlib only; owned by branch P (improve/issue-1024-npm).

Pure logic for `npm_build` (npm.build, plan mode copy + file, station 1.0.22); no pymxs. The core never takes a host
object. Method of lab L11 (docs/experiments/npm.build.md, verdict `new`), built on atlas_core (rigid_plan,
rigid_raster, correspondence_table):
  * one texel for every texture ID: the target of the passport (default 39 px/m), +-1 %, the same in m and cm
    (GeoAGR Priority: texel by the root of the group area, x10 between IDs, cm ignored - GeoAGR.ms:27531-27536);
  * every library ID group of the VPM moves RIGIDLY (one uniform scale, one shift), so the K6 seam stays 0;
  * the cell is the full-resolution source map repeated over the real UV extent of the group (GeoAGR: 256 px render
    tiles :27440, empty / stretched islands over 1 UV :27096, fit_map_new :1152);
  * glass is a white cell and its faces join the NPM object (GeoAGR: diffuse colour, transparency lost :27665);
  * plugs are colours, no file path (GeoAGR: `Tile_C:\\...` :27638);
  * a missing or unreadable map, or a layout that does not fit, refuses the build: no atlas is written (GeoAGR: exit
    codes never checked, a black 128 px atlas);
  * the correspondence table (ID, source UDIM from the VPM table / passport, material, map, scale, shift, cell) is
    written next to the atlas and into the report for npm.to_vpm (branch Q).

Input mesh: {'key': handle, 'name', 'part': 'body'|'glass', 'verts': [[x, y, z]] world metres, 'tris', 'mat_ids',
'uvs': [[u, v]] | None, 'uv_tris': [[a, b, c]] | None, 'materials': {library id: {'name', 'map': path | None,
'color': [r, g, b] | None}}}. Maps: {path: {'w', 'h'} | {'error': text}} (headers for the plan; pixels at apply).
"""
import importlib.util
import math
import os

TOOL = 'npm.build'
OPTION_KEYS = {'texel_px_per_m', 'max_size', 'pad', 'glass_ids', 'udim_table', 'out_dir', 'name', 'layout'}
TEXEL_TOL = 0.01
# layout (owner question, #1024 is never blocked - a parameter): 'islands' (default) gives every UV island of an ID
# its own cell at the same scale (the texture is sampled at the island's real UV, so the K6 phase between islands is
# kept) and no two islands overlap - tex.check of an NPM fails overlapping islands (`tex_padding`, checks_core
# padding_findings: overlap is allowed only in the VPM, 2.5.1.5); 'stack' is the L11 prototype: one rigid cell per ID
# with the K6 pieces stacked as in the VPM tile (smaller atlas, tex.check reports the overlap).
LAYOUTS = ('islands', 'stack')


def _sibling(name, alias):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


atlas = _sibling('atlas_core.py', 'agr_tools_atlas_core_npm')
_udimtile = _sibling('udimtile_core.py', 'agr_tools_udimtile_core_npm')


def _num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError('{} must be a positive number: {!r}'.format(name, v))
    return float(v)


def options(opts):
    """Validated options with the defaults of #1024 §1.0.22 and lab L11 (JSON-ready)."""
    opts = dict(opts or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown npm.build options: ' + ', '.join(sorted(unknown)))
    out = {'texel_px_per_m': _num(opts.get('texel_px_per_m', atlas.NPM_TEXEL_PX_M), 'options.texel_px_per_m'),
           'max_size': opts.get('max_size', 2048), 'pad': opts.get('pad', atlas.PADDING_MIN_PX),
           'out_dir': opts.get('out_dir'), 'name': opts.get('name'), 'layout': opts.get('layout', 'islands')}
    if out['layout'] not in LAYOUTS:
        raise ValueError('options.layout must be one of {}'.format(list(LAYOUTS)))
    if out['max_size'] not in atlas.NPM_SIZES:
        raise ValueError('options.max_size must be one of {}'.format(list(atlas.NPM_SIZES)))
    if type(out['pad']) is not int or out['pad'] < atlas.PADDING_MIN_PX:
        raise ValueError('options.pad must be an integer >= {} px'.format(atlas.PADDING_MIN_PX))
    glass = opts.get('glass_ids', [])
    if not isinstance(glass, list) or any(type(i) is not int or i <= 0 for i in glass):
        raise ValueError('options.glass_ids must be a list of library ids')
    out['glass_ids'] = sorted(set(glass))
    table = opts.get('udim_table', {})
    if not isinstance(table, dict):
        raise ValueError('options.udim_table must be {library id: UDIM} (vpm_table.json / passport)')
    out['udim_table'] = {}
    for k, v in sorted(table.items(), key=lambda kv: str(kv[0])):
        if not str(k).isdigit() or type(v) is not int or not 1001 <= v <= 1100:
            raise ValueError('options.udim_table: {!r} -> {!r} is not library id -> UDIM 1001..1100'.format(k, v))
        out['udim_table'][str(int(k))] = v
    for key in ('out_dir', 'name'):
        if out[key] is not None and (not isinstance(out[key], str) or not out[key].strip()):
            raise ValueError('options.{} must be a non-empty string'.format(key))
    return out


def udim_table_of(vpm_table, objects):
    """{library id: UDIM} of the VPM objects from a vpm_table.json (vpm.build, branch M) - the passport source."""
    out = {}
    for row in vpm_table.get('meshes', []):
        if row.get('copy') in objects or row.get('object') in objects:
            for k, v in row['udim_table'].items():
                out[str(k)] = int(v)
    return out


def _tri_area3(a, b, c):
    e1 = [b[i] - a[i] for i in range(3)]
    e2 = [c[i] - a[i] for i in range(3)]
    n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
    return 0.5 * math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])


def _tri_area2(a, b, c):
    return 0.5 * abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))


def tile_of(u, v):
    return _udimtile.udim_tile(u, v)


def combine(meshes):
    """One NPM mesh from the meshes in order (body first): {'verts', 'tris', 'mat_ids', 'uvs', 'uv_tris', 'part',
    'src': [(mesh index, face)]}; the glue attaches the copies in the same order."""
    out = {'verts': [], 'tris': [], 'mat_ids': [], 'uvs': [], 'uv_tris': [], 'part': [], 'src': []}
    for mi, m in enumerate(meshes):
        vb, ub = len(out['verts']), len(out['uvs'])
        out['verts'].extend(m['verts'])
        if m.get('uvs') is not None:
            out['uvs'].extend(m['uvs'])
        for f, t in enumerate(m['tris']):
            out['tris'].append([i + vb for i in t])
            out['mat_ids'].append(m['mat_ids'][f])
            out['uv_tris'].append([i + ub for i in m['uv_tris'][f]] if m.get('uv_tris') is not None else None)
            out['part'].append(m.get('part', 'body'))
            out['src'].append((mi, f))
    return out

def uv_islands(cm, faces):
    """UV islands of the faces (connected through shared UV vertices), each sorted, in order of the first face."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for f in faces:
        t = cm['uv_tris'][f]
        for i in t[1:]:
            a, b = find(t[0]), find(i)
            if a != b:
                parent[a] = b
    out = {}
    for f in faces:
        out.setdefault(find(cm['uv_tris'][f][0]), []).append(f)
    return sorted(out.values(), key=lambda fs: fs[0])


def plan(meshes, opts, maps):
    """Plan of npm.build: {'options', 'findings': [(code, faces 0-based of the combined mesh, detail)], 'groups',
    'atlas' (rigid_plan), 'uvs', 'uv_tris', 'table', 'summary'}. Findings make the build fail closed."""
    o = options(opts)
    if not meshes:
        raise ValueError('nothing to build: select the VPM objects (body and glass)')
    cm = combine(meshes)
    findings = []
    glass_ids = set(o['glass_ids']) | {i for m in meshes if m.get('part') == 'glass' for i in m['mat_ids']}
    noid = [f for f, i in enumerate(cm['mat_ids']) if i <= 0]
    if noid:
        findings.append(('id_range', noid, 'material id <= 0'))
    nouv = [f for f, t in enumerate(cm['uv_tris']) if t is None]
    if nouv:
        findings.append(('no_uv', nouv, 'no UV channel 1 (run vpm.build first)'))
    by_id = {}
    for f, mid in enumerate(cm['mat_ids']):
        by_id.setdefault(mid, []).append(f)
    mats = {}
    for m in meshes:
        for k, spec in (m.get('materials') or {}).items():
            k = int(k)
            if k in mats and mats[k] != spec:
                findings.append(('id_conflict', by_id.get(k, []),
                                 'library id {} has two materials in the selection'.format(k)))
            mats[k] = spec
    parts = {}
    for f, mid in enumerate(cm['mat_ids']):
        parts.setdefault(mid, set()).add(cm['part'][f])
    groups, face_key = [], [None] * len(cm['tris'])
    for mid in sorted(by_id):
        faces = by_id[mid]
        if mid <= 0 or any(cm['uv_tris'][f] is None for f in faces):
            continue
        if len(parts[mid]) > 1:
            findings.append(('id_conflict', faces, 'library id {} on body and glass'.format(mid)))
        spec = mats.get(mid) or {}
        kind = 'glass' if mid in glass_ids else ('texture' if spec.get('map') else 'plug')
        uv_a = geo_a = 0.0
        tile_area = {}
        for f in faces:
            p = [cm['verts'][i] for i in cm['tris'][f]]
            q = [cm['uvs'][t] for t in cm['uv_tris'][f]]
            a2, a3 = _tri_area2(*q), _tri_area3(*p)
            uv_a += a2
            geo_a += a3
            c = tile_of(sum(x[0] for x in q) / 3.0, sum(x[1] for x in q) / 3.0)
            tile_area[c] = tile_area.get(c, 0.0) + a3
        base = {'library_id': mid, 'kind': kind, 'part': sorted(parts[mid])[0], 'material': spec.get('name'),
                'map': spec.get('map') if kind == 'texture' else None,
                'color': list(spec.get('color') or [128, 128, 128])}
        if str(mid) in o['udim_table']:
            base['udim'], base['udim_source'] = o['udim_table'][str(mid)], 'vpm_table'
        else:
            base['udim'] = max(tile_area.items(), key=lambda kv: (kv[1], -kv[0]))[0] if tile_area else None
            base['udim_source'] = 'uv_area_majority'
        if kind == 'texture':
            if uv_a <= 1e-15 or geo_a <= 1e-12:
                findings.append(('no_uv', faces, 'ID {}: no UV or geometry area, texel not measurable'.format(mid)))
                continue
            mpu = math.sqrt(geo_a / uv_a)  # metres per UV unit (K6: isotropic), one scale for the whole ID
            base['m_per_uv'] = [mpu, mpu]
            info = maps.get(base['map']) or {'error': 'not read'}
            if info.get('error'):
                findings.append(('map_missing', faces, 'ID {}: map {} {} - no atlas is written'.format(
                    mid, base['map'], info['error'])))
                continue
            base['map_px'] = [info['w'], info['h']]
            base['source_texel_px_per_m'] = round(info['w'] / mpu, 4)
        parts_of = [faces] if o['layout'] == 'stack' else uv_islands(cm, faces)
        for k, fs in enumerate(parts_of, 1):
            idx = sorted({t for f in fs for t in cm['uv_tris'][f]})
            us = [cm['uvs'][t][0] for t in idx]
            vs = [cm['uvs'][t][1] for t in idx]
            key = str(mid) if o['layout'] == 'stack' else '{}.{}'.format(mid, k)
            groups.append(dict(base, key=key, island=None if o['layout'] == 'stack' else k, faces=len(fs),
                               uv_box=[min(us), min(vs), max(us), max(vs)]))
            for f in fs:
                face_key[f] = key
    lay = None
    if not findings:
        try:
            lay = atlas.rigid_plan(groups, o['texel_px_per_m'], o['pad'], o['max_size'])
        except atlas.AtlasFitError as exc:
            findings.append(('atlas_overflow', [], '{}: {}'.format(exc, exc.calc)))
        except atlas.AtlasError as exc:
            findings.append(('atlas', [], str(exc)))
    out = {'options': o, 'findings': findings, 'groups': groups, 'atlas': lay, 'combined': cm, 'face_key': face_key}
    if lay is None:
        out.update(uvs=None, uv_tris=None, table=None, summary=None)
        return out
    new_uv, new_tris, key = [], [], {}
    for f, t in enumerate(cm['uv_tris']):
        cell = lay['cells'][face_key[f]]
        ids = []
        for i in t:
            k = (cm['mat_ids'][f], i)
            if k not in key:
                key[k] = len(new_uv)
                new_uv.append(list(atlas.to_atlas(cell, cm['uvs'][i])))
            ids.append(key[k])
        new_tris.append(ids)
    report = {'size': lay['size'], 'texel': lay['texel'], 'cells': lay['cells'], 'groups': groups}
    out.update(uvs=new_uv, uv_tris=new_tris, table=atlas.correspondence_table(report))
    out['summary'] = {
        'atlas_px': lay['size'], 'fill': lay['fill'], 'texel_px_per_m': lay['texel'], 'pad_px': lay['pad'],
        'faces': len(cm['tris']), 'layout': o['layout'], 'cells': len(groups),
        'kinds': {k: len({g['library_id'] for g in groups if g['kind'] == k}) for k in atlas.KINDS},
        'glass_faces': sum(1 for mid in cm['mat_ids'] if mid in glass_ids)}
    return out


def measure(back, p):
    """Read-back of the NPM copy (combined order): texel per texture group (+-1 % of the target), rigid transfer
    (atlas UV = scale * VPM UV + shift, <= 1e-5) and every UV inside its cell. Returns (findings, measured)."""
    cm, lay = p['combined'], p['atlas']
    size, target = lay['size'], lay['texel']
    if len(back['tris']) != len(cm['tris']) or back['mat_ids'] != cm['mat_ids']:
        diff = [f + 1 for f, (a, b) in enumerate(zip(back['mat_ids'], cm['mat_ids'])) if a != b][:10]
        raise RuntimeError('NPM copy faces / material ids differ from the plan (attach order): {} vs {} faces, '
                           'first differing faces {}'.format(len(back['tris']), len(cm['tris']), diff))
    findings, texel, rigid, outside = [], {}, 0.0, []
    kinds = {g['library_id']: g['kind'] for g in p['groups']}
    areas = {}
    for f, mid in enumerate(back['mat_ids']):
        cell = lay['cells'][p['face_key'][f]]
        q = [back['uvs'][i] for i in back['uv_tris'][f]]
        src = [cm['uvs'][i] for i in cm['uv_tris'][f]]
        for a, s in zip(q, src):
            want = atlas.to_atlas(cell, s)
            rigid = max(rigid, abs(a[0] - want[0]), abs(a[1] - want[1]))
            u0, v0, u1, v1 = cell['region']
            pad = 0.5 / size
            if not (u0 - pad <= a[0] <= u1 + pad and v0 - pad <= a[1] <= v1 + pad) and kinds[mid] == 'texture':
                outside.append(f)
        if kinds[mid] == 'texture':
            pa = [back['verts'][i] for i in back['tris'][f]]
            acc = areas.setdefault(mid, [0.0, 0.0])
            acc[0] += _tri_area2(*q) * size * size
            acc[1] += _tri_area3(*pa)
    for mid, (ua, ga) in sorted(areas.items()):
        if ga > 1e-12:
            texel[mid] = math.sqrt(ua / ga)
    bad = [mid for mid, t in texel.items() if abs(t / target - 1) > TEXEL_TOL]
    if bad:
        findings.append(('texel', [f + 1 for f, m in enumerate(back['mat_ids']) if m in bad],
                         'texel {} px/m off the target {} by more than 1 %'.format(
                             {m: round(texel[m], 3) for m in bad}, target)))
    if rigid > 1e-5:
        findings.append(('rigid', [], 'atlas UV differs from scale * UV + shift by {:.2e}'.format(rigid)))
    if outside:
        findings.append(('cell', sorted({f + 1 for f in outside}), 'UV outside the cell of its ID'))
    return findings, {'texel_px_per_m': {str(m): round(t, 4) for m, t in sorted(texel.items())},
                      'rigid_max_uv': rigid, 'outside_cell': len(set(outside))}


def files_of(name, size, has_alpha):
    """File names of the NPM atlas by names_core when `name` is an NPM SM name, else T_<name>_d_1.png."""
    try:
        nc = _sibling('names_core.py', 'agr_tools_names_core_npm')
        obj = nc.parse_object(name, 'npm')
        if isinstance(obj, dict):
            d = nc.texture_stem(obj, 'npm', 'diffuse', 1) + '.png'
            o = nc.texture_stem(obj, 'npm', 'opacity', 1) + '.png' if has_alpha else None
            return d, o, nc.material_name(obj, 1)
    except (ValueError, KeyError, ImportError):
        pass
    return 'T_{}_d_1.png'.format(name), ('T_{}_o_1.png'.format(name) if has_alpha else None), 'M_{}_1'.format(name)


def table_json(p, scene, version, files):
    """Sidecar `npm_table.json` (correspondence table; the passport write belongs to branch F)."""
    return {'schema': 1, 'tool': TOOL, 'issue': '#1024', 'scene': scene, 'core': version, 'options': p['options'],
            'atlas_px': p['atlas']['size'], 'texel_px_per_m': p['atlas']['texel'], 'files': files,
            'rule': 'atlas_uv = scale * vpm_uv + shift; vpm_uv = (atlas_uv - shift) / scale', 'table': p['table']}
