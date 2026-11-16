"""new-case: AGR Tools 1.0 (#1024) NPM -> VPM logic, stdlib only; owned by branch Q (improve/issue-1024-npm-to-vpm).

Pure logic for `npm_to_vpm` (npm.to_vpm, plan mode copy, station 1.0.24); no pymxs, the core never takes a host
object. Method of lab L11 (docs/experiments/npm.to_vpm.md, verdict `new`):

* main path - the correspondence table of npm.build (branch P, atlas_core.correspondence_table, written as
  `npm_table.json` next to the atlas): every face goes back by its row, vpm_uv = (atlas_uv - shift) / scale
  (atlas_core.from_atlas), so the VPM UV, its UDIM (from the VPM table / passport, not from the UV centre), the
  texel and the library material come back exactly; body and glass return as SEPARATE meshes, each numbered from
  1001 (owner answer V9, 06.11.2026);
* without a table (`atlas.unatlas`) - one region per library ID, crop and UV by ONE formula in whole atlas pixels
  (`region_box` / `region_uv`), the crop keeps its native size (no 2048 stretch), slot = ID, UDIM = 1000 + ID; a
  region outside the first atlas tile is shifted back when it lies inside one tile, else an explicit finding;
* windows - planes of the window IDs: elements -> frame (normal by area, up = world Z) -> width / height -> library
  type by size per axis in METRES (tolerance `window_tol_m`), the 90 deg variant, `none` / `ambiguous` reported ->
  instance of the generated window (windowgen_core of branch J); the planes go to the hidden layer `_npm_src`.

Not repeated from GeoAGR UnAtlas (GeoAGR.ms:29390-29909): UDIM by the stack number instead of the ID (:29864-29866),
every crop stretched to 2048 (:29835), crop and UV by different formulas (truncated integer crop + 5 % padding
:29816-29819 vs float UV :29870-29882), a stack outside the first UDIM skipped with a Listener line (:29888), an
existing crop overwritten.

Mesh: {'verts': [[x, y, z]] world metres, 'local': [[x, y, z]] object space (system units), 'tris', 'mat_ids',
'uvs': [[u, v]] | None, 'uv_tris': [[a, b, c]] | None}.
"""
import importlib.util
import math
import os
import struct
import sys
import zlib

TOOL = 'npm.to_vpm'
MODES = ('auto', 'table', 'regions')
OPTION_KEYS = {'mode', 'table', 'window_ids', 'window_types', 'window_tol_m', 'library', 'statuses', 'recess_m',
               'name', 'out_dir', 'crop_pad_px', 'glass_ids'}
DEFAULTS = {'mode': 'auto', 'table': None, 'window_ids': [], 'window_types': None, 'window_tol_m': 0.05,
            'library': None, 'statuses': ['confirmed', 'unconfirmed'], 'recess_m': 0.0, 'name': None,
            'out_dir': None, 'crop_pad_px': 0, 'glass_ids': []}
SRC_LAYER = '_npm_src'
LAYER = 'AGR_vpm'
TABLE_FILE = 'npm_table.json'
UV_TOL = 1e-6           # restored UV inside its UDIM tile
# 1.0.1 (KPP1 e2e 20261106-075555-c179f5f0): Max keeps channel 1 of the NPM copy in float32. An atlas UV in [0, 1]
# carries up to one float32 ulp there (2**-24); (atlas_uv - shift) / scale multiplies it by 1 / scale, ~64 for a plug
# cell of 8 px in a 512 atlas -> ~2e-6 VPM-UV units on the vertices that lie ON a tile line after the grid cut of
# vpm.build. The tile test allows that storage error per row (still far below a texel: 2e-6 of a 4096 px tile).
F32_ULP_UNIT = 2.0 ** -24
REGION_TOL_PX = 0.5     # atlas UV inside the cell of its row (half an atlas pixel)
PLANAR_TOL_M = 0.01     # a window plane deviating more is not a plane
TIE_M = 0.001           # two types closer than this are equally good -> ambiguous
HORIZONTAL_COS = 0.95   # |normal . Z| above this: the plane has no up direction
# Findings that stop the apply (fail-closed: nothing is written). Window findings (`window_no_type`,
# `window_ambiguous`, `window_frame`) are reported; the plane still goes to `_npm_src`, no instance is made.
BLOCKING = ('no_uv', 'table_no_row', 'table_region', 'udim_mismatch', 'id_range', 'region_straddle', 'atlas_missing',
            'table_invalid')
