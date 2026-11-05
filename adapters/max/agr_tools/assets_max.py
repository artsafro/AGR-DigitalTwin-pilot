"""new-case: thin 3ds Max side of the AGR Tools `assets` module (#1024). All decisions live in assets_core.py.

* names of a library .max without loading it (getMAXFileObjectNames);
* merge from a verified COPY of the library .max in the cache (the Drive original is only read and hashed);
* layer ASSET_<lib>_<high|low>, user props agr_asset_*, material policy reuse/copy (#useSceneMtlDups /
  #renameMtlDups), texture repath by basename (copied into the project folder or pointing at the library);
* layout from the origin (assets_core.layout_rows), one undo record, journal line (K1), optional passport patch;
* readback of what is in the scene.
Metres through units.SystemScale (no decodeValue). Runs in Max 2024 (PySide2/Py3.10) and 2025+.
"""
import os
import shutil
import time
from pathlib import Path

import pymxs
from pymxs import runtime as rt


def _core():
    import importlib.util
    import sys
    name = 'agr_tools_assets_core'
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).with_name('assets_core.py')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _core()

UNIT_M = {'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344, 'millimeters': 0.001, 'centimeters': 0.01,
          'meters': 1.0, 'kilometers': 1000.0}


def m_per_unit():
    t = str(rt.units.SystemType).lstrip('#').lower()
    return UNIT_M[t] * float(rt.units.SystemScale)


def _handle(n):
    return int(rt.getHandleByAnim(n))


def _handles():
    return {_handle(o) for o in rt.objects}


def _new_nodes(before):
    return [o for o in rt.objects if _handle(o) not in before]


# ---- index ------------------------------------------------------------------------------------------------
def object_names(max_path):
    return [str(n) for n in rt.getMAXFileObjectNames(str(max_path), quiet=True)]


def scan_flora(root, cache_dir, lib='flora'):
    """Scan a Flora library folder and save the index. Reads .max object names only when the file changed."""
    old = core.load_index(cache_dir, lib)
    if core.flora_needs_names(root, old):
        lay = core.flora_layout(root)
        names = object_names(os.path.join(root, lay['max']))
    else:
        names = old['sources'][core.flora_layout(root)['max']]['objects']
    idx = core.scan_flora(root, names, lib=lib, old_index=old)
    core.save_index(cache_dir, idx)
    return idx


