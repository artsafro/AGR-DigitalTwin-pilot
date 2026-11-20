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
EMB_M = 3e-3         # outline nodes reach 3 mm past the old outline (hides the joint), never welded
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
    shifts0, stuck, clamped = wp.embed_shifts(cells, H, Z, EMB_M)
    shifts = wp.relax_shifts(cells, H, Z, shifts0, XVIEW_M)
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
    new_faces, rebuilt = [], []
    for name, w in WALLS.items():
        rep['walls'][name] = []
        for plane, old, area in facade_planes(bm, w):
            made, info = build_wall(bm, name, w, plane, old, contact, uvl, fl, tile_of_finish)
            info['area_m2'] = round(area, 3)
            rep['walls'][name].append(info)
            new_faces += made
            rebuilt.append((w['ax'], w['sg'], plane))
    # the posts' remaining (side) faces end on the rebuilt plane: separate elements, nothing welded or moved (w8)
    post_left = [f for f in post_faces if f.is_valid]
    rep['post_faces_built'] = len(post_faces)
    rep['post_faces_merged_into_walls'] = len(post_faces) - len(post_left)
    new_faces += post_left
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
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
