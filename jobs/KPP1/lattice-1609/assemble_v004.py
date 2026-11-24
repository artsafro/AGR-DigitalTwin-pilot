"""KPP1 lattice step 3 (#1609): accepted lattice body + corner posts as separate inset elements + VPM UV/materials.

Pattern: n/a | new-case: KPP1 v004 draft assembly - the step-2 lattice body (BM-00, accepted 2026-11-21) gets its finish
bands and periodic UDIM UVs from the shared VPM owner (tools/blender/vpm_uv.py), and the four corner posts of quad-v003
are rebuilt as separate voxel elements [D336] (never welded into the body). Blender 5.1, writes OUT_DIR only:

    blender -b --factory-startup --python assemble_v004.py -- BODY.fbx QUAD_V003.fbx OUT_DIR TEX_DIR V003_TEXTURES

1. Body: every face of BODY.fbx (lattice p6) gets the finish of its z band (`posts_plan.finish_of_face`,
   finish_bands.json); then `vpm_uv.texel_cut` (edge-ring splits, no T-junction) + `vpm_uv.pack_uv` (world metres,
   whole-period shift into the finish's UDIM tile).
2. Posts: faces of the quad-v003 Main whose centre lies outside the lattice ring, grouped by shared vertices; the group
   at each ring corner is that corner's post (`posts_plan.outside_components`; the other groups are listed in the
   report for the package step). Each post is voxelised on the snapped planes of its own faces
   (`corner_plan.post_cells`, rays cast outward so the open contact side never counts), voxels inside the ring are
   body; boundary quads are built except the hidden contact on the ring planes (`posts_plan.ring_contact`).
   Finish per post quad = the UDIM tile of the coplanar v003 post face nearest to its centre, read with the tile
   scheme of the v003 UVs (V003_TEXTURES = the R1 set textures.json, 1005 = Frame_RAL9016; NOT materials.json, whose
   1005 is the ladder cage); an unmapped tile or a finish missing from vpm_textures.json is an error.
3. Objects: SM_Kpp_1_Main (body) and SM_Kpp_1_Main_Post_<corner> (separate elements, own vertices); one material
   M_Kpp_1_Main_1 (UDIM Diffuse/ERM/Normal from TEX_DIR, vpm_uv.main_material). Writes master-v004-lattice.blend,
   SM_Kpp_1.v004-lattice.fbx and assemble.json (counts, tiles, overflow, density, posts, other components).
"""
import hashlib
import json
import os
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'quad-1372'))
sys.path.insert(0, str(ROOT / 'tools' / 'blender'))
sys.path.insert(0, str(ROOT / 'adapters' / 'max' / 'agr_tools'))
import posts_plan as pp  # noqa: E402
import corner_plan as cp  # noqa: E402
import vpm_uv  # noqa: E402
from udimtile_core import face_tile  # noqa: E402

RECT = (-14.985, -5.685, 12.675, 5.975)   # lattice ring in the R1 frame (lattice_r1.json rings[0])
NEAR_M = 0.4
GLASS_CAP = 0.24   # lattice opening back face at reveal 0.25 (step 2); glass sits 1 cm in front of it
ELEMENT_SNAP_M = 0.003   # element planes closer than 3 mm are one plane (no 1-2 mm sliver quads, #1609)
GLASS_GAP = 0.01   # glass sits 1 cm in front of the body surface behind it
SEE_M = 0.6   # body faces up to 0.6 m behind the ring plane read the v003 finish at their place (doors/frames 0.3-0.45)
REACH_M = 1.5   # how far behind the ring plane a ray looks for that v003 surface (N entrance vestibule ~1 m deep)
ROOF_Z = 7.85   # v003 roof slab at 7.91, parapet top 8.65: faces inside the ring at or above this are the roof element
KEEP_GAP_M = 0.006   # kept v003 elements stop 6 mm in front of the body: > 2 mm duplicates, > 5 mm co-directional
KEEP_MERGE_M = 0.0021   # > the 2 mm xView / V004 duplicate-vertex tolerance
NICHE_M = 0.15   # a frame reaches back to a body surface at most this deep (0.11 niches; not the 0.25 openings)
OUT_SIGN = {'SW': (-1, -1), 'SE': (1, -1), 'NE': (1, 1), 'NW': (-1, 1)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def import_fbx(path, pick):
    """Import an FBX, return the world-space bmesh of the single mesh object `pick(obj)` accepts and remove every
    imported object again (the scene keeps only what this script builds). Not exactly one match = error."""
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=str(path))
    new = [o for o in bpy.data.objects if o.name not in before]
    hit = [o for o in new if o.type == 'MESH' and pick(o)]
    if len(hit) != 1:
        raise ValueError(f'{path}: expected one matching mesh, got {[o.name for o in hit]}')
    bm = bmesh.new()
    bm.from_mesh(hit[0].data)
    bm.transform(hit[0].matrix_world)
    bm.normal_update()
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    return bm


