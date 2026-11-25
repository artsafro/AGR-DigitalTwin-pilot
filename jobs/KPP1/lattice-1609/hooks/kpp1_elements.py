"""KPP1 #1609 elements kernel (oks-npm stage `body`, point `after`): posts, frames, portals as separate elements [D336].

Pattern: n/a | new-case: stdlib planning kernel of the KPP1 v004 inset elements on the accepted lattice body (corner
posts, frames, portals, annex, glass, finishes; tests run without Blender). Folded from lattice-1609/posts_plan.py
and quad-1372/corner_plan.py (review r1 P1-1, skeleton [D324]); `corner_plan.TOL` is `CORNER_TOL` here, nothing
else changed. Imported by hooks/kpp1_assemble.py; no command line of its own.
"""
import math


# ===== elements plan (was lattice-1609/posts_plan.py) =====
# KPP1 lattice step 3 kernel (#1609): corner posts as separate inset elements [D336] + finish of body faces.
#
# Pattern: n/a | new-case: KPP1 corner posts cut out of the quad-v003 master as separate voxel elements on top of the
# accepted lattice body (step 2), plus the finish band of every lattice body face; stdlib only (tests run without Blender).
#
# - `outside_components`: faces of the source master whose centre lies outside the envelope rectangle (the lattice ring)
#   grouped by shared vertices; a component whose plan bbox comes within `near_m` of a ring corner is that corner's
#   post. Every other component is reported (it stays for the package step), never dropped silently.
# - `inside_ring` / `ring_contact`: voxel centres inside the ring are body (never post cells); a post face lying on the
#   ring boundary and facing into the ring is hidden contact with the body and is not built.
# - `finish_of_face`: finish band of a lattice body face from its centre z. A horizontal face lying on a band border
#   belongs to the wall it closes: an up-facing sill to the band below, a down-facing head to the band above.
# Fail-closed: empty input, NaN/inf, a degenerate rectangle, a z outside every band or bands with gaps/overlaps raise
# ValueError naming the item.

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


def outside_ring(c, rect, tol=1e-3):
    """True if the plan point c lies more than tol outside the ring (points on the ring planes are not outside)."""
    x0, y0, x1, y1 = check_rect(rect)
    _finite(c[:2], 'point')
    return c[0] < x0 - tol or c[0] > x1 + tol or c[1] < y0 - tol or c[1] > y1 + tol


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


OUT_RAYS = {'W': ((0, -1),), 'E': ((0, 1),), 'S': ((1, -1),), 'N': ((1, 1),)}


def element_plan(lo, hi, area, nonaxis_area, rect, tol=1e-3, flat_m=1e-4, planes=None):
    """Package step (#1609, Artem 2026-11-24): plan of one non-post outside component of quad-v003.

    side = the one ring side the plan bbox reaches beyond (more than tol); rays = the outward axis only: frames are
    open along the facade (no end caps, e.g. x 4.9-5.4 on S), only the outward view is closed.
    method: 'voxel' for an all-axis-aligned solid (rebuilt on its own plane lines
    [D336]); 'keep' for a flat, slanted or open component (its v003 quads stay, as a separate element). planes =
    distinct own plane counts per axis (x, y, z); a voxel solid needs >= 2 on both axes other than the outward one.
    kind: ground-standing (lo z <= 1 cm) slanted = Portal, ground-standing axis = Annex, else Frame.
    Fail-closed: NaN/inf, lo > hi, area <= 0, nonaxis_area outside 0..area, no side or two sides."""
    _finite(list(lo) + list(hi) + [area, nonaxis_area], 'element')
    if len(lo) != 3 or len(hi) != 3 or any(a > b for a, b in zip(lo, hi)):
        raise ValueError(f'element bbox {lo}..{hi} is not a box')
    if not area > 0 or not 0 <= nonaxis_area <= area + TOL:
        raise ValueError(f'element area {area} / non-axis area {nonaxis_area} out of range')
    x0, y0, x1, y1 = check_rect(rect)
    sides = [s for s, out in (('W', lo[0] < x0 - tol), ('E', hi[0] > x1 + tol),
                              ('S', lo[1] < y0 - tol), ('N', hi[1] > y1 + tol)) if out]
    if len(sides) != 1:
        raise ValueError(f'element {lo}..{hi} lies beyond ring sides {sides} (needs exactly one)')
    side = sides[0]
    flat = min(b - a for a, b in zip(lo, hi)) < flat_m
    slanted = nonaxis_area > TOL
    out_axis = OUT_RAYS[side][0][0]
    open_axes = [] if planes is None else [a for a in range(3) if a != out_axis and planes[a] < 2]
    method = 'keep' if flat or slanted or open_axes else 'voxel'
    ground = lo[2] <= 0.01
    kind = ('Portal' if slanted else 'Annex') if ground else 'Frame'
    why = ('flat' if flat else 'slanted faces' if slanted
           else f'open surface: < 2 own planes on axis {"xyz"[open_axes[0]]}' if open_axes else 'axis-aligned solid')
    return {'side': side, 'kind': kind, 'method': method, 'rays': OUT_RAYS[side], 'why': why}


