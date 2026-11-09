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
sys.path.insert(0, str(Path(__file__).resolve().parent))
# flora_tile_uv == #217 remap_uv (tests/test_site_assembly_v015.py); the tool module needs Pillow, Blender has none.
from assembly_rules import remap_rect, flora_tile_uv as remap_uv

# Reviewed source slots of the MAF meshes: v005 set and «Верона» A4.2 rows (#790/#1046). Every loop must lie in its
# source slot; it is then moved affinely into the slot of the site atlas (MAF-09: one 512 set).
MAF_SOURCE_ATLAS = {'v005': 'C:/x/vatutino-maf/v005-set/atlas/vatutino_maf_atlas_512.json',
                    'verona': 'C:/x/vatutino-maf/gen-v001/atlas-v006-2/vatutino_maf_atlas_512_v006p2.json'}
GROUND_UCX = {'v014': 'C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx',
              'v015': 'C:/x/t_e35c49dd/ground-v015-dcc-v001/vpm_ucx/SM_Vatutino_Ground.fbx'}


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


args = sys.argv[sys.argv.index('--') + 1:]
outdir, profile = args[:2]
site = args[2] if len(args) > 2 else 'v014'
out = Path(outdir)
src_dir = out / '_src'  # VPM intermediates; only the numbered maps of the final pass go into the ZIP
src_dir.mkdir(exist_ok=True)
src_rects = {k: {n: m['uv'] for n, m in json.loads(Path(v).read_text())['materials'].items()} for k, v in MAF_SOURCE_ATLAS.items()}
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
    dest = src_dir / 'T_Vatutino_Ground_D_MAF.1001.png'
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
                    if Path(old).parent == src_dir and Path(old).is_file():
                        continue
                    if 'flora-library/' not in old:
                        raise RuntimeError(f'unmapped VPM Flora image {old}')
                    source = Path('C:/x/flora-library') / old.split('flora-library/', 1)[1]
                    if not source.is_file():
                        raise RuntimeError(f'missing source image {source}')
                    kind = 'O' if 'opacity' in source.name else 'D'
                    dest = src_dir / f'T_Vatutino_Ground_{kind}_FloraID{sid}.1001.png'
                    if not dest.exists():
                        dest.write_bytes(source.read_bytes())
                    node.image.filepath = str(dest)
                    node.image.reload()
    elif role == 'maf':
        for p in me.polygons:
            name = me.materials[p.material_index].name
            key = prepare['maf_materials'][name]
            family = 'verona' if lid.startswith('VAT_MAF_T3508') else 'v005'
            for i in p.loop_indices:
                loop = me.uv_layers.active.data[i]
                try:
                    loop.uv = remap_rect(list(loop.uv), src_rects[family][key], maf_rects[key]['uv'])
                except (ValueError, KeyError) as exc:
                    maf_bad.append([ob.name, p.index, key, list(loop.uv), str(exc)])
        me.materials.clear()
        me.materials.append(maf_mat)
        for p in me.polygons:
            p.material_index = 0
    else:
        for index, mat in enumerate(list(me.materials)):
            slot = mat.name.removeprefix('M_Vatutino_Ground_')
            tex = (out / f'T_Vatutino_Ground_D_{slot}.png') if profile == 'npm' else (src_dir / f'T_Vatutino_Ground_D_{slot}.1001.png')
            image = next((n.image for n in (mat.node_tree.nodes if mat.use_nodes else []) if n.type == 'TEX_IMAGE' and n.image
                          and Path(bpy.path.abspath(n.image.filepath)).is_file()), None)
            if image is not None:
                # Ground v015 is delivered textured (#371): keep its reviewed diffuse map, bytes unchanged.
                tex.write_bytes(Path(bpy.path.abspath(image.filepath)).read_bytes())
            else:
                if mat.use_nodes:
                    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                    color = list(bsdf.inputs['Base Color'].default_value)[:3]
                else:
                    color = list(mat.diffuse_color)[:3]
                color = [round(max(0, min(1, c)) ** (1 / 2.2) * 255) for c in color]
                solid_png(tex, color, 2048 if profile == 'npm' else 4096)
            name = mat.name
            mat.name = name + '_source'  # keep the delivered name exact (no '.001' suffix)
            me.materials[index] = material(name, tex)
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
    bpy.ops.import_scene.fbx(filepath=GROUND_UCX[site])
    for ob in set(bpy.data.objects) - before:
        if ob.name.startswith('UCX_'):
            meshes.append(ob)
        else:
            bpy.data.objects.remove(ob, do_unlink=True)
