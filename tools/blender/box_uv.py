"""new-case: world box UV projection of a tiling trim at panel scale, target object only (#1538).

Re-unwrap of a tiling (repeating) texture defaults to a world box projection at the texture's panel
scale (session 0a21d4de, elv-tc-vpm, 2026-11-16: per-tile snapping and neighbour propagation broke the
panel joints; Artem's "UVW-map box 5-5-5 m" was accepted). docs/domain/uv-textures.md.

- every listed face is projected on its dominant world axis (+-X, +-Y, +-Z) in metres, scaled by
  px_per_m / texture_px, so one texture period = 1.0 UV. Directional texel (#1574): along the face's trace
  on the projection plane it is px_per_m, across it px_per_m * |n_axis| (unit normal component on the
  dominant axis, >= 1/sqrt(3)), so a rotated or sloped face gets less than px_per_m (a wall rotated 40 deg
  at 819.2 px/m: 627.5 px/m). Both singular values of every face's UV-px / metre Jacobian (per fan
  triangle, so a non-planar face is checked too) must lie in 512..1706, else BoxUVTexelError names the
  faces and the least px_per_m at which they all pass; nothing is written. The report carries the range
  as texel_px_per_m;
- the winding of the projection follows the face normal (no mirrored islands, walls keep V = world Z);
- listed faces that share an edge and the same axis form one island, except across an edge that lies on a
  world period line (both ends on u = k or v = k periods, #1573): such an edge is an island border; each
  island moves by a whole number of periods (integers in UV) into the UDIM tile, so the UV jump across any
  edge between coplanar faces (period-line borders included) is a whole number of periods and the joints
  stay continuous;
- an island that cannot fit the tile with the margin at its world phase raises BoxUVOverflow and nothing
  is written. Remedy: cut the faces on world period lines (k * period_m; a cut elsewhere keeps the island
  connected) or lower px_per_m within 512..1706. An island touching a period line has phase 0 there, so it
  fits only with margin_px=0; tile margin vs world phase is an open conflict (docs/domain/conflicts.md);
- period borders and tile fit share float32 world-phase normalization (#1600): three float32 ULPs
  at the input magnitude (sum of absolute transform terms), capped at half a texture pixel. UVs use
  that same normalized phase (including before whole-period subtraction); cuts outside that budget stay connected;
- UVs are written through the mesh data API (no bpy.ops, no selection, no edit mode), only to the loops of
  the listed faces of the one target object; uv_fingerprint / uv_violations prove other objects (glass,
  UCX, ...) and unlisted faces kept their UV state.

The planning core is pure Python (plan_box_uv); box_project_uv is the thin Blender wrapper.
Atlas packing and unique (non-tiling) textures are out of scope.
"""
import hashlib
import math
import numbers
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'))
import udimtile_core  # noqa: E402

TEXEL_MIN, TEXEL_MAX = 512.0, 1706.0   # reg p.32 §6.2, inclusive
LAST_UDIM = 1100                        # reg p.23, p.31 §2.1.3: 10x10 grid 1001-1100
AXES = ('+x', '-x', '+y', '-y', '+z', '-z')
EPS = 1e-9                              # periods: residual float64 arithmetic tolerance
PERIOD_SNAP_PX = 0.5                    # never correct a world phase by more than half a texel
TEXEL_RTOL = 1e-9                       # relative float tolerance of the inclusive texel bounds


class BoxUVError(ValueError):
    """Invalid input for the box projection; nothing was written."""


class BoxUVTexelError(BoxUVError):
    """A face's directional texel is outside 512..1706 px/m; nothing was written."""


class BoxUVOverflow(BoxUVError):
    """An island does not fit the tile at its world phase; nothing was written."""


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise BoxUVError(f'{name} must be a finite number: {value!r}')
    return float(value)