def glass_shift(depths, cap):
    """Shift (m, >= 0) that moves a glass component inward-to-outward so its deepest face lies at most `cap` behind
    the ring plane (in front of the lattice opening back face). depths = per-face distance from the ring plane."""
    _finite(list(depths) + [cap], 'glass depth')
    if not depths:
        raise ValueError('glass component without faces')
    if min(depths) < 0 or cap <= 0:
        raise ValueError(f'glass depth {min(depths)} / cap {cap} out of range')
    return max(0.0, max(depths) - cap)


def glass_target(depths, behind, cap_max, gap):
    """Shift (m, outward, >= 0) and mode for one glass component (#1609 package step). depths = its face depths behind
    the ring plane; behind = depths of the lattice body surface seen at its sample points (rays from outside).
    'reveal'/'surface': the pane moves to at most min(cap_max, nearest body surface with room - gap) behind the ring
    plane (a sample whose body surface leaves no room, e.g. a pane edge in a jamb, is ignored); 'onto_wall': fewer than
    half of the samples have room (the body is a solid wall there), the pane moves `gap` in front of the ring plane."""
    _finite(list(behind) + [cap_max, gap], 'glass target')
    if gap <= 0 or cap_max <= gap:
        raise ValueError(f'gap {gap} / cap {cap_max} out of range')
    room = [d - gap for d in behind if d - gap >= gap]
    if behind and len(room) < 0.5 * len(behind):
        glass_shift(depths, cap_max)            # same input checks
        return max(depths) + gap, 'onto_wall'
    cap = min([cap_max] + room)
    return glass_shift(depths, cap), ('reveal' if cap == cap_max else 'surface')


def frame_reach(own, around, gap_m, niche_m, contact_m=0.002, touch_m=0.001):
    """Depths (m behind the ring plane) a frame's back reaches to, as lines of its outward axis (#1609 package review,
    V003 decor embed [D199]). own = body depths hit by rays under the frame footprint, around = the same in a margin
    around it (None = miss), gap_m = the frame's minimum distance to the body. A frame that touches the body
    (gap_m <= touch_m) keeps the old rule: own depths in (contact_m, niche_m]. A floating frame (it stands over a
    lattice opening) takes those own depths, or if there are none the around depths in (contact_m, niche_m]: it reaches
    the niche beside it. Sorted unique; never deeper than niche_m. Non-finite / negative input = error."""
    vals = [d for d in list(own) + list(around) if d is not None]
    _finite(vals + [gap_m, niche_m, contact_m, touch_m], 'frame reach')
    if niche_m <= contact_m or contact_m < 0 or touch_m < 0 or gap_m < 0:
        raise ValueError(f'gap {gap_m} / niche {niche_m} / contact {contact_m} / touch {touch_m} out of range')
    if any(d < -contact_m for d in vals):
        raise ValueError(f'body depth {min(vals)} in front of the ring plane')
    keep = lambda ds: sorted({d for d in ds if d is not None and contact_m < d <= niche_m})  # noqa: E731
    mine = keep(own)
    return mine if mine or gap_m <= touch_m else keep(around)


