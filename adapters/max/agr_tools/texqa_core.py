"""new-case: AGR Tools 0.9 (#979) texture QA (ERM channels, DirectX normals) logic, stdlib only (branch B).

Pure logic for `tex_erm_normal_check` (tex.erm_normal_check); no pymxs. Read-only: the files are only read, never
written. Also the shared stdlib PNG reader/writer of branch B (udim.slots, atlas.flora, atlas.groundel use it).

Source: there is no team or GeoAGR implementation of a DirectX check (GeoAGR gap #4). GeoAGR decides "is this a
normal map" by binarising with `-threshold 50%` and a 32-colour palette through ImageMagick (`GeoAGR.ms:1685`,
`render_map_bump` `GeoAGR.ms:2188-2216`); runtime finding R02 (measured): 128 -> 255, so the flat #8080FF is not
recognised and `normalmap.exe` runs on a finished normal map. Nothing of that is taken over (#853):

T1 no binarisation by a threshold: statistics on the 8-bit values themselves (mean, spread, flat-area offset);
T2 no palette decision: orientation from the gradient field itself. A tangent-space normal map is the gradient of a
   height field, so its field is curl-free in its own convention. The curl of (R, G) read as OpenGL (Y+ up) and as
   DirectX (Y- down) is compared; the convention with the small curl wins, no convention wins -> `ambiguous`;
T3 no external ImageMagick: PNG via checks_core.png_info (header) and stdlib zlib (pixels);
T4 the extension is not trusted: the file signature decides (a JPEG named `.png` is `format_mismatch`);
T5 every file and channel is reported; an undecidable case is `ambiguous`, never a pass.

ERM (VPM): R = emission, G = roughness, B = metalness. Without emission in the material R must stay ~0
(`erm_false_emission`); R = G = B everywhere is a grey picture, not a packed ERM (`erm_grey`).
"""
import importlib.util
import math
import struct
import sys
import zlib
from pathlib import Path

PNG_SIG = b'\x89PNG\r\n\x1a\n'
FLAT = (128, 128, 255)
FLAT_TOL = 3            # 8-bit units: 127/129 are the usual rounding of 0.5
EMISSION_TOL = 8        # R above this without emission is light where there is none
UNIT_TOL = 0.2          # |n| outside 1 +- 0.2 ...
UNIT_SHARE = 0.05       # ... on more than 5 % of the pixels: not a unit normal field
CURL_WIN = 0.5          # the winning convention has < half the curl of the other
GRAD_FLOOR = 1e-4       # mean squared gradient below this: flat, orientation not needed
MAX_SAMPLES = 512       # analysis grid side (the whole image is decoded, the statistics use a stride)
CODES = ('missing_file', 'unreadable', 'format_mismatch', 'bit_depth', 'alpha_channel', 'normal_opengl',
         'normal_orientation_unknown', 'normal_flat_offset', 'normal_not_unit', 'erm_false_emission', 'erm_grey')
AMBIGUOUS = ('normal_orientation_unknown',)


def _sibling(filename, alias):
    """A sibling core of the package: the one runtime._load_core registered, else loaded from this folder."""
    mod = sys.modules.get(alias)
    if mod is not None and getattr(mod, '__file__', None):
        return mod
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


def checks():
    return _sibling('checks_core.py', 'agr_tools_checks_core')


