"""new-case: AGR Tools 1.0 (#1024) grey tile maps and RAL recolour logic, stdlib only. Stub of branch 0; owned by branch L (improve/issue-1024-materials).

Pure logic for `mat_tiles` (mat.tiles, plan mode `file`); no pymxs. Uses edit_core.py for reports, preview hashes and
new paths; the core never takes a host object.

Contract K3 (#1024) + owner answers 06.11.2026 (V12: not only panels/paving/crumb - the set of the materials audit;
UDIM step 3.6 m, a multiple of the 1.2 and 0.6 m modules):

* A grey base map is a MASK PNG (RGB 8 bit): R = body grey (tone of each tile, lerp weight), G = joint coverage
  (0 body .. 255 joint, anti-aliased), B = 0. It is generated in METRES: module, joint, bond (1/2 offset of every
  second course), period. The map holds exactly one period (default 3.6 m) at `px_per_m` (default 1000, owner
  answer 06.11 morning on audit Q1; 1024 or 1137.8 are parameters), so the size is round(period * px_per_m) and the
  effective density is size / period.
* Seamless by construction only when the module divides the period; otherwise the module is fitted to the nearest
  integer count and the stretch is reported (> max_stretch_pct: finding). `seam_levels` measures the step across the
  tile edge against the metric pattern continued past the edge: 0 for a periodic map (norm <= 1 level).
* Recolour by mask (K3): body = lerp(dark RAL, RAL, R / grey_ref) where grey_ref is the measured mean body grey (so
  the mean body colour is the RAL), joint = lerp(dark RAL, RAL, joint_t), pixel = lerp(body, joint, G / 255).
  dark RAL = RAL * dark_factor. Check: CIEDE2000 between the mean body colour and the RAL <= 2.
* ERM from the record fields (R emissive, G roughness, B metallic), solid. Normal (DirectX, green down) from the same
  mask: joints are recessed (height = 1 - G/255; crumb: height from R).

Defects of the recipes this replaces (regression tests in tests/max_tools/test_agr_tools_materials.py):
* #1024 default 4096 px at 1024 px/m = 4.0 m: 4.0 / 0.6 = 6.67 modules -> a visible seam at every tile edge;
* Ground recipe 100x300 with the joint OUTSIDE the module (pitch 105 x 305, tools/materials/ground_recipes.json:17):
  3.6 / 0.105 = 34.3 -> not periodic on the 3.6 m UDIM step;
* brick 250x65 + 10 mm joint (pitch 260 mm): 3.6 / 0.26 = 13.85 -> fitted to 14 (-1.1 %, Q3 answered 06.11:
  tolerance 1.5 % for bricks, per base map `max_stretch_pct`; the global default stays 1.2 %).
"""
import hashlib
import math
import struct
import zlib

