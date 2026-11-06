"""AGR Tools 1.0 (#1024), owned by branch N (improve/issue-1024-vpm-maps): plug islands in UDIM (udim.plugs, station 1.0.21), stdlib only; no pymxs.

Plan row `udim.plugs`, mode `copy`: the faces of the placeholder materials (interior, roof, metal: a solid colour, no
texture) get a small UV island in the centre of the UDIM tile of their material ID, so each UDIM tile that is used
has content for the 256 px placeholder maps (`tex.placeholders`, `vpmmaps_core.build_maps`). Works on an export COPY.

Source idea: team script GridUVLayout22.ms `layoutPlugs` (SHA256 3d4be7e910f70367ce3e806010d8524d2a498ff476c2de840ade64615b2b7824;
read, not copied, #853). Measured by the team-script audit T02 (griduv22, GeoAGR-private work/team-scripts-audit): the island is
a square of 0.05 centred at (0.5, 0.5) of the tile 1000+matID, a fixed tile mode puts all faces into one tile. Defects not repeated:
* it needs the Modify panel and an Unwrap_UVW modifier (`polyop.setMapVert` on the copy instead, host adapter);
* `runPlugs` checks `classOf node` and, after its first run, the node is a PolyMeshObject, so a second run is refused
  with a message box: no class check here, a rerun gives the same UV (idempotent);
* UDIM = 1000 + matID without a range check: an ID outside 1..100 or a work ID >= 1001 is refused (K3);
* it breaks all edges of the selected faces and does not report what it moved: the report lists faces/tiles per
  mesh and an occupied tile centre (a real island already there) as ambiguous.

Tile numbering is per mesh (owner answer V9 06.11.2026): the body starts at 1001 and the windows/glass mesh starts at
1001 too, so `tile(matid) = 1000 + matid` holds inside ONE mesh whose IDs were renumbered dense by vpm.build.
Faces: {'face': int, 'matid': int, 'verts': [(x, y, z), ...]} in metres (units.SystemScale applied by the glue).
"""
import math

PLUG_SIZE = 0.05
PLUG_CENTRE = (0.5, 0.5)
TILES_PER_ROW = 10
MAX_TILE_ID = 100


def tile_for(matid, fixed=None):
    """UDIM number of a face: `fixed` (a tile number 1001..1100) for every face, else 1000 + matID."""
    if fixed is not None:
        if type(fixed) is not int or not 1001 <= fixed <= 1000 + MAX_TILE_ID:
            raise ValueError('fixed UDIM must be 1001..1100: ' + repr(fixed))
        return fixed
    if type(matid) is not int or not 1 <= matid <= MAX_TILE_ID:
        raise ValueError('material ID {} cannot be a UDIM tile (1..{}; IDs >= 1001 are work IDs, K3)'.format(
            matid, MAX_TILE_ID))
    return 1000 + matid


def tile_offset(udim):
    """(du, dv) of a UDIM number: 1001 -> (0, 0), 1011 -> (0, 1), 1012 -> (1, 1)."""
    n = int(udim) - 1001
    if not 0 <= n < MAX_TILE_ID:
        raise ValueError('UDIM must be 1001..1100: ' + repr(udim))
    return n % TILES_PER_ROW, n // TILES_PER_ROW


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(v):
    ln = math.sqrt(_dot(v, v))
    if ln < 1e-12:
        return None
    return (v[0] / ln, v[1] / ln, v[2] / ln)


