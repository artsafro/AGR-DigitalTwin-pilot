"""new-case: AGR Tools 0.8 (#908) udim logic, stdlib only (branch C, improve/issue-908-names).

Pure logic for `udim_ids_to_udims` (udim.ids_to_udims); no pymxs. Material ID n (1..100) is laid out in UDIM tile
1000+n (u0 = (n-1) % 10, v0 = (n-1) // 10, the standard 1001 + u + 10*v numbering) on an export copy.

Lab source (docs/experiments/udim.ids_to_udims.md, L02): GeoAGR IDs->UDIMs `GeoAGR.ms:35920-36001`, scale spinner
`GeoAGR.ms:14633`; measured in Max 2024, no GeoAGR code copied (#853). Team script UDIM-MultiSub_Universal
(max22-26).ms (sha256 91e96741…3508, the reverse UDIM -> ID direction) was read for the idea of judging a face by
its UV corners against the tile grid; nothing is copied.

Fixed source defects (regression tests in tests/max_tools/test_agr_tools_udim.py):
D1 only the first selected object was processed (`GeoAGR.ms:35929`) -> the glue loops over every object;
D2 IDs > 100 were skipped silently and overlapped ID 1 (`GeoAGR.ms:35949`) -> IDs outside 1..100 are refused,
   listed and flagged; their faces keep their UVs and the report says which tile they sit in;
D3 a zero-extent ID group gave NaN UVs (`GeoAGR.ms:35964`) -> skipped and reported, never divided by zero;
D4 every ID normalised on its own changes texel density between IDs -> mode `texel` uses one UV/3D ratio for all
   IDs of the run (the largest that still fits every group in `scale` of its tile); `fit` keeps the source idea;
D5 Unwrap_UVW was added to the working object (`GeoAGR.ms:35933`, D030) -> copies only (glue);
D6 UV vertices shared between faces of different IDs were dragged along -> split per ID before moving;
D7 no report -> per-ID rows (faces, tile, scale, bbox, UV/3D ratio) and a readback: every face of a placed ID
   lies inside its tile.

#979 rework (team script UDIM Tool v9.2, `UDIM_Tool_new.mzp` sha256
ded25b7f71c9f717971d7ac70756a38f7baf198f846063045a7996ddae96e1cd, T02/udim_tool_v92 card; ideas only):
D8 mode `keep` = the v9.2 «ID -> UDIM All, keep the layout»: every face moves by a whole-tile offset into tile
   1000+ID, nothing is scaled; seams are cut per (UV vertex, offset), so a vertex shared by faces that move
   differently is split (v9.2 keyed it by target tile only: one offset for a face straddling a tile line, V7);
D9 the v9.2 clamp of the source tile to 1001..1100 moved a layout with negative UVs one tile off -> `floor`;
D10 the tile chosen from the first face of a vertex depended on face order -> every face uses its own centroid;
D11 a face that crosses a tile line cannot keep its layout inside one tile -> its ID is refused (`straddles`);
D12 v9.2 edited the base channel under Unwrap_UVW / UVW_Xform (hidden or shifted result) -> the glue reads the
    evaluated stack and collapses the stack on the copy only;
D13 ID > 100 left shared vertices moved (v9.2 V8) -> faces of a refused ID keep their own UV vertices.
"""
import importlib.util
import math
from pathlib import Path


def _sibling(name, alias):
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_udimtile = _sibling('udimtile_core.py', 'agr_tools_udimtile_core_ids')

ID_MIN, ID_MAX = 1, 100
MODES = ('fit', 'texel', 'keep')
DEFAULT_SCALE = 0.95
EPS = 1e-9
INSIDE_TOL = 1e-6


def tile_of_id(mid):
    if type(mid) is not int or not ID_MIN <= mid <= ID_MAX:
        raise ValueError('material ID outside 1..100: ' + repr(mid))
    return 1000 + mid


def tile_origin(tile):
    if type(tile) is not int or not 1001 <= tile <= 1100:
        raise ValueError('UDIM tile outside 1001..1100: ' + repr(tile))
    return _udimtile.tile_origin(tile)


def tile_of_uv(u, v):
    """UDIM tile of a point (1001 + floor(u) + 10*floor(v)), or None outside the 10-column grid."""
    try:
        return _udimtile.udim_tile(u, v)
    except _udimtile.UdimDomainError:
        return None


def face_tile(uvs, idx, tol=INSIDE_TOL):
    """The one tile that contains every corner of the face (tolerance inward), else None."""
    pts = [uvs[i] for i in idx]
    cu = sum(p[0] for p in pts) / len(pts)
    cv = sum(p[1] for p in pts) / len(pts)
    tile = tile_of_uv(cu, cv)
    if tile is None or tile > 1100:
        return None
    u0, v0 = tile_origin(tile)
    for u, v in pts:
        if not (u0 - tol <= u <= u0 + 1 + tol and v0 - tol <= v <= v0 + 1 + tol):
            return None
    return tile