def validate_params(px_per_m, tile, texture_px, margin_px):
    px = _finite(px_per_m, 'px_per_m')
    if not TEXEL_MIN <= px <= TEXEL_MAX:
        raise BoxUVError(f'px_per_m {px!r} outside {TEXEL_MIN:g}..{TEXEL_MAX:g} (reg p.32 §6.2)')
    if isinstance(texture_px, bool) or not isinstance(texture_px, numbers.Integral) or texture_px <= 0:
        raise BoxUVError(f'texture_px must be a positive integer: {texture_px!r}')
    margin = _finite(margin_px, 'margin_px')
    if margin < 0 or 2 * margin >= texture_px:
        raise BoxUVError(f'margin_px {margin_px!r} outside [0, texture_px / 2)')
    try:
        origin = udimtile_core.tile_origin(tile)
    except ValueError as exc:
        raise BoxUVError(str(exc)) from None
    if tile > LAST_UDIM:
        raise BoxUVError(f'UDIM tile {tile!r} outside 1001..{LAST_UDIM}')
    return px, origin, margin / texture_px


def newell_normal(coords):
    nx = ny = nz = 0.0
    for (x0, y0, z0), (x1, y1, z1) in zip(coords, coords[1:] + coords[:1]):
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def axis_key(normal):
    """Dominant world axis of a normal; ties prefer Z, then X (same order as vpm_uv.project)."""
    nx, ny, nz = normal
    ax, ay, az = abs(nx), abs(ny), abs(nz)
    if not all(math.isfinite(c) for c in normal) or max(ax, ay, az) <= 1e-12:
        raise BoxUVError(f'degenerate or non-finite face normal: {normal!r}')
    if az >= ax and az >= ay:
        return '+z' if nz > 0 else '-z'
    if ax >= ay:
        return '+x' if nx > 0 else '-x'
    return '+y' if ny > 0 else '-y'


def axis_uv(co, key):
    """World metres -> planar (u, v) metres; right-handed about the axis, so winding is kept."""
    x, y, z = co
    return {'+z': (x, y), '-z': (x, -y), '+x': (y, z), '-x': (-y, z),
            '+y': (-x, z), '-y': (x, z)}[key]


def _snap(p):
    """Phase within EPS of a whole period -> that whole period (keeps a period-aligned side on the tile edge)."""
    r = round(p)
    return float(r) if abs(p - r) <= EPS else p


def _period_coord(metres, scale, texture_px, magnitude=None):
    """Canonical world phase for both island borders and tile fit (#1600).

    Blender world coordinates are float32: allow three ULPs at the ORIGINAL input
    magnitude, plus float64 arithmetic slack. The wrapper includes translation and
    absolute local*matrix terms, not just the possibly cancelled result. Without
    transform metadata the planner uses the world magnitude. Cap at half a texel; at
    larger coordinates unresolved cuts deliberately remain fail-closed. Normalize
    before subtracting the island shift, otherwise that magnitude would be lost.
    This is rounding correction, not permission to pack or rescale an island.
    """
    p = metres * scale
    magnitude = abs(metres) if magnitude is None else max(abs(metres), magnitude)
    ulps = 3 * math.ldexp(1.0, math.frexp(magnitude)[1] - 24) * scale
    tolerance = min(PERIOD_SNAP_PX / texture_px, max(EPS, ulps + EPS))
    k = round(p)
    return float(k) if abs(p - k) <= tolerance else p


def on_period_line(a, b, scale, texture_px=4096, a_magnitude=None, b_magnitude=None):
    """True when both endpoints normalize to the SAME world period line."""
    for i in (0, 1):
        pa = _period_coord(a[i], scale, texture_px, None if a_magnitude is None else a_magnitude[i])
        pb = _period_coord(b[i], scale, texture_px, None if b_magnitude is None else b_magnitude[i])
        if pa == round(pa) and pb == pa:
            return True
    return False


def face_texel(coords, key, px):
    """(min, max) singular value in px/m of the map world face -> UV pixels (projection along `key` x px).

    Projecting a plane with unit normal n onto the coordinate plane of axis a keeps lengths along the plane's
    trace (singular value 1) and scales the direction across it by |n . a|; so the singular values are px
    and px * |n_a| / |n|. Evaluated for the Newell normal and for every fan triangle whose area is at least
    1e-6 of the face area (a non-planar face is checked per piece; slivers of collinear corners, whose
    normal is roundoff, are skipped)."""
    axis = 'xyz'.index(key[1])
    face_n = newell_normal(coords)
    face_len = math.sqrt(sum(c * c for c in face_n))
    normals = [list(face_n)]
    p0 = coords[0]
    for i in range(1, len(coords) - 1):
        d1 = [coords[i][k] - p0[k] for k in range(3)]
        d2 = [coords[i + 1][k] - p0[k] for k in range(3)]
        t = [d1[(k + 1) % 3] * d2[(k + 2) % 3] - d1[(k + 2) % 3] * d2[(k + 1) % 3] for k in range(3)]
        if math.sqrt(sum(c * c for c in t)) >= 1e-6 * face_len:
            normals.append(t)
    ratios = [abs(n[axis]) / math.sqrt(sum(c * c for c in n)) for n in normals]
    return px * min(ratios), px                  # |n_a| / |n| <= 1: the trace direction keeps px


