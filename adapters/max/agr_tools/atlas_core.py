"""new-case: stdlib NPM atlas UV layout for the AGR Tools button.

Mirrors tools/materials/npm_atlas_udim.py pack() for flat Kd materials and
in-memory map_Kd images, including diffuse alpha, dissolve and a separate
opacity plane, without numpy or PIL. The returned image is the same atlas the
remapped UVs address. Padding stays the normative minimum of 8 px. An unmapped
material, a tile crossing, a non-finite coordinate, an opacity map without
map_Kd and an empty mesh are errors. Every face is remapped or named in
``dropped``; this layout drops none (it raises instead).
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

ATLAS_SIZES = (1024, 2048)
PADDING_MIN_PX = 8
GROUND_MIN, GROUND_MAX = 10.0, 40.0
BACKGROUND = (90, 90, 90)
EPS = 1e-6
# 0.9 (#979, branch B). Profiles of pack(): 'npm' (the 0.2 sizes) and 'groundel' (one set <= 512, A101AGRLP.ms
# :1374 `BitmapCorrectTest 512`, sha256 86c43d4d…6926, measured in lab L06). shrink=True takes the smallest
# square of the profile that holds the same cells at the same texel (VPM_to_NPM.ms sha256 613925939568…10e8, T06:
# the atlas was not reduced to its content, 6.6 % fill).
PROFILE_SIZES = {'npm': (256, 512, 1024, 2048), 'groundel': (128, 256, 512)}
GROUNDEL_MAX = 512


class AtlasError(ValueError):
    """Input the packer refuses, naming the element."""


class AtlasFitError(AtlasError):
    """The cells do not fit the largest allowed atlas at the lowest allowed texel; `calc` holds the numbers."""

    def __init__(self, message, calc):
        super().__init__(message)
        self.calc = calc


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _mul(a, s):
    return tuple(x * s for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _svd_desc(m00, m01, m10, m11):
    """Singular values of a 2x2 matrix, largest first. Float64, no numpy."""
    p = m00 * m00 + m10 * m10
    q = m00 * m01 + m10 * m11
    r = m01 * m01 + m11 * m11
    tr = p + r
    det = p * r - q * q
    disc = math.sqrt(max(0.0, tr * tr - 4.0 * det))
    return (math.sqrt(max(0.0, (tr + disc) / 2.0)), math.sqrt(max(0.0, (tr - disc) / 2.0)))


def _plane_offsets(pts):
    n = (0.0, 0.0, 0.0)
    for i, p in enumerate(pts):
        n = _add(n, _cross(p, pts[(i + 1) % len(pts)]))
    c = tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))
    nl = _norm(n)
    if nl <= 2e-12:
        return [(0.0, 0.0) for _ in pts]
    n = _mul(n, 1.0 / nl)
    x = None
    for i, p in enumerate(pts):
        e = _sub(pts[(i + 1) % len(pts)], p)
        e = _sub(e, _mul(n, _dot(e, n)))
        en = _norm(e)
        if en > 1e-12:
            x = _mul(e, 1.0 / en)
            break
    if x is None:
        return [(0.0, 0.0) for _ in pts]
    y = _cross(n, x)
    out = []
    for p in pts:
        d = _sub(p, c)
        out.append((_dot(d, x), _dot(d, y)))
    return out


def _face_texel(pts_m, px):
    lo, hi = math.inf, 0.0
    for i in range(1, len(pts_m) - 1):
        e1, e2 = _sub(pts_m[i], pts_m[0]), _sub(pts_m[i + 1], pts_m[0])
        l1 = _norm(e1)
        n = _cross(e1, e2)
        an = _norm(n)
        if l1 <= 1e-12 or an <= 2e-12:
            continue
        x = _mul(e1, 1.0 / l1)
        y = _mul(_cross(n, x), 1.0 / an)
        g00, g01 = l1, _dot(e2, x)
        g10, g11 = 0.0, _dot(e2, y)
        det = g00 * g11 - g01 * g10
        if abs(det) <= 1e-30:
            continue
        ig00, ig01 = g11 / det, -g01 / det
        ig10, ig11 = -g10 / det, g00 / det
        q0, q1 = _sub(px[i], px[0]), _sub(px[i + 1], px[0])
        m00 = q0[0] * ig00 + q1[0] * ig10
        m01 = q0[0] * ig01 + q1[0] * ig11
        m10 = q0[1] * ig00 + q1[1] * ig10
        m11 = q0[1] * ig01 + q1[1] * ig11
        smax, smin = _svd_desc(m00, m01, m10, m11)
        lo, hi = min(lo, smin), max(hi, smax)
    if hi == 0.0 and lo == math.inf:
        return None
    return (lo, hi)


def _same_path(a, b):
    ra, rb = os.path.normcase(str(Path(a).resolve())), os.path.normcase(str(Path(b).resolve()))
    return ra == rb


def _finite3(p, what, index):
    if not isinstance(p, (tuple, list)) or len(p) < 2:
        raise AtlasError(f"partial {what} {index}: {p!r}")
    coords = p[:3] if what == 'vertex' else p[:2]
    if what == 'vertex' and len(p) < 3:
        raise AtlasError(f"partial {what} {index}: {p!r}")
    for c in coords:
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c):
            raise AtlasError(f"non-finite {what} coordinate")
    return tuple(float(c) for c in coords)


def _src_px(uvs, face_uv, rec):
    pts = []
    for t in face_uv:
        u, v = uvs[t]
        pts.append(((u - rec['tu']) * rec['W'], (1.0 - (v - rec['tv'])) * rec['H']))
    return pts


def _cell(rec, pad, k):
    rec['k'] = k
    gap = pad + 1
    rec['dw'] = int(math.ceil((rec['x1'] - rec['x0']) * k)) + 2 * gap
    rec['dh'] = int(math.ceil((rec['y1'] - rec['y0']) * k)) + 2 * gap
    rec['bx0'] = rec['x0'] - gap / k
    rec['by0'] = rec['y0'] - gap / k


def _plug_extent(vertices, faces, rec, mode, plug_px_m, cell_px, unit_m):
    offs, ext_x, ext_y = {}, 0.0, 0.0
    for f in rec['faces']:
        pts_m = [_mul(vertices[i], unit_m) for i in faces[f]]
        if mode == 'ground':
            o = [_mul(p, plug_px_m) for p in _plane_offsets(pts_m)]
        else:
            src = rec['src_px'][f]
            size = max(max(p[k] for p in src) - min(p[k] for p in src) for k in (0, 1))
            mean = (sum(p[0] for p in src) / len(src), sum(p[1] for p in src) / len(src))
            scale = cell_px / size if size > 0 else 0.0
            o = [((p[0] - mean[0]) * scale, (p[1] - mean[1]) * scale) for p in src]
        offs[f] = o
        ext_x = max(ext_x, 2 * max(abs(p[0]) for p in o))
        ext_y = max(ext_y, 2 * max(abs(p[1]) for p in o))
    return ext_x, ext_y, offs


def _shelf(recs, size):
    x = y = shelf = 0
    for rec in sorted(recs, key=lambda q: (-q['dh'], -q['dw'], q['name'])):
        if rec['dw'] > size or rec['dh'] > size:
            return False
        if x + rec['dw'] > size:
            x, y, shelf = 0, y + shelf, 0
        if y + rec['dh'] > size:
            return False
        rec['cx'], rec['cy'] = x, y
        x += rec['dw']
        shelf = max(shelf, rec['dh'])
    return True


def _byte(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise AtlasError(f"material {name!r}: pixel {value!r} outside 0..255")
    return value


def _rgb_plane(name, rgb):
    if not isinstance(rgb, list) or not rgb or not isinstance(rgb[0], list) or not rgb[0]:
        raise AtlasError(f"material {name!r}: partial bitmap")
    width = len(rgb[0])
    out = []
    for row in rgb:
        if not isinstance(row, list) or len(row) != width:
            raise AtlasError(f"material {name!r}: partial bitmap")
        parsed = []
        for px in row:
            if not isinstance(px, (tuple, list)) or len(px) != 3:
                raise AtlasError(f"material {name!r}: partial bitmap")
            parsed.append(tuple(_byte(c, name) for c in px))
        out.append(tuple(parsed))
    return out


def _scalar_plane(name, plane, width, height, what):
    if not isinstance(plane, list) or len(plane) != height:
        raise AtlasError(f"material {name!r}: {what}")
    out = []
    for row in plane:
        if not isinstance(row, list) or len(row) != width:
            raise AtlasError(f"material {name!r}: {what}")
        out.append(tuple(_byte(v, name) for v in row))
    return out


def _flat_rgb(rgb):
    sample = rgb[0][0]
    return all(px == sample for row in rgb for px in row)


def _flat_alpha(alpha):
    sample = alpha[0][0]
    return all(v == sample for row in alpha for v in row)


def _scale_alpha(alpha, width, height, dissolve):
    out = []
    for y in range(height):
        row = []
        for x in range(width):
            base = 255.0 if alpha is None else float(alpha[y][x])
            row.append(int(max(0, min(255, round(base * dissolve)))))
        out.append(tuple(row))
    return out


def _classify_material(name, spec, dissolve):
    """Same plug / alpha rules as npm_atlas_udim.analyze. Opacity without map_Kd is an error."""
    if not isinstance(spec, dict):
        raise AtlasError(f"material {name!r}: dissolve has no entry")
    rgb = spec.get('rgb')
    opacity = spec.get('opacity')
    if rgb is not None:
        rgb = _rgb_plane(name, rgb)
        height, width = len(rgb), len(rgb[0])
        alpha = spec.get('alpha')
        if alpha is not None:
            alpha = _scalar_plane(name, alpha, width, height, 'diffuse alpha size does not match map_Kd')
            if _flat_alpha(alpha) and alpha[0][0] == 255:
                alpha = None
        if opacity is not None:
            if alpha is not None:
                raise AtlasError(f"material {name!r}: both diffuse alpha and map_d opacity")
            if spec.get('opacity_alpha'):
                raise AtlasError(f"material {name!r}: opacity map must be grey, same size as diffuse")
            alpha = _scalar_plane(name, opacity, width, height,
                                  'opacity map must be grey, same size as diffuse')
        if dissolve < 1.0:
            alpha = _scale_alpha(alpha, width, height, dissolve)
        flat_a = alpha is None or _flat_alpha(alpha)
        if _flat_rgb(rgb) and flat_a:
            return {'plug': True, 'color': rgb[0][0], 'W': width, 'H': height,
                    'plug_alpha': 255 if alpha is None else alpha[0][0], 'rgb': None, 'alpha': None}
        return {'plug': False, 'color': rgb[0][0], 'W': width, 'H': height, 'plug_alpha': 255,
                'rgb': rgb, 'alpha': alpha}
    if opacity is not None or spec.get('alpha') is not None:
        raise AtlasError(f"material {name!r}: map_d without map_Kd is not supported")
    if spec.get('color') is not None:
        color = spec['color']
        if not isinstance(color, (tuple, list)) or len(color) != 3:
            raise AtlasError(f"material {name!r}: neither map_Kd nor Kd")
        return {'plug': True, 'color': tuple(_byte(c, name) for c in color), 'W': 1, 'H': 1,
                'plug_alpha': int(round(255 * dissolve)), 'rgb': None, 'alpha': None}
    raise AtlasError(f"material {name!r}: neither map_Kd nor Kd")


# Pillow 12 ImagingResample: 8-bit result, two guard bits, half-up fixed coefficients.
_PRECISION_BITS = 22
_PRECISION = 1 << _PRECISION_BITS
_COEFF_BIAS = 1 << (_PRECISION_BITS - 1)


def _sinc(x):
    if x == 0.0:
        return 1.0
    x *= math.pi
    return math.sin(x) / x


def _lanczos3(x):
    if -3.0 <= x < 3.0:
        return _sinc(x) * _sinc(x / 3.0)
    return 0.0


def _clip8(value):
    shifted = value >> _PRECISION_BITS
    if shifted < 0:
        return 0
    if shifted > 255:
        return 255
    return shifted


def _pillow_coeffs(in_size, out_size, box0, box1):
    """Coefficient window from Pillow's precompute_coeffs + normalize_coeffs_8bpc."""
    scale = (box1 - box0) / out_size
    filterscale = scale if scale > 1.0 else 1.0
    support = 3.0 * filterscale
    inv = 1.0 / filterscale
    columns = []
    for xx in range(out_size):
        center = box0 + (xx + 0.5) * scale
        xmin = int(center - support + 0.5)
        if xmin < 0:
            xmin = 0
        xmax = int(center + support + 0.5)
        if xmax > in_size:
            xmax = in_size
        count = xmax - xmin
        weights, total = [], 0.0
        for x in range(count):
            weight = _lanczos3((x + xmin - center + 0.5) * inv)
            weights.append(weight)
            total += weight
        if total != 0.0:
            weights = [weight / total for weight in weights]
        fixed = []
        for weight in weights:
            if weight < 0:
                fixed.append(int(-0.5 + weight * _PRECISION))
            else:
                fixed.append(int(0.5 + weight * _PRECISION))
        columns.append((xmin, fixed))
    return columns


