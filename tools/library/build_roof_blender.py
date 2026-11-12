"""new-case: hash-pinned roof component extraction into AGR library/1 native review assets.

Not a semantic classifier, finish reconstruction or building delivery. Copies only;
geometry is translated to bottom-center, exact split vertices reunited, source UV
retained and source atlas material replaced with an explicitly neutral local ID 1.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def neutral():
    material = bpy.data.materials.new('matid_1')
    material['agr_material_id'] = 1
    material.diffuse_color = (.42, .57, .68, 1)
    return material


def extract(source, plan):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    result = []
    for row in plan['assets']:
        obj = bpy.data.objects.get(row['source_object'])
        if obj is None or obj.type != 'MESH':
            raise ValueError('unmapped source_object: ' + row['source_object'])
        mesh = obj.data
        if len(mesh.uv_layers) != 1:
            raise ValueError(obj.name + ': expected one measured UV layer')
        if max(row['faces']) >= len(mesh.polygons):
            raise ValueError(row['id'] + ': face outside source')
        polygons = [mesh.polygons[i] for i in row['faces']]
        if any(p.material_index != row['material_slot'] for p in polygons):
            raise ValueError(row['id'] + ': unmapped material slot')
        if sum(len(p.vertices)-2 for p in polygons) != row['triangles']:
            raise ValueError(row['id'] + ': stale triangle measurement')
        # Use linear transform and local coordinate differences before translation.
        # Avoid world-space float32 cancellation on georeferenced deliveries.
        indices = sorted({i for p in polygons for i in p.vertices})
        pts = {i: obj.matrix_world.to_3x3() @ mesh.vertices[i].co for i in indices}
        lo = [min(p[i] for p in pts.values()) for i in range(3)]
        hi = [max(p[i] for p in pts.values()) for i in range(3)]
        anchor = Vector(((lo[0]+hi[0])/2, (lo[1]+hi[1])/2, lo[2]))
        vertices, mapping, byco = [], {}, {}
        for index in indices:
            co = tuple(pts[index]-anchor)
            if not all(math.isfinite(v) for v in co):
                raise ValueError(row['id'] + ': nonfinite vertex')
            if co not in byco:
                byco[co] = len(vertices)
                vertices.append(co)
            mapping[index] = byco[co]
        faces, uvs = [], []
        for p in polygons:
            face = [mapping[i] for i in p.vertices]
            if len(set(face)) != len(face):
                raise ValueError(row['id'] + ': collapsed face after exact reunion')
            faces.append(face)
            values = [tuple(mesh.uv_layers[0].data[i].uv) for i in p.loop_indices]
            if not all(math.isfinite(c) for uv in values for c in uv):
                raise ValueError(row['id'] + ': nonfinite UV')
            uvs.append(values)
        result.append((row, vertices, faces, uvs))
    return result


def save_asset(row, vertices, faces, uvs, profile, root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    name = f'{row["id"]}_{profile}_body'
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(neutral())
    uv = mesh.uv_layers.new(name='SourceAtlasUV')
    for polygon, coords in zip(mesh.polygons, uvs):
        for loop, value in zip(polygon.loop_indices, coords):
            uv.data[loop].uv = value
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    bpy.data.orphans_purge(do_recursive=True)
    path = root/f'assets/{row["id"]}/{profile}.blend'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('existing output: ' + str(path))
    bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
    mesh.calc_loop_triangles()
    size = [max(v.co[i] for v in mesh.vertices)-min(v.co[i] for v in mesh.vertices) for i in range(3)]
    return dict(path=path.relative_to(root).as_posix(), sha256=sha(path),
                triangles=len(mesh.loop_triangles), size_m=size, objects=[name],
                materials=[{'id': 1, 'name': 'matid_1'}])


def label(scene, body, x, y, size=.23):
    data = bpy.data.curves.new('Label', 'FONT')
    data.body, data.size = body, size
    obj = bpy.data.objects.new('Label', data)
    scene.collection.objects.link(obj)
    obj.location = (x, y, 3)


def showcase(assets, root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    rotation = Vector((1, -1.4, 1)).to_track_quat('Z', 'Y').to_matrix().transposed()
    for index, asset in enumerate(assets):
        variant = asset['variants']['vpm']
        with bpy.data.libraries.load(str(root/variant['path']), link=False) as (_, dest):
            dest.objects = variant['objects']
        x, y = (index % 5)*7, -(index//5)*8
        for obj in dest.objects:
            scene.collection.objects.link(obj)
            projected = [rotation@v.co for v in obj.data.vertices]
            lo = [min(p[i] for p in projected) for i in range(3)]
            hi = [max(p[i] for p in projected) for i in range(3)]
            scale = min(5.5/max(hi[0]-lo[0], .001), 4.8/max(hi[1]-lo[1], .001))
            for vertex, point in zip(obj.data.vertices, projected):
                vertex.co = ((point.x-(hi[0]+lo[0])/2)*scale+x+3,
                             (point.y-(hi[1]+lo[1])/2)*scale+y-2,
                             (point.z-(hi[2]+lo[2])/2)*scale)
        label(scene, asset['id']+' '+asset['name'], x, y-5, .22)
        label(scene, ' x '.join(f'{v:.3f}' for v in variant['size_m'])+' m', x, y-5.45, .21)
        label(scene, f'NPM = VPM {variant["triangles"]} tris', x, y-5.85, .21)
    label(scene, 'ROOF EQUIPMENT / #1257 / source-derived form prototypes', 0, 2, .55)
    label(scene, '10 forms from G01 | neutral finish, source UV retained | each card fitted independently, NOT one display scale', 0, 1, .29)
    label(scene, 'Unconfirmed engineering identity / library review only / no atlas, xView or delivery certificate / visual approval pending', 0, -15, .28)
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    camera.location = (17, -6.5, 100)
    camera.data.type, camera.data.ortho_scale = 'ORTHO', 37
    scene.camera = camera
    scene.world = bpy.data.worlds.new('ShowcaseWorld')
    scene.world.color = (.12, .12, .12)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.render.resolution_x, scene.render.resolution_y = 3300, 1800
    scene.render.resolution_percentage = 100
    folder = root/'previews'
    folder.mkdir()
    scene.render.filepath = str(folder/'roof-sheet.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'roof-showcase.blend'), check_existing=False)
    bpy.ops.render.render(write_still=True)
    return dict(path='previews/roof-sheet.png', sha256=sha(folder/'roof-sheet.png'))


def main():
    repo, source, root = [Path(p).resolve() for p in sys.argv[sys.argv.index('--')+1:]]
    if bpy.app.version < (5, 1, 2):
        raise ValueError('Blender 5.1.2+ required')
    if root.exists() or root.is_relative_to(repo) or repo.is_relative_to(root) or source.is_relative_to(root):
        raise ValueError('output must be a new external directory, never an input/ancestor/repository')
    sys.path.insert(0, str(repo/'tools/library'))
    from check_library import load_json
    from roof_parts import validate_plan
    plan_path = repo/'library/roof_equipment/extraction.json'
    plan_hash = sha(plan_path)
    plan = validate_plan(load_json(plan_path))
    if sha(source) != plan['source_sha256']:
        raise ValueError('source sha256 mismatch')
    parts = extract(source, plan)
    root.mkdir(parents=True, exist_ok=False)
    assets = []
    for cell, (row, vertices, faces, uvs) in enumerate(parts, 1):
        variants = {p: save_asset(row, vertices, faces, uvs, p, root) for p in ('npm', 'vpm')}
        assets.append(dict(id=row['id'], name=row['name'], status='ready', confirmation='unconfirmed',
                           source={'component': row['component'], 'object': row['source_object'],
                                   'source_sha256': plan['source_sha256'],
                                   'geometry': 'source-derived component, exact split vertices reunited; bottom-center translation only',
                                   'material': 'local neutral ID 1, NOT recovered customer AGR finish ID; source UV retained, no atlas offered',
                                   'profiles': 'same geometry for both profiles per user decision on t_d0a92d95, 2026-11-12'},
                           reason=[], preview_cell=cell, variants=variants))
    sheet = showcase(assets, root)
    inputs = ['library/roof_equipment/extraction.json', 'tools/library/roof_parts.py', 'tools/library/build_roof_blender.py']
    catalogue = dict(schema='agr-library/1', library='roof_equipment', version='v001', pivot='bottom-center',
                     inputs=[dict(path=p, sha256=sha(repo/p)) for p in inputs], showcase=sheet, assets=assets)
    with (root/'catalogue.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(catalogue, indent=2, allow_nan=False)+'\n')
    if sha(source) != plan['source_sha256'] or sha(plan_path) != plan_hash:
        raise ValueError('input changed during build; discard this candidate version')
    files = sorted(p for p in root.rglob('*') if p.is_file())
    with (root/'SHA256SUMS.txt').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(''.join(f'{sha(p)}  {p.relative_to(root).as_posix()}\n' for p in files))
    print('ROOF_LIBRARY_COMPLETE', len(assets), 'assets', len(assets)*2, 'variants', bpy.app.version_string)


if __name__ == '__main__':
    main()
