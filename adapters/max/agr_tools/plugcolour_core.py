"""new-case: AGR Tools 1.0 (#1024) plug colours check logic, stdlib only. Stub of branch 0; owned by branch L (improve/issue-1024-materials).

Pure logic for `tex_plug_colour` (tex.plug_colour, plan mode `read`: preview only); no pymxs. Uses edit_core.py for
reports; PNG decoding is tex_core.decode_png (0.8, all colour types, palette + tRNS, 16 bit, Adam7), TGA is decoded
here; other formats (JPG, BMP, TIF) are decoded by the glue through .NET System.Drawing (no Max gamma).

Lab L14 (docs/experiments/tex.plug_colour.md, jobs 20261106-023826-7907def9 ...) measured the source, GeoAGR UDIMs
«Colors Tex» (GeoAGR.ms:14475, handler :39668-39965), and its verdict `new` is implemented here:
* «most popular» was the FIRST colour found -> here the mode of a full histogram (ties are reported, never guessed);
* row 0 was never read (rows from 1, numbering from 0) -> every row is read (large maps: a regular grid sample that
  includes row 0 and column 0, never a skip);
* alpha ignored (RGBA/palette became opaque RGB) -> weight = alpha / 255, alpha 0 is not counted, the transparent
  share is reported;
* the written colour went dark by the gamma 2.2 of the Max bitmap slot -> values are file bytes (gamma 1.0);
* sources were overwritten in place (7 of 7) -> read only; the plug file is a NEW file (plug_png) by mat.tiles;
* 512^2 / 256x1024 maps were not counted, one modal dialog each -> any size, no dialogs.

Per file report: file, size, colours (distinct visible), top-N with shares, transparent share, chosen colour, mean,
spread (RMSE to the mean, normalised 0..1; max CIEDE2000 of the visible colours to the chosen one) and the decision.
Thresholds are parameters (Q02/Q03 of the plan: RMSE <= 0.03 default).
"""
import hashlib
import importlib.util
import math
import os
import struct
import sys

DEFAULTS = {'max_rmse': 0.03, 'top': 5, 'max_samples': 1 << 20}
DECISIONS = ('pass', 'spread', 'tie', 'no_visible', 'unreadable')
CODES = {'plug_spread': 'not one colour: spread above the threshold',
         'plug_tie': 'two or more colours share the top weight',
         'plug_no_visible': 'every pixel is transparent',
         'plug_unreadable': 'the file could not be read'}
NATIVE_EXTS = ('.png', '.tga')


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


def tex_core():
    return _sibling('agr_tools_tex_core', 'tex_core.py')


def options(opts):
    o = dict(DEFAULTS)
    for k, v in (opts or {}).items():
        if k in ('max_rmse',):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
                raise ValueError('max_rmse must be 0..1')
            o[k] = float(v)
        elif k in ('top', 'max_samples'):
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(k + ' must be a positive integer')
            o[k] = v
    return o


# ---- decoding -------------------------------------------------------------------------------------------------
def decode_tga(data):
    """(w, h, n, pixels RGB/RGBA top-down) of an uncompressed or RLE true-colour TGA (24/32 bit) or 8-bit grey."""
    if len(data) < 18:
        raise ValueError('TGA too short')
    idlen, cmtype, itype = data[0], data[1], data[2]
    w, h = struct.unpack('<HH', data[12:16])
    bpp, desc = data[16], data[17]
    if cmtype != 0 or itype not in (2, 3, 10, 11) or bpp not in (8, 24, 32):
        raise ValueError('unsupported TGA (type {}, {} bit)'.format(itype, bpp))
    pos = 18 + idlen
    k = bpp // 8
    total = w * h
    if itype in (2, 3):
        raw = data[pos:pos + total * k]
        if len(raw) != total * k:
            raise ValueError('TGA data truncated')
    else:
        out = bytearray()
        while len(out) < total * k:
            head = data[pos]
            pos += 1
            count = (head & 0x7f) + 1
            if head & 0x80:
                out += data[pos:pos + k] * count
                pos += k
            else:
                out += data[pos:pos + count * k]
                pos += count * k
        raw = bytes(out[:total * k])
    n = 4 if k == 4 else 3
    px = bytearray(total * n)
    if k == 1:
        px[0::3], px[1::3], px[2::3] = raw, raw, raw
    else:
        px[0::n], px[1::n], px[2::n] = raw[2::k], raw[1::k], raw[0::k]  # BGR(A) -> RGB(A)
        if n == 4:
            px[3::4] = raw[3::4]
    if not desc & 0x20:  # bottom-up origin
        stride = w * n
        px = b''.join(bytes(px[(h - 1 - y) * stride:(h - y) * stride]) for y in range(h))
    return w, h, n, bytes(px)