def body_bmesh(path, names, bands):
    bm = import_fbx(path, lambda o: True)
    fl = bm.faces.layers.int.new('finish')
    count = {}
    for f in bm.faces:
        zs = [v.co.z for v in f.verts]
        fin = pp.finish_of_face(min(zs), max(zs), f.normal.z, bands)
        f[fl] = names.index(fin)
        count[fin] = count.get(fin, 0) + 1
    return bm, count


def check_tile_scheme(src, uvl, finish_of_udim, bands):
    """The v003 tile scheme must agree with the finish bands on the ring walls: per band, the finish with the largest
    area of v003 faces lying on the ring planes (outward, centre >= 5 cm from a band border) is the band's finish
    (or its declared `v003_finish`, finish_bands.json).
    A scheme from another texture set (materials.json: 1005 = ladder cage) fails here instead of mislabelling posts."""
    x0, y0, x1, y1 = RECT
    area = {}
    for f in src.faces:
        c, n = f.calc_center_median(), f.normal
        on = ((abs(c.x - x0) < 1e-3 and n.x < -0.999) or (abs(c.x - x1) < 1e-3 and n.x > 0.999)
              or (abs(c.y - y0) < 1e-3 and n.y < -0.999) or (abs(c.y - y1) < 1e-3 and n.y > 0.999))
        if not on:
            continue
        band = next((bd for bd in bands if bd['z0'] + 0.05 <= c.z <= bd['z1'] - 0.05), None)
        if band is None:
            continue
        tile = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
        key = (band.get('v003_finish', band['finish']), finish_of_udim.get(tile, f'unmapped UDIM {tile}'))
        area[key] = area.get(key, 0.0) + f.calc_area()
    best = {}
    for (band, fin), a in area.items():
        if a > best.get(band, (None, 0.0))[1]:
            best[band] = (fin, a)
    bad = {band: fin for band, (fin, a) in best.items() if fin != band}
    if not best or bad:
        raise ValueError(f'v003 tile scheme disagrees with the finish bands on the ring walls: {bad or "no wall faces"}')
    return {band: round(a, 2) for band, (fin, a) in best.items()}


