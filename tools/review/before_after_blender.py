"""new-case: Blender side of tools/review/before_after.py (#1360): one camera, two scene versions.

Run only through dt_ai.core.blender_runner.run_blender (background, factory startup).
Pass 1 loads both scenes and measures the union bounding box of their render-visible
meshes (fit mode); pass 2 loads each scene again, applies the SAME camera and the
same Workbench settings, renders before.png / after.png and records the camera that
was actually used for each render. The driver compares the two records.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector  # noqa: F401

if not bpy.app.background:
    raise RuntimeError('background-only Before/After renderer')

cfg = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
request = cfg['request']
out = Path(cfg['output_dir'])


def load(path):
    if path.lower().endswith('.blend'):
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=path, use_image_search=request['style'] == 'texture')
    return bpy.context.scene


def meshes(scene):
    found = [o for o in scene.objects if o.type == 'MESH' and not o.hide_render]
    if not found:
        raise RuntimeError(f'no render-visible mesh in {bpy.data.filepath or "imported scene"}')
    return found


def bbox(scene):
    points = [o.matrix_world @ Vector(c) for o in meshes(scene) for c in o.bound_box]
    return (Vector([min(p[i] for p in points) for i in range(3)]),
            Vector([max(p[i] for p in points) for i in range(3)]))


def fit_camera(union):
    low, high = union
    centre = (low + high) / 2
    extent = max((high - low).length, 1e-3)
    az, el = math.radians(request['azimuth_deg']), math.radians(request['elevation_deg'])
    direction = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    rotation = (-direction).to_track_quat('-Z', 'Y').to_matrix()
    right, up = rotation.col[0], rotation.col[1]
    corners = [Vector((x, y, z)) for x in (low.x, high.x) for y in (low.y, high.y) for z in (low.z, high.z)]
    xs = [(c - centre).dot(right) for c in corners]
    ys = [(c - centre).dot(up) for c in corners]
    width, height = request['resolution']
    span = max(max(xs) - min(xs), (max(ys) - min(ys)) * width / height) * request['margin']
    return {'location': centre + direction * extent * 2, 'rotation': rotation.to_euler(),
            'ortho_scale': max(span, 1e-3), 'clip_start': extent * 1e-3, 'clip_end': extent * 5}


def setup(scene, fitted, thickness):
    width, height = request['resolution']
    render = scene.render
    render.engine = 'BLENDER_WORKBENCH'
    render.resolution_x, render.resolution_y, render.resolution_percentage = width, height, 100
    render.pixel_aspect_x = render.pixel_aspect_y = 1.0
    render.film_transparent = False
    render.use_stamp = False
    # These flags also control PNG metadata even when the visible stamp is off.
    for prop in render.bl_rna.properties:
        if prop.identifier.startswith('use_stamp_') and prop.type == 'BOOLEAN':
            setattr(render, prop.identifier, False)
    render.image_settings.file_format = 'PNG'
    shading = scene.display.shading
    shading.light = 'STUDIO'
    shading.show_cavity = False
    shading.show_shadows = False
    shading.color_type = {'solid': 'SINGLE', 'wire': 'OBJECT', 'material': 'MATERIAL',
                          'texture': 'TEXTURE'}[request['style']]
    shading.single_color = (0.8, 0.8, 0.8)
    shading.background_type = 'VIEWPORT'
    shading.background_color = (0.05, 0.05, 0.05)
    # Workbench uses the explicit VIEWPORT colour, never inherited world nodes.
    scene.world = bpy.data.worlds.new('BeforeAfterWorld')
    scene.world.color = (0.05, 0.05, 0.05)
    scene.display_settings.display_device = 'sRGB'
    scene.display_settings.emulation = 'AUTO'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.view_settings.use_curve_mapping = False
    scene.view_settings.use_white_balance = False
    if request['mode'] == 'named':
        camera = scene.objects.get(request['name'])
        if camera is None or camera.type != 'CAMERA':
            raise RuntimeError(f"camera {request['name']!r} is missing in {bpy.data.filepath or 'scene'}")
    else:
        data = bpy.data.cameras.new('BeforeAfterCamera')
        camera = bpy.data.objects.new('BeforeAfterCamera', data)
        scene.collection.objects.link(camera)
        data.type = 'ORTHO'
        data.ortho_scale = fitted['ortho_scale']
        data.clip_start, data.clip_end = fitted['clip_start'], fitted['clip_end']
        data.sensor_fit = 'AUTO'
        camera.location = fitted['location']
        camera.rotation_euler = fitted['rotation']
    scene.camera = camera
    wires = []
    if request['style'] == 'wire':
        objects = meshes(scene)
        for obj in objects:
            obj.color = (0.82, 0.82, 0.82, 1.0)
            wire = obj.copy()
            scene.collection.objects.link(wire)
            modifier = wire.modifiers.new('BeforeAfterWire', 'WIREFRAME')
            modifier.thickness = thickness
            wires.append(modifier)
            modifier.use_replace = True
            wire.color = (0.05, 0.05, 0.05, 1.0)
    bpy.context.view_layer.update()
    return camera, wires


def render_record(scene, wires):
    shading = scene.display.shading
    thicknesses = [m.thickness for m in wires]
    if thicknesses and any(t != thicknesses[0] for t in thicknesses):
        raise RuntimeError('mismatched wire thickness within scene')
    return {'engine': scene.render.engine, 'style': request['style'],
            'view_transform': scene.view_settings.view_transform,
            'look': scene.view_settings.look, 'exposure': scene.view_settings.exposure,
            'gamma': scene.view_settings.gamma,
            'use_curve_mapping': scene.view_settings.use_curve_mapping,
            'use_white_balance': scene.view_settings.use_white_balance,
            'emulation': scene.display_settings.emulation,
            'display_device': scene.display_settings.display_device,
            'world_color': list(scene.world.color), 'world_use_nodes': scene.world.use_nodes,
            'background_type': shading.background_type,
            'background_color': list(shading.background_color),
            'thickness': thicknesses[0] if thicknesses else None}


def record(scene, camera):
    data = camera.data
    res = [scene.render.resolution_x * scene.render.resolution_percentage // 100,
           scene.render.resolution_y * scene.render.resolution_percentage // 100]
    aspect = [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y]
    projection = camera.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=res[0], y=res[1],
                                           scale_x=aspect[0], scale_y=aspect[1])
    return {'type': data.type, 'matrix_world': [v for row in camera.matrix_world for v in row],
            'projection': [v for row in projection for v in row],
            'lens': data.lens, 'ortho_scale': data.ortho_scale, 'sensor_width': data.sensor_width,
            'sensor_height': data.sensor_height,
            'sensor_fit': data.sensor_fit, 'shift_x': data.shift_x, 'shift_y': data.shift_y,
            'clip_start': data.clip_start, 'clip_end': data.clip_end,
            'resolution': res, 'pixel_aspect': aspect}


fitted = None
thickness = None
if request['mode'] == 'fit' or request['style'] == 'wire':
    boxes = [bbox(load(cfg[role])) for role in ('before', 'after')]
    union = (Vector([min(b[0][i] for b in boxes) for i in range(3)]),
             Vector([max(b[1][i] for b in boxes) for i in range(3)]))
    thickness = max(max(union[1] - union[0]), 1e-3) * 6e-4
    if request['mode'] == 'fit':
        fitted = fit_camera(union)
evidence = {}
for role in ('before', 'after'):
    scene = load(cfg[role])
    mesh_count = len(meshes(scene))  # before setup(): the 'wire' style adds wireframe copies (r1 P3)
    camera, wires = setup(scene, fitted, thickness)
    scene.render.filepath = str(out / f'{role}.png')
    bpy.ops.render.render(write_still=True)
    evidence[role] = {'camera': record(scene, camera), 'mesh_objects': mesh_count,
                      'render': render_record(scene, wires)}
(out / 'render-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
