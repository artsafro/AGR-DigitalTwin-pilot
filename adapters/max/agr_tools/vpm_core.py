"""new-case: AGR Tools 1.0 (#1024) VPM build (steps K6, K3) logic, stdlib only; owned by branch M (improve/issue-1024-vpm-layout).

Pure logic for `vpm_build` (vpm.build, plan mode copy + file); no pymxs. The cores never take a host object.
Steps of #1024 §1.0.17 done here (the glue writes the copy and the files):
  1. UV: panels and brick (projected ids) - the K6 projection from the common grid zero with the perimeter
     unroll (uvlayout_core.project_k6); other ids keep their unwrap;
  2. texel: other ids are rescaled to the texel of their period around UV (0, 0) (udim.rescale rule, L09);
  3. layout into UDIM seam to seam: cut by the integer UV grid, whole shifts into the tile of the material (K6);
  4. renumbering library ids -> UDIM 1001.. without gaps PER MESH (K3; owner answer V9 06.11.2026: body and the
     windows/glass mesh each start at 1001), matlib_core.renumber_dense of branch L when it is implemented;
  5. glass: faces of the glass ids go to a separate object with its own numbering;
  9. check: seam metric (norm 0), texel per piece (+-1 %), 0 pieces across a tile line, UDIM 1001..N without gaps
     (udim.distortion rule on the pieces).
Steps 6-8 (maps D+ERM+N, tex.dilate, udim.plugs) belong to branches N; the glue calls vpmmaps_core.build_maps and
reports `skipped` while it is a stub.

Input mesh: {'key': handle, 'name', 'verts': [[x, y, z]] metres world double, 'tris', 'mat_ids',
'uvs': [[u, v]] | None, 'uv_tris': [[a, b, c]] | None}.
"""
import importlib.util
import math
import os

TOOL = 'vpm.build'
OPTION_KEYS = {'grid_zero_m', 'step_m', 'period_by_id', 'tile_px', 'texel_px_per_m', 'projected_ids', 'glass_ids',
               'unroll', 'out_dir'}
GLASS_SUFFIX = '_glass'


def _sibling(name, alias):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lay = _sibling('uvlayout_core.py', 'agr_tools_uvlayout_core_vpm')
u10 = _sibling('udim10_core.py', 'agr_tools_udim10_core_vpm')


def _num(v, name, positive=True):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (positive and v <= 0):
        raise ValueError('{} must be a {}number: {!r}'.format(name, 'positive ' if positive else '', v))
    return float(v)


def _ids(v, name):
    if v == 'all':
        return 'all'
    if not isinstance(v, list) or any(isinstance(i, bool) or not isinstance(i, int) or i <= 0 for i in v):
        raise ValueError('{} must be "all" or a list of positive library ids: {!r}'.format(name, v))
    return sorted(set(v))


