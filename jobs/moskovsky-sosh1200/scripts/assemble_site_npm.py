"""moskovsky-sosh1200 stage 10: job-local NPM site assembly (Ground + GroundEl + Flora -> one Ground FBX).

new-case: modelled on jobs/VATUTINO-SITE/assemble_delivery.py (NPM branch). No geometry edits: inputs are the
accepted Ground v002 geometry (v003 IDs/textures, cut by GPZU) + markings, MAF v002 (geometry accepted) and Flora v002.
Changes made here, all recorded in assembly.json:
  * names to the NPM grammar (reg 2.10.3.3-5): SM_<A>_Ground / _GroundEl / _GroundElGlass / _Flora,
    M_<A>_<suffix>_<slot>, T_<A>_<suffix>_d_<slot>.png, glass M_Glass_01 (untextured, opacity 0.5);
  * Ground UDIM 1001..1010 -> per-slot 0..1 UVs (integer U shift per cover; identical under texture repeat);
  * MAF: every opaque material uses the one 512 atlas -> one material M_<A>_GroundEl_1 (reg 2.5.12);
  * frame: local -> MSK-77 XY (local + origin), shared pivot at an integer MSK point, Z unchanged
    (Z 0 = +-0.000; the absolute Baltic mark is unknown -> stays open, reg 2.8.2 / 4.1.4).

blender -b --factory-startup --python-exit-code 1 --python assemble_site_npm.py -- CONFIG.json
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

cfg = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
A = cfg['address']
out = Path(cfg['out'])
pkg = out / 'package'
tex = out / '_tex'
fbx = pkg / f"{cfg['code']}_{A}_Ground.fbx"
for p in (fbx, out / 'assembly.json', out / 'assembled.blend'):
    if p.exists():
        raise RuntimeError(f'existing output {p}')
pkg.mkdir(parents=True, exist_ok=True)
tex.mkdir(parents=True, exist_ok=True)
origin = Vector((cfg['origin_xy_msk77'][0], cfg['origin_xy_msk77'][1], 0.0))
pivot = Vector(cfg['pivot_msk77'])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_new(src, dest):
    dest = Path(dest)
    if dest.exists():
        raise RuntimeError(f'existing output {dest}')
    shutil.copyfile(src, dest)
    return dest


def image(path):
    """Load with the datablock name = PNG file name (reg 2.10.3.4); an imported namesake is renamed *_src."""
    name = Path(path).name
    if name in bpy.data.images:
        bpy.data.images[name].name = name + '_src'
    img = bpy.data.images.load(str(path))
    img.name = name
    if img.name != name:
        raise RuntimeError(f'image name taken: {name}')
    return img


def material(name, diffuse=None, opacity=None, alpha=None):
    if name in bpy.data.materials:
        raise RuntimeError(f'material name taken: {name}')
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    if diffuse:
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = image(diffuse)
        tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    if opacity:
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = image(opacity)
        node.image.colorspace_settings.name = 'Non-Color'
        tree.links.new(node.outputs['Color'], bsdf.inputs['Alpha'])
    if alpha is not None:
        bsdf.inputs['Alpha'].default_value = alpha
        bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    return mat


MIRRORED = []


def bake(ob):
    if ob.data.users > 1:
        ob.data = ob.data.copy()
    mirrored = ob.matrix_world.determinant() < 0
    ob.data.transform(ob.matrix_world)
    if mirrored:  # a mirrored instance renders with reversed winding; keep that facing after the bake
        ob.data.flip_normals()
        MIRRORED.append(ob.name)
    ob.parent = None
    ob.matrix_world = Matrix.Identity(4)


def join(objects, name):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bounds(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return [[min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]]


bpy.ops.wm.read_factory_settings(use_empty=True)
report = {'config': cfg, 'blender': bpy.app.version_string, 'inputs': {}, 'local_bounds': {}, 'changes': []}

# ---- Ground surface + markings (OBJ, Z up, local frame) ------------------------------------------------------
ground_objs = []
for key in ('ground_obj', 'markings_obj'):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=cfg[key], forward_axis='Y', up_axis='Z')
    new = [o for o in set(bpy.data.objects) - before if o.type == 'MESH']
    report['inputs'][key] = {'path': cfg[key], 'sha256': sha(cfg[key]), 'objects': [o.name for o in new]}
    ground_objs += new
slot_of = {name: i + 1 for i, name in enumerate(cfg['ground_slots'])}  # source material -> slot (UDIM order)
ground_mats = {}
for name, slot in slot_of.items():
    src = Path(cfg['ground_textures'][name])
    dest = copy_new(src, tex / f'T_{A}_Ground_d_{slot}.png')
    ground_mats[name] = (slot, dest, sha(src))
uv_bad = 0
for ob in ground_objs:
    bake(ob)
    me = ob.data
    names = [m.name.split('.')[0] for m in me.materials]
    unknown = sorted(set(names) - set(slot_of))
    if unknown:
        raise RuntimeError(f'Ground material without slot: {unknown}')
    uv = me.uv_layers.active.data
    for p in me.polygons:
        slot = slot_of[names[p.material_index]]
        for li in p.loop_indices:
            u, v = uv[li].uv
            u -= slot - 1
            if not (-1e-6 <= u <= 1 + 1e-6 and -1e-6 <= v <= 1 + 1e-6):
                uv_bad += 1
            uv[li].uv = (u, v)
report['changes'].append('Ground UDIM -> per-slot 0..1 (U shift by slot-1); loops outside 0..1 after shift: %d' % uv_bad)
if uv_bad:
    raise RuntimeError(f'{uv_bad} Ground UV loops outside their tile')
for ob in ground_objs:
    for i, m in enumerate(ob.data.materials):
        base = m.name.split('.')[0]
        slot, dest, _ = ground_mats[base]
        mname = f'M_{A}_Ground_{slot}'
        ob.data.materials[i] = bpy.data.materials.get(mname) or material(mname, dest)
report['ground_slots'] = {n: {'slot': s, 'texture': d.name, 'source_sha256': h} for n, (s, d, h) in ground_mats.items()}

# ---- MAF (FBX, instanced objects) ----------------------------------------------------------------------------
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=cfg['maf_fbx'])
maf = [o for o in set(bpy.data.objects) - before]
report['inputs']['maf_fbx'] = {'path': cfg['maf_fbx'], 'sha256': sha(cfg['maf_fbx']), 'objects': len(maf)}
for o in [o for o in maf if o.type != 'MESH']:
    bpy.data.objects.remove(o, do_unlink=True)
maf = [o for o in maf if o.name in bpy.data.objects and o.type == 'MESH']
glass = [o for o in maf if '_GroundElGlass' in o.name]
opaque = [o for o in maf if o not in glass]
nomap = {}
for o in opaque:
    for p in o.data.polygons:
        m = o.data.materials[p.material_index]
        has = m and m.use_nodes and any(n.type == 'TEX_IMAGE' and n.image for n in m.node_tree.nodes)
        if not has:
            nomap[m.name if m else None] = nomap.get(m.name if m else None, 0) + 1
report['maf_opaque_faces_without_atlas'] = nomap
if nomap:
    raise RuntimeError(f'MAF opaque faces without the atlas map: {nomap}')
atlas = copy_new(cfg['maf_atlas'], tex / f'T_{A}_GroundEl_d_1.png')
m_el = material(f'M_{A}_GroundEl_1', atlas)
m_glass = material('M_Glass_01', alpha=0.5)
for group, mat in ((opaque, m_el), (glass, m_glass)):
    for o in group:
        bake(o)
        o.data.materials.clear()
        o.data.materials.append(mat)
        for p in o.data.polygons:
            p.material_index = 0
report['changes'].append(f'MAF: {len(opaque)} opaque instances -> M_{A}_GroundEl_1 (atlas sha {sha(cfg["maf_atlas"])}); '
                         f'{len(glass)} glass instances -> M_Glass_01 (opacity 0.5, no maps)')

# ---- Flora (FBX, one mesh, atlas d/o) -------------------------------------------------------------------------
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=cfg['flora_fbx'])
flora = [o for o in set(bpy.data.objects) - before if o.type == 'MESH']
report['inputs']['flora_fbx'] = {'path': cfg['flora_fbx'], 'sha256': sha(cfg['flora_fbx']), 'objects': len(flora)}
d = copy_new(cfg['flora_d'], tex / f'T_{A}_Flora_d_1.png')
o_ = copy_new(cfg['flora_o'], tex / f'T_{A}_Flora_o_1.png')
for o in flora:
    bake(o)
    old = [m.name for m in o.data.materials]
    for m in list(o.data.materials):
        m.name = m.name + '_src'
    o.data.materials.clear()
    o.data.materials.append(material(f'M_{A}_Flora_1', d, o_))
    for p in o.data.polygons:
        p.material_index = 0
report['changes'].append(f'Flora: materials {old} -> M_{A}_Flora_1 (d/o from {cfg["flora_d"]}, {cfg["flora_o"]})')

# ---- join, frame, pivot -----------------------------------------------------------------------------------------
meshes = {'Ground': join(ground_objs, f'SM_{A}_Ground'), 'GroundEl': join(opaque, f'SM_{A}_GroundEl'),
          'Flora': join(flora, f'SM_{A}_Flora')}
if glass:
    meshes['GroundElGlass'] = join(glass, f'SM_{A}_GroundElGlass')
shift = origin - pivot
for key, ob in meshes.items():
    report['local_bounds'][key] = bounds(ob)
    ob.data.transform(Matrix.Translation(shift))
    ob.location = pivot
report['changes'].append(f'frame: vertices += origin - pivot = {list(shift)}; object location = pivot {list(pivot)} (MSK-77 XY, Z = +-0.000)')
report['mirrored_instances_flipped'] = MIRRORED
counts = {k: tris(o) for k, o in meshes.items()}
report['triangles'] = counts
report['triangles_total'] = sum(counts.values())
report['budget'] = cfg['budget']
report['msk_bounds'] = {k: bounds(o) for k, o in meshes.items()}
all_b = list(report['msk_bounds'].values())
report['msk_bounds_all'] = [[min(b[0][i] for b in all_b) for i in range(3)], [max(b[1][i] for b in all_b) for i in range(3)]]
report['materials'] = {k: [m.name for m in o.data.materials] for k, o in meshes.items()}
for ob in bpy.data.objects:
    if ob not in meshes.values():
        bpy.data.objects.remove(ob, do_unlink=True)
import re
bad = [x.name for x in list(bpy.data.materials) + list(bpy.data.images) + [o for o in meshes.values()]
       if re.search(r'\.[0-9]{3}$', x.name) and not x.name.endswith('_src')
       and (x in meshes.values() or any(x in (ob.data.materials[:]) for ob in meshes.values())
            or any(n.type == 'TEX_IMAGE' and n.image == x for ob in meshes.values() for m in ob.data.materials
                   for n in m.node_tree.nodes))]
if bad:
    raise RuntimeError(f'.NNN suffix on delivered names: {bad}')
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'assembled.blend'))
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes.values():
    ob.select_set(True)
# Same unit/axis export as the accepted Ground tool and the Vatutino site NPM (tools/blender/ground_json_to_fbx.py).
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
                         apply_scale_options='FBX_SCALE_UNITS', global_scale=1.0, bake_anim=False,
                         use_triangles=True, path_mode='COPY', embed_textures=True,
                         axis_forward='Y', axis_up='Z', use_custom_props=False)
report['fbx'] = {'path': str(fbx), 'sha256': sha(fbx), 'bytes': fbx.stat().st_size}
(out / 'assembly.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
print('ASSEMBLED', counts, report['triangles_total'])