PNG_SIG = b'\x89PNG\r\n\x1a\n'
DEFAULTS = {
    'px_per_m': 1000.0,       # owner answer 06.11 morning (audit Q1): 3.6 m = 3600 px, modules whole; was 1024
    'period_m': 3.6,          # owner answer 06.11: UDIM step 3.6 m (crumb: its own 1 m period)
    'max_stretch_pct': 1.2,   # module fitted to the period: allowed stretch (audit Q3: brick -1.1 %)
    'seam_max_levels': 1.0,   # K3 acceptance: edge difference <= 1 level
    'delta_e_max': 2.0,       # K3 acceptance: CIEDE2000 mean tile body vs RAL <= 2
    'dark_factor': 0.55,      # dark RAL = RAL * dark_factor
    'joint_t': 0.35,          # joint colour = lerp(dark, RAL, joint_t)
    'normal_strength': 4.0,
}
# Base maps: metres. tiles: module (x along U, y along V), joint inside the module (centred on module borders),
# bond = offset of every second course in modules, v_joints/h_joints. noise: grain (cell) size.
BASE_MAPS = {
    'facade_600x1200': {'kind': 'tiles', 'module': (0.6, 1.2), 'joint': 0.005, 'bond': 0.0,
                        'source': 'K3: OBR22 facade panels 600x1200, joint 5 mm (OBR22_SHARED_UV_V011.md:12-24)'},
    'ground_100x300': {'kind': 'tiles', 'module': (0.3, 0.1), 'joint': 0.005, 'bond': 0.5,
                       'source': 'K3: Vatutino paving «Gotika» 100x300, joint 5 mm inside the module'},
    'crumb_1x1': {'kind': 'noise', 'grain': 0.004, 'period': 1.0, 'tone_var': 20,
                  'source': 'K3: rubber crumb, seamless 1x1 m'},
    'tile_600x600': {'kind': 'tiles', 'module': (0.6, 0.6), 'joint': 0.005, 'bond': 0.0,
                     'source': 'audit G3: cassette 600x600 (KPP1 PAN-05)'},
    'tile_300x300': {'kind': 'tiles', 'module': (0.3, 0.3), 'joint': 0.004, 'bond': 0.0,
                     'source': 'audit G4: plinth 300x300 (KPP1, PSU275), joint assumed 4 mm'},
    'slab_900x300': {'kind': 'tiles', 'module': (0.9, 0.3), 'joint': 0.005, 'bond': 0.5,
                     'source': 'audit G6: step slab 900x300 (Vatutino)'},
    'brick_250x65': {'kind': 'tiles', 'module': (0.26, 0.075), 'joint': 0.010, 'bond': 0.5, 'max_stretch_pct': 1.5,
                     'source': 'audit B1: brick 250x65, joint 10, half bond (OBR22, FACADES-ATLAS); '
                               'Q3 06.11: 75 mm course step = 48 per 3.6 m, 14 bricks per tile (257.14 mm, -1.1 %), '
                               'stretch tolerance 1.5 %'},
    'panel_v1200': {'kind': 'tiles', 'module': (1.2, None), 'joint': 0.005, 'bond': 0.0, 'h_joints': False,
                    'source': 'audit: sandwich panel, vertical joints 1.2 m (PSU275 1.19 -> 1.2)'},
    'panel_v600': {'kind': 'tiles', 'module': (0.6, None), 'joint': 0.005, 'bond': 0.0, 'h_joints': False,
                   'source': 'audit: cassette, vertical joints 0.6 m (KPP1 7047)'},
}
GREY_BASE = 232
TONE_VAR = 8
OVERRIDES = ('px_per_m', 'period_m', 'module', 'joint', 'bond', 'fit', 'max_stretch_pct', 'grain', 'size_px')


# ---- spec ------------------------------------------------------------------------------------------------------
def _num(v, name, lo=0.0, hi=1e9):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo < v <= hi:
        raise ValueError('{} must be a number in ({}, {}]: {!r}'.format(name, lo, hi, v))
    return float(v)


