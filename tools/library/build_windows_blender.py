"""new-case: versioned native windows assets and labelled Blender showcase from D204 geometry.

Card #1259 authorizes new outputs only. No customer DCC scene is opened or changed.
This is a library-template build, not an atlas or building delivery.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def material(mid):
    m = bpy.data.materials.get(f'matid_{mid}')
    if m:
        return m
    m = bpy.data.materials.new(f'matid_{mid}')
    m['agr_material_id'] = mid
    m.diffuse_color = {1: (0.12, 0.14, 0.17, 1), 4: (0.18, 0.2, 0.22, 1),
                       5: (0.45, 0.48, 0.5, 1), 10: (0.27, 0.56, 0.76, 1)}[mid]
    return m


def save_variant(asset, profile, mesh, root, wg):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    names, ids = [], set()
    for part in ('frame', 'glass'):
        data = wg.part_mesh(mesh, part)
        if not data['faces']:
            continue
        name = f'{asset["id"]}_{profile}_{part}'
        me = bpy.data.meshes.new(name)
        me.from_pydata(data['verts'], [], data['faces'])
        slots = sorted(set(data['mat_ids']))
        for mid in slots:
            me.materials.append(material(mid))
        for polygon, mid in zip(me.polygons, data['mat_ids']):
            polygon.material_index = slots.index(mid)
        uv = me.uv_layers.new(name='UVMap')
        # Per-face box projection, UV-ready templates only; no claimed atlas/density certificate.
        for polygon in me.polygons:
            axes = sorted(range(3), key=lambda axis: abs(polygon.normal[axis]))[:2]
            for loop in polygon.loop_indices:
                co = me.vertices[me.loops[loop].vertex_index].co
                uv.data[loop].uv = (co[axes[0]], co[axes[1]])
        obj = bpy.data.objects.new(name, me)
        scene.collection.objects.link(obj)
        names.append(name)
        ids.update(slots)
    rel = f'assets/{asset["id"]}/{profile}.blend'
    path = root/rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('refusing existing output: ' + str(path))
    bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
    pts = mesh['verts']
    size = [max(p[i] for p in pts)-min(p[i] for p in pts) for i in range(3)]
    return {'path': rel, 'sha256': sha(path), 'triangles': sum(len(f)-2 for f in mesh['faces']),
            'size_m': size, 'objects': names, 'materials': [{'id': mid, 'name': f'matid_{mid}'} for mid in sorted(ids)]}


def label(text, x, z, color, size=0.16):
    curve = bpy.data.curves.new('label', 'FONT')
    curve.body = text
    curve.size = size
    curve.space_line = 1.15
    obj = bpy.data.objects.new('label', curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (x, -0.4, z)
    obj.rotation_euler = (math.pi/2, 0, 0)
    mat = bpy.data.materials.get(color)
    if mat is None:
        mat = bpy.data.materials.new(color)
        mat.diffuse_color = {'white': (0.86, 0.9, 0.94, 1), 'red': (1, 0.23, 0.16, 1),
                             'amber': (1, 0.72, 0.2, 1)}[color]
    curve.materials.append(mat)


def showcase(assets, root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    cols, cw, ch = 7, 5.6, 5.2
    rows = math.ceil(len(assets)/cols)
    for a in assets:
        index = a['preview_cell']-1
        x, top = (index % cols)*cw, -(index//cols)*ch
        color = 'red' if a['status'] == 'quarantine' else ('white' if a['confirmation'] == 'confirmed' else 'amber')
        label(f'{a["id"]}  {a["source"]["family"]}  {a["confirmation"]}', x, top, color, 0.17)
        # Display original name in two short lines, retaining full name in catalogue.
        name = a['name']
        label(name[:36] + ('\n'+name[36:72] if len(name)>36 else ''), x, top-0.25, color, 0.13)
        if a['status'] != 'ready':
            label('QUARANTINE\nNo generated asset\nSee catalogue reason', x, top-1.6, 'red', 0.22)
            continue
        variant = a['variants']['vpm']
        with bpy.data.libraries.load(str(root/variant['path']), link=False) as (src, dst):
            dst.objects = src.objects
        w, _, h = variant['size_m']
        scale = min(4.8/w, 3.5/h)
        for obj in dst.objects:
            scene.collection.objects.link(obj)
            obj.location = (x+(4.8-w*scale)/2, 0, top-4.3)
            obj.scale = (scale,)*3
        label(f'{w:.3f} x {h:.3f} m | NPM 2 / VPM {variant["triangles"]} tris', x, top-4.65, color, 0.14)
    width, height = cols*cw, rows*ch
    label('WINDOWS LIBRARY / #1259 / D258', 0, 1.5, 'white', 0.42)
    label('D204 geometric VPM templates | NPM plane only, atlas not baked | amber = unconfirmed | red = quarantine', 0, 0.8, 'white', 0.19)
    label('Library cleanliness only. C35 stays open. Not a delivery certificate. User visual approval pending.', 0, -height-0.1, 'amber', 0.22)
    cam = bpy.data.objects.new('ShowcaseCamera', bpy.data.cameras.new('ShowcaseCamera'))
    scene.collection.objects.link(cam)
    cam.location = (width/2-0.3, -80, -height/2+1)
    cam.rotation_euler = (math.pi/2, 0, 0)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = height+5
    scene.camera = cam
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = 'WORLD'
    scene.world = bpy.data.worlds.new('ShowcaseWorld')
    scene.world.color = (0.035, 0.045, 0.06)
    scene.render.resolution_x = 4704
    scene.render.resolution_y = 6400
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    folder = root/'previews'
    folder.mkdir()
    scene.render.filepath = str(folder/'windows-sheet.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'windows-showcase.blend'), check_existing=False)
    bpy.ops.render.render(write_still=True)
    return {'path': 'previews/windows-sheet.png', 'sha256': sha(folder/'windows-sheet.png')}


def main():
    if bpy.app.version < (5, 1, 2):
        raise ValueError('Blender 5.1.2+ required')
    repo, root = map(lambda p: Path(p).resolve(), sys.argv[sys.argv.index('--')+1:])
    if root.exists() or root.is_relative_to(repo) or repo.is_relative_to(root):
        raise ValueError('output must be a new external version directory')
    sys.path.insert(0, str(repo/'tools/library'))
    from migrate_windows import prepare, load_module
    plan = prepare(repo)
    wg = load_module(repo/'adapters/max/agr_tools/windowgen_core.py', 'native_migration_windowgen')
    inputs = ['library/windows/window_types.json', 'library/windows/standard.json', 'library/windows/confirmations.json',
              'library/windows/sources/win-typical-max-sashes-v001.json', 'library/windows/sources/elv-tc-vpm-census-v001.json',
              'adapters/max/agr_tools/windowgen_core.py', 'tools/library/window_sashes.py',
              'tools/library/migrate_windows.py', 'tools/library/build_windows_blender.py']
    rows = [{'path': path, 'sha256': sha(repo/path)} for path in inputs]
    root.mkdir(parents=True, exist_ok=False)
    assets = []
    for asset in plan['assets']:
        meshes = asset.pop('meshes')
        asset['variants'] = {profile: save_variant(asset, profile, mesh, root, wg) for profile, mesh in meshes.items()}
        assets.append(asset)
    sheet = showcase(assets, root)
    if any(sha(repo/row['path']) != row['sha256'] for row in rows):
        raise ValueError('source changed during generation')
    catalogue = {'schema': 'agr-library/1', 'library': 'windows', 'version': 'v001', 'pivot': 'bottom-left',
                 'inputs': rows, 'showcase': sheet, 'assets': assets}
    with (root/'catalogue.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(catalogue, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    files = sorted(p for p in root.rglob('*') if p.is_file())
    with (root/'SHA256SUMS.txt').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(''.join(sha(p)+'  '+p.relative_to(root).as_posix()+'\n' for p in files))
    print('AGR_WINDOWS_MIGRATION', len(assets), 'assets', sum(bool(a['variants']) for a in assets), 'ready', str(root))


if __name__ == '__main__':
    main()