def clamp_outside(points, side, rect, gap):
    """Kept v003 elements reach into the ring (a portal's sides run 0.16 m into the old wall), where the lattice body
    now stands: they would pierce it (V004 self-intersections per mesh). Every point less than `gap` outside the
    `side` ring plane moves onto plane + gap (outward), so the element stops just in front of the body and never
    touches it (gap > the 2 mm duplicate tolerance). Returns (points, moved count). Unknown side / gap <= 0 = error."""
    x0, y0, x1, y1 = check_rect(rect)
    _finite([gap], 'gap')
    if gap <= 0:
        raise ValueError(f'gap {gap} must be > 0')
    if side not in ('W', 'E', 'S', 'N'):
        raise ValueError(f'unknown side {side!r}')
    ax = 0 if side in 'WE' else 1
    sg = -1 if side in 'WS' else 1
    plane = {'W': x0, 'E': x1, 'S': y0, 'N': y1}[side]
    limit = plane + sg * gap
    out, moved = [], 0
    for p in points:
        _finite(p, 'point')
        q = list(p)
        if (q[ax] - limit) * sg < 0:
            q[ax] = limit
            moved += 1
        out.append(tuple(q))
    return out, moved


def roof_face(centre, rect, z_min, tol=0.002):
    """A source face belongs to the roof element (#1609 package step: the lattice body is an open facade tube, the
    v003 roof slab, parapet top / inner faces and roof equipment stay as one separate element [D336]) if its centre
    lies inside the ring (more than tol from the ring planes, so no facade face) at or above z_min."""
    _finite(list(centre[:3]) + [z_min], 'roof face')
    return inside_ring(centre, rect, tol) and centre[2] >= z_min


def contiguous_udims(tiles):
    """V008 UDIM sequence (#1609 package): the delivered tiles must run 1001, 1002, ... without gaps. Maps the used
    tiles in ascending order onto 1001.. (rank order, so every old tile keeps its neighbours' order). Returns
    {old: new}. Empty input, a tile outside 1001..1100 or a non-int = error."""
    tiles = sorted(set(tiles))
    if not tiles:
        raise ValueError('no UDIM tiles')
    for t in tiles:
        if isinstance(t, bool) or not isinstance(t, int) or not 1001 <= t <= 1100:
            raise ValueError(f'UDIM tile {t!r} outside 1001..1100')
    return {t: 1001 + i for i, t in enumerate(tiles)}


def majority_finish(hits, fallback, min_share=0.5):
    """Finish of a lattice opening back face from the v003 surfaces seen behind it (#1609 package step): `hits` = one
    entry per sample point, a finish name or None (no v003 surface within reach). The most frequent finish wins if it
    covers at least `min_share` of ALL samples (ties: alphabetical, deterministic); else the band `fallback` stays.
    Returns (finish, share). Empty samples or a share outside (0, 1] = error."""
    if not hits:
        raise ValueError('no sample points')
    _finite([min_share], 'min_share')
    if not 0 < min_share <= 1:
        raise ValueError(f'min_share {min_share} outside (0, 1]')
    if not fallback:
        raise ValueError('no fallback finish')
    count = {}
    for h in hits:
        if h is not None:
            count[h] = count.get(h, 0) + 1
    if not count:
        return fallback, 0.0
    best = min(count, key=lambda k: (-count[k], k))
    share = count[best] / len(hits)
    return (best, share) if share >= min_share else (fallback, share)


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


# ===== post voxels (was quad-1372/corner_plan.py) =====
# new-case: KPP1 quad master corners as separate clean elements (#1609): pure planning kernel, no Blender.
#
# Artem 2026-11-16 rejected the v003 corners: everything was welded into ONE mesh and the rules were forced onto
# it. Decision [D336] and the body rules (docs/research/body-modelling.md BM-04/BM-05/BM-09): posts (стойки) are
# geometry - separate inset elements with clean quads, never welded into the body; the wall under them is not cut;
# panels are texture with a seam. This module plans:
#
# 1. `conform_rect` - the body wall rectangle [0, S] x [z0, z1] at a building corner (s = distance from the corner
#    along the wall) to re-mesh: a union of whole wall faces (the posts' hidden contact strip is "don't care"),
#    no opening, no other element attached inside, and a grid whose every line ends on a kept vertex of the
#    border: no line ends inside a kept border edge (no T-junction), every kept border vertex is a line, every UV
#    seam is a line (a slanted seam rejects the rectangle), no two lines closer than `min_gap` (no sliver
#    rows/columns, BM-09). Largest area wins.
# 2. `post_cells` - the posts as a voxel set on the snapped global x/y/z lines of the R1 post triangles (inside =
#    odd ray parity in two directions, both must agree), and `post_faces` - its boundary quads (conforming, one
#    clean element), minus faces lying on the body wall that face into the body (hidden contact, would overlap).
# 3. `affine_uv` - exact planar UV map of a source face, used to give every new corner the source UV.
#
# Every failure is an error naming the corner/wall/face; nothing falls back to a default.

