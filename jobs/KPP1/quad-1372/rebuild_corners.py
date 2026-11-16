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
3. Body wall strips: on both walls of the corner the largest rectangle [0, S] x [z0, z1] of whole wall faces
   (`wall_strip`, S in `STRIP_S`) is deleted and refilled with a clean grid (border, every UV seam / finish line,
   even splits <= `STEP_M`); every new corner gets the UV of the deleted face under the cell (exact affine), the
   finish attribute comes from its UDIM tile. Grid border vertices within `WELD_M` of a kept body vertex are
   welded to it; the corner edge is shared by the two strips.
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
STRIP_S = (0.15, 2.0)   # the corner zone: up to 2 m from the corner along each wall
STRIP_Z = (3.9, 8.65)   # the upper storey of both walls at both corners: the r1-v003 floor band line to the wall top
MIN_BAND_M = 0.1        # a leftover z band thinner than this is not searched again
MIN_GAP_M = 0.05        # no grid line closer than 5 cm to another (no sliver rows / columns)
STEP_M = 0.6
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


def seam_lines(faces_sel, s_of, uvl):
    """(s-lines, z-lines, slanted) of every UV-discontinuous edge between two selected faces. An axis seam becomes a
    grid line; a slanted seam cannot be one and is returned (position + UV jump) for the report: the cell under it
    takes the UV of the face under its centre."""
    sel = set(faces_sel)
    s_lines, z_lines, slanted = set(), set(), []
    for f in faces_sel:
        for e in f.edges:
            other = [g for g in e.link_faces if g is not f and g in sel]
            if not other:
                continue
            g = other[0]
            if g.index < f.index:
                continue
            jump = 0.0
            for v in e.verts:
                uf = [l[uvl].uv for l in f.loops if l.vert is v][0]
                ug = [l[uvl].uv for l in g.loops if l.vert is v][0]
                jump = max(jump, (uf - ug).length)
            seam = jump > SEAM_UV
            if seam:
                (s0, z0), (s1, z1) = s_of(e.verts[0]), s_of(e.verts[1])
                if abs(s0 - s1) < 2e-5:
                    s_lines.add(round(s0, 6))
                elif abs(z0 - z1) < 2e-5:
                    z_lines.add(round(z0, 6))
                else:
                    slanted.append([[round(c, 4) for c in e.verts[0].co], [round(c, 4) for c in e.verts[1].co], round(jump, 6)])
    return s_lines, z_lines, slanted


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
    names = o.get('finish_names', '').split(',')
    posts_r1 = r1_post_tris(r1, CORNERS)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    uvl = bm.loops.layers.uv['UVMap']
    fl = bm.faces.layers.int['finish']
    finish_of_tile = {}
    for f in bm.faces:
        t = face_tile([tuple(l[uvl].uv) for l in f.loops])
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
        # 3. wall strips (planned on the body first, so the posts added later are not wall faces)
        strips = []
        for wname, ax, plane, normal, s_ax, s_sign in walls(corner):
            s0 = corner['yc'] if s_ax == 1 else corner['xc']

            def s_of(v, s_ax=s_ax, s_sign=s_sign, s0=s0):
                s_ = (v.co[s_ax] - s0) * s_sign
                return (0.0 if abs(s_) <= PLANE_M else s_, v.co.z)   # the r1 0.4 mm corner offset is the corner
            cand = []
            for f in bm.faces:
                if sum(f.normal[k] * normal[k] for k in range(3)) < 0.9999:
                    continue
                if any(abs(v.co[ax] - plane) > PLANE_M for v in f.verts):
                    continue
                pts = [s_of(v) for v in f.verts]
                if min(p[0] for p in pts) < -2e-5 or min(p[0] for p in pts) > STRIP_S[1] + 0.5:
                    continue
                cand.append((f, pts))
            # the posts' hidden contact quads on this wall: the union of v003 deleted the wall under them
            virtual, skipped_contact = [], []
            for corners_, n in pplan['contact']:
                if abs(n[ax]) == 1 and all(abs(c[ax] - plane) <= PLANE_M for c in corners_):
                    pts = []
                    for c in corners_:
                        s_ = (c[s_ax] - s0) * s_sign
                        pts.append((0.0 if abs(s_) <= PLANE_M else s_, c[2]))
                    s_lo, s_hi = min(p[0] for p in pts), max(p[0] for p in pts)
                    z_lo, z_hi = min(p[1] for p in pts), max(p[1] for p in pts)
                    near = [q for _, q in cand if cp.clip_area(q, s_lo, s_hi, z_lo, z_hi) > 0]
                    cuts = sorted({z_lo, z_hi} | {p[1] for q in near for p in q if z_lo < p[1] < z_hi})
                    for za, zb in zip(cuts, cuts[1:]):       # only where the v003 union left no wall face
                        covered = sum(cp.clip_area(q, s_lo, s_hi, za, zb) for q in near)
                        if covered <= 1e-10:
                            virtual.append([(s_lo, za), (s_hi, za), (s_hi, zb), (s_lo, zb)])
                        elif abs(covered - (s_hi - s_lo) * (zb - za)) > 1e-8:
                            skipped_contact.append([round(v, 4) for v in (s_lo, s_hi, za, zb)])
            polys = [pts for _, pts in cand] + virtual
            crep.setdefault('contact_fill', {})[wname] = {
                'virtual': [[round(v, 4) for v in (q[0][0], q[1][0], q[0][1], q[2][1])] for q in virtual],
                'partly_covered': skipped_contact}
            rects = []
            free = [STRIP_Z]
            while free:
                lo, hi = free.pop()
                try:
                    r = cp.wall_strip([(pts, None) for pts in polys], *STRIP_S, z_min=lo, z_max=hi)
                except ValueError:
                    continue                     # no clean rectangle of whole faces in this band: left as v003
                rects.append(r)
                for a, b in ((lo, r['z0']), (r['z1'], hi)):
                    if b - a >= MIN_BAND_M:
                        free.append((a, b))
            if not rects:
                raise ValueError(f'{name}/{wname}: no clean wall rectangle at the corner')
            for r in sorted(rects, key=lambda r: r['z0']):
                inside = [cand[k] for k in r['faces'] if k < len(cand)]   # virtual contact quads have no face
                s_lines, z_lines, slanted = seam_lines([f for f, _ in inside], s_of, uvl)
                strips.append({'wall': wname, 'ax': ax, 'plane': plane, 'normal': normal, 's_ax': s_ax, 's_sign': s_sign,
                               's0': s0, 'plan': {'S': r['S'], 'z0': r['z0'], 'z1': r['z1']}, 'inside': inside,
                               's_lines': s_lines, 'z_lines': z_lines, 'slanted': slanted})
        borders = {z for st in strips for z in (st['plan']['z0'], st['plan']['z1'])}
        shared = {}
        for st in strips:
            plan = st['plan']
            cols = cp.grid_lines(0.0, plan['S'], st['s_lines'], STEP_M, MIN_GAP_M)
            # the seams of this rectangle, then the other rectangles' borders (corner edge shared) where no sliver
            req = set(st['z_lines'])
            for z in sorted(borders):
                if all(abs(z - q) >= MIN_GAP_M for q in req | {plan['z0'], plan['z1']}):
                    req.add(z)
            rows = cp.grid_lines(plan['z0'], plan['z1'], req, STEP_M, MIN_GAP_M)
            srcs = [(f, pts, [tuple(l[uvl].uv) for l in f.loops]) for f, pts in st['inside']]
            maps = {}
            cells = []
            for i in range(len(cols) - 1):
                for j in range(len(rows) - 1):
                    c = ((cols[i] + cols[i + 1]) / 2, (rows[j] + rows[j + 1]) / 2)
                    src = next((k for k, (_, pts, _) in enumerate(srcs) if point_in_poly(c, pts, 1e-7)), None)
                    if src is None:
                        raise ValueError(f'{name}/{st["wall"]}: cell {c} lies on no deleted wall face')
                    if src not in maps:
                        maps[src] = cp.affine_uv(srcs[src][1], srcs[src][2], UV_AFFINE_TOL)
                    cells.append((i, j, src))
            bmesh.ops.delete(bm, geom=[f for f, _ in st['inside']], context='FACES')
            bm.verts.ensure_lookup_table()
            vlist = [v for v in bm.verts if v.link_faces]
            kd = KDTree(len(vlist))
            for k, v in enumerate(vlist):
                kd.insert(v.co, k)
            kd.balance()
            welds = []
            grid = {}

            def vert(i, j, st=st, cols=cols, rows=rows, kd=kd, grid=grid, welds=welds, vlist=vlist):
                if (i, j) in grid:
                    return grid[(i, j)]
                p = [0.0, 0.0, rows[j]]
                p[st['ax']] = st['plane']
                p[st['s_ax']] = st['s0'] + cols[i] * st['s_sign']
                key = tuple(round(v, 6) for v in p)
                if key in shared:
                    grid[(i, j)] = shared[key]
                    return shared[key]
                border = i in (0, len(cols) - 1) or j in (0, len(rows) - 1)
                v = None
                if border:
                    hits = sorted((d, k) for _, k, d in kd.find_range(p, WELD_M))
                    if hits:
                        v = vlist[hits[0][1]]
                        welds.append(round(hits[0][0], 6))
                if v is None:
                    v = bm.verts.new(p)
                grid[(i, j)] = v
                if i == 0:
                    shared[key] = v
                return v
            new = []
            for i, j, src in cells:
                ring = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                vs = [vert(*r) for r in ring]
                st_pts = [(cols[a], rows[b]) for a, b in ring]
                # orient to the wall normal
                f = bm.faces.new(vs)
                f.normal_update()
                if sum(f.normal[k] * st['normal'][k] for k in range(3)) < 0:
                    f.normal_flip()
                for loop in f.loops:
                    k = vs.index(loop.vert)
                    loop[uvl].uv = maps[src](*st_pts[k])
                uvs = [tuple(l[uvl].uv) for l in f.loops]
                tile = face_tile(uvs)
                if tile not in finish_of_tile:
                    raise ValueError(f'{name}/{st["wall"]}: UDIM {tile} has no finish')
                f[fl] = finish_of_tile[tile]
                f.material_index = 0
                f.smooth = False
                new.append(f)
            crep.setdefault('wall_rectangles', []).append({
                                'wall': st['wall'], 'S': plan['S'], 'z0': plan['z0'], 'z1': plan['z1'],
                                'faces_deleted': len(st['inside']),
                                'cols': [round(c, 4) for c in cols], 'rows': [round(r, 4) for r in rows],
                                'faces_new': len(new), 'welded_border_vertices': len(welds), 'slanted_uv_seams': st['slanted'],
                                'weld_max_m': max(welds, default=0.0)})
        # 2. posts back, a separate unwelded element
        made, info = build_posts(bm, pplan, finish_of_tile, uvl, fl)
        crep['posts'] = info
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    degrees = {}
    worst = 0.0
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
