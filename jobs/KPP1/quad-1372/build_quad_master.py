"""new-case: KPP1 all-quad editable master from the approved triangulated R1 master (#1372, F26).

Run in Blender 5.1 (factory startup) on a NEW packet copy:
    blender -b --factory-startup --python build_quad_master.py -- <packet_root>

Same-surface operations only (no vertex of R1 moves, except T-junction corners welded within 20 um):
1. T-junctions [D200]: a vertex lying on another face's edge (20 um, `twinqa.look.TJUNCTION_TOL_M`) is
   inserted into that edge and the face is re-triangulated, so both sides share the vertex.
2. Coplanar pairing: `bmesh.ops.join_triangles` joins triangle pairs that are coplanar (0.01 deg), share
   UVs across the edge and have the same material.
3. Remaining triangles: every triangle edge gets a midpoint; the marks are closed over quads (0, 2 opposite
   or 4 marked edges) so a split edge is split on both sides (no new T-junction). Triangle -> 3 quads,
   quad -> 2 or 4 quads. New points are edge midpoints/centroids of planar faces, UVs are interpolated
   per corner (seams kept), material index and flat shading are copied to every child face.
Then the finish attribute is recovered from UDIM tiles exactly as `benchmark-1318/prepare_master.py`, the
master is saved as `master-quad-v001.blend` + a quad work FBX, and both are reopened and fingerprinted.
Outputs that exist already fail the run (never overwrite a version).

v002 (user decision 2026-11-14, «Принимаю рекомендации»: R1 overlaps deleted/merged within <= 5 mm, 100 % quads):
    blender -b --factory-startup --python build_quad_master.py -- <packet_root> v002 <union-zones.json>
Step 0 `union_zones` runs before step 1 on `SM_Kpp_1_Main`: the zones of `plan_union_zones.py` (R1 xView face
pairs) are snapped onto one exact axis plane (<= 5 mm), the touching solids are unioned (Blender exact boolean,
self intersection), the coincident opposite double layer is deleted, boolean vertices are welded within 2 mm and
dangling flaps in a zone are deleted; every move, weld and deletion is listed in `quad-build-v002.json`. Fan
centres keep > 2.1 mm from every vertex (xView Overlapping Vertices) where the face allows it. R1 is never written.
"""
import collections
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

SOURCE_SHA = '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676'  # r1-v002 SM_Kpp_1.fbx
TJ_TOL = 2e-5            # = twinqa.look.TJUNCTION_TOL_M [D200]
PLANAR_TOL_M = 1e-5      # 4th corner within 10 um of the partner plane: either diagonal keeps the R1 surface
UV_TOL = 1e-6            # UV continuity across the shared edge (no seam inside a quad)
RENDER = ('SM_Kpp_1_Main', 'SM_Kpp_1_MainGlass')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(o):
    me = o.data
    data = {'vertices': [[round(c, 7) for c in v.co] for v in me.vertices],
            'polygons': [list(p.vertices) for p in me.polygons],
            'uv': [[round(c, 7) for c in d.uv] for d in me.uv_layers[0].data] if me.uv_layers else [],
            'materials': [p.material_index for p in me.polygons]}
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def point_seg(p, a, b):
    ab = b - a
    t = (p - a).dot(ab) / max(ab.length_squared, 1e-30)
    t = min(1.0, max(0.0, t))
    return (a + ab * t - p).length, t


def find_tjunctions(bm):
    kd = KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()
    found = []
    for e in bm.edges:
        a, b = e.verts
        mid = (a.co + b.co) / 2
        r = (a.co - b.co).length / 2 + TJ_TOL
        face_verts = {v.index for f in e.link_faces for v in f.verts}
        for co, idx, _ in kd.find_range(mid, r):
            if idx in face_verts:
                continue
            d, t = point_seg(co, a.co, b.co)
            if d < TJ_TOL and (co - a.co).length >= TJ_TOL and (co - b.co).length >= TJ_TOL:
                found.append((e.index, idx, t))
    return found


def fix_tjunctions(bm):
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
    found = find_tjunctions(bm)
    by_edge = collections.defaultdict(list)
    for ei, vi, t in found:
        by_edge[ei].append((t, vi))
    plan = [(bm.edges[ei].verts[0], bm.edges[ei].verts[1], [(t, bm.verts[vi], vi) for t, vi in sorted(items)], ei)
            for ei, items in by_edge.items()]
    log, touched = [], set()
    for a, b, points, ei in plan:
        cur = a
        for t, target, vi in points:
            e = next(x for x in cur.link_edges if x.other_vert(cur) is b)
            fac = (target.co - cur.co).length / max((b.co - cur.co).length, 1e-30)
            _, nv = bmesh.utils.edge_split(e, cur, fac)
            log.append({'vertex': vi, 'edge': ei, 't': round(t, 6), 'corner_move_m': (nv.co - target.co).length})
            touched.update(nv.link_faces)
            bmesh.ops.weld_verts(bm, targetmap={nv: target})
            cur = target
    faces = [f for f in touched if f.is_valid and len(f.verts) > 3]
    if faces:
        bmesh.ops.triangulate(bm, faces=faces, quad_method='FIXED', ngon_method='EAR_CLIP')
    bm.verts.index_update(); bm.edges.index_update(); bm.faces.index_update()
    left = find_tjunctions(bm)
    if left:
        raise ValueError(f'{len(left)} T-junction(s) remain after the fix')
    return found, log


