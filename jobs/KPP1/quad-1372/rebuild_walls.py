"""new-case: KPP1 quad master v004 = v003 with the W, S and N facade planes rebuilt as whole clean grids (#1609, [D357]).

Artem 2026-11-20 «по кпп ок», option A: rebuild the W, S and N walls as whole planes by BM-01..03/BM-11 - lines only at
the wall outline (openings, edges) and at finish borders, posts as separate inset elements [D336], a new continuous
UV per finish (the R1-atlas seams are dropped); the NPM atlas is rebaked by `agr vpm-to-npm` from the new master.
Run in Blender 5.1 on the v003 master (never written):
    blender -b --factory-startup --python rebuild_walls.py -- <master-quad-v003.blend> <r1-v003 local FBX> <new out dir>

1. Corner posts out of the body and planned from r1-v003 as separate elements (`rebuild_corners.plan_posts`).
2. Per facade (`WALLS`) every plane of axis-aligned outward faces (`facade_planes`, >= AREA_MIN m2) is replaced by
   the `wall_plan.plan` grid; the posts' hidden contact area counts as wall (wildcard finish, the row neighbour's).
   Each rebuilt plane is an element of its own (D336, SKELETONS "embed/offset, never welding"): no node is welded to
   the body; outline nodes move EMB_M past the old outline (`wall_plan.embed_shifts`), so the body's border vertices
   stay > the 2 mm xView vertex limit away. Witness: `nodes_near_other_vertex` in the report.
   UV: planar, 1/S per metre as in v003, continuous inside segments of <= S along the facade and in z; seams on
   existing grid lines; UDIM tile = the finish's tile (`finish` attribute kept). UV uses the unshifted grid.
3. Posts back as separate unwelded elements (`rebuild_corners.build_posts`, UV from r1).
Outputs (new files only): `master-quad-v004.blend`, `SM_Kpp_1.quad-v004.fbx`, `walls-build-v004.json`.
"""
import json
import os
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rebuild_corners as rc  # noqa: E402
import wall_plan as wp  # noqa: E402
from udimtile_core import face_tile, tile_origin  # noqa: E402  (path set by rebuild_corners)

VERSION = 'v004'
S = 2.048            # metres per UDIM tile, spec.json `S` of every KPP1 finish (v003 UV scale 0.488 = 1/2.048)
MAX_CELL = S         # a cell never spans more than one UV segment
PLANE_M = rc.PLANE_M
SNAP_M = 3e-3        # vertex coordinates within 3 mm share one grid line: no wall cell/slot under the 2 mm xView
                     # vertex limit (w7 with 2.1 mm chained clusters into 1.6-2.0 mm gaps, #1609 w8)
EMB_M = 3e-3         # w9 (default): outline nodes reach 3 mm past the old outline, walls are separate elements.
                     # V004 per mesh counts the lip through the body's reveals: 9 653 (7 549 pierce pairs, all
                     # between elements). BODY_WELD=True (w10/w11 probes) sets EMB_M = 0 and welds walls to the body.
BODY_WELD = False    # w10: weld only (dup 199 + self-int 40, but ~2 900 T-junction fans at the reveals);
                     # w11: + collapse the T vertices onto wall nodes (V004 129, but 6 333 triangles): both rejected
CONFORM = True       # w12 (variant A, Artem 2026-11-20 «принимаю рекомендации»): every flat axis plane of the body
                     # (walls, reveals, niches, sills, heads) on one conforming line set (`wall_plan.conform`), welded
                     # as one body; posts separate elements. Replaces the per-plane walls + embed of w9.
if BODY_WELD or CONFORM:
    EMB_M = 0.0
WELD_BODY_M = 2.1e-3  # wall/body vertices closer than the 2 mm V004/xView tolerance (+0.1 mm) are welded (body only)
AREA_MIN = 0.5       # m2; smaller planes stay as in v003
XVIEW_M = 2e-3       # xView vertex limit, judged per element [D336]: `wall_plan.relax_shifts` keeps wall nodes apart
FLAT_M = 2e-3        # a facade face within 2 mm of flat (r1 float noise, 0.1-1.2 mm tilts) joins its plane
BOWTIE_M = 2.5e-3    # a body vertex left with two face fans (its plane faces went to a wall) splits; each extra copy
                     # moves 2.5 mm into its fan (> the 2 mm xView vertex limit), hidden under the 3 mm wall embed