def _resize_lanczos(plane, box, out_w, out_h, channels):
    """Separable Lanczos-3. Horizontal 8-bit clip, then vertical, matching PIL."""
    height, width = len(plane), len(plane[0])
    xw = _pillow_coeffs(width, out_w, box[0], box[2])
    yw = _pillow_coeffs(height, out_h, box[1], box[3])
    horizontal = []
    for y in range(height):
        row = []
        for xmin, coeffs in xw:
            if channels == 1:
                acc = _COEFF_BIAS
                for i, coeff in enumerate(coeffs):
                    acc += plane[y][xmin + i] * coeff
                row.append(_clip8(acc))
            else:
                acc = [_COEFF_BIAS, _COEFF_BIAS, _COEFF_BIAS]
                for i, coeff in enumerate(coeffs):
                    pixel = plane[y][xmin + i]
                    acc[0] += pixel[0] * coeff
                    acc[1] += pixel[1] * coeff
                    acc[2] += pixel[2] * coeff
                row.append(tuple(_clip8(v) for v in acc))
        horizontal.append(row)
    out = []
    for xmin, coeffs in yw:
        row = []
        for x in range(out_w):
            if channels == 1:
                acc = _COEFF_BIAS
                for i, coeff in enumerate(coeffs):
                    acc += horizontal[xmin + i][x] * coeff
                row.append(_clip8(acc))
            else:
                acc = [_COEFF_BIAS, _COEFF_BIAS, _COEFF_BIAS]
                for i, coeff in enumerate(coeffs):
                    sample = horizontal[xmin + i][x]
                    acc[0] += sample[0] * coeff
                    acc[1] += sample[1] * coeff
                    acc[2] += sample[2] * coeff
                row.append(tuple(_clip8(v) for v in acc))
        out.append(row)
    return out


