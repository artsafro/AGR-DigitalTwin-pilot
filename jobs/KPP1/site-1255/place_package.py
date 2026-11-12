"""new-case: KPP1 approved approximate R1 placement [D260], not a survey solution.

Run in private headless Blender: --python place_package.py -- SOURCE_DIR NEW_OUTPUT_DIR.
VPM bakes only the approved plan rotation; NPM also bakes translation and absolute zero.
Inputs stay immutable. Output directory is exclusively created; reruns require a new version.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NOTE = ('approximate, ±0.1 m, fitted to customer NPM 0607_77_05_0009005_117_02; '
        'entrance orientation not independently confirmed')


def transform_point(point, fit, profile):
    if profile not in ('npm', 'vpm'):
        raise ValueError('unsupported profile: ' + str(profile))
    values = [*point, fit['theta_deg'], *fit['origin_msk_blender_xy'], fit['zero_abs']]
    if len(point) != 3 or len(fit['origin_msk_blender_xy']) != 2 or not all(math.isfinite(v) for v in values):
        raise ValueError('finite XYZ and placement required')
    a = math.radians(fit['theta_deg'])
    x, y, z = point
    x, y = math.cos(a)*x - math.sin(a)*y, math.sin(a)*x + math.cos(a)*y
    if profile == 'npm':
        x += fit['origin_msk_blender_xy'][0]
        y += fit['origin_msk_blender_xy'][1]
        z += fit['zero_abs']
    return [x, y, z]


def prepare(src, out, fit):
    import hashlib
    required = ['SM_Kpp_1.fbx', '0000_Kpp_1_01.fbx', 'SM_Kpp_1.zip']
    if not src.is_dir() or out.resolve().is_relative_to(src.resolve()):
        raise ValueError('source directory missing or output aliases source')
    if out.exists():
        raise ValueError('output already exists: ' + str(out))
    # This is an approved job transform, not a general placement API.
    approved = [-6.053044176714781, 8056.143933445407, -9581.26989822931, 171.05]
    actual = [fit['theta_deg'], *fit['origin_msk_blender_xy'], fit['zero_abs']]
    if actual != approved:
        raise ValueError('placement is not the approved best fit [D260]')
    transform_point([0, 0, 0], fit, 'npm')
    hashes = {}
    for name in required:
        p = src / name
        if not p.is_file():
            raise ValueError('missing input: ' + name)
        hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    expected = {
        'SM_Kpp_1.fbx': '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676',
        '0000_Kpp_1_01.fbx': '9604a8f14f064495a8ccbbf17d21cdd1445825f6a9fc3ca215531327ada812bd',
        'SM_Kpp_1.zip': '7479908fb68dd7fd95dad84c858605cfbf23c6c4fad306384a8082c15dac8fff',
    }
    if hashes != expected:
        raise ValueError('source hashes differ from R1 v002: ' + repr(hashes))
    return hashes


if __name__ == '__main__':
    src, out = map(Path, sys.argv[sys.argv.index('--')+1:])
    fit = json.loads((HERE / 'fit-npm-r1-v002.json').read_text())
    hashes = prepare(src, out, fit)
    required = ['SM_Kpp_1.fbx', '0000_Kpp_1_01.fbx', 'SM_Kpp_1.zip']
    import bpy
    from mathutils import Matrix
    out.mkdir()  # exclusive: pre-existing directory is never used
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    reports = []
    for profile, name in [('vpm', required[0]), ('npm', required[1])]:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = 1.0
        bpy.ops.import_scene.fbx(filepath=str((src / name).resolve()))
        objects = list(bpy.context.scene.objects)
        if not objects or any(o.type != 'MESH' for o in objects):
            raise RuntimeError('empty or unsupported non-mesh FBX')
        entry = {'profile': profile, 'file': name, 'objects': [], 'glasses': []}
        angle = math.radians(fit['theta_deg'])
        rotation = Matrix.Rotation(angle, 4, 'Z')
        origin = transform_point([0, 0, 0], fit, profile)
        for ob in objects:
            # Bake orientation into mesh, preserve UVs/material IDs and object names.
            world = ob.matrix_world.copy()
            ob.data.transform(rotation @ world)
            ob.matrix_world = Matrix.Translation(origin)
            entry['objects'].append({'name': ob.name, 'vertices': len(ob.data.vertices),
                                     'faces': len(ob.data.polygons), 'pivot': list(ob.location)})
        if profile == 'vpm':
            from importlib.util import spec_from_file_location, module_from_spec
            spec = spec_from_file_location('package_core', ROOT / 'adapters/max/agr_tools/package_core.py')
            core = module_from_spec(spec)
            spec.loader.exec_module(core)
            mats = {s.material.name: s.material for o in objects for s in o.material_slots
                    if s.material and 'MainGlass' in s.material.name}
            for name_mat, mat in mats.items():
                bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if mat.use_nodes else None
                rgb = list(bsdf.inputs['Base Color'].default_value[:3]) if bsdf else list(mat.diffuse_color[:3])
                srgb = lambda c: round(255 * (12.92*c if c <= .0031308 else 1.055*c**(1/2.4)-.055))
                entry['glasses'].append({'name': name_mat, 'diffuse': [srgb(c) for c in rgb],
                                         'opacity': 100*(bsdf.inputs['Alpha'].default_value if bsdf else mat.diffuse_color[3]),
                                         'ior': bsdf.inputs['IOR'].default_value if bsdf else 1.5,
                                         'glossiness': 100*(1-(bsdf.inputs['Roughness'].default_value if bsdf else mat.roughness))})
            # Customer TEC26 xlsx, column Central checkpoint. Repeated whole-project areas
            # are NOT asserted to be this building's areas; unknowns stay empty and fail V011.
            props = dict(address='проезд Востряковский, вл. 10', okrug='ЮАО', rajon='Бирюлево-Западное',
                         name='Центральная проходная', developer="ООО 'Развитие генерации ТЭЦ-26'",
                         designer="ООО 'Аспект'", cadNum='77:05:0009005:117', FNO_code='', FNO_name='',
                         ZU_area=6.4882, h_relief=171.05, h_otn=8.65, h_abs=179.70,
                         s_obsh='', s_naz='', s_podz='', spp_gns='', act_AGR='', other=NOTE + ' [D260]')
            data = core.geojson_document(props, '',
                                         [round(v, 3) for v in fit['origin_msk_blender_xy']],
                                         core.glasses_entry(entry['glasses']), False)
            (out / 'SM_Kpp_1.geojson').write_bytes(data)
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.export_scene.fbx(filepath=str((out / name).resolve()), use_selection=True,
                                 object_types={'MESH'}, axis_forward='-Z', axis_up='Y',
                                 apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                                 bake_anim=False, use_triangles=True, mesh_smooth_type='FACE',
                                 path_mode='COPY' if profile == 'npm' else 'STRIP',
                                 embed_textures=profile == 'npm', add_leaf_bones=False)
        if profile == 'vpm':
            import base64
            from mathutils import Vector
            # Real output model thumbnail, not a fabricated preview or customer photograph.
            for ob in objects:
                if ob.name.startswith('UCX_'):
                    ob.hide_render = True
            bpy.ops.object.camera_add(location=(37, -42, 27))
            camera = bpy.context.object
            camera.rotation_euler = (Vector((0, 0, 4)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = 42
            scene = bpy.context.scene
            scene.camera = camera
            bpy.ops.object.light_add(type='SUN', location=(10, -10, 20))
            bpy.context.object.data.energy = 3
            bpy.context.object.rotation_euler = (.4, -.4, -.3)
            if scene.world is None:
                scene.world = bpy.data.worlds.new('Site1255PreviewWorld')
            scene.world.color = (.3, .3, .3)
            scene.render.engine = 'CYCLES'
            scene.cycles.samples = 16
            scene.render.resolution_x = scene.render.resolution_y = 256
            scene.render.resolution_percentage = 100
            scene.render.image_settings.file_format = 'JPEG'
            scene.render.filepath = str((out / 'thumbnail_256.jpg').resolve())
            bpy.ops.render.render(write_still=True)
            doc = json.loads(data)
            doc['features'][0]['properties']['imageBase64'] = base64.b64encode((out / 'thumbnail_256.jpg').read_bytes()).decode('ascii')
            (out / 'SM_Kpp_1.geojson').write_text(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        reports.append(entry)
    import hashlib
    import zipfile
    if any(hashlib.sha256((src / n).read_bytes()).hexdigest() != h for n, h in hashes.items()):
        raise RuntimeError('input changed during placement; no completion receipt')
    with zipfile.ZipFile(src / 'SM_Kpp_1.zip') as original:
        names = original.namelist()
        if len(names) != len(set(names)) or any(n != 'SM_Kpp_1.fbx' and not (n.startswith('T_Kpp_1_') and n.endswith('.png') and '/' not in n and '\\' not in n) for n in names):
            raise RuntimeError('unsupported/duplicate source ZIP member')
        with zipfile.ZipFile(out / 'SM_Kpp_1.zip', 'x', zipfile.ZIP_DEFLATED) as package:
            for n in names:
                package.writestr(n, (out / n).read_bytes() if n == 'SM_Kpp_1.fbx' else original.read(n))
            package.write(out / 'SM_Kpp_1.geojson', 'SM_Kpp_1.geojson')
    # No Ground invented: the single-building NPM ZIP intentionally fails V001 composition.
    with zipfile.ZipFile(out / '0000_Kpp_1.zip', 'x', zipfile.ZIP_DEFLATED) as package:
        package.write(out / '0000_Kpp_1_01.fbx', '0000_Kpp_1_01.fbx')
    (out / 'placement-export.json').write_text(json.dumps({'decision': 'D260', 'placement': NOTE,
        'source_sha256': hashes, 'blender': bpy.app.version_string,
        'zero_abs_m': 171.05, 'fit': fit, 'exports': reports, 'passed': False}, ensure_ascii=False, indent=2), encoding='utf-8')
