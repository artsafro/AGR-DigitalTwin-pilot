"""new-case: AGR Tools 0.9 (#979) qa.facade_compare logic, stdlib only, no pymxs (branch C, improve/issue-979-qa).

«лист | ВПМ | НПМ» at one scale and the joint count of each panel. Idea of the pilot TEC26 scripts
(jobs/TEC26-OKS/scripts/render_facades.py, joint_count.py, compare_facades.py; Blender workbench, 200 px/m,
retro pr574): count the joints actually SHOWN on the sheet and on the model, never a spec value. Rewritten without
numpy/PIL/bpy:

* images: PNG (8-bit grey/RGB/RGBA/palette, non-interlaced), BMP (8/24/32-bit uncompressed), PGM/PPM (P5/P6);
  written as PNG (stdlib zlib), always a NEW file (edit_core.new_path + write_new);
* the "render" of a facade is an orthographic rasterisation of the evaluated mesh (snapshot read by facade_max.py)
  at a fixed px/m, in Python: the scene renderer and the viewport are not used at all, so nothing to restore
  (the `apply_atlas_uv` renderer swap, T06, cannot happen);
* joints: on a pixel row, the field is the span of non-background pixels; a joint is a run of background or
  dark (< dark × median field luminance) pixels strictly inside the field. Several rows; the row count is the
  median. Sheet count != model count -> fail.
"""
import math
import struct
import zlib

FACADE_CODES = ('facade_joints', 'facade_unmeasurable')
DEFAULTS = {'px_per_m': 100.0, 'rows': [0.3, 0.5, 0.7], 'dark': 0.8, 'facade': '-y', 'max_px': 6000}
# facade key = outward normal of the facade; viewer on that side. (normal axis, sign, right axis, right sign)
VIEW = {'-y': (1, -1, 0, 1), '+y': (1, 1, 0, -1), '+x': (0, 1, 1, 1), '-x': (0, -1, 1, -1)}
BG = None


class Image:
    """RGB image: width, height, rows of (r, g, b) tuples or None (background / no pixel)."""

    def __init__(self, width, height, fill=None):
        if width <= 0 or height <= 0:
            raise ValueError('image size must be positive')
        self.width, self.height = int(width), int(height)
        self.px = [[fill] * self.width for _ in range(self.height)]

    def lum_row(self, y):
        return [None if p is None else (p[0] + p[1] + p[2]) / 3.0 for p in self.px[y]]


# ---- reading ------------------------------------------------------------------------------------------
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def read_png(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    pos, idat, plte, trns, hdr = 8, b'', None, None, None
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            hdr = struct.unpack('>IIBBBBB', chunk)
        elif kind == b'PLTE':
            plte = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif kind == b'tRNS':
            trns = chunk
        elif kind == b'IDAT':
            idat += chunk
        elif kind == b'IEND':
            break
    if hdr is None:
        raise ValueError('PNG without IHDR')
    w, h, depth, ctype, _, _, interlace = hdr
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 3, 4, 6):
        raise ValueError('PNG: only 8-bit non-interlaced grey/RGB/palette/RGBA supported (depth {}, type {})'.format(
            depth, ctype))
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * bpp
    img = Image(w, h)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                line[i] = (line[i] + _paeth(a, b, c)) & 255
            elif f != 0:
                raise ValueError('PNG: bad filter {}'.format(f))
        prev = line
        row = img.px[y]
        for x in range(w):
            q = line[x * bpp:(x + 1) * bpp]
            if ctype == 0:
                row[x] = (q[0], q[0], q[0])
            elif ctype == 2:
                row[x] = (q[0], q[1], q[2])
            elif ctype == 3:
                alpha = trns[q[0]] if trns and q[0] < len(trns) else 255
                row[x] = tuple(plte[q[0]]) if alpha else None
            elif ctype == 4:
                row[x] = (q[0], q[0], q[0]) if q[1] else None
            else:
                row[x] = (q[0], q[1], q[2]) if q[3] else None
    return img