def spec(name, overrides=None):
    """Resolved generation spec of a base map + its findings [(code, detail)] (module fit, bond parity)."""
    if name not in BASE_MAPS:
        raise ValueError('unknown base map {!r}; one of {}'.format(name, sorted(BASE_MAPS)))
    o = dict(overrides or {})
    bad = set(o) - set(OVERRIDES)
    if bad:
        raise ValueError('unknown tile override(s): {}'.format(sorted(bad)))
    base = BASE_MAPS[name]
    ppm = _num(o.get('px_per_m', DEFAULTS['px_per_m']), 'px_per_m', 16, 8192)
    period = _num(o.get('period_m', base.get('period', DEFAULTS['period_m'])), 'period_m', 0.01, 100)
    fit = bool(o.get('fit', True))
    max_stretch = _num(o.get('max_stretch_pct', base.get('max_stretch_pct', DEFAULTS['max_stretch_pct'])),
                       'max_stretch_pct', 0, 100)
    size = o.get('size_px')
    size = int(round(period * ppm)) if size is None else int(_num(size, 'size_px', 1, 16384))
    findings = []
    s = {'name': name, 'kind': base['kind'], 'period_m': period, 'px_per_m': ppm, 'size_px': size,
         'px_per_m_eff': size / period, 'source': base['source']}
    if base['kind'] == 'noise':
        grain = _num(o.get('grain', base['grain']), 'grain', 0.0001, 1)
        n = period / grain
        cells = int(round(n))
        if abs(n - cells) > 1e-6:
            findings.append(('module_not_dividing', 'grain {} m: {:.4f} cells in {} m'.format(grain, n, period)))
        s.update({'grain': grain, 'cells': max(1, cells), 'tone_var': base.get('tone_var', TONE_VAR)})
        return s, findings
    mx, my = o.get('module', base['module'])
    mx = _num(mx, 'module x', 0.001, 100)
    h_joints = base.get('h_joints', True)
    my = period if my is None else _num(my, 'module y', 0.001, 100)
    joint = _num(o.get('joint', base['joint']), 'joint', 0.0, 1)
    bond = float(o.get('bond', base['bond']))
    if not 0.0 <= bond < 1.0:
        raise ValueError('bond must be 0 <= bond < 1')
    counts, fitted, stretch = [], [], []
    for axis, m in (('x', mx), ('y', my)):
        n = period / m
        k = max(1, int(round(n)))
        exact = abs(n - k) <= 1e-6 * max(1.0, n)
        if exact:
            counts.append(k), fitted.append(period / k), stretch.append(0.0)
            continue
        if not fit:
            findings.append(('module_not_dividing', '{}: {} m modules in {} m = {:.4f} (tile edge cuts a module)'
                             .format(axis, m, period, n)))
            counts.append(n), fitted.append(m), stretch.append(0.0)
            continue
        pct = (period / k - m) / m * 100.0
        counts.append(k), fitted.append(period / k), stretch.append(round(pct, 4))
        if abs(pct) > max_stretch:
            findings.append(('module_stretched', '{}: {} m -> {:.5f} m ({:+.2f} % > {} %)'.format(
                axis, m, period / k, pct, max_stretch)))
    if bond and h_joints and isinstance(counts[1], int) and counts[1] % 2:
        findings.append(('bond_odd_courses', '{} courses with a {} bond: the bond does not repeat'.format(
            counts[1], bond)))
    if joint * 2 >= min(fitted):
        raise ValueError('joint {} m is too wide for module {}'.format(joint, fitted))
    s.update({'module': [fitted[0], fitted[1]], 'module_in': [mx, my], 'counts': counts, 'stretch_pct': stretch,
              'joint': joint, 'bond': bond, 'h_joints': h_joints, 'fit': fit})
    return s, findings


# ---- raster ----------------------------------------------------------------------------------------------------
def _cover(a, b, m, j):
    """Fraction of [a, b) (metres) inside the joint bands [k*m - j/2, k*m + j/2] (any k, also negative)."""
    if j <= 0 or b <= a:
        return 0.0
    h = j / 2.0
    total = 0.0
    k0 = int(math.floor((a - h) / m))
    k1 = int(math.ceil((b + h) / m))
    for k in range(k0, k1 + 1):
        lo, hi = max(a, k * m - h), min(b, k * m + h)
        if hi > lo:
            total += hi - lo
    return min(1.0, total / (b - a))


def _hash(i, j, seed):
    x = (i * 73856093) ^ (j * 19349663) ^ (seed * 83492791)
    x &= 0xffffffff
    x ^= (x >> 13)
    x = (x * 0x5bd1e995) & 0xffffffff
    x ^= (x >> 15)
    return x


def _tone(i, j, seed, var):
    return GREY_BASE + (_hash(i, j, seed) % (2 * var + 1)) - var


def _seed(name):
    return int(hashlib.sha256(name.encode('ascii')).hexdigest()[:8], 16)