WINDOW_CODES = ('window_no_type', 'window_ambiguous', 'window_frame')


def _sibling(name, alias):
    mod = sys.modules.get(alias)
    if mod is not None and getattr(mod, '__file__', None):
        return mod
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


_udimtile = _sibling('udimtile_core.py', 'agr_tools_udimtile_core_npm2vpm')


def atlas():
    return _sibling('atlas_core.py', 'agr_tools_atlas_core_q')


def winplace():
    return _sibling('winplace_core.py', 'agr_tools_winplace_core_q')


# ---- options ---------------------------------------------------------------------------------------------------
def _ids(v, what):
    if not isinstance(v, list) or any(type(i) is not int or i <= 0 for i in v):
        raise ValueError('options.{} must be a list of library ids (integers > 0)'.format(what))
    return sorted(set(v))


def options(opts):
    """Validated options with the defaults of #1024 §1.0.24 and lab L11 (JSON-ready)."""
    opts = dict(opts or {})
    unknown = set(opts) - OPTION_KEYS
    if unknown:
        raise ValueError('unknown npm.to_vpm options: ' + ', '.join(sorted(unknown)))
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    out.update(opts)
    if out['mode'] not in MODES:
        raise ValueError('options.mode must be one of {}'.format(list(MODES)))
    out['window_ids'] = _ids(out['window_ids'], 'window_ids')
    out['glass_ids'] = _ids(out['glass_ids'], 'glass_ids')
    t = out['window_tol_m']
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or not 0 < t <= 0.5:
        raise ValueError('options.window_tol_m must be a number of metres in (0, 0.5]')
    r = out['recess_m']
    if isinstance(r, bool) or not isinstance(r, (int, float)) or not math.isfinite(r):
        raise ValueError('options.recess_m must be a finite number of metres')
    p = out['crop_pad_px']
    if type(p) is not int or not 0 <= p <= 64:
        raise ValueError('options.crop_pad_px must be an integer 0..64')
    wt = out['window_types']
    if wt is not None and (not isinstance(wt, list) or not wt or not all(isinstance(x, str) and x for x in wt)):
        raise ValueError('options.window_types must be a non-empty list of library type ids or null')
    st = out['statuses']
    if not isinstance(st, list) or not st or not all(s in ('confirmed', 'unconfirmed') for s in st):
        raise ValueError('options.statuses must be a non-empty list of confirmed / unconfirmed')
    for key in ('library', 'name', 'out_dir'):
        if out[key] is not None and (not isinstance(out[key], str) or not out[key].strip()):
            raise ValueError('options.{} must be a non-empty string'.format(key))
    tb = out['table']
    if tb is not None and not isinstance(tb, (str, dict, list)):
        raise ValueError('options.table must be a path to npm_table.json, its JSON object or its row list')
    if out['mode'] == 'regions' and tb is not None:
        raise ValueError('options.table is given but options.mode is regions')
    return out


# ---- correspondence table --------------------------------------------------------------------------------------
def _pair(v):
    return isinstance(v, list) and len(v) == 2 and all(
        not isinstance(c, bool) and isinstance(c, (int, float)) and math.isfinite(c) for c in v)


