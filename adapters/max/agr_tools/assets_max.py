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


def scan_flora(root, cache_dir, lib='flora', extra_preview_dirs=()):
    """Scan a Flora library folder and save the index. Reads .max object names only when the file changed."""
    old = core.load_index(cache_dir, lib)
    if core.flora_needs_names(root, old):
        lay = core.flora_layout(root)
        names = object_names(os.path.join(root, lay['max']))
    else:
        names = old['sources'][core.flora_layout(root)['max']]['objects']
    idx = core.scan_flora(root, names, lib=lib, old_index=old, extra_preview_dirs=extra_preview_dirs)
    core.save_index(cache_dir, idx)
    return idx


def source_copy(index, rec, cache_dir):
    """Verified copy of the library file in <cache>/sources/ (created once; never the original)."""
    src = os.path.join(index['root'], rec['source']['path'])
    sha = rec['source'].get('sha256') or core.sha256_file(src)
    dst = os.path.join(cache_dir, 'sources', sha[:12] + '_' + os.path.basename(src))
    if core.same_file(src, dst):
        raise ValueError('cache aliases library input: ' + dst)
    if os.path.isfile(dst):
        if core.sha256_file(dst) != sha:
            raise ValueError('cache content differs from recorded source: ' + dst)
    else:
        import tempfile
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.agr-source-', dir=os.path.dirname(dst))
        try:
            with os.fdopen(fd, 'wb') as target, open(src, 'rb') as source:
                shutil.copyfileobj(source, target)
            if core.sha256_file(tmp) != sha:
                raise ValueError('library file changed while copying: ' + src)
            os.link(tmp, dst)
        finally:
            os.unlink(tmp)
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


def _bring(index, rec, rows, s, cache_dir, flag_mtl, report):
    """Bring one asset's versions into the scene. Returns ({version: [nodes]}, source sha256, texture dirs).

    flora_max: merge from the verified copy of the library .max.
    maf_zip:   extract the archive members into <project>/assets/<lib>/<name>/ (the zip on the Drive is only read),
               then merge from the extracted <name>.max, or import <name>_<ver>.fbx (source fbx, or no .max)."""
    names = [o for r in rows for o in r['objects']]
    if index['adapter'] == 'flora_max':
        src, sha = source_copy(index, rec, cache_dir)
        return _merge(src, names, flag_mtl), sha, []
    zpath = os.path.join(index['root'], rec['source']['path'])
    sha = rec['source'].get('sha256') or core.sha256_file(zpath)
    rec['source']['sha256'] = sha
    for r in rows:
        r['props'][core.PROP_SHA] = sha
    dest = os.path.join(s['project_dir'] or os.path.join(cache_dir, 'extract'), 'assets', index['lib'], rec['name'])
    has_max = any(v.get('max') for v in rec['versions'].values())
    use_fbx = s['source'] == 'fbx' or not has_max
    vers = [r['version'] for r in rows]
    keep = core.maf_member_filter(rec['name'], use_fbx, vers)
    files = core.extract_members(zpath, dest, keep)
    report.setdefault('extracted', {})[rec['id']] = {'dir': dest, 'files': len(files), 'route': 'fbx' if use_fbx
                                                     else 'max'}
    if not use_fbx:
        src = files.get((rec['name'] + '.max').lower())
        if not src:
            raise ValueError('no .max extracted from ' + zpath)
        return _merge(src, names, flag_mtl), sha, [dest]
    by_ver = {}
    for v in vers:
        f = files.get((rec['name'] + '_' + v + '.fbx').lower())
        if not f:
            report['errors'].append('{} [{}]: no fbx in the archive'.format(rec['id'], v))
            continue
        by_ver[v] = _import_fbx(f, float(s['fbx_scale']))
    return by_ver, sha, [dest]


def _merge(src, names, flag_mtl):
    before = _handles()
    rt.mergeMAXFile(src, rt.Array(*names), rt.Name('autoRenameDups'), flag_mtl, rt.Name('neverReparent'), quiet=True)
    by_ver = {}
    for n in _new_nodes(before):
        by_ver.setdefault(core.version_of(n.name) or 'high', []).append(n)
    return by_ver