class Grey:
    """Row source of a grey mask: rows(y) -> (key, R bytes, G bytes); unique rows are cached by key."""

    def __init__(self, s):
        self.s = s
        self.w = self.h = s['size_px']
        self.k = s['size_px'] / s['period_m']          # px per metre (effective)
        self.seed = _seed(s['name'])
        self._cache = {}

    def _x(self, i):
        return i / self.k, (i + 1) / self.k

    # metric pattern (world, not wrapped): used for the tile and for the seam measure past the edge
    def course(self, y_m):
        return int(math.floor(y_m / self.s['module'][1]))

    def column(self, course, xs):
        """(R, G) values of pixel columns xs on a course (tiles)."""
        s = self.s
        mx = s['module'][0]
        off = (course % 2) * s['bond'] * mx if s['bond'] else 0.0
        ny = s['counts'][1]
        r, g = [], []
        for i in xs:
            a, b = self._x(i)
            g.append(_cover(a - off, b - off, mx, s['joint']))
            ix = int(math.floor(((a + b) / 2 - off) / mx))
            nx = s['counts'][0]
            ix = ix % nx if isinstance(nx, int) else ix
            cy = course % ny if isinstance(ny, int) else course
            r.append(_tone(ix, cy, self.seed, TONE_VAR))
        return r, g

    def row_cover(self, j):
        s = self.s
        if not s['h_joints']:
            return 0.0
        a, b = j / self.k, (j + 1) / self.k
        return _cover(a, b, s['module'][1], s['joint'])

    def row(self, j):
        """(key, R, G) of pixel row j (0 <= j < h, or outside for the seam measure)."""
        s = self.s
        if s['kind'] == 'noise':
            return self._noise_row(j)
        yc = (j + 0.5) / self.k
        course = self.course(yc)
        ny = s['counts'][1]
        ckey = course % ny if isinstance(ny, int) else course
        base = self._cache.get(('c', ckey))
        if base is None:
            r, g = self.column(course, range(self.w))
            base = (bytes(r), [x for x in g], bytes(int(round(x * 255)) for x in g))
            self._cache[('c', ckey)] = base
        cy = self.row_cover(j)
        if cy <= 0:
            return ('c', ckey), base[0], base[2]
        gy = int(round(cy * 255))
        key = ('j', ckey, gy)
        got = self._cache.get(key)
        if got is None:
            got = bytes(int(round((cx + cy - cx * cy) * 255)) for cx in base[1])
            self._cache[key] = got
        return key, base[0], got

    def _noise_row(self, j):
        s = self.s
        cells = s['cells']
        cell = s['period_m'] / cells
        yc = (j + 0.5) / self.k
        cy = int(math.floor(yc / cell)) % cells
        key = ('n', cy)
        got = self._cache.get(key)
        if got is None:
            r = bytes(_tone(int(math.floor(((i + 0.5) / self.k) / cell)) % cells, cy, self.seed, s['tone_var'])
                      for i in range(self.w))
            got = (r, bytes(self.w))
            self._cache[key] = got
        return key, got[0], got[1]

    def edge_column(self, i):
        """R, G of one pixel column i over all rows (also i = -1, i = w: the metric pattern continued)."""
        s = self.s
        rs, gs = [], []
        for j in range(self.h):
            if s['kind'] == 'noise':
                cells = s['cells']
                cell = s['period_m'] / cells
                cx = int(math.floor(((i + 0.5) / self.k) / cell))
                cy = int(math.floor(((j + 0.5) / self.k) / cell))
                cx = cx % cells if abs(s['period_m'] / s['grain'] - cells) < 1e-6 else cx
                rs.append(_tone(cx, cy % cells, self.seed, s['tone_var']))
                gs.append(0)
                continue
            course = self.course((j + 0.5) / self.k)
            r, g = self.column(course, [i])
            cy = self.row_cover(j)
            rs.append(r[0])
            gs.append(int(round((g[0] + cy - g[0] * cy) * 255)))
        return rs, gs


