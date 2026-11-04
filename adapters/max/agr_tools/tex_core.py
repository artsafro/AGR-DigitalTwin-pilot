"""new-case: AGR Tools 0.8 (#908) tex logic, stdlib only (branch B, improve/issue-908-tex); no pymxs.

Three plan rows, glue in tex_max.py:

* `tex.format_fix` (`tex_format_fix`): writes fixed PNG copies into a NEW folder, never in place. The
  format is decided from the PNG header (`checks_core.png_info`: IHDR bit depth + colour type, tRNS), not
  from `identify` text (lab L03: palette invisible, 16-bit RGB shown as `32-bit Argb`). Alpha is removed only
  where the rule forbids it, over an explicit background or by edge colour (dilate on request), otherwise
  the file is refused with a reason; a fully opaque alpha channel is dropped losslessly. Every file is
  processed (a JPG does not stop the batch); the aspect ratio is kept (a non-square file is reported, never
  stretched); the size limit is a parameter (default 3 MiB = 3*1024^2 bytes) reached by lossless re-encoding
  first and posterisation only when needed, with RMSE reported. Dilate is off by default.
* `tex.placeholders` (`tex_placeholders`): solid D/ERM/N placeholder PNG (8-bit RGB, colour type 2, no
  alpha, exact colour) with VPM-2.10-4.3 names `T_{Address}[_Ground]_{Diffuse|ERM|Normal}_{Slot}.{UDIM}.png`
  in an explicit folder (os.path.join, a folder without trailing separator is still the folder), sizes
  128..4096 (default 256 = VPM flat placeholder), an existing file is refused or versioned, never overwritten.
* `scene.missing_maps` (`scene_missing_maps`): read-only report over all bitmap-like maps (glue enumerates
  them); `<UDIM>`/`<UVTILE>` expanded per tile, ranked relink candidates by base name with an ambiguity
  flag, hidden and UCX owners flagged (not filtered), resolution of existing files, JSON + table.

GeoAGR is cited only as `GeoAGR.ms:<line>`; team scripts by file name + SHA256 (#853); no code is copied.
"""
import hashlib
import importlib.util
import os
import re
import struct
import sys
import zlib

PNG_SIG = b'\x89PNG\r\n\x1a\n'
MIB = 1024 * 1024
DEFAULT_MAX_BYTES = 3 * MIB          # NPM textures.max_file_bytes (3145728)
MAX_POSTERIZE_BITS = 6               # lossy fallback: drop at most this many low bits per channel
PLACEHOLDER_SIZES = (128, 256, 512, 1024, 2048, 4096)
DEFAULT_PLACEHOLDER_SIZE = 256       # VPM textures.flat_placeholder.size_px (NPM 128 on request)
PLACEHOLDER_COLOURS = {'Diffuse': (200, 200, 200), 'ERM': (0, 255, 0), 'Normal': (128, 128, 255)}
MAPS = ('Diffuse', 'ERM', 'Normal')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.bmp', '.exr', '.hdr', '.psd', '.dds', '.gif')
_ADDRESS = re.compile(r'^[A-Za-z0-9_]+$')
_UDIM = re.compile(r'<udim>', re.I)
_UVTILE = re.compile(r'<uvtile>', re.I)


# ---- sibling cores (same instances as runtime._load_core) ----------------------------------------------
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


def checks():
    return _sibling('agr_tools_checks_core', 'checks_core.py')


def edit_core():
    return _sibling('agr_tools_edit_core', 'edit_core.py')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# ---- PNG decode (all colour types, depths 1..16, Adam7) ------------------------------------------------
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
_ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))


class Image:
    """8-bit pixels, 3 (RGB) or 4 (RGBA) channels, row-major bytes."""
    __slots__ = ('w', 'h', 'n', 'px')

    def __init__(self, w, h, n, px):
        if n not in (3, 4) or len(px) != w * h * n:
            raise ValueError('bad image buffer')
        self.w, self.h, self.n, self.px = int(w), int(h), int(n), bytes(px)

    def rgb(self):
        if self.n == 3:
            return self.px
        out = bytearray(self.w * self.h * 3)
        out[0::3], out[1::3], out[2::3] = self.px[0::4], self.px[1::4], self.px[2::4]
        return bytes(out)

    def alpha(self):
        return self.px[3::4] if self.n == 4 else None


def _chunks(data):
    if data[:8] != PNG_SIG:
        raise ValueError('not a PNG file')
    pos = 8
    while pos + 12 <= len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length or pos + 12 + length > len(data):
            raise ValueError('truncated PNG chunk')
        crc = struct.unpack('>I', data[pos + 8 + length:pos + 12 + length])[0]
        if zlib.crc32(kind + body) & 0xffffffff != crc:
            raise ValueError('PNG chunk CRC mismatch: ' + kind.decode('latin-1'))
        yield kind, body
        if kind == b'IEND':
            return
        pos += 12 + length
    raise ValueError('PNG without IEND')