def voxel_element(src, uvl, fids, rays, finish_of_udim, label, snap=cp.SNAP_M, body_tree=None):
    """Voxel rebuild of one axis-aligned outside component on the snapped planes of its own faces [D336]:
    `corner_plan.post_cells` (rays: outward axis first), voxels inside the ring are body, contact faces on the ring
    planes are not built. Finish per quad = the UDIM tile of the nearest coplanar source face (v003 tile scheme).
    A non-axis face, an unmapped tile or a quad without a coplanar source face is an error naming it."""
    tris, pfaces = [], []
    xs_raw, ys_raw, zs_raw = [], [], []
    for fi in fids:
        f = src.faces[fi]
        pts = [tuple(v.co) for v in f.verts]
        n = f.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        if abs(n[ax]) < 0.999:
            raise ValueError(f'{label}: face {fi} at {tuple(round(c, 3) for c in f.calc_center_median())} '
                             f'is not axis-aligned (normal {tuple(round(c, 4) for c in n)})')
        (xs_raw, ys_raw, zs_raw)[ax].append(sum(p[ax] for p in pts) / len(pts))
        for k in range(1, len(pts) - 1):
            tris.append((pts[0], pts[k], pts[k + 1]))
        tile = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
        if tile not in finish_of_udim:
            raise ValueError(f'{label}: face {fi} UDIM {tile} has no finish in the v003 tile scheme')
        pfaces.append((f.calc_center_median().copy(), tuple(int(round(n[k])) for k in range(3)), tile))
    x0, y0, x1, y1 = RECT
    lo = [min(p[a] for t in tris for p in t) - 1e-3 for a in range(3)]
    hi = [max(p[a] for t in tris for p in t) + 1e-3 for a in range(3)]
    if body_tree is not None:
        # frames reach back to a body surface <= NICHE_M behind them (a ground-floor niche 0.11 deep would leave the
        # frame floating 11 cm in front of the wall): that surface's plane becomes a line of the outward axis
        ax, sg = rays[0]
        plane = {(0, -1): x0, (0, 1): x1, (1, -1): y0, (1, 1): y1}[(ax, sg)]
        a2, b2 = [k for k in range(3) if k != ax]
        d_dir = Vector([0.0, 0.0, 0.0])
        d_dir[ax] = -sg
        for i in range(5):
            for j in range(5):
                o = Vector([0.0, 0.0, 0.0])
                o[ax] = plane + sg * 0.5
                o[a2] = lo[a2] + (hi[a2] - lo[a2]) * (i + 0.5) / 5
                o[b2] = lo[b2] + (hi[b2] - lo[b2]) * (j + 0.5) / 5
                hit = body_tree.ray_cast(o, d_dir, 1.0)
                if hit[2] is not None and 0.002 < hit[3] - 0.5 <= NICHE_M:
                    (xs_raw, ys_raw, zs_raw)[ax].append(hit[0][ax])
        lo[ax] = min(lo[ax], min((xs_raw, ys_raw, zs_raw)[ax]) - 1e-3)
        hi[ax] = max(hi[ax], max((xs_raw, ys_raw, zs_raw)[ax]) + 1e-3)
    xs, _ = cp.snap_values(xs_raw, snap, prefer=[v for v in (x0, x1) if lo[0] <= v <= hi[0]])
    ys, _ = cp.snap_values(ys_raw, snap, prefer=[v for v in (y0, y1) if lo[1] <= v <= hi[1]])
    zs, _ = cp.snap_values(zs_raw, snap)
    if body_tree is None:     # posts: every voxel inside the ring is body
        skip = lambda c: pp.inside_ring(c, RECT)  # noqa: E731
    else:                     # frames: a voxel is body only behind a body surface (outward ray hits the body), so a
        out_dir = Vector([0.0, 0.0, 0.0])        # frame in front of a recessed wall keeps its inner part (no gap)
        out_dir[rays[0][0]] = rays[0][1]
        skip = lambda c: body_tree.ray_cast(Vector(c), out_dir, 2.0)[2] is not None  # noqa: E731
    cells = cp.post_cells(tris, xs, ys, zs, rays=tuple(rays), skip=skip)
    def hidden(c, n):
        """Contact with the body: on the ring plane facing in, or (frames) facing a body surface within 1 mm."""
        if pp.ring_contact(c, n, RECT):
            return True
        if body_tree is None:
            return False
        nv = Vector(n)
        hit = body_tree.ray_cast(Vector(c) - nv * 0.001, nv, 0.002)
        return hit[2] is not None
    quads = cp.post_faces(cells, xs, ys, zs, hidden=hidden)
    out = []
    for corners_, n in quads:
        cen = Vector([sum(c[k] for c in corners_) / 4 for k in range(3)])
        if not any(pn == n for p, pn, t in pfaces):
            raise ValueError(f'{label}: quad at {tuple(cen)} normal {n} has no coplanar v003 face')
        best = min(range(len(pfaces)), key=lambda i: (pfaces[i][1] != n, (pfaces[i][0] - cen).length))
        out.append((corners_, n, finish_of_udim[pfaces[best][2]]))
    gaps = {k: round(min((b - a for a, b in zip(v, v[1:])), default=0), 4) for k, v in (('x', xs), ('y', ys), ('z', zs))}
    return out, {'source_faces': len(fids), 'lines': [len(xs), len(ys), len(zs)], 'min_gap_m': gaps,
                 'cells': len(cells), 'quads': len(out), 'finishes': sorted({o[2] for o in out})}


