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

0.9 rework (#979, branch E1, audit cards T01/T02/T05/T06; team scripts read for ideas only):
* format_fix (T01/png_compressor: compress_png.py 75ff969b…ef088, compress_png_gui.py e8cb5687…441a): lossless
  first; then a <= 256 colour palette with Floyd-Steinberg dithering (Q01) and posterisation compete, the fitting
  candidate with the least RMSE wins and an RMSE over `max_rmse` (Q02 open: a parameter) is a refusal with the
  measured value, never «готово»; a file already under the limit is never quantised; no temporary files in the
  core (the glue's decoder removes its own).
* placeholders (T01/index_to_rgb 90070bbf…750dc, T05/Texture_Zaglushki_Ground 888eacc9…4867c, T02/atlas_builder
  v9 maf e6477f51…380e): average over visible pixels (alpha-weighted), rounded; RGB 24 bit; several UDIMs per
  call, a repeated UDIM is refused (never written twice); ERM metal slots `[0,0,255]` (R emission, G roughness,
  B metalness: metal with roughness 0), non-metal default as 0.8; an unreadable `diffuse_from` (TGA, EXR, PSD…)
  skips the Diffuse file with a reason instead of a silent grey; one set per address of the selected objects.
* missing_maps (T06/alexyo_texfinder_v2 056bc4b4…7e0a): relink candidates also by the project texture mask of the
  owner object and map role (`T_<Address>[_NNN]_<Type>_<d|n|o|m|r>_1.*`, VPM `T_<Address>_<Map>_1.<UDIM>.*`),
  any image extension (.png AND .jpg), ranked, ambiguity flagged; search folders default to the map paths (no
  "123" default), a relative search folder is refused.
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
ERM_METAL = (0, 0, 255)              # R emission 0, G roughness 0 (metal is smooth), B metalness 255
MAPS = ('Diffuse', 'ERM', 'Normal')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.bmp', '.exr', '.hdr', '.psd', '.dds', '.gif')
# Formats the Max glue decodes through .NET System.Drawing; TGA/EXR/HDR/PSD/DDS are not among them (T05: a TGA
# became a silent grey 128 there), so they are refused with a reason before any decode.
DRAWING_EXTS = ('.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff')
DEFAULT_MAX_RMSE = 0.03              # quality floor of lossy fitting (Q02 open: parameter; T01 8 colours = 0.157)
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


def names_core():
    """The names grammar (texture masks of missing_maps candidates); same module name as runtime._load_core."""
    return _sibling('agr_tools_names_core', 'names_core.py')


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


def encode_palette_png(w, h, palette, indices, level=9):
    """Indexed PNG: IHDR depth 8, colour type 3, PLTE of <= 256 RGB entries, no tRNS."""
    if not 1 <= len(palette) <= 256 or len(indices) != w * h:
        raise ValueError('bad palette image')
    head = PNG_SIG + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 3, 0, 0, 0))
    plte = _chunk(b'PLTE', b''.join(bytes(c) for c in palette))
    best = None
    for ft in (0, 1, 2):
        z = zlib.compress(_filtered(bytes(indices), w, h, 1, ft), level)
        if best is None or len(z) < len(best):
            best = z
    return head + plte + _chunk(b'IDAT', best) + _chunk(b'IEND', b'')


def exact_palette(img, limit=256):
    """(palette, indices) when an RGB image has <= limit distinct colours, else None (lossless)."""
    px = img.px
    colours = {}
    idx = bytearray(img.w * img.h)
    for i in range(img.w * img.h):
        c = px[3 * i:3 * i + 3]
        k = colours.get(c)
        if k is None:
            if len(colours) >= limit:
                return None
            k = colours[c] = len(colours)
        idx[i] = k
    return [tuple(c) for c in colours], bytes(idx)


