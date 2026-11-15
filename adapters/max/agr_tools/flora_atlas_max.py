"""new-case: AGR Tools 0.9 (#979) Flora and GroundEl atlases, 3ds Max side (branch B).

runtime.edits_090 calls `atlas_flora(ctx, mode, nodes, preview)` (atlas.flora, new files) and
`atlas_groundel(ctx, mode, nodes, preview)` (atlas.groundel, copies; the `groundel` profile of atlas.npm);
ctx: agr (runtime globals), core (atlas_core), edit (edit_core), emax (edit_max), options (dict of the preview).
No C# at runtime: pixels are read by the stdlib PNG reader (texqa_core) and written by the stdlib PNG writer, so
Max 2024 and 2026 write the same bytes (no Max bitmap save, no gamma, no OCIO). Non-PNG sources are read through
Max (openBitMap/getPixels) only where the profile allows them (GroundEl JPG); TGA and other formats are
`skipped` with the reason (VPM_to_NPM defect: a TGA crashed the whole run).

Both: preview reads the evaluated mesh (snapshot, so a primitive + Bend is read as shown), channel 1 and the
materials; nothing changes. apply re-checks the preview (edit_core.require_current), writes the atlas PNG(s) into
a NEW folder (never overwritten), then in ONE undo record makes export copies, collapses a COPY to Editable_Mesh,
writes the remapped channel 1 and an atlas material on the copy, reads the copy back and checks the sources are
unchanged. Any failure deletes the copies and the new folder's files of this run.

Options: atlas.flora — max_size 2048, pad 8, out_dir; atlas.groundel — profile 'groundel' (default, <= 512) or
'npm' (VPM_to_NPM: up to 2048, plugs allowed), size 512 / 2048, out_dir;
texel 'ground' (default) or 'none' (NPM only: preserve source pixels with uniform atlas scaling).
"""
import os

TOOL_FLORA = 'atlas.flora'
TOOL_GROUNDEL = 'atlas.groundel'
LAYER_FLORA = 'AGR_export_flora'
LAYER_GROUNDEL = 'AGR_export_groundel'
FLORA_KEYS = {'max_size', 'pad', 'out_dir'}
GROUNDEL_KEYS = {'profile', 'size', 'out_dir', 'texel'}
BLOCKING = {'map_missing', 'map_unreadable', 'groundel_alpha', 'atlas_overflow', 'atlas_refused', 'no_uv',
            'texture_unsupported', 'uv_tiling', 'opacity_mismatch'}


def _same_file(a, b):
    """Same path after normalisation (case, separators, relative parts)."""
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _rt():
    from pymxs import runtime
    return runtime


def _helpers(ctx):
    return ctx.agr._load_core('texqa_max.py', 'agr_tools_texqa_max')


def _tq(ctx):
    return ctx.core.texqa()


