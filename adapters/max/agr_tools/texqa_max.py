"""new-case: AGR Tools 0.9 (#979) texture QA (ERM channels, DirectX normals), 3ds Max side (branch B).

runtime.edits_090 calls `tex_erm_normal_check(ctx, mode, nodes, preview)`; ctx: agr (runtime globals), core
(texqa_core), edit (edit_core), emax (edit_max), options (dict of the preview). Read row: preview only, the scene
and the files are not changed (the files are opened for reading only, Python `open(..., 'rb')`; no Max bitmap,
so neither gamma nor OCIO touches the pixels).

Also the shared Max helpers of branch B (udim.slots, udim.matid_unwrap, tex.finish_map, atlas.flora,
atlas.groundel load this file through runtime._load_core): selection, material map walk, file read, metres per
system unit from `units.SystemType`/`units.SystemScale` (never the string `units.decodeValue`, which gives
1.5m -> 1.0 on ru-RU, measured T05/light_metr).

Options: `emissive` (list of material names that DO emit light; default: read from the material).
"""
import hashlib
import os

TOOL = 'tex.erm_normal_check'
OPTION_KEYS = {'emissive'}
_UNIT_M = {'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344, 'millimeters': 0.001, 'centimeters': 0.01,
           'meters': 1.0, 'kilometers': 1000.0}


def _rt():
    from pymxs import runtime
    return runtime


# ---- shared helpers (branch B glue) -----------------------------------------------------------------------
def handle(n):
    return int(_rt().getHandleByAnim(n))


def target_nodes(nodes, what='objects'):
    """The given nodes or the selection, de-duplicated, in handle order. Empty is an error, not a pass."""
    rt = _rt()
    nodes = list(rt.selection) if nodes is None else list(nodes)
    if not nodes:
        raise ValueError('nothing selected: select the {} to check'.format(what))
    out, seen = [], set()
    for n in nodes:
        if not rt.isValidNode(n):
            raise ValueError('invalid node in the target set')
        h = handle(n)
        if h in seen:
            raise ValueError('duplicate node in the target set')
        seen.add(h)
        out.append(n)
    return sorted(out, key=handle)


def unit_m():
    """Metres per system unit from units.SystemType * units.SystemScale (no decodeValue)."""
    import math
    rt = _rt()
    kind = str(rt.units.SystemType).lower().lstrip('#')
    if kind not in _UNIT_M:
        raise ValueError('unmapped system unit type: ' + kind)
    value = _UNIT_M[kind] * float(rt.units.SystemScale)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('invalid system units')
    return value


