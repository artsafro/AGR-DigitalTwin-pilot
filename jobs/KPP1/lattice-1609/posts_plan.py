"""KPP1 lattice step 3 kernel (#1609): corner posts as separate inset elements [D336] + finish of body faces.

Pattern: n/a | new-case: KPP1 corner posts cut out of the quad-v003 master as separate voxel elements on top of the
accepted lattice body (step 2), plus the finish band of every lattice body face; stdlib only (tests run without Blender).

- `outside_components`: faces of the source master whose centre lies outside the envelope rectangle (the lattice ring)
  grouped by shared vertices; a component whose plan bbox comes within `near_m` of a ring corner is that corner's
  post. Every other component is reported (it stays for the package step), never dropped silently.
- `inside_ring` / `ring_contact`: voxel centres inside the ring are body (never post cells); a post face lying on the
  ring boundary and facing into the ring is hidden contact with the body and is not built.
- `finish_of_face`: finish band of a lattice body face from its centre z. A horizontal face lying on a band border
  belongs to the wall it closes: an up-facing sill to the band below, a down-facing head to the band above.
Fail-closed: empty input, NaN/inf, a degenerate rectangle, a z outside every band or bands with gaps/overlaps raise
ValueError naming the item.
"""
import math

TOL = 1e-6


def _finite(vals, what):
    for v in vals:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f'{what}: non-finite value {v!r}')


def check_rect(rect):
    """rect = (x0, y0, x1, y1) of the envelope ring; x0 < x1 and y0 < y1."""
    if len(rect) != 4:
        raise ValueError(f'ring rectangle needs 4 numbers, got {rect!r}')
    _finite(rect, 'ring rectangle')
    x0, y0, x1, y1 = rect
    if not (x1 - x0 > TOL and y1 - y0 > TOL):
        raise ValueError(f'degenerate ring rectangle {rect!r}')
    return tuple(float(v) for v in rect)


def ring_corners(rect):
    x0, y0, x1, y1 = check_rect(rect)
    return {'SW': (x0, y0), 'SE': (x1, y0), 'NE': (x1, y1), 'NW': (x0, y1)}


def inside_ring(c, rect, tol=1e-3):
    """True if the plan point c lies strictly inside the ring (more than tol from the boundary)."""
    x0, y0, x1, y1 = check_rect(rect)
    _finite(c[:2], 'point')
    return x0 + tol < c[0] < x1 - tol and y0 + tol < c[1] < y1 - tol


def ring_contact(centre, normal, rect, tol=1e-6):
    """A post face on the ring boundary whose normal points into the ring: hidden contact with the body."""
    x0, y0, x1, y1 = check_rect(rect)
    x, y = centre[0], centre[1]
    in_y, in_x = y0 - tol <= y <= y1 + tol, x0 - tol <= x <= x1 + tol
    return ((abs(x - x0) <= tol and tuple(normal) == (1, 0, 0) and in_y)
            or (abs(x - x1) <= tol and tuple(normal) == (-1, 0, 0) and in_y)
            or (abs(y - y0) <= tol and tuple(normal) == (0, 1, 0) and in_x)
            or (abs(y - y1) <= tol and tuple(normal) == (0, -1, 0) and in_x))


def outside_components(verts, faces, rect, near_m=0.4, out_tol=1e-3):
    """verts [(x, y, z)], faces [[vertex index]] -> {'posts': {corner: [face idx]}, 'other': [[face idx]], 'bbox': ...}.

    A face is outside if its centre lies more than out_tol outside the ring rectangle. Components = outside faces
    connected through shared vertices. A component within near_m of exactly one ring corner (plan bbox distance) is
    that corner's post; near two corners is an error naming it."""
    if not verts or not faces:
        raise ValueError('empty mesh')
    x0, y0, x1, y1 = check_rect(rect)
    if not (isinstance(near_m, (int, float)) and math.isfinite(near_m) and near_m > 0):
        raise ValueError(f'near_m must be a positive finite number, got {near_m!r}')
    for i, v in enumerate(verts):
        _finite(v, f'vertex {i}')
    out = []
    for fi, f in enumerate(faces):
        if len(f) < 3:
            raise ValueError(f'face {fi} has < 3 corners')
        cx = sum(verts[k][0] for k in f) / len(f)
        cy = sum(verts[k][1] for k in f) / len(f)
        if cx < x0 - out_tol or cx > x1 + out_tol or cy < y0 - out_tol or cy > y1 + out_tol:
            out.append(fi)
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for fi in out:
        f = faces[fi]
        for k in f[1:]:
            parent[find(k)] = find(f[0])
    comps = {}
    for fi in out:
        comps.setdefault(find(faces[fi][0]), []).append(fi)
    corners = ring_corners(rect)
    posts, other, boxes = {}, [], {}
    for fs in sorted(comps.values(), key=lambda c: c[0]):
        vs = {k for fi in fs for k in faces[fi]}
        lo = [min(verts[k][a] for k in vs) for a in range(3)]
        hi = [max(verts[k][a] for k in vs) for a in range(3)]
        near = [n for n, (cx, cy) in corners.items()
                if math.hypot(min(max(cx, lo[0]), hi[0]) - cx, min(max(cy, lo[1]), hi[1]) - cy) <= near_m]
        if len(near) > 1:
            raise ValueError(f'outside component at {lo}..{hi} is near corners {near}')
        if near:
            posts.setdefault(near[0], []).extend(fs)
            boxes.setdefault(near[0], []).append((lo, hi))
        else:
            other.append(fs)
    return {'posts': posts, 'other': other, 'bbox': boxes, 'outside_faces': len(out)}


def check_bands(bands):
    if not bands:
        raise ValueError('no finish bands')
    for b in bands:
        _finite((b['z0'], b['z1']), f'band {b.get("finish")}')
        if not b['z1'] > b['z0'] or not b.get('finish'):
            raise ValueError(f'bad band {b!r}')
    for a, b in zip(bands, bands[1:]):
        if abs(a['z1'] - b['z0']) > TOL:
            raise ValueError(f'bands {a["finish"]} / {b["finish"]} leave a gap or overlap at {a["z1"]} / {b["z0"]}')
    return bands


def finish_of_face(z_lo, z_hi, nz, bands, eps=1e-4):
    """Finish of a body face spanning z_lo..z_hi with normal z component nz (bands from finish_bands.json)."""
    check_bands(bands)
    _finite((z_lo, z_hi, nz), 'face')
    if z_hi - z_lo > 1e-4:
        z = (z_lo + z_hi) / 2
    elif nz > 0.5:
        z = z_lo - eps          # up-facing (sill, plinth top): the wall below
    elif nz < -0.5:
        z = z_lo + eps          # down-facing (head, soffit): the wall above
    else:
        raise ValueError(f'flat face at z {z_lo} without a vertical normal ({nz})')
    for b in bands:
        if b['z0'] - TOL <= z < b['z1'] - TOL or (b is bands[-1] and abs(z - b['z1']) <= TOL):
            return b['finish']
    raise ValueError(f'z {z} lies in no finish band')