def quantize(img, colours=256):
    """Median cut over a 5-bit-per-channel histogram -> (palette, indices, rgb pixels of the result).
    Every histogram cell maps to the weighted mean of its box (pngquant-style idea, no dithering)."""
    px = img.px
    r5, g5, b5 = (px[c::3].translate(bytes(v >> 3 for v in range(256))) for c in range(3))
    keys = [(r << 10) | (g << 5) | b for r, g, b in zip(r5, g5, b5)]
    hist, sums = {}, {}
    for i, k in enumerate(keys):
        if k in hist:
            hist[k] += 1
            s = sums[k]
            s[0] += px[3 * i]
            s[1] += px[3 * i + 1]
            s[2] += px[3 * i + 2]
        else:
            hist[k] = 1
            sums[k] = [px[3 * i], px[3 * i + 1], px[3 * i + 2]]
    cells = [(sums[k][0] / hist[k], sums[k][1] / hist[k], sums[k][2] / hist[k], hist[k], k) for k in hist]
    def measured(box):
        if len(box) < 2:
            return (-1, 0, box)
        spreads = [max(c[a] for c in box) - min(c[a] for c in box) for a in range(3)]
        a = spreads.index(max(spreads))
        return (spreads[a], a, box)

    boxes = [measured(cells)]
    while len(boxes) < colours:
        bi = max(range(len(boxes)), key=lambda i: boxes[i][0])
        spread, axis, box = boxes[bi]
        if spread <= 0:
            break
        boxes.pop(bi)
        box = sorted(box, key=lambda c: c[axis])
        total, run, cut = sum(c[3] for c in box), 0, 1
        for j, c in enumerate(box):
            run += c[3]
            if run * 2 >= total:
                cut = min(max(j + 1, 1), len(box) - 1)
                break
        boxes += [measured(box[:cut]), measured(box[cut:])]
    boxes = [b[2] for b in boxes]
    palette, lut = [], {}
    for bi, box in enumerate(boxes):  # a cell takes the mean colour of its own median-cut box
        n = sum(c[3] for c in box)
        palette.append(tuple(int(round(sum(c[a] * c[3] for c in box) / n)) for a in range(3)))
        for c in box:
            lut[c[4]] = bi
    indices = bytes(lut[k] for k in keys)
    flat = b''.join(bytes(c) for c in palette)
    out = b''.join(flat[3 * i:3 * i + 3] for i in indices)
    return palette, indices, out


def dither(img, palette):
    """Floyd-Steinberg error diffusion of an RGB image onto `palette` -> (indices, rgb pixels).

    Nearest palette colour per 5-bit cell (cached), errors carried in integer arrays row by row."""
    w, h, px = img.w, img.h, img.px
    pal = [tuple(c) for c in palette]
    cache = {}

    def nearest(r, g, b):
        key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)
        k = cache.get(key)
        if k is None:
            cr, cg, cb = (r | 4), (g | 4), (b | 4)
            k = min(range(len(pal)), key=lambda i: (pal[i][0] - cr) ** 2 + (pal[i][1] - cg) ** 2 + (pal[i][2] - cb) ** 2)
            cache[key] = k
        return k

    indices = bytearray(w * h)
    out = bytearray(w * h * 3)
    err = [0] * ((w + 2) * 3)
    for y in range(h):
        nxt = [0] * ((w + 2) * 3)
        row = y * w
        for x in range(w):
            o = 3 * (row + x)
            e = 3 * (x + 1)
            r = min(255, max(0, px[o] + (err[e] >> 4)))
            g = min(255, max(0, px[o + 1] + (err[e + 1] >> 4)))
            b = min(255, max(0, px[o + 2] + (err[e + 2] >> 4)))
            k = nearest(r, g, b)
            c = pal[k]
            indices[row + x] = k
            out[o], out[o + 1], out[o + 2] = c
            for ch, v in ((0, r - c[0]), (1, g - c[1]), (2, b - c[2])):
                if v:
                    err[e + 3 + ch] += 7 * v
                    nxt[e - 3 + ch] += 3 * v
                    nxt[e + ch] += 5 * v
                    nxt[e + 3 + ch] += v
        err = nxt
    return bytes(indices), bytes(out)


def max_channel_error(a, b):
    return max((abs(x - y) for x, y in zip(a, b)), default=0)


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
             'keep_allowed_alpha', 'max_posterize_bits', 'palette', 'dither', 'max_rmse'}
    extra = set(o) - known
    if extra:
        raise ValueError('unknown tex.format_fix options: ' + ', '.join(sorted(extra)))
    out = {'profile': o.get('profile', 'npm'), 'background': o.get('background'), 'dilate': bool(o.get('dilate', False)),
           'max_bytes': o.get('max_bytes', DEFAULT_MAX_BYTES), 'max_side': o.get('max_side'),
           'keep_allowed_alpha': bool(o.get('keep_allowed_alpha', True)),
           'max_posterize_bits': o.get('max_posterize_bits', MAX_POSTERIZE_BITS),
           'palette': bool(o.get('palette', True)), 'dither': bool(o.get('dither', True)),
           'max_rmse': o.get('max_rmse', DEFAULT_MAX_RMSE)}
    if out['profile'] not in ('npm', 'vpm'):
        raise ValueError('profile must be npm or vpm')
    if type(out['max_rmse']) not in (int, float) or not 0 <= out['max_rmse'] <= 1:
        raise ValueError('max_rmse must be a number 0..1 (RMSE of 8-bit channels normalised to 1)')
    out['max_rmse'] = float(out['max_rmse'])
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