def check_texel(faces, keys, px):
    """Per-face directional texel; raises BoxUVTexelError naming every face outside 512..1706."""
    lo_all, hi_all, bad = math.inf, -math.inf, []
    for fid, _, coords in faces:
        lo, hi = face_texel([tuple(map(float, c)) for c in coords], keys[fid], px)
        lo_all, hi_all = min(lo_all, lo), max(hi_all, hi)
        if lo < TEXEL_MIN * (1 - TEXEL_RTOL) or hi > TEXEL_MAX * (1 + TEXEL_RTOL):
            bad.append((lo, fid, hi))
    if bad:
        bad.sort(key=lambda b: b[0])
        # texel is linear in px: the least px at which every face reaches the floor (max texel = px <= 1706)
        need = (math.ceil(max(px * TEXEL_MIN / lo for lo, _, _ in bad) * 10) / 10
                if all(lo > 0 for lo, _, _ in bad) else math.inf)
        listed = ', '.join(f'face {fid!r} ({lo:.1f}..{hi:.1f} px/m)' for lo, fid, hi in bad[:8])
        remedy = (f'raise px_per_m >= {need:.1f} (<= {TEXEL_MAX:g}), or fix the geometry'
                  if need <= TEXEL_MAX else 'no px_per_m in range fits; fix the geometry')
        raise BoxUVTexelError(
            f'{len(bad)} face(s) have directional texel outside {TEXEL_MIN:g}..{TEXEL_MAX:g} px/m at px_per_m '
            f'{px:g} (box projection compresses a rotated or sloped face by |n_axis|, reg p.32 §6.2): {listed}; '
            f'{remedy}')
    return [round(lo_all, 6), round(hi_all, 6)]


def _ordered(ids):
    try:
        return sorted(ids)
    except TypeError:
        return sorted(ids, key=repr)