def options(opts):
    """Validated options with the defaults of #1024 / owner answers 06.11.2026 (JSON-ready)."""
    opts = dict(opts or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown vpm.build options: ' + ', '.join(sorted(unknown)))
    zero = opts.get('grid_zero_m', [0.0, 0.0, 0.0])
    if not isinstance(zero, list) or len(zero) != 3:
        raise ValueError('options.grid_zero_m must be [x, y, z] metres')
    out = {'grid_zero_m': [_num(c, 'options.grid_zero_m', False) for c in zero],
           'step_m': _num(opts.get('step_m', lay.STEP_M), 'options.step_m'),
           'tile_px': opts.get('tile_px', lay.TILE_PX),
           'projected_ids': _ids(opts.get('projected_ids', 'all'), 'options.projected_ids'),
           'glass_ids': _ids(opts.get('glass_ids', []), 'options.glass_ids'),
           'unroll': opts.get('unroll', True), 'out_dir': opts.get('out_dir')}
    if out['glass_ids'] == 'all':
        raise ValueError('options.glass_ids must be a list')
    if type(out['tile_px']) is not int or out['tile_px'] <= 0:
        raise ValueError('options.tile_px must be a positive integer')
    if not isinstance(out['unroll'], bool):
        raise ValueError('options.unroll must be true or false')
    if out['out_dir'] is not None and (not isinstance(out['out_dir'], str) or not out['out_dir'].strip()):
        raise ValueError('options.out_dir must be a folder path')
    per = opts.get('period_by_id', {})
    if not isinstance(per, dict):
        raise ValueError('options.period_by_id must be {library id: metres}')
    out['period_by_id'] = {}
    for k, v in sorted(per.items()):
        if not str(k).isdigit() or int(k) <= 0:
            raise ValueError('options.period_by_id key must be a library id: {!r}'.format(k))
        out['period_by_id'][str(int(k))] = _num(v, 'options.period_by_id[{}]'.format(k))
    tx = opts.get('texel_px_per_m')
    # px/m is a parameter (owner question «1000 or 1024» open, GeoAGR-private research/materials-audit-1.0 Q1):
    # given, it fixes the pixels of one UDIM step; default tile_px / step_m (4096 / 3.6 = 1137.8 px/m).
    out['texel_px_per_m'] = _num(tx, 'options.texel_px_per_m') if tx is not None else None
    return out


def period_of(o, mid):
    return o['period_by_id'].get(str(mid), o['step_m'])


def texel_of(o, mid):
    """px/m of a material: the pixels of one UDIM over its period."""
    return px_per_step(o) / period_of(o, mid)


def px_per_step(o):
    return o['texel_px_per_m'] * o['step_m'] if o['texel_px_per_m'] else float(o['tile_px'])


def _corner_uv(mesh, f):
    return [list(mesh['uvs'][i][:2]) for i in mesh['uv_tris'][f]]


def _piece_texel(mesh, piece, px):
    """Texel extremes over the fan triangles of one piece (metres via the weights)."""
    a, b, c = (mesh['verts'][i] for i in mesh['tris'][piece['tri']])
    pts = [[w[0] * a[j] + w[1] * b[j] + w[2] * c[j] for j in range(3)] for w in piece['w']]
    out = []
    for i in range(1, len(pts) - 1):
        jac = u10.jacobian([pts[0], pts[i], pts[i + 1]], [piece['uv'][0], piece['uv'][i], piece['uv'][i + 1]])
        if jac is not None and jac[1] > 1e-15:
            out.append((math.sqrt(jac[0] * jac[1]) * px, jac[0] / jac[1], jac[2]))
    return out


def weld(mesh, pieces):
    """Output geometry of the pieces: vertices as weights over the SOURCE vertices (welded by their weights),
    fan triangles, welded UV vertices. Returns {'verts_w': [[[vid, w]...]], 'tris', 'uvs', 'uv_tris', 'mat_ids'}."""
    vkey, verts_w, ukey, uvs = {}, [], {}, []
    tris, uv_tris, mats, src = [], [], [], []
    for p in pieces:
        corners = mesh['tris'][p['tri']]
        vids, uids = [], []
        for w, uv in zip(p['w'], p['uv']):
            acc = {}
            for j in range(3):
                if abs(w[j]) > 1e-12:
                    acc[corners[j]] = acc.get(corners[j], 0.0) + w[j]
            key = tuple(sorted((vid, round(x, 9)) for vid, x in acc.items()))
            if key not in vkey:
                vkey[key] = len(verts_w)
                verts_w.append([[vid, x] for vid, x in sorted(acc.items())])
            v = vkey[key]
            k2 = (v, round(uv[0], 9), round(uv[1], 9))
            if k2 not in ukey:
                ukey[k2] = len(uvs)
                uvs.append([uv[0], uv[1]])
            vids.append(v)
            uids.append(ukey[k2])
        for i in range(1, len(vids) - 1):
            tri = [vids[0], vids[i], vids[i + 1]]
            if len(set(tri)) < 3:
                continue
            tris.append(tri)
            uv_tris.append([uids[0], uids[i], uids[i + 1]])
            mats.append(p['mat'])
            src.append(p['tri'])
    return {'verts_w': verts_w, 'tris': tris, 'uvs': uvs, 'uv_tris': uv_tris, 'mat_ids': mats, 'src_tri': src}


def build_part(mesh, faces, o, renumber, part):
    """Steps 1-4 and 9 for the faces of one output mesh. Returns (summary, geometry, findings)."""
    findings = []
    used = sorted({mesh['mat_ids'][f] for f in faces})
    table = renumber(used)
    # 'all' (default until branch L's library gives the recipes): every face, glass too, is projected (K6);
    # a list keeps the unwrap of the other ids (rescaled to their texel, step 2).
    projected = [f for f in faces if o['projected_ids'] == 'all' or mesh['mat_ids'][f] in o['projected_ids']]
    pset = set(projected)
    kept = [f for f in faces if f not in pset]
    uv = {}
    walls_info, wall_of, pairs = [], {}, set()
    if projected:
        proj, wall_of, walls_info, pairs = lay.project_k6(mesh, projected, o['grid_zero_m'], lambda m: period_of(o, m),
                                                   o['unroll'])
        uv.update(proj)
    rescaled = []
    if kept:
        if mesh.get('uvs') is None or mesh.get('uv_tris') is None:
            findings.append(('no_uv', kept, 'no UV channel 1 on faces that are not projected (ids {})'.format(
                sorted({mesh['mat_ids'][f] for f in kept}))))
            return None, None, findings
        for mid in sorted({mesh['mat_ids'][f] for f in kept}):
            mf = [f for f in kept if mesh['mat_ids'][f] == mid]
            try:
                before = u10.density(mesh, mf, px_per_step(o))
            except ValueError:
                findings.append(('no_uv', mf, 'ID {}: faces without UV area'.format(mid)))
                return None, None, findings
            sc = texel_of(o, mid) / before
            for f in mf:
                uv[f] = [[u * sc, v * sc] for u, v in _corner_uv(mesh, f)]  # around the common zero UV (0, 0)
            rescaled.append({'id': mid, 'faces': len(mf), 'before_px_per_m': round(before, 4),
                             'scale': round(sc, 9)})
    if kept:
        wall_of = {**wall_of, **lay.plane_regions(mesh, kept)}
    mats = {f: mesh['mat_ids'][f] for f in faces}
    pieces = lay.shift_into_tiles(lay.cut_grid(uv, mats), table)
    crossing = lay.crossing_pieces(pieces)
    if crossing:
        findings.append(('crossing', sorted({pieces[i]['tri'] for i in crossing}),
                         '{} pieces across a tile line'.format(len(crossing))))
    seam = lay.seam_metric(mesh, pieces, px_per_step(o), wall_of, pairs)
    # the norm 0 is for the K6 projection; a kept unwrap ("прочее — существующей развёрткой") is reported only
    kept_seam = [b for b in seam['bad'] if b['kind'] != 'fold' and not set(b['faces']) <= pset]
    bad_seam = [b for b in seam['bad'] if b['kind'] != 'fold' and set(b['faces']) <= pset]
    if bad_seam:
        findings.append(('seam', sorted({f for b in bad_seam for f in b['faces']}),
                         'seam up to {:.3f} px on internal/chain edges (norm 0)'.format(max(b['px'] for b in bad_seam))))
    texel, tex_bad = {}, set()
    for p in pieces:
        want = texel_of(o, p['mat'])
        for tx, _an, det in _piece_texel(mesh, p, px_per_step(o)):
            lo, hi = texel.get(p['mat'], (tx, tx))
            texel[p['mat']] = (min(lo, tx), max(hi, tx))
            if abs(tx / want - 1) > u10.SCALE_TOL:
                tex_bad.add(p['tri'])
    if tex_bad:
        findings.append(('texel', sorted(tex_bad), 'texel off by more than 1 %'))
    tiles = sorted({p['tile'] for p in pieces})
    want_tiles = list(range(lay.FIRST_UDIM, lay.FIRST_UDIM + len(table)))
    if tiles != want_tiles:
        findings.append(('udim_gap', [], 'tiles {} instead of {}'.format(tiles, want_tiles)))
    geo = weld(mesh, pieces)
    geo['plane_of_src'] = {str(f): list(v) if isinstance(v, tuple) else v for f, v in wall_of.items()}
    geo['chain_pairs'] = sorted(sorted(list(x) for x in pr) for pr in pairs)
    summary = {'part': part, 'faces_in': len(faces), 'pieces': len(pieces),
               'cut_faces': _cut_count(faces, pieces),
               'udim_table': {str(k): v for k, v in sorted(table.items())}, 'tiles': tiles,
               'projected_faces': len(projected), 'kept_uv_faces': len(kept), 'rescaled': rescaled,
               'walls': len(walls_info), 'seam_internal_max_px': seam['internal_max'],
               'seam_chain_max_px': seam['chain_max'], 'seam_fold_max_px': seam['fold_max'],
               'fold_edges': sum(1 for b in seam['bad'] if b['kind'] == 'fold'),
               'seam_kept_uv_max_px': max((b['px'] for b in kept_seam), default=0.0),
               'edges_compared': seam['edges'], 'crossing_pieces': len(crossing),
               'texel_px_per_m': {str(k): [round(v[0], 3), round(v[1], 3)] for k, v in sorted(texel.items())},
               'texel_target': {str(k): round(texel_of(o, k), 4) for k in used},
               'out_tris': len(geo['tris']), 'out_verts': len(geo['verts_w'])}
    return summary, geo, findings


def _cut_count(faces, pieces):
    n = {}
    for p in pieces:
        n[p['tri']] = n.get(p['tri'], 0) + 1
    return sum(1 for f in faces if n.get(f, 0) > 1)


def build(meshes, opts, renumber=None):
    """Plan of vpm.build over the meshes. Returns {'options', 'objects': [{'key', 'name', 'findings', 'parts':
    [{'name', 'summary', 'geometry'}]}]}; geometry is for the glue only (not in the report)."""
    o = options(opts)
    if not meshes:
        raise ValueError('nothing to build: select the OKS meshes')
    renumber = renumber or lay.renumber_dense
    out = []
    for m in meshes:
        lay._check_mesh({'verts': m['verts'], 'tris': m['tris'], 'mat_ids': m['mat_ids'], 'uv': None})
        findings = []
        bad_ids = sorted({i for i in m['mat_ids'] if i <= 0 or i >= 1001})
        if bad_ids:
            faces = [f + 1 for f, i in enumerate(m['mat_ids']) if i in bad_ids]
            findings.append(('id_range', faces, 'material ids {} are not library ids (>= 1001 on working geometry, '
                                                'K3)'.format(bad_ids[:10])))
            out.append({'key': m['key'], 'name': m['name'], 'findings': findings, 'parts': []})
            continue
        glass = set(o['glass_ids'])
        body_f = [f for f, i in enumerate(m['mat_ids']) if i not in glass]
        glass_f = [f for f, i in enumerate(m['mat_ids']) if i in glass]
        parts = []
        for part, faces, name in (('body', body_f, m['name']), ('glass', glass_f, m['name'] + GLASS_SUFFIX)):
            if not faces:
                continue
            summary, geo, f2 = build_part(m, faces, o, renumber, part)
            findings.extend((c, [f + 1 for f in ids], d) for c, ids, d in f2)
            if summary is not None:
                parts.append({'name': name, 'summary': dict(summary, object=name), 'geometry': geo})
        out.append({'key': m['key'], 'name': m['name'], 'findings': findings, 'parts': parts})
    return {'options': o, 'objects': out}


def table_json(plan, scene, version):
    """The sidecar of the file step: UDIM table per output mesh (K3; written into the passport by branch F)."""
    return {'schema': 1, 'tool': TOOL, 'issue': '#1024', 'scene': scene, 'core': version,
            'options': plan['options'],
            'meshes': [{'source': o['name'], 'object': p['name'], 'part': p['summary']['part'],
                        'udim_table': p['summary']['udim_table'], 'texel_target': p['summary']['texel_target']}
                       for o in plan['objects'] for p in o['parts']]}
