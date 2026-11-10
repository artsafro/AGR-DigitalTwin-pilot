"""#298 clean ZIP-FBX evidence: fixed-camera normals, material IDs and VP sections.

new-case: job-local quantitative D125 evidence. Renders are not human acceptance.
"""
import colorsys
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

fbx, output, adapter_file, offset_file = sys.argv[sys.argv.index('--') + 1:]
out = Path(output)
if out.exists():
    raise RuntimeError(f'new output directory required: {out}')
out.mkdir(parents=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=fbx)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.startswith('UCX_')]
for o in bpy.context.scene.objects:
    if o.name.startswith('UCX_'):
        o.hide_render = True
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.resolution_x = 768
scene.render.resolution_y = 768
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = True
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1

surface = [o for o in meshes if o.name == 'SM_Vatutino_Ground']
# Reconstruct a ray-castable Ground-only surface using the delivered material role,
# not the working Ground. VPM places all render roles into one mesh.
vs, fs = [], []
areas = {}
ground_polygons = []
for ob in surface:
    me = ob.data
    me.calc_loop_triangles()
    start = len(vs)
    vs.extend([ob.matrix_world @ v.co for v in me.vertices])
    for tri in me.loop_triangles:
        mat = me.materials[tri.material_index]
        name = mat.name if mat else ''
        ground_slot = name.startswith('M_Vatutino_Ground_') and 'ID' not in name and 'MAF' not in name
        if not ground_slot:
            continue
        points = [vs[start + i] for i in tri.vertices]
        normal = (points[1] - points[0]).cross(points[2] - points[0])
        if normal.z <= 0:
            continue
        fs.append([start + i for i in tri.vertices])
        areas[name] = areas.get(name, 0.0) + normal.z / 2
        ground_polygons.append([name, [[p.x, p.y] for p in points]])
bvh = BVHTree.FromPolygons(vs, fs, all_triangles=True)
low = Vector(tuple(min(v[i] for v in vs) for i in range(3)))
high = Vector(tuple(max(v[i] for v in vs) for i in range(3)))
center = (low + high) / 2
span = max(high.x - low.x, high.y - low.y)
center.z = 152
cam_data = bpy.data.cameras.new('D125_fixed_camera')
cam_data.type = 'ORTHO'
cam_data.ortho_scale = span * 1.48
cam = bpy.data.objects.new('D125_fixed_camera', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def camera(direction):
    cam.location = center + Vector(direction).normalized() * span * 2
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()


def emission(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    e = tree.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*rgb, 1)
    tree.links.new(e.outputs[0], tree.nodes.new('ShaderNodeOutputMaterial').inputs['Surface'])
    return mat

orientation = bpy.data.materials.new('D125_Backfacing')
orientation.use_nodes = True
nodes = orientation.node_tree.nodes
nodes.clear()
g = nodes.new('ShaderNodeNewGeometry')
mix = nodes.new('ShaderNodeMixRGB')
mix.inputs[1].default_value = (0, 0, 1, 1)
mix.inputs[2].default_value = (1, 0, 0, 1)
e = nodes.new('ShaderNodeEmission')
output_node = nodes.new('ShaderNodeOutputMaterial')
links = orientation.node_tree.links
links.new(g.outputs['Backfacing'], mix.inputs[0])
links.new(mix.outputs[0], e.inputs['Color'])
links.new(e.outputs[0], output_node.inputs['Surface'])
scene.view_layers[0].material_override = orientation
views = {'top': (0, 0, 1), 'oblique45': (1, -1, 1), 'oblique135': (1, 1, 1), 'oblique225': (-1, 1, 1), 'oblique315': (-1, -1, 1)}
report = {'fbx': fbx, 'blender': bpy.app.version_string, 'views': {}, 'projected_triangle_area_m2': areas}
for name, direction in views.items():
    camera(direction)
    scene.render.filepath = str(out / f'face_orientation_{name}.png')
    bpy.ops.render.render(write_still=True)
    rendered = bpy.data.images.load(scene.render.filepath, check_existing=False)
    pixels = list(rendered.pixels)
    if len(pixels) != 768 * 768 * 4:
        raise RuntimeError('render readback has no pixels')
    bpy.data.images.remove(rendered)
    red = sum(pixels[i] > .8 and pixels[i + 2] < .2 and pixels[i + 3] > .5 for i in range(0, len(pixels), 4))
    blue = sum(pixels[i + 2] > .8 and pixels[i] < .2 and pixels[i + 3] > .5 for i in range(0, len(pixels), 4))
    report['views'][name] = {'red_pixels': red, 'blue_pixels': blue, 'camera_location': list(cam.location), 'camera_euler': list(cam.rotation_euler), 'ortho_scale': cam_data.ortho_scale, 'size_px': 768}
scene.view_layers[0].material_override = None
legend = {}
for ob in meshes:
    for index, mat in enumerate(list(ob.data.materials)):
        if mat.name not in legend:
            count = len(legend)
            rgb = colorsys.hsv_to_rgb((count * .61803398875) % 1, .65, .9)
            legend[mat.name] = {'rgb': list(rgb), 'id': count + 1}
        ob.data.materials[index] = emission('D125_' + mat.name, legend[mat.name]['rgb'])
camera(views['top'])
scene.render.filepath = str(out / 'material_ids_top.png')
bpy.ops.render.render(write_still=True)
report['legend'] = legend
(out / 'ground-polygons.json').write_text(json.dumps(ground_polygons), encoding='utf-8')
adapter = json.loads(Path(adapter_file).read_text(encoding='utf-8'))
offset = json.loads(Path(offset_file).read_text())['placement_offset']

def hit(x, y):
    pos, normal, index, distance = bvh.ray_cast(Vector((x - offset[0], y - offset[1], 1000)), Vector((0, 0, -1)))
    return pos.z if pos else None

points = []
for p in adapter['elevations']:
    if p.get('source') != 'point' or not p.get('inside'):
        continue
    z = hit(p['x'], p['y'])
    points.append({'ref': p.get('ref'), 'x': p['x'], 'y': p['y'], 'source_z': p['z'], 'model_z': z, 'deviation_m': z - p['z'] if z is not None else None})
report['spot_heights'] = points
report['sections'] = []
for p in points:
    samples = []
    for i in range(101):
        x = p['x'] - 5 + i / 10
        samples.append([x, hit(x, p['y'])])
    report['sections'].append({'spot': p, 'samples': samples})

def project(x, y):
    point = world_to_camera_view(scene, cam, Vector((x - offset[0], y - offset[1], center.z)))
    return [point.x * 768, (1 - point.y) * 768]

report['source_overlay'] = {'boundary': [[project(*p[:2]) for p in ring] for ring in adapter['boundary']['coordinates']], 'planting': [project(p['x'], p['y']) for p in adapter['planting'] if p.get('inside')], 'maf': [project(p['x'], p['y']) for p in adapter['maf'] if p.get('inside')]}
(out / 'evidence.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
print('EVIDENCE', len(points), 'spot heights;', len(fs), 'Ground triangles;', {k: v['red_pixels'] for k, v in report['views'].items()})
