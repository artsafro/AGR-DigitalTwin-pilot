"""#298 job-local package assembly on prepared copies; new-case: site profile assembly.

Existing MAF UVs are preserved and checked against the regenerated #313 atlas.
Flora uses the reviewed #217 affine UV map; no geometry repair is performed.
"""
import json
import re
import sys
import struct
import zlib
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.library.flora_atlas_from_scene import remap_uv


def solid_png(path, color, size):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    row = b'\0' + bytes(color) * size
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(row * size)) + chunk(b'IEND', b''))


def material(name, diffuse, opacity=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node = tree.nodes.new('ShaderNodeTexImage')
    node.image = bpy.data.images.load(str(diffuse), check_existing=True)
    tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    if opacity:
        alpha = tree.nodes.new('ShaderNodeTexImage')
        alpha.image = bpy.data.images.load(str(opacity), check_existing=True)
        alpha.image.colorspace_settings.name = 'Non-Color'
        tree.links.new(alpha.outputs['Color'], bsdf.inputs['Alpha'])
    return mat


def join(objects, name):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    ob = bpy.context.object
    # Bake every transform into mesh coordinates, then share the original world origin.
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    ob.name = name
    return ob


outdir, profile = sys.argv[sys.argv.index('--') + 1:]
out = Path(outdir)
fbx = out / 'SM_Vatutino_Ground.fbx'
if fbx.exists():
    raise RuntimeError(f'existing output {fbx}')
bpy.ops.wm.open_mainfile(filepath=str(out / 'prepared.blend'))
atlas_dir = out.parent / 'atlas'
flora_report = json.loads((atlas_dir / 'flora-atlas.json').read_text())
tiles = {r['material_id']: r['uv'] for r in flora_report['ids']}
maf_rects = json.loads((atlas_dir / 'maf-uv.json').read_text())['materials']
prepare = json.loads((out / 'prepare.json').read_text())
flora_materials = {}
for sid in tiles:
    suffix = 'Flora' if profile == 'npm' else 'Ground'
    flora_materials[sid] = material(f'M_Vatutino_{suffix}_ID{sid}', Path(flora_report['material']['diffuse']), Path(flora_report['material']['opacity']))
maf_texture = atlas_dir / 'T_Vatutino_GroundEl_D_1.png'
if profile == 'vpm':
    dest = out / 'T_Vatutino_Ground_D_MAF.1001.png'
    if dest.exists():
        raise RuntimeError(f'existing output {dest}')
    dest.write_bytes(maf_texture.read_bytes())
    maf_texture = dest
maf_mat = material('M_Vatutino_GroundEl_1' if profile == 'npm' else 'M_Vatutino_Ground_MAF', maf_texture)
roles = {'surface': [], 'maf': [], 'flora': []}
seen = set()
maf_bad = []
for ob in list(bpy.data.objects):
    if ob.type != 'MESH' or (not ob.get('library_id') and not ob.name.startswith('SM_Vatutino_Ground')):
        bpy.data.objects.remove(ob, do_unlink=True)
        continue
    lid = ob.get('library_id')
    role = 'surface' if not lid else ('maf' if lid.startswith('VAT_MAF_') else 'flora')
    roles[role].append(ob)
    me = ob.data
    if me.as_pointer() in seen:
        continue
    seen.add(me.as_pointer())
    if role == 'flora':
        sid = me.attributes['species_id'].data[0].value
        if profile == 'npm':
            for uv in me.uv_layers.active.data:
                uv.uv = remap_uv(list(uv.uv), tiles[sid])
            me.materials.clear()
            me.materials.append(flora_materials[sid])
            for p in me.polygons:
                p.material_index = 0
        else:
            # FLO-08 atlas is NPM only. VPM keeps the source UVs/materials;
            # #369 texture defects remain visible, never silently normalize UVs.
            for mat in me.materials:
                for node in mat.node_tree.nodes:
                    if node.type != 'TEX_IMAGE' or not node.image:
                        continue
                    old = node.image.filepath.replace('\\', '/')
                    if Path(old).parent == out and Path(old).is_file():
                        continue
                    if 'flora-library/' not in old:
                        raise RuntimeError(f'unmapped VPM Flora image {old}')
                    source = Path('C:/x/flora-library') / old.split('flora-library/', 1)[1]
                    if not source.is_file():
                        raise RuntimeError(f'missing source image {source}')
                    kind = 'O' if 'opacity' in source.name else 'D'
                    dest = out / f'T_Vatutino_Ground_{kind}_FloraID{sid}.1001.png'
                    if not dest.exists():
                        dest.write_bytes(source.read_bytes())
                    node.image.filepath = str(dest)
                    node.image.reload()
    elif role == 'maf':
        for p in me.polygons:
            name = me.materials[p.material_index].name
            key = prepare['maf_materials'][name]
            u0, v0, u1, v1 = maf_rects[key]['uv']
            for i in p.loop_indices:
                u, v = me.uv_layers.active.data[i].uv
                if not (u0 - 1e-6 <= u <= u1 + 1e-6 and v0 - 1e-6 <= v <= v1 + 1e-6):
                    maf_bad.append([ob.name, p.index, key, u, v])
        me.materials.clear()
        me.materials.append(maf_mat)
        for p in me.polygons:
            p.material_index = 0
    else:
        for index, mat in enumerate(list(me.materials)):
            slot = mat.name.removeprefix('M_Vatutino_Ground_')
            if mat.use_nodes:
                bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                color = list(bsdf.inputs['Base Color'].default_value)[:3]
            else:
                color = list(mat.diffuse_color)[:3]
            color = [round(max(0, min(1, c)) ** (1 / 2.2) * 255) for c in color]
            tex = out / (f'T_Vatutino_Ground_D_{slot}.png' if profile == 'npm' else f'T_Vatutino_Ground_D_{slot}.1001.png')
            solid_png(tex, color, 2048 if profile == 'npm' else 4096)
            me.materials[index] = material(mat.name, tex)
if maf_bad:
    (out / 'maf-uv-failed.json').write_text(json.dumps(maf_bad))
    raise RuntimeError(f'{len(maf_bad)} MAF UV loops outside their reviewed slot')
counts = {}
for role, objects in roles.items():
    counts[role] = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objects)
if profile == 'npm' and sum(counts.values()) > 180000:
    raise RuntimeError(f'NPM over budget {counts}')
meshes = [join(roles['surface'], 'SM_Vatutino_Ground'), join(roles['maf'], 'SM_Vatutino_GroundEl'), join(roles['flora'], 'SM_Vatutino_Flora')]
if profile == 'vpm':
    meshes = [join(meshes, 'SM_Vatutino_Ground')]
    # Preserve reviewed v014 Ground UCX; never rebuild it from the placed vegetation scene.
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath='C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx')
    for ob in set(bpy.data.objects) - before:
        if ob.name.startswith('UCX_'):
            meshes.append(ob)
        else:
            bpy.data.objects.remove(ob, do_unlink=True)
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes:
    ob.select_set(True)
    if profile == 'npm':
        for mat in ob.data.materials:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    node.image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'assembled.blend'))
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
                         bake_anim=False, path_mode='COPY' if profile == 'npm' else 'STRIP', embed_textures=profile == 'npm',
                         axis_forward='-Y', axis_up='Z', use_custom_props=True)
(out / 'assembly.json').write_text(json.dumps({'profile': profile, 'triangles': counts, 'maf_uv_outside': len(maf_bad), 'objects': len(meshes), 'blender': bpy.app.version_string}, indent=1))
print('ASSEMBLED', profile, counts, 'objects', len(meshes))