def keep_element(src, uvl, fids, finish_of_udim, label, side=None):
    """A flat or slanted outside component keeps its v003 faces (quads) as its own element [D336]; finish per face
    from its v003 UDIM tile (unmapped tile = error). With `side`, points inside the ring (or closer than KEEP_GAP_M
    to its plane) move to KEEP_GAP_M in front of it (`posts_plan.clamp_outside`: no piercing of the lattice body);
    a face that collapses there (area < 1e-8 m2, it lay inside the wall) is dropped and counted."""
    out, moved, dropped = [], 0, 0
    for fi in fids:
        f = src.faces[fi]
        tile = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
        if tile not in finish_of_udim:
            raise ValueError(f'{label}: face {fi} UDIM {tile} has no finish in the v003 tile scheme')
        pts = [tuple(v.co) for v in f.verts]
        if side is not None:
            pts, m = pp.clamp_outside(pts, side, RECT, KEEP_GAP_M)
            moved += m
            vs = [Vector(p) for p in pts]
            area = sum(((vs[k] - vs[0]).cross(vs[k + 1] - vs[0])).length for k in range(1, len(vs) - 1)) / 2
            if area < 1e-8 or len({tuple(round(c, 6) for c in p) for p in pts}) < len(pts):
                dropped += 1
                continue
        out.append((pts, tuple(f.normal), finish_of_udim[tile]))
    return out, {'points_moved': moved, 'faces_dropped': dropped}


def post_plans(path, finish_of_udim, bands, with_elements=False, body_tree=None):
    src = import_fbx(path, lambda o: o.name.startswith('SM_Kpp_1_Main') and 'Glass' not in o.name)
    uvl = src.loops.layers.uv.active
    scheme_ok = check_tile_scheme(src, uvl, finish_of_udim, bands)
    src.faces.ensure_lookup_table()
    verts = [tuple(v.co) for v in src.verts]
    src.verts.index_update()
    faces = [[v.index for v in f.verts] for f in src.faces]
    comps = pp.outside_components(verts, faces, RECT, NEAR_M)
    plans, rep = {}, {}
    for corner, fids in sorted(comps['posts'].items()):
        sx, sy = OUT_SIGN[corner]
        out, r = voxel_element(src, uvl, fids, ((0, sx), (1, sy)), finish_of_udim, corner)
        r['bbox'] = [[round(c, 3) for c in b] for bb in comps['bbox'][corner] for b in bb]
        plans[corner], rep[corner] = out, r
    other, elements, count = [], {}, {}
    for fs in comps['other']:
        vs = {k for fi in fs for k in faces[fi]}
        lo = [min(verts[k][a] for k in vs) for a in range(3)]
        hi = [max(verts[k][a] for k in vs) for a in range(3)]
        row = {'faces': len(fs), 'lo': [round(c, 3) for c in lo], 'hi': [round(c, 3) for c in hi]}
        if with_elements:
            area = sum(src.faces[fi].calc_area() for fi in fs)
            slanted = sum(src.faces[fi].calc_area() for fi in fs if max(abs(c) for c in src.faces[fi].normal) < 0.999)
            planes = [len(cp.snap_values([sum(v.co[a] for v in src.faces[fi].verts) / len(src.faces[fi].verts)
                                          for fi in fs if abs(src.faces[fi].normal[a]) >= 0.999] or [0.0])[0])
                      if any(abs(src.faces[fi].normal[a]) >= 0.999 for fi in fs) else 0 for a in range(3)]
            plan = pp.element_plan(lo, hi, area, slanted, RECT, planes=planes)
            key = (plan['kind'], plan['side'])
            count[key] = count.get(key, 0) + 1
            name = f"SM_Kpp_1_Main_{plan['kind']}_{plan['side']}{count[key]:02d}"
            row.update(name=name, area_m2=round(area, 3), slanted_area_m2=round(slanted, 3), method=plan['method'],
                       why=plan['why'], own_planes=planes)
            if plan['method'] == 'voxel':
                out, r = voxel_element(src, uvl, fs, plan['rays'], finish_of_udim, name, ELEMENT_SNAP_M, body_tree)
                row.update(r)
            else:
                out, clamp = keep_element(src, uvl, fs, finish_of_udim, name,
                                          None if plan['why'] == 'flat' else plan['side'])
                row.update(clamp=clamp, quads=sum(1 for o in out if len(o[0]) == 4), finishes=sorted({o[2] for o in out}))
            if not out:
                raise ValueError(f'{name}: rebuild gave no faces ({row})')
            elements[name] = out
        other.append(row)
    if with_elements:
        roof = [f.index for f in src.faces if pp.roof_face(tuple(f.calc_center_median()), RECT, ROOF_Z)]
        if not roof:
            raise ValueError(f'no v003 roof faces inside the ring above z {ROOF_Z}')
        elements['SM_Kpp_1_Main_Roof'], _ = keep_element(src, uvl, roof, finish_of_udim, 'SM_Kpp_1_Main_Roof')
        other.append({'name': 'SM_Kpp_1_Main_Roof', 'faces': len(roof), 'method': 'keep',
                      'why': f'v003 roof inside the ring above z {ROOF_Z} (the lattice body is an open facade tube)',
                      'quads': sum(1 for o in elements['SM_Kpp_1_Main_Roof'] if len(o[0]) == 4),
                      'finishes': sorted({o[2] for o in elements['SM_Kpp_1_Main_Roof']})})
    src.free()
    return plans, rep, other, elements, comps['outside_faces'], scheme_ok


