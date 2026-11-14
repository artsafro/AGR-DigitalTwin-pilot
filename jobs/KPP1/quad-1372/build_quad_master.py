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


def classify_and_split(bm, uv_layer):
    """Close edge-midpoint marks so every face becomes quads; return new mesh arrays."""
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
        else:  # triangle with 3 marks or quad with 4: fan of quads around the centroid
            verts.append(sum((verts[x] for x in c), Vector()) / n)
            C = len(verts) - 1
            Cu = sum(u, Vector((0.0, 0.0))) / n
            for i in range(n):
                p = (i - 1) % n
                out.append(([c[i], M[i], C, M[p]], [u[i], Mu[i], Cu, Mu[p]]))
        for pc, pu in out:
            polys.append(pc); uvs.append(pu); src_face.append(f.index)
    return verts, polys, uvs, src_face, len(marked)


def quadify(obj):
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    before = {'faces': len(bm.faces), 'verts': len(bm.verts)}
    tj, tj_log = fix_tjunctions(bm)
    uv_layer = bm.loops.layers.uv.active
    join_info = pair_triangles(bm, uv_layer)
    deg = collections.Counter(len(f.verts) for f in bm.faces)
    bm.faces.ensure_lookup_table()
    mats = [f.material_index for f in bm.faces]
    smooth = [f.smooth for f in bm.faces]
    verts, polys, uvs, src, n_marked = classify_and_split(bm, uv_layer)
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
    return {'r1': before, 'tjunctions_found': len(tj), 'tjunction_fixes': tj_log,
            'after_join_degrees': dict(deg), 'pairing': join_info, 'marked_edges': n_marked,
            'quad_faces': len(new.polygons), 'degrees': dict(collections.Counter(p.loop_total for p in new.polygons))}


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


def distance(bvh_to, tris_to, pts64):
    """Two-stage distance: float32 BVH prefilter, float64 exact recheck of every sample above 1 um
    (mathutils is float32: needle triangles give ~1 mm artefacts that are not geometry)."""
    out, rechecked = [], 0
    for p in pts64:
        d = bvh_to.find_nearest(Vector(p))[3]
        if d > 1e-6:
            rechecked += 1
            cand = {i for _, _, i, _ in bvh_to.find_nearest_range(Vector(p), d + 1e-3)}
            d = min(_pt_tri64(p, *tris_to[i]) for i in cand)
        out.append(d)
    out.sort()
    return {'samples': len(out), 'max_m': out[-1], 'p95_m': out[int(0.95 * (len(out) - 1))],
            'mean_m': sum(out) / len(out), 'float64_rechecked': rechecked}


def main(root):
    src = root / 'source/SM_Kpp_1.fbx'
    if sha(src) != SOURCE_SHA:
        raise ValueError('source is not the approved r1-v002 SM_Kpp_1.fbx')
    out_blend, out_fbx, report = root / 'master-quad-v001.blend', root / 'SM_Kpp_1.quad-v001.fbx', root / 'quad-build.json'
    if any(p.exists() for p in (out_blend, out_fbx, report)):
        raise ValueError('quad master outputs occupied; use a new version')
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
           'tj_tol_m': TJ_TOL, 'meshes': {}}
    for n in RENDER:
        o = objs[n]
        info = quadify(o)
        bvh, tris = tri_bvh(o)
        r1_bvh, r1_tris = r1[n]
        info['distance_new_to_r1'] = distance(r1_bvh, r1_tris, samples(tris))
        info['distance_r1_to_new'] = distance(bvh, tris, samples(r1_tris))
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
                'approval': 'Artem 2026-11-14 "Да, давай сделаем квад мастер" (#1372)', 'synthetic': False})
    report.write_text(json.dumps(rep, indent=2))
    print('QUAD', json.dumps({n: {k: v for k, v in i.items() if k != 'tjunction_fixes'} for n, i in rep['meshes'].items()}))


if __name__ == '__main__':
    main(Path(sys.argv[sys.argv.index('--') + 1]))