def _crop_resize(plane, channels, rec):
    bw, bh = rec['dw'] / rec['k'], rec['dh'] / rec['k']
    ix0, iy0 = math.floor(rec['bx0']) - 2, math.floor(rec['by0']) - 2
    ix1 = math.ceil(rec['bx0'] + bw) + 2
    iy1 = math.ceil(rec['by0'] + bh) + 2
    height, width = len(plane), len(plane[0])
    sub = []
    for y in range(iy0, iy1):
        yy = y % height
        sub.append(tuple(plane[yy][x % width] for x in range(ix0, ix1)))
    box = (rec['bx0'] - ix0, rec['by0'] - iy0, rec['bx0'] - ix0 + bw, rec['by0'] - iy0 + bh)
    return _resize_lanczos(sub, box, rec['dw'], rec['dh'], channels)


def _paste(buf, size, channels, x0, y0, patch):
    for y, row in enumerate(patch):
        base = ((y0 + y) * size + x0) * channels
        if channels == 1:
            buf[base:base + len(row)] = bytes(row)
        else:
            span = bytearray(len(row) * 3)
            for i, px in enumerate(row):
                span[i * 3:i * 3 + 3] = bytes(px)
            buf[base:base + len(span)] = span


def _raster(recs, size):
    """Diffuse RGB plus a separate opacity plane. UVs address this image, not the source bitmap."""
    rgb = bytearray((BACKGROUND[0], BACKGROUND[1], BACKGROUND[2])) * (size * size)
    alpha = bytearray((255,)) * (size * size)
    any_alpha = False
    for rec in recs:
        x0, y0, dw, dh = rec['cx'], rec['cy'], rec['dw'], rec['dh']
        if rec['plug']:
            patch = [rec['color']] * dw
            for y in range(dh):
                _paste(rgb, size, 3, x0, y0 + y, [patch])
            if rec['plug_alpha'] != 255:
                any_alpha = True
                span = bytes((rec['plug_alpha'],)) * dw
                for y in range(dh):
                    base = ((y0 + y) * size + x0)
                    alpha[base:base + dw] = span
        else:
            _paste(rgb, size, 3, x0, y0, _crop_resize(rec['rgb'], 3, rec))
            if rec['alpha'] is not None:
                any_alpha = True
                _paste(alpha, size, 1, x0, y0, _crop_resize(rec['alpha'], 1, rec))
    return {'rgb': bytes(rgb), 'alpha': bytes(alpha) if any_alpha else None, 'size': size}


