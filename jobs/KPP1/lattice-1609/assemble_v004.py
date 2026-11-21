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


def post_plans(path, finish_of_udim, bands):
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
        tris, pfaces = [], []
        xs_raw, ys_raw, zs_raw = [], [], []
        for fi in fids:
            f = src.faces[fi]
            pts = [tuple(v.co) for v in f.verts]
            n = f.normal
            ax = max(range(3), key=lambda k: abs(n[k]))
            if abs(n[ax]) < 0.999:
                raise ValueError(f'{corner}: post face {fi} at {tuple(round(c, 3) for c in f.calc_center_median())} '
                                 f'is not axis-aligned (normal {tuple(round(c, 4) for c in n)})')
            (xs_raw, ys_raw, zs_raw)[ax].append(sum(p[ax] for p in pts) / len(pts))
            for k in range(1, len(pts) - 1):
                tris.append((pts[0], pts[k], pts[k + 1]))
            tile = face_tile([tuple(lp[uvl].uv) for lp in f.loops])
            if tile not in finish_of_udim:
                raise ValueError(f'{corner}: post face {fi} UDIM {tile} has no finish in the v003 tile scheme')
            pfaces.append((f.calc_center_median().copy(), tuple(int(round(n[k])) for k in range(3)), tile))
        x0, y0, x1, y1 = RECT
        xs, _ = cp.snap_values(xs_raw, prefer=[x0, x1])
        ys, _ = cp.snap_values(ys_raw, prefer=[y0, y1])
        zs, _ = cp.snap_values(zs_raw)
        sx, sy = OUT_SIGN[corner]
        cells = cp.post_cells(tris, xs, ys, zs, rays=((0, sx), (1, sy)),
                              skip=lambda c: pp.inside_ring(c, RECT))
        quads = cp.post_faces(cells, xs, ys, zs, hidden=lambda c, n: pp.ring_contact(c, n, RECT))
        out = []
        for corners_, n in quads:
            cen = Vector([sum(c[k] for c in corners_) / 4 for k in range(3)])
            cand = [(p - cen).length for p, pn, t in pfaces if pn == n]
            if not cand:
                raise ValueError(f'{corner}: post quad at {tuple(cen)} normal {n} has no coplanar v003 face')
            best = min(range(len(pfaces)), key=lambda i: (pfaces[i][1] != n, (pfaces[i][0] - cen).length))
            out.append((corners_, n, finish_of_udim[pfaces[best][2]]))
        gaps = {k: round(min((b - a for a, b in zip(v, v[1:])), default=0), 4) for k, v in (('x', xs), ('y', ys), ('z', zs))}
        plans[corner] = out
        rep[corner] = {'source_faces': len(fids), 'bbox': [[round(c, 3) for c in b] for bb in comps['bbox'][corner] for b in bb],
                       'lines': [len(xs), len(ys), len(zs)], 'min_gap_m': gaps, 'cells': len(cells), 'quads': len(out),
                       'finishes': sorted({o[2] for o in out})}
    other = []
    for fs in comps['other']:
        vs = {k for fi in fs for k in faces[fi]}
        other.append({'faces': len(fs), 'lo': [round(min(verts[k][a] for k in vs), 3) for a in range(3)],
                      'hi': [round(max(verts[k][a] for k in vs), 3) for a in range(3)]})
    src.free()
    return plans, rep, other, comps['outside_faces'], scheme_ok


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


def to_object(bm, name, mat):
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
    bpy.context.scene.collection.objects.link(ob)
    return ob


def main(body_fbx, v003_fbx, out, tex_dir, v003_textures):
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
    plans, post_rep, other, outside, scheme = post_plans(v003_fbx, finish_of_udim, bands)
    missing = sorted(set(pp.ring_corners(RECT)) - set(plans))
    mat = vpm_uv.main_material(bpy, spec, tex_dir)
    objs, qa = {}, {}
    nb, q, d = finish_uv(body, names, spec)
    objs['SM_Kpp_1_Main'] = to_object(nb, 'SM_Kpp_1_Main', mat)
    qa['SM_Kpp_1_Main'] = {'uv': q, 'density_px_m': d, 'faces_before_texel_cut': None}
    nb.free()
    for corner, quads in sorted(plans.items()):
        name = f'SM_Kpp_1_Main_Post_{corner}'
        nb, q, d = finish_uv(post_bmesh(quads, names), names, spec)
        objs[name] = to_object(nb, name, mat)
        qa[name] = {'uv': q, 'density_px_m': d}
        nb.free()
    os.makedirs(out)
    rep = {'inputs': {'body_fbx': os.path.abspath(body_fbx), 'body_sha256': sha(body_fbx),
                      'quad_v003_fbx': os.path.abspath(v003_fbx), 'quad_v003_sha256': sha(v003_fbx),
                      'tex_dir': os.path.abspath(tex_dir), 'v003_textures': os.path.abspath(v003_textures),
                      'v003_textures_sha256': sha(v003_textures)},
           'ring': RECT, 'body_finish_faces': body_count, 'posts': post_rep, 'corners_without_post': missing,
           'v003_outside_faces': outside, 'tile_scheme_check_wall_area_m2': scheme, 'other_outside_components': other,
           'objects': {}, 'uv_qa': qa,
           'modelling_split': 'Modelling split [D336]: plinth=body (finish band); inset=corner posts (this step), '
                              'windows/surrounds/portals/roof/annex (package step); texture=cassette panels (UDIM, '
                              'whole-period shift); reason=Artem 2026-11-16/21 (posts geometry, panels texture)'}
    for name, ob in objs.items():
        me = ob.data
        rep['objects'][name] = {'faces': len(me.polygons), 'verts': len(me.vertices),
                                'tris': sum(1 for p in me.polygons if len(p.vertices) == 3),
                                'ngons': sum(1 for p in me.polygons if len(p.vertices) > 4)}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'master-v004-lattice.blend'), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, 'SM_Kpp_1.v004-lattice.fbx'), use_selection=False,
                             mesh_smooth_type='FACE', path_mode='STRIP')
    with open(os.path.join(out, 'assemble.json'), 'x', encoding='utf-8') as fh:
        json.dump(rep, fh, indent=1, default=str)
    print('ASSEMBLE', json.dumps({'objects': rep['objects'], 'missing': missing, 'other': len(other)}))


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    if len(a) != 5:
        raise SystemExit(__doc__)
    main(*a)