CORNER_TOL = 2e-5          # = twinqa.look.TJUNCTION_TOL_M [D200]
SNAP_M = 6e-4       # R1 post planes 0.3-0.4 mm apart (e.g. -15.0753 / -15.075, -5.6854 / -5.685) are one plane


def snap_values(values, tol=SNAP_M, prefer=()):
    """Cluster sorted values within `tol` (chain); each cluster maps to a preferred value inside it, else its
    rounded mean. Returns (sorted representatives, {value: representative})."""
    vals = sorted(set(values) | set(prefer))
    if not vals:
        return [], {}
    for v in vals:
        if not math.isfinite(v):
            raise ValueError(f'non-finite coordinate {v!r}')
    clusters, cur = [], [vals[0]]
    for v in vals[1:]:
        if v - cur[-1] <= tol:
            cur.append(v)
        else:
            clusters.append(cur)
            cur = [v]
    clusters.append(cur)
    reps, mapping = [], {}
    for c in clusters:
        pref = [p for p in prefer if c[0] - 1e-12 <= p <= c[-1] + 1e-12]
        if len(pref) > 1:
            raise ValueError(f'preferred values {pref} fall into one {tol} m cluster')
        r = pref[0] if pref else round(sum(c) / len(c), 4)
        reps.append(r)
        for v in c:
            mapping[v] = r
    return reps, mapping


def _area(poly):
    return abs(sum(poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1] for i in range(len(poly)))) / 2




def _union_area(rects):
    """Area of a union of axis rectangles [(s0, s1, z0, z1)] (coordinate compression)."""
    xs = sorted({r[k] for r in rects for k in (0, 1)})
    ys = sorted({r[k] for r in rects for k in (2, 3)})
    area = 0.0
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            if any(r[0] <= cx <= r[1] and r[2] <= cy <= r[3] for r in rects):
                area += (xb - xa) * (yb - ya)
    return area


def _lines_ok(lines, kept_edges, min_gap, tol):
    """Sorted unique lines, or None if two are closer than min_gap or one ends inside a kept border edge."""
    out = []
    for v in sorted(lines):
        if out and v - out[-1] <= tol:
            continue
        out.append(v)
    if any(b - a < min_gap - tol for a, b in zip(out, out[1:])):
        return None
    for v in out:
        if any(lo + tol < v < hi - tol for lo, hi in kept_edges):
            return None
    return out


def _bump(why, key):
    why[key] = why.get(key, 0) + 1


