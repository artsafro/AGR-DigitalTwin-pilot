"""new-case: AGR Tools 1.0 (#1024) texel rescale / UV distortion check logic, stdlib only; owned by branch M (improve/issue-1024-vpm-layout).

Pure logic for `udim_rescale` (udim.rescale, copy) and `udim_distortion` (udim.distortion, read); no pymxs.
Owned by branch M (improve/issue-1024-vpm-layout). Lab L09: docs/experiments/udim.rescale.md,
docs/experiments/udim.distortion.md (measured in 3ds Max 2024).

Mesh (indexed, as the Max glue reads channel 1 of the evaluated TriMesh):
  {'verts': [[x, y, z]...] METRES (world, double), 'tris': [[a, b, c]...], 'mat_ids': [...],
   'uvs': [[u, v]...] map vertices, 'uv_tris': [[a, b, c]...] map faces}.
Metres come from units.SystemScale in the glue (never units.decodeValue), so a centimetre scene gives the same
numbers as a metre scene.

udim.rescale (GeoAGR «ReScale Density» `GeoAGR.ms:43253-43455`): density = tile_px * sqrt(A_uv / A_m²) px/m over
the faces in scope; scale = target / density, applied around the COMMON zero of the projection (UV (0, 0) by
default, the K6 origin), before the K6 layout; whole UV elements touching the scope are scaled, nothing is
broken. GeoAGR defects not repeated: density per system unit (centimetre scene x100), scale around the
selection centre (the island leaves the tile, the K6 phase is lost), `breakSelected` (467-572 px seam),
rewriting the material's maps (copies of sub-materials, new paths, `_id1_id1` chains), silent refusals.

udim.distortion (GeoAGR «Texels Distorsions» `GeoAGR.ms:16071-16457`): per triangle the Jacobian UV -> metres in
the face plane, singular values s1 >= s2: texel = sqrt(s1 * s2) * tile_px against the target (+-1 %),
anisotropy s1 / s2 (limit 1.02, about 1 degree of shear), mirroring by the sign of the determinant. GeoAGR
defects not repeated: Area normalised by the object mean (good faces get 0.62), Angle from the first three
vertices only, Edge depends on texel and units (0.00 in cm), the Unwrap_UVW path silently shows "no
distortion", a primitive throws, no threshold and no machine report.
"""
import math

TILE_PX = 3600   # px of one UDIM tile: 3.6 m at 1000 px/m (owner answer 06.11 morning); default target 1000 px/m
STEP_M = 3.6
SCALE_TOL = 0.01      # +-1 % (vpm.build acceptance)
ANISO_TOL = 1.02      # s1 / s2
RESCALE_KEYS = {'target_px_per_m', 'tile_px', 'pivot_uv', 'faces'}
DISTORTION_KEYS = {'target_px_per_m', 'tile_px', 'scale_tol', 'aniso_tol'}


def _pos(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError('{} must be a positive number: {!r}'.format(name, v))
    return float(v)


def check_mesh(mesh):
    for k in ('verts', 'tris', 'mat_ids', 'uvs', 'uv_tris'):
        if k not in mesh:
            raise ValueError('mesh without ' + k)
    if not mesh['tris']:
        raise ValueError('empty mesh: no faces')
    if len(mesh['uv_tris']) != len(mesh['tris']) or len(mesh['mat_ids']) != len(mesh['tris']):
        raise ValueError('mesh lists differ in length (tris / uv_tris / mat_ids)')
    nv, nu = len(mesh['verts']), len(mesh['uvs'])
    for t, ut in zip(mesh['tris'], mesh['uv_tris']):
        if any(not (0 <= i < nv) for i in t) or any(not (0 <= i < nu) for i in ut):
            raise ValueError('face index out of range')
    for p in mesh['verts']:
        if not all(math.isfinite(c) for c in p):
            raise ValueError('non-finite vertex')
    for p in mesh['uvs']:
        if not all(math.isfinite(c) for c in p[:2]):
            raise ValueError('non-finite UV')
    return mesh


def _area3(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return 0.5 * math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2)


def _area2(a, b, c):
    return 0.5 * abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))


def density(mesh, faces, tile_px=TILE_PX):
    """px/m over the faces: tile_px * sqrt(sum A_uv / sum A_m²) (metres, never system units)."""
    a_uv = a_m = 0.0
    for f in faces:
        t, ut = mesh['tris'][f], mesh['uv_tris'][f]
        a_m += _area3(*(mesh['verts'][i] for i in t))
        a_uv += _area2(*(mesh['uvs'][i] for i in ut))
    if a_m <= 0 or a_uv <= 0:
        raise ValueError('zero area: the faces have no 3D or no UV area')
    return tile_px * math.sqrt(a_uv / a_m)


