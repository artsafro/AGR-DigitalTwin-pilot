"""AGR Tools 1.0 (#1024), owned by branch N (improve/issue-1024-vpm-maps): shared module vpmmaps: D + ERM + N maps of the VPM step of vpm.build; stdlib only.

Lab L15 (docs/experiments/vpm.build-maps.md, verdict `new`): GeoAGR Render Material (`GeoAGR.ms:22888-23415`) is NOT
taken. Not repeated: ERM and normal from brightness/bump (`:23095-23101`), UDIM = ID + 1000 (`:22998`), the `_1` slot
hard-wired in the name (`:23016-23018`), a ready ERM that is not 256x256 giving no ERM file, silent overwrite and a
changed Physical Diffuse (almost black), non-deterministic PNGs, external programs without an exit-code check.

Here (K3): the record of the material library supplies the maps. Per used library id of a mesh, with the UDIM from
`matlib_core.renumber_dense` (UDIM numbering is per mesh, owner answer V9 06.11.2026: body from 1001, windows/glass
mesh from 1001 too):
* Diffuse: `rgb_srgb` of the record (solid), or the mask recipe through the `base_map` file when it is given
  (`options.map_dir`); never a Physical-material read;
* ERM: R = emissive, G = roughness, B = metallic of the record, 8 bit: the record keeps levels 0..255 and the texel
  is that level (1.0.1: one scale with matlib_core / tiles_core; L15 acceptance 2, delta <= 1 level); a ready
  ERM file of ANY size (256..4096) is copied byte for byte (`options.ready_erm`);
* Normal: flat 128/128/255 for a solid record; from the grey mask (height) for a mask recipe; a supplied normal map
  (`options.ready_normal`) passes unchanged (same bytes);
* names by names_core (`T_<Address>[_Ground]_<Diffuse|ERM|Normal>_<Slot>.<UDIM>.png`), PNG 8 bit RGB, no alpha, fixed
  encoder settings: the same input gives the same bytes (no timestamps);
* an existing target is skipped with a reason (or versioned), never overwritten; a missing base map is `failed`/skipped
  with a reason, never an empty "successful" file.
"""
import importlib.util
import os
import sys

KINDS = ('D', 'ERM', 'N')
KIND_ROLE = {'D': 'diffuse', 'ERM': 'metalness', 'N': 'normal'}
FLAT_NORMAL = (128, 128, 255)
DEFAULT_SIZE = 1024          # placeholder ceiling (VPM tiles are 1000 px/m, 3600 px); a solid record needs no more
SOLID_SIZE = 256             # solid colour: flat placeholder size (VPM flat_placeholder.size_px)


def _sibling(module_name, filename):
    mod = sys.modules.get(module_name)
    if mod is not None:
        return mod
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tex():
    return _sibling('agr_tools_tex_core', 'tex_core.py')


def _edit():
    return _sibling('agr_tools_edit_core', 'edit_core.py')


def _names():
    return _sibling('agr_tools_names_core', 'names_core.py')


def _level(value, name):
    """8-bit level of the library record, taken as it is (1.0.1 contract, KPP1 e2e 20261106-075555-c179f5f0).

    The library (matlib_core.load_library, materials_vNNN.json "byte_fields") keeps roughness / metallic / emissive
    as integer levels 0..255 (dt_ai MaterialRegistry `Byte`, tiles_core ERM); the ERM texel is that level. Only the
    Physical material normalises to 0..1, at its own boundary (matlib_core.sub_spec). A float (0..1 scale), a bool or
    a level outside 0..255 is an error, not a guess or a clamp."""
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('{} must be an integer level 0..255 of the library record: {!r}'.format(name, value))
    return value


def erm_colour(record):
    """(R, G, B) of the ERM texel: emissive, roughness, metallic levels 0..255 of the library record (not from
    brightness)."""
    return (_level(record.get('emissive', 0), 'emissive'), _level(record['roughness'], 'roughness'),
            _level(record['metallic'], 'metallic'))