FBX_UNIT = {'millimeters': 'mm', 'centimeters': 'cm', 'meters': 'm', 'kilometers': 'km', 'inches': 'in',
            'feet': 'ft', 'miles': 'mi'}


def _import_fbx(path, scale=1.0):
    """FBX into the scene: convert to the scene's system unit (Scale Factor 1), Z up, no cameras/lights/animation;
    scale is an extra multiplier about the origin (pivots of the A101 assets are at the origin)."""
    rt.pluginManager.loadClass(rt.FbxImporter)
    unit = FBX_UNIT.get(str(rt.units.SystemType).lstrip('#').lower(), 'm')
    for key, val in (('Mode', rt.Name('create')), ('Animation', False), ('Cameras', False), ('Lights', False),
                     ('ConvertUnit', rt.Name(unit)), ('ScaleConversion', True), ('UpAxis', rt.Name('Z')),
                     ('GenerateLog', False)):
        rt.FBXImporterSetParam(rt.Name(key), val)
    before = _handles()
    rt.importFile(path, rt.Name('noPrompt'), using=rt.FbxImporter)
    nodes = [n for n in _new_nodes(before) if rt.superclassof(n) == rt.GeometryClass]
    extra = [n for n in _new_nodes(before) if rt.superclassof(n) != rt.GeometryClass]
    for n in extra:
        rt.delete(n)
    if abs(scale - 1.0) > 1e-9:
        for n in nodes:
            rt.scale(n, rt.Point3(scale, scale, scale))
            n.pos = n.pos * scale
    return nodes


# ---- import -----------------------------------------------------------------------------------------------
def run_import(index, ids, settings, cache_dir, scene_label=None, localappdata=None, passport=None,
               texture_dirs=()):
    """Import selected assets. Returns the report (also written to the journal). texture_dirs: extra folders
    searched after the library's own TextureFlora (e.g. when the library folder is a disposable mirror)."""
    t0 = time.perf_counter()
    s = core.merge_settings(settings)
    existing = scene_assets()
    plan = core.import_plan(index, ids, s['versions'], existing.keys())
    if index['adapter'] == 'maf_zip':  # decision 07.11: packing errors block the import unless allow_flagged
        alib = _sibling('assets_library')
        audit_index = index
        mpath = s.get('maf_measured') or str(Path(__file__).resolve().parents[3] / 'library/assets/maf_measured.json')
        if os.path.isfile(mpath):  # archives without a sidecar are judged by their Max measurement
            import json
            with open(mpath, encoding='utf-8') as f:
                audit_index, _unknown = alib.attach_measured(index, json.load(f)['measured'])
        plan = core.gate_plan(plan, alib.audit_maf(audit_index)['rows'], s['allow_flagged'])
    by_id = {r['id']: r for r in index['assets']}
    k = m_per_unit()
    report = {'plan': plan, 'plan_sha256': core.plan_hash(plan), 'imported': [], 'errors': [],
              'textures': {'repathed': 0, 'copied': 0, 'missing': [], 'conflicts': []}, 'moves': {}}
    for row in plan:
        if row['status'] not in ('merge', 'already_in_scene'):
            report['errors'].append('{}: {}'.format(row['id'], row['status']))
    merge_rows = [r for r in plan if r['status'] == 'merge']
    flag_mtl = rt.Name('useSceneMtlDups' if s['materials'] == 'reuse' else 'renameMtlDups')
    tex_dirs = []
    if index['adapter'] == 'flora_max':
        lay = index.get('layout') or core.flora_layout(index['root'])
        tex_dirs = [os.path.join(index['root'], d) for d in (lay.get('textures'), lay.get('viz_textures')) if d]
    tex_dirs += [d for d in texture_dirs if d]
    project_tex = None
    if s['textures'] == 'project' and s['project_dir'] and index['adapter'] == 'flora_max':
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
                    by_ver, sha, extra_tex = _bring(index, rec, rows, s, cache_dir, flag_mtl, report)
                    tex_dirs += [d for d in extra_tex if d not in tex_dirs]
                    nodes = [n for ns in by_ver.values() for n in ns]
                    if not nodes:
                        raise ValueError('nothing merged for ' + ', '.join(o for r in rows for o in r['objects']))
                    boxes = {}
                    for r in rows:
                        vn = by_ver.get(r['version'], [])
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
                    groups.append({'id': aid, 'boxes': boxes, 'nodes': by_ver})
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
            report['errors'].extend('missing texture: ' + p for p in tp['missing'])
            report['errors'].extend('texture conflict: ' + p for p in tp['conflicts'])
            # layout
            moves = core.layout_rows([{'id': g['id'], 'boxes': g['boxes']} for g in groups], s['gap_m'],
                                     s['row_limit_m'])
            for g in groups:
                for ver, (dx, dy, dz) in moves.get(g['id'], {}).items():
                    d = rt.Point3(dx / k, dy / k, dz / k)
                    for n in g['nodes'][ver]:
                        n.pos = n.pos + d
            report['moves'] = {i: {v: list(m) for v, m in mv.items()} for i, mv in moves.items()}
        finally:
            rt.enableSceneRedraw()
    rt.freeSceneBitmaps()
    counts = {'merged': len(report['imported']),
              'skipped': sum(1 for r in plan if r['status'] != 'merge'), 'errors': len(report['errors']),
              'blocked_by_audit': sum(1 for r in plan if r['status'] == 'blocked_by_audit')}
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