def _fit(img, ft, opts, row):
    """Over the limit after lossless RGB: an exact palette (lossless) wins when it fits; otherwise the lossy
    candidates in order (256-colour palette, dithered by default; then least posterisation): the first fitting
    one within `max_rmse` is taken. RMSE above `max_rmse` is a refusal with the measured value (T01: 8 colours,
    RMSE 0.157, was «готово»). Records encoding, colours, max per-channel error, RMSE and every try in `row`;
    None + row['reason'] when nothing fits or passes. Palette only for RGB (alpha keeps RGBA + posterize)."""
    limit = opts['max_bytes']
    tried = ['rgb_lossless {}'.format(row['lossless_bytes'])]
    lossy = []
    if opts['palette'] and img.n == 3:
        exact = exact_palette(img)
        if exact is not None:
            png = encode_palette_png(img.w, img.h, exact[0], exact[1])
            tried.append('palette_exact {}'.format(len(png)))
            if len(png) <= limit:
                row.update(encoding='palette_exact', colours=len(exact[0]), max_channel_error=0, rmse=0.0,
                           tried=tried)
                row['actions'].append('palette_exact_{}'.format(len(exact[0])))
                return png
        else:
            pal, idx, out = quantize(img)
            kind = 'palette_quantized'
            if opts['dither']:
                idx, out = dither(img, pal)
                kind = 'palette_dithered'
            png = encode_palette_png(img.w, img.h, pal, idx)
            err = rmse(img.px, out)
            tried.append('{} {} rmse {}'.format(kind, len(png), err))
            if len(png) <= limit:
                lossy.append((err, kind, png, out, len(pal), '{}_{}'.format(kind, len(pal))))
    best = _least_posterize(img, ft, limit, opts['max_posterize_bits'])
    if best is not None:
        bits, png, px = best
        err = rmse(img.px, px)
        tried.append('rgb_posterize_{}bit {} rmse {}'.format(bits, len(png), err))
        lossy.append((err, 'rgb_posterize', png, px, None, 'posterize_{}bit'.format(bits)))
    else:
        tried.append('posterize up to {} bits'.format(opts['max_posterize_bits']))
    row['tried'] = tried
    if not lossy:
        row['reason'] = '{} still > {} bytes: set options.max_side'.format(', '.join(tried), limit)
        return None
    # Order of Artem's decision (T01, 05.11.2026): palette before posterize; the first one within max_rmse wins,
    # else the refusal names the best measured RMSE.
    passing = [c for c in lossy if c[0] <= opts['max_rmse']]
    err, kind, png, px, colours, action = passing[0] if passing else min(lossy, key=lambda c: (c[0], len(c[2])))
    row.update(encoding=kind, max_channel_error=max_channel_error(img.px, px), rmse=err)
    if colours is not None:
        row['colours'] = colours
    if err > opts['max_rmse']:
        row['reason'] = ('quality: best fitting {} has RMSE {} > max_rmse {} (not written; raise max_rmse or set '
                         'options.max_side)').format(kind, err, opts['max_rmse'])
        row['quality_fail'] = True
        return None
    row['actions'].append(action)
    return png


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
        # palette PNG (colour type 3, 8-bit entries) is a valid delivery format (decision of Artem 05.11.2026)
        if ctype != 3 and (depth != 8 or ctype not in (2, 6)):
            row['actions'].append('to_8bit_rgb')
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
        row['encoding'] = 'copied'
    else:
        png, ft = encode_png(img, with_filter=True)
        row['encoding'] = 'rgb_lossless'
        if len(png) > opts['max_bytes']:
            row['lossless_bytes'] = len(png)
            png = _fit(img, ft, opts, row)
            if png is None:
                return row
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


