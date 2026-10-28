"""new-case: stdlib texel min/median readout for the AGR Tools button.

Pattern: new-case. px/m is map_px * sqrt(uv_area / world_area), the same
quantity as dt_ai.ops.texel_density_readout. A missing material assignment is
an error that names the material. Empty, non-finite and zero-size input fail
closed. An output path that resolves to an input writes nothing.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

# Locked standards: VPM uv.diffuse_density_px_per_m (D160) and NPM
# textures.ground_density_px_per_square_meter, read as px per linear metre (D097).
BANDS = {
    'VPM': (512.0, 1706.0),
    'NPM': (10.0, 40.0),
}
REL_TOL = 1e-6
_WORLD_EPS = 1e-12
_UV_EPS = 1e-16


def assert_texel_close(a, b, tol=REL_TOL):
    """Relative closeness. A difference of exactly ``tol`` is an error."""
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise ValueError('unsupported texel value')
    if not math.isfinite(float(a)) or not math.isfinite(float(b)):
        raise ValueError('non-finite texel')
    scale = max(abs(float(a)), abs(float(b)))
    if scale == 0.0:
        raise ValueError('at_threshold: zero texel')
    if abs(float(a) - float(b)) / scale >= tol:
        raise ValueError('threshold')


def _median(values):
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _coords(points, width, label):
    if isinstance(points, (str, bytes)) or not isinstance(points, (list, tuple)):
        raise ValueError(f'partial {label}')
    out = []
    for point in points:
        if isinstance(point, (str, bytes)) or not isinstance(point, (list, tuple)) or len(point) != width:
            raise ValueError(f'partial {label}')
        nums = []
        for coord in point:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)):
                raise ValueError(f'partial {label}')
            number = float(coord)
            if not math.isfinite(number):
                raise ValueError(f'non-finite {label}')
            nums.append(number)
        out.append(tuple(nums))
    return out


def _newell(points):
    origin = points[0]
    total = [0.0, 0.0, 0.0]
    local = [(point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]) for point in points]
    for index, point in enumerate(local):
        nxt = local[(index + 1) % len(local)]
        total[0] += point[1] * nxt[2] - point[2] * nxt[1]
        total[1] += point[2] * nxt[0] - point[0] * nxt[2]
        total[2] += point[0] * nxt[1] - point[1] * nxt[0]
    return tuple(total)


def _norm(vector):
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


def _shoelace(points):
    origin = points[0]
    total = 0.0
    local = [(point[0] - origin[0], point[1] - origin[1]) for point in points]
    for index, point in enumerate(local):
        nxt = local[(index + 1) % len(local)]
        total += point[0] * nxt[1] - point[1] * nxt[0]
    return 0.5 * total


def _areas(xyz, uv):
    if len(xyz) == 3:
        a = (xyz[1][0] - xyz[0][0], xyz[1][1] - xyz[0][1], xyz[1][2] - xyz[0][2])
        b = (xyz[2][0] - xyz[0][0], xyz[2][1] - xyz[0][1], xyz[2][2] - xyz[0][2])
        cross = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
        world = 0.5 * _norm(cross)
        e1 = (uv[1][0] - uv[0][0], uv[1][1] - uv[0][1])
        e2 = (uv[2][0] - uv[0][0], uv[2][1] - uv[0][1])
        uv_area = 0.5 * abs(e1[0] * e2[1] - e1[1] * e2[0])
        return uv_area, world
    world = _norm(_newell(xyz)) / 2.0
    return abs(_shoelace(uv)), world


def _density(uv_area, world, map_px):
    if world < _WORLD_EPS or uv_area < _UV_EPS:
        raise ValueError('at_threshold: zero area')
    value = map_px * math.sqrt(uv_area / world)
    if not math.isfinite(value):
        raise ValueError('non-finite density')
    return value


def _map_px(value, material):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"unmapped material {material!r}: unsupported map size {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"material {material!r}: non-finite map size")
    if isinstance(value, float) and not number.is_integer():
        raise ValueError(f"unmapped material {material!r}: unsupported map size {value!r}")
    px = int(number)
    if px == 0:
        raise ValueError(f"material {material!r}: at_threshold: map size 0")
    if px < 0:
        raise ValueError(f"material {material!r}: negative map size {px}")
    return px


def summarize(payload):
    """Min and median px/m per mesh and per material. Every face is reported or dropped."""
    if not isinstance(payload, dict):
        raise ValueError('unsupported payload')
    missing = [key for key in ('profile', 'materials', 'faces') if key not in payload]
    if missing:
        raise ValueError('partial: missing ' + ', '.join(missing))
    profile = payload['profile']
    if profile not in BANDS:
        raise ValueError(f'unsupported profile {profile!r}')
    materials = payload['materials']
    faces = payload['faces']
    if not isinstance(materials, list) or not isinstance(faces, list):
        raise ValueError('partial: materials and faces must be lists')
    if len(faces) == 0:
        raise ValueError('empty: no faces')
    sizes = {}
    seen = {}
    for item in materials:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not item['name']:
            raise ValueError('partial material name')
        name = item['name']
        if name in seen:
            raise ValueError(f"duplicate material {name!r}: refusing the first entry")
        seen[name] = True
        if 'map_px' not in item or item['map_px'] is None:
            raise ValueError(f"unmapped material {name!r}: no assigned map size")
        sizes[name] = _map_px(item['map_px'], name)
    lo, hi = BANDS[profile]
    kept, dropped = [], []
    for index, face in enumerate(faces):
        if not isinstance(face, dict):
            dropped.append({'face': index, 'reason': 'unsupported face'})
            continue
        mesh = face.get('mesh')
        material = face.get('material')
        if not isinstance(mesh, str) or not mesh:
            dropped.append({'face': index, 'reason': f"partial face: no mesh {face.get('id')!r}"})
            continue
        if not isinstance(material, str) or not material:
            dropped.append({'face': index, 'reason': 'partial face: no material'})
            continue
        if material not in sizes:
            raise ValueError(f"unmapped material {material!r}: no assigned map size")
        try:
            xyz = _coords(face.get('xyz'), 3, 'world coordinate')
            uv = _coords(face.get('uv'), 2, 'UV coordinate')
            if len(xyz) != len(uv) or len(xyz) < 3:
                raise ValueError('partial face: UV count does not match the world corners')
            uv_area, world = _areas(xyz, uv)
            value = _density(uv_area, world, sizes[material])
        except ValueError as exc:
            if 'unmapped' in str(exc) or 'at_threshold' in str(exc) or 'non-finite' in str(exc):
                raise
            dropped.append({'face': index, 'reason': str(exc)})
            continue
        status = 'pass' if lo <= value <= hi else 'fail'
        kept.append({'face': index, 'mesh': mesh, 'material': material, 'px_per_m': value, 'status': status})
    seen_index = {item['face'] for item in kept} | {item['face'] for item in dropped}
    if seen_index != set(range(len(faces))):
        raise ValueError('internal: an input element was not reported')
    def rows(key):
        groups = {}
        for item in kept:
            groups.setdefault(item[key], []).append(item['px_per_m'])
        out = []
        for name, values in groups.items():
            out.append({'name': name, 'min_px_per_m': min(values), 'median_px_per_m': _median(values)})
        return out
    status = 'fail' if dropped or any(item['status'] != 'pass' for item in kept) else 'pass'
    return {
        'status': status,
        'profile': profile,
        'meshes': rows('mesh'),
        'materials': rows('material'),
        'faces': kept,
        'dropped': dropped,
    }


def _same(a, b):
    a, b = Path(a), Path(b)
    try:
        if os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve())):
            return True
    except OSError as exc:
        raise ValueError(f'cannot resolve paths: {exc}') from exc
    if a.exists() and b.exists():
        try:
            return os.path.samefile(a, b)
        except OSError as exc:
            raise ValueError(f'cannot compare input and output identity: {exc}') from exc
    return False


def publish(source, dest, payload, report=None):
    """Write JSON only when input, output, report and the partial path are distinct files."""
    dest = Path(dest)
    roles = [('input', Path(source)), ('output', dest), ('output.partial', Path(str(dest) + '.partial'))]
    if report is not None:
        roles.append(('report', Path(report)))
    for index, (left, path_a) in enumerate(roles):
        for right, path_b in roles[index + 1:]:
            if _same(path_a, path_b):
                raise ValueError(f'{right} path is the input path: {path_b}')
    data = (json.dumps(payload, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with dest.open('xb') as handle:
        handle.write(data)
    if report is not None:
        with Path(report).open('xb') as handle:
            handle.write(data)
    return dest