def plan_box_uv(faces, px_per_m, tile, *, texture_px=4096, margin_px=8, world_magnitudes=None):
    """faces: [(face_id, [vertex_key, ...], [(x, y, z) world, ...]), ...].

    Optional world_magnitudes maps each vertex key to nonnegative XYZ sums of absolute
    transform input terms (metres), for float32 matrix arithmetic uncertainty.
    Returns (uvs, report): uvs = {face_id: [(u, v) per corner]}; report['texel_px_per_m'] = [min, max]
    directional texel over all faces. Raises BoxUVError / BoxUVTexelError / BoxUVOverflow."""
    px, (tu, tv), margin = validate_params(px_per_m, tile, texture_px, margin_px)
    faces = list(faces)
    if not faces:
        raise BoxUVError('no faces to project')
    seen, keys, scale = set(), {}, px / texture_px
    for fid, verts, coords in faces:
        if fid in seen:
            raise BoxUVError(f'duplicate face {fid!r}')
        seen.add(fid)
        if len(verts) < 3 or len(verts) != len(coords):
            raise BoxUVError(f'face {fid!r}: needs >= 3 corners with one coordinate each')
        if any(not math.isfinite(c) for co in coords for c in co):
            raise BoxUVError(f'face {fid!r}: non-finite vertex')
        keys[fid] = axis_key(newell_normal([tuple(map(float, co)) for co in coords]))
    parent = {fid: fid for fid, _, _ in faces}

    def find(f):
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    metres = {fid: [axis_uv(co, keys[fid]) for co in coords] for fid, _, coords in faces}
    magnitudes = {}
    for fid, verts, coords in faces:
        values = []
        for vertex, co in zip(verts, coords):
            if world_magnitudes is None:
                mag = tuple(abs(c) for c in co)
            else:
                if vertex not in world_magnitudes:
                    raise BoxUVError(f'missing world magnitude for vertex {vertex!r}')
                mag = world_magnitudes[vertex]
                if len(mag) != 3 or any(_finite(c, 'world magnitude') < 0 for c in mag):
                    raise BoxUVError(f'invalid world magnitude for vertex {vertex!r}: {mag!r}')
            values.append(tuple(abs(c) for c in axis_uv(mag, keys[fid])))
        magnitudes[fid] = values
    texel = check_texel(faces, keys, px)
    edge_owner, period_cuts = {}, 0
    for fid, verts, _ in faces:
        corner = dict(zip(verts, metres[fid]))
        corner_mag = dict(zip(verts, magnitudes[fid]))
        for a, b in zip(verts, verts[1:] + verts[:1]):
            e = (keys[fid], frozenset((a, b)))
            if e not in edge_owner:
                edge_owner[e] = fid
            elif on_period_line(corner[a], corner[b], scale, texture_px, corner_mag[a], corner_mag[b]):
                period_cuts += 1      # world period line: island border, the jump there is a whole period
            else:
                parent[find(fid)] = find(edge_owner[e])
    islands = {}
    for fid, _, _ in faces:
        islands.setdefault(find(fid), []).append(fid)
    uvs, overflow, report_islands = {}, [], []
    phases = {f: [tuple(_period_coord(c, scale, texture_px, m) for c, m in zip(p, mag))
                  for p, mag in zip(coords, magnitudes[f])]
              for f, coords in metres.items()}
    for members in islands.values():
        pts = [p for f in members for p in phases[f]]
        umin, vmin = min(p[0] for p in pts), min(p[1] for p in pts)
        umax, vmax = max(p[0] for p in pts), max(p[1] for p in pts)
        ku, kv = math.floor(umin - margin + EPS), math.floor(vmin - margin + EPS)   # whole periods
        hi_u, hi_v = umax - ku, vmax - kv
        entry = {'axis': keys[members[0]], 'faces': _ordered(members), 'shift': [ku, kv],
                 'span': [round(umax - umin, 6), round(vmax - vmin, 6)]}
        report_islands.append(entry)
        if hi_u > 1 - margin + EPS or hi_v > 1 - margin + EPS:
            overflow.append(entry)
            continue
        for f in members:
            uvs[f] = [(_snap(u - ku) + tu, _snap(v - kv) + tv) for u, v in phases[f]]
    if overflow:
        worst = overflow[0]
        period = texture_px / px
        raise BoxUVOverflow(
            f'{len(overflow)} island(s) do not fit tile {tile} with margin {margin_px} px at their world phase, '
            f'first: axis {worst["axis"]} faces {worst["faces"][:8]} span {worst["span"]} periods; cut the faces '
            f'on world period lines (k * {period:g} m, a cut elsewhere keeps the island connected) or lower '
            f'px_per_m; an island that touches a period line fits only with margin_px=0 (tile margin vs world '
            f'phase: docs/domain/conflicts.md). Float32 resolution limit: corrections are capped at '
            f'{PERIOD_SNAP_PX:g} texel; if an exact cut still fails at large coordinates, move the '
            f'geometry and its pivot nearer the origin before cutting')
    return uvs, {'tile': tile, 'px_per_m': px, 'texture_px': texture_px, 'period_m': texture_px / px,
                 'faces': len(uvs), 'islands': report_islands, 'period_cut_edges': period_cuts,
                 'texel_px_per_m': texel}


# ------------------------------------------------------------------ Blender wrapper (data API only)
def _face_ids(faces, count):
    try:
        ids = list(faces)
    except TypeError:
        raise BoxUVError(f'faces must be an iterable of polygon indices: {faces!r}') from None
    for i in ids:
        if isinstance(i, bool) or not isinstance(i, numbers.Integral) or not 0 <= i < count:
            raise BoxUVError(f'face index {i!r} outside 0..{count - 1}')
    return [int(i) for i in ids]