# w8: the post side faces now END ON the rebuilt plane (w7 moved them 6 mm behind it, which folded the 10 mm post
# steps into 4 mm stubs and 2 mm vertex pairs inside the post element); posts and walls are separate elements [D336].
WALLS = {  # ax: plane normal axis; hax: in-plane horizontal axis; tsign: facade direction of u (v003 UV sign)
    'W': {'ax': 0, 'sg': -1, 'hax': 1, 'tsign': -1},
    'S': {'ax': 1, 'sg': -1, 'hax': 0, 'tsign': 1},
    'N': {'ax': 1, 'sg': 1, 'hax': 0, 'tsign': -1},
}


def facade_planes(bm, w):
    """Every plane of the facade: axis-aligned faces looking out (normal sg along ax), grouped by their position
    along ax (positions within PLANE_M + 1 mm are one plane: the r1 0.4 mm double layer). Planes < AREA_MIN stay."""
    ax, sg = w['ax'], w['sg']
    found = {}
    for f in bm.faces:
        if f.normal[ax] * sg < 0.999:
            continue
        vals = [v.co[ax] for v in f.verts]
        if max(vals) - min(vals) > FLAT_M:
            continue
        found.setdefault(round(sum(vals) / len(vals), 3), []).append(f)
    groups = []
    for k in sorted(found):
        if groups and k - groups[-1][-1] <= PLANE_M + 1e-3:
            groups[-1].append(k)
        else:
            groups.append([k])
    out = []
    for g in groups:
        faces = [f for k in g for f in found[k]]
        area = sum(f.calc_area() for f in faces)
        if area >= AREA_MIN:
            plane = sum(v.co[ax] for f in faces for v in f.verts) / sum(len(f.verts) for f in faces)
            out.append((plane, faces, area))
    return out