def face_basis(verts):
    """(u_axis, v_axis) of a planar face: Newell normal, the longest projected edge from vertex 1 as U (the source
    rule), or None for a degenerate face (fewer than 3 vertices, zero area, zero edges)."""
    if len(verts) < 3:
        return None
    nx = ny = nz = 0.0
    for i, p in enumerate(verts):
        q = verts[(i + 1) % len(verts)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    n = _unit((nx, ny, nz))
    if n is None:
        return None
    best, best_len = None, 0.0
    for p in verts[1:]:
        e = _sub(p, verts[0])
        e = _sub(e, tuple(c * _dot(e, n) for c in n))      # onto the face plane
        ln = math.sqrt(_dot(e, e))
        if ln > best_len + 1e-12:
            best, best_len = e, ln
    u = _unit(best) if best else None
    if u is None:
        return None
    return u, _cross(n, u)


def plug_uv(verts, udim, size=PLUG_SIZE, centre=PLUG_CENTRE):
    """UV (u, v) per vertex: the face fitted uniformly (aspect kept) into a `size` square centred at `centre` of the
    tile `udim`. Degenerate face -> None."""
    basis = face_basis(verts)
    if basis is None:
        return None
    u_ax, v_ax = basis
    flat = [(_dot(p, u_ax), _dot(p, v_ax)) for p in verts]
    umin, umax = min(p[0] for p in flat), max(p[0] for p in flat)
    vmin, vmax = min(p[1] for p in flat), max(p[1] for p in flat)
    span = max(umax - umin, vmax - vmin)
    if span < 1e-12:
        return None
    k = size / span
    cu, cv = (umin + umax) / 2.0, (vmin + vmax) / 2.0
    du, dv = tile_offset(udim)
    return [((p[0] - cu) * k + centre[0] + du, (p[1] - cv) * k + centre[1] + dv) for p in flat]


def plug_options(options):
    o = dict(options or {})
    known = {'size', 'fixed_udim', 'matids', 'occupied', 'centre'}
    extra = sorted(set(o) - known)
    if extra:
        raise ValueError('unknown options: ' + ', '.join(extra))
    size = o.get('size', PLUG_SIZE)
    if not isinstance(size, (int, float)) or isinstance(size, bool) or not 0 < size <= 0.5:
        raise ValueError('size must be in (0, 0.5] of a tile')
    centre = o.get('centre', list(PLUG_CENTRE))
    if len(centre) != 2 or not all(0 < c < 1 for c in centre):
        raise ValueError('centre must be [u, v] inside the tile')
    matids = o.get('matids')
    if matids is not None and (not matids or any(type(m) is not int for m in matids)):
        raise ValueError('matids must be a non-empty list of integer material IDs')
    if o.get('fixed_udim') is not None:
        tile_for(1, o['fixed_udim'])
    return {'size': float(size), 'centre': [float(c) for c in centre], 'fixed_udim': o.get('fixed_udim'),
            'matids': None if matids is None else sorted(set(matids)),
            'occupied': {int(k): bool(v) for k, v in (o.get('occupied') or {}).items()}}


def plug_plan(faces, opts):
    """Plan over the faces of ONE mesh: {'faces': [{face, matid, udim, uv}], 'skipped': [...], 'tiles': {udim: count},
    'ambiguous': [...]}. Empty input is an error. `opts['occupied']` {udim: True} marks a tile whose centre already
    holds a real island (reported ambiguous, still planned: a plug is only for placeholder materials)."""
    if not faces:
        raise ValueError('no faces selected: select the faces of the placeholder materials (empty input is an error)')
    planned, skipped, tiles = [], [], {}
    for f in faces:
        mid = f['matid']
        if opts['matids'] is not None and mid not in opts['matids']:
            continue
        try:
            udim = tile_for(mid, opts['fixed_udim'])
        except ValueError as exc:
            skipped.append({'face': f['face'], 'code': 'plug_matid', 'reason': str(exc)})
            continue
        uv = plug_uv(f['verts'], udim, opts['size'], opts['centre'])
        if uv is None:
            skipped.append({'face': f['face'], 'code': 'plug_degenerate',
                            'reason': 'face {} is degenerate (zero area): no island'.format(f['face'])})
            continue
        planned.append({'face': f['face'], 'matid': mid, 'udim': udim, 'uv': uv})
        tiles[udim] = tiles.get(udim, 0) + 1
    if not planned and not skipped:
        raise ValueError('no face matches options.matids: nothing to plug')
    ambiguous = [{'item': 'tile {}'.format(u), 'reason': 'tile centre already holds a real island; the plug sits on '
                  'top of it (plugs are for placeholder materials only)'} for u in sorted(tiles)
                 if opts['occupied'].get(u)]
    return {'faces': planned, 'skipped': skipped, 'tiles': tiles, 'ambiguous': ambiguous}


def plug_check(uv_by_face, udim, size=PLUG_SIZE, centre=PLUG_CENTRE, tol=2e-6):
    """Readback check: span of the island(s) in tile `udim` == size and centre == `centre` (+- tol)."""
    du, dv = tile_offset(udim)
    us = [p[0] - du for uv in uv_by_face for p in uv]
    vs = [p[1] - dv for uv in uv_by_face for p in uv]
    if not us:
        return False
    span = max(max(us) - min(us), max(vs) - min(vs))
    return (abs(span - size) <= tol and abs((max(us) + min(us)) / 2 - centre[0]) <= tol
            and abs((max(vs) + min(vs)) / 2 - centre[1]) <= tol)