def table_rows(doc):
    """Validated rows of a correspondence table: the npm_table.json object of npm.build ({'table': rows, ...}) or the
    row list itself. ValueError names the bad row (the table is never guessed)."""
    rows = doc.get('table') if isinstance(doc, dict) else doc
    if not isinstance(rows, list) or not rows:
        raise ValueError('correspondence table: no rows (npm_table.json of npm.build)')
    out, keys = [], set()
    for i, r in enumerate(rows):
        where = 'correspondence table row {}'.format(i + 1)
        if not isinstance(r, dict):
            raise ValueError(where + ': not an object')
        lid = r.get('library_id')
        if type(lid) is not int or lid <= 0:
            raise ValueError(where + ': library_id must be an integer > 0')
        if not _pair(r.get('scale')) or not _pair(r.get('shift')) or min(abs(c) for c in r['scale']) <= 1e-12:
            raise ValueError(where + ': scale / shift must be two finite numbers (scale != 0)')
        reg = r.get('region')
        if not isinstance(reg, list) or len(reg) != 4 or not _pair(reg[:2]) or not _pair(reg[2:]) \
                or reg[2] < reg[0] or reg[3] < reg[1]:
            raise ValueError(where + ': region must be [u0, v0, u1, v1]')
        udim = r.get('udim')
        if udim is not None and (type(udim) is not int or not 1001 <= udim <= 1100):
            raise ValueError(where + ': udim must be 1001..1100 or null')
        part = r.get('part') or 'body'
        if part not in ('body', 'glass'):
            raise ValueError(where + ': part must be body or glass')
        key = str(r.get('key') or lid)
        if key in keys:
            raise ValueError(where + ': duplicate key ' + key)
        keys.add(key)
        size = r.get('atlas_px')
        out.append({'library_id': lid, 'key': key, 'udim': udim, 'region': [float(c) for c in reg],
                    'scale': [float(c) for c in r['scale']], 'shift': [float(c) for c in r['shift']], 'part': part,
                    'kind': r.get('kind') or 'texture', 'material': r.get('material'), 'map': r.get('map'),
                    'atlas_px': size if type(size) is int and size > 0 else None})
    parts = {}
    for r in out:
        parts.setdefault(r['library_id'], set()).add(r['part'])
    both = sorted(k for k, v in parts.items() if len(v) > 1)
    if both:
        raise ValueError('correspondence table: library ids {} are on body and glass'.format(both))
    return out


def tile_origin(udim):
    return _udimtile.tile_origin(udim)


def in_tile(pts, udim, tol=UV_TOL):
    u0, v0 = tile_origin(udim)
    return all(u0 - tol <= u <= u0 + 1 + tol and v0 - tol <= v <= v0 + 1 + tol for u, v in pts)


def tile_excess(pts, udim):
    """Largest distance (VPM-UV units) of the points outside the tile `udim`, 0.0 inside."""
    u0, v0 = tile_origin(udim)
    return max([0.0] + [max(u0 - u, u - u0 - 1, v0 - v, v - v0 - 1, 0.0) for u, v in pts])


def row_tol(row):
    """Tile tolerance of a correspondence row: UV_TOL + one float32 ulp of the atlas UV mapped back by 1 / scale."""
    return UV_TOL + F32_ULP_UNIT / min(abs(row['scale'][0]), abs(row['scale'][1]))


def _row_of(rows_by_id, mid, pts, size):
    """(row, None) of a face by its library id and the cell region holding its atlas UV centroid, else (None, why)."""
    cand = rows_by_id.get(mid)
    if not cand:
        return None, 'no_row'
    cu = sum(p[0] for p in pts) / len(pts)
    cv = sum(p[1] for p in pts) / len(pts)
    tol = REGION_TOL_PX / float(size or 2048)
    hit = [r for r in cand if r['region'][0] - tol <= cu <= r['region'][2] + tol
           and r['region'][1] - tol <= cv <= r['region'][3] + tol]
    if len(hit) == 1:
        return hit[0], None
    return None, ('outside' if not hit else 'several')


