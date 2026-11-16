"""new-case: world box UV projection of a tiling trim at panel scale, target object only (#1538).

Re-unwrap of a tiling (repeating) texture defaults to a world box projection at the texture's panel
scale (session 0a21d4de, elv-tc-vpm, 2026-11-16: per-tile snapping and neighbour propagation broke the
panel joints; Artem's "UVW-map box 5-5-5 m" was accepted). docs/domain/uv-textures.md.

- every listed face is projected on its dominant world axis (+-X, +-Y, +-Z) in metres, scaled by
  px_per_m / texture_px, so one texture period = 1.0 UV and texel density = px_per_m;
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
EPS = 1e-9                              # periods (5 nm at a 5 m period): period-line and tile-fit tolerance


class BoxUVError(ValueError):
    """Invalid input for the box projection; nothing was written."""


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


def on_period_line(a, b, scale):
    """True when edge a-b (planar metres) lies on one world period line u = k or v = k (UV units)."""
    for i in (0, 1):
        pa, pb = a[i] * scale, b[i] * scale
        k = round(pa)
        if abs(pa - k) <= EPS and abs(pb - k) <= EPS:
            return True
    return False


def _ordered(ids):
    try:
        return sorted(ids)
    except TypeError:
        return sorted(ids, key=repr)


def plan_box_uv(faces, px_per_m, tile, *, texture_px=4096, margin_px=8):
    """faces: [(face_id, [vertex_key, ...], [(x, y, z) world, ...]), ...].

    Returns (uvs, report): uvs = {face_id: [(u, v) per corner]}. Raises BoxUVError / BoxUVOverflow."""
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
    edge_owner, period_cuts = {}, 0
    for fid, verts, _ in faces:
        corner = dict(zip(verts, metres[fid]))
        for a, b in zip(verts, verts[1:] + verts[:1]):
            e = (keys[fid], frozenset((a, b)))
            if e not in edge_owner:
                edge_owner[e] = fid
            elif on_period_line(corner[a], corner[b], scale):
                period_cuts += 1      # world period line: island border, the jump there is a whole period
            else:
                parent[find(fid)] = find(edge_owner[e])
    islands = {}
    for fid, _, _ in faces:
        islands.setdefault(find(fid), []).append(fid)
    uvs, overflow, report_islands = {}, [], []
    for members in islands.values():
        pts = [(u * scale, v * scale) for f in members for u, v in metres[f]]
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
            uvs[f] = [(_snap(u * scale - ku) + tu, _snap(v * scale - kv) + tv) for u, v in metres[f]]
    if overflow:
        worst = overflow[0]
        period = texture_px / px
        raise BoxUVOverflow(
            f'{len(overflow)} island(s) do not fit tile {tile} with margin {margin_px} px at their world phase, '
            f'first: axis {worst["axis"]} faces {worst["faces"][:8]} span {worst["span"]} periods; cut the faces '
            f'on world period lines (k * {period:g} m, a cut elsewhere keeps the island connected) or lower '
            f'px_per_m; an island that touches a period line fits only with margin_px=0 (tile margin vs world '
            f'phase: docs/domain/conflicts.md)')
    return uvs, {'tile': tile, 'px_per_m': px, 'texture_px': texture_px, 'period_m': texture_px / px,
                 'faces': len(uvs), 'islands': report_islands, 'period_cut_edges': period_cuts}


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
    for i in ids:
        poly = mesh.polygons[i]
        plan_in.append((i, list(poly.vertices), [tuple(mw @ mesh.vertices[v].co) for v in poly.vertices]))
    uvs, report = plan_box_uv(plan_in, px_per_m, tile, texture_px=texture_px, margin_px=margin_px)
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