# ---- VPM UDIM tiles of placed assets (assets_textures) ------------------------------------------------------
def _sibling(name):
    import importlib.util
    import sys
    key = 'agr_tools_' + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, Path(__file__).with_name(name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


def png_size(path):
    import struct
    try:
        with open(path, 'rb') as f:
            head = f.read(24)
    except OSError:
        return None
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return list(struct.unpack('>II', head[16:24]))


def write_flat_png(path, rgb, size=256):
    """Flat 8-bit RGB PNG (colour type 2), exclusive create (never overwrites)."""
    import struct
    import zlib

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    row = b'\x00' + bytes(rgb) * size
    data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(row * size, 9)) + chunk(b'IEND', b''))
    with open(path, 'xb') as f:
        f.write(data)


def _uv_stats(node, k):
    mesh = rt.snapshotAsMesh(node)
    if not rt.meshop.getMapSupport(mesh, 1):
        return None, 0.0
    n = int(rt.meshop.getNumMapVerts(mesh, 1))
    us, vs = [], []
    for i in range(1, n + 1):
        p = rt.meshop.getMapVert(mesh, 1, i)
        us.append(float(p.x))
        vs.append(float(p.y))
    area = sum(float(rt.meshop.getFaceArea(mesh, f)) for f in range(1, int(mesh.numfaces) + 1)) * k * k
    return [[min(us), min(vs)], [max(us), max(vs)]], area


def _shift_uv(node, du, dv):
    """Move channel 1 by a whole tile on the node's base object (instances follow)."""
    cls = str(rt.classof(node.baseObject))
    if cls == 'Editable_Poly':
        get, put, cnt = rt.polyop.getMapVert, rt.polyop.setMapVert, rt.polyop.getNumMapVerts
    elif cls == 'Editable_mesh':
        get, put, cnt = rt.meshop.getMapVert, rt.meshop.setMapVert, rt.meshop.getNumMapVerts
    else:
        raise ValueError('{}: base object {} (Editable_Poly/Mesh expected)'.format(node.name, cls))
    d = rt.Point3(du, dv, 0)
    for i in range(1, int(cnt(node.baseObject, 1)) + 1):
        put(node.baseObject, 1, i, get(node.baseObject, 1, i) + d)
    if cls == 'Editable_mesh':
        rt.update(node)