def plan_table(mesh, rows, skip=()):
    """Faces back by the table: {'findings': [(code, faces 0-based, detail)], 'parts': {part: out mesh}}.

    out mesh: {'faces': [source faces], 'verts': [local], 'tris', 'mat_ids', 'uvs', 'uv_tris', 'rows': {library
    id: row}}; faces in `skip` (window planes) are left out."""
    findings = []
    if mesh.get('uv_tris') is None:
        return {'findings': [('no_uv', list(range(len(mesh['tris']))), 'no UV channel 1 on the NPM')], 'parts': {}}
    size = next((r['atlas_px'] for r in rows if r['atlas_px']), None)
    by_id = {}
    for r in rows:
        by_id.setdefault(r['library_id'], []).append(r)
    skip = set(skip)
    no_row, outside, wrong_udim, excess = {}, [], {}, {}
    face_row = {}
    for f, mid in enumerate(mesh['mat_ids']):
        if f in skip:
            continue
        pts = [mesh['uvs'][i] for i in mesh['uv_tris'][f]]
        row, why = _row_of(by_id, mid, pts, size)
        if row is None:
            if why == 'no_row':
                no_row.setdefault(mid, []).append(f)
            else:
                outside.append(f)
            continue
        face_row[f] = row
    for mid, faces in sorted(no_row.items()):
        findings.append(('table_no_row', faces, 'library id {}: {} face(s), no row in the correspondence table'.format(
            mid, len(faces))))
    if outside:
        findings.append(('table_region', outside, '{} face(s): the atlas UV is outside every cell of its id '
                                                  '(or in several)'.format(len(outside))))
    parts = {}
    fa = atlas().from_atlas
    for f in sorted(face_row):
        row = face_row[f]
        part = parts.setdefault(row['part'], {'faces': [], 'vmap': {}, 'umap': {}, 'verts': [], 'tris': [],
                                              'mat_ids': [], 'uvs': [], 'uv_tris': [], 'rows': {}})
        tri, utri, back = [], [], []
        for vi in mesh['tris'][f]:
            if vi not in part['vmap']:
                part['vmap'][vi] = len(part['verts'])
                part['verts'].append(list(mesh['local'][vi]))
            tri.append(part['vmap'][vi])
        for ti in mesh['uv_tris'][f]:
            k = (ti, row['key'])
            if k not in part['umap']:
                part['umap'][k] = len(part['uvs'])
                part['uvs'].append(list(fa(row, mesh['uvs'][ti])))
            utri.append(part['umap'][k])
            back.append(part['uvs'][part['umap'][k]])
        if row['udim'] is not None and not in_tile(back, row['udim'], row_tol(row)):
            wrong_udim.setdefault(row['library_id'], []).append(f)
            excess[row['library_id']] = max(excess.get(row['library_id'], 0.0), tile_excess(back, row['udim']))
        part['faces'].append(f)
        part['tris'].append(tri)
        part['uv_tris'].append(utri)
        part['mat_ids'].append(mesh['mat_ids'][f])
        part['rows'].setdefault(row['library_id'], row)
    for mid, faces in sorted(wrong_udim.items()):
        findings.append(('udim_mismatch', faces, 'library id {}: the restored UV leaves UDIM {} of the table by up to '
                                                 '{:.3g} UV'.format(mid, by_id[mid][0]['udim'], excess[mid])))
    for p in parts.values():
        del p['vmap'], p['umap']
    return {'findings': findings, 'parts': parts}


# ---- without a table: one region per ID (atlas.unatlas) --------------------------------------------------------
def region_box(pts, w, h, pad=0):
    """Pixel box (x0, y0, x1, y1; rows from the top, x1/y1 exclusive) of the atlas UV points of one ID in WHOLE
    pixels, `pad` px around, clamped to the atlas. The same box is the crop and the UV frame (`region_uv`)."""
    eps = 1e-7
    xs = [u * w for u, _ in pts]
    ys = [(1.0 - v) * h for _, v in pts]
    x0 = max(0, int(math.floor(min(xs) + eps)) - pad)
    y0 = max(0, int(math.floor(min(ys) + eps)) - pad)
    x1 = min(w, int(math.ceil(max(xs) - eps)) + pad)
    y1 = min(h, int(math.ceil(max(ys) - eps)) + pad)
    return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)


def region_uv(uv, box, w, h, udim):
    """UV of an atlas point in the crop of `box`, placed in tile `udim`: the inverse of the crop by the same pixels."""
    x0, y0, x1, y1 = box
    tu, tv = tile_origin(udim)
    x, y = uv[0] * w, (1.0 - uv[1]) * h
    return (tu + (x - x0) / float(x1 - x0), tv + (y1 - y) / float(y1 - y0))


def crop_error_px(uv, box, w, h, udim):
    """Atlas-pixel distance between where `region_uv` sends a point and where the crop puts that atlas pixel (0 by
    construction; the regression measure of the lab, GeoAGR: 1-8 px, 14-16 px at the atlas edge)."""
    x0, y0, x1, y1 = box
    nu, nv = region_uv(uv, box, w, h, udim)
    tu, tv = tile_origin(udim)
    cx = x0 + (nu - tu) * (x1 - x0)
    cy = y1 - (nv - tv) * (y1 - y0)
    return math.hypot(cx - uv[0] * w, cy - (1.0 - uv[1]) * h)