def normal_from_height(img, strength=1.0):
    """Tangent-space normal map (Image, RGB) from a grey height map: central differences, wrap-around (tiles are
    seamless), +Z up, OpenGL-style +Y in the image's up direction. Flat input gives exactly 128/128/255."""
    tc = _tex()
    w, h, n, px = img.w, img.h, img.n, img.px
    height = [px[i * n] for i in range(w * h)]
    out = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            dx = (height[y * w + (x + 1) % w] - height[y * w + (x - 1) % w]) / 255.0 * strength
            dy = (height[((y - 1) % h) * w + x] - height[((y + 1) % h) * w + x]) / 255.0 * strength
            ln = (dx * dx + dy * dy + 1.0) ** 0.5
            o = 3 * (y * w + x)
            out[o] = int((-dx / ln) * 127.5 + 128.0 + 0.5) if dx else 128
            out[o + 1] = int((-dy / ln) * 127.5 + 128.0 + 0.5) if dy else 128
            out[o + 2] = int((1.0 / ln) * 127.5 + 127.5 + 0.5) if (dx or dy) else 255
    return tc.Image(w, h, 3, out)


def _read_file(path):
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError:
        return None


def map_name(mesh, kind, udim, slot=1, model='vpm'):
    """File name of one map by the names_core grammar. `mesh` is the SM object name (Address and Ground are read from
    it); the UDIM is the dense per-mesh tile."""
    names = _names()
    obj = names.parse_object(mesh, model)
    if isinstance(obj, str):
        raise ValueError('mesh name {!r} is not an SM object name: {}'.format(mesh, obj))
    stem = names.texture_stem(obj, model, KIND_ROLE[kind], slot, udim)
    if stem is None:
        raise ValueError('no {} map in model {}'.format(kind, model))
    return stem + '.png'


def _record_maps(record, size, opts, read):
    """{kind: (bytes | None, reason | None)} of one library record."""
    tc = _tex()
    out = {}
    mask_img = None
    recipe = record.get('recipe')
    kind = recipe.get('kind') if isinstance(recipe, dict) else recipe
    base = record.get('base_map')
    if kind in ('metric_pattern', 'greyscale_mask') and base:
        path = os.path.join(opts['map_dir'], base) if opts.get('map_dir') else None
        data = read(path) if path else None
        if data is None or data[:8] != tc.PNG_SIG:
            reason = 'base map {!r} of {} not found as PNG in map_dir: Diffuse/Normal skipped, nothing guessed'.format(
                base, record.get('key'))
            return {'D': (None, reason), 'N': (None, reason),
                    'ERM': (tc.solid_png(SOLID_SIZE, erm_colour(record)), None)}
        mask_img = tc.decode_png(data)[0]
    rgb = record.get('rgb_srgb')
    if mask_img is not None:
        out['D'] = (tc.encode_png(_tint(mask_img, rgb)), None)
        out['N'] = (tc.encode_png(normal_from_height(mask_img, opts['normal_strength'])), None)
    else:
        if not rgb or len(rgb) != 3:
            out['D'] = (None, 'record {} has no rgb_srgb'.format(record.get('key')))
        else:
            out['D'] = (tc.solid_png(size, tuple(int(c) for c in rgb)), None)
        out['N'] = (tc.solid_png(size, FLAT_NORMAL), None)
    out['ERM'] = (tc.solid_png(size, erm_colour(record)), None)
    return out


def _tint(mask_img, rgb):
    """Grey mask x colour (lerp dark -> colour as K3: colour = lerp(dark, RAL, grey)); dark = colour / 4."""
    tc = _tex()
    if not rgb or len(rgb) != 3:
        return tc.Image(mask_img.w, mask_img.h, 3, bytearray(mask_img.rgb()))
    out = bytearray(mask_img.w * mask_img.h * 3)
    n = mask_img.n
    for i in range(mask_img.w * mask_img.h):
        g = mask_img.px[i * n]
        for c in range(3):
            dark = rgb[c] // 4
            out[3 * i + c] = dark + ((rgb[c] - dark) * g + 127) // 255
    return tc.Image(mask_img.w, mask_img.h, 3, out)