def format_objects(edit, rows, owners):
    """Report objects when the sources came from selected objects: one entry per owner node, a finding per
    refused texture (`tex_quality`: lossy RMSE over max_rmse; `tex_refused`: any other refusal)."""
    found = {}
    for h, name in sorted({(int(o[0]), str(o[1])) for v in (owners or {}).values() for o in v}):
        found[h] = {'name': name, 'findings': []}
    for r in rows:
        if 'reason' not in r:
            continue
        code = 'tex_quality' if r.get('quality_fail') else 'tex_refused'
        for o in (owners or {}).get(r['source'], ()):
            f = edit.finding(code, (), '{}: {}'.format(os.path.basename(r['source']), r['reason']))
            if f not in found[int(o[0])]['findings']:
                found[int(o[0])]['findings'].append(f)
    return [edit.entry(h, v['name'], v['findings']) for h, v in sorted(found.items())]


def format_report(edit, mode, out, rows, state_hash, opts, written=(), owners=None):
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
    if owners:
        extra['owners'] = {p: [list(o) for o in v] for p, v in owners.items()}
    if mode == 'apply':
        extra['written'] = list(written)
    objects = format_objects(edit, rows, owners)
    return edit.report('tex.format_fix', mode, objects, done, skipped, ambiguous,
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
    known = {'folder', 'address', 'ground', 'slots', 'udim', 'udims', 'sizes', 'colours', 'diffuse_from',
             'on_exists', 'metal_slots'}
    extra = set(o) - known
    if extra:
        raise ValueError('unknown tex.placeholders options: ' + ', '.join(sorted(extra)))
    if 'udim' in o and 'udims' in o:
        raise ValueError('give udim or udims, not both')
    out = {'folder': o.get('folder'), 'address': o.get('address'), 'ground': bool(o.get('ground', False)),
           'slots': o.get('slots', [1]), 'udims': o.get('udims', [o.get('udim', 1001)]),
           'sizes': o.get('sizes', [DEFAULT_PLACEHOLDER_SIZE]),
           'on_exists': o.get('on_exists', 'refuse'), 'diffuse_from': o.get('diffuse_from'),
           'metal_slots': o.get('metal_slots', [])}
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
    if (not isinstance(out['udims'], list) or not out['udims']
            or any(type(u) is not int or not 1001 <= u <= 1100 for u in out['udims'])):
        raise ValueError('udim/udims must be 1001..1100')
    if (not isinstance(out['metal_slots'], list)
            or any(type(s) is not int or s not in out['slots'] for s in out['metal_slots'])):
        raise ValueError('metal_slots must be a list of requested slots')
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


def diffuse_source(path, data, decode=None):
    """(colour, None) or (None, reason) for `diffuse_from`: PNG in the core, System.Drawing formats through
    `decode(path)`; TGA/EXR/PSD/DDS/HDR are refused with a reason (T05: a TGA became a silent grey 128)."""
    ext = os.path.splitext(str(path))[1].lower()
    if data is None:
        return None, 'diffuse_from not found: {}'.format(path)
    try:
        if data[:8] == PNG_SIG:
            img = decode_png(data)[0]
        elif ext in DRAWING_EXTS and decode is not None:
            img = decode(path)
        else:
            return None, ('diffuse_from {} cannot be read ({} is not PNG/JPG/BMP/TIF): Diffuse placeholder skipped, '
                          'not a guessed grey').format(os.path.basename(str(path)), ext or 'no extension')
        return average_colour(img), None
    except Exception as exc:  # noqa: BLE001 - an unreadable source is a reason, never a grey default
        return None, 'diffuse_from {} unreadable: {}'.format(os.path.basename(str(path)), exc)


def average_colour(img):
    """Single average colour (VPM flat_placeholder.single_average_color) over the VISIBLE pixels: alpha-weighted
    for RGBA (a fully transparent pixel weighs 0, T05/T01 counted it as black), rounded half up (T01 floored)."""
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


def placeholder_plan(opts, exists=os.path.exists, sets=None):
    """Planned files: [{map, size, slot, udim, colour, path, owners}] or a reason (refused). os.path.join, never
    string glue. `sets`: [{address, ground, owners:[[handle, name]]}] (one set per address of the selected
    objects); default one set from opts address/ground. A path requested twice in one call (same address, slot,
    UDIM: T02 atlas_builder wrote 6 records into 3 files) is refused the second time, never written twice; ERM
    of a `metal_slots` slot is ERM_METAL; a Diffuse without a readable source (opts `diffuse_reason`) is refused."""
    edit = edit_core()
    rows, planned = [], set()
    many = len(opts['sizes']) > 1
    if sets is None:
        sets = [{'address': opts['address'], 'ground': opts['ground'], 'owners': []}]
    for st in sets:
        for size in opts['sizes']:
            folder = os.path.join(opts['folder'], str(size)) if many else opts['folder']
            for slot in opts['slots']:
                for udim in opts['udims']:
                    for mp in MAPS:
                        name = placeholder_name(st['address'], mp, slot, udim, st['ground'])
                        target = os.path.join(folder, name)
                        colour = opts['colours'][mp]
                        if mp == 'ERM' and slot in opts.get('metal_slots', ()):
                            colour = list(ERM_METAL)
                        row = {'map': mp, 'size': size, 'slot': slot, 'udim': udim, 'colour': colour, 'name': name,
                               'address': st['address'], 'owners': [list(o) for o in st.get('owners', ())]}
                        key = os.path.normcase(os.path.abspath(target))
                        if key in planned:
                            row.update(path=target, code='placeholder_duplicate',
                                       reason='requested twice in this call (UDIM {} slot {}): second refused, '
                                              'nothing overwritten'.format(udim, slot))
                            rows.append(row)
                            continue
                        planned.add(key)
                        if mp == 'Diffuse' and opts.get('diffuse_reason'):
                            row.update(path=target, code='placeholder_source', reason=opts['diffuse_reason'])
                            rows.append(row)
                            continue
                        try:
                            row['path'] = edit.new_path(target, version=opts['on_exists'] == 'version', exists=exists)
                            if row['path'] != target:
                                row['versioned_from'] = target
                        except FileExistsError:
                            row.update(path=target, code='placeholder_exists',
                                       reason='exists, not overwritten (on_exists=refuse): ' + target)
                        rows.append(row)
    return rows


def placeholder_objects(edit, rows):
    """One entry per owner node; a finding per refused file of its set."""
    found = {}
    for r in rows:
        for h, name in r.get('owners') or ():
            found.setdefault(int(h), {'name': name, 'findings': []})
            if 'reason' in r:
                f = edit.finding(r.get('code', 'placeholder_refused'), (), '{}: {}'.format(r['name'], r['reason']))
                if f not in found[int(h)]['findings']:
                    found[int(h)]['findings'].append(f)
    return [edit.entry(h, v['name'], v['findings']) for h, v in sorted(found.items())]


def placeholder_report(edit, mode, opts, rows, state_hash=None, written=()):
    done = [{'path': r['path'], 'map': r['map'], 'size': r['size'], 'colour': r['colour']}
            for r in rows if 'reason' not in r]
    skipped = [edit.skipped(r['path'], r['reason']) for r in rows if 'reason' in r]
    extra = {'options': opts, 'files': rows}
    if mode == 'apply':
        extra['written'] = list(written)
    return edit.report('tex.placeholders', mode, placeholder_objects(edit, rows), done, skipped, [],
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


_SLOT_ROLES = (  # map slot name (property or sub-texmap slot name, any case) -> names_core role
    (('normal', 'bump'), 'normal'),
    (('opacity', 'cutout', 'transparency'), 'opacity'),
    (('rough', 'gloss'), 'roughness'),
    (('metal', 'specular level', 'specularlevel', 'specular_level'), 'metalness'),
    (('emission', 'emissive', 'self-illum', 'selfillum', 'self_illum'), 'emission'),
    (('diffuse', 'base color', 'base_color', 'basecolor', 'albedo'), 'diffuse'),
)


def role_of_slot(slot):
    """names_core map role of a material slot name, else None. Reflection is NOT metalness (T06: renamer V13 gave
    `_m` to specular AND reflection, TexFinder then moved it): an unknown slot has no mask candidate."""
    s = str(slot or '').lower()
    if not s or any(k in s for k in ('reflect', 'coat', 'sheen', 'sss', 'scatter', 'thin', 'aniso', 'weight',
                                     'diff_rough', 'diffuse_rough', 'diffuse rough', 'displace')):
        return None
    for keys, role in _SLOT_ROLES:
        if any(k in s for k in keys):
            return role
    return None


def mask_stems(node, role, udim=None):
    """Lower-case file stems of the project texture mask for an owner object and map role (slot 1), NPM and VPM
    readings (TexFinder idea `T<base><suf>_1.*`, here from the names grammar, not by cutting 2 characters)."""
    if not node or role is None:
        return []
    nc = names_core()
    out = []
    for model in ('npm', 'vpm'):
        obj = nc.parse_object(node, model)
        if isinstance(obj, str):
            continue
        try:
            stem = nc.texture_stem(obj, model, role, 1, udim if model == 'vpm' else None)
        except ValueError:
            stem = None
        if stem and stem.lower() not in out:
            out.append(stem.lower())
    return out


def candidates(path, index, masks=()):
    """Ranked relink candidates for a missing path: same name + extension first (rank 0), then the same
    base name with another extension (rank 1), then files named by the project mask of an owner (rank 2, any
    image extension: .png and .jpg both listed); each path once, sorted within a rank."""
    stem, ext = os.path.splitext(os.path.basename(path))
    me = _norm(path)
    out, seen = [], set()
    for p in index.get(stem.lower(), []):
        key = _norm(p)
        if key in seen or key == me:
            continue
        seen.add(key)
        out.append({'path': p, 'rank': 0 if os.path.splitext(p)[1].lower() == ext.lower() else 1, 'by': 'name'})
    for m in masks:
        for p in index.get(m, []):
            key = _norm(p)
            if key in seen or key == me:
                continue
            seen.add(key)
            out.append({'path': p, 'rank': 2, 'by': 'mask', 'mask': m})
    return sorted(out, key=lambda c: (c['rank'], c['path'].lower()))


def search_folders(paths, map_paths=(), scene_dir='', search=(), isdir=os.path.isdir):
    """(flat, recursive) folders of the candidate index. Default (no `search`) is the map paths themselves: the
    folder of every map path, or its nearest existing parent when that folder is gone, plus the user map paths and
    the scene folder (T06: TexFinder's "123" default found nothing). A relative search folder is refused."""
    flat = set()
    for p in paths:
        if not p or not os.path.isabs(p):
            continue
        folder = os.path.dirname(p)
        flat.add(folder)
        probe = folder
        while probe and not isdir(probe):
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        if probe and probe != folder and isdir(probe):
            flat.add(probe)
    flat |= {f for f in map_paths if f}
    if scene_dir:
        flat.add(scene_dir)
    deep = []
    for f in search or ():
        if not isinstance(f, str) or not f.strip() or not os.path.isabs(f):
            raise ValueError('search folders must be absolute paths (a relative "123" finds nothing): ' + repr(f))
        deep.append(f)
    return sorted(flat), deep


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
        masks = []
        if not r['exists']:
            for o in r['owners']:
                role = o.get('role') or role_of_slot(o.get('slot'))
                for m in mask_stems(o.get('node'), role, r.get('tile')):
                    if m not in masks:
                        masks.append(m)
        r['masks'] = masks
        r['candidates'] = [] if r['exists'] else candidates(r['path'], index, masks)
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


# ---- bitmap enumerator of a material tree (1.0, branch N: owner of the enumerator; used by tex.dilate / vpm.build) --
def material_bitmaps(tree, _top=None, _matid=None, _slot=None):
    """Flat rows of every bitmap below a material tree dict (no pymxs; the glue builds the dict).

    tree: {'name', 'subs': [{'id': int, 'material': tree}], 'maps': [{'slot': str, 'name', 'file': str|None,
    'children': [tree...]}]}. Rows: {'material' (top), 'owner' (sub-material), 'matid' (the Multi/Sub ID the bitmap
    sits under, else None), 'slot', 'role' (role_of_slot), 'map', 'path', 'udim' (names_core.udim_of or None)}.
    A texmap tree nested in a texmap (Mix, Composite, Output) keeps the slot of the outermost material slot."""
    names = names_core()
    rows = []
    top = _top or tree.get('name')
    for sub in tree.get('subs') or ():
        rows += material_bitmaps(sub['material'], top, sub.get('id'), _slot)
    for tm in tree.get('maps') or ():
        slot = _slot if _slot is not None else tm.get('slot')
        if tm.get('file'):
            rows.append({'material': top, 'owner': tree.get('name'), 'matid': _matid, 'slot': slot,
                         'role': role_of_slot(slot), 'map': tm.get('name'), 'path': tm['file'],
                         'udim': names.udim_of(tm['file'])})
        for child in tm.get('children') or ():
            rows += material_bitmaps(child, top, _matid, slot)
    return rows


def bitmaps_by_id(rows):
    """{matid: [rows]} of material_bitmaps rows; maps outside a Multi/Sub are under key None."""
    out = {}
    for r in rows:
        out.setdefault(r['matid'], []).append(r)
    return out