def build_wall(bm, name, w, plane, old, contact, uvl, fl, tile_of_finish):
    """Replace the faces `old` of one plane by the wall_plan grid as an element of its own: never welded to the
    body, outline nodes embedded EMB_M past the old outline (wall_plan.embed_shifts)."""
    ax, hax, sg, tsign = w['ax'], w['hax'], w['sg'], w['tsign']
    faces2d = [([(v.co[hax], v.co.z) for v in f.verts], f[fl]) for f in old]
    for corners_, n in contact:
        if abs(n[ax]) == 1 and all(abs(c[ax] - plane) <= PLANE_M for c in corners_):
            faces2d.append(([(c[hax], c[2]) for c in corners_], None))
    p = wp.plan(faces2d, MAX_CELL, SNAP_M)
    H, Z, cells = p['H'], p['Z'], p['cells']
    if EMB_M > 0:
        shifts0, stuck, clamped = wp.embed_shifts(cells, H, Z, EMB_M)
        shifts = wp.relax_shifts(cells, H, Z, shifts0, XVIEW_M)
    else:   # w10: the wall is body, welded to the body at its outline (weld_body); nothing overhangs
        shifts0, shifts, stuck, clamped = {}, {}, [], []
    relaxed = sum(1 for k, v in shifts0.items() if shifts.get(k) != v)
    old_verts = {v for f in old for v in f.verts}
    bmesh.ops.delete(bm, geom=old, context='FACES_ONLY')
    loose = [v for v in old_verts if v.is_valid and not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    t_lines = H if tsign > 0 else [-h for h in reversed(H)]
    t_start = wp.uv_segments(t_lines, S)
    z_start = wp.uv_segments(Z, S)
    nodes = {}

    def node(a, b):
        if (a, b) not in nodes:
            dh, dz = shifts.get((a, b), (0.0, 0.0))
            co = [0.0, 0.0, 0.0]
            co[ax], co[hax], co[2] = plane, H[a] + dh, Z[b] + dz
            nodes[(a, b)] = bm.verts.new(co)
        return nodes[(a, b)]
    e_h = [0.0, 0.0, 0.0]
    e_h[hax] = 1.0
    flip = Vector(e_h).cross(Vector((0.0, 0.0, 1.0)))[ax] * sg < 0
    made = []
    for (a, b), fin in sorted(cells.items()):
        if fin not in tile_of_finish:
            raise ValueError(f'{name}: finish {fin} has no UDIM tile in the master')
        u0, v0 = tile_origin(tile_of_finish[fin])
        ts = t_start[a if tsign > 0 else len(H) - 2 - a]
        ring = [(a, b), (a + 1, b), (a + 1, b + 1), (a, b + 1)]
        if flip:
            ring = ring[::-1]
        f = bm.faces.new([node(*k) for k in ring])
        for loop, (ia, ib) in zip(f.loops, ring):
            loop[uvl].uv = (u0 + (tsign * H[ia] - ts) / S, v0 + (Z[ib] - z_start[b]) / S)
        if face_tile([tuple(lp[uvl].uv) for lp in f.loops]) != tile_of_finish[fin]:
            raise ValueError(f'{name}: cell {a},{b} UV left its tile')
        f[fl] = fin
        f.material_index = 0
        f.smooth = False
        made.append(f)
    gaps = sorted(bb - aa for vals in (H, Z) for aa, bb in zip(vals, vals[1:]))
    return made, {'plane': round(plane, 4), 'faces_old': len(old), 'faces_new': len(made), 'lines_h': len(H),
                  'lines_z': len(Z), 'fine_lines': p['fine'], 'snap_max_m': round(p['snap_max_m'], 6),
                  'min_gap_m': round(gaps[0], 5), 'gaps_below_3cm': sum(1 for g in gaps if g < 0.03),
                  'area_error_m2': {str(k): round(v, 6) for k, v in p['area_error_m2'].items()},
                  'nodes': len(nodes), 'nodes_embedded': len(shifts), 'nodes_stuck': len(stuck), 'nodes_clamped': len(clamped), 'nodes_relaxed': relaxed,
                  'uv_segments_t': len(set(t_start)), 'uv_segments_z': len(set(z_start))}


def axes2d(ax):
    """World axes of the in-plane (h, z) coordinates of a plane with normal axis `ax`."""
    return {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]


def all_planes(bm, posts, wall_dirs):
    """Variant A: every connected flat axis-aligned piece of the body, all six normal directions. Faces at
    positions within PLANE_M + 1 mm are one plane (the r1 0.4 mm double layer); a plane splits into components
    (faces linked by vertices, merged while their 2D boxes touch). Post faces join only the W/S/N directions
    (`wall_dirs`, their flush faces become wall as in w9); posts stay separate elements otherwise."""
    found = {}
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        if abs(n[ax]) < 0.999:
            continue
        sg = 1 if n[ax] > 0 else -1
        if f in posts and (ax, sg) not in wall_dirs:
            continue
        vals = [v.co[ax] for v in f.verts]
        if max(vals) - min(vals) > FLAT_M:
            continue
        found.setdefault((ax, sg), {}).setdefault(round(sum(vals) / len(vals), 3), []).append(f)
    out = []
    for (ax, sg), d in sorted(found.items()):
        groups = []
        for k in sorted(d):
            if groups and k - groups[-1][-1] <= PLANE_M + 1e-3:
                groups[-1].append(k)
            else:
                groups.append([k])
        a1, a2 = axes2d(ax)
        for g in groups:
            faces = [f for k in g for f in d[k]]
            parent = {f: f for f in faces}

            def root(f):
                while parent[f] is not f:
                    parent[f] = parent[parent[f]]
                    f = parent[f]
                return f
            by_v = {}
            for f in faces:
                for v in f.verts:
                    by_v.setdefault(v, []).append(f)
            for fs in by_v.values():
                for f in fs[1:]:
                    a, b = root(fs[0]), root(f)
                    if a is not b:
                        parent[a] = b
            comps = {}
            for f in faces:
                comps.setdefault(root(f), []).append(f)
            boxes = []
            for fs in comps.values():
                co = [v.co for f in fs for v in f.verts]
                boxes.append([fs, min(c[a1] for c in co), max(c[a1] for c in co),
                              min(c[a2] for c in co), max(c[a2] for c in co)])
            merged = True
            while merged:
                merged = False
                for i in range(len(boxes)):
                    for j in range(i + 1, len(boxes)):
                        p, q = boxes[i], boxes[j]
                        if p[1] <= q[2] + SNAP_M and q[1] <= p[2] + SNAP_M and p[3] <= q[4] + SNAP_M \
                                and q[3] <= p[4] + SNAP_M:
                            boxes[i] = [p[0] + q[0], min(p[1], q[1]), max(p[2], q[2]), min(p[3], q[3]), max(p[4], q[4])]
                            del boxes[j]
                            merged = True
                            break
                    if merged:
                        break
            for fs, h0, h1, z0, z1 in boxes:
                pos = sum(v.co[ax] for f in fs for v in f.verts) / sum(len(f.verts) for f in fs)
                out.append({'ax': ax, 'sg': sg, 'axes': (a1, a2), 'pos': pos, 'faces': fs, 'box': (h0, h1, z0, z1)})
    return out


def adjacency(bm, face_pid, planes):
    """{(p, q): [(t, lo, hi)]} from the body edges between two plane components with different normal axes; spans
    along the same axis are merged. Returns (adj, skipped edges that are not axis-aligned)."""
    raw, skipped = {}, 0
    for e in bm.edges:
        lf = [face_pid.get(f) for f in e.link_faces]
        if len(lf) != 2 or None in lf or lf[0] == lf[1]:
            continue
        p, q = sorted(lf)
        if planes[p]['ax'] == planes[q]['ax']:
            continue
        d = e.verts[1].co - e.verts[0].co
        t = 3 - planes[p]['ax'] - planes[q]['ax']
        if d.length < 1e-9 or abs(d[t]) < 0.999 * d.length:
            skipped += 1
            continue
        lo, hi = sorted((e.verts[0].co[t], e.verts[1].co[t]))
        raw.setdefault((p, q, t), []).append((lo, hi))
    adj = {}
    for (p, q, t), spans in raw.items():
        spans.sort()
        merged = [list(spans[0])]
        for lo, hi in spans[1:]:
            if lo <= merged[-1][1] + SNAP_M:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        adj.setdefault((p, q), []).extend((t, lo, hi) for lo, hi in merged)
    return adj, skipped


def uv_axes(faces, uvl, axes):
    """(u from h or z, u sign, v sign) of the old UV: least squares of the in-face UV deltas against the in-plane
    coordinate deltas (R1-atlas seam offsets drop out of in-face deltas). Default (h, +, +) when unmeasurable."""
    a1, a2 = axes
    s = [[0.0, 0.0], [0.0, 0.0]]   # s[uv][coord] = sum duv * dcoord
    for f in faces:
        lps = list(f.loops)
        for la, lb in zip(lps, lps[1:] + lps[:1]):
            dc = (lb.vert.co[a1] - la.vert.co[a1], lb.vert.co[a2] - la.vert.co[a2])
            du = (lb[uvl].uv[0] - la[uvl].uv[0], lb[uvl].uv[1] - la[uvl].uv[1])
            for i in range(2):
                for j in range(2):
                    s[i][j] += du[i] * dc[j]
    if abs(s[0][0]) + abs(s[0][1]) < 1e-9:
        return 0, 1, 1
    uax = 0 if abs(s[0][0]) >= abs(s[0][1]) else 1
    usg = 1 if s[0][uax] >= 0 else -1
    vsg = 1 if s[1][1 - uax] >= 0 else -1
    return uax, usg, vsg


def build_plane(bm, pl, p, uvl, fl, tile_of_finish):
    """Grid of plan `p` on plane component `pl` (welded later: variant A, the walls are one body with the reveals).
    UV planar 1/S per metre, axes and signs as the old faces (`uv_axes`), continuous inside segments of <= S."""
    ax, sg, (a1, a2), pos = pl['ax'], pl['sg'], pl['axes'], pl['pos']
    H, Z, cells = p['H'], p['Z'], p['cells']
    uax, usg, vsg = pl['uv']
    lines_ = (H, Z)

    def seg(vals, sign):
        tl = vals if sign > 0 else [-x for x in reversed(vals)]
        st = wp.uv_segments(tl, S)
        return lambda a: st[a if sign > 0 else len(vals) - 2 - a]
    su, sv = seg(lines_[uax], usg), seg(lines_[1 - uax], vsg)
    nodes = {}

    def node(a, b):
        if (a, b) not in nodes:
            co = [0.0, 0.0, 0.0]
            co[ax], co[a1], co[a2] = pos, H[a], Z[b]
            nodes[(a, b)] = bm.verts.new(co)
        return nodes[(a, b)]
    e1, e2 = [0.0] * 3, [0.0] * 3
    e1[a1], e2[a2] = 1.0, 1.0
    flip = Vector(e1).cross(Vector(e2))[ax] * sg < 0
    made = []
    for (a, b), fin in sorted(cells.items()):
        if fin not in tile_of_finish:
            raise ValueError(f'plane {ax}{sg:+d}@{pos:.3f}: finish {fin} has no UDIM tile in the master')
        u0, v0 = tile_origin(tile_of_finish[fin])
        ij = (a, b)
        us, vs = su(ij[uax]), sv(ij[1 - uax])
        ring = [(a, b), (a + 1, b), (a + 1, b + 1), (a, b + 1)]
        if flip:
            ring = ring[::-1]
        f = bm.faces.new([node(*k) for k in ring])
        for loop, k in zip(f.loops, ring):
            cu, cv = lines_[uax][k[uax]], lines_[1 - uax][k[1 - uax]]
            loop[uvl].uv = (u0 + (usg * cu - us) / S, v0 + (vsg * cv - vs) / S)
        if face_tile([tuple(lp[uvl].uv) for lp in f.loops]) != tile_of_finish[fin]:
            raise ValueError(f'plane {ax}{sg:+d}@{pos:.3f}: cell {a},{b} UV left its tile')
        f[fl] = fin
        f.material_index = 0
        f.smooth = False
        made.append(f)
    return made


def conform_rebuild(bm, posts, contact, uvl, fl, tile_of_finish, rep):
    """Variant A (Artem 2026-11-20 «принимаю рекомендации»): all flat axis planes of the body rebuilt on one
    conforming set of grid lines (`wall_plan.conform`), then welded: walls, reveals, niches, sills and heads are one
    body whose nodes coincide on every shared edge; posts stay separate elements [D336]."""
    import time
    t0 = time.perf_counter()
    wall_dirs = {(w['ax'], w['sg']) for w in WALLS.values()}
    planes = all_planes(bm, set(posts), wall_dirs)
    print('CONFORM planes', len(planes), round(time.perf_counter() - t0, 1), flush=True)
    face_pid = {f: i for i, pl in enumerate(planes) for f in pl['faces']}
    adj, skipped = adjacency(bm, face_pid, planes)
    print('CONFORM adj', len(adj), round(time.perf_counter() - t0, 1), flush=True)
    unplaced = 0
    kplanes = {}
    for i, pl in enumerate(planes):
        pl['uv'] = uv_axes(pl['faces'], uvl, pl['axes'])
        a1, a2 = pl['axes']
        kplanes[i] = {'faces': [([(v.co[a1], v.co[a2]) for v in f.verts], f[fl]) for f in pl['faces']],
                      'axes': pl['axes'], 'ax': pl['ax'], 'pos': pl['pos']}
    for corners_, n in contact:
        ax = max(range(3), key=lambda i: abs(n[i]))
        a1, a2 = axes2d(ax)
        hit = None
        for i, pl in enumerate(planes):
            if pl['ax'] != ax or (pl['ax'], pl['sg']) not in wall_dirs:
                continue
            if not all(abs(c[ax] - pl['pos']) <= PLANE_M for c in corners_):
                continue
            h0, h1, z0, z1 = pl['box']
            if min(c[a1] for c in corners_) <= h1 + 0.05 and max(c[a1] for c in corners_) >= h0 - 0.05 \
                    and min(c[a2] for c in corners_) <= z1 + 0.05 and max(c[a2] for c in corners_) >= z0 - 0.05:
                hit = i
                break
        if hit is None:
            unplaced += 1
        else:
            kplanes[hit]['faces'].append(([(c[a1], c[a2]) for c in corners_], None))
    print('CONFORM plan start', round(time.perf_counter() - t0, 1), flush=True)
    plans, rounds = wp.conform(kplanes, adj, MAX_CELL, SNAP_M,
                               log=lambda n, d: print('CONFORM round', n, 'dirty', d, round(time.perf_counter() - t0, 1), flush=True))
    print('CONFORM fixpoint', rounds, round(time.perf_counter() - t0, 1), flush=True)
    old = [f for pl in planes for f in pl['faces']]
    old_verts = {v for f in old for v in f.verts}
    made = []
    for i, pl in enumerate(planes):
        made += build_plane(bm, pl, plans[i], uvl, fl, tile_of_finish)
    bmesh.ops.delete(bm, geom=old, context='FACES_ONLY')
    loose = [v for v in old_verts if v.is_valid and not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    by_dir = {}
    for i, pl in enumerate(planes):
        k = f"{'xyz'[pl['ax']]}{'+' if pl['sg'] > 0 else '-'}"
        d = by_dir.setdefault(k, {'planes': 0, 'faces_old': 0, 'faces_new': 0})
        d['planes'] += 1
        d['faces_old'] += len(pl['faces'])
        d['faces_new'] += len(plans[i]['cells'])
    rep['conform'] = {'planes': len(planes), 'adjacent_pairs': len(adj), 'edges_not_axis_aligned': skipped,
                      'conform': rounds, 'contact_unplaced': unplaced, 'by_direction': by_dir,
                      'faces_old': len(old), 'faces_new': len(made),
                      'area_error_m2_max': round(max((abs(v) for p in plans.values()
                                                      for v in p['area_error_m2'].values()), default=0.0), 6)}
    return made


def boundary_edges(bm, posts):
    """Open edges of the body (non-post faces): T-junction / gap witness after the weld."""
    post = set(posts)
    return sum(1 for e in bm.edges if sum(1 for f in e.link_faces if f not in post) == 1
               and all(f not in post for f in e.link_faces))


def _elements(bm):
    """{vertex index: element id} - loose parts (vertices linked by edges)."""
    bm.verts.index_update()
    parent = list(range(len(bm.verts)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        a, b = root(e.verts[0].index), root(e.verts[1].index)
        if a != b:
            parent[a] = b
    return [root(i) for i in range(len(parent))]


def near_pairs(bm, limit):
    """Vertices within `limit` of another vertex OF THE SAME ELEMENT (the element-wise xView vertex rule, [D336]:
    unwelded inset elements may touch inside one delivery object)."""
    elem = _elements(bm)
    verts = list(bm.verts)
    kd = KDTree(len(verts))
    for v in verts:
        kd.insert(v.co, v.index)
    kd.balance()
    near = []
    for v in verts:
        for _co, i, _d in kd.find_range(v.co, limit):
            if i > v.index and elem[i] == elem[v.index]:
                near.append([round(c, 4) for c in v.co])
                break
    return near


def collapse_t_vertices(bm, wall_faces, post_faces, tol=5e-4):
    """A body vertex lying inside a boundary edge of a rebuilt wall (a T-junction against the wall's long edge) is
    welded to the nearer end of that edge: it slides ALONG the shared outline line, so the outline is unchanged and
    only the body's own tessellation edge to it moves (w11). Post vertices never move ([D336]). Returns the count."""
    wall = {f for f in wall_faces if f.is_valid}
    post_v = {v for f in post_faces if f.is_valid for v in f.verts}
    wall_v = {v for f in wall for v in f.verts}
    cand = [v for v in bm.verts if v not in wall_v and v not in post_v]
    kd = KDTree(len(cand))
    for i, v in enumerate(cand):
        kd.insert(v.co, i)
    kd.balance()
    target = {}
    for e in {e for f in wall for e in f.edges}:
        if sum(1 for f in e.link_faces if f in wall) != 1:
            continue
        a, b = e.verts[0].co, e.verts[1].co
        ab = b - a
        ln = ab.length
        if ln < 1e-9:
            continue
        for _co, i, _d in kd.find_range((a + b) / 2, ln / 2 + tol):
            v = cand[i]
            t = (v.co - a).dot(ab) / (ln * ln)
            if not 0 < t < 1 or (a + ab * t - v.co).length > tol or v in target:
                continue
            target[v] = e.verts[0] if t < 0.5 else e.verts[1]
    bmesh.ops.weld_verts(bm, targetmap=target)
    return len(target)


def weld_body(bm, post_faces, dist):
    """Weld the rebuilt walls to the body: every non-post vertex within `dist` of a wall node (or another non-post
    vertex) joins one cluster; the wall node, if any, is the target (it keeps the grid position). Post vertices are
    never touched ([D336]: posts stay separate, unwelded). Returns the number of vertices welded away."""
    post_v = {v for f in post_faces if f.is_valid for v in f.verts}
    verts = [v for v in bm.verts if v not in post_v]
    kd = KDTree(len(verts))
    for i, v in enumerate(verts):
        kd.insert(v.co, i)
    kd.balance()
    target, done = {}, set()
    for i, v in enumerate(verts):
        if i in done:
            continue
        group = [j for _co, j, _d in kd.find_range(v.co, dist) if j not in done]
        if len(group) < 2:
            continue
        keep = min(group, key=lambda j: (verts[j].co - v.co).length)
        for j in group:
            done.add(j)
            if j != keep:
                target[verts[j]] = verts[keep]
    bmesh.ops.weld_verts(bm, targetmap=target)
    return len(target)


def split_bowties(bm, uvl, sep):
    """A body vertex left with two or more face fans (its connecting plane faces went to a wall element) is an xView
    bow-tie. Keep the largest fan on it; every other fan gets its own copy moved `sep` towards that fan's centre (in
    the fan, hidden under the wall embed). Face and loop data are kept. Returns [[x, y, z, fans], ...]."""
    out = []
    for v in list(bm.verts):
        faces = list(v.link_faces)
        if len(faces) < 2:
            continue
        parent = {f: f for f in faces}

        def root(f):
            while parent[f] is not f:
                f = parent[f]
            return f
        for e in v.link_edges:
            lf = list(e.link_faces)
            for f in lf[1:]:
                a, b = root(lf[0]), root(f)
                if a is not b:
                    parent[a] = b
        fans = {}
        for f in faces:
            fans.setdefault(root(f), []).append(f)
        if len(fans) < 2:
            continue
        groups = sorted(fans.values(), key=lambda g: -len(g))
        out.append([round(c, 4) for c in v.co] + [len(groups)])
        for g in groups[1:]:
            centre = sum((f.calc_center_median() for f in g), Vector()) / len(g)
            d = centre - v.co
            if d.length < 1e-9:
                raise ValueError(f'bow-tie fan at {tuple(v.co)} has no direction')
            nv = bm.verts.new(v.co + d.normalized() * sep)
            for f in g:
                uvs = [tuple(lp[uvl].uv) for lp in f.loops]
                nf = bm.faces.new([nv if x is v else x for x in f.verts], f)
                for lay in bm.faces.layers.int.values():
                    nf[lay] = f[lay]
                nf.material_index, nf.smooth = f.material_index, f.smooth
                for lp, uv in zip(nf.loops, uvs):
                    lp[uvl].uv = uv
                bmesh.ops.delete(bm, geom=[f], context='FACES_ONLY')
    return out


def main(master, r1, out_dir):
    master, r1, out_dir = Path(master).resolve(), Path(r1).resolve(), Path(out_dir).resolve()
    if rc.sha(master) != rc.MASTER_V003:
        raise ValueError(f'{master} is not master-quad-v003 {rc.MASTER_V003[:8]}')
    if rc.sha(r1) != rc.qp.R1_V003:
        raise ValueError(f'{r1} is not r1-v003 {rc.qp.R1_V003[:8]}')
    if os.path.lexists(out_dir):
        raise ValueError(f'{out_dir} exists; use a new directory (never overwrite a version)')
    if out_dir in master.parents or out_dir in r1.parents:
        raise ValueError('output directory aliases an input')
    out_blend, out_fbx, report = (out_dir / f'master-quad-{VERSION}.blend', out_dir / f'SM_Kpp_1.quad-{VERSION}.fbx',
                                  out_dir / f'walls-build-{VERSION}.json')
    bpy.ops.wm.open_mainfile(filepath=str(master))
    o = bpy.data.objects['SM_Kpp_1_Main']
    if not all(abs(o.matrix_world[i][j] - (i == j)) < 1e-6 for i in range(4) for j in range(4)):
        raise ValueError('SM_Kpp_1_Main has a non-identity transform')
    posts_r1 = rc.r1_post_tris(r1, rc.CORNERS)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    uvl = bm.loops.layers.uv['UVMap']
    fl = bm.faces.layers.int['finish']
    tile_of_finish = {}
    for f in bm.faces:
        t = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
        if tile_of_finish.setdefault(f[fl], t) != t:
            raise ValueError(f'finish {f[fl]} lies on two UDIM tiles')
    rep = {'version': VERSION, 'issue': 1609, 'blender': bpy.app.version_string,
           'inputs': {'master_v003': {'path': str(master), 'sha256': rc.MASTER_V003},
                      'r1_v003': {'path': str(r1), 'sha256': rc.qp.R1_V003}},
           'decision': 'D357 (Artem 2026-11-20 «по кпп ок», option A): W/S/N walls rebuilt whole by BM-01..03/BM-11, '
                       'posts separate inset elements [D336], continuous UV per finish, NPM atlas rebaked',
           'params': {'embed_m': EMB_M, 'area_min_m2': AREA_MIN, 'snap_m': SNAP_M, 'max_cell_m': MAX_CELL},
           'faces_before': len(bm.faces), 'posts': {}, 'walls': {}, 'synthetic': False}
    plans, contact = {}, []
    for name, corner in rc.CORNERS.items():
        bm.faces.ensure_lookup_table()
        dead = [f for f in bm.faces if rc.in_box(corner, *f.calc_center_median()[:2])
                and not rc.body_side(None, corner, *f.calc_center_median()[:2])]
        rep['posts'][name] = {'post_faces_deleted': len(dead)}
        bmesh.ops.delete(bm, geom=dead, context='FACES')
        plans[name] = rc.plan_posts(corner, posts_r1[name])
        contact += plans[name]['contact']
    # posts first: their faces flush with a facade plane join that plane's grid (one surface, no coplanar overlap)
    post_faces = []
    for name in rc.CORNERS:
        made, info = rc.build_posts(bm, plans[name], {t: f for f, t in tile_of_finish.items()}, uvl, fl)
        rep['posts'][name].update({k: v for k, v in info.items() if k not in ('xs', 'ys', 'zs')})
        post_faces += made
    new_faces, rebuilt, wall_faces = [], [], []
    if CONFORM:
        wall_faces = conform_rebuild(bm, post_faces, contact, uvl, fl, tile_of_finish, rep)
        new_faces += wall_faces
    for name, w in WALLS.items() if not CONFORM else ():
        rep['walls'][name] = []
        for plane, old, area in facade_planes(bm, w):
            made, info = build_wall(bm, name, w, plane, old, contact, uvl, fl, tile_of_finish)
            info['area_m2'] = round(area, 3)
            rep['walls'][name].append(info)
            new_faces += made
            wall_faces += made
            rebuilt.append((w['ax'], w['sg'], plane))
    # the posts' remaining (side) faces end on the rebuilt plane: separate elements, nothing welded or moved (w8)
    post_left = [f for f in post_faces if f.is_valid]
    rep['post_faces_built'] = len(post_faces)
    rep['post_faces_merged_into_walls'] = len(post_faces) - len(post_left)
    new_faces += post_left
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    if BODY_WELD or CONFORM:
        rep['body_vertices_welded'] = weld_body(bm, post_left, WELD_BODY_M)
    if CONFORM:
        rep['open_body_edges'] = boundary_edges(bm, [f for f in post_left if f.is_valid])
    if BODY_WELD and not CONFORM:
        rep['t_vertices_collapsed'] = collapse_t_vertices(bm, wall_faces, post_left)
    rep['bowties_split'] = split_bowties(bm, uvl, BOWTIE_M)
    near = near_pairs(bm, XVIEW_M)
    rep['nodes_near_other_vertex'] = {'count': len(near), 'limit_m': XVIEW_M, 'scope': 'same element [D336]',
                                      'first': near[:20]}
    bm.normal_update()
    degrees = {}
    for f in bm.faces:
        degrees[len(f.verts)] = degrees.get(len(f.verts), 0) + 1
    rep.update({'faces_after': len(bm.faces), 'degrees': degrees, 'loose_vertices_deleted': len(loose)})
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    out_dir.mkdir(parents=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend), copy=True)
    bpy.ops.export_scene.fbx(filepath=str(out_fbx), use_selection=False, object_types={'MESH'},
                             mesh_smooth_type='FACE', use_triangles=False, add_leaf_bones=False,
                             axis_forward='-Z', axis_up='Y', apply_unit_scale=True, bake_space_transform=False)
    rep['outputs'] = {out_blend.name: rc.sha(out_blend), out_fbx.name: rc.sha(out_fbx)}
    report.write_text(json.dumps(rep, indent=1))
    print('WALLS', json.dumps({k: [(i['plane'], i['faces_old'], i['faces_new'], i['gaps_below_3cm'], i['nodes_stuck'])
                                   for i in v] for k, v in rep['walls'].items()}))
    print('NEAR', rep['nodes_near_other_vertex']['count'], rep['nodes_near_other_vertex']['first'][:5])
    print('DEGREES', degrees, 'faces', rep['faces_before'], '->', rep['faces_after'])


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    main(*args[:3])
