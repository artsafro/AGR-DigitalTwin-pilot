"""new-case: AGR Tools 0.8 (#908) tex, 3ds Max side (branch B, improve/issue-908-tex).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `scene_missing_maps` (scene.missing_maps),
`tex_format_fix` (tex.format_fix), `tex_placeholders` (tex.placeholders).
ctx: agr (runtime globals), core (tex_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Nothing here edits the scene: maps are read from materials/texmaps of ALL nodes (hidden and UCX included),
from scene materials and from the AssetManager; paths are checked with `doesFileExist`; UV tiles come from
in-memory `snapshotAsMesh` copies. Files are written only by tex.format_fix / tex.placeholders, only as new
files (edit_core.write_new, exclusive create) into new folders.

Shared enumerator (read by branches D `scene.maps_usage` and E3 `scene.census`, SPLIT #979): the signature
`_scene_maps(core, nodes) -> (records, notes)` and the record keys `path, owners, uv_tiles, source` are kept;
0.9 (#979 E1) only ADDS owner keys `slot` (sub-texmap slot name in its parent) and `role` (names_core role or
None) for the mask candidates of scene.missing_maps.
"""
import os
import shutil
import tempfile

_FILE_PROPS = ('filename', 'fileName', 'HDRIMapName', 'bitmapFileName', 'Filename')


def _rt():
    from pymxs import runtime
    return runtime


def _undef(v):
    rt = _rt()
    return v is None or v == rt.undefined


def _handle(a):
    return int(_rt().getHandleByAnim(a))


# ---- shared readers ------------------------------------------------------------------------------------
def _exists(path):
    rt = _rt()
    try:
        return bool(rt.doesFileExist(path)) and os.path.isfile(path)
    except Exception:  # noqa: BLE001 - a malformed path is a missing file
        return False