# ---- format --------------------------------------------------------------------------------------------
def sniff(data):
    """File format from the signature: png, jpeg, tga?, bmp, tiff, exr, dds, or unknown. The extension is ignored."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        return 'empty'
    if data[:8] == PNG_SIG:
        return 'png'
    if data[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    if data[:2] == b'BM':
        return 'bmp'
    if data[:4] in (b'II*\x00', b'MM\x00*'):
        return 'tiff'
    if data[:4] == b'v/1\x01':
        return 'exr'
    if data[:4] == b'DDS ':
        return 'dds'
    if len(data) >= 18 and data[2] in (1, 2, 3, 9, 10, 11) and data[16] in (8, 15, 16, 24, 32):
        return 'tga'
    return 'unknown'


def jpeg_size(data):
    """(width, height) from the first SOF marker of a JPEG, else ValueError."""
    if data[:2] != b'\xff\xd8':
        raise ValueError('not a JPEG file')
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            raise ValueError('JPEG marker expected')
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        (length,) = struct.unpack('>H', data[pos + 2:pos + 4])
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack('>HH', data[pos + 5:pos + 9])
            return w, h
        pos += 2 + length
    raise ValueError('JPEG without SOF')


# ---- PNG read ------------------------------------------------------------------------------------------
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class Picture:
    """Decoded picture: 8-bit samples, `n` channels per pixel (1 grey, 2 grey+alpha, 3 RGB, 4 RGBA)."""

    def __init__(self, w, h, n, px, depth=8, color_type=None, alpha=False):
        if len(px) != w * h * n:
            raise ValueError('bad picture buffer')
        self.w, self.h, self.n, self.px = int(w), int(h), int(n), bytes(px)
        self.depth, self.color_type, self.has_alpha = depth, color_type, bool(alpha)

    def channel(self, c):
        return self.px[c::self.n]

    def rgb(self):
        if self.n == 3:
            return self.px
        if self.n == 4:
            out = bytearray(self.w * self.h * 3)
            out[0::3], out[1::3], out[2::3] = self.px[0::4], self.px[1::4], self.px[2::4]
            return bytes(out)
        grey = self.px[0::self.n]
        out = bytearray(self.w * self.h * 3)
        out[0::3] = out[1::3] = out[2::3] = grey
        return bytes(out)

    def alpha(self):
        """Alpha plane or None (no alpha channel and no tRNS)."""
        if self.n == 4:
            return self.px[3::4]
        if self.n == 2:
            return self.px[1::2]
        return None


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _unfilter(raw, stride, height, bpp):
    rows, prev, pos = [], bytes(stride), 0
    for _ in range(height):
        if pos + 1 + stride > len(raw):
            raise ValueError('truncated PNG image data')
        ft = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif ft == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(a, prev[i], c)) & 255
        elif ft != 0:
            raise ValueError('unknown PNG filter type {}'.format(ft))
        rows.append(bytes(line))
        prev = line
    return rows


def read_png(data):
    """Picture from PNG bytes (8/16-bit, every colour type, tRNS, no interlace). ValueError otherwise.

    The header comes from checks_core.png_info (the 0.5.0 reader), the pixels from stdlib zlib."""
    w, h, depth, ctype, alpha = checks().png_info(data)
    pos, plte, trns, idat, lace = 8, None, None, [], 0
    while pos + 12 <= len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise ValueError('truncated PNG chunk')
        if kind == b'IHDR':
            lace = body[12]
        elif kind == b'PLTE':
            plte = body
        elif kind == b'tRNS':
            trns = body
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            break
        pos += 12 + length
    if lace:
        raise ValueError('interlaced PNG is not read (re-save without interlace)')
    if ctype == 3 and plte is None:
        raise ValueError('palette PNG without PLTE')
    try:
        raw = zlib.decompress(b''.join(idat))
    except zlib.error as exc:
        raise ValueError('broken PNG image data: {}'.format(exc)) from None
    nch = _CHANNELS[ctype]
    bits = depth * nch
    stride = (w * bits + 7) // 8
    rows = _unfilter(raw, stride, h, max(1, bits // 8))
    out_n = {0: 1, 2: 3, 3: 3, 4: 2, 6: 4}[ctype]
    key = None
    if trns is not None and ctype in (0, 2):
        key = struct.unpack('>H', trns[:2])[0] if ctype == 0 else struct.unpack('>HHH', trns[:6])
        out_n += 1
    pal_a = None
    if ctype == 3:
        pal = [tuple(plte[i:i + 3]) for i in range(0, len(plte) - 2, 3)]
        if trns is not None:
            pal_a = list(trns[:len(pal)]) + [255] * max(0, len(pal) - len(trns))
            out_n = 4
    px = bytearray()
    maxv = (1 << depth) - 1
    for line in rows:
        if depth == 8 and key is None and ctype != 3:
            px += line[:w * nch]
            continue
        if depth == 16:
            s = struct.unpack('>{}H'.format(w * nch), line[:2 * w * nch])
            s8 = [(v * 255 + 32767) // 65535 for v in s]
        elif depth < 8:
            per, mask = 8 // depth, maxv
            s = []
            for byte in line:
                for k in range(per):
                    s.append((byte >> (8 - depth * (k + 1))) & mask)
            s = s[:w * nch]
            s8 = s if ctype == 3 else [(v * 255 + maxv // 2) // maxv for v in s]
        else:
            s = list(line[:w * nch])
            s8 = s
        for x in range(w):
            p = s[x * nch:(x + 1) * nch]
            q = s8[x * nch:(x + 1) * nch]
            if ctype == 3:
                if p[0] >= len(pal):
                    raise ValueError('palette index out of range')
                px += bytes(pal[p[0]])
                if pal_a is not None:
                    px.append(pal_a[p[0]])
                continue
            px += bytes(q)
            if key is not None:
                px.append(0 if (tuple(p) if ctype == 2 else p[0]) == key else 255)
    return Picture(w, h, out_n, px, depth=depth, color_type=ctype, alpha=alpha)


# ---- PNG write (8-bit, colour types 0 / 2 / 6) ---------------------------------------------------------
def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def write_png(w, h, px, channels):
    """PNG bytes of an 8-bit picture: channels 1 = grey (ct 0), 3 = RGB (ct 2, 24 bit), 4 = RGBA (ct 6).

    Deterministic (filter 0, zlib level 9): the same pixels give the same file in every Max version."""
    ctype = {1: 0, 3: 2, 4: 6}[channels]
    if len(px) != w * h * channels:
        raise ValueError('bad picture buffer')
    stride = w * channels
    raw = b''.join(b'\x00' + bytes(px[y * stride:(y + 1) * stride]) for y in range(h))
    return (PNG_SIG + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ctype, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(raw, 9)) + _chunk(b'IEND', b''))


def pixel_md5(pic):
    import hashlib
    return hashlib.md5(struct.pack('<III', pic.w, pic.h, pic.n) + pic.px).hexdigest()


# ---- analysis -------------------------------------------------------------------------------------------
def _grid(pic):
    step = max(1, int(math.ceil(max(pic.w, pic.h) / float(MAX_SAMPLES))))
    xs = list(range(0, pic.w, step))
    ys = list(range(0, pic.h, step))
    return xs, ys


def _stats(values):
    vals = list(values)
    if not vals:
        return {'min': 0, 'max': 0, 'mean': 0.0}
    return {'min': min(vals), 'max': max(vals), 'mean': round(sum(vals) / len(vals), 3)}


def normal_analysis(pic):
    """Statistics and verdict of one normal map. Returns {'stats', 'orientation', 'findings': [(code, detail)]}.

    orientation: 'directx' | 'opengl' | 'flat' | 'unknown' (gradients without a curl-free convention)."""
    n = pic.n
    if n < 3:
        return {'stats': {}, 'orientation': 'unknown',
                'findings': [('normal_not_unit', 'grey picture: a normal map has R, G and B')]}
    xs, ys = _grid(pic)
    w = pic.w
    px = pic.px

    def at(x, y):
        o = (y * w + x) * n
        return px[o], px[o + 1], px[o + 2]

    rs, gs, bs = [], [], []
    off_unit, flat_dev, flat_count = 0, 0, 0
    a = {}
    for y in ys:
        for x in xs:
            r, g, b = at(x, y)
            rs.append(r)
            gs.append(g)
            bs.append(b)
            vx, vy, vz = r / 127.5 - 1.0, g / 127.5 - 1.0, b / 127.5 - 1.0
            if abs(math.sqrt(vx * vx + vy * vy + vz * vz) - 1.0) > UNIT_TOL:
                off_unit += 1
            a[(x, y)] = (vx, vy)
    findings = []
    total = len(rs)
    stats = {'R': _stats(rs), 'G': _stats(gs), 'B': _stats(bs), 'samples': total}
    if off_unit > UNIT_SHARE * total:
        findings.append(('normal_not_unit', '{:.1%} of the pixels are not unit normals (|n| outside 1+-{}); '
                                            'mean RGB {}/{}/{}'.format(off_unit / float(total), UNIT_TOL,
                                                                       stats['R']['mean'], stats['G']['mean'],
                                                                       stats['B']['mean'])))
    # flat areas: a pixel equal to its right and lower neighbours is flat; flat pixels must be ~ (128,128,255)
    for yi in range(len(ys) - 1):
        for xi in range(len(xs) - 1):
            x, y = xs[xi], ys[yi]
            c = at(x, y)
            if c == at(xs[xi + 1], y) and c == at(x, ys[yi + 1]):
                flat_count += 1
                if max(abs(c[k] - FLAT[k]) for k in range(3)) > FLAT_TOL:
                    flat_dev += 1
    stats['flat_samples'] = flat_count
    if flat_count and flat_dev > 0.5 * flat_count:
        findings.append(('normal_flat_offset', '{} of {} flat samples differ from (128,128,255) by more than {}'
                                               .format(flat_dev, flat_count, FLAT_TOL)))
    # orientation by curl: OpenGL dh/dy_img = +G', DirectX dh/dy_img = -G'; dh/dx = -R' in both
    grad = curl_gl = curl_dx = 0.0
    cells = 0
    for yi in range(len(ys) - 1):
        for xi in range(len(xs) - 1):
            x0, x1, y0, y1 = xs[xi], xs[xi + 1], ys[yi], ys[yi + 1]
            r00, g00 = a[(x0, y0)]
            r10, g10 = a[(x1, y0)]
            r01, g01 = a[(x0, y1)]
            r11, g11 = a[(x1, y1)]
            d_r_dy = ((r01 + r11) - (r00 + r10)) / 2.0
            d_g_dx = ((g10 + g11) - (g00 + g01)) / 2.0
            d_r_dx = ((r10 + r11) - (r00 + r01)) / 2.0
            d_g_dy = ((g01 + g11) - (g00 + g10)) / 2.0
            curl_gl += (-d_r_dy - d_g_dx) ** 2
            curl_dx += (-d_r_dy + d_g_dx) ** 2
            grad += d_r_dx ** 2 + d_g_dy ** 2 + d_r_dy ** 2 + d_g_dx ** 2
            cells += 1
    cells = max(cells, 1)
    grad, curl_gl, curl_dx = grad / cells, curl_gl / cells, curl_dx / cells
    stats['curl'] = {'opengl': round(curl_gl, 9), 'directx': round(curl_dx, 9), 'gradient': round(grad, 9)}
    if grad < GRAD_FLOOR:
        orientation = 'flat'
    elif curl_dx < CURL_WIN * curl_gl:
        orientation = 'directx'
    elif curl_gl < CURL_WIN * curl_dx:
        orientation = 'opengl'
        findings.append(('normal_opengl', 'green channel is Y+ up (OpenGL): curl OpenGL {:.3g} < DirectX {:.3g}; '
                                          'VPM needs DirectX (green down), invert G'.format(curl_gl, curl_dx)))
    else:
        orientation = 'unknown'
        findings.append(('normal_orientation_unknown', 'gradients without a curl-free convention '
                                                       '(OpenGL {:.3g}, DirectX {:.3g}): check by eye'
                                                       .format(curl_gl, curl_dx)))
    return {'stats': stats, 'orientation': orientation, 'findings': findings}


def erm_analysis(pic, emissive=False):
    """Channel statistics of an ERM (R emission, G roughness, B metalness) and its findings."""
    n = pic.n
    if n < 3:
        return {'stats': {}, 'findings': [('erm_grey', 'grey picture: an ERM packs three channels')]}
    xs, ys = _grid(pic)
    w, px = pic.w, pic.px
    rs, gs, bs = [], [], []
    grey = True
    for y in ys:
        for x in xs:
            o = (y * w + x) * n
            r, g, b = px[o], px[o + 1], px[o + 2]
            rs.append(r)
            gs.append(g)
            bs.append(b)
            if grey and not (r == g == b):
                grey = False
    stats = {'R': _stats(rs), 'G': _stats(gs), 'B': _stats(bs), 'samples': len(rs),
             'R_lit_share': round(sum(1 for r in rs if r > EMISSION_TOL) / float(len(rs)), 6)}
    findings = []
    if grey and stats['R']['max'] > 0:
        findings.append(('erm_grey', 'R = G = B in every sample (mean {}): a grey picture, not a packed '
                                     'emission/roughness/metalness map'.format(stats['R']['mean'])))
    elif not emissive and stats['R']['max'] > EMISSION_TOL:
        findings.append(('erm_false_emission', 'R (emission) up to {} on {:.1%} of the pixels, the material has '
                                               'no emission: R must be 0'.format(stats['R']['max'],
                                                                                  stats['R_lit_share'])))
    return {'stats': stats, 'findings': findings}


def check_file(path, data, role, emissive=False):
    """One map file -> {'file', 'role', 'format', 'size', 'findings': [(code, detail)], 'stats', ...}.

    data: bytes or None (missing). role: 'normal' | 'erm'."""
    if role not in ('normal', 'erm'):
        raise ValueError('role must be normal or erm: ' + repr(role))
    name = str(path).replace('\\', '/').rsplit('/', 1)[-1]
    out = {'file': name, 'path': str(path), 'role': role, 'format': None, 'size': None, 'depth': None,
           'findings': [], 'stats': {}}
    if data is None:
        out['findings'].append(('missing_file', '{}: file not found'.format(name)))
        return out
    fmt = sniff(data)
    out['format'] = fmt
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if fmt != 'png':
        detail = '{}: the file is {} (signature), not PNG'.format(name, fmt.upper())
        if ext == 'png':
            detail += ' although named .png'
        out['findings'].append(('format_mismatch', detail))
        return out
    try:
        pic = read_png(data)
    except (ValueError, struct.error, IndexError, KeyError) as exc:
        out['findings'].append(('unreadable', '{}: {}'.format(name, exc)))
        return out
    out['size'] = [pic.w, pic.h]
    out['depth'] = pic.depth
    out['pixel_md5'] = pixel_md5(pic)
    if pic.depth != 8:
        out['findings'].append(('bit_depth', '{}: {} bits per channel, VPM maps are 8 bit'.format(name, pic.depth)))
    alpha = pic.alpha()
    if alpha is not None:
        opaque = min(alpha) == 255
        out['findings'].append(('alpha_channel', '{}: {} map with an alpha channel ({}); alpha belongs only to '
                                                 'Diffuse'.format(name, role, 'all opaque' if opaque else
                                                                  'min alpha {}'.format(min(alpha)))))
    res = normal_analysis(pic) if role == 'normal' else erm_analysis(pic, emissive)
    out['stats'] = res['stats']
    if role == 'normal':
        out['orientation'] = res['orientation']
    out['findings'].extend(res['findings'])
    return out


def erm_normal_plan(objects):
    """objects: [{'key', 'name', 'maps': [{'path', 'role', 'emissive', 'data'(bytes|None), 'material'}],
    'skipped': [(item, reason)]}] -> {'entries': [(key, name, [(code, detail)])], 'done', 'skipped', 'ambiguous'}.

    Every map file is listed in `done` with its findings and statistics; an undecidable orientation is also in
    `ambiguous`. No ERM/normal map in the whole input is an error (an empty input is never a pass)."""
    if not any(o['maps'] for o in objects):
        raise ValueError('no ERM or normal map on the selected objects (by file name T_*_ERM_* / *_Normal_* / '
                         '_n_ or a bump/normal slot)')
    entries, done, skipped, ambiguous = [], [], [], []
    for o in objects:
        findings = []
        seen = set()
        for m in o['maps']:
            key = (str(m['path']).lower(), m['role'], bool(m.get('emissive')))
            if key in seen:
                continue
            seen.add(key)
            res = check_file(m['path'], m.get('data'), m['role'], bool(m.get('emissive')))
            row = {'object': o['name'], 'material': m.get('material'), 'file': res['file'], 'path': res['path'],
                   'role': res['role'], 'format': res['format'], 'size': res['size'], 'depth': res['depth'],
                   'codes': sorted({c for c, _ in res['findings']}), 'stats': res['stats']}
            if 'orientation' in res:
                row['orientation'] = res['orientation']
            if 'pixel_md5' in res:
                row['pixel_md5'] = res['pixel_md5']
            done.append(row)
            for code, detail in res['findings']:
                findings.append((code, detail))
                if code in AMBIGUOUS:
                    ambiguous.append({'object': o['name'], 'file': res['file'], 'code': code, 'detail': detail})
        for item, reason in o.get('skipped', ()):
            skipped.append((item, reason))
        entries.append((o['key'], o['name'], findings))
    return {'entries': entries, 'done': done, 'skipped': skipped, 'ambiguous': ambiguous}


_ROLE_TOKENS = {'normal': 'normal', 'n': 'normal', 'nrm': 'normal', 'erm': 'erm'}


def role_of(path, slot_hint=None):
    """'normal' | 'erm' | None from the file name tokens (T_<Addr>_<Normal|ERM>_<slot>.<UDIM>, NPM `_n_`),
    else from the material slot (a bump/normal slot is a normal map)."""
    stem = str(path).replace('\\', '/').rsplit('/', 1)[-1]
    stem = stem.split('.', 1)[0]
    for token in reversed(stem.split('_')):
        role = _ROLE_TOKENS.get(token.lower())
        if role:
            return role
    hint = str(slot_hint or '').lower()
    if 'normal' in hint or 'bump' in hint:
        return 'normal'
    return None