def _unfilter(raw, width, height, bpp_bits, channels_bytes_per_px):
    """Reverse PNG filters for one (sub)image; returns rows of scanline bytes."""
    stride = (width * bpp_bits + 7) // 8
    bpp = max(1, channels_bytes_per_px)
    rows, prev, pos = [], bytearray(stride), 0
    for _ in range(height):
        ft = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        if len(line) != stride:
            raise ValueError('truncated PNG image data')
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
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif ft != 0:
            raise ValueError('unknown PNG filter type {}'.format(ft))
        rows.append(line)
        prev = line
    return rows, pos


def _samples(line, width, depth, nch):
    """Scanline -> list of integer samples (width*nch)."""
    count = width * nch
    if depth == 8:
        return list(line[:count])
    if depth == 16:
        return list(struct.unpack('>{}H'.format(count), bytes(line[:2 * count])))
    out, per = [], 8 // depth
    mask = (1 << depth) - 1
    for byte in line:
        for k in range(per):
            out.append((byte >> (8 - depth * (k + 1))) & mask)
    return out[:count]


def decode_png(data):
    """(Image, info). info: width, height, depth, color_type, interlace, trns (bool), palette size."""
    ihdr, plte, trns, idat = None, None, None, []
    for kind, body in _chunks(data):
        if kind == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body)
        elif kind == b'PLTE':
            plte = body
        elif kind == b'tRNS':
            trns = body
        elif kind == b'IDAT':
            idat.append(body)
    if ihdr is None:
        raise ValueError('PNG without IHDR')
    w, h, depth, ctype, comp, filt, lace = ihdr
    if ctype not in _CHANNELS or comp or filt or lace not in (0, 1):
        raise ValueError('unsupported PNG header')
    if ctype == 3 and plte is None:
        raise ValueError('palette PNG without PLTE')
    nch = _CHANNELS[ctype]
    raw = zlib.decompress(b''.join(idat))
    bits = depth * nch
    bpp = (bits + 7) // 8
    has_alpha = ctype in (4, 6) or trns is not None
    n = 4 if has_alpha else 3
    maxv = (1 << depth) - 1
    key = None
    if trns is not None and ctype == 0:
        key = struct.unpack('>H', trns[:2])[0]
    elif trns is not None and ctype == 2:
        key = struct.unpack('>HHH', trns[:6])
    pal = None
    if ctype == 3:
        pal = [bytes(plte[i:i + 3]) for i in range(0, len(plte), 3)]
        pal_a = list(trns or b'')[:len(pal)] + [255] * max(0, len(pal) - len(trns or b''))
        pal = [p + bytes((a,)) if n == 4 else p for p, a in zip(pal, pal_a)]

    def to8(v):
        return v if depth == 8 else (v * 255 + maxv // 2) // maxv

    def convert(line, pw):
        """One unfiltered scanline -> pw pixels of n 8-bit channels."""
        if depth == 8 and key is None and ctype in (2, 6):
            return bytes(line[:pw * nch])
        s = _samples(line, pw, depth, nch)
        if ctype == 3:
            try:
                return b''.join(pal[i] for i in s)
            except IndexError:
                raise ValueError('palette index out of range') from None
        row = bytearray(pw * n)
        for c in range(pw):
            p = s[c * nch:(c + 1) * nch]
            if ctype == 0:
                v = to8(p[0])
                px = (v, v, v, 0 if p[0] == key else 255)
            elif ctype == 4:
                v = to8(p[0])
                px = (v, v, v, to8(p[1]))
            elif ctype == 2:
                px = (to8(p[0]), to8(p[1]), to8(p[2]), 0 if tuple(p) == key else 255)
            else:
                px = (to8(p[0]), to8(p[1]), to8(p[2]), to8(p[3]))
            row[c * n:(c + 1) * n] = bytes(px[:n])
        return bytes(row)

    out = bytearray(w * h * n)
    passes = [(0, 0, 1, 1)] if lace == 0 else _ADAM7
    pos = 0
    for x0, y0, dx, dy in passes:
        pw = (w - x0 + dx - 1) // dx if w > x0 else 0
        ph = (h - y0 + dy - 1) // dy if h > y0 else 0
        if pw == 0 or ph == 0:
            continue
        rows, used = _unfilter(raw[pos:], pw, ph, bits, bpp)
        pos += used
        for r, line in enumerate(rows):
            y = y0 + r * dy
            px = convert(line, pw)
            if dx == 1:
                out[y * w * n:(y + 1) * w * n] = px
            else:
                for c in range(pw):
                    o = (y * w + x0 + c * dx) * n
                    out[o:o + n] = px[c * n:(c + 1) * n]
    info ={'width': w, 'height': h, 'depth': depth, 'color_type': ctype, 'interlace': lace,
            'trns': trns is not None, 'palette': len(plte) // 3 if plte else 0}
    return Image(w, h, n, out), info


# ---- PNG encode (8-bit RGB / RGBA) ---------------------------------------------------------------------
def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def _filtered(px, w, h, n, ft):
    stride = w * n
    out = bytearray()
    prev = bytes(stride)
    for y in range(h):
        line = px[y * stride:(y + 1) * stride]
        out.append(ft)
        if ft == 0:
            out += line
        elif ft == 1:
            out += line[:n] + bytes((a - b) & 255 for a, b in zip(line[n:], line))
        elif ft == 2:
            out += bytes((a - b) & 255 for a, b in zip(line, prev))
        else:
            raise ValueError('encoder filter {}'.format(ft))
        prev = line
    return bytes(out)


def encode_png(img, filters=(0, 1, 2), level=9, with_filter=False):
    """Smallest of whole-image filter strategies; IHDR depth 8, colour type 2 (RGB) or 6 (RGBA)."""
    ctype = 2 if img.n == 3 else 6
    head = PNG_SIG + _chunk(b'IHDR', struct.pack('>IIBBBBB', img.w, img.h, 8, ctype, 0, 0, 0))
    best, best_ft = None, None
    for ft in filters:
        z = zlib.compress(_filtered(img.px, img.w, img.h, img.n, ft), level)
        if best is None or len(z) < len(best):
            best, best_ft = z, ft
    png = head + _chunk(b'IDAT', best) + _chunk(b'IEND', b'')
    return (png, best_ft) if with_filter else png


def solid_png(size, colour):
    """Solid 8-bit RGB square PNG, exact colour."""
    r, g, b = _colour(colour)
    row = b'\x00' + bytes((r, g, b)) * size
    head = PNG_SIG + _chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
    return head + _chunk(b'IDAT', zlib.compress(row * size, 9)) + _chunk(b'IEND', b'')


# ---- pixel operations ----------------------------------------------------------------------------------
def rmse(a, b):
    """Root mean square error of two equal-length 8-bit buffers, normalised to [0, 1]."""
    if len(a) != len(b):
        raise ValueError('rmse of different sizes')
    if not a:
        return 0.0
    hist = [0] * 511
    for x, y in zip(a, b):
        hist[x - y + 255] += 1
    s = sum(c * (i - 255) ** 2 for i, c in enumerate(hist) if c)
    return round((s / len(a)) ** 0.5 / 255.0, 6)


def posterize(px, bits):
    """Round every channel to the nearest multiple of 2**bits (fewer distinct values, deflates better)."""
    step = 1 << bits
    table = bytes(min(255, ((v + step // 2) // step) * step) for v in range(256))
    return px.translate(table)


def flatten(img, background):
    """RGBA over an explicit background colour -> RGB; (Image, count of non-opaque pixels)."""
    br, bg, bb = _colour(background)
    px, out, partial = img.px, bytearray(img.w * img.h * 3), 0
    for i in range(img.w * img.h):
        r, g, b, a = px[4 * i:4 * i + 4]
        o = 3 * i
        if a == 255:
            out[o:o + 3] = bytes((r, g, b))
            continue
        partial += 1
        k = 255 - a
        out[o] = (r * a + br * k + 127) // 255
        out[o + 1] = (g * a + bg * k + 127) // 255
        out[o + 2] = (b * a + bb * k + 127) // 255
    return Image(img.w, img.h, 3, out), partial


def dilate(img, background=None):
    """Edge colour for transparent pixels: fully transparent pixels take the mean colour of already filled
    4-neighbours, ring by ring; partly transparent pixels keep their own colour (alpha dropped). Pixels a
    ring cannot reach (an image without any opaque pixel) take `background` or are refused."""
    w, h = img.w, img.h
    px = img.px
    out = bytearray(img.rgb())
    filled = bytearray(1 if a else 0 for a in px[3::4])
    if not any(filled):
        if background is None:
            raise ValueError('fully transparent image: dilate needs a background colour')
        return flatten(img, background)
    count = w * h - sum(filled)
    front = [i for i in range(w * h) if not filled[i]]
    while front:
        newly, rest = [], []
        for i in front:
            x, y = i % w, i // w
            acc, k = [0, 0, 0], 0
            for j in ((i - 1) if x > 0 else -1, (i + 1) if x < w - 1 else -1, (i - w) if y > 0 else -1,
                      (i + w) if y < h - 1 else -1):
                if j >= 0 and filled[j]:
                    acc[0] += out[3 * j]
                    acc[1] += out[3 * j + 1]
                    acc[2] += out[3 * j + 2]
                    k += 1
            if k:
                newly.append((i, [(c + k // 2) // k for c in acc]))
            else:
                rest.append(i)
        if not newly:
            break
        for i, c in newly:
            out[3 * i:3 * i + 3] = bytes(c)
            filled[i] = 1
        front = rest
    return Image(w, h, 3, out), count


def downscale(img, max_side):
    """Halve (2x2 box) while the longer side exceeds max_side; aspect kept. (Image, factor)."""
    factor = 1
    while max(img.w, img.h) > max_side:
        if img.w % 2 or img.h % 2 or min(img.w, img.h) < 2:
            raise ValueError('cannot halve {}x{} evenly'.format(img.w, img.h))
        w, h, n, px = img.w // 2, img.h // 2, img.n, img.px
        out = bytearray(w * h * n)
        s = img.w * n
        for y in range(h):
            r0, r1 = 2 * y * s, (2 * y + 1) * s
            for x in range(w):
                for c in range(n):
                    a = 2 * x * n + c
                    out[(y * w + x) * n + c] = (px[r0 + a] + px[r0 + a + n] + px[r1 + a] + px[r1 + a + n] + 2) // 4
        img = Image(w, h, n, out)
        factor *= 2
    return img, factor


def _colour(c):
    if not isinstance(c, (list, tuple)) or len(c) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in c):
        raise ValueError('colour must be [r, g, b] integers 0..255: ' + repr(c))
    return tuple(c)


# ---- tex.format_fix ------------------------------------------------------------------------------------
def _least_posterize(img, ft, limit, max_bits):
    """Smallest posterize depth (fewest dropped bits, least loss) whose PNG fits the limit: binary search,
    each try encoded with the filter that won the lossless pass. (bits, png, pixels) or None."""
    lo, hi, best = 1, max_bits, None
    while lo <= hi:
        mid = (lo + hi) // 2
        px = posterize(img.px, mid)
        png = encode_png(Image(img.w, img.h, img.n, px), filters=(ft,))
        if len(png) <= limit:
            best, hi = (mid, png, px), mid - 1
        else:
            lo = mid + 1
    return best


def map_kind(stem):
    """Map type from a delivery texture stem: VPM Diffuse/ERM/Normal or NPM d/n/o/m/r, else None."""
    parts = stem.split('.')[0].split('_')
    if len(parts) < 2:
        return None
    m = parts[-2]
    return m if m in MAPS or m in ('d', 'n', 'o', 'm', 'r') else None


def alpha_allowed(profile, stem):
    """NPM never; VPM only in Diffuse (VPM textures.diffuse_alpha, normal_and_erm_alpha: forbidden)."""
    return profile == 'vpm' and map_kind(stem) == 'Diffuse'


def format_options(options):
    """Validated, complete options of tex.format_fix (recorded in the preview plan)."""
    o = dict(options or {})
    known = {'files', 'folder', 'out', 'profile', 'background', 'dilate', 'max_bytes', 'max_side',
             'keep_allowed_alpha', 'max_posterize_bits'}
    extra = set(o) - known
    if extra:
        raise ValueError('unknown tex.format_fix options: ' + ', '.join(sorted(extra)))
    out = {'profile': o.get('profile', 'npm'), 'background': o.get('background'), 'dilate': bool(o.get('dilate', False)),
           'max_bytes': o.get('max_bytes', DEFAULT_MAX_BYTES), 'max_side': o.get('max_side'),
           'keep_allowed_alpha': bool(o.get('keep_allowed_alpha', True)),
           'max_posterize_bits': o.get('max_posterize_bits', MAX_POSTERIZE_BITS)}
    if out['profile'] not in ('npm', 'vpm'):
        raise ValueError('profile must be npm or vpm')
    if out['background'] is not None:
        out['background'] = list(_colour(out['background']))
    if type(out['max_bytes']) is not int or out['max_bytes'] < 1024:
        raise ValueError('max_bytes must be an integer >= 1024')
    if out['max_side'] is not None and (type(out['max_side']) is not int or out['max_side'] < 1):
        raise ValueError('max_side must be a positive integer')
    if type(out['max_posterize_bits']) is not int or not 0 <= out['max_posterize_bits'] <= 7:
        raise ValueError('max_posterize_bits must be 0..7')
    for key in ('out', 'folder'):
        if o.get(key) is not None:
            if not isinstance(o[key], str) or not o[key].strip():
                raise ValueError(key + ' must be a folder path')
            out[key] = o[key]
    if o.get('files') is not None:
        if not isinstance(o['files'], list) or not all(isinstance(p, str) and p for p in o['files']):
            raise ValueError('files must be a list of paths')
        out['files'] = list(o['files'])
    return out


def list_sources(folder):
    """Image files directly in a folder (sorted, case-insensitive)."""
    return sorted((os.path.join(folder, f) for f in os.listdir(folder)
                   if os.path.splitext(f)[1].lower() in IMAGE_EXTS and os.path.isfile(os.path.join(folder, f))),
                  key=lambda p: p.lower())


def _norm(p):
    return os.path.normcase(os.path.abspath(p))


def output_folder(sources, out=None, exists=os.path.exists):
    """Target folder: explicit `out` (must be new or empty, never a source folder) or a new versioned
    `AGR_format_fix` beside the first source."""
    edit = edit_core()
    folders = {_norm(os.path.dirname(p)) for p in sources}
    if out is not None:
        if _norm(out) in folders:
            raise ValueError('output folder is a source folder (never in place): ' + out)
        if exists(out) and (not os.path.isdir(out) or os.listdir(out)):
            raise FileExistsError('output folder exists and is not empty: ' + out)
        return out
    if not sources:
        raise ValueError('no source files')
    return edit.new_path(os.path.join(os.path.dirname(sources[0]), 'AGR_format_fix'), version=True, exists=exists)


def fix_one(path, data, opts, decoded=None):
    """Plan + result for one source file. Returns a row dict; `row['png']` holds the output bytes (not in
    the report) or the row has `reason` (refused). `decoded` = Image from the glue for a non-PNG file."""
    stem, ext = os.path.splitext(os.path.basename(path))
    row = {'source': path, 'sha256': sha256(data), 'bytes_in': len(data), 'out_name': stem + '.png',
           'actions': [], 'notes': []}
    if ext.lower() == '.png':
        try:
            w, h, depth, ctype, has_alpha = checks().png_info(data)
            img, info = decode_png(data)
        except (ValueError, zlib.error, struct.error) as exc:
            row['reason'] = 'unreadable PNG: {}'.format(exc)
            return row
        row['format'] = {'width': w, 'height': h, 'bit_depth': depth, 'color_type': ctype, 'alpha': has_alpha,
                         'interlace': info['interlace']}
        if depth != 8 or ctype not in (2, 6):
            row['actions'].append('to_8bit_rgb' if ctype != 3 else 'palette_to_rgb')
        if info['interlace']:
            row['actions'].append('deinterlace')
    else:
        if decoded is None:
            row['reason'] = '{} cannot be decoded here (only PNG in the stdlib core; Max decodes others)'.format(ext)
            return row
        img = decoded
        row['format'] = {'width': img.w, 'height': img.h, 'bit_depth': 8, 'color_type': None,
                         'alpha': img.n == 4, 'interlace': 0, 'source_format': ext.lower().lstrip('.')}
        row['actions'].append('{}_to_png'.format(ext.lower().lstrip('.')))
    if img.w != img.h:
        row['notes'].append('not square {}x{}: kept, not stretched'.format(img.w, img.h))
    if img.n == 4:
        alpha = img.alpha()
        transparent = len(alpha) - alpha.count(255)
        if not transparent:
            img = Image(img.w, img.h, 3, img.rgb())
            row['actions'].append('alpha_dropped_opaque')
        elif opts['keep_allowed_alpha'] and alpha_allowed(opts['profile'], stem):
            row['notes'].append('alpha kept: allowed in {} Diffuse'.format(opts['profile'].upper()))
        elif opts['dilate']:
            img, count = dilate(img, opts['background'])
            row['actions'].append('alpha_flattened_dilate')
            row['flattened_pixels'] = count
        elif opts['background'] is not None:
            img, count = flatten(img, opts['background'])
            row['actions'].append('alpha_flattened')
            row['flattened_pixels'] = count
            row['background'] = list(opts['background'])
        else:
            row['reason'] = ('alpha in use ({} non-opaque pixels) and forbidden in {} {}: choose options.background '
                             '[r,g,b] or options.dilate').format(transparent, opts['profile'].upper(),
                                                                 map_kind(stem) or 'textures')
            return row
    if opts['max_side'] is not None and max(img.w, img.h) > opts['max_side']:
        try:
            img, factor = downscale(img, opts['max_side'])
        except ValueError as exc:
            row['reason'] = 'max_side: {}'.format(exc)
            return row
        row['actions'].append('downscaled_1/{}'.format(factor))
    row['size_px'] = [img.w, img.h]
    untouched = (not row['actions'] and ext.lower() == '.png' and len(data) <= opts['max_bytes'])
    if untouched:
        row['png'] = bytes(data)
        row['actions'].append('copied_unchanged')
    else:
        png, ft = encode_png(img, with_filter=True)
        if len(png) > opts['max_bytes']:
            row['lossless_bytes'] = len(png)
            best = _least_posterize(img, ft, opts['max_bytes'], opts['max_posterize_bits'])
            if best is None:
                row['reason'] = ('{} bytes after lossless re-encoding and posterize up to {} bits still > {}: '
                                 'set options.max_side').format(len(png), opts['max_posterize_bits'],
                                                                opts['max_bytes'])
                return row
            bits, png, px = best
            row['actions'].append('posterize_{}bit'.format(bits))
            row['rmse'] = rmse(img.px, px)
        if 'rmse' not in row:
            row['rmse'] = 0.0
            row['actions'].append('reencoded_lossless')
        row['png'] = png
    row['bytes_out'] = len(row['png'])
    row['sha256_out'] = sha256(row['png'])
    return row


def format_fix(sources, opts, read, decode=None, exists=os.path.exists):
    """Rows for every source (none stops the batch) + output folder. read(path)->bytes|None,
    decode(path)->Image|None for non-PNG files."""
    out = output_folder(sources, opts.get('out'), exists)
    rows, names = [], {}
    for path in sources:
        data = read(path)
        if data is None:
            rows.append({'source': path, 'reason': 'source file not found', 'actions': [], 'notes': []})
            continue
        dec = None
        if not path.lower().endswith('.png') and decode is not None:
            try:
                dec = decode(path)
            except Exception as exc:  # noqa: BLE001 - one bad file never stops the batch
                rows.append({'source': path, 'reason': 'decode failed: {}'.format(exc), 'actions': [], 'notes': []})
                continue
        try:
            row = fix_one(path, data, opts, dec)
        except Exception as exc:  # noqa: BLE001 - recorded per file, the batch goes on
            row = {'source': path, 'reason': 'failed: {}: {}'.format(type(exc).__name__, exc), 'actions': [],
                   'notes': []}
        if 'png' in row:
            key = row['out_name'].lower()
            if key in names:
                row['reason'] = 'output name {} already taken by {}'.format(row['out_name'], names[key])
                row['ambiguous'] = True
                row.pop('png')
            else:
                names[key] = path
                row['out'] = os.path.join(out, row['out_name'])
        rows.append(row)
    return out, rows


def format_state(sources, read, opts, out):
    files = []
    for p in sources:
        data = read(p)
        files.append({'path': p, 'sha256': sha256(data) if data is not None else None})
    taken = sorted(os.listdir(out)) if os.path.isdir(out) else ([None] if os.path.exists(out) else [])
    return {'tool': 'tex.format_fix', 'files': files, 'options': opts, 'out': out, 'out_content': taken}


def format_report(edit, mode, out, rows, state_hash, opts, written=()):
    done, skipped, ambiguous, table = [], [], [], []
    for r in rows:
        public = {k: v for k, v in r.items() if k != 'png'}
        table.append(public)
        if 'reason' in r:
            skipped.append(edit.skipped(r['source'], r['reason']))
            if r.get('ambiguous'):
                ambiguous.append({'item': r['source'], 'reason': r['reason']})
        else:
            done.append({'source': r['source'], 'out': r['out'], 'actions': r['actions'], 'rmse': r.get('rmse', 0.0)})
    extra = {'out': out, 'options': opts, 'files': table}
    if mode == 'apply':
        extra['written'] = list(written)
    return edit.report('tex.format_fix', mode, [], done, skipped, ambiguous,
                       state_hash=state_hash if mode == 'preview' else None, extra=extra)


def write_outputs(edit, out, rows):
    """Exclusive create of every planned output (never overwrites); returns written paths."""
    os.makedirs(out, exist_ok=True)
    written = []
    for r in rows:
        if 'png' in r:
            edit.write_new(r['out'], r['png'])
            written.append(r['out'])
    return written


# ---- tex.placeholders ----------------------------------------------------------------------------------
def placeholder_options(options):
    o = dict(options or {})
    known = {'folder', 'address', 'ground', 'slots', 'udim', 'sizes', 'colours', 'diffuse_from', 'on_exists'}
    extra = set(o) - known
    if extra:
        raise ValueError('unknown tex.placeholders options: ' + ', '.join(sorted(extra)))
    out = {'folder': o.get('folder'), 'address': o.get('address'), 'ground': bool(o.get('ground', False)),
           'slots': o.get('slots', [1]), 'udim': o.get('udim', 1001), 'sizes': o.get('sizes', [DEFAULT_PLACEHOLDER_SIZE]),
           'on_exists': o.get('on_exists', 'refuse'), 'diffuse_from': o.get('diffuse_from')}
    colours = dict(PLACEHOLDER_COLOURS)
    for k, v in (o.get('colours') or {}).items():
        if k not in MAPS:
            raise ValueError('colour for unknown map ' + repr(k))
        colours[k] = _colour(v)
    out['colours'] = {k: list(v) for k, v in colours.items()}
    if out['folder'] is not None and (not isinstance(out['folder'], str) or not out['folder'].strip()):
        raise ValueError('folder must be a path')
    if out['address'] is not None and not _ADDRESS.match(str(out['address'])):
        raise ValueError('address must be A-Z a-z 0-9 _ (VPM naming.stem_characters)')
    if not isinstance(out['slots'], list) or not out['slots'] or any(type(s) is not int or s < 1 for s in out['slots']):
        raise ValueError('slots must be a list of positive integers')
    if type(out['udim']) is not int or not 1001 <= out['udim'] <= 1100:
        raise ValueError('udim must be 1001..1100')
    if (not isinstance(out['sizes'], list) or not out['sizes']
            or any(s not in PLACEHOLDER_SIZES for s in out['sizes']) or len(set(out['sizes'])) != len(out['sizes'])):
        raise ValueError('sizes must be distinct values of {}'.format(list(PLACEHOLDER_SIZES)))
    if out['on_exists'] not in ('refuse', 'version'):
        raise ValueError('on_exists must be refuse or version')
    return out


def placeholder_name(address, mp, slot, udim, ground=False):
    """VPM-2.10-4.3: T_{Address}_{Diffuse|ERM|Normal}_{SlotNumber}.{UDIM}.png (Ground: T_{Address}_Ground_...)."""
    if mp not in MAPS:
        raise ValueError('unknown map ' + repr(mp))
    return 'T_{}{}_{}_{}.{}.png'.format(address, '_Ground' if ground else '', mp, slot, udim)


def average_colour(img):
    """Single average colour (VPM flat_placeholder.single_average_color); alpha-weighted for RGBA."""
    n, px = img.n, img.px
    tot, acc = 0, [0, 0, 0]
    for i in range(img.w * img.h):
        wgt = px[i * n + 3] if n == 4 else 255
        tot += wgt
        for c in range(3):
            acc[c] += px[i * n + c] * wgt
    if not tot:
        raise ValueError('fully transparent image has no average colour')
    return [(a + tot // 2) // tot for a in acc]


def placeholder_plan(opts, exists=os.path.exists):
    """Planned files: [{map, size, colour, path}] or a reason (refused). os.path.join, never string glue."""
    edit = edit_core()
    rows = []
    many = len(opts['sizes']) > 1
    for size in opts['sizes']:
        folder = os.path.join(opts['folder'], str(size)) if many else opts['folder']
        for slot in opts['slots']:
            for mp in MAPS:
                name = placeholder_name(opts['address'], mp, slot, opts['udim'], opts['ground'])
                target = os.path.join(folder, name)
                row = {'map': mp, 'size': size, 'slot': slot, 'udim': opts['udim'], 'colour': opts['colours'][mp],
                       'name': name}
                try:
                    row['path'] = edit.new_path(target, version=opts['on_exists'] == 'version', exists=exists)
                    if row['path'] != target:
                        row['versioned_from'] = target
                except FileExistsError:
                    row['path'] = target
                    row['reason'] = 'exists, not overwritten (on_exists=refuse): ' + target
                rows.append(row)
    return rows


def placeholder_report(edit, mode, opts, rows, state_hash=None, written=()):
    done = [{'path': r['path'], 'map': r['map'], 'size': r['size'], 'colour': r['colour']}
            for r in rows if 'reason' not in r]
    skipped = [edit.skipped(r['path'], r['reason']) for r in rows if 'reason' in r]
    extra = {'options': opts, 'files': rows}
    if mode == 'apply':
        extra['written'] = list(written)
    return edit.report('tex.placeholders', mode, [], done, skipped, [],
                       state_hash=state_hash if mode == 'preview' else None, extra=extra)


def write_placeholders(edit, rows):
    written = []
    for r in rows:
        if 'reason' in r:
            continue
        os.makedirs(os.path.dirname(r['path']), exist_ok=True)
        edit.write_new(r['path'], solid_png(r['size'], r['colour']))
        written.append(r['path'])
    return written


# ---- scene.missing_maps --------------------------------------------------------------------------------
def image_size(data):
    """(w, h) from PNG/JPEG/TGA headers, else None. PNG via checks_core.png_info."""
    if not data:
        return None
    try:
        if data[:8] == PNG_SIG:
            w, h = checks().png_info(data[:33])[:2]  # signature + IHDR: a header read is enough
            return [w, h]
        if data[:2] == b'\xff\xd8':
            pos = 2
            while pos + 4 <= len(data):
                if data[pos] != 0xFF:
                    pos += 1
                    continue
                marker = data[pos + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    pos += 2
                    continue
                length = struct.unpack('>H', data[pos + 2:pos + 4])[0]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack('>HH', data[pos + 5:pos + 9])
                    return [w, h]
                pos += 2 + length
            return None
        if len(data) >= 18 and data[2] in (1, 2, 3, 9, 10, 11) and data[1] in (0, 1):
            w, h = struct.unpack('<HH', data[12:16])
            return [w, h] if w and h else None
    except (ValueError, struct.error, IndexError):
        return None
    return None


def udim_pattern(path):
    """Regex over file names of a tiled path (<UDIM> / <UVTILE>), or None for a plain path."""
    name = os.path.basename(path)
    if not (_UDIM.search(name) or _UVTILE.search(name)):
        return None
    parts = re.split(r'(<udim>|<uvtile>)', name, flags=re.I)
    rx = ''
    for p in parts:
        low = p.lower()
        rx += r'(?P<udim>1\d{3})' if low == '<udim>' else r'u(?P<u>\d+)_v(?P<v>\d+)' if low == '<uvtile>' else re.escape(p)
    return re.compile('^' + rx + '$', re.I)


def tile_path(path, udim):
    u, v = (udim - 1001) % 10, (udim - 1001) // 10
    folder, name = os.path.split(path)
    name = _UDIM.sub(str(udim), name)
    name = _UVTILE.sub('u{}_v{}'.format(u + 1, v + 1), name)
    return os.path.join(folder, name)


def tiles_on_disk(path, listdir=os.listdir):
    rx = udim_pattern(path)
    folder = os.path.dirname(path)
    found = set()
    try:
        names = listdir(folder)
    except OSError:
        return found
    for n in names:
        m = rx.match(n)
        if not m:
            continue
        if m.groupdict().get('udim'):
            found.add(int(m.group('udim')))
        else:
            found.add(1001 + (int(m.group('u')) - 1) + 10 * (int(m.group('v')) - 1))
    return found


def uv_tiles(faces):
    """UDIM tiles used by UV faces (lists of (u, v)); a face belongs to the tile of its centroid."""
    out = set()
    for f in faces:
        if not f:
            continue
        u = sum(p[0] for p in f) / len(f)
        v = sum(p[1] for p in f) / len(f)
        if u < 0 or v < 0 or u >= 10:
            continue
        out.add(1001 + int(u) + 10 * int(v))
    return out


def candidate_index(folders, listdir=os.listdir, isdir=os.path.isdir, recursive=(), limit=20000):
    """{stem.lower(): [paths]} of image files in the folders (search folders recursively)."""
    index, seen, count = {}, set(), 0
    todo = [(f, False) for f in folders] + [(f, True) for f in recursive]
    while todo:
        folder, deep = todo.pop()
        key = (_norm(folder), deep)
        if key in seen or not folder:
            continue
        seen.add(key)
        try:
            names = listdir(folder)
        except OSError:
            continue
        for n in names:
            p = os.path.join(folder, n)
            if deep and isdir(p):
                todo.append((p, True))
                continue
            stem, ext = os.path.splitext(n)
            if ext.lower() in IMAGE_EXTS:
                index.setdefault(stem.lower(), []).append(p)
                count += 1
                if count >= limit:
                    return index
    return index


def candidates(path, index):
    """Ranked relink candidates for a missing path: same name + extension first (rank 0), then the same
    base name with another extension (rank 1); each path once, sorted within a rank."""
    stem, ext = os.path.splitext(os.path.basename(path))
    me = _norm(path)
    out, seen = [], set()
    for p in index.get(stem.lower(), []):
        key = _norm(p)
        if key in seen or key == me:
            continue
        seen.add(key)
        out.append({'path': p, 'rank': 0 if os.path.splitext(p)[1].lower() == ext.lower() else 1})
    return sorted(out, key=lambda c: (c['rank'], c['path'].lower()))


def missing_maps(maps, exists, read_head, index, listdir=os.listdir):
    """maps: [{path, owners:[{handle,node,material,map,hidden,ucx}], uv_tiles:set|None, source}] from the
    glue, one record per (path) after merging. Returns rows, one per concrete path (UDIM per tile)."""
    merged = {}
    for m in maps:
        key = m['path']
        rec = merged.setdefault(key, {'path': key, 'owners': [], 'uv_tiles': set(), 'sources': set()})
        for o in m.get('owners', []):
            if o not in rec['owners']:
                rec['owners'].append(o)
        rec['uv_tiles'] |= set(m.get('uv_tiles') or ())
        rec['sources'].add(m.get('source', 'material'))
    rows = []
    for key in sorted(merged, key=str.lower):
        rec = merged[key]
        base = {'owners': sorted(rec['owners'], key=lambda o: (o.get('node') or '', o.get('material') or '')),
                'sources': sorted(rec['sources'])}
        if udim_pattern(key):
            disk = tiles_on_disk(key, listdir)
            tiles = sorted(rec['uv_tiles'] | disk)
            if not tiles:
                rows.append(dict(base, path=key, tiled=key, tile=None, exists=False,
                                 note='tiled path: no tile on disk and no UV tile'))
                continue
            for t in tiles:
                rows.append(dict(base, path=tile_path(key, t), tiled=key, tile=t, in_uv=t in rec['uv_tiles']))
        else:
            rows.append(dict(base, path=key, tiled=None, tile=None))
    for r in rows:
        if 'exists' not in r:
            r['exists'] = bool(exists(r['path']))
        r['size_px'] = image_size(read_head(r['path'])) if r['exists'] else None
        r['candidates'] = [] if r['exists'] else candidates(r['path'], index)
        r['ambiguous'] = len(r['candidates']) > 1
        r['hidden'] = any(o.get('hidden') for o in r['owners'])
        r['ucx'] = any(o.get('ucx') for o in r['owners'])
    return rows


def missing_table(rows):
    """Plain text table (one line per path) for the panel and the MCP answer."""
    head = 'exists | path | size | owners | flags | candidates'
    lines = [head, '-' * len(head)]
    for r in rows:
        owners = ', '.join(sorted({'{}/{}'.format(o.get('node') or '-', o.get('material') or '-')
                                   for o in r['owners']})) or '(asset only)'
        flags = ','.join(f for f in ('hidden' if r['hidden'] else '', 'UCX' if r['ucx'] else '',
                                     'ambiguous' if r['ambiguous'] else '', 'tile {}'.format(r['tile']) if r['tile'] else '')
                         if f) or '-'
        size = 'x'.join(map(str, r['size_px'])) if r['size_px'] else '-'
        cands = '; '.join('{}[{}]'.format(c['path'], c['rank']) for c in r['candidates']) or '-'
        lines.append(' | '.join(('yes' if r['exists'] else 'NO', r['path'], size, owners, flags, cands)))
    return lines


def missing_report(edit, rows, state_hash, nodes, extra=None):
    """Read-only report: objects = owner nodes (finding per missing path), plan.maps/table/summary."""
    found = {}
    for r in rows:
        for o in r['owners']:
            if o.get('handle'):
                found.setdefault(o['handle'], {'name': o['node'], 'findings': []})
                if not r['exists']:
                    flags = [f for f in ('hidden' if o.get('hidden') else '', 'UCX' if o.get('ucx') else '') if f]
                    detail = '{} ({}){}'.format(r['path'], o.get('material') or '-',
                                                ' [' + ','.join(flags) + ']' if flags else '')
                    f = edit.finding('map_missing', (), detail)
                    if f not in found[o['handle']]['findings']:
                        found[o['handle']]['findings'].append(f)
    for h, name in nodes:
        found.setdefault(h, {'name': name, 'findings': []})
    objects = [edit.entry(h, v['name'], v['findings']) for h, v in sorted(found.items())]
    ambiguous = [{'item': r['path'], 'candidates': [c['path'] for c in r['candidates']]} for r in rows if r['ambiguous']]
    summary = {'paths': len(rows), 'missing': sum(1 for r in rows if not r['exists']),
               'with_candidate': sum(1 for r in rows if not r['exists'] and r['candidates']),
               'ambiguous': len(ambiguous), 'hidden': sum(1 for r in rows if r['hidden']),
               'ucx': sum(1 for r in rows if r['ucx'])}
    plan = {'read_only': True, 'maps': rows, 'table': missing_table(rows), 'summary': summary}
    plan.update(extra or {})
    return edit.report('scene.missing_maps', 'preview', objects, [], [], ambiguous, state_hash=state_hash,
                       extra=plan)