def plan_maps(udim_table, library, out_dir, options=None, read=_read_file, exists=os.path.exists):
    """Planned maps without writing: {'maps': [{mesh, udim, kind, path, name, data, sha256}], 'skipped': [...]}.

    udim_table {mesh: {library_id: udim}}; library: load_library() result (`by_id`) or {library_id: record}."""
    tc, edit = _tex(), _edit()
    o = dict(options or {})
    known = {'size', 'slot', 'on_exists', 'map_dir', 'ready_erm', 'ready_normal', 'normal_strength', 'model'}
    extra = sorted(set(o) - known)
    if extra:
        raise ValueError('unknown options: ' + ', '.join(extra))
    if not udim_table:
        raise ValueError('empty UDIM table: nothing to build (empty input is an error)')
    if o.get('on_exists', 'refuse') not in ('refuse', 'version'):
        raise ValueError('on_exists must be refuse or version')
    size = o.get('size', SOLID_SIZE)
    if size not in tc.PLACEHOLDER_SIZES:
        raise ValueError('size must be one of {}'.format(tc.PLACEHOLDER_SIZES))
    opts = {'map_dir': o.get('map_dir'), 'normal_strength': float(o.get('normal_strength', 1.0))}
    by_id = library.get('by_id', library) if isinstance(library, dict) else {m['library_id']: m for m in library}
    maps, skipped, seen = [], [], set()
    for mesh in sorted(udim_table):
        table = udim_table[mesh]
        udims = sorted(table.values())
        if len(set(udims)) != len(udims) or (udims and udims != list(range(udims[0], udims[0] + len(udims)))):
            raise ValueError('UDIM table of {} is not dense and unique: {}'.format(mesh, udims))
        for lib_id in sorted(table):
            udim = table[lib_id]
            record = by_id.get(lib_id)
            if record is None:
                skipped.append({'mesh': mesh, 'udim': udim, 'kind': '*', 'reason': 'library id {} is not in the '
                                'library'.format(lib_id)})
                continue
            produced = _record_maps(record, size, opts, read)
            for kind in KINDS:
                ready = (o.get('ready_erm') if kind == 'ERM' else o.get('ready_normal') if kind == 'N' else None) or {}
                data, reason = produced[kind]
                if lib_id in ready:                       # ready map of ANY size passes as it is (L15: no ERM file for 512)
                    data = read(ready[lib_id])
                    reason = None if data is not None else 'ready {} {!r} not readable'.format(kind, ready[lib_id])
                row = {'mesh': mesh, 'udim': udim, 'kind': kind}
                if data is None:
                    skipped.append(dict(row, reason=reason))
                    continue
                slot = o.get('slot', 1)
                slot = slot.get(mesh, 1) if isinstance(slot, dict) else slot
                name = map_name(mesh, kind, udim, slot, o.get('model', 'vpm'))
                target = os.path.join(out_dir, name)
                key = os.path.normcase(os.path.abspath(target))
                if key in seen:
                    skipped.append(dict(row, path=target, reason='same file requested twice (two meshes of one address with the same slot and UDIM: give options.slot {mesh: slot}): second skipped'))
                    continue
                seen.add(key)
                try:
                    path = edit.new_path(target, version=o.get('on_exists', 'refuse') == 'version', exists=exists)
                except FileExistsError:
                    skipped.append(dict(row, path=target, reason='exists, not overwritten (on_exists=refuse)'))
                    continue
                maps.append(dict(row, path=path, name=os.path.basename(path), data=data,
                                 sha256=tc.sha256(data)))
    return {'maps': maps, 'skipped': skipped}


def build_maps(udim_table, library, out_dir, options=None):
    """D + ERM + N maps of the VPM step of vpm.build, by names_core grammar, into NEW files of out_dir (K3).

    udim_table: {mesh name: {library_id: udim}} (matlib_core.renumber_dense per mesh); library: load_library().
    Returns {'maps': [{'mesh', 'udim', 'kind', 'path', 'sha256'}], 'skipped': [...]}."""
    edit = _edit()
    plan = plan_maps(udim_table, library, out_dir, options)
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for m in plan['maps']:
        edit.write_new(m['path'], m['data'])
        out.append({k: m[k] for k in ('mesh', 'udim', 'kind', 'path', 'sha256')})
    return {'maps': out, 'skipped': plan['skipped']}