def _is_map(v):
    """A texture map value. Measured (job 20261105-140419-b58396e2, Max 2024): `superClassOf v == rt.textureMap`
    is never true in pymxs, so the superclass is compared by name."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return False
    try:
        return str(_rt().superClassOf(v)).lower() == 'texturemap'
    except Exception:  # noqa: BLE001 - a non-Max value is not a map
        return False


def _walk_map(tex, slot, out, material, depth=0):
    rt = _rt()
    if depth > 16 or tex is None:
        return
    try:
        cls = str(rt.classOf(tex)).lower()
    except Exception:  # noqa: BLE001 - not a Max value
        return
    if cls == 'bitmaptexture':
        out.append({'material': material, 'slot': slot, 'path': str(tex.filename or ''), 'map': tex})
        return
    if cls == 'normal_bump':
        slot = slot + '/normal'
    try:
        count = int(rt.getNumSubTexmaps(tex))
    except Exception:  # noqa: BLE001 - not a texture map
        return
    for i in range(1, count + 1):
        _walk_map(rt.getSubTexmap(tex, i), slot, out, material, depth + 1)


def sub_materials(n):
    """[(material id or None, material)] of a node: a Multi/Sub gives its listed slots, a single material id None."""
    rt = _rt()
    mat = n.material
    if mat is None:
        return []
    if rt.classOf(mat) == rt.MultiMaterial:
        out = []
        for i in range(len(mat.materialIDList)):
            sub = mat.materialList[i]
            if sub is not None:
                out.append((int(mat.materialIDList[i]), sub))
        return out
    return [(None, mat)]


def material_maps(mat):
    """[{'material', 'slot', 'path', 'map'}] of every Bitmaptexture under the material's map slots
    (getNumSubTexmaps / getSubTexmap / getSubTexmapSlotName: the same API for Standard, Physical and others)."""
    rt = _rt()
    out = []
    name = str(mat.name)
    for i in range(1, int(rt.getNumSubTexmaps(mat)) + 1):
        tex = rt.getSubTexmap(mat, i)
        if tex is None:
            continue
        try:
            slot = str(rt.getSubTexmapSlotName(mat, i))
        except Exception:  # noqa: BLE001 - unnamed slot
            slot = 'slot{}'.format(i)
        _walk_map(tex, slot, out, name)
    return out


def emissive(mat):
    """True when the material declares emission (Standard self-illumination, Physical emission, a map in it)."""
    rt = _rt()
    for prop in rt.getPropNames(mat):
        key = str(prop).lower()
        if not ('selfillum' in key or 'emission' in key or 'emit' in key):
            continue
        try:
            v = rt.getProperty(mat, prop)
        except Exception:  # noqa: BLE001
            continue
        if _is_map(v):
            return True
        if isinstance(v, bool):
            if v and 'use' in key:
                return True
            continue
        if isinstance(v, (int, float)) and 'color' not in key and float(v) > 0:
            if 'amount' in key or key in ('emission', 'emissionweight', 'emission_weight'):
                return True
    return False


def resolve(path):
    """Existing full path of a map file name (as given, else through the map paths), or None."""
    if path and os.path.isfile(path):
        return path
    if not path:
        return None
    try:
        full = str(_rt().mapPaths.getFullFilePath(path))
    except Exception:  # noqa: BLE001
        full = ''
    return full if full and os.path.isfile(full) else None


def read_bytes(path):
    full = resolve(path)
    if full is None:
        return None
    with open(full, 'rb') as f:
        return f.read()


def md5(data):
    return None if data is None else hashlib.md5(data).hexdigest()


# ---- tex.erm_normal_check ------------------------------------------------------------------------------
def _options(ctx):
    opts = dict(ctx.options or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown tex.erm_normal_check options: ' + ', '.join(sorted(unknown)))
    em = opts.get('emissive', None)
    if em is not None and (not isinstance(em, list) or not all(isinstance(x, str) for x in em)):
        raise ValueError('options.emissive must be a list of material names')
    return {'emissive': em}


def collect(core, nodes, options):
    rt = _rt()
    objects, state = [], []
    for n in nodes:
        maps, skipped = [], []
        if rt.superClassOf(n) != rt.GeometryClass:
            skipped.append((str(n.name), 'not geometry'))
        subs = sub_materials(n)
        if not subs and not skipped:
            skipped.append((str(n.name), 'no material'))
        for _mid, mat in subs:
            em = (str(mat.name) in options['emissive']) if options['emissive'] is not None else emissive(mat)
            for m in material_maps(mat):
                role = core.role_of(m['path'], m['slot'])
                if role is None:
                    continue
                data = read_bytes(m['path'])
                maps.append({'path': resolve(m['path']) or m['path'], 'role': role, 'emissive': em,
                             'data': data, 'material': m['material']})
        if not maps and not skipped:
            skipped.append((str(n.name), 'no ERM or normal map on the object'))
        objects.append({'key': handle(n), 'name': str(n.name), 'maps': maps, 'skipped': skipped})
        state.append({'handle': handle(n), 'name': str(n.name),
                      'maps': sorted([m['path'], m['role'], m['emissive'], md5(m['data'])] for m in maps)})
    return objects, state


def tex_erm_normal_check(ctx, mode, nodes, preview):
    edit, core = ctx.edit, ctx.core
    if mode != 'preview':
        raise ValueError(TOOL + ' is read-only: there is no apply')
    options = _options(ctx)
    nodes = target_nodes(nodes)
    objects, state = collect(core, nodes, options)
    plan = core.erm_normal_plan(objects)
    entries = [edit.entry(key, name, [edit.finding(c, (), d) for c, d in f]) for key, name, f in plan['entries']]
    skipped = [edit.skipped(item, reason) for item, reason in plan['skipped']]
    return edit.report(TOOL, 'preview', entries, plan['done'], skipped, plan['ambiguous'],
                       state_hash=edit.fingerprint(state), extra={'options': options, 'issue': '#979'})