def uv_elements(mesh):
    """Connected UV elements (map faces sharing a map vertex) -> list of sorted face lists."""
    parent = list(range(len(mesh['uvs'])))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for ut in mesh['uv_tris']:
        r = find(ut[0])
        for i in ut[1:]:
            q = find(i)
            if q != r:
                parent[q] = r
    groups = {}
    for f, ut in enumerate(mesh['uv_tris']):
        groups.setdefault(find(ut[0]), []).append(f)
    return [sorted(g) for _, g in sorted(groups.items(), key=lambda kv: min(kv[1]))]


def rescale_options(options):
    opts = dict(options or {})
    unknown = set(opts) - RESCALE_KEYS
    if unknown:
        raise ValueError('unknown udim.rescale options: ' + ', '.join(sorted(unknown)))
    out = {'tile_px': opts.get('tile_px', TILE_PX), 'pivot_uv': list(opts.get('pivot_uv', [0.0, 0.0])),
           'faces': opts.get('faces')}
    if type(out['tile_px']) is not int or out['tile_px'] <= 0:
        raise ValueError('options.tile_px must be a positive integer: {!r}'.format(out['tile_px']))
    out['target_px_per_m'] = _pos(opts.get('target_px_per_m', out['tile_px'] / STEP_M), 'options.target_px_per_m')
    if len(out['pivot_uv']) != 2 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in out['pivot_uv']):
        raise ValueError('options.pivot_uv must be [u, v]')
    out['pivot_uv'] = [float(c) for c in out['pivot_uv']]
    if out['faces'] is not None:
        if not isinstance(out['faces'], list) or not out['faces'] or any(
                isinstance(f, bool) or not isinstance(f, int) or f < 1 for f in out['faces']):
            raise ValueError('options.faces must be a non-empty list of 1-based face numbers')
        out['faces'] = sorted(set(out['faces']))
    return out


def rescale_plan(mesh, options=None):
    """New UVs for one mesh: {'uvs', 'scale', 'before_px_per_m', 'after_px_per_m', 'faces_scope', 'faces_scaled',
    'elements', 'outside_scope', 'notes'}. Empty scope -> ValueError (never a silent pass)."""
    check_mesh(mesh)
    o = rescale_options(options)
    nf = len(mesh['tris'])
    scope = list(range(nf)) if o['faces'] is None else [f - 1 for f in o['faces']]
    if any(f >= nf for f in scope):
        raise ValueError('options.faces names a face beyond {}'.format(nf))
    before = density(mesh, scope, o['tile_px'])
    sc = o['target_px_per_m'] / before
    in_scope = set(scope)
    elements = [e for e in uv_elements(mesh) if in_scope.intersection(e)]
    moved = sorted({i for e in elements for f in e for i in mesh['uv_tris'][f]})
    pu, pv = o['pivot_uv']
    uvs = [list(p[:2]) for p in mesh['uvs']]
    for i in moved:
        u, v = uvs[i]
        uvs[i] = [pu + (u - pu) * sc, pv + (v - pv) * sc]
    scaled = sorted({f for e in elements for f in e})
    after = density(dict(mesh, uvs=uvs), scope, o['tile_px'])
    outside = sorted(set(scaled) - in_scope)
    notes = ['{} faces outside the scope share a UV element with it and were scaled with it (no breakSelected)'
             .format(len(outside))] if outside else []
    return {'uvs': uvs, 'scale': sc, 'before_px_per_m': before, 'after_px_per_m': after, 'faces_scope': len(scope),
            'faces_scaled': len(scaled), 'elements': len(elements), 'outside_scope': len(outside),
            'notes': notes, 'options': o}


