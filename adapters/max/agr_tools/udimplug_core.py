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
1001 too. A vpm.build copy keeps the LIBRARY ids on its faces and puts each id into the dense tile of its own table
(KPP1 e2e 1.0.0: id 12 -> 1004, not 1012), so the tile of a face is read from the UDIM table of the mesh
(`udim_table` {library id: UDIM}: options, else the `agr_udim_table` user prop that vpm.build writes on its copy);
only a mesh without a table keeps `tile(matid) = 1000 + matid` (IDs already dense, GridUVLayout22 rule). An id that is
not in the table is refused (`plug_matid`), never guessed (1.0.1).
Faces: {'face': int, 'matid': int, 'verts': [(x, y, z), ...]} in metres (units.SystemScale applied by the glue).
"""
import importlib.util
import math
from pathlib import Path


def _sibling(name, alias):
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_udimtile = _sibling('udimtile_core.py', 'agr_tools_udimtile_core_plug')

PLUG_SIZE = 0.05
PLUG_CENTRE = (0.5, 0.5)
TILES_PER_ROW = 10
MAX_TILE_ID = 100


def tile_for(matid, fixed=None, table=None):
    """UDIM number of a face: `fixed` (a tile number 1001..1100) for every face, else the UDIM of the mesh table
    {library id: UDIM} (vpm.build copy), else 1000 + matID."""
    if fixed is not None:
        if type(fixed) is not int or not 1001 <= fixed <= 1000 + MAX_TILE_ID:
            raise ValueError('fixed UDIM must be 1001..1100: ' + repr(fixed))
        return fixed
    if table is not None:
        if matid not in table:
            raise ValueError('material ID {} is not in the UDIM table of the mesh {} (vpm.build copy): no tile'.format(
                matid, sorted(table)))
        return table[matid]
    if type(matid) is not int or not 1 <= matid <= MAX_TILE_ID:
        raise ValueError('material ID {} cannot be a UDIM tile (1..{}; IDs >= 1001 are work IDs, K3)'.format(
            matid, MAX_TILE_ID))
    return 1000 + matid


def tile_offset(udim):
    """(du, dv) of a UDIM number: 1001 -> (0, 0), 1011 -> (0, 1), 1012 -> (1, 1)."""
    if type(udim) is not int or not 1001 <= udim <= 1100:
        raise ValueError('UDIM must be 1001..1100: ' + repr(udim))
    return _udimtile.tile_origin(udim)


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


def udim_table(value):
    """{library id: UDIM} of a mesh from options / the `agr_udim_table` user prop (JSON object, string keys allowed);
    UDIM 1001..1100. Ids may share a tile: the glass copy of vpm.build has every glass id in 1001 (D221); two PLUGGED
    ids in one tile are refused by plug_plan. None stays None."""
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise ValueError('udim_table must be a non-empty object {library id: UDIM}')
    out = {}
    for k, v in value.items():
        try:
            lid = int(k)
        except (TypeError, ValueError):
            raise ValueError('udim_table key must be a library id: {!r}'.format(k))
        if lid <= 0 or str(lid) != str(k).strip() or type(v) is not int or not 1001 <= v <= 1000 + MAX_TILE_ID:
            raise ValueError('udim_table row {!r}: {!r} must be library id -> UDIM 1001..1100'.format(k, v))
        out[lid] = v
    return out


def plug_options(options):
    o = dict(options or {})
    known = {'size', 'fixed_udim', 'matids', 'occupied', 'centre', 'udim_table'}
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
            'udim_table': udim_table(o.get('udim_table')),
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
            udim = tile_for(mid, opts['fixed_udim'], opts.get('udim_table'))
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
    if opts['fixed_udim'] is None and opts.get('udim_table') is not None:
        ids_of = {}
        for f in planned:
            ids_of.setdefault(f['udim'], set()).add(f['matid'])
        shared = {u: sorted(ids) for u, ids in sorted(ids_of.items()) if len(ids) > 1}
        if shared:
            raise ValueError('udim_table gives one UDIM to two plugged ids {} (a glass copy keeps all glass ids in 1001, '
                             'D221: glass gets no plugs, give options.matids)'.format(shared))
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