def decode(path, data, other=None):
    """(w, h, n, pixels, decoder) of a map file. `other(path)` -> tex_core.Image for formats the core cannot read."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.png' or data[:8] == b'\x89PNG\r\n\x1a\n':
        img, _ = tex_core().decode_png(data)
        return img.w, img.h, img.n, img.px, 'png'
    if ext == '.tga':
        w, h, n, px = decode_tga(data)
        return w, h, n, px, 'tga'
    if other is None:
        raise ValueError('no decoder for {} (the glue decodes it through .NET)'.format(ext or 'file'))
    img = other(path)
    return img.w, img.h, img.n, img.px, 'dotnet'


# ---- analysis -------------------------------------------------------------------------------------------------
def _stride(w, h, max_samples):
    s = 1
    while (w // s + (w % s > 0)) * (h // s + (h % s > 0)) > max_samples:
        s += 1
    return s


def histogram(w, h, n, px, max_samples=DEFAULTS['max_samples']):
    """({(r, g, b): alpha weight}, samples, transparent samples, stride). Rows and columns from 0, stride grid."""
    s = _stride(w, h, max_samples)
    hist = {}
    samples = transparent = 0
    stride = w * n
    for y in range(0, h, s):
        row = px[y * stride:(y + 1) * stride]
        for x in range(0, w, s):
            o = x * n
            a = row[o + 3] if n == 4 else 255
            samples += 1
            if a == 0:
                transparent += 1
                continue
            key = (row[o], row[o + 1], row[o + 2])
            hist[key] = hist.get(key, 0.0) + a / 255.0
    return hist, samples, transparent, s


def analyse(name, w, h, n, px, opts=None):
    """Report row of one map (see module doc)."""
    o = options(opts)
    hist, samples, transparent, stride = histogram(w, h, n, px, o['max_samples'])
    row = {'file': name, 'size': [w, h], 'channels': n, 'stride': stride, 'samples': samples,
           'transparent_share': round(transparent / samples, 6) if samples else 0.0}
    total = sum(hist.values())
    if total <= 0:
        row.update({'colours': 0, 'top': [], 'chosen': None, 'mean': None, 'rmse': None, 'max_delta_e': None,
                    'decision': 'no_visible'})
        return row
    ranked = sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))
    best = ranked[0][1]
    tied = [c for c, wt in ranked if abs(wt - best) <= 1e-9 * max(1.0, best)]
    chosen = list(ranked[0][0])
    mean = [sum(c[i] * wt for c, wt in hist.items()) / total for i in range(3)]
    sq = sum(wt * sum((c[i] - mean[i]) ** 2 for i in range(3)) for c, wt in hist.items()) / (3 * total)
    rmse = math.sqrt(sq) / 255.0
    tiles = _sibling('agr_tools_tiles_core', 'tiles_core.py')
    max_de = max(tiles.delta_e2000(c, chosen) for c, wt in ranked[:64])  # the 64 heaviest colours
    row.update({'colours': len(hist),
                'top': [{'rgb': list(c), 'share': round(wt / total, 6)} for c, wt in ranked[:o['top']]],
                'chosen': chosen, 'mean': [round(x, 3) for x in mean], 'rmse': round(rmse, 6),
                'max_delta_e': round(max_de, 4)})
    if len(tied) > 1:
        row['decision'] = 'tie'
        row['tied'] = [list(c) for c in tied[:o['top']]]
    elif rmse > o['max_rmse']:
        row['decision'] = 'spread'
    else:
        row['decision'] = 'pass'
    return row


def finding_of(row):
    d = row['decision']
    if d == 'pass':
        return None
    code = 'plug_' + {'spread': 'spread', 'tie': 'tie', 'no_visible': 'no_visible', 'unreadable': 'unreadable'}[d]
    if d == 'spread':
        detail = '{}: RMSE {} > threshold, chosen {} ({:.1%})'.format(
            os.path.basename(row['file']), row['rmse'], row['chosen'], row['top'][0]['share'])
    elif d == 'tie':
        detail = '{}: tie of {}'.format(os.path.basename(row['file']), row['tied'])
    else:
        detail = '{}: {}'.format(os.path.basename(row['file']), row.get('error', CODES[code]))
    return code, detail


def analyse_file(path, read, other=None, opts=None):
    """Row of one file: read(path) -> bytes. Errors become the decision `unreadable`."""
    try:
        data = read(path)
        if data is None:
            raise ValueError('file is missing')
        sha = hashlib.sha256(data).hexdigest()
        w, h, n, px, how = decode(path, data, other)
    except Exception as exc:  # noqa: BLE001 - one broken file is a finding, the others still count
        return {'file': path, 'decision': 'unreadable', 'error': '{}: {}'.format(type(exc).__name__, exc)[:300]}
    row = analyse(path, w, h, n, px, opts)
    row.update({'sha256': sha, 'decoder': how})
    return row


def plug_png(rgb, size=256):
    """NEW plug file bytes: solid RGB square, exact colour (written by mat.tiles; this row never writes)."""
    return tex_core().solid_png(size, tuple(int(c) for c in rgb))


def report(edit, entries, rows, ambiguous, state_hash, opts):
    return edit.report('tex.plug_colour', 'preview', objects=entries, done=[r['file'] for r in rows],
                       ambiguous=ambiguous, state_hash=state_hash,
                       extra={'files': rows, 'options': opts})