# ---- distortion ----------------------------------------------------------------------------------------------
def jacobian(p3, uv):
    """Singular values (s1 >= s2) and det sign of the map metres -> UV of one triangle, in the face plane.

    The face frame: e1 along the first edge, e2 = n x e1 (n from the winding), so a UV laid as seen from the
    front has det > 0. Returns (s1, s2, det) or None for a degenerate 3D triangle."""
    a, b, c = p3
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    n = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]]
    ln = math.sqrt(sum(x * x for x in n))
    lab = math.sqrt(sum(x * x for x in ab))
    if ln <= 1e-18 or lab <= 1e-12:
        return None
    e1 = [x / lab for x in ab]
    nn = [x / ln for x in n]
    e2 = [nn[1] * e1[2] - nn[2] * e1[1], nn[2] * e1[0] - nn[0] * e1[2], nn[0] * e1[1] - nn[1] * e1[0]]
    x1, y1 = lab, 0.0
    x2, y2 = sum(ac[i] * e1[i] for i in range(3)), sum(ac[i] * e2[i] for i in range(3))
    du1, dv1 = uv[1][0] - uv[0][0], uv[1][1] - uv[0][1]
    du2, dv2 = uv[2][0] - uv[0][0], uv[2][1] - uv[0][1]
    d = x1 * y2 - x2 * y1
    # J = [[du1, du2], [dv1, dv2]] * inv([[x1, x2], [y1, y2]])
    j11 = (du1 * y2 - du2 * y1) / d
    j12 = (du2 * x1 - du1 * x2) / d
    j21 = (dv1 * y2 - dv2 * y1) / d
    j22 = (dv2 * x1 - dv1 * x2) / d
    det = j11 * j22 - j12 * j21
    fro = j11 * j11 + j12 * j12 + j21 * j21 + j22 * j22
    disc = math.sqrt(max(fro * fro - 4.0 * det * det, 0.0))
    s1 = math.sqrt(max((fro + disc) / 2.0, 0.0))
    s2 = math.sqrt(max((fro - disc) / 2.0, 0.0))
    return s1, s2, det


def distortion_options(options):
    opts = dict(options or {})
    unknown = set(opts) - DISTORTION_KEYS
    if unknown:
        raise ValueError('unknown udim.distortion options: ' + ', '.join(sorted(unknown)))
    out = {'tile_px': opts.get('tile_px', TILE_PX), 'target_px_per_m': opts.get('target_px_per_m'),
           'scale_tol': _pos(opts.get('scale_tol', SCALE_TOL), 'options.scale_tol'),
           'aniso_tol': _pos(opts.get('aniso_tol', ANISO_TOL), 'options.aniso_tol')}
    if type(out['tile_px']) is not int or out['tile_px'] <= 0:
        raise ValueError('options.tile_px must be a positive integer')
    if out['target_px_per_m'] is not None:
        out['target_px_per_m'] = _pos(out['target_px_per_m'], 'options.target_px_per_m')
    if out['aniso_tol'] < 1.0:
        raise ValueError('options.aniso_tol must be >= 1')
    return out


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def distortion_rows(mesh, options=None, groups=None):
    """Per face (or per group of triangles = one polygon) the texel, anisotropy and mirroring.

    groups: [[tri...]...] polygons of the host (default: one per triangle). Target: options.target_px_per_m, else
    the MEDIAN texel of the object (named in the result; the median, not the mean, so good faces are not punished
    by bad ones - GeoAGR defect 1). Returns {'target_px_per_m', 'target_source', 'rows': [{'face' 1-based,
    'px_per_m', 'aniso', 'mirrored', 'codes'}], 'bad': {code: [faces]}}."""
    check_mesh(mesh)
    o = distortion_options(options)
    groups = groups or [[i] for i in range(len(mesh['tris']))]
    per = []
    for g in groups:
        vals = []
        for f in g:
            p3 = [mesh['verts'][i] for i in mesh['tris'][f]]
            uv = [mesh['uvs'][i] for i in mesh['uv_tris'][f]]
            vals.append(jacobian(p3, uv))
        per.append(vals)
    texels = [math.sqrt(s1 * s2) * o['tile_px'] for vals in per for v in vals if v for s1, s2, _ in [v]]
    if not texels:
        raise ValueError('no face with 3D area')
    target, source = (o['target_px_per_m'], 'option') if o['target_px_per_m'] else (_median(texels), 'median')
    rows, bad = [], {}
    for k, vals in enumerate(per, 1):
        codes, worst_tx, worst_an, mirrored = [], None, 1.0, False
        for v in vals:
            if v is None:
                continue
            s1, s2, det = v
            if s2 <= 1e-15:
                codes.append('degenerate_uv')
                continue
            tx = math.sqrt(s1 * s2) * o['tile_px']
            if worst_tx is None or abs(tx / target - 1) > abs(worst_tx / target - 1):
                worst_tx = tx
            worst_an = max(worst_an, s1 / s2)
            mirrored = mirrored or det < 0
        if worst_tx is not None and abs(worst_tx / target - 1) > o['scale_tol']:
            codes.append('texel_scale')
        if worst_an > o['aniso_tol']:
            codes.append('anisotropy')
        if mirrored:
            codes.append('mirrored')
        codes = sorted(set(codes))
        for c in codes:
            bad.setdefault(c, []).append(k)
        rows.append({'face': k, 'px_per_m': round(worst_tx, 4) if worst_tx is not None else None,
                     'aniso': round(worst_an, 6), 'mirrored': mirrored, 'codes': codes})
    return {'target_px_per_m': round(target, 6), 'target_source': source, 'rows': rows, 'bad': bad,
            'options': o}