def _bounds(rec):
    vals = list(rec['dens'].values())
    mean = sorted(math.sqrt(a * b) for a, b in vals)
    smin = min(a for a, _ in vals)
    smax = max(b for _, b in vals)
    lo = GROUND_MIN * 1.03 / smin if smin > 1e-9 else math.inf
    return mean[(len(mean) - 1) // 2], lo, GROUND_MAX * 0.97 / smax


def _fit_calc(built, tex, size, pad, mode):
    """Numbers of a layout that does not fit: cells at the lowest allowed texel against the atlas area."""
    rows = []
    for rec in built:
        if mode == 'ground' and not rec['plug']:
            med, lo, hi = _bounds(rec)
            k = max(lo, min(hi, GROUND_MIN * 1.05 / med))
            _cell(rec, pad, k)
            texel = round(med * k, 3)
        else:
            texel = None
        rows.append({'material': rec['name'], 'cell_px': [rec['dw'], rec['dh']], 'texel_px_per_m': texel})
    need = sum(r['cell_px'][0] * r['cell_px'][1] for r in rows)
    return {'atlas_px': size, 'atlas_area_px2': size * size, 'cells_area_px2': need, 'padding_px': pad,
            'lowest_texel_px_per_m': GROUND_MIN * 1.05 if mode == 'ground' else None,
            'widest_cell_px': max(max(r['cell_px']) for r in rows) if rows else 0, 'cells': rows}


def pack(vertices, uvs, faces, face_uvs, face_materials, materials, *, mode='ground', size=2048,
         pad=PADDING_MIN_PX, target=35.0, plug_px_m=12.5, plug_cell=16, unit_m=1.0, profile=None, shrink=False):
    """Return remapped UVs, UDIM tiles and cell boxes. Raises AtlasError; never edits inputs.

    profile None keeps the 0.2 contract (sizes 1024/2048, no shrink). profile 'npm' / 'groundel' (0.9) allows the
    sizes of PROFILE_SIZES; shrink=True then returns the smallest of them that holds the same cells at the same
    texel. A layout that does not fit raises AtlasFitError with the calculation (`calc`)."""
    if mode not in ('ground', 'oks'):
        raise AtlasError(f"mode must be ground or oks, got {mode!r}")
    if profile is not None and profile not in PROFILE_SIZES:
        raise AtlasError(f"profile must be one of {sorted(PROFILE_SIZES)}, got {profile!r}")
    allowed = ATLAS_SIZES if profile is None else PROFILE_SIZES[profile]
    if size not in allowed:
        raise AtlasError(f"atlas size must be one of {allowed}, got {size}")
    if not isinstance(pad, int) or isinstance(pad, bool) or pad < PADDING_MIN_PX:
        raise AtlasError(f"padding must be an integer >= {PADDING_MIN_PX} px, got {pad}")
    for value, what in ((target, 'target'), (plug_px_m, 'plug texel'), (unit_m, 'unit_m')):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise AtlasError(f"{what} must be a positive finite number, got {value}")
    if unit_m <= 0:
        raise AtlasError(f"unit_m must be a positive finite number, got {unit_m}")
    for value, what in ((target, 'target'), (plug_px_m, 'plug texel')):
        if not GROUND_MIN <= value <= GROUND_MAX:
            raise AtlasError(f"{what} {value} px/m outside the Ground band {GROUND_MIN}..{GROUND_MAX}")
    if not faces:
        raise AtlasError('mesh has no faces')
    if not (len(faces) == len(face_uvs) == len(face_materials)):
        raise AtlasError('faces, face_uvs and face_materials differ in length')
    verts = [_finite3(p, 'vertex', i) for i, p in enumerate(vertices)]
    points = [_finite3(p, 'uv', i) for i, p in enumerate(uvs)]
    nv, nt = len(verts), len(points)
    face_lists, uv_lists = [], []
    for f, (vi, ti) in enumerate(zip(faces, face_uvs)):
        vi, ti = list(vi), list(ti)
        if len(vi) != len(ti) or len(vi) < 3:
            raise AtlasError(f"face {f}: vertex/UV index count mismatch or < 3")
        for i in vi:
            if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < nv:
                raise AtlasError(f"face {f}: index out of range")
        for i in ti:
            if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < nt:
                raise AtlasError(f"face {f}: index out of range")
        face_lists.append(vi)
        uv_lists.append(ti)
    recs = {}
    owner = {}
    for f, (ti, m) in enumerate(zip(uv_lists, face_materials)):
        if m not in materials:
            raise AtlasError(f"face {f}: material {m!r} has no definition (MTL / material map)")
        recs.setdefault(m, {'name': m, 'faces': [], 'dens': {}, 'src_px': {}})['faces'].append(f)
        for t in ti:
            if owner.setdefault(t, m) != m:
                raise AtlasError(f"UV vertex {t} is shared by materials {owner[t]!r} and {m!r}; split the UV seam")
    built = []
    for name in sorted(recs):
        rec = recs[name]
        spec = materials[name]
        if not isinstance(spec, dict) or 'dissolve' not in spec:
            raise AtlasError(f"material {name!r}: dissolve has no entry")
        dis = spec['dissolve']
        if isinstance(dis, bool) or not isinstance(dis, (int, float)) or not math.isfinite(dis) or not 0.0 <= dis <= 1.0:
            raise AtlasError(f"material {name!r}: dissolve {dis} outside 0..1")
        idx = sorted({t for f in rec['faces'] for t in uv_lists[f]})
        us = [points[t][0] for t in idx]
        vs = [points[t][1] for t in idx]
        umn, umx, vmn, vmx = min(us), max(us), min(vs), max(vs)
        rec['tu'] = int(math.floor((umn + umx) / 2))
        rec['tv'] = int(math.floor((vmn + vmx) / 2))
        if not (0 <= rec['tu'] <= 9 and 0 <= rec['tv'] <= 9):
            raise AtlasError(f"material {name!r}: UV centre outside the UDIM grid 1001..1100")
        if umn < rec['tu'] - EPS or umx > rec['tu'] + 1 + EPS or vmn < rec['tv'] - EPS or vmx > rec['tv'] + 1 + EPS:
            raise AtlasError(f"material {name!r}: UV island crosses a UDIM tile border")
        rec['tile'] = 1001 + rec['tu'] + 10 * rec['tv']
        classified = _classify_material(name, spec, dis)
        rec.update(classified)
        rec['x0'], rec['x1'] = (umn - rec['tu']) * rec['W'], (umx - rec['tu']) * rec['W']
        rec['y0'], rec['y1'] = (1 - (vmx - rec['tv'])) * rec['H'], (1 - (vmn - rec['tv'])) * rec['H']
        for f in rec['faces']:
            rec['src_px'][f] = _src_px(points, uv_lists[f], rec)
            pts_m = [_mul(verts[i], unit_m) for i in face_lists[f]]
            texel = _face_texel(pts_m, rec['src_px'][f])
            if texel is not None:
                rec['dens'][f] = texel
        built.append(rec)
    if mode == 'ground':
        for rec in built:
            if not rec['dens']:
                raise AtlasError(f"material {rec['name']!r}: no face with measurable UV and geometry area")
    plug_scales = {}
    for rec in built:
        if rec['plug']:
            rec['x1'], rec['y1'], plug_scales[rec['name']] = _plug_extent(
                verts, face_lists, rec, mode, plug_px_m, plug_cell, unit_m)
            rec['x0'] = rec['y0'] = 0.0
            _cell(rec, pad, 1.0)
    tex = [rec for rec in built if not rec['plug']]
    used = None
    if mode == 'ground':
        for rec in tex:
            _med, lo, hi = _bounds(rec)
            if lo > hi:
                smin = min(a for a, _ in rec['dens'].values())
                smax = max(b for _, b in rec['dens'].values())
                raise AtlasError(
                    f"material {rec['name']!r}: directional texel spread {smin:.2f}..{smax:.2f} source "
                    f"px/m (ratio {smax / max(smin, 1e-300):.2f}) cannot fit the band "
                    f"{GROUND_MIN}..{GROUND_MAX} with one uniform scale")
        t = target
        while t >= GROUND_MIN * 1.05 - 1e-9:
            for rec in tex:
                med, lo, hi = _bounds(rec)
                _cell(rec, pad, max(lo, min(hi, t / med)))
            if _shelf(built, size):
                used = t
                break
            t *= 0.96
    else:
        def fits(scale):
            for rec in tex:
                _cell(rec, pad, scale)
            return _shelf(built, size)
        if fits(1.0):
            used = 1.0
        elif fits(0.004):
            lo, hi = 0.004, 1.0
            for _ in range(24):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if fits(mid) else (lo, mid)
            fits(lo)
            used = lo
    if used is None:
        calc = _fit_calc(built, tex, size, pad, mode)
        raise AtlasFitError(f"materials {[rec['name'] for rec in built]} do not fit one {size} atlas", calc)
    if shrink and profile is not None:
        final = size
        for smaller in sorted((s for s in allowed if s < size), reverse=True):
            if not _shelf(built, smaller):
                break
            final = smaller
        _shelf(built, final)
        size = final
    byname = {rec['name']: rec for rec in built}
    new_uv, new_fuv, shared = [], [], {}
    for f, m in enumerate(face_materials):
        rec = byname[m]
        if rec['plug']:
            o = plug_scales[m][f]
            ids = []
            for x, y in o:
                ax = rec['cx'] + rec['dw'] / 2 + x
                ay = rec['cy'] + rec['dh'] / 2 + y
                new_uv.append((ax / size, 1 - ay / size))
                ids.append(len(new_uv) - 1)
            new_fuv.append(tuple(ids))
            continue
        ids = []
        for t, (px, py) in zip(uv_lists[f], rec['src_px'][f]):
            if t not in shared:
                x = rec['cx'] + (px - rec['bx0']) * rec['k']
                y = rec['cy'] + (py - rec['by0']) * rec['k']
                new_uv.append((x / size, 1 - y / size))
                shared[t] = len(new_uv) - 1
            ids.append(shared[t])
        new_fuv.append(tuple(ids))
    covered = list(range(len(face_lists)))
    image = _raster(built, size)
    return {
        'uvs': new_uv,
        'face_uvs': new_fuv,
        'tiles': sorted({rec['tile'] for rec in built}),
        'cells': {rec['name']: [rec['cx'], rec['cy'], rec['dw'], rec['dh']] for rec in built},
        'kinds': {rec['name']: 'plug' if rec['plug'] else 'texture' for rec in built},
        'dropped': [],
        'faces': covered,
        'used': used,
        'rgb': image['rgb'],
        'alpha': image['alpha'],
        'size': size,
        'texel_px_per_m': {rec['name']: round(_bounds(rec)[0] * rec['k'], 4)
                           for rec in built if not rec['plug'] and rec['dens']},
    }


# ---- 0.9 (#979, branch B): GroundEl map rule, Flora atlas, 24-bit output --------------------------------------
def _sibling(filename, alias):
    import importlib.util
    import sys
    mod = sys.modules.get(alias)
    if mod is not None and getattr(mod, '__file__', None):
        return mod
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


def texqa():
    """Stdlib PNG reader/writer of branch B (texqa_core.py)."""
    return _sibling('texqa_core.py', 'agr_tools_texqa_core')


GROUNDEL_CODES = ('map_missing', 'map_unreadable', 'groundel_not_square', 'groundel_size', 'groundel_alpha',
                  'atlas_overflow')


def groundel_map_rule(info, limit=GROUNDEL_MAX):
    """Findings [(code, detail)] and warnings [text] of one GroundEl map against the 512 rule (lab L06).

    info: None (no map / no file) or {'file', 'format', 'w', 'h', 'depth', 'alpha_min'(int|None)}.
    Square, power of two 128..limit; alpha by the pixels (a fully opaque alpha channel is not an error, it is
    dropped: the output is 24-bit RGB); depth != 8 is a warning. A missing or unspecified map is an error
    (source defect 2: skipped silently)."""
    if info is None:
        return [('map_missing', 'no diffuse map file (unspecified or not found)')], []
    if info.get('error'):
        return [('map_unreadable', '{}: {}'.format(info['file'], info['error']))], []
    out, warn = [], []
    w, h = info['w'], info['h']
    if w != h:
        out.append(('groundel_not_square', '{}: {}x{} is not square'.format(info['file'], w, h)))
    side = max(w, h)
    if side > limit or min(w, h) < 128 or (w & (w - 1)) or (h & (h - 1)):
        out.append(('groundel_size', '{}: {}x{}; GroundEl maps are squares 128, 256 or {} px'.format(
            info['file'], w, h, limit)))
    if info.get('alpha_min') is not None and info['alpha_min'] < 255:
        out.append(('groundel_alpha', '{}: transparent pixels (min alpha {}); NPM maps carry no alpha'.format(
            info['file'], info['alpha_min'])))
    if info.get('depth') not in (None, 8):
        warn.append('{}: {} bits per channel, expected 8'.format(info['file'], info['depth']))
    return out, warn


def rows_rgb(pic):
    """pack() bitmap rows [[(r, g, b)]] and alpha rows [[a]] (None without alpha) from a texqa Picture."""
    rgb = pic.rgb()
    alpha = pic.alpha()
    rows, arows = [], []
    for y in range(pic.h):
        o = y * pic.w * 3
        rows.append([tuple(rgb[o + 3 * x:o + 3 * x + 3]) for x in range(pic.w)])
        if alpha is not None:
            arows.append(list(alpha[y * pic.w:(y + 1) * pic.w]))
    return rows, (arows if alpha is not None else None)


def atlas_png(laid):
    """(diffuse PNG bytes, 24-bit RGB colour type 2; opacity PNG bytes, 8-bit grey, or None) of a pack() result."""
    tq = texqa()
    size = laid['size']
    diffuse = tq.write_png(size, size, laid['rgb'], 3)
    opacity = tq.write_png(size, size, laid['alpha'], 1) if laid['alpha'] is not None else None
    return diffuse, opacity


# ---- Flora atlas ------------------------------------------------------------------------------------------
# Team sources read for the idea only (#853): FloraAtlas.ms sha256 0160f807…1093, Flora Atlas V1.2.mcr sha256
# a6bae6da…6be29 (the old Flora Atlas.mcr c343563c…6d5d is dropped). Measured defects (T05, Max 2024/2026) fixed:
# A1 C# helper (fails to compile in Max 2026, opacity lost) -> stdlib only, no C# at runtime;
# A2 one tile per object (5 tiles for 3 textures, 8 % fill) -> one tile per unique texture file;
# A3 an instance remapped twice (8/32 faces right) -> the glue remaps one mesh per instance group;
# A4 padding 2 px without bleed -> padding >= 8 px, edge pixels bled into it;
# A5 small tiles upscaled up to x3 -> scale <= 1, never above the source pixels;
# A6 diffuse written as RGBA (colour type 6) -> diffuse 24-bit RGB (colour type 2), opacity a separate grey atlas;
# A7 a primitive with modifiers loses the remap after writing / Collect collapses stacks outside undo -> the
#    evaluated mesh is read, only export copies are written (glue, one undo record).
FLORA_SIZES = (256, 512, 1024, 2048)


def uv_crop(w, h, uv_box):
    """Pixel crop (x0, y0, x1, y1) of a texture for the UV bbox (u0, v0, u1, v1); UV outside 0..1 -> AtlasError."""
    u0, v0, u1, v1 = uv_box
    if u0 < -EPS or v0 < -EPS or u1 > 1 + EPS or v1 > 1 + EPS:
        raise AtlasError('UV outside 0..1 (tiling) cannot be cropped into an atlas cell: '
                         '{:.4f}..{:.4f} x {:.4f}..{:.4f}'.format(u0, u1, v0, v1))
    x0 = max(0, int(math.floor(u0 * w + EPS)))
    x1 = min(w, int(math.ceil(u1 * w - EPS)))
    y0 = max(0, int(math.floor((1.0 - v1) * h + EPS)))
    y1 = min(h, int(math.ceil((1.0 - v0) * h - EPS)))
    return x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)