def _read(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        return f.read()


def _read_head(path, size=65536):
    if not path or not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        return f.read(size)


def _resolve(path):
    """Absolute path of a scene map: as is when it exists, else through the map paths, else unchanged."""
    rt = _rt()
    if path and os.path.isfile(path):
        return path
    try:
        full = str(rt.mapPaths.getFullFilePath(path))
    except Exception:  # noqa: BLE001 - unresolved stays as written
        full = ''
    return full if full and os.path.isfile(full) else path


def _decode_other(core):
    """Decoder for non-PNG sources (JPG, TGA, BMP...) through .NET System.Drawing -> temporary PNG -> core."""
    def decode(path):
        rt = _rt()
        tmp = tempfile.mkdtemp(prefix='agr_tex_')
        try:
            bmp = rt.dotNetObject('System.Drawing.Bitmap', path)
            try:
                png = os.path.join(tmp, 'decoded.png')
                bmp.Save(png, rt.dotNetClass('System.Drawing.Imaging.ImageFormat').Png)
            finally:
                bmp.Dispose()
            with open(png, 'rb') as f:
                img, _ = core.decode_png(f.read())
            return img
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return decode


def _materials(mat):
    """Material/texmap tree below `mat`: (materials, texmaps), each once (depth first)."""
    rt = _rt()
    mats, maps, stack, seen = [], [], [mat], set()
    while stack:
        m = stack.pop()
        if _undef(m):
            continue
        try:
            key = _handle(m)
        except Exception:  # noqa: BLE001 - not an animatable
            continue
        if key in seen:
            continue
        seen.add(key)
        if rt.superClassOf(m) == rt.textureMap:
            maps.append(m)
        else:
            mats.append(m)
        try:
            for i in range(int(rt.getNumSubMtls(m))):
                stack.append(rt.getSubMtl(m, i + 1))
        except Exception:  # noqa: BLE001 - texmaps have no sub-materials
            pass
        try:
            for i in range(int(rt.getNumSubTexmaps(m))):
                stack.append(rt.getSubTexmap(m, i + 1))
        except Exception:  # noqa: BLE001
            pass
    return mats, maps


def _slot_names(mat):
    """{texmap anim handle: slot name in its parent} below `mat` (first parent wins, depth first)."""
    rt = _rt()
    out, stack, seen = {}, [mat], set()
    while stack:
        m = stack.pop()
        if _undef(m):
            continue
        try:
            key = _handle(m)
        except Exception:  # noqa: BLE001
            continue
        if key in seen:
            continue
        seen.add(key)
        try:
            for i in range(int(rt.getNumSubMtls(m))):
                stack.append(rt.getSubMtl(m, i + 1))
        except Exception:  # noqa: BLE001
            pass
        try:
            for i in range(int(rt.getNumSubTexmaps(m))):
                sub = rt.getSubTexmap(m, i + 1)
                if _undef(sub):
                    continue
                try:
                    out.setdefault(_handle(sub), str(rt.getSubTexmapSlotName(m, i + 1)))
                except Exception:  # noqa: BLE001 - a slot without a name has no role
                    pass
                stack.append(sub)
        except Exception:  # noqa: BLE001
            pass
    return out


def _map_file(tm):
    rt = _rt()
    for prop in _FILE_PROPS:
        try:
            if rt.isProperty(tm, prop):
                v = rt.getProperty(tm, prop)
                if not _undef(v) and str(v).strip():
                    return str(v)
        except Exception:  # noqa: BLE001
            continue
    return None


def _map_channel(tm):
    rt = _rt()
    try:
        coords = tm.coords
        if rt.isProperty(coords, 'mapChannel'):
            return int(coords.mapChannel)
    except Exception:  # noqa: BLE001 - maps without coords use channel 1
        pass
    return 1


# ---- tex.format_fix ------------------------------------------------------------------------------------
def _node_maps(nodes):
    rt = _rt()
    out = []
    for n in nodes:
        if _undef(n.material):
            continue
        maps = rt.usedMaps(n.material)
        for i in range(int(maps.count) if maps is not None else 0):
            p = _resolve(str(maps[i]))
            if p not in out:
                out.append(p)
    return out


def _node_map_owners(nodes):
    """{resolved map path: [[handle, name]]} over the usedMaps of the nodes' materials."""
    rt = _rt()
    out = {}
    for n in nodes:
        if _undef(n.material):
            continue
        maps = rt.usedMaps(n.material)
        for i in range(int(maps.count) if maps is not None else 0):
            p = _resolve(str(maps[i]))
            owner = [_handle(n), str(n.name)]
            if owner not in out.setdefault(p, []):
                out[p].append(owner)
    return out


def _sources(ctx, opts, nodes):
    """(sources, owners). owners {path: [[handle, name]]} only when the files come from the target objects."""
    core = ctx.core
    if opts.get('files'):
        return [os.path.abspath(p) for p in opts['files']], {}
    if opts.get('folder'):
        if not os.path.isdir(opts['folder']):
            raise ValueError('folder not found: ' + opts['folder'])
        return core.list_sources(os.path.abspath(opts['folder'])), {}
    targets = ctx.agr._targets(nodes)
    owners = {p: o for p, o in _node_map_owners(targets).items()
              if os.path.splitext(p)[1].lower() in core.IMAGE_EXTS}
    paths = sorted(owners, key=str.lower)
    if not paths:
        raise ValueError('no texture files on the target objects; give options.files or options.folder')
    return paths, owners


def tex_format_fix(ctx, mode, nodes, preview):
    """Temporary files: only the .NET decoder makes one (mkdtemp) and removes it in `finally` (T01: the team
    compressor left 18 files / 78 MB in %TEMP%)."""
    core, edit = ctx.core, ctx.edit
    if mode == 'preview':
        opts = core.format_options(ctx.options)
        sources, owners = _sources(ctx, opts, nodes)
        opts['files'] = sources
        opts.pop('folder', None)
        out, rows = core.format_fix(sources, opts, _read, _decode_other(core), exists=os.path.exists)
        state = core.format_state(sources, _read, opts, out)
        rep = core.format_report(edit, 'preview', out, rows, edit.fingerprint(dict(state, owners=owners)), opts,
                                 owners=owners)
        return rep
    plan = preview['plan']
    opts, out = plan['options'], plan['out']
    sources = opts['files']
    owners = plan.get('owners') or {}
    edit.require_current(preview, dict(core.format_state(sources, _read, opts, out), owners=owners))
    run = dict(opts, out=out)
    out2, rows = core.format_fix(sources, run, _read, _decode_other(core), exists=os.path.exists)
    planned = [(f['source'], f.get('out'), f.get('sha256_out')) for f in plan['files']]
    if [(r['source'], r.get('out'), r.get('sha256_out')) for r in rows] != planned:
        raise edit.StalePreview('apply result differs from the preview; run preview again')
    written = core.write_outputs(edit, out2, rows)
    return core.format_report(edit, 'apply', out2, rows, None, opts, written, owners=owners)


# ---- tex.placeholders ----------------------------------------------------------------------------------
def _scene_address(ctx, nodes):
    """Address and Ground flag of ONE target set (0.8 API): from the names SM_{Address}_{Main|MainGlass|Ground}."""
    sets = _address_sets(nodes)
    if len(sets) != 1:
        raise ValueError('address unknown: select one SM_<Address>_Main/Ground object or give options.address '
                         '(found {})'.format(sorted((s['address'], s['ground']) for s in sets)))
    return sets[0]['address'], sets[0]['ground']


def _address_sets(nodes):
    """One placeholder set per (address, ground) of the selected names SM_{Address}_{Main|MainGlass|Ground}[_NNN]
    (as 0.8), owners = the nodes of that address (several addresses: several sets in one call)."""
    import re
    rt = _rt()
    src = list(nodes) if nodes is not None else list(rt.selection)
    found = {}
    for n in src:
        m = re.match(r'^(?:UCX_)?SM_([A-Za-z0-9_]+?)_(Main|MainGlass|Ground)(?:_\d{3})?$', str(n.name))
        if m:
            key = (m.group(1), m.group(2) == 'Ground')
            found.setdefault(key, []).append([_handle(n), str(n.name)])
    return [{'address': a, 'ground': g, 'owners': sorted(o)} for (a, g), o in sorted(found.items())]


def _placeholder_opts(ctx, nodes):
    core = ctx.core
    rt = _rt()
    opts = core.placeholder_options(ctx.options)
    if opts['address'] is None:
        sets = _address_sets(nodes)
        if not sets:
            raise ValueError('address unknown: select SM_<Address>_Main/Ground objects or give options.address')
    else:
        src = list(nodes) if nodes is not None else list(rt.selection)
        sets = [{'address': opts['address'], 'ground': opts['ground'],
                 'owners': sorted([_handle(n), str(n.name)] for n in src)}]
    opts['sets'] = sets
    if opts['folder'] is None:
        scene = str(rt.maxFilePath)
        if not scene:
            raise ValueError('scene is not saved: give options.folder (no relative Maps\\ default)')
        opts['folder'] = os.path.join(scene, 'Maps')
    opts['folder'] = os.path.abspath(opts['folder'])
    if opts['diffuse_from']:
        path = _resolve(opts['diffuse_from'])
        colour, reason = core.diffuse_source(path, _read(path), _decode_other(core))
        if reason:
            opts['diffuse_reason'] = reason
        else:
            opts['colours']['Diffuse'] = colour
        opts['diffuse_from'] = path
    return opts


def _placeholder_state(rows, opts):
    return {'tool': 'tex.placeholders', 'options': opts,
            'targets': [{'path': r['path'], 'exists': os.path.exists(r['path'])} for r in rows]}


def tex_placeholders(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode == 'preview':
        opts = _placeholder_opts(ctx, nodes)
        rows = core.placeholder_plan(opts, sets=opts['sets'])
        return core.placeholder_report(edit, 'preview', opts, rows, edit.fingerprint(_placeholder_state(rows, opts)))
    plan = preview['plan']
    opts = plan['options']
    rows = plan['files']
    edit.require_current(preview, _placeholder_state(rows, opts))
    written = core.write_placeholders(edit, rows)
    return core.placeholder_report(edit, 'apply', opts, rows, None, written)


# ---- scene.missing_maps (read only) --------------------------------------------------------------------
def _hidden(n):
    try:
        return bool(n.isHidden) or bool(n.layer.isHidden)
    except Exception:  # noqa: BLE001
        return bool(n.isHidden)


def _uv_faces(n, channel):
    """UV faces (lists of (u, v)) of a node's map channel from an in-memory snapshot."""
    rt = _rt()
    try:
        if not rt.canConvertTo(n, rt.TriMeshGeometry):
            return []
        m = rt.snapshotAsMesh(n)
    except Exception:  # noqa: BLE001 - shapes/helpers have no UVs
        return []
    try:
        if not rt.meshop.getMapSupport(m, channel):
            return []
        faces = []
        for f in range(int(rt.meshop.getNumMapFaces(m, channel))):
            p = rt.meshop.getMapFace(m, channel, f + 1)
            pts = []
            for k in (p.x, p.y, p.z):
                v = rt.meshop.getMapVert(m, channel, int(k))
                pts.append((float(v.x), float(v.y)))
            faces.append(pts)
        return faces
    finally:
        try:
            rt.delete(m)
        except Exception:  # noqa: BLE001
            pass


def _scene_maps(core, nodes):
    """[{path, owners, uv_tiles, source}] from node materials (all nodes), scene materials, AssetManager."""
    rt = _rt()
    records, notes = [], []
    done_mats = set()
    for n in nodes:
        mat = n.material
        if _undef(mat):
            continue
        mats, maps = _materials(mat)
        slots = _slot_names(mat)
        done_mats |= {_handle(m) for m in mats}
        name = str(n.name)
        info = {'handle': _handle(n), 'node': name, 'hidden': _hidden(n), 'ucx': name.upper().startswith('UCX_')}
        top = str(mat.name)
        for tm in maps:
            path = _map_file(tm)
            if path is None:
                continue
            tiles = None
            if core.udim_pattern(path):
                tiles = sorted(core.uv_tiles(_uv_faces(n, _map_channel(tm))))
            slot = slots.get(_handle(tm))
            role_of = getattr(core, 'role_of_slot', None)  # a reader passing an older core still works
            owner = dict(info, material=top, map=str(tm.name), slot=slot, role=role_of(slot) if role_of else None)
            records.append({'path': _resolve(path), 'owners': [owner], 'uv_tiles': tiles, 'source': 'material'})
    try:
        for i in range(int(rt.sceneMaterials.count)):
            mat = rt.sceneMaterials[i]
            if _undef(mat) or _handle(mat) in done_mats:
                continue
            for tm in _materials(mat)[1]:
                path = _map_file(tm)
                if path:
                    records.append({'path': _resolve(path), 'source': 'scene_material',
                                    'owners': [{'handle': None, 'node': None, 'material': str(mat.name),
                                                'map': str(tm.name), 'hidden': False, 'ucx': False}]})
    except Exception as exc:  # noqa: BLE001 - recorded, the material walk above still stands
        notes.append('sceneMaterials: {}'.format(exc))
    known = {os.path.normcase(r['path']) for r in records}
    try:
        am = rt.AssetManager
        for i in range(int(am.GetNumAssets())):
            a = am.GetAssetByIndex(i + 1)
            if _undef(a) or str(a.GetType()).lower() != 'bitmap':
                continue
            path = str(a.GetFileName())
            if path and os.path.normcase(_resolve(path)) not in known and os.path.normcase(path) not in known:
                records.append({'path': _resolve(path), 'owners': [], 'uv_tiles': None, 'source': 'asset_manager'})
                known.add(os.path.normcase(path))
    except Exception as exc:  # noqa: BLE001
        notes.append('AssetManager: {}'.format(exc))
    return records, notes


def _search_folders(core, records, opts):
    """Candidate folders: core.search_folders over the map paths (auto, no "123" default), user map paths, scene
    folder; options.search adds absolute folders searched recursively."""
    rt = _rt()
    user = []
    try:
        for i in range(int(rt.mapPaths.count())):
            user.append(str(rt.mapPaths.get(i + 1)))
    except Exception:  # noqa: BLE001 - no user map paths
        pass
    return core.search_folders([r['path'] for r in records], user, str(rt.maxFilePath), opts.get('search') or [])


def scene_missing_maps(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    opts = dict(ctx.options)
    extra = set(opts) - {'search'}
    if extra:
        raise ValueError('unknown scene.missing_maps options: ' + ', '.join(sorted(extra)))
    if opts.get('search') is not None and (not isinstance(opts['search'], list)
                                           or not all(isinstance(p, str) for p in opts['search'])):
        raise ValueError('search must be a list of folders')
    core.search_folders([], (), '', opts.get('search') or [])  # refuse a relative folder before any scene walk
    targets = list(nodes) if nodes is not None else list(rt.objects)
    records, notes = _scene_maps(core, targets)
    flat, deep = _search_folders(core, records, opts)
    index = core.candidate_index(flat, recursive=deep)
    rows = core.missing_maps(records, _exists, _read_head, index)
    owners = sorted({(o['handle'], o['node']) for r in rows for o in r['owners'] if o.get('handle')})
    state = {'tool': 'scene.missing_maps', 'maps': rows}
    return core.missing_report(edit, rows, edit.fingerprint(state), owners,
                               extra={'notes': notes, 'search': {'folders': flat, 'recursive': deep}})


# ---- bitmap enumerator (1.0, branch N) -----------------------------------------------------------------
def _tree(mat, seen=None):
    """Material/texmap tree dict for tex_core.material_bitmaps from a pymxs material or texmap."""
    rt = _rt()
    seen = set() if seen is None else seen
    if _undef(mat):
        return {'name': None, 'subs': [], 'maps': []}
    key = _handle(mat)
    if key in seen:                       # a loop or a shared map is walked once per branch
        return {'name': str(mat.name), 'subs': [], 'maps': []}
    seen = seen | {key}
    node = {'name': str(mat.name), 'subs': [], 'maps': []}
    if rt.superClassOf(mat) == rt.textureMap:
        return node
    ids = []
    try:
        ids = [int(i) for i in mat.materialIDList]
    except Exception:  # noqa: BLE001 - not a Multi/Sub
        pass
    try:
        for i in range(int(rt.getNumSubMtls(mat))):
            sub = rt.getSubMtl(mat, i + 1)
            if not _undef(sub):
                node['subs'].append({'id': ids[i] if i < len(ids) else i + 1, 'material': _tree(sub, seen)})
    except Exception:  # noqa: BLE001
        pass
    try:
        for i in range(int(rt.getNumSubTexmaps(mat))):
            tm = rt.getSubTexmap(mat, i + 1)
            if _undef(tm):
                continue
            entry = {'slot': str(rt.getSubTexmapSlotName(mat, i + 1)), 'name': str(tm.name), 'file': _map_file(tm),
                     'children': []}
            child = _tree_texmap(tm, seen)
            entry['children'] = child
            node['maps'].append(entry)
    except Exception:  # noqa: BLE001
        pass
    return node


def _tree_texmap(tm, seen):
    rt = _rt()
    out = []
    try:
        for i in range(int(rt.getNumSubTexmaps(tm))):
            sub = rt.getSubTexmap(tm, i + 1)
            if _undef(sub) or _handle(sub) in seen:
                continue
            seen = seen | {_handle(sub)}
            out.append({'name': str(sub.name), 'subs': [], 'maps': [
                {'slot': str(rt.getSubTexmapSlotName(tm, i + 1)), 'name': str(sub.name), 'file': _map_file(sub),
                 'children': _tree_texmap(sub, seen)}]})
    except Exception:  # noqa: BLE001
        pass
    return out


def scene_bitmaps(core, nodes):
    """[{node, handle, rows}] bitmap rows (tex_core.material_bitmaps) of the materials of `nodes`, one entry per node;
    resolved paths. Nodes without a material have an empty list (reported by the caller, not dropped silently)."""
    out = []
    for n in nodes:
        rows = []
        if not _undef(n.material):
            rows = core.material_bitmaps(_tree(n.material))
            for r in rows:
                r['path'] = _resolve(r['path'])
        out.append({'node': str(n.name), 'handle': _handle(n), 'rows': rows})
    return out