def vpm_udims(lib, kind, address, project_dir, mode='preview', version='high', slot=1, tile_limit=None,
              extra_used=None, obj_type='Ground', texel=1000.0):
    """VPM textures of the imported assets of one library: preview -> plan; apply -> maps copied under the VPM
    names into <project>/textures/vpm/, flat ERM/Normal placeholders, UVs moved by whole tiles, bitmaps repointed,
    read back. Only the tile-per-set route changes the scene; the packed route returns its plan."""
    tex = _sibling('assets_textures')
    names = _sibling('names_core')
    k = m_per_unit()
    nodes = [o for o in rt.objects if str(rt.getUserProp(o, core.PROP_LIB)) == lib and
             str(rt.getUserProp(o, core.PROP_VER)) == version]
    rows = []
    for n in nodes:
        if n.material is None:
            continue
        maps = [str(m.filename) for m in node_bitmaps([n])]
        bb, area = _uv_stats(n, k)
        diffuse = [p for p in maps if tex.role_of(p) == 'diffuse']
        rows.append({'asset': str(rt.getUserProp(n, core.PROP_ID)), 'version': version, 'material': str(n.material.name),
                     'maps': maps, 'uv_bbox': bb, 'area3d_m2': area,
                     'tex_px': png_size(diffuse[0]) if diffuse else None, 'node': str(n.name)})
    sets = tex.texture_sets(rows)
    folder = os.path.join(project_dir, 'textures', 'vpm')
    existing = os.listdir(folder) if os.path.isdir(folder) else []
    used = tex.used_tiles(existing, address, names.udim_of, ground=obj_type.startswith('Ground'))
    for s_, tiles in (extra_used or {}).items():
        used.setdefault(int(s_), set()).update(tiles)
    plan = tex.vpm_plan(sets, used, address, names.texture_stem, kind, slot, tile_limit, obj_type, texel)
    plan.update(used={str(s_): sorted(v) for s_, v in used.items()}, folder=folder, nodes=len(nodes))
    if mode != 'apply' or plan['mode'] != 'tile_per_set' or plan['blocking']:
        plan['applied'] = False
        return plan
    os.makedirs(folder, exist_ok=True)
    written = []
    for r in plan['rows']:
        for c in r['copy']:
            ext = os.path.splitext(c['src'])[1] or '.png'
            dst = os.path.join(folder, c['stem'] + ext)
            if os.path.exists(dst):
                raise ValueError('exists, not overwritten: ' + dst)
            shutil.copyfile(c['src'], dst)
            c['dst'] = dst
            written.append(dst)
        for p in r['placeholders']:
            dst = os.path.join(folder, p['stem'] + '.png')
            write_flat_png(dst, p['rgb'])
            p['dst'] = dst
            written.append(dst)
    done_base = set()
    for r in plan['rows']:
        du, dv = r['uv_offset']
        new_by_old = {c['src']: c['dst'] for c in r['copy']}
        for n in nodes:
            if n.material is None or str(n.material.name) != r['material']:
                continue
            h = _handle(n.baseObject)
            if h not in done_base:
                _shift_uv(n, du, dv)
                done_base.add(h)
            for m in node_bitmaps([n]):
                if str(m.filename) in new_by_old:
                    m.filename = new_by_old[str(m.filename)]
    rt.freeSceneBitmaps()
    back = []
    for r in plan['rows']:
        u0, v0 = r['uv_offset']
        for n in nodes:
            if n.material is None or str(n.material.name) != r['material']:
                continue
            bb, _ = _uv_stats(n, k)
            maps = [str(m.filename) for m in node_bitmaps([n])]
            back.append({'node': str(n.name), 'udim': r['udim'], 'uv_bbox': bb,
                         'inside_tile': bb is not None and bb[0][0] >= u0 - 1e-4 and bb[0][1] >= v0 - 1e-4 and
                         bb[1][0] <= u0 + 1 + 1e-4 and bb[1][1] <= v0 + 1 + 1e-4,
                         'maps': maps, 'maps_exist': all(os.path.isfile(p) for p in maps),
                         'maps_udim': sorted({names.udim_of(p) for p in maps})})
    plan.update(applied=True, written=written, readback=back)
    return plan


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