def conform_rect(faces, items, edges, s_lo, s_hi, z_lo, z_hi, gone=frozenset(), dontcare=(), seams=(),
                 min_gap=0.03, tol=CORNER_TOL, weight=None):
    """Plan the largest conforming wall rectangle [0, S] x [z0, z1], S in [s_lo, s_hi], z0/z1 in [z_lo, z_hi].

    faces: {fid: [(s, z), ...]} wall faces in the plane (s >= 0); items: [(s, z, fids)] every mesh vertex lying in
    the wall plane with ALL its faces (any orientation); edges: [((s, z), (s, z), fids)] every mesh edge lying in
    the plane with its faces; gone: faces deleted anyway (the posts); dontcare: [(s0, s1, z0, z1)] rectangles that
    need no wall face (the posts' hidden contact); seams: [((s, z), (s, z))] UV seams between two wall faces.
    weight: {fid: w} - when given, the plan maximises (sum of w inside, area) and a rectangle with no weight inside
    is not a plan (nothing to fix: the irregular faces carry the weight).
    Returns {'S', 'z0', 'z1', 'faces', 'cols', 'rows', 'area', 'score'}; raises ValueError naming why nothing fits."""
    if not faces:
        raise ValueError('no wall faces')
    for name, v in (('s_lo', s_lo), ('s_hi', s_hi), ('z_lo', z_lo), ('z_hi', z_hi), ('min_gap', min_gap)):
        if not math.isfinite(v):
            raise ValueError(f'{name} is not finite: {v!r}')
    if not (0 < s_lo <= s_hi and z_lo < z_hi and min_gap > 0):
        raise ValueError(f'empty search box s {s_lo}..{s_hi} z {z_lo}..{z_hi} (min_gap {min_gap})')
    boxes = {}
    for fid, poly in faces.items():
        if len(poly) < 3 or any(not (math.isfinite(s) and math.isfinite(z)) for s, z in poly):
            raise ValueError(f'bad wall face {fid}: {poly!r}')
        ss, zs = [p[0] for p in poly], [p[1] for p in poly]
        if min(ss) < -tol:
            raise ValueError(f'wall face {fid} beyond the corner: {poly!r}')
        boxes[fid] = (min(ss), max(ss), min(zs), max(zs), _area(poly))
    for s, z, _ in items:
        if not (math.isfinite(s) and math.isfinite(z)):
            raise ValueError(f'non-finite vertex {(s, z)!r}')
    s_cands = sorted({round(b[1], 6) for b in boxes.values() if s_lo - tol <= b[1] <= s_hi + tol})
    z_cands = sorted({round(z, 6) for b in boxes.values() for z in (b[2], b[3]) if z_lo - tol <= z <= z_hi + tol})
    best, why = None, {}
    pairs = sorted(((z0, z1) for i, z0 in enumerate(z_cands) for z1 in z_cands[i + 1:]), key=lambda p: p[0] - p[1])
    for S in reversed(s_cands):
        near = {f: b for f, b in boxes.items() if b[0] < S - tol}
        for z0, z1 in pairs:
            area = S * (z1 - z0)
            if weight is None and best is not None and area <= best['area'] + 1e-9:
                continue
            inside, ok = set(), True
            for f, b in near.items():
                if b[2] < z1 - tol and b[3] > z0 + tol:
                    if b[1] > S + tol or b[2] < z0 - tol or b[3] > z1 + tol:
                        ok = False
                        break
                    inside.add(f)
            if not ok:
                _bump(why, 'crossed')
                continue
            score = (round(sum(weight.get(f, 0.0) for f in inside), 9) if weight is not None else 0.0, round(area, 9))
            if weight is not None and (score[0] <= 0 or (best is not None and score <= best['score'])):
                _bump(why, 'nothing to fix' if score[0] <= 0 else 'smaller')
                continue
            dc = [(max(0.0, r[0]), min(S, r[1]), max(z0, r[2]), min(z1, r[3])) for r in dontcare]
            dc = [r for r in dc if r[1] > r[0] and r[3] > r[2]]
            cover = sum(boxes[f][4] for f in inside) + _union_area(dc) - sum(
                clip_area(faces[f], *r) for f in inside for r in dc)
            if abs(cover - area) > 1e-6 + 1e-5 * area:
                _bump(why, 'coverage')
                continue
            dead = inside | set(gone)
            border = {'b': set(), 't': set(), 'l': set(), 'r': set()}
            attached = False
            for s, z, fids in items:
                if not (set(fids) - dead):
                    continue
                if s < -tol or s > S + tol or z < z0 - tol or z > z1 + tol:
                    continue
                on = [k for k, c in (('l', abs(s) <= tol), ('r', abs(s - S) <= tol),
                                     ('b', abs(z - z0) <= tol), ('t', abs(z - z1) <= tol)) if c]
                if not on:
                    attached = True
                    break
                for k in on:
                    border[k].add(round(z if k in 'lr' else s, 6))
            if attached:
                _bump(why, 'attached')
                continue
            kept_e = {'b': [], 't': [], 'l': [], 'r': []}
            for p, q, fids in edges:
                if not (set(fids) - dead):
                    continue
                for k, ax, val, lo, hi in (('l', 0, 0.0, z0, z1), ('r', 0, S, z0, z1),
                                           ('b', 1, z0, 0.0, S), ('t', 1, z1, 0.0, S)):
                    if abs(p[ax] - val) <= tol and abs(q[ax] - val) <= tol:
                        a, c = sorted((p[1 - ax], q[1 - ax]))
                        if c > lo + tol and a < hi - tol:
                            kept_e[k].append((a, c))
            s_seam, z_seam, slanted = set(), set(), False
            for p, q in seams:
                if not all(-tol <= v[0] <= S + tol and z0 - tol <= v[1] <= z1 + tol for v in (p, q)):
                    continue
                if abs(p[0] - q[0]) <= tol:
                    if tol < p[0] < S - tol:
                        s_seam.add(round(p[0], 6))
                elif abs(p[1] - q[1]) <= tol:
                    if z0 + tol < p[1] < z1 - tol:
                        z_seam.add(round(p[1], 6))
                else:
                    slanted = True
                    break
            if slanted:
                _bump(why, 'slanted seam')
                continue
            cols = _lines_ok({0.0, S} | {v for v in border['b'] | border['t'] | s_seam if tol < v < S - tol},
                             kept_e['b'] + kept_e['t'], min_gap, tol)
            rows = _lines_ok({z0, z1} | {v for v in border['l'] | border['r'] | z_seam if z0 + tol < v < z1 - tol},
                             kept_e['l'] + kept_e['r'], min_gap, tol)
            if cols is None or rows is None:
                _bump(why, 'lines')
                continue
            best = {'S': S, 'z0': z0, 'z1': z1, 'faces': sorted(inside), 'cols': cols, 'rows': rows,
                    'area': area, 'score': score}
    if best is None:
        raise ValueError(f'no conforming rectangle (rejected: {why})')
    return best