def post_bmesh(quads, names):
    bm = bmesh.new()
    fl = bm.faces.layers.int.new('finish')
    V = {}
    for corners_, n, fin in quads:
        vs = []
        for c in corners_:
            key = tuple(round(v, 6) for v in c)
            if key not in V:
                V[key] = bm.verts.new(c)
            vs.append(V[key])
        f = bm.faces.new(vs)
        f.normal_update()
        if f.normal.dot(Vector(n)) < 0:
            f.normal_flip()
        f[fl] = names.index(fin)
    bm.normal_update()
    return bm


def finish_uv(bm, names, spec):
    nb = vpm_uv.texel_cut(bm, names, spec)
    qa = vpm_uv.pack_uv(nb, names, spec)
    dens = vpm_uv.density_qa(nb, names, spec)
    return nb, qa, dens


def to_object(bm, name, mat, names):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    me.materials.append(mat)
    for p in me.polygons:
        p.material_index = 0
        p.use_smooth = False
    if 'UVM' in me.uv_layers:
        me.uv_layers.remove(me.uv_layers['UVM'])
    me.uv_layers.active = me.uv_layers['UVMap']
    ob = bpy.data.objects.new(name, me)
    ob['finish_names'] = ','.join(names)   # face attribute 'finish' index -> name (export_npm reads it)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def carry_v003(path, report, body_tree):
    """Glass and UCX hulls of quad-v003 stay (own objects, own materials). A glass component lying inside the ring
    deeper than its cap moves outward along its side's normal (`posts_plan.glass_shift`): cap = GLASS_CAP (opening back
    face at reveal 0.25) or GLASS_GAP in front of the nearest body surface seen behind it (rays from outside at the
    face centres and corners; `posts_plan.glass_target`), so no glass hides behind the lattice body; where the body is
    a solid wall (the N screen glazing, not in the body per the line list) the pane goes GLASS_GAP in front of the wall;
    glass reaching outside the ring stays and is listed."""
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=str(path))
    new = [o for o in bpy.data.objects if o.name not in before]
    keep = {}
    for o in new:
        base = o.name.split('.')[0]
        if o.type == 'MESH' and (base == 'SM_Kpp_1_MainGlass' or base.startswith('UCX_SM_Kpp_1_Main_')):
            keep[base] = o
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    if 'SM_Kpp_1_MainGlass' not in keep or not any(k.startswith('UCX_') for k in keep):
        raise ValueError(f'{path}: glass or UCX hulls missing: {sorted(keep)}')
    for base, o in keep.items():
        o.name = base
    g = keep['SM_Kpp_1_MainGlass']
    bm = bmesh.new()
    bm.from_mesh(g.data)
    bm.transform(g.matrix_world)
    bm.normal_update()
    x0, y0, x1, y1 = RECT
    moved, kept = [], []
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        comp, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for nf in e.link_faces:
                    if nf.index not in seen:
                        seen.add(nf.index)
                        stack.append(nf)
        sides = {}
        depths = []
        for f in comp:
            c = f.calc_center_median()
            d = {'W': c.x - x0, 'E': x1 - c.x, 'S': c.y - y0, 'N': y1 - c.y}
            s = min(d, key=d.get)
            depths.append(d[s])
            sides[s] = sides.get(s, 0.0) + f.calc_area()
        lo = [round(min(v.co[a] for f in comp for v in f.verts), 3) for a in range(3)]
        if min(depths) < 0:
            kept.append({'faces': len(comp), 'lo': lo, 'why': 'reaches outside the ring'})
            continue
        side = max(sides, key=sides.get)
        nv = Vector({'W': (-1, 0, 0), 'E': (1, 0, 0), 'S': (0, -1, 0), 'N': (0, 1, 0)}[side])
        plane = {'W': x0, 'E': x1, 'S': y0, 'N': y1}[side]
        ax = 0 if side in 'WE' else 1
        behind = []
        for f in comp:
            for p in [f.calc_center_median()] + [v.co.lerp(f.calc_center_median(), 0.1) for v in f.verts]:
                o = p.copy()
                o[ax] = plane + nv[ax] * 0.5
                loc, _, idx, dist = body_tree.ray_cast(o, -nv, 0.5 + SEE_M)
                if idx is not None:
                    behind.append(dist - 0.5)
        shift, how = pp.glass_target(depths, behind, GLASS_CAP, GLASS_GAP)
        if shift:
            vec = nv * shift
            for v in {v for f in comp for v in f.verts}:
                v.co += vec
        moved.append({'faces': len(comp), 'lo': lo, 'side': side, 'shift_m': round(shift, 4), 'mode': how,
                      'depth_m': [round(min(depths), 4), round(max(depths), 4)]})
    bm.transform(g.matrix_world.inverted())
    bm.to_mesh(g.data)
    bm.free()
    report['glass'] = {'cap_m': GLASS_CAP, 'components': moved, 'outside_ring': kept,
                       'shifted': sum(1 for m in moved if m['shift_m'])}
    report['ucx'] = sorted(k for k in keep if k.startswith('UCX_'))
    return keep