def face_cell(uvs, idx, tol=INSIDE_TOL):
    """(floor u, floor v) of the face's UV centroid when every corner lies in that unit cell (tolerance), else
    None. No clamp and no grid limit: a face at u -0.7 is in cell -1 (D9)."""
    pts = [uvs[i] for i in idx]
    cu = sum(float(p[0]) for p in pts) / len(pts)
    cv = sum(float(p[1]) for p in pts) / len(pts)
    fu, fv = math.floor(cu), math.floor(cv)
    for u, v in pts:
        if not (fu - tol <= u <= fu + 1 + tol and fv - tol <= v <= fv + 1 + tol):
            return None
    return fu, fv


def ids_from_tiles(uvs, face_uvs):
    """UDIM -> ID of every face (tile - 1000 of the face's tile), None where the face is in no tile 1001..1100.

    The reverse direction (udim.udims_to_ids rule: centroid tile, `floor`) for the round-trip check."""
    out = []
    for idx in face_uvs:
        t = face_tile(uvs, idx)
        out.append(None if t is None else t - 1000)
    return out


def _area3(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return 0.5 * math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2)


def _area2(a, b, c):
    return 0.5 * abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))


def _fan(poly):
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def _check_mesh(mesh):
    n = len(mesh['faces'])
    if not n or len(mesh['face_uvs']) != n or len(mesh['ids']) != n:
        raise ValueError('mesh faces, UV faces and IDs differ in count')
    for f, fu in zip(mesh['faces'], mesh['face_uvs']):
        if len(f) != len(fu) or len(f) < 3:
            raise ValueError('face and UV face corner counts differ')
    for p in mesh['uvs']:
        if not all(math.isfinite(float(c)) for c in p[:2]):
            raise ValueError('non-finite UV in the source')


def measure(mesh):
    """Per ID: faces (0-based), UV bbox, UV area, 3D area (world units of the read vertices)."""
    _check_mesh(mesh)
    groups = {}
    for f, mid in enumerate(mesh['ids']):
        g = groups.setdefault(int(mid), {'faces': [], 'uv_area': 0.0, 'area3': 0.0,
                                         'bbox': [math.inf, math.inf, -math.inf, -math.inf]})
        g['faces'].append(f)
        poly3 = [mesh['vertices'][i] for i in mesh['faces'][f]]
        poly2 = [mesh['uvs'][i] for i in mesh['face_uvs'][f]]
        g['area3'] += sum(_area3(*t) for t in _fan(poly3))
        g['uv_area'] += sum(_area2(*t) for t in _fan(poly2))
        b = g['bbox']
        for u, v in poly2:
            b[0], b[1], b[2], b[3] = min(b[0], u), min(b[1], v), max(b[2], u), max(b[3], v)
    return groups


def plan_scales(meshes, mode='fit', scale=DEFAULT_SCALE):
    """{(mesh index, ID): {'status', 'scale'|None, 'reason'?}} for all meshes of one run.

    fit: each ID group fitted to `scale` of its tile, aspect kept (the source behaviour, per ID).
    texel: one UV/3D area ratio C for every placed ID of the run: s_id = sqrt(C / r_id) with r_id = UV area /
    3D area; C is the largest value with every group's longer side <= `scale`."""
    if mode not in MODES:
        raise ValueError('mode must be fit or texel: ' + repr(mode))
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 0.0 < float(scale) <= 1.0:
        raise ValueError('scale must be in (0, 1]: ' + repr(scale))
    scale = float(scale)
    out, candidates = {}, []
    for mi, mesh in enumerate(meshes):
        for mid, g in measure(mesh).items():
            key = (mi, mid)
            if not ID_MIN <= mid <= ID_MAX:
                out[key] = {'status': 'rejected', 'scale': None,
                            'reason': 'material ID {} outside 1..100 has no UDIM tile; UVs kept'.format(mid)}
                continue
            if mode == 'keep':
                bad = [f + 1 for f in g['faces'] if face_cell(mesh['uvs'], mesh['face_uvs'][f]) is None]
                if bad:
                    out[key] = {'status': 'straddles', 'scale': None, 'faces': bad[:1000],
                                'reason': 'ID {}: {} face(s) cross a tile line, the layout cannot be kept inside '
                                          'one tile; UVs kept'.format(mid, len(bad))}
                else:
                    out[key] = {'status': 'placed', 'scale': 1.0, 'keep': True}
                continue
            w, h = g['bbox'][2] - g['bbox'][0], g['bbox'][3] - g['bbox'][1]
            ext = max(w, h)
            if not ext > EPS:
                out[key] = {'status': 'zero_extent', 'scale': None,
                            'reason': 'UV group of ID {} has zero extent; not scaled (no NaN), UVs kept'.format(mid)}
                continue
            if mode == 'texel' and (g['uv_area'] <= EPS * EPS or g['area3'] <= EPS * EPS):
                out[key] = {'status': 'zero_extent', 'scale': None,
                            'reason': 'ID {} has zero UV or 3D area; texel density undefined, UVs kept'.format(mid)}
                continue
            out[key] = {'status': 'placed', 'scale': scale / ext}
            candidates.append((key, ext, g['uv_area'] / g['area3'] if g['area3'] > 0 else None))
    if mode == 'texel' and candidates:
        c = min((scale / ext) ** 2 * r for _, ext, r in candidates)
        for key, ext, r in candidates:
            out[key]['scale'] = math.sqrt(c / r)
    return out