def _session_core():
    """Shared helpers (session_core.py next to this file), loaded by path like the other sibling cores."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('agr_tools_session_core', Path(__file__).with_name('session_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_in_session = _session_core().in_session


# ---- reading ------------------------------------------------------------------------------------------------
def read_uv_mesh(n):
    """Evaluated TriMesh (world space) with channel 1: {'vertices', 'faces', 'uvs', 'face_uvs', 'ids'}."""
    import math
    rt = _rt()
    mesh = rt.snapshotAsMesh(n)
    nv, nf = int(mesh.numverts), int(mesh.numfaces)
    if not nf:
        raise ValueError('empty mesh: ' + str(n.name))
    if not rt.meshop.getMapSupport(mesh, 1):
        raise LookupError('no UV channel 1: ' + str(n.name))
    verts = []
    for i in range(1, nv + 1):
        p = rt.getVert(mesh, i)
        verts.append((float(p.x), float(p.y), float(p.z)))
    nu = int(rt.meshop.getNumMapVerts(mesh, 1))
    uvs = []
    for i in range(1, nu + 1):
        p = rt.meshop.getMapVert(mesh, 1, i)
        uvs.append((float(p.x), float(p.y)))
    faces, fuv, ids = [], [], []
    for i in range(1, nf + 1):
        f = rt.getFace(mesh, i)
        faces.append([int(f.x) - 1, int(f.y) - 1, int(f.z) - 1])
        m = rt.meshop.getMapFace(mesh, 1, i)
        fuv.append([int(m.x) - 1, int(m.y) - 1, int(m.z) - 1])
        ids.append(int(rt.getFaceMatID(mesh, i)))
    for p in verts:
        if not all(math.isfinite(c) for c in p):
            raise ValueError('non-finite vertex: ' + str(n.name))
    for p in uvs:
        if not all(math.isfinite(c) for c in p):
            raise ValueError('non-finite UV: ' + str(n.name))
    return {'vertices': verts, 'faces': faces, 'uvs': uvs, 'face_uvs': fuv, 'ids': ids}


def face_materials(h, n, ids):
    """Material of every face (Multi/Sub by its listed ID; a single material for all), or ValueError."""
    subs = h.sub_materials(n)
    if not subs:
        raise ValueError('no material')
    if subs[0][0] is None:
        return [subs[0][1]] * len(ids)
    by_id = {mid: m for mid, m in subs}
    out = []
    for mid in ids:
        if mid not in by_id:
            raise ValueError('material ID {} has no sub-material'.format(mid))
        out.append(by_id[mid])
    return out


def maps_of(h, mat):
    """(diffuse path or None, opacity path or None) of a material."""
    diffuse = opacity = None
    for m in h.material_maps(mat):
        slot = m['slot'].lower()
        if diffuse is None and ('diffuse' in slot or 'base_color' in slot or 'basecolor' in slot
                                or 'base color' in slot):
            diffuse = m['path'] or None
        elif opacity is None and ('opacity' in slot or 'cutout' in slot):
            opacity = m['path'] or None
    return diffuse, opacity


def _max_picture(ctx, path):
    """Picture through Max (non-PNG sources only)."""
    rt = _rt()
    bm = rt.openBitMap(path)
    if bm is None:
        raise ValueError('Max cannot open the bitmap')
    try:
        w, h = int(bm.width), int(bm.height)

        def span(x, y, count, bm=bm):
            return rt.getPixels(bm, rt.point2(x, y), count)
        rows, arows = ctx.agr.bitmap_rows(w, h, span)
    finally:
        rt.close(bm)
    px = bytearray()
    for row, arow in zip(rows, arows):
        for (r, g, b), a in zip(row, arow):
            px += bytes((r, g, b, a))
    return _tq(ctx).Picture(w, h, 4, bytes(px), depth=8, alpha=any(a < 255 for row in arows for a in row))


def load_picture(ctx, path, allow_max=False):
    """(Picture, info) or (None, info with 'error'); info: file, format, w, h, depth, alpha_min, md5."""
    h = _helpers(ctx)
    tq = _tq(ctx)
    full = h.resolve(path) if path else None
    name = os.path.basename(str(path or ''))
    if full is None:
        return None, None
    data = open(full, 'rb').read()
    fmt = tq.sniff(data)
    info = {'file': name, 'path': full, 'format': fmt, 'md5': h.md5(data), 'w': None, 'h': None, 'depth': None,
            'alpha_min': None}
    try:
        if fmt == 'png':
            pic = tq.read_png(data)
        elif fmt == 'jpeg' and allow_max:
            pic = _max_picture(ctx, full)
        else:
            info['error'] = '{} source is not read ({}); save it as PNG'.format(fmt.upper(), name)
            info['unsupported'] = True
            return None, info
    except (ValueError, IndexError, KeyError) as exc:
        info['error'] = str(exc)
        return None, info
    alpha = pic.alpha()
    info.update(w=pic.w, h=pic.h, depth=pic.depth, alpha_min=min(alpha) if alpha is not None else None)
    return pic, info


def _new_folder(ctx, options, label):
    rt = _rt()
    root = options.get('out_dir') or os.environ.get('AGR_TEST_OUTPUT')
    if not root:
        base = str(rt.maxFilePath or '')
        root = base if base and os.path.isdir(base) else str(rt.getDir(rt.name('temp')))
    folder = ctx.edit.new_path(os.path.join(root, label), version=True)
    os.makedirs(folder)
    return folder


def _write(ctx, folder, name, data):
    path = ctx.edit.new_path(os.path.join(folder, name))
    ctx.edit.write_new(path, data)
    return path


def _bitmap_material(name, diffuse, opacity=None):
    rt = _rt()
    mat = rt.Standardmaterial()
    mat.name = name
    mat.diffuse = rt.color(255, 255, 255)
    tex = rt.Bitmaptexture()
    tex.filename = diffuse
    mat.diffuseMap = tex
    if opacity:
        op = rt.Bitmaptexture()
        op.filename = opacity
        mat.opacityMap = op
    return mat


def _material_state(n):
    rt = _rt()
    return None if n.material is None else [str(rt.classOf(n.material)), str(n.material.name)]


def _source_state(ctx, n, mesh):
    rt = _rt()
    return {'handle': int(rt.getHandleByAnim(n)), 'name': str(n.name), 'mesh': mesh,
            'material': _material_state(n), 'snapshot': ctx.emax.snapshot([n])[0],
            'stack': [str(rt.classOf(n.baseObject))] + [str(rt.classOf(m)) for m in n.modifiers]}


def _copy_with_uv(ctx, n, uvs, face_uvs, mesh, name_suffix, layer):
    """Export copy (collapsed to Editable_Mesh), channel 1 written and read back."""
    rt = _rt()
    c = rt.copy(n)
    c.name = rt.uniqueName(str(n.name) + name_suffix)
    rt.convertToMesh(c)
    back_mesh = read_uv_mesh(c)
    if back_mesh['faces'] != mesh['faces']:
        rt.delete(c)
        raise RuntimeError('export copy topology differs from the evaluated source: ' + str(n.name))
    ctx.agr._write_channel(c, uvs, face_uvs)
    back = ctx.agr._read_channel(c)
    ctx.agr.assert_uv_close(back['uvs'], uvs)
    if back['face_uvs'] != [list(f) for f in face_uvs]:
        raise RuntimeError('copy readback differs from the written UVs: ' + str(c.name))
    layer_obj = rt.LayerManager.getLayerFromName(layer)
    if layer_obj is None or layer_obj == rt.undefined:
        layer_obj = rt.LayerManager.newLayerFromName(layer)
    layer_obj.addNode(c)
    return c


# ---- atlas.groundel -------------------------------------------------------------------------------------------
def _groundel_options(ctx, mode, preview):
    if mode == 'apply':
        return dict(preview['plan']['options'])
    opts = dict(ctx.options or {})
    unknown = set(opts) - GROUNDEL_KEYS
    if unknown:
        raise ValueError('unknown atlas.groundel options: ' + ', '.join(sorted(unknown)))
    profile = opts.get('profile', 'groundel')
    if profile not in ('groundel', 'npm'):
        raise ValueError("options.profile must be 'groundel' or 'npm'")
    size = opts.get('size', ctx.core.GROUNDEL_MAX if profile == 'groundel' else 2048)
    if size not in ctx.core.PROFILE_SIZES[profile]:
        raise ValueError('options.size must be one of {}'.format(ctx.core.PROFILE_SIZES[profile]))
    out_dir = opts.get('out_dir')
    if out_dir is not None and (not isinstance(out_dir, str) or not out_dir):
        raise ValueError('options.out_dir must be a folder path')
    # #1024 (Artem 06.11): in NPM the texel matters only for Ground; MAF/Flora atlases keep their source pixels
    # (uniform scale to the atlas size, flat colours as plug cells) -> atlas_core.pack mode 'oks'.
    texel = opts.get('texel', 'ground')
    if texel not in ('ground', 'none'):
        raise ValueError("options.texel must be 'ground' or 'none'")
    if texel == 'none' and profile != 'npm':
        raise ValueError("options.texel 'none' needs profile 'npm' (GroundEl keeps the Ground texel)")
    return {'profile': profile, 'size': size, 'out_dir': out_dir, 'texel': texel}


def _groundel_scan(ctx, nodes, options):
    rt = _rt()
    h, core = _helpers(ctx), ctx.core
    unit = h.unit_m()
    objs, state, specs = [], [], {}
    for n in nodes:
        o = {'node': n, 'key': h.handle(n), 'name': str(n.name), 'findings': [], 'warnings': [], 'maps': [],
             'mesh': None, 'mats': None}
        objs.append(o)
        if rt.superClassOf(n) != rt.GeometryClass:
            o['findings'].append(('no_uv', 'not geometry'))
            state.append({'name': o['name'], 'skip': 'not geometry'})
            continue
        try:
            mesh = read_uv_mesh(n)
            mats = face_materials(h, n, mesh['ids'])
        except LookupError as exc:
            o['findings'].append(('no_uv', str(exc)))
            state.append({'name': o['name'], 'skip': str(exc)})
            continue
        except ValueError as exc:
            o['findings'].append(('map_missing', str(exc)))
            state.append({'name': o['name'], 'skip': str(exc)})
            continue
        o['mesh'] = mesh
        names = []
        seen = {}
        for m in mats:
            key = '{}|{}'.format(o['name'], str(m.name))
            names.append(key)
            if key in seen:
                continue
            seen[key] = m
            diffuse, _ = maps_of(h, m)
            pic, info = load_picture(ctx, diffuse, allow_max=True)
            row = {'material': str(m.name), 'file': diffuse, 'info': info}
            if pic is None and options['profile'] == 'npm' and not diffuse:
                c = m.diffuse
                specs[key] = {'color': (int(round(float(c.r))), int(round(float(c.g))), int(round(float(c.b)))),
                              'dissolve': 1.0}
                row['plug'] = True
            elif pic is None:
                if info is not None and info.get('unsupported') and options['profile'] == 'npm':
                    o['skipped'] = o.get('skipped', []) + [(str(m.name), info['error'])]
                    o['findings'].append(('texture_unsupported', info['error']))
                else:
                    f, _w = core.groundel_map_rule(info)   # None -> map_missing, error -> map_unreadable
                    o['findings'].extend(f)
            else:
                if options['profile'] == 'groundel':
                    f, w = core.groundel_map_rule(info)
                    o['findings'].extend(f)
                    o['warnings'].extend(w)
                rows, arows = core.rows_rgb(pic)
                spec = {'rgb': rows, 'dissolve': 1.0}
                if options['profile'] == 'npm' and arows is not None and any(a < 255 for r in arows for a in r):
                    spec['alpha'] = arows
                specs[key] = spec
            o['maps'].append(row)
        o['mats'] = names
        state.append(_source_state(ctx, n, mesh))
        state[-1]['maps'] = [[r['material'], r['file'], (r['info'] or {}).get('md5')] for r in o['maps']]
    return objs, state, specs, unit


def atlas_groundel(ctx, mode, nodes, preview):
    rt = _rt()
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    h = _helpers(ctx)
    options = _groundel_options(ctx, mode, preview)
    nodes = h.target_nodes(nodes)
    objs, state, specs, unit = _groundel_scan(ctx, nodes, options)
    blocked = any(c in BLOCKING for o in objs for c, _ in o['findings'])
    laid, calc = None, None
    if not blocked:
        verts, uvs, faces, fuv, fmats, owner = [], [], [], [], [], []
        for o in objs:
            m = o['mesh']
            vb, ub = len(verts), len(uvs)
            verts += m['vertices']
            uvs += m['uvs']
            faces += [[i + vb for i in f] for f in m['faces']]
            fuv += [[i + ub for i in f] for f in m['face_uvs']]
            fmats += o['mats']
            owner += [o['key']] * len(m['faces'])
        try:
            laid = core.pack(verts, uvs, faces, fuv, fmats, specs,
                             mode='oks' if options.get('texel') == 'none' else 'ground', size=options['size'], pad=8,
                             unit_m=unit, profile=options['profile'], shrink=True)
        except core.AtlasFitError as exc:
            calc = exc.calc
            for o in objs:
                o['findings'].append(('atlas_overflow', '{}: needs {} px2 of cells at the lowest texel {} px/m, the '
                                                        '{} atlas holds {} px2'.format(
                                                            exc, calc['cells_area_px2'], calc['lowest_texel_px_per_m'],
                                                            calc['atlas_px'], calc['atlas_area_px2'])))
        except core.AtlasError as exc:
            for o in objs:
                o['findings'].append(('atlas_refused', str(exc)))
    entries = [edit.entry(o['key'], o['name'], [edit.finding(c, (), d) for c, d in o['findings']]) for o in objs]
    skipped = [edit.skipped(item, reason) for o in objs for item, reason in o.get('skipped', [])]
    plan_extra = {'options': options, 'unit_m': unit, 'issue': '#979', 'layer': LAYER_GROUNDEL,
                  'warnings': [w for o in objs for w in o['warnings']],
                  'maps': [{'object': o['name'], 'material': r['material'], 'file': os.path.basename(str(r['file'] or '')),
                            'size': None if not r['info'] else [r['info']['w'], r['info']['h']],
                            'plug': bool(r.get('plug'))} for o in objs for r in o['maps']],
                  'calc': calc}
    done = []
    if laid is not None:
        plan_extra.update(atlas={'size': laid['size'], 'cells': laid['cells'], 'texel_px_per_m': laid['texel_px_per_m'],
                                 'tiles': laid['tiles']})
        done = [{'object': o['name'], 'faces': len(o['mesh']['faces']), 'atlas': laid['size']} for o in objs]
    if mode == 'preview':
        return edit.report(TOOL_GROUNDEL, 'preview', entries, done, skipped, (), state_hash=edit.fingerprint(state),
                           extra=plan_extra)
    edit.require_current(preview, state)
    if edit.fingerprint([preview['plan'].get('atlas'), preview['plan']['done']]) != edit.fingerprint(
            [plan_extra.get('atlas'), done]):
        raise edit.StalePreview('the atlas differs from the preview; run preview again')
    if laid is None or any(c in BLOCKING for o in objs for c, _ in o['findings']):
        raise ValueError('atlas.groundel is blocked by the findings of the preview (missing/unreadable map, alpha, '
                         'overflow): no atlas and no copy are written')
    folder = _new_folder(ctx, options, 'AGR_groundel_atlas')
    diffuse_png, opacity_png = core.atlas_png(laid)
    files, copies, objects, applied = [], [], [], []
    try:
        diffuse = _write(ctx, folder, 'T_GroundEl_atlas_d_1.png', diffuse_png)
        files.append(diffuse)
        opacity = None
        if opacity_png is not None:
            opacity = _write(ctx, folder, 'T_GroundEl_atlas_o_1.png', opacity_png)
            files.append(opacity)

        def body():
            base = 0
            ubase = 0
            mat = _bitmap_material('M_GroundEl_atlas_1', diffuse, opacity)
            for o in objs:
                nf = len(o['mesh']['faces'])
                fl = laid['face_uvs'][base:base + nf]
                used = sorted({i for f in fl for i in f})
                local = {g: k for k, g in enumerate(used)}
                uvs = [laid['uvs'][g] for g in used]
                fuv = [[local[g] for g in f] for f in fl]
                c = _copy_with_uv(ctx, o['node'], uvs, fuv, o['mesh'], '_AGR_groundel_', LAYER_GROUNDEL)
                copies.append(c)
                c.material = mat
                objects.append(edit.entry(h.handle(c), str(c.name), []))
                applied.append({'object': str(c.name), 'source': o['name'], 'faces': nf})
                base += nf
                ubase += len(used)
            after = [_source_state(ctx, o['node'], read_uv_mesh(o['node'])) for o in objs]
            if edit.fingerprint([{k: v for k, v in a.items()} for a in after]) != edit.fingerprint(
                    [{k: v for k, v in s.items() if k != 'maps'} for s in state]):
                raise RuntimeError('working objects changed during apply')
        _in_session(emax, TOOL_GROUNDEL, body)
    except Exception:
        alive = [c for c in copies if rt.isValidNode(c)]
        if alive:
            rt.delete(alive)
        for f in files:
            if os.path.isfile(f):
                os.remove(f)
        raise
    pic = _tq(ctx).read_png(open(diffuse, 'rb').read())
    written = {'diffuse': diffuse, 'opacity': opacity, 'size': [pic.w, pic.h], 'color_type': pic.color_type,
               'pixel_md5': _tq(ctx).pixel_md5(pic)}
    if pic.color_type != 2 or pic.w > options['size']:
        raise RuntimeError('atlas file is not a 24-bit RGB PNG within the size: ' + str(written))
    extra = dict(plan_extra, copies=[str(c.name) for c in copies], written=written, folder=folder)
    return edit.report(TOOL_GROUNDEL, 'apply', objects, applied, skipped, (), extra=extra)


# ---- atlas.flora --------------------------------------------------------------------------------------------
def _flora_options(ctx, mode, preview):
    if mode == 'apply':
        return dict(preview['plan']['options'])
    opts = dict(ctx.options or {})
    unknown = set(opts) - FLORA_KEYS
    if unknown:
        raise ValueError('unknown atlas.flora options: ' + ', '.join(sorted(unknown)))
    out = {'max_size': opts.get('max_size', 2048), 'pad': opts.get('pad', ctx.core.PADDING_MIN_PX),
           'out_dir': opts.get('out_dir')}
    if out['max_size'] not in ctx.core.FLORA_SIZES:
        raise ValueError('options.max_size must be one of {}'.format(ctx.core.FLORA_SIZES))
    if type(out['pad']) is not int or out['pad'] < ctx.core.PADDING_MIN_PX:
        raise ValueError('options.pad must be an integer >= {}'.format(ctx.core.PADDING_MIN_PX))
    return out


def _instance_key(n):
    rt = _rt()
    return (int(rt.getHandleByAnim(n.baseObject)),) + tuple(int(rt.getHandleByAnim(m)) for m in n.modifiers)


def atlas_flora(ctx, mode, nodes, preview):
    rt = _rt()
    edit, core, emax = ctx.edit, ctx.core, ctx.emax
    h = _helpers(ctx)
    tq = _tq(ctx)
    options = _flora_options(ctx, mode, preview)
    nodes = h.target_nodes(nodes)
    groups = {}
    for n in nodes:
        if rt.superClassOf(n) == rt.GeometryClass:
            groups.setdefault(_instance_key(n), []).append(n)
    objs, state, textures, uses, tex_of = [], [], {}, {}, {}
    for n in nodes:
        o = {'node': n, 'key': h.handle(n), 'name': str(n.name), 'findings': [], 'mesh': None, 'tex': None}
        objs.append(o)
        if rt.superClassOf(n) != rt.GeometryClass:
            o['findings'].append(('no_uv', 'not geometry'))
            continue
        group = groups[_instance_key(n)]
        o['rep'] = group[0]
        if group[0] is not n:
            o['instance_of'] = str(group[0].name)
        try:
            mesh = read_uv_mesh(n)
            mats = face_materials(h, n, mesh['ids'])
        except LookupError as exc:
            o['findings'].append(('no_uv', str(exc)))
            continue
        except ValueError as exc:
            o['findings'].append(('map_missing', str(exc)))
            continue
        o['mesh'] = mesh
        face_tex = []
        for m in mats:
            diffuse, opacity = maps_of(h, m)
            full = h.resolve(diffuse) if diffuse else None
            if full is None:
                o['findings'].append(('map_missing', 'material {}: diffuse map {} not found'.format(m.name, diffuse)))
                face_tex.append(None)
                continue
            key = os.path.normcase(os.path.abspath(full))
            if key not in textures:
                pic, info = load_picture(ctx, full)
                if pic is None:
                    o['findings'].append(('texture_unsupported', info['error']))
                    textures[key] = None
                else:
                    alpha = pic.alpha()
                    if alpha is not None and min(alpha) == 255:
                        alpha = None
                    textures[key] = {'w': pic.w, 'h': pic.h, 'rgb': pic.rgb(), 'alpha': alpha, 'file': info['file'],
                                     'md5': info['md5'], 'opacity': None}
                    if opacity:
                        op, oinfo = load_picture(ctx, opacity)
                        if op is None or (op.w, op.h) != (pic.w, pic.h):
                            o['findings'].append(('opacity_mismatch', 'opacity {} must be a PNG of the diffuse size'
                                                  .format(opacity)))
                        elif _same_file(oinfo['path'], info['path']):
                            # #1024: A101 Flora points the opacity slot at the diffuse PNG itself: its own alpha.
                            # #1382: decided before the alpha test; an opaque or RGB diffuse keeps alpha None, so
                            # it never falls through to channel(0) (its red channel as a cutout).
                            pass
                        elif alpha is not None:
                            o['findings'].append(('opacity_mismatch', 'both diffuse alpha and an opacity map'))
                        else:
                            textures[key]['alpha'] = op.channel(0)
                            textures[key]['opacity'] = oinfo['file']
                            textures[key]['opacity_md5'] = oinfo['md5']
            elif textures[key] is None:
                o['findings'].append(('texture_unsupported', 'diffuse {} is not a readable PNG'.format(full)))
            face_tex.append(key if textures.get(key) else None)
        o['tex'] = face_tex
        if group[0] is n:
            for f, key in enumerate(face_tex):
                if key is None:
                    continue
                uses.setdefault(key, []).extend(mesh['uvs'][i] for i in mesh['face_uvs'][f])
        state.append(dict(_source_state(ctx, n, mesh), textures=sorted({textures[k]['md5'] for k in face_tex
                                                                         if k and textures.get(k)})))
    plan = None
    if not any(c in BLOCKING for o in objs for c, _ in o['findings']):
        if not uses:
            raise ValueError('no flora texture on the selected objects')
        try:
            plan = core.flora_plan({k: textures[k] for k in uses}, uses, options['max_size'], options['pad'])
        except core.AtlasError as exc:
            code = 'uv_tiling' if 'tiling' in str(exc) else 'atlas_refused'
            for o in objs:
                o['findings'].append((code, str(exc)))
    entries = [edit.entry(o['key'], o['name'], [edit.finding(c, (), d) for c, d in o['findings']]) for o in objs]
    extra = {'options': options, 'issue': '#979', 'layer': LAYER_FLORA,
             'instances': [{'object': o['name'], 'instance_of': o['instance_of']} for o in objs if o.get('instance_of')]}
    done = []
    if plan is not None:
        names = {k: textures[k]['file'] for k in uses}
        extra['atlas'] = {'size': plan['size'], 'fill': plan['fill'], 'scale': plan['layout']['scale'],
                          'tiles': [dict(t, texture=names[t['texture']]) for t in plan['tiles']],
                          'opacity': any(textures[k]['alpha'] is not None for k in uses)}
        done = [{'object': o['name'], 'faces': len(o['mesh']['faces']), 'instance_of': o.get('instance_of')}
                for o in objs if o['mesh'] is not None]
    if mode == 'preview':
        return edit.report(TOOL_FLORA, 'preview', entries, done, (), (), state_hash=edit.fingerprint(state),
                           extra=extra)
    edit.require_current(preview, state)
    if edit.fingerprint([preview['plan'].get('atlas'), preview['plan']['done']]) != edit.fingerprint(
            [extra.get('atlas'), done]):
        raise edit.StalePreview('the atlas differs from the preview; run preview again')
    if plan is None or any(o['findings'] for o in objs):
        raise ValueError('atlas.flora is blocked by the findings of the preview: no atlas and no copy are written')
    size, layout = plan['size'], plan['layout']
    tex_in = {k: dict(textures[k], crop=plan['crops'][k]) for k in uses}
    img = core.flora_raster(tex_in, layout, options['pad'])
    folder = _new_folder(ctx, options, 'AGR_flora_atlas')
    files, copies, objects, applied = [], [], [], []
    try:
        diffuse = _write(ctx, folder, 'T_Flora_atlas_d_1.png', tq.write_png(size, size, img['rgb'], 3))
        files.append(diffuse)
        opacity = None
        if img['alpha'] is not None:
            opacity = _write(ctx, folder, 'T_Flora_atlas_o_1.png', tq.write_png(size, size, img['alpha'], 1))
            files.append(opacity)

        def remap(o):
            mesh = o['mesh']
            uvs, fuv = [], []
            for f, key in enumerate(o['tex']):
                t = textures[key]
                row = []
                for i in mesh['face_uvs'][f]:
                    u, v = mesh['uvs'][i]
                    uvs.append(core.flora_uv(u, v, t['w'], t['h'], plan['crops'][key], layout['cells'][key],
                                             size, layout['scale']))
                    row.append(len(uvs) - 1)
                fuv.append(row)
            return uvs, fuv

        def body():
            mat = _bitmap_material('M_Flora_atlas_1', diffuse, opacity)
            reps = {}
            for o in objs:
                if o.get('instance_of') is None:
                    uvs, fuv = remap(o)
                    c = _copy_with_uv(ctx, o['node'], uvs, fuv, o['mesh'], '_AGR_flora_', LAYER_FLORA)
                    reps[o['name']] = c
                else:
                    c = rt.instance(reps[o['instance_of']])
                    c.name = rt.uniqueName(o['name'] + '_AGR_flora_')
                    c.transform = o['node'].transform
                    rt.LayerManager.getLayerFromName(LAYER_FLORA).addNode(c)
                copies.append(c)
                c.material = mat
            for o, c in zip(objs, copies):
                back = read_uv_mesh(c)
                inside = 0
                for f, key in enumerate(o['tex']):
                    x, y, w, hh = layout['cells'][key]
                    ok = True
                    for i in back['face_uvs'][f]:
                        u, v = back['uvs'][i]
                        px, py = u * size, (1.0 - v) * size
                        if not (x - 1e-3 <= px <= x + w + 1e-3 and y - 1e-3 <= py <= y + hh + 1e-3):
                            ok = False
                    inside += ok
                nf = len(o['tex'])
                findings = [] if inside == nf else [edit.finding('outside_tile', (), '{}/{} faces in their tile'
                                                                 .format(inside, nf))]
                objects.append(edit.entry(h.handle(c), str(c.name), findings))
                applied.append({'object': str(c.name), 'source': o['name'], 'faces_in_tile': inside, 'faces': nf,
                                'instance_of': o.get('instance_of')})
            after = []
            for o in objs:
                s = dict(_source_state(ctx, o['node'], read_uv_mesh(o['node'])))
                s['textures'] = sorted({textures[k]['md5'] for k in o['tex'] if k})
                after.append(s)
            if edit.fingerprint(after) != edit.fingerprint(state):
                raise RuntimeError('working objects changed during apply')
        _in_session(emax, TOOL_FLORA, body)
    except Exception:
        alive = [c for c in copies if rt.isValidNode(c)]
        if alive:
            rt.delete(alive)
        for f in files:
            if os.path.isfile(f):
                os.remove(f)
        raise
    dpic = tq.read_png(open(diffuse, 'rb').read())
    written = {'diffuse': diffuse, 'diffuse_color_type': dpic.color_type, 'diffuse_pixel_md5': tq.pixel_md5(dpic),
               'opacity': opacity, 'size': size, 'fill': plan['fill']}
    if opacity:
        opic = tq.read_png(open(opacity, 'rb').read())
        written.update(opacity_color_type=opic.color_type, opacity_pixel_md5=tq.pixel_md5(opic))
    extra = dict(extra, copies=[str(c.name) for c in copies], written=written, folder=folder)
    return edit.report(TOOL_FLORA, 'apply', objects, applied, (), (), extra=extra)