def read_bmp(data):
    if data[:2] != b'BM':
        raise ValueError('not a BMP')
    off = struct.unpack('<I', data[10:14])[0]
    w, h = struct.unpack('<ii', data[18:26])
    bits, comp = struct.unpack('<HI', data[28:34])
    if comp not in (0, 3) or bits not in (8, 24, 32):
        raise ValueError('BMP: only uncompressed 8/24/32-bit supported')
    pal = []
    if bits == 8:
        ncol = struct.unpack('<I', data[46:50])[0] or 256
        start = 14 + struct.unpack('<I', data[14:18])[0]
        pal = [(data[start + 4 * i + 2], data[start + 4 * i + 1], data[start + 4 * i]) for i in range(ncol)]
    top_down = h < 0
    h = abs(h)
    stride = ((w * bits + 31) // 32) * 4
    img = Image(w, h)
    for r in range(h):
        y = r if top_down else h - 1 - r
        base = off + r * stride
        row = img.px[y]
        for x in range(w):
            if bits == 8:
                row[x] = pal[data[base + x]]
            else:
                k = base + x * (bits // 8)
                row[x] = (data[k + 2], data[k + 1], data[k])
    return img


def read_pnm(data):
    parts, pos = [], 2
    magic = data[:2]
    if magic not in (b'P5', b'P6'):
        raise ValueError('not a binary PGM/PPM')
    while len(parts) < 3:
        while data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b'#':
            while data[pos:pos + 1] not in (b'\n', b''):
                pos += 1
            continue
        start = pos
        while not data[pos:pos + 1].isspace():
            pos += 1
        parts.append(int(data[start:pos]))
    pos += 1
    w, h, maxv = parts
    if maxv != 255:
        raise ValueError('PGM/PPM: only maxval 255')
    ch = 1 if magic == b'P5' else 3
    img = Image(w, h)
    for y in range(h):
        row = img.px[y]
        for x in range(w):
            k = pos + (y * w + x) * ch
            row[x] = (data[k],) * 3 if ch == 1 else tuple(data[k:k + 3])
    return img


def read_image(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return read_png(data)
    if data[:2] == b'BM':
        return read_bmp(data)
    if data[:2] in (b'P5', b'P6'):
        return read_pnm(data)
    raise ValueError('unsupported image (PNG/BMP/PGM/PPM): ' + str(path))


def write_png(img, background=(255, 255, 255)):
    raw = bytearray()
    for row in img.px:
        raw.append(0)
        for p in row:
            raw.extend(background if p is None else p)
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', img.width, img.height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


def write_pgm(img):
    body = bytearray()
    for row in img.px:
        for p in row:
            body.append(255 if p is None else int(round((p[0] + p[1] + p[2]) / 3.0)))
    return b'P5\n%d %d\n255\n' % (img.width, img.height) + bytes(body)


# ---- background of a sheet ----------------------------------------------------------------------------------
def mask_background(img, tol=12):
    """Sheet: the colour of the four corners (paper) becomes background (None). Returns a new image."""
    corners = [img.px[0][0], img.px[0][-1], img.px[-1][0], img.px[-1][-1]]
    corners = [c for c in corners if c is not None]
    out = Image(img.width, img.height)
    if not corners:
        out.px = [list(r) for r in img.px]
        return out
    bg = tuple(sorted(c[k] for c in corners)[len(corners) // 2] for k in range(3))
    for y in range(img.height):
        out.px[y] = [None if p is None or max(abs(p[k] - bg[k]) for k in range(3)) <= tol else p
                     for p in img.px[y]]
    return out


# ---- joints ----------------------------------------------------------------------------------------------
def count_row(lum, dark=DEFAULTS['dark']):
    """Joints on one luminance row (None = background). Field = first..last non-background pixel; joints = runs of
    background or dark pixels strictly inside it (a run touching the field edge is the outline)."""
    idx = [i for i, v in enumerate(lum) if v is not None]
    if len(idx) < 4:
        return {'ok': False, 'reason': 'no field on this row', 'joints': None}
    lo, hi = idx[0], idx[-1]
    vals = sorted(v for v in lum[lo:hi + 1] if v is not None)
    med = vals[len(vals) // 2]
    thr = dark * med
    runs, start = [], None
    for i in range(lo, hi + 1):
        v = lum[i]
        bad = v is None or v < thr
        if bad and start is None:
            start = i
        elif not bad and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, hi + 1))
    inner = [(a, b) for a, b in runs if a > lo and b <= hi]
    return {'ok': True, 'joints': len(inner), 'field_px': [lo, hi + 1],
            'centres_px': [round((a + b - 1) / 2.0, 1) for a, b in inner]}


def count_joints(img, rows=None, dark=DEFAULTS['dark']):
    """Median joint count over row fractions (from the top of the field's bounding box)."""
    ys = [y for y in range(img.height) if any(p is not None for p in img.px[y])]
    if not ys:
        return {'ok': False, 'reason': 'empty image', 'joints': None, 'rows': []}
    top, bottom = ys[0], ys[-1]
    out = []
    for f in rows or DEFAULTS['rows']:
        y = int(round(top + f * (bottom - top)))
        r = count_row(img.lum_row(y), dark)
        r['y'] = y
        r['fraction'] = f
        out.append(r)
    counts = sorted(r['joints'] for r in out if r['ok'])
    if not counts:
        return {'ok': False, 'reason': 'no row with a field', 'joints': None, 'rows': out}
    return {'ok': True, 'joints': counts[len(counts) // 2], 'rows': out,
            'consistent': len(set(counts)) == 1}


# ---- orthographic rasterisation ----------------------------------------------------------------------------
def rasterize(tris, facade='-y', px_per_m=DEFAULTS['px_per_m'], max_px=DEFAULTS['max_px']):
    """tris: [((p0, p1, p2) metres, shade)] where shade is (r, g, b) or a callable (b0, b1, b2) -> (r, g, b)
    (barycentric, for textures). Faces looking away from the viewer are culled; nearest face wins.
    Returns (Image, view) with view = {facade, px_per_m, origin_m (s0, z_top), size_px}."""
    if facade not in VIEW:
        raise ValueError('facade must be one of ' + ', '.join(VIEW))
    na, nsign, ra, rsign = VIEW[facade]
    vis = []
    for (p0, p1, p2), shade in tris:
        e1 = [p1[k] - p0[k] for k in range(3)]
        e2 = [p2[k] - p0[k] for k in range(3)]
        n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
        if n[na] * nsign <= 1e-12:
            continue
        pts = [(p[ra] * rsign, p[2], p[na] * nsign) for p in (p0, p1, p2)]
        vis.append((pts, shade))
    if not vis:
        raise ValueError('no face looks toward facade ' + facade)
    s0 = min(p[0] for pts, _ in vis for p in pts)
    s1 = max(p[0] for pts, _ in vis for p in pts)
    z0 = min(p[1] for pts, _ in vis for p in pts)
    z1 = max(p[1] for pts, _ in vis for p in pts)
    w = int(math.ceil((s1 - s0) * px_per_m)) + 1
    h = int(math.ceil((z1 - z0) * px_per_m)) + 1
    if w > max_px or h > max_px:
        raise ValueError('facade raster {}x{} px > max_px {} (lower px_per_m)'.format(w, h, max_px))
    img = Image(w, h)
    depth = [[-math.inf] * w for _ in range(h)]
    for pts, shade in vis:
        xy = [((p[0] - s0) * px_per_m, (z1 - p[1]) * px_per_m, p[2]) for p in pts]
        (x0, y0, d0), (x1, y1, d1), (x2, y2, d2) = xy
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        xa, xb = max(0, int(math.floor(min(x0, x1, x2)))), min(w - 1, int(math.ceil(max(x0, x1, x2))))
        ya, yb = max(0, int(math.floor(min(y0, y1, y2)))), min(h - 1, int(math.ceil(max(y0, y1, y2))))
        flat = shade if not callable(shade) else None
        for py in range(ya, yb + 1):
            cy = py + 0.5
            drow, prow = depth[py], img.px[py]
            for px in range(xa, xb + 1):
                cx = px + 0.5
                b0 = ((y1 - y2) * (cx - x2) + (x2 - x1) * (cy - y2)) / den
                b1 = ((y2 - y0) * (cx - x2) + (x0 - x2) * (cy - y2)) / den
                b2 = 1.0 - b0 - b1
                if b0 < -1e-9 or b1 < -1e-9 or b2 < -1e-9:
                    continue
                d = b0 * d0 + b1 * d1 + b2 * d2
                if d <= drow[px]:
                    continue
                drow[px] = d
                prow[px] = flat if flat is not None else shade(b0, b1, b2)
    view = {'facade': facade, 'px_per_m': px_per_m, 'origin_m': [round(s0, 6), round(z1, 6)], 'size_px': [w, h],
            'width_m': round(s1 - s0, 6), 'height_m': round(z1 - z0, 6)}
    return img, view


def texture_shader(img, uvs, tint=None):
    """Callable shade for a textured triangle: uvs = ((u0,v0),(u1,v1),(u2,v2)), wrap-around, nearest texel."""
    def shade(b0, b1, b2):
        u = b0 * uvs[0][0] + b1 * uvs[1][0] + b2 * uvs[2][0]
        v = b0 * uvs[0][1] + b1 * uvs[1][1] + b2 * uvs[2][1]
        x = int((u % 1.0) * img.width) % img.width
        y = int((1.0 - (v % 1.0)) * img.height) % img.height
        p = img.px[y][x]
        return p if p is not None else (tint or (128, 128, 128))
    return shade


# ---- one scale, side by side --------------------------------------------------------------------------------
def resample(img, factor):
    """Nearest-neighbour scale by `factor` (target px/m / source px/m)."""
    if factor <= 0 or not math.isfinite(factor):
        raise ValueError('bad resample factor')
    w, h = max(1, int(round(img.width * factor))), max(1, int(round(img.height * factor)))
    out = Image(w, h)
    for y in range(h):
        sy = min(img.height - 1, int(y / factor))
        src = img.px[sy]
        out.px[y] = [src[min(img.width - 1, int(x / factor))] for x in range(w)]
    return out


def compose(panels, gap=16, frame=4):
    """panels: [(Image, ok)] at one px/m, bottoms aligned; a red frame marks a panel whose count differs."""
    h = max(p.height for p, _ in panels) + 2 * frame
    w = sum(p.width + 2 * frame for p, _ in panels) + gap * (len(panels) + 1)
    out = Image(w, h + 2 * gap, fill=(255, 255, 255))
    x = gap
    for p, ok in panels:
        top = gap + (h - 2 * frame - p.height)
        colour = (0, 160, 0) if ok else (220, 0, 0)
        for yy in range(top - frame, top + p.height + frame):
            for xx in range(x, x + p.width + 2 * frame):
                inside = top <= yy < top + p.height and x + frame <= xx < x + frame + p.width
                if not inside:
                    out.px[yy][xx] = colour
        for yy in range(p.height):
            src = p.px[yy]
            dst = out.px[top + yy]
            for xx in range(p.width):
                dst[x + frame + xx] = src[xx] if src[xx] is not None else (255, 255, 255)
        x += p.width + 2 * frame + gap
    return out


def compare(sheet, sheet_px_per_m, models, px_per_m, rows=None, dark=DEFAULTS['dark']):
    """sheet: Image (paper background masked), models: {'vpm': Image, 'npm': Image|None} rendered at px_per_m.
    Returns {'sheet': count, 'vpm': count, 'npm': count, 'ok': bool, 'panels': [(Image, ok)]}."""
    if not sheet_px_per_m or sheet_px_per_m <= 0:
        raise ValueError('sheet_px_per_m must be positive (scale of the sheet image)')
    s = count_joints(sheet, rows, dark)
    out = {'sheet': s, 'models': {}, 'ok': True, 'reasons': []}
    if not s['ok']:
        out['ok'] = False
        out['reasons'].append('лист: ' + s['reason'])
    panels = [(resample(sheet, px_per_m / sheet_px_per_m), s['ok'])]
    for key in ('vpm', 'npm'):
        img = models.get(key)
        if img is None:
            continue
        c = count_joints(img, rows, dark)
        good = c['ok'] and s['ok'] and c['joints'] == s['joints']
        out['models'][key] = c
        if not good:
            out['ok'] = False
            out['reasons'].append('{}: швов {} ≠ лист {}'.format(key.upper(), c.get('joints'), s.get('joints'))
                                  if c['ok'] else '{}: {}'.format(key.upper(), c['reason']))
        panels.append((img, good))
    if not out['models']:
        raise ValueError('qa.facade_compare: no model panel (VPM/NPM)')
    panels[0] = (panels[0][0], out['ok'] or all(c.get('joints') == s.get('joints') for c in out['models'].values()))
    out['panels'] = panels
    return out


def facade_options(options):
    opts = {'px_per_m': DEFAULTS['px_per_m'], 'rows': list(DEFAULTS['rows']), 'dark': DEFAULTS['dark'],
            'facade': DEFAULTS['facade'], 'max_px': DEFAULTS['max_px'], 'sheet': None, 'sheet_px_per_m': None,
            'sheets': None, 'npm': None, 'out': None}
    for k, v in (options or {}).items():
        if k not in opts:
            raise ValueError('unknown qa.facade_compare option: ' + k)
        opts[k] = v
    for k in ('px_per_m', 'dark', 'max_px'):
        if isinstance(opts[k], bool) or not isinstance(opts[k], (int, float)) or not opts[k] > 0:
            raise ValueError('qa.facade_compare: {} must be a positive number'.format(k))
    if opts['facade'] not in VIEW:
        raise ValueError('facade must be one of ' + ', '.join(VIEW))
    if not isinstance(opts['rows'], list) or not opts['rows'] or not all(
            isinstance(f, (int, float)) and 0 <= f <= 1 for f in opts['rows']):
        raise ValueError('rows: list of fractions 0..1')
    sheets = {}
    if opts['sheets'] is not None:
        if not isinstance(opts['sheets'], dict) or not opts['sheets']:
            raise ValueError('sheets: {object name: {path, px_per_m}}')
        for name, spec in opts['sheets'].items():
            if not isinstance(spec, dict) or set(spec) - {'path', 'px_per_m', 'facade'} or 'path' not in spec \
                    or 'px_per_m' not in spec:
                raise ValueError('sheets[{}]: {{path, px_per_m[, facade]}}'.format(name))
            sheets[name] = spec
    elif opts['sheet'] is not None:
        if not opts['sheet_px_per_m']:
            raise ValueError('sheet_px_per_m is required with sheet')
        sheets['*'] = {'path': opts['sheet'], 'px_per_m': opts['sheet_px_per_m']}
    else:
        raise ValueError('qa.facade_compare needs sheet (+ sheet_px_per_m) or sheets {object: {path, px_per_m}}')
    if opts['npm'] is not None and not isinstance(opts['npm'], dict):
        raise ValueError('npm: {VPM object name: NPM object name}')
    opts['sheets'] = sheets
    return opts


def facade_report(edit, results, state_hash, skipped=(), extra=None):
    """results: [{handle, name, compare (from compare()), image, view}] -> read-only report, one object per facade."""
    if not results and not skipped:
        raise ValueError('qa.facade_compare: empty target set')
    objects, rows = [], []
    for r in results:
        c = r['compare']
        fl = []
        if not c['ok']:
            unmeasurable = not c['sheet']['ok'] or any(not m['ok'] for m in c['models'].values())
            fl.append(edit.finding('facade_unmeasurable' if unmeasurable else 'facade_joints', (),
                                   '; '.join(c['reasons'])))
        objects.append(edit.entry(r['handle'], r['name'], fl))
        rows.append({'name': r['name'], 'sheet': c['sheet'].get('joints'),
                     'vpm': c['models'].get('vpm', {}).get('joints'), 'npm': c['models'].get('npm', {}).get('joints'),
                     'ok': c['ok'], 'image': r.get('image'), 'view': r.get('view'), 'sheet_path': r.get('sheet_path'),
                     'rows': {'sheet': c['sheet'].get('rows'),
                              **{k: v.get('rows') for k, v in c['models'].items()}}})
    if not objects:
        raise ValueError('qa.facade_compare: nothing compared: ' + '; '.join(s['reason'] for s in skipped))
    plan = {'read_only': True, 'facades': rows, 'renderer_used': False,
            'note': 'модель растеризуется из снимка сетки (px/м фиксирован); рендерер сцены и вьюпорт не используются'}
    plan.update(extra or {})
    return edit.report('qa.facade_compare', 'preview', objects, [r['image'] for r in results if r.get('image')],
                       list(skipped), [], state_hash=state_hash, extra=plan)