def seam_levels(grey):
    """Mean |step| (levels) between the tile's last column/row and the metric pattern one pixel past the opposite
    edge, max over R/G and both axes. 0 for a periodic map; K3 norm <= 1 level."""
    w, h = grey.w, grey.h
    worst = 0.0
    # columns: tile column w-1 vs pattern column -1 (the column the next tile continues from)
    r_last = [grey.row(j)[1][w - 1] for j in range(h)]
    g_last = [grey.row(j)[2][w - 1] for j in range(h)]
    r_prev, g_prev = grey.edge_column(-1)
    worst = max(worst, _mean_abs(r_last, r_prev), _mean_abs(g_last, g_prev))
    # rows: tile row h-1 vs pattern row -1
    _, r1, g1 = grey.row(h - 1)
    _, r0, g0 = grey.row(-1)
    worst = max(worst, _mean_abs(r1, r0), _mean_abs(g1, g0))
    return round(worst, 4)


def _mean_abs(a, b):
    return sum(abs(int(x) - int(y)) for x, y in zip(a, b)) / max(1, len(a))


def row_keys(grey):
    """[(key, count)] over the tile rows (ordered by first appearance) and the per-row key list."""
    keys, order, count = [], [], {}
    for j in range(grey.h):
        k = grey.row(j)[0]
        keys.append(k)
        if k not in count:
            count[k] = 0
            order.append(k)
        count[k] += 1
    return keys, [(k, count[k]) for k in order]


def body_histogram(grey):
    """Histogram (256) of R over body pixels (G == 0) of the whole tile."""
    keys, counts = row_keys(grey)
    rows = {}
    for j in range(grey.h):
        k = keys[j]
        if k not in rows:
            rows[k] = grey.row(j)
    hist = [0] * 256
    for k, n in counts:
        _, r, g = rows[k]
        for rv, gv in zip(r, g):
            if gv == 0:
                hist[rv] += n
    return hist


def grey_ref(hist):
    total = sum(hist)
    if not total:
        raise ValueError('grey map without body pixels')
    return sum(i * c for i, c in enumerate(hist)) / total


