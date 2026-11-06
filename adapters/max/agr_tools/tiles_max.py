"""new-case: AGR Tools 1.0 (#1024) grey tile maps (K3), 3ds Max side. Stub of branch 0; owned by branch L (improve/issue-1024-materials).

runtime.edits_100 calls `mat_tiles(ctx, mode, nodes, preview)` for mat.tiles (plan mode `file`: new folder only).
ctx: agr (runtime globals), core (tiles_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost). Import pymxs inside functions so this file loads under plain pytest.

Which maps: per selected object its user prop `agr_tile` (JSON {base_map, overrides...}) or else the library records
(recipe greyscale_mask) of its face material IDs; without objects options.maps / options.records, default the whole
library. Options: library, out_dir, maps, records, px_per_m, period_m, write_normals (default true).
preview: checks every base map (module fit, seam, CIEDE2000 of the recoloured mean body for its records' RALs) and
lists the files apply would write. apply (unaltered preview): a NEW folder (never an existing one), mask/normal per
base map, D per record (recoloured mask; solid records a 256 px plug), ERM plug per record, PNG readback (raw sha256)
and `tiles_manifest.json`. Scene untouched.
"""
import json
import os
import tempfile

TILE_PROP = 'agr_tile'
GLOBAL = ('px_per_m', 'period_m')


def _rt():
    from pymxs import runtime
    return runtime


def _library(ctx):
    matlib = ctx.agr._load_core('matlib_core.py', 'agr_tools_matlib_core')
    p = ctx.options.get('library') or str(ctx.agr._repo_root() / 'library' / 'materials' / 'materials.json')
    return matlib.load_library(p)


def _face_ids(node):
    rt = _rt()
    try:
        if rt.superClassOf(node) != rt.GeometryClass or not rt.canConvertTo(node, rt.TriMeshGeometry):
            return None
        m = rt.snapshotAsMesh(node)
    except Exception:  # noqa: BLE001
        return None
    try:
        return sorted({int(rt.getFaceMatID(m, i)) for i in range(1, int(m.numfaces) + 1)})
    finally:
        rt.delete(m)


def _out_dir(ctx):
    if ctx.options.get('out_dir'):
        return os.path.abspath(str(ctx.options['out_dir']))
    rt = _rt()
    base = str(rt.maxFilePath) or tempfile.gettempdir()
    return ctx.edit.new_path(os.path.join(base, 'AGR_materials_maps'), version=True)


def _global_overrides(ctx):
    return {k: ctx.options[k] for k in GLOBAL if k in ctx.options}


def _targets(ctx, nodes, library):
    """[(owner or None, [(base_map, overrides, [record...])])], skipped."""
    core, edit = ctx.core, ctx.edit
    glob = _global_overrides(ctx)
    by_id = library['by_id']
    rt = _rt()
    out, skipped = [], []
    for n in nodes or ():
        if not rt.isValidNode(n):
            continue
        name = str(n.name)
        prop = rt.getUserProp(n, TILE_PROP)
        if prop is not None and str(prop).strip():
            try:
                spec = json.loads(str(prop))
                base = spec.pop('base_map')
            except Exception as exc:  # noqa: BLE001 - a broken prop is a finding, not a crash
                out.append(({'handle': int(ctx.emax.handle(n)), 'name': name}, [], 'bad agr_tile: {}'.format(exc)))
                continue
            recs = [r for r in library['materials'] if r['base_map'] == base]
            out.append(({'handle': int(ctx.emax.handle(n)), 'name': name}, [(base, dict(glob, **spec), recs)], None))
            continue
        ids = _face_ids(n)
        if ids is None:
            skipped.append(edit.skipped(name, 'not a mesh object'))
            continue
        recs = [by_id[i] for i in ids if i in by_id and by_id[i]['recipe']['kind'] == 'greyscale_mask']
        if not recs:
            skipped.append(edit.skipped(name, 'no greyscale_mask library ids on its faces'))
            continue
        groups = {}
        for r in recs:
            groups.setdefault(r['base_map'], []).append(r)
        out.append(({'handle': int(ctx.emax.handle(n)), 'name': name},
                    [(b, dict(glob), rs) for b, rs in sorted(groups.items())], None))
    if not nodes:
        maps = ctx.options.get('maps')
        rec_ids = ctx.options.get('records')
        recs = [by_id[i] for i in rec_ids] if rec_ids else [r for r in library['materials']
                                                              if r['recipe']['kind'] == 'greyscale_mask']
        names = list(maps) if maps else sorted({r['base_map'] for r in recs if r['base_map']})
        out.append((None, [(b, dict(glob), [r for r in recs if r['base_map'] == b]) for b in names], None))
        if rec_ids:  # solid records asked by id get their plugs too
            out.append((None, [(None, {}, [r for r in recs if r['recipe']['kind'] != 'greyscale_mask'])], None))
    return out, skipped