def flora_layout(crops, max_size=2048, pad=PADDING_MIN_PX, sizes=FLORA_SIZES):
    """crops: {key: (x0, y0, x1, y1)} -> {'size', 'scale', 'cells': {key: [x, y, w, h]} (inner, without pad)}.

    The smallest square of `sizes` <= max_size that holds every crop at scale 1 (no upscale), else max_size with
    one uniform scale < 1 for every tile (largest that fits)."""
    if not isinstance(pad, int) or isinstance(pad, bool) or pad < PADDING_MIN_PX:
        raise AtlasError(f"padding must be an integer >= {PADDING_MIN_PX} px, got {pad}")
    if max_size not in sizes:
        raise AtlasError(f"atlas size must be one of {sizes}, got {max_size}")
    if not crops:
        raise AtlasError('no texture to put in the atlas')

    def place(side, scale):
        recs = []
        for key in sorted(crops):
            x0, y0, x1, y1 = crops[key]
            iw = max(1, int(math.ceil((x1 - x0) * scale - 1e-9)))
            ih = max(1, int(math.ceil((y1 - y0) * scale - 1e-9)))
            recs.append({'name': key, 'dw': iw + 2 * pad, 'dh': ih + 2 * pad, 'iw': iw, 'ih': ih})
        if not _shelf(recs, side):
            return None
        return {r['name']: [r['cx'] + pad, r['cy'] + pad, r['iw'], r['ih']] for r in recs}

    for side in sorted(s for s in sizes if s <= max_size):
        cells = place(side, 1.0)
        if cells is not None:
            return {'size': side, 'scale': 1.0, 'cells': cells}
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2.0
        if place(max_size, mid) is not None:
            lo = mid
        else:
            hi = mid
    if lo <= 0.0 or place(max_size, lo) is None:
        raise AtlasError('textures do not fit one {} atlas'.format(max_size))
    scale = math.floor(lo * 10000) / 10000.0
    return {'size': max_size, 'scale': scale, 'cells': place(max_size, scale)}


