"""new-case: stdlib UCX variant picker for the AGR Tools collision button.

Pattern: new-case. Picks the variant documented in
docs/methods/ucx-collisions/WHEN.md for an explicit or measured object kind and
builds the pieces with the same rules as tools/methods/ucx/ucx_variants.py.
piece count and triangle count are the parity subject. Original vertex lists
are not modified. An output path that resolves to an input writes nothing.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import deque
from pathlib import Path

OUTSIDE_LIMIT = 0.05  # above this the facade AABB is a passage/non-convex body
FEW_LEVELS = (2, 6)  # slice-prisms only for a few near-convex levels
CELL_M = 0.25
GAP_M = 0.004
MERGE_GAP_M = 0.003
MIN_THICK_M = 0.02
LEVEL_AREA_M2 = 1.0
LEVEL_MIN_M = 0.5
SIMPLIFY_M = 0.01
MAX_PIECES = 999
HULL_VOLUME_MIN = 1e-6  # at or below this a single hull is flat, never a volumetric pass
BOUNDS_TOL_M = 1e-4  # emitted world-bounds readback; exactly this far is not a pass
DIGEST_TOL_M = 1e-4  # preview geometry quantum; a move of exactly this is stale
DIGEST_KEYS = ('handle', 'name', 'base_class', 'transform', 'object_transform',
               'parent', 'properties', 'material', 'vertices', 'faces')
BOX_TRIS = (
    (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
    (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
)
KIND_VARIANT = {
    'near-convex-box': 'single-hull',
    'passage': 'kernel-boxes',
    'non-convex': 'kernel-boxes',
    'tight-budget': 'kernel-boxes',
    'few-levels': 'slice-prisms',
}


def triangle_limit(model_triangles):
    """[D012] budget. n < 50 000 -> 15 000, else min(ceil(5% n), 100 000)."""
    if isinstance(model_triangles, bool) or not isinstance(model_triangles, int) or model_triangles < 0:
        raise ValueError(f'unsupported model triangle count {model_triangles!r}')
    if model_triangles < 50000:
        return 15000
    return min(math.ceil(model_triangles * 0.05), 100000)


def budget_verdict(triangles, limit):
    """Exactly the budget is a failure, never a pass. Over the budget is an error."""
    if isinstance(triangles, bool) or not isinstance(triangles, int) or triangles < 0:
        raise ValueError(f'unsupported triangle count {triangles!r}')
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError(f'unsupported triangle limit {limit!r}')
    if triangles > limit:
        raise ValueError(f'UCX triangles {triangles} exceed the budget {limit}')
    if triangles == limit:
        return {'status': 'fail', 'code': 'at_threshold'}
    return {'status': 'pass', 'code': ''}


def kind_from_outside(outside, bands):
    """Map a measured outside fraction and level count to one WHEN.md kind.

    The fraction exactly at the convex limit is ``at_threshold`` and raises.
    It is never rounded onto either kind.
    """
    if isinstance(bands, bool) or not isinstance(bands, int) or bands < 1:
        raise ValueError(f'unsupported level count {bands!r}')
    if isinstance(outside, bool) or not isinstance(outside, (int, float)) or not math.isfinite(float(outside)):
        raise ValueError(f'non-finite outside fraction {outside!r}')
    outside = float(outside)
    if outside == OUTSIDE_LIMIT:
        raise ValueError('at_threshold: outside fraction is exactly the convex limit')
    if outside > OUTSIDE_LIMIT:
        return 'passage', 'kernel-boxes'
    if FEW_LEVELS[0] <= bands <= FEW_LEVELS[1]:
        return 'few-levels', 'slice-prisms'
    return 'near-convex-box', 'single-hull'


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _rotate(point, angle_deg):
    """Row-vector rotation matching ``point @ _rot(angle).T``."""
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = point
    return (c * x - s * y, s * x + c * y, z)


def _check(verts, tris):
    if not verts or not tris:
        raise ValueError('empty mesh')
    points = []
    for point in verts:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError('partial vertex')
        nums = []
        for coord in point:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)):
                raise ValueError('partial vertex')
            number = float(coord)
            if not math.isfinite(number):
                raise ValueError('non-finite vertex')
            nums.append(number)
        points.append(tuple(nums))
    faces = []
    area = 0.0
    count = len(points)
    for face in tris:
        if not isinstance(face, (list, tuple)) or len(face) != 3:
            raise ValueError('partial triangle')
        idx = []
        for index in face:
            if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= count:
                raise ValueError(f'triangle index out of range: {index!r}')
            idx.append(index)
        a = _sub(points[idx[1]], points[idx[0]])
        b = _sub(points[idx[2]], points[idx[0]])
        area += 0.5 * _norm(_cross(a, b))
        faces.append(tuple(idx))
    if area <= 1e-9:
        raise ValueError('mesh has zero surface area')
    return points, faces


def facade_angle(verts, tris):
    s = c = wsum = 0.0
    found = False
    for i0, i1, i2 in tris:
        n = _cross(_sub(verts[i1], verts[i0]), _sub(verts[i2], verts[i0]))
        length = _norm(n)
        if length <= 1e-12:
            continue
        n = (n[0] / length, n[1] / length, n[2] / length)
        if abs(n[2]) >= 0.2:
            continue
        found = True
        phi = math.atan2(n[1], n[0])
        weight = length * math.hypot(n[0], n[1])
        s += weight * math.sin(4 * phi)
        c += weight * math.cos(4 * phi)
        wsum += weight
    if not found or math.hypot(s, c) < 1e-9 * wsum:
        return 0.0
    return math.degrees(math.atan2(s, c) / 4)


def _volume(verts, tris):
    if not verts:
        return 0.0
    origin = verts[0]
    total = 0.0
    for i0, i1, i2 in tris:
        a, b, c = _sub(verts[i0], origin), _sub(verts[i1], origin), _sub(verts[i2], origin)
        total += a[0] * (b[1] * c[2] - b[2] * c[1])
        total -= a[1] * (b[0] * c[2] - b[2] * c[0])
        total += a[2] * (b[0] * c[1] - b[1] * c[0])
    return abs(total) / 6.0


def _box_piece(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    verts = (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )
    return verts, BOX_TRIS


def _exactly(delta, tol):
    return math.isclose(delta, tol, rel_tol=0.0, abs_tol=0.0) or abs(delta - tol) <= tol * 2e-7


def accept_hull_volume(volume):
    """'hull' or 'flat'. The flat limit itself is an error, never either verdict."""
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(float(volume)):
        raise ValueError(f'non-finite hull volume {volume!r}')
    volume = float(volume)
    if volume < 0:
        raise ValueError('negative hull volume')
    if _exactly(volume, HULL_VOLUME_MIN):
        raise ValueError('at_threshold: hull volume is exactly the flat limit')
    if volume < HULL_VOLUME_MIN:
        return 'flat'
    return 'hull'


def _orient(pts, ia, ib, ic, ip):
    return _dot(_cross(_sub(pts[ib], pts[ia]), _sub(pts[ic], pts[ia])), _sub(pts[ip], pts[ia]))


def _point_outside_triangle(pts, face, ip, eps):
    a, b, c = (pts[i] for i in face)
    point = pts[ip]
    normal = _cross(_sub(b, a), _sub(c, a))
    area = _dot(normal, normal)
    if area <= eps:
        return False

    def bary(u, v):
        return _dot(normal, _cross(_sub(v, u), _sub(point, u)))

    limit = -eps
    return bary(b, c) < limit or bary(c, a) < limit or bary(a, b) < limit


def _convex_hull(raw):
    """Convex hull as outward triangles. Flat and non-finite input raise; points are not mutated."""
    if not raw:
        raise ValueError('empty mesh')
    uniq = []
    seen = set()
    for point in raw:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError('partial vertex')
        nums = []
        for coord in point:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(float(coord)):
                raise ValueError('non-finite vertex')
            nums.append(float(coord))
        key = tuple(round(num, 9) for num in nums)
        if key not in seen:
            seen.add(key)
            uniq.append(key)
    pts = uniq
    count = len(pts)
    if count < 4:
        raise ValueError('flat hull')
    span = max(max(point[axis] for point in pts) - min(point[axis] for point in pts) for axis in range(3))
    eps = max(span, 1.0) ** 3 * 1e-12
    i0 = min(range(count), key=lambda i: pts[i])
    i1 = max(range(count), key=lambda i: _norm(_sub(pts[i], pts[i0])))
    if _norm(_sub(pts[i1], pts[i0])) <= eps:
        raise ValueError('flat hull')
    i2 = max(range(count), key=lambda i: _norm(_cross(_sub(pts[i1], pts[i0]), _sub(pts[i], pts[i0]))))
    if _norm(_cross(_sub(pts[i1], pts[i0]), _sub(pts[i2], pts[i0]))) <= eps:
        raise ValueError('flat hull')
    i3 = max(range(count), key=lambda i: abs(_orient(pts, i0, i1, i2, i)))
    if abs(_orient(pts, i0, i1, i2, i3)) <= eps:
        raise ValueError('flat hull')

    def outward(ia, ib, ic, interior):
        if _orient(pts, ia, ib, ic, interior) > 0:
            return (ia, ic, ib)
        return (ia, ib, ic)

    faces = [
        outward(i0, i1, i2, i3),
        outward(i0, i1, i3, i2),
        outward(i0, i2, i3, i1),
        outward(i1, i2, i3, i0),
    ]
    used = {i0, i1, i2, i3}
    for ip in range(count):
        if ip in used:
            continue
        visible = [face for face in faces if _orient(pts, *face, ip) > eps]
        if not visible:
            coplanar = [face for face in faces if abs(_orient(pts, *face, ip)) <= eps]
            visible = [face for face in coplanar if _point_outside_triangle(pts, face, ip, eps)]
            if not visible:
                continue
        edge_count = {}
        for a, b, c in visible:
            for edge in ((a, b), (b, c), (c, a)):
                edge_count[edge] = edge_count.get(edge, 0) + 1
        horizon = [edge for edge, hits in edge_count.items()
                   if hits == 1 and (edge[1], edge[0]) not in edge_count]
        visible_set = set(visible)
        faces = [face for face in faces if face not in visible_set]
        for a, b in horizon:
            faces.append((a, b, ip))
        used.add(ip)
    used_idx = sorted({index for face in faces for index in face})
    remap = {old: new for new, old in enumerate(used_idx)}
    verts = [pts[index] for index in used_idx]
    tris = [tuple(remap[index] for index in face) for face in faces]
    tris = [face for face in tris if len(set(face)) == 3]
    if len(verts) < 4 or not tris:
        raise ValueError('flat hull')
    return verts, tuple(tris)


def world_metres(points, rows, to_m):
    """Object-space system units to world metres. Max row-vector: x*row1 + y*row2 + z*row3 + row4."""
    if isinstance(to_m, bool) or not isinstance(to_m, (int, float)) or not math.isfinite(float(to_m)):
        raise ValueError(f'non-finite system units {to_m!r}')
    scale = float(to_m)
    if scale == 0.0 or _exactly(scale, 0.0):
        raise ValueError('at_threshold: system unit scale is exactly zero')
    if scale < 0:
        raise ValueError('invalid system units')
    if not points:
        raise ValueError('empty mesh')
    if not isinstance(rows, (list, tuple)) or len(rows) != 4:
        raise ValueError('partial transform')
    matrix = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError('partial transform')
        nums = []
        for coord in row:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(float(coord)):
                raise ValueError('non-finite transform')
            nums.append(float(coord))
        matrix.append(nums)
    out = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError('partial vertex')
        coords = []
        for coord in point:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(float(coord)):
                raise ValueError('non-finite vertex')
            coords.append(float(coord))
        x, y, z = coords
        r1, r2, r3, r4 = matrix
        out.append((
            (x * r1[0] + y * r2[0] + z * r3[0] + r4[0]) * scale,
            (x * r1[1] + y * r2[1] + z * r3[1] + r4[1]) * scale,
            (x * r1[2] + y * r2[2] + z * r3[2] + r4[2]) * scale,
        ))
    return out


def _bounds_of(points):
    if not points:
        raise ValueError('empty bounds')
    return (
        tuple(min(point[axis] for point in points) for axis in range(3)),
        tuple(max(point[axis] for point in points) for axis in range(3)),
    )


def assert_world_bounds(got, expected, tol=BOUNDS_TOL_M):
    """Readback of emitted world bounds. A difference of exactly ``tol`` is an error."""
    if not got or not expected:
        raise ValueError('empty bounds')
    boxes = []
    for box in (got, expected):
        if not isinstance(box, (list, tuple)) or len(box) != 2:
            raise ValueError('partial bounds')
        nums = []
        for corner in box:
            if not isinstance(corner, (list, tuple)) or len(corner) != 3:
                raise ValueError('partial bounds')
            triple = []
            for coord in corner:
                if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(float(coord)):
                    raise ValueError('non-finite bounds')
                triple.append(float(coord))
            nums.append(triple)
        boxes.append(nums)
    worst = max(abs(boxes[0][corner][axis] - boxes[1][corner][axis]) for corner in range(2) for axis in range(3))
    if _exactly(worst, tol):
        raise ValueError('at_threshold: emitted world bounds differ by exactly the tolerance')
    if worst > tol:
        raise ValueError(f'emitted world bounds differ by {worst}')


def ucx_export_names(mesh_name, count):
    """Export-copy name and UCX piece names bound to that mesh identity."""
    if not isinstance(mesh_name, str) or not mesh_name.strip():
        raise ValueError('unmapped mesh name')
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError('empty UCX name family')
    if count > MAX_PIECES:
        raise ValueError(f'{count} pieces > {MAX_PIECES}')
    export = mesh_name + '_AGR_ucx_'
    pieces = [f'UCX_{mesh_name}_{index:02d}' for index in range(1, count + 1)]
    return export, pieces


def assert_ucx_names_bound(mesh_name, planned_names):
    if not isinstance(planned_names, (list, tuple)) or not planned_names:
        raise ValueError('empty UCX name family')
    export, pieces = ucx_export_names(mesh_name, len(planned_names))
    if list(planned_names) != pieces:
        raise ValueError(f'UCX names {planned_names[0]!r} are not bound to export mesh {mesh_name!r}')
    return export, pieces


def reserve_ucx_names(existing, families):
    """Reject an occupied export/UCX name before the caller creates anything.

    ``existing`` is not modified. The error names the occupied name.
    """
    if not isinstance(families, (list, tuple)) or not families:
        raise ValueError('empty target set')
    if not isinstance(existing, (list, tuple)):
        raise ValueError('partial name set')
    occupied = []
    for name in existing:
        if not isinstance(name, str) or not name.strip():
            raise ValueError('unmapped mesh name')
        occupied.append(name)
    taken = set(occupied)
    claimed = []
    for family in families:
        if not isinstance(family, (list, tuple)) or len(family) != 2:
            raise ValueError('partial UCX name family')
        export, pieces = family
        if not isinstance(export, str) or not export.strip():
            raise ValueError('unmapped mesh name')
        if not isinstance(pieces, (list, tuple)) or not pieces:
            raise ValueError('empty UCX name family')
        for name in (export, *pieces):
            if not isinstance(name, str) or not name.strip():
                raise ValueError('unmapped mesh name')
            if name in taken or name in claimed:
                raise ValueError('occupied name ' + name)
            claimed.append(name)
    return claimed


def _text_finite(value, label):
    if not isinstance(value, str):
        raise ValueError('partial ' + label)
    token = value.strip().lower()
    if token in {'nan', '+nan', '-nan', 'inf', '+inf', '-inf'}:
        raise ValueError('non-finite ' + label)
    return value


def _canonical_record(rec):
    if not isinstance(rec, dict):
        raise ValueError('partial geometry digest')
    if set(rec) != set(DIGEST_KEYS):
        missing = [key for key in DIGEST_KEYS if key not in rec]
        extra = sorted(set(rec) - set(DIGEST_KEYS))
        if missing:
            raise ValueError('unmapped key ' + missing[0])
        raise ValueError('unmapped key ' + extra[0])
    handle = rec['handle']
    if isinstance(handle, bool) or not isinstance(handle, int):
        raise ValueError('partial geometry digest')
    name = _text_finite(rec['name'], 'mesh name')
    if not name.strip():
        raise ValueError('unmapped mesh name')
    parent = rec['parent']
    if parent is not None and (isinstance(parent, bool) or not isinstance(parent, int)):
        raise ValueError('partial geometry digest')
    material = rec['material']
    if material is not None:
        material = _text_finite(material, 'material')
    vertices = []
    if not isinstance(rec['vertices'], (list, tuple)) or not rec['vertices']:
        raise ValueError('partial vertex')
    for point in rec['vertices']:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError('partial vertex')
        quantized = []
        for coord in point:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(float(coord)):
                raise ValueError('non-finite vertex')
            quantized.append(int(round(float(coord) / DIGEST_TOL_M)))
        vertices.append(quantized)
    faces = []
    if not isinstance(rec['faces'], (list, tuple)) or not rec['faces']:
        raise ValueError('partial face')
    for face in rec['faces']:
        if not isinstance(face, (list, tuple)) or len(face) != 3:
            raise ValueError('partial face')
        indexes = []
        for index in face:
            if isinstance(index, bool) or not isinstance(index, int):
                raise ValueError('partial face')
            indexes.append(index)
        faces.append(indexes)
    return {
        'handle': handle,
        'name': name,
        'base_class': _text_finite(rec['base_class'], 'base class'),
        'transform': _text_finite(rec['transform'], 'transform'),
        'object_transform': _text_finite(rec['object_transform'], 'object transform'),
        'parent': parent,
        'properties': _text_finite(rec['properties'], 'properties'),
        'material': material,
        'vertices': vertices,
        'faces': faces,
    }


def geometry_digest(records):
    """Identity, transform, properties and quantized evaluated geometry."""
    if not isinstance(records, (list, tuple)) or not records:
        raise ValueError('empty geometry digest')
    payload = [_canonical_record(rec) for rec in records]
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def _vertex_delta(stored, current):
    if len(stored) != len(current):
        return None
    worst = 0.0
    for left, right in zip(stored, current):
        lv, rv = left.get('vertices'), right.get('vertices')
        if not isinstance(lv, (list, tuple)) or not isinstance(rv, (list, tuple)) or len(lv) != len(rv):
            return None
        for a, b in zip(lv, rv):
            if len(a) != 3 or len(b) != 3:
                return None
            for x, y in zip(a, b):
                if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    return None
                if not math.isfinite(float(x)) or not math.isfinite(float(y)):
                    raise ValueError('non-finite vertex')
                worst = max(worst, abs(float(x) - float(y)))
    return worst


def assert_preview_current(stored, current):
    """The stored preview must still describe this geometry. Exactly one tolerance step is an error."""
    if not stored or not current:
        raise ValueError('empty ucx preview')
    delta = _vertex_delta(stored, current)
    if delta is not None and _exactly(delta, DIGEST_TOL_M):
        raise ValueError('at_threshold: ucx preview geometry moved by exactly the tolerance')
    if geometry_digest(stored) != geometry_digest(current):
        raise ValueError('stale or altered ucx preview; run dry-run again')


def _single_hull(verts, tris):
    used = sorted({index for face in tris for index in face})
    pts = [verts[index] for index in used]
    hull = None
    try:
        hull = _convex_hull(pts)
    except ValueError as exc:
        text = str(exc)
        if any(word in text for word in ('at_threshold', 'non-finite', 'partial', 'empty')):
            raise
        hull = None
    if hull is not None and accept_hull_volume(_volume(hull[0], hull[1])) == 'hull':
        return [hull]
    angle = facade_angle(verts, tris)
    framed = [_rotate(point, -angle) for point in pts]
    flo = [min(point[axis] for point in framed) for axis in range(3)]
    fhi = [max(point[axis] for point in framed) for axis in range(3)]
    for axis in range(3):
        if fhi[axis] - flo[axis] < MIN_THICK_M:
            mid = (fhi[axis] + flo[axis]) / 2
            flo[axis], fhi[axis] = mid - MIN_THICK_M / 2, mid + MIN_THICK_M / 2
    corners, faces = _box_piece(flo, fhi)
    return [([_rotate(point, angle) for point in corners], faces)]


def _levels(verts, tris):
    buckets = {}
    for i0, i1, i2 in tris:
        n = _cross(_sub(verts[i1], verts[i0]), _sub(verts[i2], verts[i0]))
        length = _norm(n)
        area = length / 2
        if area <= 0 or abs(n[2]) < 0.999 * length:
            continue
        z = round((verts[i0][2] + verts[i1][2] + verts[i2][2]) / 3, 3)
        buckets[z] = buckets.get(z, 0.0) + area
    lo = min(point[2] for point in verts)
    hi = max(point[2] for point in verts)
    cuts = [lo] + [z for z in sorted(buckets) if buckets[z] >= LEVEL_AREA_M2 and lo < z < hi] + [hi]
    out = [cuts[0]]
    for z in cuts[1:]:
        if z - out[-1] >= LEVEL_MIN_M:
            out.append(z)
    if out[-1] != hi:
        out[-1] = hi
    return out


def _edges(tris):
    seen = set()
    for face in tris:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            seen.add((a, b) if a < b else (b, a))
    return seen


def _plan_hull(points):
    pts = sorted({(round(float(x), 9), round(float(y), 9)) for x, y in points})
    if len(pts) < 3:
        return pts

    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for point in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], point) <= 1e-12:
            lower.pop()
        lower.append(point)
    for point in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], point) <= 1e-12:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _simplify(poly, tol=SIMPLIFY_M):
    pts = list(poly)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        best, index = tol, None
        for i in range(len(pts)):
            a, p, b = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            ab = (b[0] - a[0], b[1] - a[1])
            length = math.hypot(ab[0], ab[1])
            dist = abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / length if length > 0 else 0.0
            if dist < best:
                best, index = dist, i
        if index is not None:
            pts.pop(index)
            changed = True
    return pts


def _prism(poly, z0, z1):
    k = len(poly)
    verts = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    tris = [(0, i + 1, i) for i in range(1, k - 1)] + [(k, k + i, k + i + 1) for i in range(1, k - 1)]
    for i in range(k):
        j = (i + 1) % k
        tris += [(i, j, k + j), (i, k + j, k + i)]
    return verts, tuple(tris)


def _slice_prisms(verts, tris):
    zs = _levels(verts, tris)
    if len(zs) < 2:
        raise ValueError('slice-prisms: the mesh has no height')
    edges = _edges(tris)
    pieces = []
    for z0, z1 in zip(zs[:-1], zs[1:]):
        pts = [(point[0], point[1]) for point in verts if z0 <= point[2] <= z1]
        for ia, ib in edges:
            a, b = verts[ia], verts[ib]
            for z in (z0, z1):
                if (a[2] - z) * (b[2] - z) < 0:
                    scale = (z - a[2]) / (b[2] - a[2])
                    pts.append((a[0] + (b[0] - a[0]) * scale, a[1] + (b[1] - a[1]) * scale))
        poly = _simplify(_plan_hull(pts))
        if len(poly) < 3:
            continue
        pieces.append(_prism(poly, z0 + MERGE_GAP_M / 2, z1 - MERGE_GAP_M / 2))
    if not pieces:
        raise ValueError('slice-prisms: no pieces')
    return pieces


def _sample(verts, tris, spacing):
    groups = {}
    for i0, i1, i2 in tris:
        a, b, c = verts[i0], verts[i1], verts[i2]
        longest = max(
            math.dist(a, b), math.dist(b, c), math.dist(c, a),
        )
        steps = max(1, int(math.ceil(longest / spacing)))
        groups.setdefault(steps, []).append((a, b, c))
    points = []
    for steps in sorted(groups):
        for a, b, c in groups[steps]:
            for i in range(steps + 1):
                for j in range(steps + 1):
                    if i + j <= steps:
                        u, w = i / steps, j / steps
                        points.append((
                            a[0] + (b[0] - a[0]) * u + (c[0] - a[0]) * w,
                            a[1] + (b[1] - a[1]) * u + (c[1] - a[1]) * w,
                            a[2] + (b[2] - a[2]) * u + (c[2] - a[2]) * w,
                        ))
    return points


def _flood(surface, nx, ny, nz):
    def at(x, y, z):
        return (x * ny + y) * nz + z

    total = nx * ny * nz
    exterior = bytearray(total)
    queue = deque()

    def seed(x, y, z):
        index = at(x, y, z)
        if surface[index] or exterior[index]:
            return
        exterior[index] = 1
        queue.append((x, y, z))

    for x in range(nx):
        for y in range(ny):
            seed(x, y, 0)
            seed(x, y, nz - 1)
        for z in range(nz):
            seed(x, 0, z)
            seed(x, ny - 1, z)
    for y in range(ny):
        for z in range(nz):
            seed(0, y, z)
            seed(nx - 1, y, z)
    while queue:
        x, y, z = queue.popleft()
        for nx_, ny_, nz_ in ((x - 1, y, z), (x + 1, y, z), (x, y - 1, z), (x, y + 1, z), (x, y, z - 1), (x, y, z + 1)):
            if 0 <= nx_ < nx and 0 <= ny_ < ny and 0 <= nz_ < nz:
                seed(nx_, ny_, nz_)
    return exterior


def _greedy(solid, nx, ny, nz, order):
    perm = (order[2], order[1], order[0])
    dims = (nx, ny, nz)
    shaped = [dims[axis] for axis in perm]

    def rem(a, b, c):
        xyz = [0, 0, 0]
        xyz[perm[0]], xyz[perm[1]], xyz[perm[2]] = a, b, c
        return solid[(xyz[0] * ny + xyz[1]) * nz + xyz[2]]

    def clear(a0, a1, b0, b1, c0, c1):
        for a in range(a0, a1):
            for b in range(b0, b1):
                for c in range(c0, c1):
                    xyz = [0, 0, 0]
                    xyz[perm[0]], xyz[perm[1]], xyz[perm[2]] = a, b, c
                    solid[(xyz[0] * ny + xyz[1]) * nz + xyz[2]] = 0

    boxes = []
    for a in range(shaped[0]):
        for b in range(shaped[1]):
            for c in range(shaped[2]):
                if not rem(a, b, c):
                    continue
                c1 = c + 1
                while c1 < shaped[2] and rem(a, b, c1):
                    c1 += 1
                b1 = b + 1
                while b1 < shaped[1] and all(rem(a, b1, cc) for cc in range(c, c1)):
                    b1 += 1
                a1 = a + 1
                while a1 < shaped[0] and all(rem(a1, bb, cc) for bb in range(b, b1) for cc in range(c, c1)):
                    a1 += 1
                clear(a, a1, b, b1, c, c1)
                lo, hi = [0, 0, 0], [0, 0, 0]
                for axis, value0, value1 in zip(perm, (a, b, c), (a1, b1, c1)):
                    lo[axis], hi[axis] = value0, value1
                boxes.append((tuple(lo), tuple(hi)))
    return boxes


def _kernel_boxes(verts, tris, model_triangles):
    angle = facade_angle(verts, tris)
    framed = [_rotate(point, -angle) for point in verts]
    limit = triangle_limit(model_triangles)
    cell = CELL_M
    budget = limit
    if budget < 12:
        raise ValueError(f'UCX triangles leave no box inside the budget {limit}')
    points = _sample(framed, tris, cell / 2)
    if not points:
        raise ValueError('empty mesh')
    origin = [min(point[axis] for point in points) - cell for axis in range(3)]
    dims = [int(math.ceil((max(point[axis] for point in points) - origin[axis]) / cell)) + 2 for axis in range(3)]
    if dims[0] * dims[1] * dims[2] > 60_000_000:
        raise ValueError(f'voxel grid {dims} too large for cell {cell} m')
    surface = bytearray(dims[0] * dims[1] * dims[2])
    for point in points:
        idx = []
        for axis in range(3):
            slot = math.floor((point[axis] - origin[axis]) / cell)
            if slot < 0:
                slot = 0
            if slot >= dims[axis]:
                slot = dims[axis] - 1
            idx.append(slot)
        surface[(idx[0] * dims[1] + idx[1]) * dims[2] + idx[2]] = 1
    exterior = _flood(surface, *dims)
    solid = bytearray(1 if not exterior[i] else 0 for i in range(len(exterior)))
    best = None
    for order in ((2, 0, 1), (0, 1, 2), (1, 0, 2)):
        boxes = _greedy(bytearray(solid), *dims, order)
        if best is None or len(boxes) < len(best):
            best = boxes
    if not best:
        raise ValueError('kernel-boxes: no pieces')
    if 12 * len(best) > budget or len(best) > MAX_PIECES:
        raise ValueError(f'kernel-boxes: {12 * len(best)} triangles exceed the budget {budget}')
    pieces = []
    for lo, hi in best:
        lo_w = [origin[axis] + lo[axis] * cell + GAP_M / 2 for axis in range(3)]
        hi_w = [origin[axis] + hi[axis] * cell - GAP_M / 2 for axis in range(3)]
        if any(hi_w[axis] <= lo_w[axis] for axis in range(3)):
            raise ValueError('kernel-boxes: collapsed box')
        corners, faces = _box_piece(lo_w, hi_w)
        pieces.append(([_rotate(point, angle) for point in corners], faces))
    return pieces


def _variant_of(kind):
    if kind not in KIND_VARIANT:
        raise ValueError(f'unmapped object kind {kind!r}')
    return KIND_VARIANT[kind]


def _measure_kind(verts, tris):
    volume = _volume(verts, tris)
    angle = facade_angle(verts, tris)
    framed = [_rotate(point, -angle) for point in verts]
    lo = [min(point[axis] for point in framed) for axis in range(3)]
    hi = [max(point[axis] for point in framed) for axis in range(3)]
    span = [hi[axis] - lo[axis] for axis in range(3)]
    aabb = abs(span[0] * span[1] * span[2])
    if aabb <= 0:
        raise ValueError('at_threshold: zero facade volume')
    outside = 1.0 - volume / aabb
    bands = len(_levels(verts, tris)) - 1
    return kind_from_outside(outside, bands)


def _audit(names, pieces, mesh):
    path = Path(__file__).with_name('ucx_audit_core.py')
    if path.is_file():
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location('agr_ucx_audit_core', path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    else:
        from twinqa.geometry import ucx_audit as mod
    hulls = []
    closed = True
    for name, (pv, pt) in zip(names, pieces):
        verts = [tuple(map(float, point)) for point in pv]
        faces = [tuple(map(int, face)) for face in pt]
        hulls.append({'name': name, 'verts': verts, 'tris': faces})
        verdict = mod.classify(verts, faces)
        if verdict.get('closed') is not True or verdict.get('convex') is not True or verdict.get('status') == 'review':
            closed = False
    raw = mod.collision_findings(hulls)
    collision, unmeasurable = [], []
    for item in raw:
        if item.get('type') == 'not_run':
            unmeasurable.append(str(item.get('reason')))
        else:
            collision.append(str(item.get('type')))
    report = mod.name_report(list(names), mesh)
    return {
        'collision': collision,
        'unmeasurable': unmeasurable,
        'mask_bad_count': int(report['mask_bad_count']),
        'closed': closed,
    }


def _names(mesh, count):
    if not isinstance(mesh, str) or not mesh.strip():
        raise ValueError('unmapped mesh name')
    if count > MAX_PIECES:
        raise ValueError(f'{count} pieces > {MAX_PIECES}')
    return [f'UCX_{mesh}_{index:02d}' for index in range(1, count + 1)]


def build(verts, tris, *, mesh, kind=None, model_triangles=None):
    """Build UCX pieces for one mesh. The input sequences are not modified."""
    points, faces = _check(verts, tris)
    if kind is None:
        chosen, variant = _measure_kind(points, faces)
    else:
        variant = _variant_of(kind)
        chosen = kind
    count = len(faces) if model_triangles is None else model_triangles
    if variant == 'single-hull':
        pieces = _single_hull(points, faces)
    elif variant == 'slice-prisms':
        pieces = _slice_prisms(points, faces)
    elif variant == 'kernel-boxes':
        pieces = _kernel_boxes(points, faces, count)
    else:
        raise ValueError(f'unmapped object kind {chosen!r}')
    if not pieces:
        raise ValueError(f'{variant}: no pieces')
    triangles = sum(len(face) for _, face in pieces)
    limit = triangle_limit(count if isinstance(count, int) and not isinstance(count, bool) else len(faces))
    verdict = budget_verdict(triangles, limit)
    names = _names(mesh, len(pieces))
    audit = _audit(names, pieces, mesh)
    findings = []
    if verdict['status'] != 'pass':
        findings.append({'code': 'at_threshold', 'ids': [1], 'detail': f'triangles={triangles} limit={limit}'})
    if audit['collision']:
        findings.append({'code': 'ucx_audit', 'ids': list(range(1, len(pieces) + 1)),
                         'detail': ','.join(audit['collision'])})
    if audit['unmeasurable'] or not audit['closed']:
        findings.append({'code': 'ucx_unmeasurable', 'ids': list(range(1, len(pieces) + 1)),
                         'detail': ','.join(audit['unmeasurable']) or 'open or non-convex'})
    status = 'fail' if findings else 'pass'
    return {
        'kind': chosen,
        'variant': variant,
        'pieces_count': len(pieces),
        'triangles': triangles,
        'limit': limit,
        'names': names,
        'status': status,
        'audit': audit,
        'findings': findings,
        'pieces': pieces,
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
    for i, (left, path_a) in enumerate(roles):
        for right, path_b in roles[i + 1:]:
            if _same(path_a, path_b):
                raise ValueError(f'{right} path is the input path: {path_b}')
    data = (json.dumps(payload, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with dest.open('xb') as handle:
        handle.write(data)
    if report is not None:
        with Path(report).open('xb') as handle:
            handle.write(data)
    return dest
