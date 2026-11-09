"""new-case: AGR Tools 0.9 (#979) maps usage report, 3ds Max side. Owned by branch D
(improve/issue-979-export-scene-light).

runtime.edits_090 calls `scene_maps_usage(ctx, mode, nodes, preview)` for scene.maps_usage.
ctx: agr (runtime globals), core (mapsuse_core), edit (edit_core), emax (edit_max), options (dict of the preview).
Import pymxs inside functions so this file loads under plain pytest.

Enumeration (read only, the whole scene whatever the scope - an «extra» file is extra for the scene):
1. the shared bitmap enumerator of scene.missing_maps, `tex_max._scene_maps` (node materials of every node,
   scene materials, AssetManager) - read here, owned by branch E1;
2. every `BitmapTexture` class instance with its dependent nodes (`refs.dependentNodes`): Blend, DoubleSided,
   Shell and any other container, lights (projector maps), renderable splines;
3. the environment map tree.
The scope (`nodes`, else every node) only chooses which owner nodes are report objects.
"""
import hashlib
import os


def _rt():
    from pymxs import runtime
    return runtime


def _handle(a):
    return int(_rt().getHandleByAnim(a))


def _tex(ctx):
    texcore = ctx.agr._load_core('tex_core.py', 'agr_tools_tex_core')
    texmax = ctx.agr._load_core('tex_max.py', 'agr_tools_tex_max')
    return texcore, texmax


def _owner(n, tm, material=None):
    return {'handle': _handle(n), 'node': str(n.name), 'material': material, 'map': str(tm.name),
            'hidden': bool(n.isHidden)}


def _class_instances(texmax):
    """[{path, owners, source}] of every BitmapTexture instance; owners through refs.dependentNodes."""
    rt = _rt()
    out, notes = [], []
    env = set()
    try:
        if rt.environmentMap is not None:
            env = {_handle(m) for m in texmax._materials(rt.environmentMap)[1]}
    except Exception as exc:  # noqa: BLE001 - recorded; the class instances below still stand
        notes.append('environmentMap: {}'.format(exc))
    for tm in rt.getClassInstances(rt.BitmapTexture):
        path = texmax._map_file(tm)
        if not path:
            continue
        try:
            deps = [n for n in rt.refs.dependentNodes(tm) if rt.isValidNode(n)]
        except Exception:  # noqa: BLE001 - no dependents readable: the map still counts as used
            deps = []
        source = 'environment' if _handle(tm) in env else ('class_instance' if deps else 'class_instance_unowned')
        out.append({'path': texmax._resolve(path), 'owners': [_owner(n, tm) for n in deps], 'source': source})
    return out, notes


def _folders(opts, result_paths, exists):
    rt = _rt()
    if opts['folders']:
        missing = [f for f in opts['folders'] if not os.path.isdir(f)]
        if missing:
            raise ValueError('maps folder not found: ' + ', '.join(missing))
        return opts['folders'], 'options'
    scene_dir = str(rt.maxFilePath)
    if scene_dir:
        for name in ('maps', 'Maps', 'textures', 'Textures'):
            cand = os.path.join(scene_dir, name)
            if os.path.isdir(cand):
                return [os.path.abspath(cand)], 'scene folder'
    dirs = sorted({os.path.dirname(os.path.abspath(p)) for p in result_paths if p and exists(p)}, key=str.lower)
    if not dirs:
        raise ValueError('no maps folder: save the scene next to a maps folder, keep an existing map in the scene '
                         'or give options.folders')
    return dirs, 'folders of the used maps'


def scene_maps_usage(ctx, mode, nodes, preview):
    core, edit = ctx.core, ctx.edit
    rt = _rt()
    if mode != 'preview':
        raise ValueError('scene.maps_usage is read-only: there is no apply')
    opts = core.maps_options(ctx.options)
    texcore, texmax = _tex(ctx)
    everything = list(rt.objects)
    records, notes = texmax._scene_maps(texcore, everything)
    more, more_notes = _class_instances(texmax)
    records += more
    notes += more_notes

    def exists(p):
        return bool(p) and os.path.isfile(p)

    cache = {}

    def digest(p):
        key = core.norm(p)
        if key not in cache:
            h = hashlib.sha256()
            with open(p, 'rb') as f:
                for block in iter(lambda: f.read(1 << 20), b''):
                    h.update(block)
            cache[key] = h.hexdigest()
        return cache[key]

    folders, why = _folders(opts, [r['path'] for r in records], exists)
    files = []
    for folder in folders:
        files += [f for f in core.list_folder(folder, opts['recursive']) if f not in files]
    result = core.usage(records, files, exists, digest)
    scope_nodes = list(nodes) if nodes is not None else everything
    owners = {o['handle'] for r in result['used'] + result['missing'] for o in r['owners'] if o.get('handle')}
    scope = sorted((_handle(n), str(n.name)) for n in scope_nodes if rt.isValidNode(n) and _handle(n) in owners)
    if nodes is not None:
        scope = sorted({(_handle(n), str(n.name)) for n in scope_nodes if rt.isValidNode(n)})
    if not scope:
        raise ValueError('no scene map is used by the nodes in scope: an empty input is an error, not a pass')
    state = {'tool': core.TOOL, 'files': [(f, os.path.getsize(f)) for f in files], 'used': result['used'],
             'missing': result['missing'], 'scope': scope}
    notes.append('maps folders: {} ({})'.format(', '.join(folders), why))
    return core.maps_report(edit, result, scope, folders, edit.fingerprint(state), notes)