def plan_regions(mesh, atlas_wh, opts, skip=()):
    """No table: {'findings', 'parts': {'body'|'glass': out mesh}, 'regions': {id: {...}}}. UDIM = 1000 + ID, slot =
    ID, the crop box = the UV frame (whole pixels, native size)."""
    findings = []
    if mesh.get('uv_tris') is None:
        return {'findings': [('no_uv', list(range(len(mesh['tris']))), 'no UV channel 1 on the NPM')], 'parts': {},
                'regions': {}}
    if atlas_wh is None or atlas_wh.get('error'):
        why = (atlas_wh or {}).get('error') or 'no diffuse map on the NPM material'
        return {'findings': [('atlas_missing', [], 'atlas: {} (no table and no atlas: nothing to cut)'.format(why))],
                'parts': {}, 'regions': {}}
    w, h = atlas_wh['w'], atlas_wh['h']
    skip = set(skip)
    by_id = {}
    for f, mid in enumerate(mesh['mat_ids']):
        if f not in skip:
            by_id.setdefault(mid, []).append(f)
    regions, bad = {}, set()
    for mid, faces in sorted(by_id.items()):
        if not 1 <= mid <= 100:
            findings.append(('id_range', faces, 'library id {} has no UDIM 1000 + ID (1..100)'.format(mid)))
            bad.add(mid)
            continue
        pts = [mesh['uvs'][t] for f in faces for t in mesh['uv_tris'][f]]
        ku = {int(math.floor(u + 1e-9)) if abs(u - round(u)) > 1e-9 else None for u, _ in pts}
        kv = {int(math.floor(v + 1e-9)) if abs(v - round(v)) > 1e-9 else None for _, v in pts}
        ku.discard(None)
        kv.discard(None)
        if len(ku) > 1 or len(kv) > 1:
            findings.append(('region_straddle', faces, 'library id {}: the atlas UV crosses an atlas tile border '
                                                       '(u tiles {}, v tiles {})'.format(mid, sorted(ku), sorted(kv))))
            bad.add(mid)
            continue
        du = ku.pop() if ku else 0
        dv = kv.pop() if kv else 0
        local = [(u - du, v - dv) for u, v in pts]
        box = region_box(local, w, h, opts['crop_pad_px'])
        regions[mid] = {'library_id': mid, 'udim': 1000 + mid, 'box_px': list(box), 'size_px': [box[2] - box[0],
                        box[3] - box[1]], 'shift_tiles': [du, dv], 'faces': len(faces),
                        'part': 'glass' if mid in opts['glass_ids'] else 'body'}
    parts = {}
    worst = 0.0
    for mid, faces in sorted(by_id.items()):
        if mid in bad:
            continue
        reg = regions[mid]
        du, dv = reg['shift_tiles']
        part = parts.setdefault(reg['part'], {'faces': [], 'vmap': {}, 'umap': {}, 'verts': [], 'tris': [],
                                              'mat_ids': [], 'uvs': [], 'uv_tris': [], 'regions': {}})
        part['regions'][mid] = reg
        for f in faces:
            tri, utri = [], []
            for vi in mesh['tris'][f]:
                if vi not in part['vmap']:
                    part['vmap'][vi] = len(part['verts'])
                    part['verts'].append(list(mesh['local'][vi]))
                tri.append(part['vmap'][vi])
            for ti in mesh['uv_tris'][f]:
                k = (ti, mid)
                if k not in part['umap']:
                    uv = (mesh['uvs'][ti][0] - du, mesh['uvs'][ti][1] - dv)
                    part['umap'][k] = len(part['uvs'])
                    part['uvs'].append(list(region_uv(uv, reg['box_px'], w, h, reg['udim'])))
                    worst = max(worst, crop_error_px(uv, reg['box_px'], w, h, reg['udim']))
                utri.append(part['umap'][k])
            part['faces'].append(f)
            part['tris'].append(tri)
            part['uv_tris'].append(utri)
            part['mat_ids'].append(mid)
    for p in parts.values():
        del p['vmap'], p['umap']
    return {'findings': findings, 'parts': parts, 'regions': regions, 'crop_error_px': worst, 'atlas_px': [w, h]}


# ---- PNG crop: exact pixels, the source bit depth kept --------------------------------------------------------
_PNG_SIG = b'\x89PNG\r\n\x1a\n'
_CH = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _chunks(data):
    if data[:8] != _PNG_SIG:
        raise ValueError('not a PNG file')
    pos, out = 8, []
    while pos + 12 <= len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise ValueError('truncated PNG chunk')
        out.append((kind, body))
        pos += 12 + length
        if kind == b'IEND':
            break
    return out


def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def png_size(data):
    """(w, h, depth, colour type) of PNG bytes."""
    ch = _chunks(data)
    if not ch or ch[0][0] != b'IHDR':
        raise ValueError('PNG without IHDR')
    w, h, depth, ctype = struct.unpack('>IIBB', ch[0][1][:10])
    return int(w), int(h), int(depth), int(ctype)