def _pair_ok(f, g, e, uv_layer):
    """Strictly convex, planar (10 um), same material, UV-continuous quad from triangles f, g over edge e."""
    if f.material_index != g.material_index or f.smooth != g.smooth or not e.is_contiguous:
        return False  # contiguous = consistent winding; a flipped partner would make a bow-tie quad
    a, b = e.verts
    for v in (a, b):
        uf = next(l[uv_layer].uv for l in f.loops if l.vert is v)
        ug = next(l[uv_layer].uv for l in g.loops if l.vert is v)
        if (uf - ug).length > UV_TOL:
            return False
    c = next(v for v in f.verts if v not in (a, b))
    d = next(v for v in g.verts if v not in (a, b))
    n = (b.co - a.co).cross(c.co - a.co)
    if n.length < 1e-12:
        return False
    n.normalize()
    if abs((d.co - a.co).dot(n)) > PLANAR_TOL_M:
        return False
    ring = [a.co, d.co, b.co, c.co]  # strictly convex: every turn has one sign
    signs = [(ring[i] - ring[i - 1]).cross(ring[(i + 1) % 4] - ring[i]).dot(n) for i in range(4)]
    return all(x > 1e-12 for x in signs) or all(x < -1e-12 for x in signs)


def pair_triangles(bm, uv_layer):
    """Near-maximum matching of compatible triangle pairs (min-degree greedy + length-3 augmenting swaps)."""
    bm.faces.ensure_lookup_table()
    tris = [f for f in bm.faces if len(f.verts) == 3]
    adj = collections.defaultdict(dict)
    for f in tris:
        for e in f.edges:
            if len(e.link_faces) != 2:
                continue
            g = e.link_faces[0] if e.link_faces[1] is f else e.link_faces[1]
            if len(g.verts) == 3 and g.index not in adj[f.index] and _pair_ok(f, g, e, uv_layer):
                adj[f.index][g.index] = e
                adj[g.index][f.index] = e
    mate = {}
    for i in sorted(adj, key=lambda i: len(adj[i])):
        if i in mate:
            continue
        free = [j for j in adj[i] if j not in mate]
        if free:
            j = min(free, key=lambda j: len([k for k in adj[j] if k not in mate]))
            mate[i], mate[j] = j, i
    for _ in range(50):
        changed = 0
        for u in list(adj):
            if u in mate:
                continue
            for v in adj[u]:
                w = mate.get(v)
                if w is None:
                    mate[u], mate[v] = v, u
                    changed += 1
                    break
                x = next((x for x in adj[w] if x not in mate and x != u), None)
                if x is not None:
                    mate[u], mate[v], mate[w], mate[x] = v, u, x, w
                    changed += 1
                    break
        if not changed:
            break
    # longer alternating paths (DFS, no blossom shrinking: may stay below the maximum matching)
    sys.setrecursionlimit(100000)

    def augment(u, seen, depth):
        for v in adj[u]:
            if v in seen:
                continue
            seen.add(v)
            w = mate.get(v)
            if w is None or (depth < 400 and w not in seen and (seen.add(w) or augment(w, seen, depth + 1))):
                mate[u], mate[v] = v, u
                return True
        return False

    for _ in range(10):
        if not sum(augment(u, {u}, 0) for u in list(adj) if u not in mate):
            break
    seen_c, odd = set(), 0
    for s0 in adj:
        if s0 in seen_c:
            continue
        stack, size = [s0], 0
        seen_c.add(s0)
        while stack:
            x = stack.pop()
            size += 1
            for y in adj[x]:
                if y not in seen_c:
                    seen_c.add(y)
                    stack.append(y)
        odd += size % 2
    edges = list({adj[i][j].index: adj[i][j] for i, j in mate.items()}.values())
    before = len(tris)
    bmesh.ops.dissolve_edges(bm, edges=edges, use_verts=False, use_face_split=False)
    bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.verts.ensure_lookup_table()
    bad = [f.index for f in bm.faces if len(f.verts) not in (3, 4)]
    if bad:
        raise ValueError(f'pairing produced non tri/quad faces: {bad[:5]}')
    return {'triangles': before, 'pairs': len(edges), 'compatible_triangles': len(adj),
            'unpaired_triangles': before - 2 * len(edges), 'odd_components_lower_bound': odd,
            'isolated_triangles': before - len(adj)}


def _convex(ring, n):
    signs = [(ring[i] - ring[i - 1]).cross(ring[(i + 1) % 4] - ring[i]).dot(n) for i in range(4)]
    return all(x > 1e-12 for x in signs) or all(x < -1e-12 for x in signs)