def box_project_uv(obj, faces, px_per_m, tile, *, texture_px=4096, margin_px=8, uv_name=None):
    """Write box-projected UVs of the listed polygons of `obj` (Blender object) into one UV layer.

    The layer is `uv_name`, else the active one, else a new 'UVMap'. Only loops of the listed polygons
    are written. Returns the plan report plus 'uv_layer' and 'created_layer'."""
    if getattr(obj, 'type', None) != 'MESH':
        raise BoxUVError(f'target must be a mesh object: {getattr(obj, "name", obj)!r}')
    mesh = obj.data
    if mesh.users > 1:
        raise BoxUVError(f'mesh {mesh.name!r} of {obj.name!r} has {mesh.users} users; writing would '
                         'change the UVs of other objects')
    ids = _face_ids(faces, len(mesh.polygons))
    mw = obj.matrix_world
    plan_in = []
    world_magnitudes = {}
    for i in ids:
        poly = mesh.polygons[i]
        for v in poly.vertices:
            co = mesh.vertices[v].co
            world_magnitudes[v] = tuple(abs(float(mw[a][3])) + sum(
                abs(float(mw[a][b]) * float(co[b])) for b in range(3)) for a in range(3))
        plan_in.append((i, list(poly.vertices), [tuple(mw @ mesh.vertices[v].co) for v in poly.vertices]))
    uvs, report = plan_box_uv(plan_in, px_per_m, tile, texture_px=texture_px, margin_px=margin_px,
                              world_magnitudes=world_magnitudes)
    layer = mesh.uv_layers.get(uv_name) if uv_name else mesh.uv_layers.active
    created = layer is None
    if created:
        layer = mesh.uv_layers.new(name=uv_name or 'UVMap', do_init=False)
        if layer is None:
            raise BoxUVError(f'mesh {mesh.name!r}: cannot add a UV layer')
    data = layer.uv
    for i in ids:
        poly = mesh.polygons[i]
        for k, li in enumerate(range(poly.loop_start, poly.loop_start + poly.loop_total)):
            data[li].vector = uvs[i][k]
    mesh.update()
    report.update(uv_layer=layer.name, created_layer=created, object=obj.name)
    return report


def _layer_digest(layer, rows=None):
    vals = layer.uv
    idx = range(len(vals)) if rows is None else rows
    return hashlib.sha256(repr([tuple(round(c, 7) for c in vals[i].vector) for i in idx]).encode()).hexdigest()


def uv_fingerprint(objects, detail=None, faces=()):
    """{object name: {'mesh', 'layers': {name: digest}, 'active'}}; for `detail` (an object name) the
    digest per layer covers only loops of polygons NOT in `faces`."""
    out, skip = {}, set(faces)
    for obj in objects:
        rec = {'type': obj.type}
        if obj.type == 'MESH':
            mesh = obj.data
            rows = None
            if obj.name == detail:
                rows = [li for p in mesh.polygons if p.index not in skip
                        for li in range(p.loop_start, p.loop_start + p.loop_total)]
            rec.update(mesh=mesh.name, active=getattr(mesh.uv_layers.active, 'name', None),
                       layers={layer.name: _layer_digest(layer, rows) for layer in mesh.uv_layers})
        out[obj.name] = rec
    return out


def uv_violations(before, after, target, created_layer=None):
    """Differences other than the target object's written layer; [] means only the target changed."""
    bad = []
    if set(before) != set(after):
        bad.append(f'object set changed: +{sorted(set(after) - set(before))} -{sorted(set(before) - set(after))}')
    for name in sorted(set(before) & set(after)):
        b, a = before[name], after[name]
        if name != target:
            if a != b:
                bad.append(f'{name}: UV state changed ({b.get("layers")} -> {a.get("layers")})')
            continue
        added = set(a.get('layers', {})) - set(b.get('layers', {}))
        if added - ({created_layer} if created_layer else set()):
            bad.append(f'{name}: unexpected new UV layer(s) {sorted(added)}')
        if set(b.get('layers', {})) - set(a.get('layers', {})):
            bad.append(f'{name}: UV layer(s) removed')
        for layer, digest in b.get('layers', {}).items():
            if a.get('layers', {}).get(layer) != digest:
                bad.append(f'{name}: unlisted faces changed in layer {layer!r}')
    return bad
