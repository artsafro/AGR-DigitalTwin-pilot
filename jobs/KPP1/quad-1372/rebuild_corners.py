"""new-case: KPP1 quad master v004 = v003 with the SW / NW corners rebuilt as separate clean elements (#1609).

Artem 2026-11-16 rejected the v003 corners («сетка ужасная, потому что все одним мешем»); decision the same day:
posts (стойки) are geometry - separate inset elements with clean quads, not welded into the body; panels are
texture with a seam. Run in Blender 5.1 on the v003 master (never written):
    blender -b --factory-startup --python rebuild_corners.py -- <master-quad-v003.blend> <r1-v003 local FBX> <new out dir>

Per corner (`CORNERS`):
1. Posts out of the body: every master face in the corner box whose centre lies outside the body quadrant is
   deleted (the welded/unioned post pieces).
2. Posts back as one separate element: the r1-v003 post triangles of the same box are voxelised on their snapped
   x/y/z planes (`corner_plan.post_cells`) and their boundary quads are added unwelded (`post_faces`); faces lying
   on the body wall and facing into it are hidden contact and are not built (they would overlap the wall). Every
   post quad takes its UV from the coplanar r1 triangle under its centre (exact affine), none -> error.
3. Body walls: on each wall of the corner, repeatedly, the conforming rectangle with the most irregular wall
   area (`corner_plan.conform_rect`: whole faces, posts' hidden contact = don't care, every line ends on a kept
   border vertex, every UV seam a line, no line closer than `MIN_GAP`) is deleted and refilled with its grid;
   every new corner gets the UV of the deleted face under the cell (exact affine, checked at every corner), the
   finish attribute comes from its UDIM tile; border nodes weld to the kept vertex within `WELD_M`. What no
   conforming rectangle can reach stays v003 and is listed in the report (`left_as_v003`, with the reason).
Outputs (new files only): `master-quad-v004.blend`, `SM_Kpp_1.quad-v004.fbx`, `corners-build-v004.json`.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils.kdtree import KDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corner_plan as cp  # noqa: E402
sys.path.insert(0, str(HERE.parents[2] / 'adapters' / 'max' / 'agr_tools'))
from udimtile_core import face_tile  # noqa: E402
sys.path.insert(0, str(HERE / 'provenance-1563' / 'hooks'))
import quad_provenance as qp  # noqa: E402

MASTER_V003 = 'b54c5f72cca60e8cd8cd0401eec7f283ce67d371c1fae6e387d189fae588ab53'  # master-quad-v003.blend (#1563)
VERSION = 'v004'
CORNERS = {  # body = x >= xc and (y >= yc if out_y < 0 else y <= yc); r1-v003 corner of the two walls
    'SW': {'xc': -14.985, 'yc': -5.685, 'out_y': -1},
    'NW': {'xc': -14.985, 'yc': 5.975, 'out_y': 1},
}
BOX_M = 0.35        # corner box half size (posts reach 0.2 m out, #1246 read-back)
OUT_M = 1e-3        # a face centre this far outside the body quadrant belongs to a post
PLANE_M = 6e-4      # wall faces within 0.6 mm of the wall plane (the r1 0.4 mm double layer is the same wall)
S_RANGE = (0.15, 3.5)   # the corner zone: up to 3.5 m from the corner along each wall
Z_RANGE = (0.0, 9.5)    # the whole wall height; conform_rect keeps only whole, conforming rectangles
MAX_RECTS = 60          # per wall and corner; each rectangle replaces irregular faces by a regular grid
MIN_GAP = 0.03          # no grid line closer than 3 cm to another (BM-09: no sliver rows / columns)
WELD_M = 2.1e-3     # = build_quad_master centre clearance: closer vertices are xView Overlapping Vertices
SEAM_UV = 1e-5
UV_AFFINE_TOL = 1e-4   # float32 UVs + the 0.4 mm corner clamp; 1e-4 UV = 0.2 px on a 2048 tile


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def body_side(c, corner, x, y):
    return x >= corner['xc'] - OUT_M and ((y >= corner['yc'] - OUT_M) if corner['out_y'] < 0 else (y <= corner['yc'] + OUT_M))


def in_box(corner, x, y):
    return abs(x - corner['xc']) <= BOX_M and abs(y - corner['yc']) <= BOX_M


def walls(corner):
    """[(name, axis, plane, normal, s_axis, s_sign)] of the two body walls meeting at the corner."""
    xc, yc, oy = corner['xc'], corner['yc'], corner['out_y']
    return [('W', 0, xc, (-1, 0, 0), 1, -oy), ('S' if oy < 0 else 'N', 1, yc, (0, oy, 0), 0, 1)]


def point_in_poly(p, poly, tol=1e-7):
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        # on edge
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        if L2 > 0:
            t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / L2))
            if math.hypot(x1 + t * dx - p[0], y1 + t * dy - p[1]) <= tol:
                return True
        if (y1 > p[1]) != (y2 > p[1]):
            xi = x1 + (p[1] - y1) * dx / dy
            if xi > p[0]:
                inside = not inside
    return inside


def r1_post_tris(r1_path, corners):
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=str(r1_path))
    new = [o for o in bpy.data.objects if o.name not in before]
    mains = [o for o in new if o.type == 'MESH' and o.name.startswith('SM_Kpp_1_Main') and 'Glass' not in o.name]
    if len(mains) != 1:
        raise ValueError(f'r1 import: expected one SM_Kpp_1_Main, got {[o.name for o in mains]}')
    o = mains[0]
    me = o.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    mw = o.matrix_world
    out = {k: [] for k in corners}
    for lt in me.loop_triangles:
        pts = [tuple(mw @ me.vertices[v].co) for v in lt.vertices]
        c = [sum(p[k] for p in pts) / 3 for k in range(3)]
        for name, corner in corners.items():
            if in_box(corner, c[0], c[1]) and not body_side(None, corner, c[0], c[1]):
                out[name].append({'pts': pts, 'uv': [tuple(uv[li].uv) for li in lt.loops],
                                  'normal': tuple((mw.to_3x3() @ lt.normal).normalized())})
    for ob in new:
        bpy.data.objects.remove(ob, do_unlink=True)
    return out


def plan_posts(corner, tris):
    """Voxel plan of the corner posts from the r1 triangles: lines, cells, visible quads, hidden contact quads."""
    # lines = planes of the axis-aligned post triangles (vertices of a long side are triangulation points, not planes)
    xs_raw, ys_raw, zs_raw = ([sum(p[k] for p in t['pts']) / 3 for t in tris if abs(t['normal'][k]) > 0.999]
                              for k in range(3))
    slanted = [t for t in tris if max(abs(c) for c in t['normal']) <= 0.999]
    if slanted:
        raise ValueError(f'{len(slanted)} r1 post triangles are not axis-aligned, e.g. {slanted[0]["pts"]}')
    if not tris:
        raise ValueError('no r1 post triangles in the corner box')
    # UV seams of the r1 posts become lines too, so no post quad straddles two UV islands
    edges = {}
    for t in tris:
        for i in range(3):
            pa, pb = t['pts'][i], t['pts'][(i + 1) % 3]
            ka, kb = tuple(round(c, 5) for c in pa), tuple(round(c, 5) for c in pb)
            edges.setdefault(frozenset((ka, kb)), []).append(({ka: t['uv'][i], kb: t['uv'][(i + 1) % 3]}, t['normal']))
    seams, slanted_seams = 0, []
    for key, uses in edges.items():
        if len(uses) != 2 or len(key) != 2:
            continue
        (u0, n0), (u1, n1) = uses
        if sum(n0[k] * n1[k] for k in range(3)) < 0.999:
            continue                            # an edge between two faces (box edge / coincident contact), no seam
        if all(math.dist(u0[k], u1[k]) <= SEAM_UV for k in key):
            continue
        pa, pb = list(key)
        along = [k for k in range(3) if abs(pa[k] - pb[k]) > 1e-5]
        if len(along) != 1:
            slanted_seams.append([pa, pb])      # cannot be a grid line: those quads take UV per corner (below)
            continue
        for m in range(3):
            if m != along[0]:
                (xs_raw, ys_raw, zs_raw)[m].append(pa[m])
        seams += 1
    xs, _ = cp.snap_values(xs_raw, prefer=[corner['xc']])
    ys, _ = cp.snap_values(ys_raw, prefer=[corner['yc']])
    zs, _ = cp.snap_values(zs_raw)
    gaps = {k: min(b - a for a, b in zip(v, v[1:])) for k, v in (('x', xs), ('y', ys), ('z', zs))}
    if min(gaps.values()) < 3e-3:
        raise ValueError(f'post planes closer than 3 mm after snapping: {gaps}; x {xs} y {ys} z {zs}')
    cells = cp.post_cells([t['pts'] for t in tris], xs, ys, zs, rays=((0, -1), (1, corner['out_y'])),
                          skip=lambda c: c[0] > corner['xc'] and ((c[1] > corner['yc']) if corner['out_y'] < 0
                                                                  else (c[1] < corner['yc'])))
    xc, yc, oy = corner['xc'], corner['yc'], corner['out_y']

    def hidden(c, n):
        on_w = n == (1, 0, 0) and abs(c[0] - xc) < 1e-9 and ((c[1] > yc) if oy < 0 else (c[1] < yc))
        on_s = n == (0, -oy, 0) and abs(c[1] - yc) < 1e-9 and c[0] > xc
        return on_w or on_s
    faces = cp.post_faces(cells, xs, ys, zs, hidden=hidden)
    every = cp.post_faces(cells, xs, ys, zs)
    shown = {tuple(c) for c, _ in faces}
    contact = [(c, n) for c, n in every if tuple(c) not in shown]
    return {'xs': xs, 'ys': ys, 'zs': zs, 'cells': cells, 'faces': faces, 'contact': contact, 'gaps': gaps,
            'seams': seams, 'slanted_seams': slanted_seams, 'tris': tris}


def build_posts(bm, plan, finish_of_tile, uvl, fl):
    """Add the planned post quads as one separate (unwelded) element; UV from the r1 triangle under each."""
    tris, faces = plan['tris'], plan['faces']
    xs, ys, zs, cells, gaps = plan['xs'], plan['ys'], plan['zs'], plan['cells'], plan['gaps']
    seams, slanted_seams = plan['seams'], plan['slanted_seams']
    verts = {}
    made, missing, per_corner = [], [], []
    for corners_, n in faces:
        ax = [abs(v) for v in n].index(1)
        a, b = [k for k in range(3) if k != ax]
        cen = [sum(c[k] for c in corners_) / 4 for k in range(3)]
        def under(q):
            for t in tris:
                tn = t['normal']
                if sum(tn[k] * n[k] for k in range(3)) < 0.999:
                    continue
                if abs(sum(p[ax] for p in t['pts']) / 3 - cen[ax]) > 1e-3:
                    continue
                if point_in_poly((q[a], q[b]), [(p[a], p[b]) for p in t['pts']], 1e-6):
                    return cp.affine_uv([(p[a], p[b]) for p in t['pts']], t['uv'], UV_AFFINE_TOL)
            return None
        f_uv = under(cen)
        if f_uv is None:
            missing.append([round(v, 4) for v in cen] + list(n))
            continue
        bvs = []
        for c in corners_:
            key = tuple(round(v, 6) for v in c)
            if key not in verts:
                verts[key] = bm.verts.new(c)
            bvs.append(verts[key])
        f = bm.faces.new(bvs)
        uvs = [f_uv(c[a], c[b]) for c in corners_]
        try:
            face_tile(uvs)
        except ValueError:
            # the quad straddles a slanted r1 UV seam: each corner takes the triangle just inside it
            per = []
            for c in corners_:
                q = [c[k] + (cen[k] - c[k]) * 0.01 for k in range(3)]
                g = under(q)
                if g is None:
                    raise ValueError(f'post corner {c} lies on no r1 post triangle') from None
                per.append(g(c[a], c[b]))
            uvs = per
            per_corner.append([round(v, 4) for v in cen])
        for loop, u in zip(f.loops, uvs):
            loop[uvl].uv = u
        tile = face_tile(uvs)
        if tile not in finish_of_tile:
            raise ValueError(f'post face at {cen}: UDIM {tile} has no finish in the master')
        f[fl] = finish_of_tile[tile]
        f.material_index = 0
        f.smooth = False
        made.append(f)
    if missing:
        raise ValueError(f'{len(missing)} post quads lie on no r1 post triangle, e.g. {missing[:5]}')
    return made, {'xs': xs, 'ys': ys, 'zs': zs, 'cells': len(cells), 'faces': len(made), 'min_gap_m': gaps, 'r1_uv_seams': seams, 'contact_quads_not_built': len(plan['contact']),
                  'r1_slanted_uv_seams': slanted_seams, 'uv_per_corner_faces': per_corner}


def s_z(wall, co):
    """(s, z) of a point in the wall plane; |s| <= PLANE_M is the corner (the r1 0.4 mm corner offset)."""
    s_ = (co[wall['s_ax']] - wall['s0']) * wall['s_sign']
    return (0.0 if abs(s_) <= PLANE_M else s_, co[2])


def collect(bm, wall, uvl):
    """The wall plane near the corner: wall faces {index: (s, z) poly}, every vertex / edge lying in the plane with
    ALL its faces (any element), and the UV seams between two wall faces."""
    bm.faces.index_update()
    ax, plane, normal = wall['ax'], wall['plane'], wall['normal']
    s_max = S_RANGE[1] + 0.5

    def in_plane(v):
        if abs(v.co[ax] - plane) > PLANE_M:
            return None
        p = s_z(wall, v.co)
        return p if -PLANE_M <= p[0] <= s_max else None
    faces, fobj = {}, {}
    for f in bm.faces:
        if sum(f.normal[k] * normal[k] for k in range(3)) <= 0:   # coplanar by its vertices; slivers have noisy normals
            continue
        pts = [in_plane(v) for v in f.verts]
        if any(p is None for p in pts):
            continue
        faces[f.index] = pts
        fobj[f.index] = f
    items, edges, seams = [], [], []
    for v in bm.verts:
        p = in_plane(v) if v.link_faces else None
        if p is not None:
            items.append((p[0], p[1], frozenset(f.index for f in v.link_faces)))
    for e in bm.edges:
        p, q = in_plane(e.verts[0]), in_plane(e.verts[1])
        if p is None or q is None or not e.link_faces:
            continue
        edges.append((p, q, frozenset(f.index for f in e.link_faces)))
        two = [f for f in e.link_faces if f.index in faces]
        if len(two) == 2:
            jump = max((([lp[uvl].uv for lp in two[0].loops if lp.vert is v][0]
                         - [lp[uvl].uv for lp in two[1].loops if lp.vert is v][0]).length) for v in e.verts)
            if jump > SEAM_UV:
                seams.append((p, q))
    weight = {}       # irregular = not an axis rectangle in (s, z): a triangle, an n-gon or a slanted edge
    for k, pts in faces.items():
        axis = len(pts) == 4 and all(abs(p[0] - q[0]) <= cp.TOL or abs(p[1] - q[1]) <= cp.TOL
                                     for p, q in zip(pts, pts[1:] + pts[:1]))
        weight[k] = 0.0 if axis else cp._area(pts)
    return {'faces': faces, 'fobj': fobj, 'items': items, 'edges': edges, 'seams': seams, 'weight': weight}


def build_rect(bm, wall, r, data, uvl, fl, finish_of_tile, where):
    """Replace the planned rectangle's faces by the grid cols x rows; every new corner takes the UV of the deleted
    face under it (exact affine), checked against the face under every corner; border nodes weld to kept vertices."""
    cols, rows = r['cols'], r['rows']
    srcs = [(data['faces'][k], [tuple(lp[uvl].uv) for lp in data['fobj'][k].loops]) for k in r['faces']]
    maps = {}

    def face_at(q):
        for k, (pts, _) in enumerate(srcs):
            if point_in_poly(q, pts, 1e-7):
                return k
        return None

    def uv_map(k):
        if k not in maps:
            maps[k] = cp.affine_uv(srcs[k][0], srcs[k][1], UV_AFFINE_TOL)
        return maps[k]
    cells, dev = [], 0.0
    for i in range(len(cols) - 1):
        for j in range(len(rows) - 1):
            ring = [(cols[i], rows[j]), (cols[i + 1], rows[j]), (cols[i + 1], rows[j + 1]), (cols[i], rows[j + 1])]
            cen = ((cols[i] + cols[i + 1]) / 2, (rows[j] + rows[j + 1]) / 2)
            samples = [cen] + [(cols[i] + (cols[i + 1] - cols[i]) * a, rows[j] + (rows[j + 1] - rows[j]) * b)
                               for a in (0.25, 0.75, 0.95) for b in (0.25, 0.75)]
            src = next((k for k in map(face_at, samples) if k is not None), None)
            if src is None:
                raise ValueError(f'{where}: cell {ring} lies on no deleted wall face')
            uvs = [uv_map(src)(*c) for c in ring]
            for c, u in zip(ring, uvs):          # the face under each corner (nudged into the cell) agrees
                k = face_at((c[0] + (cen[0] - c[0]) * 0.01, c[1] + (cen[1] - c[1]) * 0.01))
                if k is not None:
                    w = uv_map(k)(*c)
                    dev = max(dev, abs(w[0] - u[0]), abs(w[1] - u[1]))
            cells.append((ring, uvs))
    if dev > UV_AFFINE_TOL:
        raise ValueError(f'{where}: the source UV is not one affine map across a cell (max {dev:.2e})')
    already = len(srcs) == len(cells) and all(len(p) == 4 for p, _ in srcs)
    rep = {'wall': wall['name'], 'S': r['S'], 'z0': r['z0'], 'z1': r['z1'], 'faces_deleted': len(srcs),
           'cols': [round(c, 4) for c in cols], 'rows': [round(z, 4) for z in rows], 'faces_new': len(cells),
           'uv_dev_max': dev, 'unchanged_clean_grid': already}
    if already:
        return rep
    bmesh.ops.delete(bm, geom=[data['fobj'][k] for k in r['faces']], context='FACES')
    vlist = [v for v in bm.verts if v.link_faces]
    kd = KDTree(len(vlist))
    for k, v in enumerate(vlist):
        kd.insert(v.co, k)
    kd.balance()
    nodes, welds = {}, []

    def node(c):
        key = (round(c[0], 6), round(c[1], 6))
        if key in nodes:
            return nodes[key]
        p = [0.0, 0.0, c[1]]
        p[wall['ax']] = wall['plane']
        p[wall['s_ax']] = wall['s0'] + c[0] * wall['s_sign']
        hits = sorted((d, k) for _, k, d in kd.find_range(p, WELD_M))
        if hits:
            v = vlist[hits[0][1]]
            welds.append(hits[0][0])
        else:
            on_border = c[0] in (cols[0], cols[-1]) or c[1] in (rows[0], rows[-1])
            if on_border and kd.find_range(p, 5e-3):
                raise ValueError(f'{where}: border node {c} has a kept vertex 2-5 mm away (would be xView overlap)')
            v = bm.verts.new(p)
        nodes[key] = v
        return v
    for ring, uvs in cells:
        vs = [node(c) for c in ring]
        f = bm.faces.new(vs)
        f.normal_update()
        if sum(f.normal[k] * wall['normal'][k] for k in range(3)) < 0:
            f.normal_flip()
        for loop in f.loops:
            loop[uvl].uv = uvs[vs.index(loop.vert)]
        tile = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
        if tile not in finish_of_tile:
            raise ValueError(f'{where}: UDIM {tile} has no finish in the master')
        f[fl] = finish_of_tile[tile]
        f.material_index = 0
        f.smooth = False
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    rep.update(welded_border_vertices=len(welds), weld_max_m=max(welds, default=0.0))
    return rep


def main(master, r1, out_dir):
    master, r1, out_dir = Path(master).resolve(), Path(r1).resolve(), Path(out_dir).resolve()
    if sha(master) != MASTER_V003:
        raise ValueError(f'{master} is not master-quad-v003 {MASTER_V003[:8]}')
    if sha(r1) != qp.R1_V003:
        raise ValueError(f'{r1} is not r1-v003 {qp.R1_V003[:8]}')
    out_blend, out_fbx, report = (out_dir / f'master-quad-{VERSION}.blend', out_dir / f'SM_Kpp_1.quad-{VERSION}.fbx',
                                  out_dir / f'corners-build-{VERSION}.json')
    if os.path.lexists(out_dir):
        raise ValueError(f'{out_dir} exists; use a new directory (never overwrite a version)')
    if out_dir in master.parents or out_dir in r1.parents or out_dir in (master, r1):
        raise ValueError('output directory aliases an input')
    bpy.ops.wm.open_mainfile(filepath=str(master))
    o = bpy.data.objects['SM_Kpp_1_Main']
    if not all(abs(o.matrix_world[i][j] - (i == j)) < 1e-6 for i in range(4) for j in range(4)):
        raise ValueError('SM_Kpp_1_Main has a non-identity transform (> 1e-6; v003 carries 1.6e-7 FBX round-off, about 2 um at 15 m)')
    posts_r1 = r1_post_tris(r1, CORNERS)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    uvl = bm.loops.layers.uv['UVMap']
    fl = bm.faces.layers.int['finish']
    finish_of_tile = {}
    for f in bm.faces:
        t = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
        if finish_of_tile.setdefault(t, f[fl]) != f[fl]:
            raise ValueError(f'UDIM {t} carries two finishes')
    rep = {'version': VERSION, 'issue': 1609, 'blender': bpy.app.version_string,
           'inputs': {'master_v003': {'path': str(master), 'sha256': MASTER_V003}, 'r1_v003': {'path': str(r1), 'sha256': qp.R1_V003}},
           'decision': 'Artem 2026-11-16: posts are geometry (separate inset elements, clean quads, not welded); panels are '
                       'texture with a seam; windows/roof/flashings inset', 'faces_before': len(bm.faces), 'corners': {},
           'synthetic': False}
    for name, corner in CORNERS.items():
        crep = rep['corners'][name] = {}
        # 1. posts out
        bm.faces.ensure_lookup_table()
        dead = [f for f in bm.faces if in_box(corner, *f.calc_center_median()[:2])
                and not body_side(None, corner, *f.calc_center_median()[:2])]
        crep['post_faces_deleted'] = len(dead)
        crep['post_deleted_bbox'] = [round(min(v.co[k] for f in dead for v in f.verts), 4) for k in range(3)] + \
                                    [round(max(v.co[k] for f in dead for v in f.verts), 4) for k in range(3)] if dead else None
        bmesh.ops.delete(bm, geom=dead, context='FACES')
        pplan = plan_posts(corner, posts_r1[name])
        # 3. body walls: conforming rectangles (corner_plan.conform_rect), one wall after the other, band by band
        for wname, ax, plane, normal, s_ax, s_sign in walls(corner):
            s0 = corner['yc'] if s_ax == 1 else corner['xc']
            wall = {'name': wname, 'ax': ax, 'plane': plane, 'normal': normal, 's_ax': s_ax, 's_sign': s_sign, 's0': s0}
            dontcare = []
            for corners_, n in pplan['contact']:      # the posts' hidden contact: the wall there needs no face
                if abs(n[ax]) == 1 and all(abs(c[ax] - plane) <= PLANE_M for c in corners_):
                    pts = [s_z(wall, c) for c in corners_]
                    dontcare.append((min(p[0] for p in pts), max(p[0] for p in pts),
                                     min(p[1] for p in pts), max(p[1] for p in pts)))
            for _ in range(MAX_RECTS):
                data = collect(bm, wall, uvl)
                try:
                    r = cp.conform_rect(data['faces'], data['items'], data['edges'], *S_RANGE, *Z_RANGE,
                                        dontcare=dontcare, seams=data['seams'], min_gap=MIN_GAP, weight=data['weight'])
                except ValueError as exc:
                    crep.setdefault('left_as_v003', {})[wname] = {
                        'irregular_faces': sum(1 for w in data['weight'].values() if w > 0), 'why': str(exc)}
                    break
                crep.setdefault('wall_rectangles', []).append(build_rect(bm, wall, r, data, uvl, fl, finish_of_tile,
                                                                         f'{name}/{wname}'))
            else:
                raise ValueError(f'{name}/{wname}: more than {MAX_RECTS} rectangles')
        # 2. posts back, a separate unwelded element
        made, info = build_posts(bm, pplan, finish_of_tile, uvl, fl)
        crep['posts'] = info
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    degrees = {}
    for f in bm.faces:
        degrees[len(f.verts)] = degrees.get(len(f.verts), 0) + 1
    rep['faces_after'] = len(bm.faces)
    rep['degrees'] = degrees
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    rep['loose_vertices_deleted'] = len(loose)
    out_dir.mkdir(parents=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend), copy=True)
    bpy.ops.export_scene.fbx(filepath=str(out_fbx), use_selection=False, object_types={'MESH'},
                             mesh_smooth_type='FACE', use_triangles=False, add_leaf_bones=False,
                             axis_forward='-Z', axis_up='Y', apply_unit_scale=True, bake_space_transform=False)
    rep['outputs'] = {out_blend.name: sha(out_blend), out_fbx.name: sha(out_fbx)}
    report.write_text(json.dumps(rep, indent=1))
    print('CORNERS', json.dumps({k: {w: (v if not isinstance(v, dict) else {a: b for a, b in v.items() if a not in ('xs', 'ys', 'zs', 'r1_slanted_uv_seams')})
                                     for w, v in c.items()} for k, c in rep['corners'].items()}))
    print('DEGREES', degrees, 'faces', rep['faces_before'], '->', rep['faces_after'])


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    main(*args[:3])