def _centre(P, Mp, Mu, kd, placed, clear_m, cell):
    """Fan centre of a triangle (3 marks) or quad (4 marks): the centroid, or with `clear_m` the point inside the
    midpoint polygon (so every fan quad stays strictly convex) farthest from every vertex, midpoint and earlier
    centre when the centroid is closer than `clear_m` (v002: xView Overlapping Vertices 2 mm). Returns
    (position, uv, clearance or None, moved)."""
    n = len(P)
    cen = sum(P, Vector()) / n
    cu = sum(Mu, Vector((0.0, 0.0))) / n   # = mean of corner UVs (v001 rule)
    if clear_m is None:
        return cen, cu, None, False
    nrm = (P[1] - P[0]).cross(P[2] - P[0]) if n == 3 else (P[2] - P[0]).cross(P[3] - P[1])

    def clearance(x):
        d = kd.find(x)[2]
        key = tuple(int(math.floor(c / cell)) for c in x)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for y in placed.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        d = min(d, (x - y).length)
        return d

    def ok(x):
        return all(_convex([P[i], Mp[i], x, Mp[(i - 1) % n]], nrm) for i in range(n))

    def grid(N=16):
        if n == 3:
            for i in range(1, N):
                for j in range(1, N - i):
                    w = (i / N, j / N, (N - i - j) / N)
                    yield (Mp[0] * w[0] + Mp[1] * w[1] + Mp[2] * w[2], Mu[0] * w[0] + Mu[1] * w[1] + Mu[2] * w[2])
        else:
            for a in range(1, N):
                for b in range(1, N):
                    s, t = a / N, b / N
                    yield ((Mp[0] * (1 - s) + Mp[1] * s) * (1 - t) + (Mp[3] * (1 - s) + Mp[2] * s) * t,
                           (Mu[0] * (1 - s) + Mu[1] * s) * (1 - t) + (Mu[3] * (1 - s) + Mu[2] * s) * t)
    best = (clearance(cen), cen, cu) if ok(cen) else (-1.0, cen, cu)
    if best[0] < clear_m:
        for x, xu in grid():
            if ok(x):
                d = clearance(x)
                if d > best[0]:
                    best = (d, x, xu)
    if best[0] < 0:
        # the source face itself has a straight corner (pairing allows it): no fan quad can be strictly convex
        # there; keep the clearance rule only, inside the midpoint polygon as before
        best = max([(clearance(cen), cen, cu)] + [(clearance(x), x, xu) for x, xu in grid()], key=lambda c: c[0])
        return best[1], best[2], best[0], 'straight-source'
    return best[1], best[2], best[0], best[1] is not cen


def classify_and_split(bm, uv_layer, clear_m=None):
    """Close edge-midpoint marks so every face becomes quads; return new mesh arrays.
    `clear_m` (v002): fan centres keep this distance from every other vertex where the face allows it."""
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    marked = set()
    for f in bm.faces:
        if len(f.verts) == 3:
            marked.update(e.index for e in f.edges)
        elif len(f.verts) != 4:
            raise ValueError(f'face {f.index}: {len(f.verts)} corners after join')
    bm.edges.ensure_lookup_table()
    queue = collections.deque(f for f in bm.faces if len(f.verts) == 4 and any(e.index in marked for e in f.edges))
    while queue:
        f = queue.popleft()
        m = [l.edge.index in marked for l in f.loops]
        n = sum(m)
        if n in (0, 4) or (n == 2 and m[0] == m[2]):
            continue
        add = [l.edge for i, l in enumerate(f.loops) if not m[i] and (n != 1 or m[(i + 2) % 4])]
        for e in add:
            marked.add(e.index)
            queue.extend(x for x in e.link_faces if len(x.verts) == 4)
    verts = [v.co.copy() for v in bm.verts]
    mid = {}

    def midpoint(e):
        if e.index not in mid:
            a, b = e.verts
            verts.append((a.co + b.co) / 2)
            mid[e.index] = len(verts) - 1
        return mid[e.index]

    for e in bm.edges:            # every midpoint first, so the centre clearance sees all of them
        if e.index in marked:
            midpoint(e)
    kd = KDTree(len(verts))
    for i, x in enumerate(verts):
        kd.insert(x, i)
    kd.balance()
    cell = max(clear_m or 0.0, 1e-3) * 2
    placed, centres = {}, []
    polys, uvs, src_face = [], [], []
    for f in bm.faces:
        loops = list(f.loops)
        n = len(loops)
        c = [l.vert.index for l in loops]
        u = [l[uv_layer].uv.copy() for l in loops]
        m = [l.edge.index in marked for l in loops]
        M = [midpoint(l.edge) if m[i] else None for i, l in enumerate(loops)]
        Mu = [(u[i] + u[(i + 1) % n]) / 2 for i in range(n)]
        out = []
        if n == 4 and not any(m):
            out = [(c, u)]
        elif n == 4 and sum(m) == 2:
            i = 0 if m[0] else 1
            j = i + 2
            # corners c[i]..c[i+3]; marked edges i (c_i->c_i+1) and j (c_j->c_j+1)
            k = lambda x: x % 4
            out = [([c[i], M[i], M[j], c[k(j + 1)]], [u[i], Mu[i], Mu[j], u[k(j + 1)]]),
                   ([M[i], c[k(i + 1)], c[j], M[j]], [Mu[i], u[k(i + 1)], u[j], Mu[j]])]
        else:  # triangle with 3 marks or quad with 4: fan of quads around the centre
            co, Cu, clr, moved = _centre([verts[x] for x in c], [verts[x] for x in M], Mu, kd, placed, clear_m, cell)
            verts.append(co)
            C = len(verts) - 1
            placed.setdefault(tuple(int(math.floor(x / cell)) for x in co), []).append(co)
            if clr is not None:
                centres.append({'face': f.index, 'clearance_m': clr, 'moved': moved})
            for i in range(n):
                p = (i - 1) % n
                out.append(([c[i], M[i], C, M[p]], [u[i], Mu[i], Cu, Mu[p]]))
        for pc, pu in out:
            polys.append(pc); uvs.append(pu); src_face.append(f.index)
    return verts, polys, uvs, src_face, len(marked), centres


