"""new-case: AGR Tools 0.8 (#908) tex, 3ds Max side (branch B, improve/issue-908-tex).

runtime.edits_080 calls `<function>(ctx, mode, nodes, preview)` for `scene_missing_maps` (scene.missing_maps),
`tex_format_fix` (tex.format_fix), `tex_placeholders` (tex.placeholders).
ctx: agr (runtime globals), core (tex_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Nothing here edits the scene: maps are read from materials/texmaps of ALL nodes (hidden and UCX included),
from scene materials and from the AssetManager; paths are checked with `doesFileExist`; UV tiles come from
in-memory `snapshotAsMesh` copies. Files are written only by tex.format_fix / tex.placeholders, only as new
files (edit_core.write_new, exclusive create) into new folders.
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


def _sources(ctx, opts, nodes):
    core = ctx.core
    if opts.get('files'):
        return [os.path.abspath(p) for p in opts['files']]
    if opts.get('folder'):
        if not os.path.isdir(opts['folder']):
            raise ValueError('folder not found: ' + opts['folder'])
        return core.list_sources(os.path.abspath(opts['folder']))
    targets = ctx.agr._targets(nodes)
    paths = [p for p in _node_maps(targets) if os.path.splitext(p)[1].lower() in core.IMAGE_EXTS]
    if not paths:
        raise ValueError('no texture files on the target objects; give options.files or options.folder')
    return paths


def tex_format_fix(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode == 'preview':
        opts = core.format_options(ctx.options)
        sources = _sources(ctx, opts, nodes)
        opts['files'] = sources
        opts.pop('folder', None)
        out, rows = core.format_fix(sources, opts, _read, _decode_other(core), exists=os.path.exists)
        state = core.format_state(sources, _read, opts, out)
        return core.format_report(edit, 'preview', out, rows, edit.fingerprint(state), opts)
    plan = preview['plan']
    opts, out = plan['options'], plan['out']
    sources = opts['files']
    edit.require_current(preview, core.format_state(sources, _read, opts, out))
    run = dict(opts, out=out)
    out2, rows = core.format_fix(sources, run, _read, _decode_other(core), exists=os.path.exists)
    planned = [(f['source'], f.get('out'), f.get('sha256_out')) for f in plan['files']]
    if [(r['source'], r.get('out'), r.get('sha256_out')) for r in rows] != planned:
        raise edit.StalePreview('apply result differs from the preview; run preview again')
    written = core.write_outputs(edit, out2, rows)
    return core.format_report(edit, 'apply', out2, rows, None, opts, written)


# ---- tex.placeholders ----------------------------------------------------------------------------------
def _scene_address(ctx, nodes):
    """Address and Ground flag from the target names SM_{Address}_{Main|MainGlass|Ground}[_NNN]."""
    import re
    rt = _rt()
    src = list(nodes) if nodes is not None else list(rt.selection)
    found = set()
    for n in src:
        m = re.match(r'^(?:UCX_)?SM_([A-Za-z0-9_]+?)_(Main|MainGlass|Ground)(?:_\d{3})?$', str(n.name))
        if m:
            found.add((m.group(1), m.group(2) == 'Ground'))
    if len(found) != 1:
        raise ValueError('address unknown: select one SM_<Address>_Main/Ground object or give options.address '
                         '(found {})'.format(sorted(found)))
    return found.pop()


def _placeholder_opts(ctx, nodes):
    core = ctx.core
    rt = _rt()
    opts = core.placeholder_options(ctx.options)
    if opts['address'] is None:
        opts['address'], opts['ground'] = _scene_address(ctx, nodes)
    if opts['folder'] is None:
        scene = str(rt.maxFilePath)
        if not scene:
            raise ValueError('scene is not saved: give options.folder (no relative Maps\\ default)')
        opts['folder'] = os.path.join(scene, 'Maps')
    opts['folder'] = os.path.abspath(opts['folder'])
    if opts['diffuse_from']:
        path = _resolve(opts['diffuse_from'])
        data = _read(path)
        if data is None:
            raise ValueError('diffuse_from not found: ' + opts['diffuse_from'])
        img = core.decode_png(data)[0] if data[:8] == core.PNG_SIG else _decode_other(core)(path)
        opts['colours']['Diffuse'] = core.average_colour(img)
        opts['diffuse_from'] = path
    return opts


def _placeholder_state(rows, opts):
    return {'tool': 'tex.placeholders', 'options': opts,
            'targets': [{'path': r['path'], 'exists': os.path.exists(r['path'])} for r in rows]}


def tex_placeholders(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    if mode == 'preview':
        opts = _placeholder_opts(ctx, nodes)
        rows = core.placeholder_plan(opts)
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
            owner = dict(info, material=top, map=str(tm.name))
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


def _search_folders(records, opts):
    rt = _rt()
    folders = {os.path.dirname(r['path']) for r in records if r['path'] and os.path.isabs(r['path'])}
    try:
        for i in range(int(rt.mapPaths.count())):
            folders.add(str(rt.mapPaths.get(i + 1)))
    except Exception:  # noqa: BLE001 - no user map paths
        pass
    if str(rt.maxFilePath):
        folders.add(str(rt.maxFilePath))
    return sorted(f for f in folders if f), list(opts.get('search') or [])


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
    targets = list(nodes) if nodes is not None else list(rt.objects)
    records, notes = _scene_maps(core, targets)
    flat, deep = _search_folders(records, opts)
    index = core.candidate_index(flat, recursive=deep)
    rows = core.missing_maps(records, _exists, _read_head, index)
    owners = sorted({(o['handle'], o['node']) for r in rows for o in r['owners'] if o.get('handle')})
    state = {'tool': 'scene.missing_maps', 'maps': rows}
    return core.missing_report(edit, rows, edit.fingerprint(state), owners,
                               extra={'notes': notes, 'search': {'folders': flat, 'recursive': deep}})
