"""new-case: unfold measured tower B rings, cut source openings and add reveals."""
import json
import math
from copy import deepcopy
import hashlib
from itertools import product
from collections import Counter, defaultdict
from pathlib import Path
import sys

import numpy as np
from shapely import Polygon, get_parts


def resample_arc(points, step):
    """Develop whole repeats on circular chords, then close at the fixed end tangent."""
    start, end = points[[0,-1]]
    mid = (start+end)/2
    tangent = (end-start)/np.linalg.norm(end-start)
    normal = np.array([-tangent[1], tangent[0]])
    q = points-mid
    x = q@normal
    y = (np.sum(q*q, axis=1)-np.sum((end-mid)**2))/2
    center = mid+(x@y)/(x@x)*normal
    radius = float(np.linalg.norm(start-center))
    assert np.max(np.abs(np.linalg.norm(points-center, axis=1)-radius)) < .002
    angle = np.unwrap(np.arctan2(*(points-center).T[::-1]))
    sweep = float(angle[-1]-angle[0])
    limit = 2*math.acos(max(-1., 1-.0199/radius))
    # Use n chords of length step/n. Their angular span is slightly longer
    # than step/R; dividing the smooth arc by step would not register on FBX.
    n = max(1, math.ceil(step/(2*radius*math.sin(limit/2))))
    delta = 2*math.asin(step/(2*radius*n))
    steps = int(abs(sweep)//(n*delta))
    breaks = list(np.arange(steps*n+1)*delta)
    stations = list(range(0, steps*n+1, n))
    remainder = abs(sweep)-breaks[-1]
    if remainder > 1e-10:
        parts = math.ceil(remainder/limit)
        breaks.extend(np.linspace(breaks[-1], abs(sweep), parts+1)[1:])
    phi = angle[0]+math.copysign(1, sweep)*np.asarray(breaks)
    xy = center+radius*np.c_[np.cos(phi), np.sin(phi)]
    xy[[0,-1]] = points[[0,-1]]
    return dict(center=center.tolist(), radius=radius, stations=stations), xy


def facade_uv(stations, zones, arcs, step):
    """Pin arc starts to integer U. Only intervening same-ID straight runs ease phase."""
    limits = [0]+[i for i in range(1,len(zones)) if zones[i]!=zones[i-1]]+[len(zones)]
    result = np.zeros((len(zones),2))
    for lo,hi in zip(limits,limits[1:]):
        knots = {}
        for start,end in arcs:
            if not lo <= start < hi: continue
            assert end <= hi
            if not knots:
                knots[lo] = (stations[lo]-stations[start])/step
            prev = max(knots)
            start_u = round(knots[prev]+(stations[start]-stations[prev])/step)
            if prev==start and start!=lo:
                raise ValueError('Adjacent arcs need a finish boundary or phase transition')
            knots[start] = start_u
            knots[end] = start_u+(stations[end]-stations[start])/step
        if not knots: knots[lo] = 0.
        prev = max(knots)
        knots[hi] = knots[prev]+(stations[hi]-stations[prev])/step
        ix = sorted(knots)
        uv = np.interp(stations[lo:hi+1], stations[ix], [knots[i] for i in ix])
        result[lo:hi] = np.c_[uv[:-1],uv[1:]]
    return result


def align_curtain_depths(cells, curtains):
    """Use the shallowest measured depth in each uninterrupted curtain slot."""
    count = len(cells[0])
    unseen = set(curtains)
    while unseen:
        stack = [unseen.pop()]
        region = []
        while stack:
            j, i = stack.pop()
            region.append((j, i))
            neighbors = {(j-1, i), (j+1, i), (j, (i-1)%count), (j, (i+1)%count)} & unseen
            unseen.difference_update(neighbors)
            stack.extend(neighbors)
        depth = min(cells[j][i] for j, i in region)
        for j, i in region:
            cells[j][i] = depth


WELD = .0025  # m; closer stations would collapse in the 2 mm vertex weld


def uniform_depths(design):
    """One reveal depth per floor type and opening class (window / curtain): the source median.

    Source depths differ by up to ~2 cm between openings of one class. Where they met at one node v005
    tapered the reveal rear to the shallower one: the wedge faces Artem rejected on 2026-11-18."""
    groups = defaultdict(list)
    for f in design['floors']:
        for o in f['openings']:
            groups[f['type'], bool(o.get('curtain'))].append(o['depth'])
    depth = {k: round(float(np.median(v)), 3) for k,v in groups.items()}
    for f in design['floors']:
        for o in f['openings']:
            o['depth'] = depth[f['type'], bool(o.get('curtain'))]
    return {f"{k[0]}:{'curtain' if k[1] else 'window'}": dict(
        depth_m=d, source_min_m=min(groups[k]), source_max_m=max(groups[k]), openings=len(groups[k]))
        for k,d in sorted(depth.items())}


def open_regions(cells):
    """Label 8-connected open cells: every face at one node then shares one depth-level set."""
    rows, cols = len(cells), len(cells[0]); label = {}; k = 0
    for start in [(j,i) for j in range(rows) for i in range(cols) if cells[j][i]]:
        if start in label: continue
        label[start] = k; stack = [start]
        while stack:
            j,i = stack.pop()
            for dj,di in product((-1,0,1), repeat=2):
                q = (j+dj, (i+di) % cols)
                if 0 <= q[0] < rows and q not in label and cells[q[0]][q[1]]:
                    label[q] = k; stack.append(q)
        k += 1
    return label


def trim_step_returns(design, layouts, turn=45.):
    """End an opening at a sharp contour corner when its short end part is a step return wall.

    The projected FBX span of two A windows runs 0.35 m along the perpendicular step beside them
    (vertices 63/65). Offsetting that part by the 0.71 m reveal folds the sill back over itself
    (overlapping faces). The window plane is the long side; the step stays solid wall and, being
    coplanar, continues the jamb. The opening is unchanged on its own plane."""
    report = []
    for floor in design['floors']:
        a,b,L,n,_,S = layouts[floor['type']]; total = S[-1]
        t = (b-a)/L[:,None]
        for op in floor['openings']:
            s0, s1 = op['s0'], op['s1']
            for j in range(len(L)):
                for sv in (S[j], S[j]+total):
                    if not s0 < sv < s1: continue
                    cross = t[j-1,0]*t[j,1]-t[j-1,1]*t[j,0]
                    if abs(math.degrees(math.atan2(cross, t[j-1]@t[j]))) < turn: continue
                    before, after = sv-s0, s1-sv
                    short, seg = (before, j-1) if before < after else (after, j)
                    if short > op['depth']+.1: continue
                    # The short part must run along the long side's normal (a return), not a facade face.
                    long_n = n[j] if before < after else n[j-1]
                    if abs(t[seg]@long_n) < math.cos(math.radians(30)): continue
                    report.append(dict(type=floor['type'], s=[s0, s1], vertex=j, trimmed_m=short))
                    if before < after: op['s0'] = s0 = sv
                    else: op['s1'] = s1 = sv
    return report


def ring_xy(layout, s):
    a,b,L,_,_,S = layout
    s %= S[-1]
    j = min(len(L)-1, int(np.searchsorted(S, s, side='right')-1))
    return a[j]+(b[j]-a[j])*((s-S[j])/L[j])


def ring_param(layout, xy):
    a,b,L,_,_,S = layout
    t = (b-a)/L[:,None]; d = np.asarray(xy)-a
    u = np.clip(np.sum(d*t, axis=1), 0, L)
    dist = np.linalg.norm(d-t*u[:,None], axis=1); j = int(np.argmin(dist))
    return float((S[j]+u[j]) % S[-1]), float(dist[j])


def cyclic(a, b, period):
    d = abs(a-b) % period
    return min(d, period-d)


def offset_xy(layout, s, d=0.):
    """Plan point at perimeter s, moved d into the body (segment normal, or the mitre at a vertex)."""
    a,b,L,n,mit,S = layout
    j = min(len(L)-1, max(0, int(np.searchsorted(S, s, side='right')-1)))
    u = (s-S[j])/L[j]
    if u < 1e-6: offset = mit[j]
    elif u > 1.-1e-6: offset = mit[(j+1) % len(L)]
    else: offset = n[j]
    return a[j]*(1-u)+b[j]*u+d*offset


def cap_mouths(design):
    """A-side recesses meeting each belt cap: {z: [(s0, s1, depth)]}. A B recess there is refused."""
    floors = design['floors']; out = {}
    for f, g in zip(floors, floors[1:]):
        if f['type'] == g['type']: continue
        z = f['top']; a, b = (f, g) if f['type'] == 'A' else (g, f)
        if any(z in (o['z0'], o['z1']) for o in b['openings']):
            raise NotImplementedError(f'Belt opening reaching the cap at {z}')
        out[z] = [(o['s0'], o['s1'], o['depth']) for o in a['openings'] if z in (o['z0'], o['z1'])]
    return out


def outer_chain(stations, period, mouths):
    """A side of a belt cap: (s, depth) points. A recess mouth adds its jamb top and back lip."""
    def depth(s0, s1):
        m = (s0+s1)/2
        found = {d for a,b,d in mouths if a < m < b or a < m+period < b}
        if len(found) > 1: raise ValueError(f'Mixed recess depths at a belt cap near s={m}')
        return found.pop() if found else 0.
    cols = [depth(a, b) for a, b in zip(stations, stations[1:]+[stations[0]+period])]
    chain = []
    for i, s in enumerate(stations):
        left, right = cols[i-1], cols[i]
        if left and right and left != right: raise ValueError(f'Mixed recess depths at s={s}')
        if left and right: chain.append((s, left))
        elif right: chain += [(s, 0.), (s, right)]
        elif left: chain += [(s, left), (s, 0.)]
        else: chain.append((s, 0.))
    return chain


def _area(poly):
    xy = np.asarray(poly)
    return .5*float(np.sum(xy[:,0]*np.roll(xy[:,1],-1)-np.roll(xy[:,0],-1)*xy[:,1]))


def _crosses(p, q, r, s):
    def orient(a, b, c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    return (orient(p,q,r)*orient(p,q,s) < -1e-12) and (orient(r,s,p)*orient(r,s,q) < -1e-12)


def _distinct(points, labels=None):
    """Corners of a cell after merging coincident ones (a shared station is one corner)."""
    keep = []
    for k, p in enumerate(points):
        if not keep or np.linalg.norm(p-points[keep[-1]]) > .00201: keep.append(k)
    while len(keep) > 1 and np.linalg.norm(points[keep[0]]-points[keep[-1]]) <= .00201: keep.pop()
    return [points[k] for k in keep], ([labels[k] for k in keep] if labels is not None else None)


def _walk(po, pb, lam1, lam2):
    """Least-cost strip of cells between chains po (A side) and pb (B side) with equal ends.

    A step advances either chain by 0..2 points. A cell keeps at most 4 distinct corners and the
    band's orientation (a folded cell is barred, so is a bow-tie). Cost: the closing rung length,
    lam2 for any step other than (1,1), lam1 for a cell with 3 distinct corners and real area."""
    m, n = len(po)-1, len(pb)-1
    band, _ = _distinct(list(po)+list(pb[::-1]))
    sign = 1. if len(band) < 3 or _area(band) >= 0 else -1.
    D = np.full((m+1, n+1), np.inf); D[0,0] = 0.; how = {}
    pts = np.r_[po, pb]
    for i in range(m+1):
        # A rung through another corner would leave a T-junction (crack) on that corner's edge.
        seg = pb-po[i]; rel = pts[None]-po[i][None,None]
        u = np.clip(np.einsum('jk,jpk->jp', seg, rel)/np.maximum(np.einsum('jk,jk->j', seg, seg), 1e-18)[:,None], 0, 1)
        near = np.linalg.norm(rel-u[...,None]*seg[:,None], axis=2) < WELD
        ends = (np.linalg.norm(pts[None]-po[i], axis=2) < WELD) | (np.linalg.norm(pts[None]-pb[:,None], axis=2) < WELD)
        through = (near & ~ends).any(axis=1)
        for j in range(n+1):
            if not (i or j) or through[j]: continue
            rung = float(np.linalg.norm(po[i]-pb[j]))
            for di, dj in product(range(3), repeat=2):
                a, b = i-di, j-dj
                if not (di or dj) or a < 0 or b < 0 or not np.isfinite(D[a,b]): continue
                cell, _ = _distinct([po[k] for k in range(a, i+1)]+[pb[k] for k in range(j, b-1, -1)])
                if len(cell) > 4: continue
                area = _area(cell) if len(cell) > 2 else 0.
                if area*sign < -1e-6: continue
                if len(cell) == 4 and (_crosses(*cell) or _crosses(*cell[1:], cell[0])): continue
                cost = rung+(lam2 if (di, dj) != (1, 1) else 0.)+(lam1 if len(cell) == 3 and abs(area) > 1e-6 else 0.)
                if D[a,b]+cost < D[i,j]:
                    D[i,j] = D[a,b]+cost; how[i,j] = (a, b)
    if not np.isfinite(D[m,n]): raise ValueError('No quad strip between the belt contours')
    steps = [(m, n)]
    while steps[-1] != (0, 0): steps.append(how[steps[-1]])
    return steps[::-1]


def ring_normal(layout, s):
    """Inward unit direction at s: the segment normal, or the mitre (radial on an arc) at a vertex."""
    a,b,L,n,mit,S = layout
    j = min(len(L)-1, max(0, int(np.searchsorted(S, s, side='right')-1)))
    u = (s-S[j])/L[j]
    if u < 1e-6: return mit[j]/np.linalg.norm(mit[j])
    if u > 1.-1e-6: return mit[(j+1) % len(L)]/np.linalg.norm(mit[(j+1) % len(L)])
    return n[j]


def ring_cast(layout, origin, direction, reach):
    """(perimeter position, distance) of the first ring hit along a ray, or None within reach."""
    a,b,L,_,_,S = layout
    e = b-a; w = origin-a
    den = direction[0]*e[:,1]-direction[1]*e[:,0]
    with np.errstate(divide='ignore', invalid='ignore'):
        dist = (w[:,1]*e[:,0]-w[:,0]*e[:,1])/den
        u = (w[:,1]*direction[0]-w[:,0]*direction[1])/den
    ok = (np.abs(den) > 1e-12) & (u >= -1e-9) & (u <= 1+1e-9) & (dist > WELD) & (dist <= reach)
    if not ok.any(): return None
    j = int(np.flatnonzero(ok)[np.argmin(dist[ok])])
    return float((S[j]+np.clip(u[j], 0, 1)*L[j]) % S[-1]), float(dist[j])


def square_rungs(layouts, grids, arcs=None, keep=.05):
    """Give each station a station straight across the belt cap (radial on the rounded corners).

    v005's caps fanned many outer stations into one inner corner (Artem 2026-11-18, «веер»). Each
    station casts along its inward (A) / outward (B) normal; where the hit is a true crossing of the
    cap (no farther than twice the nearest distance + 0.2 m) and no station of the other ring lies
    within `keep`, the hit becomes a full-height station there. The tall A block only takes stations on
    its rounded corners (`arcs`: perimeter spans); the belt B takes them anywhere. Returns the counts."""
    added = {}
    for src, dst, sign in (('A', 'B', 1.), ('B', 'A', -1.)):
        L, M = layouts[src], layouts[dst]; T = M[-1][-1]; new = []
        for s in grids[src][:-1]:
            xy = offset_xy(L, s); t, near = ring_param(M, xy)
            if near < WELD: continue
            hit = ring_cast(M, xy, sign*ring_normal(L, s), 3.)
            if hit is None or hit[1] > 2*near+.2: continue
            if min(cyclic(hit[0], q, T) for q in grids[dst][:-1]+new) < keep: continue
            if dst == 'A' and not any(lo < hit[0] < hi for lo, hi in (arcs or {}).get('A', ())): continue
            new.append(hit[0])
        grids[dst] = sorted(grids[dst][:-1]+new)+[grids[dst][-1]]
        added[dst] = len(new)
    return added


def cap_cells(layouts, grids, mouths, lam1=5., lam2=.3):
    """Quad belt caps: {z: (cells, lip_edges)}; cells hold ('A', s, depth) / ('B', t) corners.

    Anchors are A front stations that are also B stations (shared walls, crossings). Between two
    anchors a least-cost walk pairs the A side (front stations plus recess mouths) with B stations.
    A triangle left by odd parity adds one station mid-way along its longest ring edge (a full-height
    grid line, so every cap edge stays a facade edge) and the walk is repeated: no fan, no T-junction."""
    A, B = layouts['A'], layouts['B']; T = (A[-1][-1], B[-1][-1])
    for _ in range(400):
        sa, sb = grids['A'][:-1], grids['B'][:-1]
        pb_all = np.array([offset_xy(B, t) for t in sb])
        result, insert = {}, None
        for z, spans in mouths.items():
            chain = outer_chain(sa, T[0], spans)
            po_all = np.array([offset_xy(A, s, d) for s, d in chain])
            anchors = []
            for i, (s, d) in enumerate(chain):
                if d: continue
                j = int(np.argmin(np.linalg.norm(pb_all-po_all[i], axis=1)))
                if np.linalg.norm(pb_all[j]-po_all[i]) < WELD: anchors.append((i, j))
            if not anchors:
                dist = np.linalg.norm(po_all[:,None]-pb_all[None], axis=2)
                dist[[i for i, (s, d) in enumerate(chain) if d or sum(c[0] == s for c in chain) > 1]] = np.inf
                anchors = [tuple(int(x) for x in np.unravel_index(np.argmin(dist), dist.shape))]
            if sum(b[1] <= a[1] for a, b in zip(anchors, anchors[1:]+anchors[:1])) > 1:
                raise ValueError(f'Belt contours meet out of order at {z}')
            no, nb = len(chain), len(sb); cells = []
            for (i0, j0), (i1, j1) in zip(anchors, anchors[1:]+anchors[:1]):
                m = (i1-i0) % no or (no if len(anchors) == 1 else 0)
                n = (j1-j0) % nb or (nb if len(anchors) == 1 else 0)
                oi = [(i0+k) % no for k in range(m+1)]; bj = [(j0+k) % nb for k in range(n+1)]
                po, pb = po_all[oi], pb_all[bj]
                steps = _walk(po, pb, lam1, lam2)
                for (a, b), (i, j) in zip(steps, steps[1:]):
                    corners = [('A', *chain[oi[k]]) for k in range(a, i+1)]+[('B', sb[bj[k]]) for k in range(j, b-1, -1)]
                    poly, labels = _distinct([po[k] for k in range(a, i+1)]+[pb[k] for k in range(j, b-1, -1)], corners)
                    if len(poly) == 3 and abs(_area(poly)) > 1e-6 and insert is None:
                        insert = _split_triangle(poly, labels, T)
                    cells.append(corners)
            lips = [(chain[k], chain[(k+1) % no]) for k in range(no) if chain[k][1] and chain[(k+1) % no][1]]
            result[z] = (cells, lips)
        if insert is None: return result
        side, value = insert
        key = 'AB'[side]
        if min(cyclic(value, q, T[side]) for q in grids[key][:-1]) < WELD:
            raise ValueError(f'Belt cap station would collapse onto an existing one: {key} {value}')
        grids[key] = sorted(grids[key][:-1]+[value])+[grids[key][-1]]
        # A station on a wall both rings share is a station of both, or the walls split apart.
        other = 'BA'[side]; t, gap = ring_param(layouts[other], offset_xy(layouts[key], value))
        if gap < WELD and min(cyclic(t, q, T[1-side]) for q in grids[other][:-1]) >= WELD:
            grids[other] = sorted(grids[other][:-1]+[t])+[grids[other][-1]]
    raise ValueError('Belt caps need too many added stations')


def _split_triangle(poly, labels, T):
    """(ring, station) at the middle of the triangle's longest edge running along a ring."""
    best = None
    for k in range(3):
        p, q = labels[k], labels[(k+1) % 3]
        if p[0] != q[0] or p[1] == q[1] or (p[0] == 'A' and p[2] != q[2]): continue
        side = 'AB'.index(p[0])
        lo, hi = sorted((p[1], q[1]))
        if hi-lo > T[side]/2: lo, hi = hi, lo+T[side]
        length = float(np.linalg.norm(poly[k]-poly[(k+1) % 3]))
        if best is None or length > best[0]: best = (length, side, ((lo+hi)/2) % T[side])
    return None if best is None else best[1:]


def build(design, config=None):
    design = deepcopy(design)
    depths = uniform_depths(design)
    verts, faces, roles, groups, indices = [], [], [], [], {}
    buckets = defaultdict(list)
    seen = set()
    planned_boundary = {}

    def bucket(p):
        return tuple(int(np.floor(x/.00201)) for x in p)

    def face(points, zone, role):
        keys = [tuple(round(float(x), 5) for x in p) for p in points]
        ids=[]
        for key in keys:
            if key in indices:
                ids.append(indices[key]); continue
            cell=bucket(key)
            match=next((i for d in product((-1,0,1),repeat=3)
                        for i in buckets.get(tuple(a+b for a,b in zip(cell,d)),())
                        if sum((x-y)**2 for x,y in zip(key,verts[i])) <= .00201**2),None)
            if match is None:
                match=len(verts); verts.append(key); buckets[cell].append(match)
            indices[key]=match; ids.append(match)
        ident=tuple(sorted(ids))
        if len(set(ids)) != len(ids) or ident in seen:
            if role.startswith('shoulder'): return
            raise ValueError(f'Repeated or collapsed {role}: {keys}')
        seen.add(ident); faces.append(ids); groups.append(zone); roles.append(role)
        return ids

    def boundary(ids, a, b, reason):
        planned_boundary[tuple(sorted((ids[a], ids[b])))] = reason

    def layout(m):
        a = np.array(m['ring']); b = np.roll(a, -1, axis=0)
        length = np.linalg.norm(b-a, axis=1); t = (b-a)/length[:,None]
        n = np.c_[-t[:,1],t[:,0]]; prev = np.roll(n,1,axis=0)
        mit = (n+prev)/(1+np.sum(n*prev,axis=1))[:,None]
        return a,b,length,n,mit,np.r_[0.,np.cumsum(length)]

    modules = design['modules']
    original = {key: layout(m)[-1] for key,m in modules.items()}
    arc_segments = {}; arc_runs = defaultdict(list); arcs = {}
    step = config['texture_step_m'] if config else None
    if step is not None:
        for key, spans in config['arc_spans'].items():
            module = modules[key]
            ring = np.asarray(module['ring']); n = len(ring)
            starts = {start: end for start,end in spans}
            i = next(j for j in range(n) if module['zone'][j-1]!=module['zone'][j]); stop = i+n
            points, zones = [], []
            while i < stop:
                j = i%n

                if j not in starts:
                    points.append(ring[j].tolist()); zones.append(module['zone'][j]); i += 1
                    continue
                end = i + (starts[j]-j)%n
                ids = np.arange(i,end+1)%n
                ids_zone = {module['zone'][k] for k in ids[:-1]}
                assert len(ids_zone)==1
                arc, xy = resample_arc(ring[ids], step)
                offset = len(points)
                arc_id = f'{key}:{j}'
                arc_runs[key].append((offset,offset+len(xy)-1))
                arcs[arc_id] = dict(arc, module=key, offset=offset, count=len(xy)-1)
                for k,pt in enumerate(xy[:-1]):
                    points.append(pt.tolist()); zones.append(module['zone'][j])
                    arc_segments[key,offset+k] = (arc_id,k)
                i = end
            # Rebase at a finish boundary so the wrap cannot split a same-ID chart.
            # Reproject opening endpoints from the old contour to the new one.
            old_ring = ring.copy()
            module.update(ring=points, zone=zones)
            new = layout(module)
            for floor in design['floors']:
                if floor['type'] != key: continue
                for op in floor['openings']:
                    mapped = []
                    for field in ('s0','s1'):
                        s = op[field] % original[key][-1]
                        index = min(n-1,np.searchsorted(original[key],s,side='right')-1)
                        fraction = (s-original[key][index])/(original[key][index+1]-original[key][index])
                        xy = old_ring[index]+fraction*(old_ring[(index+1)%n]-old_ring[index])
                        a,b,L,_,_,S = new
                        t = (b-a)/L[:,None]; u = np.clip(np.sum((xy-a)*t, axis=1),0,L)
                        k = np.argmin(np.linalg.norm(xy-a-u[:,None]*t,axis=1))
                        mapped.append(float(S[k]+u[k]))
                    op['s0'],op['s1'] = mapped[0], mapped[1] + (new[-1][-1] if mapped[1]<mapped[0] else 0)
    # Coalesce endpoints of nearly coincident section traces before computing the
    # Boolean. Welding only after tessellation leaves wedges and T-junctions.
    before_snap = layout(modules['B'])[-1]
    a = np.asarray(modules['A']['ring'])
    b = np.asarray(modules['B']['ring'], dtype=float)
    for i, xy in enumerate(b):
        nearest = a[np.argmin(np.linalg.norm(a-xy, axis=1))]
        if np.linalg.norm(nearest-xy) <= .006:
            b[i] = nearest
    modules['B']['ring'] = b.tolist()
    layouts = {key: layout(m) for key,m in modules.items()}
    uv_edges = {}
    if step is not None:
        uv_edges = {k:facade_uv(l[-1],modules[k]['zone'],arc_runs[k],step) for k,l in layouts.items()}
        for arc in arcs.values():
            ring = modules[arc['module']]['ring']; start=arc['offset']
            arc['points'] = [ring[i%len(ring)] for i in range(start,start+arc['count']+1)]
    updated = layouts['B'][-1]
    for floor in design['floors']:
        if floor['type'] == 'B':
            for op in floor['openings']:
                for field in ('s0', 's1'):
                    turn, s = divmod(op[field], before_snap[-1])
                    op[field] = float(turn*updated[-1] + np.interp(s, before_snap, updated))
    trimmed = trim_step_returns(design, layouts)
    profiles = {key: Polygon(m['ring']) for key,m in design['modules'].items()}
    boundaries = {key: [] for key in layouts}
    for part in get_parts(profiles['A'].boundary.intersection(profiles['B'].boundary)):
        if hasattr(part,'coords'):
            for xy in part.coords:
                for key,(a,b,L,n,mit,S) in layouts.items():
                    t=(b-a)/L[:,None]; d=np.array(xy)-a; u=np.sum(d*t,axis=1); clip=np.clip(u,0,L)
                    j=np.argmin(np.linalg.norm(d-t*clip[:,None],axis=1)); boundaries[key].append(S[j]+clip[j])
    floor_map={key: [f for f in design['floors'] if f['type']==key] for key in layouts}
    grids={}
    for key,(a,b,L,n,mit,S) in layouts.items():
        fixed=list(S); total=S[-1]; moving=[]
        for s in boundaries[key]:
            if min(abs(s-q) for q in fixed)>.006:
                fixed.append(s)
        for floor in floor_map[key]:
            for op in floor['openings']:
                moving += [op['s0']%total,op['s1']%total]
        # Revit float noise is not a finish seam. Keep structural/arc stations fixed.
        clean=[]
        for s in sorted(fixed):
            if not clean or s-clean[-1]>1e-4: clean.append(s)
        for s in sorted(moving):
            if min(abs(s-q) for q in clean)>.018: clean.append(s)
        clean.sort(); grids[key]=clean
        for floor in floor_map[key]:
            for op in floor['openings']:
                for field in ('s0','s1'):
                    s=op[field]; period=int(s//total); s=s%total
                    op[field]=min(clean,key=lambda q:abs(q-s))+period*total

    # Share every station along geometrically coincident contour edges, including
    # opening-grid cuts that only occur on one of the two profiles.
    for src, dst in (('A', 'B'), ('B', 'A')):
        a, b, L, _, _, S = layouts[dst]
        t = (b-a)/L[:,None]
        sa, sb, _, _, _, SS = layouts[src]
        for s in list(grids[src]):
            j = min(len(sa)-1, np.searchsorted(SS,s,side='right')-1)
            xy = sa[j] + (sb[j]-sa[j]) * ((s-SS[j])/(SS[j+1]-SS[j]))
            u = np.clip(np.sum((xy-a)*t, axis=1), 0, L)
            for i in np.flatnonzero(np.linalg.norm(xy-a-u[:,None]*t, axis=1) < WELD):
                q = S[i]+u[i]
                if min(abs(q-existing) for existing in grids[dst]) > .00201:
                    grids[dst].append(q)
        grids[dst].sort()

    def point(key,s,z,d=0.):
        return (*offset_xy(layouts[key],s,d),z)

    def material(key,s):
        return design['modules'][key]['zone'][int(np.searchsorted(layouts[key][-1],s,side='right')-1)]

    arc_spans = {k: [(layouts[k][-1][a], layouts[k][-1][b]) for a, b in v] for k, v in arc_runs.items()}
    squared = square_rungs(layouts, grids, arc_spans) if {'A','B'} <= layouts.keys() else {}
    caps = cap_cells(layouts, grids, cap_mouths(design)) if {'A','B'} <= layouts.keys() else {}

    def cap(points, lower):
        """One belt-cap polygon; drops repeated corners, skips zero-area rungs, faces the exposed side."""
        pts = []
        for p in points:
            p = tuple(float(x) for x in p)
            if not pts or math.dist(p, pts[-1]) > .00201: pts.append(p)
        while len(pts) > 1 and math.dist(pts[0], pts[-1]) <= .00201: pts.pop()
        if len(pts) < 3: return None
        xy = np.asarray(pts)[:,:2]
        area = .5*float(np.sum(xy[:,0]*np.roll(xy[:,1],-1)-np.roll(xy[:,0],-1)*xy[:,1]))
        if abs(area) < 1e-6: return None
        if lower == 'B': pts, area = pts[::-1], -area
        return face(pts, 2, 'shoulder_up' if area > 0 else 'shoulder_down')

    def boundary_at(p, q, reason):
        ids = [indices[tuple(round(float(x),5) for x in v)] for v in (p,q)]
        planned_boundary[tuple(sorted(ids))] = reason

    floors=design['floors']; blocks=[]
    uvs, arc_faces = {}, {}
    for f in floors:
        if not blocks or f['type']!=blocks[-1][-1]['type']: blocks.append([])
        blocks[-1].append(f)
    terminals = {floors[0]['bottom'], floors[-1]['top']}
    for block in blocks:
        key=block[0]['type']; ss=grids[key]; period=ss[-1]; count=len(ss)-1
        ops=[o for f in block for o in f['openings']]
        low=block[0]['bottom']; high=block[-1]['top']
        zz=sorted({low,high}|{z for o in ops for z in [o['z0'],o['z1']] if low<z<high})
        cells=[]
        for row_index, (z0,z1) in enumerate(zip(zz,zz[1:])):
            z=(z0+z1)/2; active=[o for o in ops if o['z0']<z<o['z1']]; row=[]
            for i, (s0,s1) in enumerate(zip(ss,ss[1:])):
                s=(s0+s1)/2
                opening=[o for o in active if o['s0']<s<o['s1'] or o['s0']<s+period<o['s1']]
                row.append(max((o['depth'] for o in opening),default=0.))
                if not opening:
                    ids = face([point(key,s0,z0),point(key,s1,z0),point(key,s1,z1),point(key,s0,z1)],material(key,s),'facade')
                    if z0 in terminals: boundary(ids,0,1,'stage_extent')
                    if z1 in terminals: boundary(ids,2,3,'stage_extent')
                    if step is not None:
                        idx = len(faces)-1
                        j = np.searchsorted(layouts[key][-1],s)-1
                        base = next(f['bottom'] for f in block if f['bottom'] <= z < f['top'])
                        S=layouts[key][-1]
                        u0,u1 = np.interp([s0,s1],S[j:j+2],uv_edges[key][j])
                        if (key,j) in arc_segments:
                            arc_faces[idx] = arc_segments[key,j]
                        # Local repeating UV chart; zone IDs are separate slots.
                        u0,u1 = u0-math.floor(u0+1e-8),u1-math.floor(u0+1e-8)
                        v0,v1 = (z0-base)/step,(z1-base)/step
                        uvs[idx]=[(u0,v0),(u1,v0),(u1,v1),(u0,v1)]
            cells.append(row)
        label = open_regions(cells)
        levels, weight = defaultdict(set), defaultdict(Counter)
        for (j,i),k in label.items():
            levels[k].add(cells[j][i])
            weight[k][material(key,(ss[i]+ss[i+1])/2)] += (ss[i+1]-ss[i])*(zz[j+1]-zz[j])
        # One finish ID per connected opening: no sliver ID strips inside a reveal.
        zone_of = {k: w.most_common(1)[0][0] for k,w in weight.items()}

        def reveal(e0, e1, lo, hi, k, flip, role, ends):
            """Straight quads lo..hi deep, split only at this opening's own depth levels: no wedge, no T."""
            cut = [lo]+[d for d in sorted(levels[k]) if lo<d<hi]+[hi]
            for p,q in zip(cut, cut[1:]):
                pts = [e0(p), e0(q), e1(q), e1(p)]
                ids = face(pts[::-1] if flip else pts, zone_of[k], role)
                ids = ids[::-1] if flip else ids
                if q == hi: boundary(ids,1,2,'reveal_lip')
                if p == lo and lo > 0: boundary(ids,3,0,'reveal_lip')
                for (a,b),z in zip(((0,1),(2,3)), ends):
                    if z in terminals: boundary(ids,a,b,'stage_extent')

        for j,(z0,z1) in enumerate(zip(zz,zz[1:])):
            for i in range(count):
                left, right = cells[j][i-1], cells[j][i]
                if left != right:  # jamb (wall to opening) or step (shallow to deep opening)
                    k = label[j,i] if right > left else label[j,(i-1)%count]
                    reveal(lambda d,s=ss[i],z=z0: point(key,s,z,d), lambda d,s=ss[i],z=z1: point(key,s,z,d),
                           min(left,right), max(left,right), k, right < left, 'jamb', (z0,z1))
        for j in range(1, len(cells)):
            for i,(s0,s1) in enumerate(zip(ss,ss[1:])):
                below, above = cells[j-1][i], cells[j][i]
                if below != above:
                    k = label[j,i] if above > below else label[j-1,i]
                    reveal(lambda d,s=s0,z=zz[j]: point(key,s,z,d), lambda d,s=s1,z=zz[j]: point(key,s,z,d),
                           min(below,above), max(below,above), k, above > below,
                           'sill' if above > below else 'head', (None,None))

    for below,above in zip(blocks,blocks[1:]):
        lower=below[-1]['type']; z=below[-1]['top']
        if lower == above[0]['type']: continue
        cells, lips = caps[z]
        for corners in cells:
            cap([point('A',c[1],z,c[2]) if c[0]=='A' else point('B',c[1],z) for c in corners], lower)
        for (s0,d0),(s1,d1) in lips:
            boundary_at(point('A',s0,z,d0), point('A',s1,z,d1), 'belt_opening_lip')
    used=sorted({i for f in faces for i in f}); reindex={i:j for j,i in enumerate(used)}
    model: dict = dict(vertices=[verts[i] for i in used], faces=[[reindex[i] for i in f] for f in faces], face_zones=groups, roles=roles)
    model['planned_boundary'] = [[reindex[a], reindex[b], reason] for (a,b),reason in sorted(planned_boundary.items())]
    model['reveal_depths'] = depths
    model['cap_cells'] = {str(z): len(c) for z,(c,_) in caps.items()}
    model['cap_square_stations'] = squared
    model['trimmed_step_returns'] = trimmed
    if step is not None:
        for i,f in enumerate(faces):
            if i in uvs: continue
            p = np.asarray([verts[j] for j in f]); d = p-p[0]; u = d[1]/np.linalg.norm(d[1])
            normal = np.cross(d[1],d[-1]); normal /= np.linalg.norm(normal)
            uvs[i] = (np.c_[d@u,d@np.cross(normal,u)]/step).tolist()
        model.update(polygon_uv=[uvs[i] for i in range(len(faces))], arc_faces=arc_faces, arcs=arcs,
                     effective_rings={k:m['ring'] for k,m in modules.items()})
    return model


if __name__ == '__main__':
    from adapters.max.agr_tools.body_core import prepare_plan

    source,out=map(Path,sys.argv[1:]); job=Path(__file__).resolve().parents[1]
    manifest=json.loads((job/'sources.json').read_bytes())
    config=manifest['training']
    gate=manifest['gate1']
    inputs={source:manifest['design_sha256'], Path(manifest['fbx']['path']):manifest['fbx']['sha256']}
    inputs.update({Path(gate['directory'])/name: digest for name,digest in gate.items() if name!='directory'})
    for path, expected in inputs.items():
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
                raise ValueError(f'Frozen input mismatch: {path}')
    design=json.loads(source.read_bytes())
    floors=design['floors']
    levels=[floors[0]['bottom']]+[f['top'] for f in floors]
    plan=prepare_plan([dict(handle=1,name='63B shell',kind='geometry',material='Stage1')],
                      opts={'levels':[dict(name=f'B{i:02d}',z_m=z) for i,z in enumerate(levels)]})
    if plan['ambiguous'] or plan['findings'] or len(plan['levels'])!=len(levels):
        raise ValueError(f'body.prepare refused: {plan}')
    prepared=[p['z_m'] for p in plan['levels']]
    for f,lo,hi in zip(floors,prepared[:-1],prepared[1:],strict=True):
        if (f['bottom'],f['top'])!=(lo,hi): raise ValueError('Non-contiguous frozen floor schedule')
        f.update(bottom=lo,top=hi)
    model=build(design,config)
    model.update(body_name=plan['renames'][0][2],body_role=dict(plan['roles'])[1],
                 body_prepare=plan,input_sha256={str(p):v for p,v in inputs.items()},
                 stage2='not_run')
    with out.open('x',encoding='utf-8') as stream:
        json.dump(model,stream,separators=(',',':'))
    print(len(model['vertices']),len(model['faces']))
