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

# Fixed Blender 5.1 Workbench policy, independent of either saved .blend.
# Record even inactive controls so a future style/light change cannot inherit them.
WORKBENCH_SHADING = {
    'show_object_outline': False,
    'object_outline_color': (0.0, 0.0, 0.0),
    'show_xray': False,
    'show_specular_highlight': True,
    'studio_light': 'Default',
    'studiolight_rotate_z': 0.0,
    'xray_alpha': 0.5,
    'show_backface_culling': False,
    'use_dof': False,
}
WORKBENCH_DISPLAY = {
    'render_aa': '8',
    'light_direction': (1 / math.sqrt(3),) * 3,
}


def workbench_record(scene):
    """Actual post-render readback, not a copy of the intended policy."""
    values = {}
    for owner, policy in ((scene.display.shading, WORKBENCH_SHADING),
                          (scene.display, WORKBENCH_DISPLAY)):
        for key in policy:
            value = getattr(owner, key)
            values[key] = value if isinstance(value, (str, bool, float)) else list(value)
    return values


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


def setup(scene, fitted):
    width, height = request['resolution']
    render = scene.render
    render.engine = 'BLENDER_WORKBENCH'
    render.resolution_x, render.resolution_y, render.resolution_percentage = width, height, 100
    render.pixel_aspect_x = render.pixel_aspect_y = 1.0
    # Saved crop/stereo state must not change the comparison's frame or eyes.
    render.use_border = False
    render.use_multiview = False
    render.image_settings.views_format = 'INDIVIDUAL'
    render.film_transparent = False
    render.use_stamp = False
    # use_stamp controls the visible overlay only. The individual toggles also
    # write PNG metadata (source path, date, render time), breaking byte parity.
    for prop in render.bl_rna.properties:
        if prop.identifier.startswith('use_stamp_') and prop.type == 'BOOLEAN':
            setattr(render, prop.identifier, False)
    render.image_settings.file_format = 'PNG'
    render.image_settings.color_mode = 'RGB'
    render.image_settings.color_depth = '8'
    render.image_settings.compression = 15
    render.dither_intensity = 1.0
    shading = scene.display.shading
    # studio_light's enum depends on light: select STUDIO before its preset.
    shading.light = 'STUDIO'
    shading.use_world_space_lighting = False
    for owner, policy in ((shading, WORKBENCH_SHADING), (scene.display, WORKBENCH_DISPLAY)):
        for key, value in policy.items():
            setattr(owner, key, value)
    shading.show_cavity = False
    shading.show_shadows = False
    shading.color_type = {'solid': 'SINGLE', 'wire': 'OBJECT', 'material': 'MATERIAL',
                          'texture': 'TEXTURE'}[request['style']]
    shading.single_color = (0.8, 0.8, 0.8)
    scene.view_settings.view_transform = 'Standard'
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
    if request['style'] == 'wire':
        objects = meshes(scene)
        extent = max((max(bbox(scene)[1] - bbox(scene)[0])), 1e-3)
        for obj in objects:
            obj.color = (0.82, 0.82, 0.82, 1.0)
            wire = obj.copy()
            scene.collection.objects.link(wire)
            modifier = wire.modifiers.new('BeforeAfterWire', 'WIREFRAME')
            modifier.thickness = extent * 6e-4
            modifier.use_replace = True
            wire.color = (0.05, 0.05, 0.05, 1.0)
    bpy.context.view_layer.update()
    return camera


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
if request['mode'] == 'fit':
    boxes = [bbox(load(cfg[role])) for role in ('before', 'after')]
    fitted = fit_camera((Vector([min(b[0][i] for b in boxes) for i in range(3)]),
                         Vector([max(b[1][i] for b in boxes) for i in range(3)])))
evidence = {}
for role in ('before', 'after'):
    scene = load(cfg[role])
    mesh_count = len(meshes(scene))  # before setup(): the 'wire' style adds wireframe copies (r1 P3)
    camera = setup(scene, fitted)
    scene.render.filepath = str(out / f'{role}.png')
    bpy.ops.render.render(write_still=True)
    evidence[role] = {'camera': record(scene, camera), 'mesh_objects': mesh_count,
                      'render': {'engine': scene.render.engine, 'style': request['style'],
                                 'use_world_space_lighting': scene.display.shading.use_world_space_lighting,
                                 'dither_intensity': scene.render.dither_intensity,
                                 'color_mode': scene.render.image_settings.color_mode,
                                 'color_depth': scene.render.image_settings.color_depth,
                                 'compression': scene.render.image_settings.compression,
                                 'use_border': scene.render.use_border,
                                 'use_multiview': scene.render.use_multiview,
                                 'image_views_format': scene.render.image_settings.views_format,
                                 'workbench': workbench_record(scene)}}
(out / 'render-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