def crop_png(data, box):
    """PNG bytes of the pixel box (x0, y0, x1, y1) of a PNG, the same bit depth and colour type (a 16-bit atlas
    stays 16-bit, the palette and tRNS are kept). Interlaced or < 8-bit sources: decoded and written 8-bit."""
    tq = _sibling('texqa_core.py', 'agr_tools_texqa_core')
    ch = _chunks(data)
    w, h, depth, ctype, comp, filt, lace = struct.unpack('>IIBBBBB', ch[0][1][:13])
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
        raise ValueError('crop box {} outside the {}x{} PNG'.format(box, w, h))
    cw, chh = x1 - x0, y1 - y0
    if lace or depth < 8:
        pic = tq.read_png(data)
        n = pic.n if pic.n in (1, 3, 4) else 4
        src = pic.px if pic.n == n else bytes(b for i in range(pic.w * pic.h) for b in (
            pic.px[2 * i], pic.px[2 * i], pic.px[2 * i], pic.px[2 * i + 1]))
        rows = b''.join(src[((y0 + y) * pic.w + x0) * n:((y0 + y) * pic.w + x1) * n] for y in range(chh))
        return tq.write_png(cw, chh, rows, n)
    bpp = _CH[ctype] * depth // 8
    raw = zlib.decompress(b''.join(b for k, b in ch if k == b'IDAT'))
    lines = tq._unfilter(raw, w * bpp, h, bpp)
    body = b''.join(b'\x00' + lines[y][x0 * bpp:x1 * bpp] for y in range(y0, y1))
    out = _PNG_SIG + _chunk(b'IHDR', struct.pack('>IIBBBBB', cw, chh, depth, ctype, 0, 0, 0))
    for k, b in ch:
        if k in (b'PLTE', b'tRNS', b'gAMA', b'sRGB', b'cHRM', b'iCCP'):
            out += _chunk(k, b)
    return out + _chunk(b'IDAT', zlib.compress(body, 9)) + _chunk(b'IEND', b'')


# ---- windows from NPM planes -----------------------------------------------------------------------------------
def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return None if n <= 1e-15 else [a[0] / n, a[1] / n, a[2] / n]