def _resample(plane, w, n, crop, iw, ih):
    """Box-filter the crop (x0, y0, x1, y1) of an n-channel plane (width w) to iw x ih. Scale 1 is a copy."""
    x0, y0, x1, y1 = crop
    cw, ch = x1 - x0, y1 - y0
    out = bytearray(iw * ih * n)
    if cw == iw and ch == ih:
        for y in range(ih):
            s = ((y0 + y) * w + x0) * n
            out[y * iw * n:(y + 1) * iw * n] = plane[s:s + iw * n]
        return bytes(out)
    fx, fy = cw / float(iw), ch / float(ih)
    for y in range(ih):
        sy0 = y0 + int(math.floor(y * fy))
        sy1 = max(sy0 + 1, y0 + int(math.ceil((y + 1) * fy - 1e-9)))
        for x in range(iw):
            sx0 = x0 + int(math.floor(x * fx))
            sx1 = max(sx0 + 1, x0 + int(math.ceil((x + 1) * fx - 1e-9)))
            acc = [0] * n
            cnt = 0
            for yy in range(sy0, min(sy1, y0 + ch)):
                base = yy * w
                for xx in range(sx0, min(sx1, x0 + cw)):
                    o = (base + xx) * n
                    for c in range(n):
                        acc[c] += plane[o + c]
                    cnt += 1
            o = (y * iw + x) * n
            for c in range(n):
                out[o + c] = (acc[c] + cnt // 2) // cnt
    return bytes(out)


def _paste_bleed(dst, size, n, cell, patch, pad):
    """Paste an iw x ih patch at cell (x, y) and bleed its edge pixels `pad` px into the padding ring."""
    x, y, iw, ih = cell
    for yy in range(-pad, ih + pad):
        sy = min(max(yy, 0), ih - 1)
        ty = y + yy
        if not 0 <= ty < size:
            continue
        row = patch[sy * iw * n:(sy + 1) * iw * n]
        left = row[:n] * pad
        right = row[-n:] * pad
        line = left + row + right
        tx = x - pad
        cut0 = max(0, -tx)
        cut1 = max(0, tx + iw + 2 * pad - size)
        seg = line[cut0 * n:len(line) - cut1 * n]
        o = (ty * size + tx + cut0) * n
        dst[o:o + len(seg)] = seg


def flora_raster(textures, layout, pad=PADDING_MIN_PX):
    """textures: {key: {'w', 'h', 'rgb' (bytes w*h*3), 'alpha' (bytes w*h or None), 'crop'}} ->
    {'rgb': bytes size*size*3, 'alpha': bytes size*size or None, 'size'}. Background black RGB, opaque white
    opacity outside the cells; cells bled into their padding."""
    size = layout['size']
    rgb = bytearray(size * size * 3)
    alpha = bytearray(b'\xff' * (size * size))
    any_alpha = False
    for key, cell in sorted(layout['cells'].items()):
        t = textures[key]
        _x, _y, iw, ih = cell
        _paste_bleed(rgb, size, 3, cell, _resample(t['rgb'], t['w'], 3, t['crop'], iw, ih), pad)
        if t.get('alpha') is not None:
            any_alpha = True
            _paste_bleed(alpha, size, 1, cell, _resample(t['alpha'], t['w'], 1, t['crop'], iw, ih), pad)
    return {'rgb': bytes(rgb), 'alpha': bytes(alpha) if any_alpha else None, 'size': size}


def flora_uv(u, v, tex_w, tex_h, crop, cell, size, scale):
    """Atlas UV of a source UV (affine: crop offset, scale, cell offset; V up)."""
    x0, y0 = crop[0], crop[1]
    cx, cy = cell[0], cell[1]
    px = cx + (u * tex_w - x0) * scale
    py = cy + ((1.0 - v) * tex_h - y0) * scale
    return (px / size, 1.0 - py / size)


def flora_plan(textures, uses, max_size=2048, pad=PADDING_MIN_PX):
    """textures: {key: {'w', 'h'}}; uses: {key: [(u, v), ...] every UV corner that samples it}.
    -> {'layout', 'crops', 'tiles': [{texture, crop, cell, scale, fill}], 'fill'}; AtlasError on tiling UVs."""
    crops = {}
    for key, pts in uses.items():
        if not pts:
            continue
        us = [p[0] for p in pts]
        vs = [p[1] for p in pts]
        t = textures[key]
        crops[key] = uv_crop(t['w'], t['h'], (min(us), min(vs), max(us), max(vs)))
    layout = flora_layout(crops, max_size, pad)
    size = layout['size']
    tiles, used = [], 0
    for key in sorted(crops):
        x0, y0, x1, y1 = crops[key]
        cell = layout['cells'][key]
        used += cell[2] * cell[3]
        tiles.append({'texture': key, 'crop_px': [x0, y0, x1, y1], 'cell_px': cell, 'scale': layout['scale'],
                      'source_px': [textures[key]['w'], textures[key]['h']]})
    return {'layout': layout, 'crops': crops, 'tiles': tiles, 'size': size,
            'fill': round(used / float(size * size), 6)}


def publish_report(path, payload, inputs):
    """Write one new JSON report. Alias of an input, or an existing file, writes nothing."""
    path = Path(path)
    partial = Path(str(path) + '.partial')
    labels = {'output': path, 'partial': partial}
    for raw in inputs:
        src = Path(raw)
        labels.setdefault(f'input:{src}', src)
        if _same_path(path, src) or _same_path(partial, src):
            raise AtlasError(f"output {path} resolves to input {src}")
    seen = {}
    for label, item in (('output', path), ('partial', partial)):
        key = os.path.normcase(str(item.resolve()))
        if key in seen:
            raise AtlasError(f"{label} and {seen[key]} are the same file")
        seen[key] = label
    if path.exists() or partial.exists():
        raise AtlasError(f"output {path} already exists; use a new versioned folder")
    data = json.dumps(payload, allow_nan=False, sort_keys=True).encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with partial.open('xb') as handle:
            handle.write(data)
        os.replace(partial, path)
    finally:
        if partial.exists():
            partial.unlink()
    for raw in inputs:
        if not Path(raw).exists():
            raise AtlasError(f"input {raw} disappeared during publish")
    return path


def publish_main(argv):
    """Exit nonzero when the report path collides with the input. Writes nothing on failure."""
    if len(argv) != 2:
        return 2
    src, dest = Path(argv[0]), Path(argv[1])
    try:
        payload = json.loads(src.read_text(encoding='utf-8'))
        publish_report(dest, payload, [src])
    except (AtlasError, OSError, ValueError, json.JSONDecodeError):
        return 2
    return 0


# ---- 1.0 (#1024, branch P): rigid group atlas of npm.build and atlas.facade_strip ---------------------------
# Lab L11 (docs/experiments/npm.build.md, verdict `new`): every group (library ID of the VPM, or a facade strip)
# moves into its cell RIGIDLY: one uniform scale per axis and one shift, the group keeps its internal layout and its
# fractional start ("scroll"), so the K6 seam stays 0. The cell is a viewport into the infinitely tiled FULL
# resolution source map over the real UV extent of the group, box-filtered once to the target texel; the padding is
# the same texture continued. Not repeated from GeoAGR Priority atlas: 256 px render tiles (GeoAGR.ms:27440), texel
# by the root of the group area (:27531-27536), empty / edge-stretched islands over 1 UV (:27096, fit_map_new :1152),
# fixed %TEMP% tile names (:27588), glass as a diffuse-colour cell (:27665), external commands without exit codes.
NPM_SIZES = (256, 512, 1024, 2048)
NPM_TEXEL_PX_M = 39.0
GLASS_RGB = (255, 255, 255)
PLUG_INNER_PX = 8
KINDS = ('texture', 'plug', 'glass')


def _ppu(group, texel):
    """Atlas px per pattern-UV unit (x, y) of a group."""
    if group['kind'] == 'texture':
        mu, mv = group['m_per_uv']
        return texel * mu, texel * mv
    u0, v0, u1, v1 = group['uv_box']
    ext = max(u1 - u0, v1 - v0)
    k = PLUG_INNER_PX / ext if ext > 1e-12 else 1.0
    return k, k


def _inner(group, ppu):
    u0, v0, u1, v1 = group['uv_box']
    if group['kind'] != 'texture':
        return PLUG_INNER_PX, PLUG_INNER_PX
    return (max(1, int(math.ceil((u1 - u0) * ppu[0] - 1e-6))), max(1, int(math.ceil((v1 - v0) * ppu[1] - 1e-6))))


def rigid_plan(groups, texel=NPM_TEXEL_PX_M, pad=PADDING_MIN_PX, max_size=2048, sizes=NPM_SIZES):
    """Cells of the rigid group atlas, the smallest square of `sizes` <= max_size that holds them at `texel` px/m.

    groups: [{'key': str, 'kind': 'texture'|'plug'|'glass', 'uv_box': [u0, v0, u1, v1] in pattern UV (one unit =
    one repeat of the map), 'm_per_uv': [mu, mv] metres per pattern-UV unit (texture), 'color': [r, g, b] (plug)}].
    Returns {'size', 'texel', 'pad', 'fill', 'cells': {key: {'outer': [x, y, w, h], 'inner': [x, y, w, h],
    'ppu': [px, py], 'scale': [su, sv], 'shift': [du, dv], 'region': [u0, v0, u1, v1]}}} with
    atlas_uv = scale * uv + shift (image rows from the top, V up). Never changes the texel to fit: a layout that
    does not fit max_size raises AtlasFitError (`calc`)."""
    if not isinstance(pad, int) or isinstance(pad, bool) or pad < PADDING_MIN_PX:
        raise AtlasError(f"padding must be an integer >= {PADDING_MIN_PX} px, got {pad}")
    if max_size not in sizes:
        raise AtlasError(f"atlas size must be one of {sizes}, got {max_size}")
    if isinstance(texel, bool) or not isinstance(texel, (int, float)) or not math.isfinite(texel) or texel <= 0:
        raise AtlasError(f"texel must be a positive number of px/m, got {texel!r}")
    if not groups:
        raise AtlasError('no group to put in the atlas')
    recs, seen = [], set()
    for g in groups:
        if g.get('kind') not in KINDS:
            raise AtlasError(f"group {g.get('key')!r}: kind must be one of {KINDS}")
        if g['key'] in seen:
            raise AtlasError(f"duplicate group {g['key']!r}")
        seen.add(g['key'])
        box = [float(c) for c in g['uv_box']]
        if not all(math.isfinite(c) for c in box) or box[2] < box[0] or box[3] < box[1]:
            raise AtlasError(f"group {g['key']!r}: invalid UV box {g['uv_box']!r}")
        if g['kind'] == 'texture':
            mu, mv = g['m_per_uv']
            if not (mu > 0 and mv > 0 and math.isfinite(mu) and math.isfinite(mv)):
                raise AtlasError(f"group {g['key']!r}: no measurable texel (UV or geometry area 0)")
        ppu = _ppu(g, texel)
        iw, ih = _inner(g, ppu)
        recs.append({'name': str(g['key']), 'dw': iw + 2 * pad, 'dh': ih + 2 * pad, 'iw': iw, 'ih': ih,
                     'ppu': ppu, 'box': box})
    size = None
    for side in sorted(s for s in sizes if s <= max_size):
        if _shelf(recs, side):
            size = side
            break
    if size is None:
        calc = {'atlas_px': max_size, 'atlas_area_px2': max_size * max_size, 'padding_px': pad,
                'texel_px_per_m': texel, 'cells_area_px2': sum(r['dw'] * r['dh'] for r in recs),
                'widest_cell_px': max(max(r['dw'], r['dh']) for r in recs),
                'cells': [{'group': r['name'], 'cell_px': [r['dw'], r['dh']]} for r in recs]}
        raise AtlasFitError(f"{len(recs)} cells at {texel} px/m do not fit one {max_size} atlas", calc)
    cells, used = {}, 0
    for r in recs:
        ix, iy = r['cx'] + pad, r['cy'] + pad
        (u0, v0, u1, v1), (px, py) = r['box'], r['ppu']
        cells[r['name']] = {
            'outer': [r['cx'], r['cy'], r['dw'], r['dh']], 'inner': [ix, iy, r['iw'], r['ih']], 'ppu': [px, py],
            'scale': [px / size, py / size],
            'shift': [(ix - u0 * px) / size, 1.0 - (iy + v1 * py) / size],
            'region': [ix / size, 1.0 - (iy + r['ih']) / size, (ix + r['iw']) / size, 1.0 - iy / size]}
        used += r['dw'] * r['dh']
    return {'size': size, 'texel': float(texel), 'pad': pad, 'fill': round(used / float(size * size), 6),
            'cells': cells}


def to_atlas(cell, uv):
    """Atlas UV of a pattern UV (rigid: scale and shift of the cell)."""
    return (cell['scale'][0] * uv[0] + cell['shift'][0], cell['scale'][1] * uv[1] + cell['shift'][1])


def from_atlas(row, uv):
    """Source UV of an atlas UV by a correspondence row (the exact reverse of npm.to_vpm, lab L11)."""
    return ((uv[0] - row['shift'][0]) / row['scale'][0], (uv[1] - row['shift'][1]) / row['scale'][1])


def _wrap_integral(prefix, total, n, x):
    """Integral of a periodic step function (period n, prefix sums) from 0 to x (x may be negative / > n)."""
    q, rem = divmod(x, n)
    i = int(rem)
    if i >= n:  # float rounding of divmod
        i, rem, q = 0, 0.0, q + 1
    return q * total + prefix[i] + (rem - i) * (prefix[i + 1] - prefix[i])


def periodic_cell(src, w, h, n, x0, y0, kx, ky, dw, dh):
    """dw x dh x n bytes: the box-filtered viewport into the infinitely tiled source (w x h x n bytes, rows from
    the top). Cell pixel (X, Y) covers the source rectangle [x0 + X/kx, x0 + (X+1)/kx) x [y0 + Y/ky, ...) exactly
    (area average, separable, periodic prefix sums): a flat region keeps its value, no 256 px intermediate."""
    from itertools import accumulate
    if w <= 0 or h <= 0 or len(src) != w * h * n:
        raise AtlasError('partial source bitmap')
    bx = [x0 + X / kx for X in range(dw + 1)]
    by = [y0 + Y / ky for Y in range(dh + 1)]
    lo_row, hi_row = int(math.floor(by[0])), int(math.ceil(by[-1]))
    rows = range(h) if hi_row - lo_row >= h else sorted({r % h for r in range(lo_row, hi_row)})
    need = set(rows)
    # horizontal pass: integral of each needed row over the column boundaries
    horiz = [[None] * h for _ in range(n)]
    for r in need:
        base = r * w * n
        for c in range(n):
            vals = src[base + c:base + w * n:n]
            pre = [0]
            pre.extend(accumulate(vals))
            tot = pre[-1]
            acc = [_wrap_integral(pre, tot, w, b) for b in bx]
            horiz[c][r] = [(acc[X + 1] - acc[X]) * kx for X in range(dw)]
    out = bytearray(dw * dh * n)
    for c in range(n):
        hc = horiz[c]
        for X in range(dw):
            col = [hc[r][X] if hc[r] is not None else 0.0 for r in range(h)]
            pre = [0.0]
            pre.extend(accumulate(col))
            tot = pre[-1]
            acc = [_wrap_integral(pre, tot, h, b) for b in by]
            for Y in range(dh):
                v = (acc[Y + 1] - acc[Y]) * ky
                out[(Y * dw + X) * n + c] = 0 if v < 0 else 255 if v > 254.5 else int(v + 0.5)
    return bytes(out)


def rigid_raster(plan, groups, maps, background=BACKGROUND):
    """{'rgb': size*size*3 bytes (24-bit), 'alpha': size*size grey bytes or None, 'size', 'sources': {key: [w, h]}}.

    maps: {key: {'w', 'h', 'rgb': bytes w*h*3, 'alpha': bytes w*h | None}} of the texture groups, read from the
    full-resolution source files (the journal records their size = the input of the cell). Pattern UV u, v sample
    the map at px (u * w, -v * h) (one pattern unit = one repeat of the map). Plugs: their colour; glass: white."""
    size, pad = plan['size'], plan['pad']
    rgb = bytearray(bytes(background)) * (size * size)
    alpha = bytearray(b'\xff' * (size * size))
    any_alpha, sources = False, {}
    for g in sorted(groups, key=lambda q: str(q['key'])):
        cell = plan['cells'][str(g['key'])]
        x, y, dw, dh = cell['outer']
        if g['kind'] == 'texture':
            m = maps.get(g['key'])
            if m is None:
                raise AtlasError(f"group {g['key']!r}: no source map")
            px, py = cell['ppu']
            u0, _v0, _u1, v1 = g['uv_box']
            kx, ky = px / m['w'], py / m['h']
            sx0 = (u0 - pad / px) * m['w']
            sy0 = -(v1 + pad / py) * m['h']
            patch = periodic_cell(m['rgb'], m['w'], m['h'], 3, sx0, sy0, kx, ky, dw, dh)
            for yy in range(dh):
                o = ((y + yy) * size + x) * 3
                rgb[o:o + dw * 3] = patch[yy * dw * 3:(yy + 1) * dw * 3]
            if m.get('alpha') is not None and min(m['alpha']) < 255:
                any_alpha = True
                ap = periodic_cell(m['alpha'], m['w'], m['h'], 1, sx0, sy0, kx, ky, dw, dh)
                for yy in range(dh):
                    o = (y + yy) * size + x
                    alpha[o:o + dw] = ap[yy * dw:(yy + 1) * dw]
            sources[str(g['key'])] = [m['w'], m['h']]
        else:
            color = GLASS_RGB if g['kind'] == 'glass' else tuple(_byte(int(c), str(g['key'])) for c in g['color'])
            span = bytes(color) * dw
            for yy in range(dh):
                o = ((y + yy) * size + x) * 3
                rgb[o:o + dw * 3] = span
    return {'rgb': bytes(rgb), 'alpha': bytes(alpha) if any_alpha else None, 'size': size, 'sources': sources}


def correspondence_table(atlas_report):
    """1.0 (#1024, branch 0 signature; owner P): the VPM -> NPM correspondence table for the passport and the
    reverse step npm.to_vpm (Q): [{'library_id', 'udim', 'region': [u0, v0, u1, v1], 'scale': [su, sv],
    'shift': [du, dv]}] from an atlas report of npm.build.

    atlas_report: {'size', 'texel', 'cells' (rigid_plan), 'groups': [{'key', 'library_id', 'udim', 'udim_source',
    'part', 'kind', 'material', 'map', 'source_texel_px_per_m'}]}. Rule (lab L11): atlas_uv = scale * vpm_uv + shift,
    so vpm_uv = (atlas_uv - shift) / scale (from_atlas). Extra keys per row: part, kind, material, map, cell_px,
    atlas_px, texel_px_per_m, source_texel_px_per_m, udim_source. The UDIM comes from the passport / VPM table,
    not from the UV centre (L11: bbox centre gave 1019 instead of 1007)."""
    size, cells = atlas_report['size'], atlas_report['cells']
    rows = []
    for g in atlas_report['groups']:
        c = cells[str(g['key'])]
        rows.append({'library_id': int(g['library_id']), 'udim': g.get('udim'), 'region': list(c['region']),
                     'scale': list(c['scale']), 'shift': list(c['shift']), 'part': g.get('part'),
                     'kind': g['kind'], 'material': g.get('material'), 'map': g.get('map'),
                     'cell_px': list(c['inner']), 'atlas_px': size, 'texel_px_per_m': atlas_report['texel'],
                     'source_texel_px_per_m': g.get('source_texel_px_per_m'), 'udim_source': g.get('udim_source')})
    return sorted(rows, key=lambda r: (str(r['part']), r['library_id']))