def layout(mesh, scales, mesh_index=0):
    """New (uvs, face_uvs) with every placed ID moved into its tile and every other face unchanged.

    UV vertices are split per ID (D6): a UV vertex used by faces of two IDs becomes two vertices. In `keep`
    mode (scales with scale 1.0 and no bbox fit) every face moves by its own whole-tile offset and the split key
    includes the offset (D8/D10)."""
    groups = measure(mesh)
    remap, uvs = {}, []
    face_uvs = []
    xform, keep = {}, {}
    for mid, g in groups.items():
        s = scales[(mesh_index, mid)]
        if s['status'] != 'placed':
            continue
        u0, v0 = tile_origin(tile_of_id(mid))
        if s.get('keep'):
            keep[mid] = (u0, v0)
            continue
        b = g['bbox']
        cu, cv = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
        xform[mid] = (s['scale'], cu, cv, u0 + 0.5, v0 + 0.5)
    for f, idx in enumerate(mesh['face_uvs']):
        mid = int(mesh['ids'][f])
        shift = None
        if mid in keep:
            fu, fv = face_cell(mesh['uvs'], idx)
            shift = (keep[mid][0] - fu, keep[mid][1] - fv)
        row = []
        for i in idx:
            if shift is not None:
                key = (mid, i) + shift
            else:
                key = (mid, i) if mid in xform else (None, i)
            if key not in remap:
                u, v = float(mesh['uvs'][i][0]), float(mesh['uvs'][i][1])
                if shift is not None:
                    u, v = u + shift[0], v + shift[1]
                elif mid in xform:
                    s, cu, cv, tu, tv = xform[mid]
                    u, v = (u - cu) * s + tu, (v - cv) * s + tv
                if not (math.isfinite(u) and math.isfinite(v)):
                    raise ValueError('non-finite UV produced for ID {}'.format(mid))
                remap[key] = len(uvs)
                uvs.append((u, v))
            row.append(remap[key])
        face_uvs.append(row)
    return uvs, face_uvs


def id_rows(mesh, scales, mesh_index=0, after=None):
    """Per-ID report rows; with `after` = (uvs, face_uvs) the readback tile of every face is checked."""
    rows = []
    groups = measure(mesh)
    post = measure(dict(mesh, uvs=after[0], face_uvs=after[1])) if after else None
    for mid in sorted(groups):
        g, s = groups[mid], scales[(mesh_index, mid)]
        row = {'id': mid, 'faces': len(g['faces']), 'status': s['status'],
               'tile': 1000 + mid if ID_MIN <= mid <= ID_MAX else None,
               'bbox_before': [round(x, 6) for x in g['bbox']],
               'uv_per_3d_before': round(g['uv_area'] / g['area3'], 9) if g['area3'] > 0 else None}
        if s['status'] == 'placed':
            row['scale'] = round(s['scale'], 9)
        else:
            row['reason'] = s['reason']
            tiles = sorted({t for t in (face_tile(mesh['uvs'], mesh['face_uvs'][f]) for f in g['faces'])
                            if t is not None})
            row['sits_in'] = tiles
        if post is not None:
            p = post[mid]
            row['bbox_after'] = [round(x, 6) for x in p['bbox']]
            row['uv_per_3d_after'] = round(p['uv_area'] / p['area3'], 9) if p['area3'] > 0 else None
            if s['status'] == 'placed':
                outside = [f + 1 for f in g['faces'] if face_tile(after[0], after[1][f]) != 1000 + mid]
                row['outside_tile'] = outside
        rows.append(row)
    return rows


def readback_outside(mesh_after):
    """Faces (1-based) of IDs 1..100 that are not inside tile 1000+ID — the per-face tile check of a readback."""
    bad = []
    for f, mid in enumerate(mesh_after['ids']):
        mid = int(mid)
        if ID_MIN <= mid <= ID_MAX and face_tile(mesh_after['uvs'], mesh_after['face_uvs'][f]) != 1000 + mid:
            bad.append(f + 1)
    return bad


def texel_spread(rows):
    """Max relative spread of UV/3D after placement over placed IDs (0.0 = equal)."""
    vals = [r['uv_per_3d_after'] for r in rows if r['status'] == 'placed' and r.get('uv_per_3d_after')]
    if len(vals) < 2:
        return 0.0
    return (max(vals) - min(vals)) / max(vals)