def source_copy(index, rec, cache_dir):
    """Verified copy of the library file in <cache>/sources/ (created once; never the original)."""
    src = os.path.join(index['root'], rec['source']['path'])
    sha = rec['source'].get('sha256') or core.sha256_file(src)
    dst = os.path.join(cache_dir, 'sources', sha[:12] + '_' + os.path.basename(src))
    if not os.path.isfile(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + '.tmp'
        shutil.copyfile(src, tmp)
        if core.sha256_file(tmp) != sha:
            os.remove(tmp)
            raise ValueError('library file changed while copying: ' + src)
        os.replace(tmp, dst)
    return dst, sha


# ---- scene state ------------------------------------------------------------------------------------------
def scene_assets():
    """{(asset id, version): [node names]} from user props."""
    out = {}
    for o in rt.objects:
        i = rt.getUserProp(o, core.PROP_ID)
        v = rt.getUserProp(o, core.PROP_VER)
        if i is not None and v is not None:
            out.setdefault((str(i), str(v)), []).append(str(o.name))
    return out


def _layer(name):
    lay = rt.LayerManager.getLayerFromName(name)
    return lay if lay is not None else rt.LayerManager.newLayerFromName(name)


def _bitmaps(mtl, out, seen, depth=0):
    if mtl is None or depth > 12:
        return
    h = _handle(mtl)
    if h in seen:
        return
    seen.add(h)
    if rt.classof(mtl) == rt.Bitmaptexture:
        out.append(mtl)
    for count, get in ((rt.getNumSubMtls, rt.getSubMtl), (rt.getNumSubTexmaps, rt.getSubTexmap)):
        try:
            n = int(count(mtl))
        except Exception:  # noqa: BLE001 - not every anim has sub-materials
            n = 0
        for i in range(1, n + 1):
            try:
                _bitmaps(get(mtl, i), out, seen, depth + 1)
            except Exception:  # noqa: BLE001
                pass


def node_bitmaps(nodes):
    maps, seen = [], set()
    for n in nodes:
        _bitmaps(n.material, maps, seen)
    return maps


def _box(nodes, k):
    lo = [1e30] * 3
    hi = [-1e30] * 3
    for n in nodes:
        bb = rt.nodeGetBoundingBox(n, rt.Matrix3(1))
        for i, c in enumerate('xyz'):
            lo[i] = min(lo[i], float(getattr(bb[0], c)) * k)
            hi[i] = max(hi[i], float(getattr(bb[1], c)) * k)
    p = nodes[0].pos
    return lo, hi, [float(p.x) * k, float(p.y) * k, float(p.z) * k]


# ---- import -----------------------------------------------------------------------------------------------
def run_import(index, ids, settings, cache_dir, scene_label=None, localappdata=None, passport=None,
               texture_dirs=()):
    """Import selected assets. Returns the report (also written to the journal). texture_dirs: extra folders
    searched after the library's own TextureFlora (e.g. when the library folder is a disposable mirror)."""
    t0 = time.perf_counter()
    s = core.merge_settings(settings)
    existing = scene_assets()
    plan = core.import_plan(index, ids, s['versions'], existing.keys())
    by_id = {r['id']: r for r in index['assets']}
    k = m_per_unit()
    report = {'plan': plan, 'plan_sha256': core.plan_hash(plan), 'imported': [], 'errors': [],
              'textures': {'repathed': 0, 'copied': 0, 'missing': [], 'conflicts': []}, 'moves': {}}
    merge_rows = [r for r in plan if r['status'] == 'merge']
    flag_mtl = rt.Name('useSceneMtlDups' if s['materials'] == 'reuse' else 'renameMtlDups')
    tex_dirs = []
    if index['adapter'] == 'flora_max':
        lay = index.get('layout') or core.flora_layout(index['root'])
        tex_dirs = [os.path.join(index['root'], d) for d in (lay.get('textures'), lay.get('viz_textures')) if d]
    tex_dirs += [d for d in texture_dirs if d]
    project_tex = None
    if s['textures'] == 'project' and s['project_dir']:
        project_tex = os.path.join(s['project_dir'], 'assets', index['lib'], 'textures')
    groups, new_by_id = [], {}
    with pymxs.undo(True, 'AGR assets import'):
        rt.disableSceneRedraw()
        try:
            asset_ids = []
            for r in merge_rows:
                if r['id'] not in asset_ids:
                    asset_ids.append(r['id'])
            for aid in asset_ids:
                rows = [r for r in merge_rows if r['id'] == aid]
                rec = by_id[aid]
                before = _handles()
                try:
                    src, sha = source_copy(index, rec, cache_dir)
                    names = [o for r in rows for o in r['objects']]
                    rt.mergeMAXFile(src, rt.Array(*names), rt.Name('autoRenameDups'), flag_mtl,
                                    rt.Name('neverReparent'), quiet=True)
                    nodes = _new_nodes(before)
                    if not nodes:
                        raise ValueError('nothing merged for ' + ', '.join(names))
                    boxes = {}
                    for r in rows:
                        vn = [n for n in nodes if core.version_of(n.name) == r['version']]
                        if not vn:
                            report['errors'].append('{} [{}]: object not merged'.format(aid, r['version']))
                            continue
                        layer = _layer(r['layer'])
                        for n in vn:
                            layer.addNode(n)
                            if s['materials'] == 'copy' and n.material is not None and \
                                    core.is_generic_material_name(str(n.material.name)):
                                n.material.name = core.copy_material_name(str(n.name), _material_names())
                            for key, val in r['props'].items():
                                rt.setUserProp(n, key, val or sha)
                        boxes[r['version']] = _box(vn, k)
                        report['imported'].append({'id': aid, 'version': r['version'],
                                                   'nodes': [str(n.name) for n in vn]})
                    new_by_id[aid] = nodes
                    groups.append({'id': aid, 'boxes': boxes})
                except Exception as exc:  # noqa: BLE001 - one asset must not stop the others
                    report['errors'].append('{}: {}: {}'.format(aid, type(exc).__name__, exc))
                    for n in _new_nodes(before):
                        rt.delete(n)
            # textures
            all_new = [n for ns in new_by_id.values() for n in ns]
            maps = node_bitmaps(all_new)
            tp = core.texture_plan([str(m.filename) for m in maps], tex_dirs, project_tex)
            for a, b in tp['copy']:
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copyfile(a, b)
            for m in maps:
                new = tp['map'].get(str(m.filename))
                if new and str(m.filename) != new:
                    m.filename = new
                    report['textures']['repathed'] += 1
            report['textures'].update(copied=len(tp['copy']), missing=tp['missing'], conflicts=tp['conflicts'])
            # layout
            moves = core.layout_rows(groups, s['gap_m'], s['row_limit_m'])
            for g in groups:
                for ver, (dx, dy, dz) in moves.get(g['id'], {}).items():
                    d = rt.Point3(dx / k, dy / k, dz / k)
                    for n in new_by_id[g['id']]:
                        if core.version_of(n.name) == ver:
                            n.pos = n.pos + d
            report['moves'] = {i: {v: list(m) for v, m in mv.items()} for i, mv in moves.items()}
        finally:
            rt.enableSceneRedraw()
    rt.freeSceneBitmaps()
    counts = {'merged': len(report['imported']),
              'skipped': sum(1 for r in plan if r['status'] != 'merge'), 'errors': len(report['errors'])}
    report['counts'] = counts
    report['duration_s'] = round(time.perf_counter() - t0, 3)
    status = 'done' if not report['errors'] else ('partial' if report['imported'] else 'failed')
    report['status'] = status
    line = core.journal_line('assets.import', 'apply', status, counts, report['plan_sha256'],
                             report['duration_s'], lib=index['lib'], ids=list(ids))
    if localappdata is None:
        localappdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    jpath = core.journal_path(scene_label if scene_label is not None else str(rt.maxFilePath + rt.maxFileName),
                              localappdata)
    core.append_journal(jpath, line)
    report['journal'] = jpath
    if passport and os.path.isfile(passport):
        import json
        with open(passport, encoding='utf-8') as f:
            p = json.load(f)
        rec = {'ts': line['ts'], 'lib': index['lib'], 'ids': list(ids), 'status': status, 'counts': counts,
               'plan_sha256': report['plan_sha256']}
        core.write_json_atomic(passport, core.passport_patch(p, rec))
        report['passport'] = passport
    return report


def _material_names():
    return {str(m.name) for m in rt.sceneMaterials}


def remove_imported(ids=None, lib=None):
    """Reliable rollback independent of undo: delete nodes carrying agr_asset_* props (all, one library, or the
    given asset ids). Returns the deleted node names."""
    gone = []
    for o in list(rt.objects):
        aid = rt.getUserProp(o, core.PROP_ID)
        if aid is None:
            continue
        if lib and str(rt.getUserProp(o, core.PROP_LIB)) != lib:
            continue
        if ids is not None and str(aid) not in ids:
            continue
        gone.append(str(o.name))
        rt.delete(o)
    return gone


def readback(lib=None):
    """Imported asset nodes as they are now: name, layer, props, material, bitmaps, transform, bbox (metres)."""
    k = m_per_unit()
    rows = []
    for o in rt.objects:
        aid = rt.getUserProp(o, core.PROP_ID)
        if aid is None or (lib and str(rt.getUserProp(o, core.PROP_LIB)) != lib):
            continue
        maps = node_bitmaps([o])
        lo, hi, piv = _box([o], k)
        rows.append({'name': str(o.name), 'layer': str(o.layer.name), 'id': str(aid),
                     'version': str(rt.getUserProp(o, core.PROP_VER)),
                     'sha256': str(rt.getUserProp(o, core.PROP_SHA)),
                     'material': None if o.material is None else str(o.material.name),
                     'material_handle': None if o.material is None else _handle(o.material),
                     'bitmaps': [{'file': str(m.filename), 'exists': os.path.isfile(str(m.filename))} for m in maps],
                     'scale': [float(o.scale.x), float(o.scale.y), float(o.scale.z)],
                     'pivot_m': piv, 'bbox_m': [lo, hi]})
    return rows