def opening_finishes(body, v003_fbx, finish_of_udim, names, bands, report):
    """Outward vertical faces of the lattice body (on the ring plane or up to 0.6 m behind it: walls, opening back
    faces) and up-facing faces (roof, sills; rays downward from 2 mm above the face) take a NON-band finish of the v003 surfaces at their place (door leaves, the N screen, frames, grilles):
    `posts_plan.majority_finish` over a 5 x 5 sample grid, rays from 2 mm in front of the face's ring plane inward up
    to REACH_M; a band finish seen (any cassette/plinth, incl. the v003 7047 top) votes for the face's own band, so the
    band scheme [D376] is never overwritten by v003 cassettes; nothing seen = the band finish stays."""
    band_fins = {b['finish'] for b in bands} | {b['v003_finish'] for b in bands if b.get('v003_finish')}
    src = import_fbx(v003_fbx, lambda o: o.name.startswith('SM_Kpp_1_Main') and 'Glass' not in o.name)
    uvl = src.loops.layers.uv.active
    src.faces.ensure_lookup_table()
    fin = {}
    keep = []
    for f in src.faces:
        if not pp.outside_ring(f.calc_center_median(), RECT, tol=0.002):
            tile = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
            if tile not in finish_of_udim:
                raise ValueError(f'v003 face {f.index} UDIM {tile} has no finish in the v003 tile scheme')
            fin[len(keep)] = finish_of_udim[tile]
            keep.append([v.index for v in f.verts])
    src.verts.ensure_lookup_table()
    tree = BVHTree.FromPolygons([tuple(v.co) for v in src.verts], keep)
    src.free()
    fl = body.faces.layers.int['finish']
    x0, y0, x1, y1 = RECT
    changed, seen = {}, 0
    for f in body.faces:
        n, c = f.normal, f.calc_center_median()
        side = ('W' if n.x < -0.999 else 'E' if n.x > 0.999 else 'S' if n.y < -0.999 else 'N' if n.y > 0.999
                else 'up' if n.z > 0.999 else None)
        if side is None:
            continue
        depth = {'W': c.x - x0, 'E': x1 - c.x, 'S': c.y - y0, 'N': y1 - c.y, 'up': 0.0}[side]
        if not -0.002 <= depth <= SEE_M or len(f.verts) != 4:
            continue
        seen += 1
        a, b, cc, d = [v.co for v in f.verts]
        hits = []
        for i in range(5):
            for j in range(5):
                u, w = (i + 0.5) / 5, (j + 0.5) / 5
                p = a.lerp(b, u).lerp(d.lerp(cc, u), w)
                o = p + n * (depth + 0.002)
                loc, _, idx, dist = tree.ray_cast(o, -n, REACH_M)
                hits.append(fin[idx] if idx is not None else None)
        band = names[f[fl]]
        hits = [band if h in band_fins else h for h in hits]
        new, share = pp.majority_finish(hits, band)
        if new != band:
            f[fl] = names.index(new)
            key = f'{band} -> {new}'
            changed[key] = changed.get(key, 0) + 1
    report['opening_finish'] = {'faces_seen': seen, 'changed': changed, 'see_m': SEE_M, 'reach_m': REACH_M}