# ---- colour ----------------------------------------------------------------------------------------------------
def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_to_lab(rgb):
    r, g, b = (_lin(float(c)) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.0
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (24389.0 / 27.0 * t + 16.0) / 116.0
    fx, fy, fz = f(x), f(y), f(z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def delta_e2000(rgb1, rgb2):
    """CIEDE2000 between two sRGB colours (D65)."""
    L1, a1, b1 = srgb_to_lab(rgb1)
    L2, a2, b2 = srgb_to_lab(rgb2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2.0
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0
    dL, dC = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dh = 0.0
    else:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
    dH = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2.0))
    Lm, Cmp = (L1 + L2) / 2.0, (C1p + C2p) / 2.0
    if C1p * C2p == 0:
        hm = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hm = (h1p + h2p) / 2.0
    else:
        hm = (h1p + h2p + 360) / 2.0 if h1p + h2p < 360 else (h1p + h2p - 360) / 2.0
    T = (1 - 0.17 * math.cos(math.radians(hm - 30)) + 0.24 * math.cos(math.radians(2 * hm))
         + 0.32 * math.cos(math.radians(3 * hm + 6)) - 0.20 * math.cos(math.radians(4 * hm - 63)))
    dtheta = 30 * math.exp(-(((hm - 275) / 25.0) ** 2))
    Rc = 2 * math.sqrt(Cmp ** 7 / (Cmp ** 7 + 25.0 ** 7))
    Sl = 1 + (0.015 * (Lm - 50) ** 2) / math.sqrt(20 + (Lm - 50) ** 2)
    Sc = 1 + 0.045 * Cmp
    Sh = 1 + 0.015 * Cmp * T
    Rt = -math.sin(math.radians(2 * dtheta)) * Rc
    return math.sqrt((dL / Sl) ** 2 + (dC / Sc) ** 2 + (dH / Sh) ** 2 + Rt * (dC / Sc) * (dH / Sh))


def _clamp(v):
    return 0 if v < 0 else 255 if v > 255 else int(round(v))


def recolour_luts(rgb, ref, dark_factor=None, joint_t=None):
    """Per channel LUT grey -> body colour and the joint colour (K3: lerp(dark RAL, RAL, grey))."""
    df = DEFAULTS['dark_factor'] if dark_factor is None else float(dark_factor)
    jt = DEFAULTS['joint_t'] if joint_t is None else float(joint_t)
    luts, joint = [], []
    for c in rgb:
        dark = c * df
        luts.append(bytes(_clamp(dark + (c - dark) * (g / ref)) for g in range(256)))
        joint.append(_clamp(dark + (c - dark) * jt))
    return luts, joint


def mean_body_colour(hist, luts):
    total = sum(hist)
    return [sum(hist[g] * lut[g] for g in range(256)) / total for lut in luts]


def recolour_row(r, g, luts, joint):
    """RGB row of a recoloured mask row (body LUT, then joint blend where G > 0)."""
    w = len(r)
    out = bytearray(w * 3)
    for c in range(3):
        out[c::3] = r.translate(luts[c])
    if any(g):
        for i, gv in enumerate(g):
            if gv:
                t = gv / 255.0
                o = i * 3
                for c in range(3):
                    out[o + c] = _clamp(out[o + c] + (joint[c] - out[o + c]) * t)
    return bytes(out)


def mask_row(r, g):
    out = bytearray(len(r) * 3)
    out[0::3] = r
    out[1::3] = g
    return bytes(out)


def normal_row(h_prev, h_cur, h_next, strength):
    """DirectX normal row (green down) from three height rows (0..255 bytes), wrap in X."""
    w = len(h_cur)
    out = bytearray(b'\x80\x80\xff' * w)
    s = strength / 255.0
    for i in range(w):
        dx = h_cur[(i + 1) % w] - h_cur[i - 1]
        dy = h_next[i] - h_prev[i]
        if dx == 0 and dy == 0:
            continue
        nx, ny, nz = -dx * s, -dy * s, 1.0
        k = 1.0 / math.sqrt(nx * nx + ny * ny + nz * nz)
        out[i * 3] = _clamp((nx * k * 0.5 + 0.5) * 255)
        out[i * 3 + 1] = _clamp((-ny * k * 0.5 + 0.5) * 255)  # DirectX: green flipped
        out[i * 3 + 2] = _clamp((nz * k * 0.5 + 0.5) * 255)
    return bytes(out)


def height_of(key, r, g, kind):
    """Height row: joints recessed (1 - G); crumb: the grain tone."""
    if kind == 'noise':
        return r
    return bytes(255 - x for x in g)


# ---- PNG (stream, filter 0) --------------------------------------------------------------------------------------
def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def png_stream(w, h, rows, level=6):
    """PNG bytes (RGB 8 bit, filter 0) from an iterable of h rows of w*3 bytes; also sha256 of the raw rows."""
    comp = zlib.compressobj(level)
    raw = hashlib.sha256()
    parts = []
    n = 0
    for row in rows:
        if len(row) != w * 3:
            raise ValueError('row width')
        raw.update(row)
        parts.append(comp.compress(b'\x00' + row))
        n += 1
    if n != h:
        raise ValueError('row count {} != {}'.format(n, h))
    parts.append(comp.flush())
    head = PNG_SIG + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    return head + _chunk(b'IDAT', b''.join(parts)) + _chunk(b'IEND', b''), raw.hexdigest()


def png_readback(data):
    """(w, h, sha256 of raw rows) of a PNG written by png_stream (RGB 8, filter 0 only)."""
    if data[:8] != PNG_SIG:
        raise ValueError('not a PNG')
    pos, idat, ihdr = 8, [], None
    while pos < len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if zlib.crc32(kind + body) & 0xffffffff != struct.unpack('>I', data[pos + 8 + n:pos + 12 + n])[0]:
            raise ValueError('PNG chunk CRC')
        if kind == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            idat.append(body)
        pos += 12 + n
    w, h, depth, ctype = ihdr[:4]
    if depth != 8 or ctype != 2:
        raise ValueError('readback expects RGB 8 bit')
    raw = zlib.decompress(b''.join(idat))
    stride = w * 3 + 1
    if len(raw) != stride * h:
        raise ValueError('PNG data size')
    sha = hashlib.sha256()
    for y in range(h):
        if raw[y * stride] != 0:
            raise ValueError('readback expects filter 0')
        sha.update(raw[y * stride + 1:(y + 1) * stride])
    return w, h, sha.hexdigest()


def solid_rows(w, h, rgb):
    row = bytes(rgb) * w
    return (row for _ in range(h))


# ---- maps of one base / record ---------------------------------------------------------------------------------
def mask_rows(grey):
    for j in range(grey.h):
        _, r, g = grey.row(j)
        yield mask_row(r, g)


def colour_rows(grey, luts, joint):
    cache = {}
    for j in range(grey.h):
        key, r, g = grey.row(j)
        row = cache.get(key)
        if row is None:
            row = recolour_row(r, g, luts, joint)
            cache[key] = row
        yield row


def normal_rows(grey, strength=None):
    st = DEFAULTS['normal_strength'] if strength is None else float(strength)
    kind = grey.s['kind']
    h = grey.h
    heights, cache = {}, {}

    def hrow(j):
        key, r, g = grey.row(j % h)
        got = heights.get(key)
        if got is None:
            got = height_of(key, r, g, kind)
            heights[key] = got
        return key, got
    for j in range(h):
        kp, hp = hrow(j - 1)
        kc, hc = hrow(j)
        kn, hn = hrow(j + 1)
        trip = (kp, kc, kn)
        row = cache.get(trip)
        if row is None:
            row = normal_row(hp, hc, hn, st)
            cache[trip] = row
        yield row


def check_base(name, overrides=None, rals=()):
    """Checks of one base map without writing it: spec findings, seam levels, mean body grey and the CIEDE2000 of the
    mean body colour to each RAL of `rals` ([{code, rgb}]). Returns (spec, grey, result, findings)."""
    s, found = spec(name, overrides)
    grey = Grey(s)
    seam = seam_levels(grey)
    hist = body_histogram(grey)
    ref = grey_ref(hist)
    findings = [{'code': c, 'detail': d} for c, d in found]
    if seam > DEFAULTS['seam_max_levels']:
        findings.append({'code': 'not_seamless', 'detail': 'edge step {} levels > {}'.format(
            seam, DEFAULTS['seam_max_levels'])})
    des = []
    for ral in rals:
        luts, _ = recolour_luts(ral['rgb'], ref)
        mean = mean_body_colour(hist, luts)
        de = round(delta_e2000(mean, ral['rgb']), 4)
        des.append({'ral': ral.get('code'), 'rgb': list(ral['rgb']), 'mean_body': [round(x, 3) for x in mean],
                    'delta_e2000': de})
        if de > DEFAULTS['delta_e_max']:
            findings.append({'code': 'recolour_delta_e', 'detail': 'RAL {}: dE2000 {} > {}'.format(
                ral.get('code'), de, DEFAULTS['delta_e_max'])})
    result = {'base_map': name, 'size_px': s['size_px'], 'period_m': s['period_m'],
              'px_per_m_eff': round(s['px_per_m_eff'], 4), 'seam_levels': seam, 'grey_ref': round(ref, 4),
              'recolour': des, 'unique_rows': len(row_keys(grey)[1])}
    if s['kind'] == 'tiles':
        result.update({'module_m': [round(x, 6) for x in s['module']], 'counts': s['counts'],
                       'stretch_pct': s['stretch_pct'], 'joint_m': s['joint'], 'bond': s['bond']})
    else:
        result.update({'grain_m': s['grain'], 'cells': s['cells']})
    return s, grey, result, findings


def erm_rgb(record):
    return [int(record['emissive']), int(record['roughness']), int(record['metallic'])]


def plug_rows(rgb, size=256):
    return solid_rows(size, size, rgb)