def clip_area(poly, s0, s1, z0, z1):
    """Area of a polygon [(s, z)] clipped to the rectangle (Sutherland-Hodgman)."""
    pts = list(poly)
    for axis, val, keep_ge in ((0, s0, True), (0, s1, False), (1, z0, True), (1, z1, False)):
        out = []
        for i in range(len(pts)):
            p, q = pts[i - 1], pts[i]
            pin = p[axis] >= val if keep_ge else p[axis] <= val
            qin = q[axis] >= val if keep_ge else q[axis] <= val
            if qin:
                if not pin:
                    t = (val - p[axis]) / (q[axis] - p[axis])
                    out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
                out.append(q)
            elif pin:
                t = (val - p[axis]) / (q[axis] - p[axis])
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        pts = out
        if not pts:
            return 0.0
    return _area(pts) if len(pts) >= 3 else 0.0




def affine_uv(pts, uvs, tol=1e-5):
    """Exact affine map (s, t) -> (u, v) from a planar face's corners; raises if the face's UVs are not affine
    within `tol` (a seam inside the face). Returns f(s, t) -> (u, v)."""
    if len(pts) < 3 or len(pts) != len(uvs):
        raise ValueError('need >= 3 corners with UVs')
    s0, t0 = pts[0]
    best = None
    for i in range(1, len(pts)):
        for j in range(i + 1, len(pts)):
            d = (pts[i][0] - s0) * (pts[j][1] - t0) - (pts[j][0] - s0) * (pts[i][1] - t0)
            if best is None or abs(d) > abs(best[0]):
                best = (d, i, j)
    d, i, j = best
    if abs(d) < 1e-12:
        raise ValueError('degenerate face')
    (si, ti), (sj, tj) = pts[i], pts[j]
    coef = []
    for c in range(2):
        a0, ai, aj = uvs[0][c], uvs[i][c], uvs[j][c]
        ds = ((ai - a0) * (tj - t0) - (aj - a0) * (ti - t0)) / d
        dt = ((aj - a0) * (si - s0) - (ai - a0) * (sj - s0)) / d
        coef.append((a0, ds, dt))

    def f(s, t):
        return tuple(a0 + ds * (s - s0) + dt * (t - t0) for a0, ds, dt in coef)
    for p, uv in zip(pts, uvs):
        got = f(*p)
        if max(abs(got[0] - uv[0]), abs(got[1] - uv[1])) > tol:
            raise ValueError(f'UVs of the face are not affine at {p} ({got} vs {uv})')
    return f