def delivery_master(objs, out):
    """Delivery copy of the element master (package step): the regulation objects are SM_<A>_Main, SM_<A>_MainGlass
    and UCX hulls (export_vpm / export_npm take exactly one *_Main), so every separate element is joined into
    SM_Kpp_1_Main as its own LOOSE part - objects joined, no vertex merged [D336]; per-part face counts are kept in
    the report and a loose-part count below the element count is an error (something got welded)."""
    main = objs['SM_Kpp_1_Main']
    parts = [o for n, o in objs.items() if n != 'SM_Kpp_1_Main']
    def islands(me):
        bm = bmesh.new()
        bm.from_mesh(me)
        seen, n = set(), 0
        for f0 in bm.faces:
            if f0.index in seen:
                continue
            n += 1
            stack = [f0]
            seen.add(f0.index)
            while stack:
                f = stack.pop()
                for v in f.verts:
                    for nf in v.link_faces:
                        if nf.index not in seen:
                            seen.add(nf.index)
                            stack.append(nf)
        bm.free()
        return n
    want = sum(islands(o.data) for o in [main] + parts)
    faces = {o.name: len(o.data.polygons) for o in [main] + parts}
    with bpy.context.temp_override(active_object=main, selected_editable_objects=[main] + parts):
        bpy.ops.object.join()
    got = islands(main.data)
    if got != want or len(main.data.polygons) != sum(faces.values()):
        raise ValueError(f'join changed the parts: islands {want} -> {got}, faces {sum(faces.values())} -> '
                         f'{len(main.data.polygons)}')
    path = os.path.join(out, 'master-v004-delivery.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    return {'file': 'master-v004-delivery.blend', 'joined_into': 'SM_Kpp_1_Main', 'parts_faces': faces,
            'loose_parts': got, 'objects': sorted(o.name for o in bpy.context.scene.objects)}