def quadify(obj, clear_m=None):
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    before = {'faces': len(bm.faces), 'verts': len(bm.verts)}
    tj, tj_log = fix_tjunctions(bm)
    # union output (v002) has planar quads/n-gons: triangulate them on their plane, then pair like R1 triangles
    poly = [f for f in bm.faces if len(f.verts) > 3]
    if poly:
        bmesh.ops.triangulate(bm, faces=poly, quad_method='BEAUTY', ngon_method='BEAUTY')
        bm.faces.index_update()
    uv_layer = bm.loops.layers.uv.active
    join_info = pair_triangles(bm, uv_layer)
    deg = collections.Counter(len(f.verts) for f in bm.faces)
    bm.faces.ensure_lookup_table()
    mats = [f.material_index for f in bm.faces]
    smooth = [f.smooth for f in bm.faces]
    verts, polys, uvs, src, n_marked, centres = classify_and_split(bm, uv_layer, clear_m)
    bm.free()
    new = bpy.data.meshes.new(me.name + '_quad')
    new.from_pydata([tuple(v) for v in verts], [], polys)
    new.validate(clean_customdata=False)
    uvl = new.uv_layers.new(name='UVMap')
    for p, pu in zip(new.polygons, uvs):
        assert p.loop_total == len(pu)
        for k in range(p.loop_total):
            uvl.data[p.loop_start + k].uv = pu[k]
    for p, s in zip(new.polygons, src):
        p.material_index = mats[s]
        p.use_smooth = smooth[s]
    for m in me.materials:
        new.materials.append(m)
    obj.data = new
    return {'r1': before, 'tjunctions_found': len(tj), 'tjunction_fixes': tj_log, 'polygons_triangulated': len(poly),
            'after_join_degrees': dict(deg), 'pairing': join_info, 'marked_edges': n_marked,
            'quad_faces': len(new.polygons), 'degrees': dict(collections.Counter(p.loop_total for p in new.polygons)),
            'centre_clear_m': clear_m, 'centres': len(centres), 'centres_moved': sum(c['moved'] is True for c in centres),
            'centres_straight_source': sum(c['moved'] == 'straight-source' for c in centres),
            'centres_below_clearance': [c for c in centres if clear_m is not None and c['clearance_m'] <= clear_m]}


MERGE_MAX_M = 0.005      # user decision 2026-11-14 (#1372): R1 overlaps deleted/merged within <= 5 mm
CENTRE_CLEAR_M = 0.0021  # v002 fan centres: > xView 2 mm from every vertex (+0.1 mm for float32 storage)
WELD_M = 0.002           # = xView Overlapping Vertices tolerance: a boolean vertex closer to another is merged
ZONE_MARGIN_M = 0.01     # in-plane margin around a zone (snap, flap search)
SLAB_EPS_M = 0.0005      # snap slab = zone spread + 0.5 mm on the zone axis


def _loose_parts(bm):
    part, n = {}, 0
    for f0 in bm.faces:
        if f0 in part:
            continue
        part[f0] = n
        stack = [f0]
        while stack:
            f = stack.pop()
            for v in f.verts:
                for g in v.link_faces:
                    if g not in part:
                        part[g] = n
                        stack.append(g)
        n += 1
    return part


def _in_zone(co, z, margin=ZONE_MARGIN_M, slab=None):
    ax = z['axis']
    if abs(co[ax] - z['value']) > (z['spread_m'] + SLAB_EPS_M if slab is None else slab):
        return False
    return all(z['lo'][k] - margin <= co[k] <= z['hi'][k] + margin for k in range(3) if k != ax)