def elements(mesh, faces):
    """Connected groups of `faces` (shared vertices, welded by position to 1e-6 m), each sorted, by first face."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def key(i):
        return tuple(int(round(c * 1e6)) for c in mesh['verts'][i])
    for f in faces:
        ks = [key(i) for i in mesh['tris'][f]]
        for k in ks[1:]:
            a, b = find(ks[0]), find(k)
            if a != b:
                parent[a] = b
    out = {}
    for f in faces:
        out.setdefault(find(key(mesh['tris'][f][0])), []).append(f)
    return sorted((sorted(v) for v in out.values()), key=lambda fs: fs[0])


def frame_of(mesh, faces):
    """Plane frame of a window element (metres): {'origin' (centre), 'x' (right), 'y' (up), 'z' (normal, the street
    side of the face winding), 'w', 'h', 'planar_m'} or {'error'}."""
    n = [0.0, 0.0, 0.0]
    vs = sorted({i for f in faces for i in mesh['tris'][f]})
    for f in faces:
        a, b, c = (mesh['verts'][i] for i in mesh['tris'][f])
        cr = _cross(_sub(b, a), _sub(c, a))
        n = [n[k] + cr[k] for k in range(3)]
    z = _unit(n)
    if z is None:
        return {'error': 'zero area'}
    if abs(z[2]) > HORIZONTAL_COS:
        return {'error': 'horizontal plane: no up direction (normal {:.3f}, {:.3f}, {:.3f})'.format(*z)}
    y = _unit([-z[2] * z[0], -z[2] * z[1], 1.0 - z[2] * z[2]])
    x = _cross(y, z)
    pts = [mesh['verts'][i] for i in vs]
    px = [_dot(p, x) for p in pts]
    py = [_dot(p, y) for p in pts]
    pz = [_dot(p, z) for p in pts]
    mz = sum(pz) / len(pz)
    cx, cy = (min(px) + max(px)) / 2.0, (min(py) + max(py)) / 2.0
    origin = [cx * x[k] + cy * y[k] + mz * z[k] for k in range(3)]
    return {'origin': origin, 'x': x, 'y': y, 'z': z, 'w': max(px) - min(px), 'h': max(py) - min(py),
            'planar_m': max(abs(v - mz) for v in pz)}


def match_type(w, h, types, tol):
    """Library type of a plane w x h (metres) per axis within tol, the 90 deg variant included.

    types: [{'id', 'width_m', 'height_m'}]. Returns {'status': ok|none|ambiguous, 'type', 'rotated', 'err',
    'dw', 'dh', 'why', 'others'}."""
    hits = []
    for t in types:
        W, H = float(t['width_m']), float(t['height_m'])
        for rot, (a, b) in ((False, (W, H)), (True, (H, W))):
            dw, dh = w - a, h - b
            if abs(dw) <= tol + 1e-9 and abs(dh) <= tol + 1e-9:
                hits.append((max(abs(dw), abs(dh)), rot, t['id'], dw, dh))
            if abs(W - H) <= TIE_M:
                break  # a square type: the rotated variant is the same window
    if not hits:
        near = sorted((max(abs(w - float(t['width_m'])), abs(h - float(t['height_m']))), t['id']) for t in types)[:1]
        return {'status': 'none', 'type': None, 'rotated': False, 'err': None, 'dw': None, 'dh': None, 'others': [],
                'why': 'нет типа в пределах {} мм по осям (ближайший {})'.format(
                    round(tol * 1000), '{} на {} мм'.format(near[0][1], round(near[0][0] * 1000)) if near else '—')}
    hits.sort(key=lambda x: (x[0], x[1], x[2]))
    best = hits[0]
    tied = sorted({h_[2] for h_ in hits[1:] if h_[0] - best[0] <= TIE_M and h_[2] != best[2]})
    base = {'type': best[2], 'rotated': best[1], 'err': round(best[0], 6), 'dw': round(best[3], 6),
            'dh': round(best[4], 6)}
    if tied:
        return dict(base, status='ambiguous', type=None, others=[best[2]] + tied,
                    why='несколько типов одного размера: {} — выбор по альбому'.format(', '.join([best[2]] + tied)))
    return dict(base, status='ok', others=sorted({h_[2] for h_ in hits[1:] if h_[2] != best[2]}), why='')


def window_plan(mesh, faces, types, tol):
    """Windows of the window-ID faces: [{'element', 'faces', 'frame', 'match'}] and findings."""
    out, findings = [], []
    for k, fs in enumerate(elements(mesh, faces), 1):
        fr = frame_of(mesh, fs)
        if 'error' not in fr and fr['planar_m'] > PLANAR_TOL_M:
            fr = {'error': 'not planar: {:.1f} mm off the plane'.format(fr['planar_m'] * 1000)}
        if 'error' in fr:
            findings.append(('window_frame', fs, 'window element {}: {}'.format(k, fr['error'])))
            out.append({'element': k, 'faces': fs, 'frame': None, 'match': None})
            continue
        m = match_type(fr['w'], fr['h'], types, tol)
        if m['status'] == 'none':
            findings.append(('window_no_type', fs, 'window element {} {:.3f} x {:.3f} m: {}'.format(
                k, fr['w'], fr['h'], m['why'])))
        elif m['status'] == 'ambiguous':
            findings.append(('window_ambiguous', fs, 'window element {} {:.3f} x {:.3f} m: {}'.format(
                k, fr['w'], fr['h'], m['why'])))
        out.append({'element': k, 'faces': fs, 'frame': fr, 'match': m})
    return out, findings


def window_rows(win, size_m, face_axis='-y', recess_m=0.0):
    """Node transform rows (metres) of the instance of a matched window: winplace_core.placement_rows on the plane
    frame (the type centre on the plane centre, the face to the street); the 90 deg variant turns the frame in its
    plane (x := up, y := -right, the normal kept)."""
    fr = win['frame']
    if win['match']['rotated']:
        fr = dict(fr, x=list(fr['y']), y=[-c for c in fr['x']])
    return winplace().placement_rows(fr, size_m, face_axis, recess_m)


# ---- the plan ----------------------------------------------------------------------------------------------------
def plan(mesh, opts, table=None, atlas_wh=None, types=None):
    """Plan of one NPM object: {'options', 'mode', 'findings', 'parts', 'windows', 'regions', 'summary'}.

    table: validated rows (table_rows) or None; atlas_wh: {'w', 'h'} | {'error'} of the atlas (regions mode);
    types: offerable library window types [{'id', 'width_m', 'height_m'}] (needed when window_ids are given)."""
    o = options(opts)
    if not mesh.get('tris'):
        raise ValueError('nothing to convert: the NPM object has no faces')
    mode = o['mode']
    if mode == 'auto':
        mode = 'table' if table is not None else 'regions'
    findings = []
    if mode == 'table' and table is None:
        findings.append(('table_invalid', [], 'options.mode is table but no correspondence table was found '
                                              '(options.table or npm_table.json next to the atlas)'))
        return {'options': o, 'mode': mode, 'findings': findings, 'parts': {}, 'windows': [], 'regions': {},
                'summary': None}
    win_faces = [f for f, mid in enumerate(mesh['mat_ids']) if mid in o['window_ids']]
    windows = []
    if win_faces:
        if not types:
            raise ValueError('options.window_ids given but no window library types (options.library)')
        windows, wf = window_plan(mesh, win_faces, types, o['window_tol_m'])
        findings.extend(wf)
    if mode == 'table':
        res = plan_table(mesh, table, skip=win_faces)
        regions = {}
    else:
        res = plan_regions(mesh, atlas_wh, o, skip=win_faces)
        regions = res['regions']
    findings.extend(res['findings'])
    counts = {}
    for w in windows:
        st = w['match']['status'] if w['match'] else 'frame'
        counts[st] = counts.get(st, 0) + 1
    summary = {'mode': mode, 'faces': len(mesh['tris']), 'window_faces': len(win_faces),
               'parts': {p: {'faces': len(v['faces']), 'ids': sorted(set(v['mat_ids']))}
                         for p, v in sorted(res['parts'].items())},
               'windows': {'elements': len(windows), 'by_status': counts,
                           'types': sorted({w['match']['type'] for w in windows if w['match'] and
                                            w['match']['status'] == 'ok'})}}
    if mode == 'table':
        summary['udim'] = {str(r['library_id']): r['udim'] for r in table}
    else:
        summary['udim'] = {str(k): v['udim'] for k, v in sorted(regions.items())}
        summary['crop_error_px'] = round(res.get('crop_error_px', 0.0), 6)
    return {'options': o, 'mode': mode, 'findings': findings, 'parts': res['parts'], 'windows': windows,
            'regions': regions, 'summary': summary}


def blocking(findings):
    return [f for f in findings if f[0] in BLOCKING]


def materials_of(p, part, name):
    """{library id: {'name', 'map', 'kind'}} of an output part: the library materials of the table rows (main path)
    or the crops of the regions (`map` = the crop file stem, written by the glue)."""
    out = {}
    if p['mode'] == 'table':
        for mid, row in sorted(p['parts'][part]['rows'].items()):
            out[mid] = {'name': row['material'] or 'M_lib_{}'.format(mid), 'map': row['map'] if row['kind'] ==
                        'texture' else None, 'kind': row['kind']}
    else:
        for mid, reg in sorted(p['parts'][part]['regions'].items()):
            out[mid] = {'name': 'M_{}_{}'.format(name, mid), 'map': crop_name(name, mid, reg['udim']),
                        'kind': 'texture'}
    return out


def crop_name(name, mid, udim):
    """VPM texture name of a region crop: T_<name>_Diffuse_<slot>.<UDIM>.png (slot 1, one UDIM per ID)."""
    return 'T_{}_Diffuse_1.{}.png'.format(name, udim)


def measure(back, part):
    """Read-back of a VPM copy against its planned part: faces, material ids, UV (<= 1e-5, float32 storage).
    Returns (findings, measured)."""
    findings = []
    if len(back['tris']) != len(part['tris']) or back['mat_ids'] != part['mat_ids']:
        raise RuntimeError('VPM copy faces / material ids differ from the plan: {} vs {} faces'.format(
            len(back['tris']), len(part['tris'])))
    worst = 0.0
    for f, t in enumerate(back['uv_tris']):
        for a, b in zip(t, part['uv_tris'][f]):
            pa, pb = back['uvs'][a], part['uvs'][b]
            worst = max(worst, abs(pa[0] - pb[0]), abs(pa[1] - pb[1]))
    if worst > 1e-5:
        findings.append(('readback', [], 'UV of the copy differs from the plan by {:.2e}'.format(worst)))
    return findings, {'uv_max_diff': worst, 'faces': len(back['tris'])}