slot_map = []
if profile == 'vpm':
    # V007: VPM maps are T_{Address}_Ground_Diffuse_<n>.1001.png, one numbered slot per material of the one mesh;
    # a Flora opacity map goes into the alpha of its diffuse (RGBA 8 bit, reg p.30).
    import numpy as np
    for n, mat in enumerate(meshes[0].data.materials, start=1):
        nodes = mat.node_tree.nodes
        bsdf = next(x for x in nodes if x.type == 'BSDF_PRINCIPLED')
        def linked(socket):
            return next((l.from_node for l in mat.node_tree.links if l.to_socket == bsdf.inputs[socket] and l.from_node.type == 'TEX_IMAGE'), None)
        diffuse, alpha = linked('Base Color'), linked('Alpha')
        dest = out / f'T_Vatutino_Ground_Diffuse_{n}.1001.png'
        if diffuse is None:
            raise RuntimeError(f'VPM material {mat.name} has no diffuse image: no silent placeholder')
        img = bpy.data.images.load(bpy.path.abspath(diffuse.image.filepath))
        if max(img.size) < 2048:
            # VPM sizes are 2048/4096 (VPM_STANDARD allowed_square_sizes_px); the 512 GroundEl atlas is enlarged x4.
            img.scale(2048, 2048)
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        if alpha is not None:
            a_img = bpy.data.images.load(bpy.path.abspath(alpha.image.filepath))
            if tuple(a_img.size) != (w, h):
                a_img.scale(w, h)
            apx = np.empty(w * h * 4, dtype=np.float32)
            a_img.pixels.foreach_get(apx)
            px[3::4] = apx[0::4]
        out_img = bpy.data.images.new(dest.stem, w, h, alpha=alpha is not None)
        out_img.pixels.foreach_set(px)
        out_img.filepath_raw = str(dest)
        out_img.file_format = 'PNG'
        bpy.context.scene.render.image_settings.color_mode = 'RGBA' if alpha is not None else 'RGB'
        out_img.save()
        diffuse.image = out_img
        if alpha is not None:
            alpha.image = out_img
        # ERM / Normal: flat 256 placeholders (reg p.22, p.31; VPM_STANDARD flat_placeholder), ERM from the
        # material's own Principled values (R emissive 0, G roughness, B metallic), Normal neutral (128, 128, 255).
        rough = float(bsdf.inputs['Roughness'].default_value)
        metal = float(bsdf.inputs['Metallic'].default_value)
        flats = {'ERM': (0.0, rough, metal), 'Normal': (128 / 255, 128 / 255, 1.0)}
        for kind, rgb in flats.items():
            flat = bpy.data.images.new(f'{kind}_{n}', 256, 256, alpha=False)
            flat.pixels.foreach_set(np.tile(np.array([*rgb, 1.0], dtype=np.float32), 256 * 256))
            flat.filepath_raw = str(out / f'T_Vatutino_Ground_{kind}_{n}.1001.png')
            flat.file_format = 'PNG'
            bpy.context.scene.render.image_settings.color_mode = 'RGB'
            flat.save()
        slot_map.append({'slot': n, 'material': mat.name, 'file': dest.name, 'alpha': alpha is not None,
                         'size': [w, h], 'erm_flat': [0, round(rough * 255), round(metal * 255)], 'normal_flat': [128, 128, 255],
                         'source': bpy.path.abspath(img.filepath)})
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes:
    ob.select_set(True)
    if profile == 'npm':
        for mat in ob.data.materials:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    node.image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'assembled.blend'))
# Same unit/axis export as the accepted Ground tool (tools/blender/ground_json_to_fbx.py): metres, Z up.
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
                         apply_scale_options='FBX_SCALE_UNITS', global_scale=1.0, bake_anim=False,
                         use_triangles=True,  # MAF-18 / V003: derived FBX triangulated on export (reg p.8 3.11, p.29 3.17) path_mode='COPY' if profile == 'npm' else 'STRIP', embed_textures=profile == 'npm',
                         axis_forward='Y', axis_up='Z', use_custom_props=True)
(out / 'assembly.json').write_text(json.dumps({'profile': profile, 'triangles': counts, 'maf_uv_outside': len(maf_bad), 'objects': len(meshes), 'blender': bpy.app.version_string, 'site': site, 'vpm_slots': slot_map}, indent=1))
print('ASSEMBLED', profile, counts, 'objects', len(meshes))