def _dedupe(bm, log=None):
    """Delete every face whose vertex set equals another face's (coincident double layer); return (count, area)."""
    groups = collections.defaultdict(list)
    for f in bm.faces:
        groups[frozenset(f.verts)].append(f)
    dup = [f for g in groups.values() if len(g) > 1 for f in g]
    bad = [g for g in groups.values() if len(g) > 1 and (len(g) != 2 or g[0].normal.dot(g[1].normal) > -0.99)]
    if bad:
        raise ValueError(f'{len(bad)} coincident face group(s) that are not an opposite pair; cannot union')
    area = sum(f.calc_area() for f in dup)
    if log is not None:
        log.extend({'centre': [round(c, 6) for c in f.calc_center_median()], 'area_m2': f.calc_area(),
                    'corners': len(f.verts)} for f in dup)
    bmesh.ops.delete(bm, geom=dup, context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    return len(dup), area


def _check_plan(plan):
    """Fail closed on a malformed zone plan: every number finite, axis 0..2, spread <= 5 mm, face ids unique ints."""
    def finite(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    n = plan.get('faces_count')
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise ValueError(f'plan faces_count {n!r} is not a positive int')
    seen = set()
    for k, z in enumerate(plan['zones']):
        if z.get('axis') not in (0, 1, 2) or isinstance(z.get('axis'), bool):
            raise ValueError(f"zone {k}: axis {z.get('axis')!r} not in 0..2")
        if not finite(z.get('value')):
            raise ValueError(f"zone {k}: plane value {z.get('value')!r} is not finite")
        s = z.get('spread_m')
        if not finite(s) or s < 0 or s > MERGE_MAX_M + 1e-5:
            raise ValueError(f'zone {k}: spread {s!r} m outside 0..{MERGE_MAX_M} m')
        for key in ('lo', 'hi'):
            if len(z.get(key) or ()) != 3 or not all(finite(c) for c in z[key]):
                raise ValueError(f'zone {k}: {key} is not 3 finite numbers')
        faces, cents = z.get('faces') or [], z.get('centroids') or []
        if not faces or len(faces) != len(cents):
            raise ValueError(f'zone {k}: faces and centroids missing or of different length')
        for f, c in zip(faces, cents):
            if not isinstance(f, int) or isinstance(f, bool) or not 0 <= f < n or f in seen:
                raise ValueError(f'zone {k}: face id {f!r} invalid or repeated')
            if len(c) != 3 or not all(finite(x) for x in c):
                raise ValueError(f'zone {k}: centroid of face {f} is not 3 finite numbers')
            seen.add(f)


def union_zones(obj, plan):
    """R1 overlap zones (plan_union_zones.py) -> union of the touching solids, same look (#1372, user decision).

    1. the plan faces are the R1 faces (centroid within 10 um, else error);
    2. snap: zone-part vertices inside a zone (its spread + 0.5 mm on the axis, 10 mm margin in plane) go onto the
       exact plane value (<= 5 mm, else error);
    3. exact self-union (Blender boolean EXACT, self intersection) of the loose parts that own zone faces; the other
       parts stay untouched and are appended back;
    4. coincident opposite faces (the double layer between the touching solids) are deleted;
    5. vertices the boolean created are welded to an R1 vertex (else another new vertex) within 2 mm;
    6. dangling flaps inside a zone (every edge boundary or non-manifold, one at least boundary) are deleted.
    Every change is listed in the returned record."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    if len(bm.faces) != plan['faces_count']:
        raise ValueError(f"mesh has {len(bm.faces)} faces, plan {plan['faces_count']}")
    mw = obj.matrix_world
    for z in plan['zones']:
        for f, c in zip(z['faces'], z['centroids']):
            got = mw @ bm.faces[f].calc_center_median()
            if (got - Vector(c)).length > 1e-5:
                raise ValueError(f'plan face {f} is not the R1 face (centroid off by {(got - Vector(c)).length} m)')
    if any(abs(x - y) > 1e-6 for r, row in zip(mw, ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
           for x, y in zip(r, row)):
        raise ValueError(f'{obj.name}: matrix_world is not identity within 1e-6; zone planes are world values')
    part = _loose_parts(bm)
    zone_parts = sorted({part[bm.faces[f]] for z in plan['zones'] for f in z['faces']})
    zp = set(zone_parts)
    snaps, snap_log = [], []
    for v in bm.verts:
        if not any(part[f] in zp for f in v.link_faces):
            continue
        hit = [z for z in plan['zones'] if _in_zone(v.co, z)]
        vals = {(z['axis'], z['value']) for z in hit}
        if len(vals) > 1:
            raise ValueError(f'vertex {v.index} at {tuple(v.co)} lies in zones with different planes {sorted(vals)}')
        if hit:
            ax, val = hit[0]['axis'], hit[0]['value']
            d = abs(v.co[ax] - val)
            if d > MERGE_MAX_M + 1e-5:  # float32 storage tolerance at ~15 m
                raise ValueError(f'vertex {v.index}: snap {d * 1000:.2f} mm > {MERGE_MAX_M * 1000} mm')
            snaps.append(d)
            if d > 0:
                snap_log.append({'from': [round(c, 6) for c in v.co], 'axis': 'xyz'[ax], 'to': val, 'move_m': d})
            v.co[ax] = val
    rest_bm = bm.copy()
    rest_bm.faces.ensure_lookup_table()
    other = [f for f in bm.faces if part[f] not in zp]
    other_idx = {f.index for f in other}
    bmesh.ops.delete(bm, geom=other, context='FACES')
    bmesh.ops.delete(rest_bm, geom=[f for f in rest_bm.faces if f.index not in other_idx], context='FACES')
    bm.to_mesh(me); bm.free()
    rest = bpy.data.meshes.new(me.name + '_untouched_parts')
    rest_bm.to_mesh(rest); rest_bm.free()
    old = KDTree(len(me.vertices))
    for v in me.vertices:
        old.insert(v.co, v.index)
    old.balance()
    faces_in = len(me.polygons)
    col = bpy.data.collections.new('union_no_operand')
    m = obj.modifiers.new('union_zones', 'BOOLEAN')
    m.solver, m.operation, m.operand_type, m.collection, m.use_self = 'EXACT', 'UNION', 'COLLECTION', col, True
    bpy.context.view_layer.objects.active = obj
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=m.name)
    me = obj.data
    faces_bool = len(me.polygons)
    bm = bmesh.new(); bm.from_mesh(me)
    deleted = []
    dup_n, dup_area = _dedupe(bm, deleted)
    new = [v for v in bm.verts if old.find(v.co)[2] > 1e-7]
    oldv = [v for v in bm.verts if old.find(v.co)[2] <= 1e-7]
    kd = KDTree(len(oldv))
    for i, v in enumerate(oldv):
        kd.insert(v.co, i)
    kd.balance()
    target, welds = {}, []
    for v in new:
        co, i, d = kd.find(v.co)
        if co is not None and d <= WELD_M:
            target[v] = oldv[i]
            welds.append({'to': 'r1', 'distance_m': d, 'at': list(oldv[i].co)})
    free = [v for v in new if v not in target]
    kdn = KDTree(len(free))
    for i, v in enumerate(free):
        kdn.insert(v.co, i)
    kdn.balance()
    for v in free:
        if v in target:
            continue
        for _, i, d in kdn.find_range(v.co, WELD_M):
            w = free[i]
            if w is not v and w not in target and v not in target:
                target[w] = v
                welds.append({'to': 'new', 'distance_m': d, 'at': list(v.co)})
    bmesh.ops.weld_verts(bm, targetmap=target)
    rounds = []
    for _ in range(10):
        n, a = _dedupe(bm, deleted)
        flaps = [f for f in bm.faces
                 if all(len(e.link_faces) != 2 for e in f.edges) and any(len(e.link_faces) == 1 for e in f.edges)
                 and any(all(_in_zone(v.co, z, slab=MERGE_MAX_M) for v in f.verts) for z in plan['zones'])]
        flap_rec = [{'centre': list(f.calc_center_median()), 'area_m2': f.calc_area(), 'corners': len(f.verts)}
                    for f in flaps]
        bmesh.ops.delete(bm, geom=flaps, context='FACES_ONLY')
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        rounds.append({'duplicates_deleted': n, 'duplicates_area_m2': a, 'flaps_deleted': flap_rec})
        if not n and not flaps:
            break
    else:
        raise ValueError('union cleanup did not converge in 10 rounds')
    degenerate = [f.index for f in bm.faces if f.calc_area() < 1e-12]
    if degenerate:
        raise ValueError(f'{len(degenerate)} zero-area face(s) after the union: {degenerate[:5]}')
    before_faces = set(bm.faces)
    bm.from_mesh(rest)   # untouched loose parts back, unchanged
    uvl = bm.loops.layers.uv.active
    tail = sorted([f.material_index] + [tuple(round(c, 7) for c in l[uvl].uv) + tuple(round(c, 7) for c in l.vert.co)
                                        for l in f.loops] for f in bm.faces if f not in before_faces)
    want = sorted([p.material_index] + [tuple(round(c, 7) for c in rest.uv_layers.active.data[i].uv)
                                        + tuple(round(c, 7) for c in rest.vertices[rest.loops[i].vertex_index].co)
                                        for i in p.loop_indices] for p in rest.polygons)
    if tail != want:
        bad = next(i for i, (a, b) in enumerate(zip(tail, want)) if a != b) if len(tail) == len(want) else -1
        raise ValueError(f'untouched parts changed while appending them back (UV or position): face {bad} '
                         f'{tail[bad] if bad >= 0 else len(tail)} != {want[bad] if bad >= 0 else len(want)}; '
                         f'uv layers bm {[l.name for l in bm.loops.layers.uv.values()]} '
                         f'rest {[l.name for l in rest.uv_layers]}')
    bm.to_mesh(me); bm.free()
    bpy.data.meshes.remove(rest)
    return {'zones': len(plan['zones']), 'zone_parts': zone_parts, 'snapped_vertices': len(snaps),
            'snap_max_m': max(snaps, default=0.0), 'faces_into_union': faces_in, 'faces_after_boolean': faces_bool,
            'double_layer_faces_deleted': dup_n, 'double_layer_area_m2': dup_area, 'snap_log': snap_log,
            'deleted_faces': deleted,
            'boolean_vertices_new': len(new), 'welds': welds, 'weld_max_m': max((w['distance_m'] for w in welds),
                                                                                   default=0.0),
            'cleanup_rounds': rounds, 'faces_out': len(me.polygons)}


def tri_bvh(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.faces.index_update()
    tris = [[tuple(float(c) for c in l.vert.co) for l in f.loops] for f in bm.faces]
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh, tris


def samples(tris, per=6):
    pts = []
    bary = [(1/3, 1/3, 1/3)] + [((i + .5) / per, (per - i - .5) / per / 2, (per - i - .5) / per / 2) for i in range(per)]
    for a, b, c in tris:
        pts += [a, b, c] + [tuple(a[k] * x + b[k] * y + c[k] * z for k in range(3)) for x, y, z in bary]
    return pts


def _pt_tri64(p, a, b, c):
    """Exact float64 point-triangle distance (Ericson, Real-Time Collision Detection 5.1.5)."""
    sub = lambda u, v: (u[0] - v[0], u[1] - v[1], u[2] - v[2])
    dot = lambda u, v: u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        q = a
    else:
        bp = sub(p, b); d3, d4 = dot(ab, bp), dot(ac, bp)
        cp = sub(p, c); d5, d6 = dot(ab, cp), dot(ac, cp)
        vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
        if d3 >= 0 and d4 <= d3:
            q = b
        elif vc <= 0 and d1 >= 0 and d3 <= 0:
            t = d1 / (d1 - d3); q = (a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2])
        elif d6 >= 0 and d5 <= d6:
            q = c
        elif vb <= 0 and d2 >= 0 and d6 <= 0:
            t = d2 / (d2 - d6); q = (a[0] + t * ac[0], a[1] + t * ac[1], a[2] + t * ac[2])
        elif va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
            t = (d4 - d3) / ((d4 - d3) + (d5 - d6)); q = (b[0] + t * (c[0] - b[0]), b[1] + t * (c[1] - b[1]), b[2] + t * (c[2] - b[2]))
        else:
            den = 1.0 / (va + vb + vc); v, w = vb * den, vc * den
            q = (a[0] + ab[0] * v + ac[0] * w, a[1] + ab[1] * v + ac[1] * w, a[2] + ab[2] * v + ac[2] * w)
    d = sub(p, q)
    return math.sqrt(dot(d, d))


def distance(bvh_to, tris_to, pts64, zones=()):
    """Two-stage distance: float32 BVH prefilter, float64 exact recheck of every sample above 1 um
    (mathutils is float32: needle triangles give ~1 mm artefacts that are not geometry).
    With `zones` (v002 union plan) the samples inside a zone are reported apart: there the hidden double layer
    between touching solids was removed on purpose, so R1 points have no new surface on them."""
    out, inside, rechecked = [], [], 0
    for p in pts64:
        d = bvh_to.find_nearest(Vector(p))[3]
        if d > 1e-6:
            rechecked += 1
            cand = {i for _, _, i, _ in bvh_to.find_nearest_range(Vector(p), d + 1e-3)}
            d = min(_pt_tri64(p, *tris_to[i]) for i in cand)
        (inside if any(_in_zone(p, z, slab=MERGE_MAX_M) for z in zones) else out).append(d)

    def stats(xs):
        xs.sort()
        return {'samples': len(xs), 'max_m': xs[-1], 'p95_m': xs[int(0.95 * (len(xs) - 1))],
                'mean_m': sum(xs) / len(xs)} if xs else {'samples': 0}
    res = {**stats(out), 'float64_rechecked': rechecked}
    if zones:
        res['inside_union_zones'] = stats(inside)
    return res


def main(root, version='v001', zones_path=None):
    """v001: R1 -> quads. v002: R1 -> union of the R1 overlap zones (plan json, user decision) -> quads."""
    src = root / 'source/SM_Kpp_1.fbx'
    if sha(src) != SOURCE_SHA:
        raise ValueError('source is not the approved r1-v002 SM_Kpp_1.fbx')
    if (version == 'v001') != (zones_path is None):
        raise ValueError('v001 is the plain quadification; every later version needs the union zone plan')
    plan = None
    if zones_path is not None:
        zones_path = Path(zones_path).resolve()
        plan = json.loads(zones_path.read_text())
        if plan.get('source_sha256') != SOURCE_SHA or plan.get('part') != 'SM_Kpp_1_Main' or not plan.get('zones'):
            raise ValueError(f'{zones_path}: not a union plan of the approved R1 SM_Kpp_1_Main')
        _check_plan(plan)
    suffix = '' if version == 'v001' else f'-{version}'
    out_blend, out_fbx, report = (root / f'master-quad-{version}.blend', root / f'SM_Kpp_1.quad-{version}.fbx',
                                  root / f'quad-build{suffix}.json')
    if any(p.exists() for p in (out_blend, out_fbx, report)):
        raise ValueError('quad master outputs occupied; use a new version')
    if zones_path is not None and zones_path in {p.resolve() for p in (out_blend, out_fbx, report, src)}:
        raise ValueError('zone plan path aliases an output or the source')
    spec = json.loads((root / 'spec.json').read_text())
    by_tile = {t['udim']: name for name, t in spec['finishes'].items()}
    names = list(spec['finishes'])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(src))
    objs = {o.name: o for o in bpy.context.scene.objects}
    missing = [n for n in RENDER if n not in objs]
    if missing:
        raise ValueError(f'render meshes missing: {missing}')
    r1 = {n: tri_bvh(objs[n]) for n in RENDER}
    ucx_before = {n: fingerprint(o) for n, o in objs.items() if n.startswith('UCX_')}
    rep = {'source_sha256': SOURCE_SHA, 'blender': bpy.app.version_string, 'planar_tol_m': PLANAR_TOL_M,
           'tj_tol_m': TJ_TOL, 'version': version, 'meshes': {}}
    if plan is not None:
        rep['union_plan'] = {'path': str(zones_path), 'sha256': sha(zones_path), 'xview_r1': plan['xview_r1']}
        rep['union'] = union_zones(objs['SM_Kpp_1_Main'], plan)
    zones = plan['zones'] if plan else ()
    for n in RENDER:
        o = objs[n]
        info = quadify(o, CENTRE_CLEAR_M if plan else None)
        bvh, tris = tri_bvh(o)
        r1_bvh, r1_tris = r1[n]
        zn = zones if n == 'SM_Kpp_1_Main' else ()
        info['distance_new_to_r1'] = distance(r1_bvh, r1_tris, samples(tris), zn)
        info['distance_r1_to_new'] = distance(bvh, tris, samples(r1_tris), zn)
        info['triangulated_beauty_tris'] = len(tris)
        rep['meshes'][n] = info
    # finish attribute from UDIM tiles (prepare_master.py rule), on the quad Main
    main_o = objs['SM_Kpp_1_Main']
    uv = main_o.data.uv_layers['UVMap']
    attr = main_o.data.attributes.new(name='finish', type='INT', domain='FACE')
    counts = dict.fromkeys(names, 0)
    for p in main_o.data.polygons:
        pts = [uv.data[i].uv for i in p.loop_indices]
        cx = sum(v.x for v in pts) / len(pts); cy = sum(v.y for v in pts) / len(pts)
        tx, ty = math.floor(cx), math.floor(cy)
        tile = 1001 + tx + 10 * ty
        if tile not in by_tile or any(not (tx <= v.x <= tx + 1 and ty <= v.y <= ty + 1) for v in pts):
            raise ValueError(f'face {p.index}: unsupported or crossing UDIM {tile}')
        attr.data[p.index].value = names.index(by_tile[tile])
        counts[by_tile[tile]] += 1
    if any(v == 0 for v in counts.values()):
        raise ValueError(f'empty finish account: {counts}')
    main_o['finish_names'] = ','.join(names)
    rep['finish_faces'] = counts
    assert ucx_before == {n: fingerprint(o) for n, o in objs.items() if n.startswith('UCX_')}
    before = {n: fingerprint(o) for n, o in objs.items()}
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    bpy.ops.export_scene.fbx(filepath=str(out_fbx), use_selection=False, object_types={'MESH'},
                             mesh_smooth_type='FACE', use_triangles=False, add_leaf_bones=False,
                             axis_forward='-Z', axis_up='Y', apply_unit_scale=True, bake_space_transform=False)
    bpy.ops.wm.open_mainfile(filepath=str(out_blend))
    reopened = {o.name: fingerprint(o) for o in bpy.context.scene.objects}
    if reopened != before:
        raise ValueError('reopened blend differs from the built master')
    rep.update({'fingerprints': before, 'outputs': {out_blend.name: sha(out_blend), out_fbx.name: sha(out_fbx)},
                'master_type': 'all-quad editable master (#1372); delivery copies stay triangulated (reg p.8 3.11)',
                'approval': 'Artem 2026-11-14 "Да, давай сделаем квад мастер" (#1372)'
                + ('; v002 union of R1 overlaps <= 5 mm and 100 % quads: Artem 2026-11-14 "Принимаю рекомендации"'
                   if plan else ''), 'synthetic': False})
    report.write_text(json.dumps(rep, indent=2))
    print('QUAD', json.dumps({n: {k: v for k, v in i.items() if k != 'tjunction_fixes'} for n, i in rep['meshes'].items()}))
    if plan:
        print('UNION', json.dumps({k: v for k, v in rep['union'].items() if k not in ('welds', 'snap_log', 'deleted_faces')}))


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    main(Path(args[0]), *args[1:3])