def _plan(ctx, nodes):
    core, edit = ctx.core, ctx.edit
    library = _library(ctx)
    targets, skipped = _targets(ctx, nodes, library)
    if not targets:
        raise ValueError('mat.tiles: empty input (select objects with tile library ids or give options.maps)')
    checked, entries, ambiguous, maps, files, records = {}, [], [], [], [], {}
    write_normals = bool(ctx.options.get('write_normals', True))
    for owner, groups, error in targets:
        found = []
        if error:
            found.append(edit.finding('bad_tile_prop', [], error))
        for base, over, recs in groups:
            for r in recs:
                records[r['library_id']] = r
            if base is None:
                continue
            key = edit.fingerprint([base, over])
            if key not in checked:
                rals = [{'code': r['ral'] or r['key'], 'rgb': r['rgb_srgb']} for r in recs]
                try:
                    s, _, result, fnd = core.check_base(base, over, rals)
                except ValueError as exc:
                    s, result, fnd = None, {'base_map': base, 'error': str(exc)}, [
                        {'code': 'bad_tile_spec', 'detail': str(exc)}]
                checked[key] = (base, over, s, result, fnd)
                maps.append(dict(result, overrides=over, findings=fnd, records=[r['library_id'] for r in recs]))
                if s is not None and not fnd:
                    tag = base if not over else '{}_{}'.format(base, key[:8])
                    files.append({'kind': 'mask', 'base_map': base, 'overrides': over, 'name': tag + '_mask.png'})
                    if write_normals:
                        files.append({'kind': 'normal', 'base_map': base, 'overrides': over,
                                      'name': tag + '_normal.png'})
                    for r in recs:
                        files.append({'kind': 'diffuse', 'base_map': base, 'overrides': over,
                                      'record': r['library_id'],
                                      'name': 'L{:03d}_{}_{}_D.png'.format(r['library_id'], r['key'], tag)})
            for f in checked[key][4]:
                found.append(edit.finding(f['code'], [], '{}: {}'.format(base, f['detail'])))
        if owner is not None:
            entries.append(edit.entry(owner['handle'], owner['name'], found))
        elif found:
            ambiguous.extend(sorted({'{}'.format(f['detail']) for f in found}))
    for lid, r in sorted(records.items()):
        files.append({'kind': 'erm', 'record': lid, 'name': 'L{:03d}_{}_ERM.png'.format(lid, r['key'])})
        if r['recipe']['kind'] != 'greyscale_mask':
            files.append({'kind': 'plug', 'record': lid, 'name': 'L{:03d}_{}_D.png'.format(lid, r['key'])})
    seen = set()
    files = [f for f in files if not (f['name'] in seen or seen.add(f['name']))]
    return library, entries, ambiguous, maps, files, skipped, records


def _state(ctx, library, out_dir, maps, files, nodes):
    rt = _rt()
    names = [[int(ctx.emax.handle(n)), str(n.name), str(rt.getUserProp(n, TILE_PROP) or '')]
             for n in (nodes or ()) if rt.isValidNode(n)]
    return {'library': library['sha256'], 'out_dir': out_dir, 'exists': os.path.exists(out_dir),
            'options': ctx.options, 'files': [f['name'] for f in files], 'nodes': names}


