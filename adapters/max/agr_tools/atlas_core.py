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


class AtlasError(ValueError):
    """Input the packer refuses, naming the element."""


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


def pack(vertices, uvs, faces, face_uvs, face_materials, materials, *, mode='ground', size=2048,
         pad=PADDING_MIN_PX, target=35.0, plug_px_m=12.5, plug_cell=16, unit_m=1.0):
    """Return remapped UVs, UDIM tiles and cell boxes. Raises AtlasError; never edits inputs."""
    if mode not in ('ground', 'oks'):
        raise AtlasError(f"mode must be ground or oks, got {mode!r}")
    if size not in ATLAS_SIZES:
        raise AtlasError(f"atlas size must be one of {ATLAS_SIZES}, got {size}")
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
        raise AtlasError(f"materials {[rec['name'] for rec in built]} do not fit one {size} atlas")
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
    }


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