def main(body_fbx, v003_fbx, out, tex_dir, v003_textures, mode='posts'):
    if mode not in ('posts', 'package'):
        raise SystemExit(f'unknown mode {mode!r}: posts | package')
    with_elements = mode == 'package'
    if os.path.exists(out):
        raise SystemExit('refused: OUT_DIR exists')
    for p in (body_fbx, v003_fbx):
        if os.path.abspath(p).startswith(os.path.abspath(out)):
            raise SystemExit('refused: an input lies inside OUT_DIR')
    spec = vpm_uv.load_spec(str(HERE.parent / 'scripts' / 'vpm_textures.json'))
    names = list(spec['finishes'])
    bands = json.loads((HERE / 'finish_bands.json').read_text(encoding='utf-8'))['bands']
    r1 = json.loads(Path(v003_textures).read_text(encoding='utf-8'))['finishes']
    finish_of_udim = {v['udim']: k for k, v in r1.items()}
    if len(finish_of_udim) != len(r1):
        raise SystemExit(f'{v003_textures}: two finishes share one UDIM')
    unknown = sorted(set(finish_of_udim.values()) - set(names))
    if unknown:
        raise SystemExit(f'{v003_textures}: finishes {unknown} are not in vpm_textures.json')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    body, body_count = body_bmesh(body_fbx, names, bands)
    plans, post_rep, other, elements, outside, scheme = post_plans(v003_fbx, finish_of_udim, bands, with_elements,
                                                                    BVHTree.FromBMesh(body))
    missing = sorted(set(pp.ring_corners(RECT)) - set(plans))
    mat = vpm_uv.main_material(bpy, spec, tex_dir)
    objs, qa = {}, {}
    carry_rep = {}
    if with_elements:
        opening_finishes(body, v003_fbx, finish_of_udim, names, bands, carry_rep)
    nb, q, d = finish_uv(body, names, spec)
    objs['SM_Kpp_1_Main'] = to_object(nb, 'SM_Kpp_1_Main', mat, names)
    qa['SM_Kpp_1_Main'] = {'uv': q, 'density_px_m': d, 'faces_before_texel_cut': None}
    nb.free()
    parts = [(f'SM_Kpp_1_Main_Post_{corner}', quads) for corner, quads in sorted(plans.items())]
    for name, quads in parts + sorted(elements.items()):
        bm = post_bmesh(quads, names)
        merged = None
        if any(r.get('name') == name and r.get('clamp', {}).get('points_moved') for r in other):
            # clamped kept element: points that met on the clamp plane closer than the xView vertex threshold (2 mm)
            # are one point of this element (its own topology, never welded to the body)
            nv = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=KEEP_MERGE_M)
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-6)
            merged = {'verts_merged': nv - len(bm.verts), 'tris': sum(1 for f in bm.faces if len(f.verts) == 3)}
        nb, q, d = finish_uv(bm, names, spec)
        objs[name] = to_object(nb, name, mat, names)
        qa[name] = {'uv': q, 'density_px_m': d, 'clamp_merge': merged}
        nb.free()
    carried = {}
    if with_elements:
        dg = bpy.context.evaluated_depsgraph_get()
        carried = carry_v003(v003_fbx, carry_rep, BVHTree.FromObject(objs['SM_Kpp_1_Main'], dg))
    os.makedirs(out)
    rep = {'inputs': {'body_fbx': os.path.abspath(body_fbx), 'body_sha256': sha(body_fbx),
                      'quad_v003_fbx': os.path.abspath(v003_fbx), 'quad_v003_sha256': sha(v003_fbx),
                      'tex_dir': os.path.abspath(tex_dir), 'v003_textures': os.path.abspath(v003_textures),
                      'v003_textures_sha256': sha(v003_textures)},
           'ring': RECT, 'body_finish_faces': body_count, 'posts': post_rep, 'corners_without_post': missing,
           'v003_outside_faces': outside, 'tile_scheme_check_wall_area_m2': scheme, 'other_outside_components': other,
           'objects': {}, 'uv_qa': qa, 'mode': mode, **carry_rep,
           'modelling_split': 'Modelling split [D336]: plinth=body (finish band); inset=corner posts, window frames, '
                              'portals and the E annex as separate elements (frames/annex voxel-rebuilt, slanted '
                              'portals keep their v003 quads); texture=cassette panels (UDIM, whole-period shift); '
                              'reason=Artem 2026-11-16/21/24 (posts geometry, panels texture)'}
    for name, ob in list(objs.items()) + sorted(carried.items()):
        me = ob.data
        rep['objects'][name] = {'faces': len(me.polygons), 'verts': len(me.vertices),
                                'tris': sum(1 for p in me.polygons if len(p.vertices) == 3),
                                'ngons': sum(1 for p in me.polygons if len(p.vertices) > 4)}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'master-v004-lattice.blend'), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, 'SM_Kpp_1.v004-lattice.fbx'), use_selection=False,
                             mesh_smooth_type='FACE', path_mode='STRIP')
    if with_elements:
        rep['delivery_master'] = delivery_master(objs, out)
    with open(os.path.join(out, 'assemble.json'), 'x', encoding='utf-8') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('ASSEMBLE', json.dumps({'objects': rep['objects'], 'missing': missing, 'other': len(other)}))


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    if len(a) not in (5, 6):
        raise SystemExit(__doc__)
    main(*a)