def _ray_hits(origin, axis, sign, tris):
    """Crossings of the ray origin + sign*t*e_axis (t > 0) with triangles (exact for axis-aligned rays)."""
    a, b = [k for k in range(3) if k != axis]
    n = 0
    for tri in tris:
        (p, q, r) = tri
        d = (q[a] - p[a]) * (r[b] - p[b]) - (r[a] - p[a]) * (q[b] - p[b])
        if abs(d) < 1e-14:
            continue                                   # triangle parallel to the ray
        l1 = ((q[a] - origin[a]) * (r[b] - origin[b]) - (r[a] - origin[a]) * (q[b] - origin[b])) / d
        l2 = ((r[a] - origin[a]) * (p[b] - origin[b]) - (p[a] - origin[a]) * (r[b] - origin[b])) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < 0:
            continue
        hit = l1 * p[axis] + l2 * q[axis] + l3 * r[axis]
        if (hit - origin[axis]) * sign > 0:
            n += 1
    return n


def post_cells(tris, xs, ys, zs, rays=((0, -1), (2, 1)), skip=lambda centre: False):
    """Voxels (i, j, k) of the global lines xs/ys/zs whose centre is inside the post triangles (odd parity on
    every ray in `rays`). The voxel centres are off every line, so no ray grazes an edge of an axis plane.
    A disagreement between the rays is an error naming the voxel. `skip(centre)` voxels (inside the body: the
    hidden inset part of a post, open in the source) are never post cells."""
    cells = set()
    boxes = [tuple((min(p[d] for p in t), max(p[d] for p in t)) for d in range(3)) for t in tris]
    column = {}   # (ray axis, voxel index on the other two axes) -> triangles whose bbox holds that ray line

    def near(c, ax, idx):
        key = (ax,) + tuple(idx[d] for d in range(3) if d != ax)
        if key not in column:
            column[key] = [t for t, bb in zip(tris, boxes)
                           if all(bb[d][0] - 1e-9 <= c[d] <= bb[d][1] + 1e-9 for d in range(3) if d != ax)]
        return column[key]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            for k in range(len(zs) - 1):
                # off-centre by fixed irrational fractions: a centred ray would run along a square face's diagonal
                c = (xs[i] + (xs[i + 1] - xs[i]) * 0.4142, ys[j] + (ys[j + 1] - ys[j]) * 0.5772,
                     zs[k] + (zs[k + 1] - zs[k]) * 0.3679)
                if skip(c):
                    continue
                par = [_ray_hits(c, ax, sg, near(c, ax, (i, j, k))) % 2 for ax, sg in rays]
                if len(set(par)) != 1:
                    raise ValueError(f'ray parity disagrees at voxel {(i, j, k)} centre {c}: {par}')
                if par[0]:
                    cells.add((i, j, k))
    return cells


def post_faces(cells, xs, ys, zs, hidden=lambda centre, normal: False):
    """Boundary quads of the voxel set: [(corners [4 x (x, y, z)] counter-clockwise from outside, normal)].
    `hidden(centre, normal)` drops faces in contact with the body (they would overlap the wall)."""
    lines = (xs, ys, zs)
    out = []
    for cell in sorted(cells):
        for ax in range(3):
            for sg in (-1, 1):
                nb = list(cell)
                nb[ax] += 1 if sg > 0 else 0
                nb[ax] -= 0 if sg > 0 else 1
                if tuple(nb) in cells:
                    continue
                a, b = [k for k in range(3) if k != ax]
                plane = lines[ax][cell[ax] + (1 if sg > 0 else 0)]
                lo_a, hi_a = lines[a][cell[a]], lines[a][cell[a] + 1]
                lo_b, hi_b = lines[b][cell[b]], lines[b][cell[b] + 1]
                quad2 = [(lo_a, lo_b), (hi_a, lo_b), (hi_a, hi_b), (lo_a, hi_b)]
                corners = []
                for pa, pb in quad2:
                    p = [0.0, 0.0, 0.0]
                    p[ax], p[a], p[b] = plane, pa, pb
                    corners.append(tuple(p))
                # (a, b, ax) is a right-handed cycle for ax = 0, 2 and left-handed for ax = 1
                if (sg > 0) != (ax == 1):
                    pass
                else:
                    corners.reverse()
                normal = [0, 0, 0]
                normal[ax] = sg
                centre = tuple(sum(c[k] for c in corners) / 4 for k in range(3))
                if hidden(centre, tuple(normal)):
                    continue
                out.append((corners, tuple(normal)))
    return out