def _write(ctx, out_dir, files, library):
    core, edit = ctx.core, ctx.edit
    by_id = library['by_id']
    os.makedirs(out_dir, exist_ok=False)  # file mode: a NEW folder only
    greys, refs, written = {}, {}, []
    for f in files:
        rec = by_id.get(f.get('record'))
        if f['kind'] in ('mask', 'normal', 'diffuse'):
            key = edit.fingerprint([f['base_map'], f['overrides']])
            if key not in greys:
                s, _ = core.spec(f['base_map'], f['overrides'])
                greys[key] = core.Grey(s)
                refs[key] = core.grey_ref(core.body_histogram(greys[key]))
            grey = greys[key]
            w = h = grey.w
            if f['kind'] == 'mask':
                rows = core.mask_rows(grey)
            elif f['kind'] == 'normal':
                rows = core.normal_rows(grey)
            else:
                luts, joint = core.recolour_luts(rec['rgb_srgb'], refs[key])
                rows = core.colour_rows(grey, luts, joint)
        elif f['kind'] == 'erm':
            w = h = 256
            rows = core.solid_rows(w, h, core.erm_rgb(rec))
        else:
            w = h = 256
            rows = core.plug_rows(rec['rgb_srgb'])
        data, raw = core.png_stream(w, h, rows)
        path = edit.write_new(os.path.join(out_dir, f['name']), data)
        with open(path, 'rb') as fh:
            rw, rh, rsha = core.png_readback(fh.read())
        if (rw, rh, rsha) != (w, h, raw):
            raise RuntimeError('PNG readback differs: ' + f['name'])
        import hashlib
        written.append(dict(f, path=path, size=[w, h], raw_sha256=raw, sha256=hashlib.sha256(data).hexdigest()))
    return written


def mat_tiles(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode == 'apply':  # options belong to the preview (runtime refuses options with apply)
        ctx.options = dict(preview['plan'].get('options') or {})
    library, entries, ambiguous, maps, files, skipped, records = _plan(ctx, nodes)
    out_dir = ctx.options.get('out_dir') and os.path.abspath(str(ctx.options['out_dir'])) or None
    if mode == 'preview':
        out_dir = out_dir or _out_dir(ctx)
        state = _state(ctx, library, out_dir, maps, files, nodes)
        if state['exists']:
            ambiguous.append('out_dir exists: mat.tiles writes only a new folder ({})'.format(out_dir))
        return edit.report('mat.tiles', 'preview', objects=entries, done=[f['name'] for f in files],
                           skipped_=skipped, ambiguous=ambiguous, state_hash=edit.fingerprint(state),
                           extra={'out_dir': out_dir, 'maps': maps, 'files': files, 'options': dict(ctx.options),
                                  'library': {'version': library['version'], 'sha256': library['sha256']},
                                  'records': sorted(records)})
    plan = preview['plan']
    out_dir = plan['out_dir']
    edit.require_current(preview, _state(ctx, library, out_dir, maps, files, nodes))
    if plan['ambiguous'] or any(e['findings'] for e in preview['objects']):
        raise ValueError('mat.tiles: the preview has findings; nothing is written')
    written = _write(ctx, out_dir, plan['files'], library)
    manifest = {'schema': 1, 'kind': 'agr.tiles_manifest', 'library': plan['library'], 'maps': plan['maps'],
                'files': [{k: v for k, v in w.items() if k != 'path'} for w in written]}
    edit.write_new(os.path.join(out_dir, 'tiles_manifest.json'),
                   (json.dumps(manifest, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
    return edit.report('mat.tiles', 'apply', objects=entries, done=[w['name'] for w in written], skipped_=skipped,
                       extra={'out_dir': out_dir, 'maps': plan['maps'], 'written': len(written),
                              'manifest': os.path.join(out_dir, 'tiles_manifest.json')})
