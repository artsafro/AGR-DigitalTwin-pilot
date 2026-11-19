"""Hook `after` stage `body` (#1619 polygon stage 2, Blender 5.1): review sheet of the stage-2 scene (read-only).

Pattern: n/a | new-case: stage-2 review sheet (iso + one window + one capsule + basket status), wire over solid.

blender -b --factory-startup --python stage2_sheet.py -- SCENE.blend STAGE2.json OUT.png [--opening N]

Opens the stage-2 .blend (never saves it), adds black Wireframe-modifier copies of the shown objects (wire over
solid) and renders with Workbench (object material colours): 1 iso of the tower, 2 one window from the street,
3 the same opening without the body (frame + glass + capsule from the side: the capsule depth), 4 the AC basket
status of STAGE2.json (none in the typical band -> the numbers, no invented basket). Tiles 2 x 2 into OUT.png.
Refuses OUT.png next to SCENE.blend.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
blend, plan_path, out_png = argv[:3]
pick = int(argv[argv.index('--opening') + 1]) if '--opening' in argv else None
if os.path.abspath(os.path.dirname(out_png)) == os.path.abspath(os.path.dirname(blend)):
    sys.exit('OUT.png must not sit next to the scene')
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
plan = json.load(open(plan_path, encoding='utf-8'))
rep = plan['report']
rows = {r['opening']: r for r in rep['rows']}
if pick is None:  # a 3-bay window on a middle floor
    mid = sorted({r['opening'] for r in rep['rows'] if r['type'].startswith('Окн_Окн_3')})
    pick = mid[len(mid) // 2]
objs = {o.name: o for o in scene.objects}
frame, glass, cap = (objs['SM_Win_{:03d}_Frame'.format(pick)], objs['SM_Win_{:03d}_Glass'.format(pick)],
                     objs['CAPSULE_63A_{:03d}'.format(pick)])


def centre(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return sum(vs, Vector()) / len(vs)


wc, cc = centre(frame), centre(cap)
out_dir = wc - cc
out_dir.z = 0
out_dir.normalize()
side = Vector((-out_dir.y, out_dir.x, 0))

black = bpy.data.materials.new('WIRE')
black.diffuse_color = (0.02, 0.02, 0.02, 1)
wires = {}


def wire_of(ob, t):
    w = ob.copy()
    w.data = ob.data
    w.name = ob.name + '_wire'
    for c in ob.users_collection:
        c.objects.link(w)
    m = w.modifiers.new('wire', 'WIREFRAME')
    m.thickness, m.use_replace, m.use_even_offset = t, True, False
    m.material_offset = len(ob.data.materials)
    w.data = ob.data.copy()
    w.data.materials.append(black)
    wires[ob.name] = w
    return w


cam_data = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_backface_culling = False
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new('sheet_bg')
scene.world.color = (0.93, 0.93, 0.93)
scene.display.shading.background_type = 'WORLD'
tmp = os.path.join(os.path.dirname(out_png), '_panels')
os.makedirs(tmp, exist_ok=True)


def look(eye, target, lens=35.0, ortho=None):
    cam.location = eye
    d = (Vector(target) - Vector(eye)).normalized()
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam_data.type, cam_data.ortho_scale = 'ORTHO', ortho
    else:
        cam_data.type, cam_data.lens = 'PERSP', lens
    cam_data.clip_start, cam_data.clip_end = 0.05, 2000


def label(text, size):
    cu = bpy.data.curves.new('lbl', 'FONT')
    cu.body, cu.size = text, size
    ob = bpy.data.objects.new('lbl', cu)
    ob.data.materials.append(black)
    scene.collection.objects.link(ob)
    ob.parent = cam
    ob.location = (-0.39, 0.36, -1.0) if cam_data.type == 'PERSP' else (-0.48 * cam_data.ortho_scale,
                                                                      0.45 * cam_data.ortho_scale, -1.0)
    return ob


def show_only(names):
    for o in scene.objects:
        if o.type in ('MESH',) and not o.name.endswith('_wire'):
            o.hide_render = o.name not in names
            if o.name in wires:
                wires[o.name].hide_render = o.hide_render


def render(i, text, size):
    lb = label(text, size)
    scene.render.filepath = os.path.join(tmp, 'p{}.png'.format(i))
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(lb)
    return scene.render.filepath


meshes = [o for o in scene.objects if o.type == 'MESH']
for o in meshes:
    wire_of(o, 0.012 if o.name.startswith('SM_Body') else 0.006)
allnames = {o.name for o in meshes}
panels = []
# 1 iso of the tower
pts = [o.matrix_world @ Vector(c) for o in meshes if o.name.startswith('SM_Body') for c in o.bound_box]
lo = Vector([min(p[k] for p in pts) for k in range(3)])
hi = Vector([max(p[k] for p in pts) for k in range(3)])
mid = (lo + hi) / 2
show_only(allnames)
look(mid + Vector((-60, -60, 30)), mid, ortho=62)
for o in meshes:  # thicker wire on the overview
    wires[o.name].modifiers['wire'].thickness = 0.03 if o.name.startswith('SM_Body') else 0.015
panels.append(render(1, '63A stage 2 v001: body v005 + {} windows + {} capsules (iso)'.format(
    rep['openings']['ok'], rep['capsules']['made']), 0.018))
for o in meshes:
    wires[o.name].modifiers['wire'].thickness = 0.012 if o.name.startswith('SM_Body') else 0.004
# 2 one window from the street
r = rows[pick]
look(wc + out_dir * 3.2 + side * 1.4 + Vector((0, 0, 0.8)), wc, lens=30)
panels.append(render(2, 'window {:03d}: {} {:.2f} x {:.2f} m, reveal {:.2f} m'.format(
    pick, r['type'].replace('Окн_Окн_', 'Okn_'), r['w'], r['h'], r['reveal_m']), 0.025))
# 3 the same opening, body hidden: frame + glass + capsule (depth)
show_only({frame.name, glass.name, cap.name})
look(wc + out_dir * 2.4 + side * 2.6 + Vector((0, 0, 1.6)), (wc + cc) / 2, lens=30)
panels.append(render(3, 'capsule {:03d}: rim on frame middle, +100 mm outline, 1.0 m deep'.format(pick), 0.025))
# 4 basket status
show_only(set())
b = rep['baskets']
txt = ('AC baskets: Revit has {} in the typical band\n+10.15..+47.95 (stage 1 floors).\nOutside the band: {}\n'
       'Nothing invented -> question to Artem.').format(
    b['in_band'], ', '.join('z {} x{}'.format(z, n) for z, n in b['outside_band_by_zmin']))
look(Vector((0, -10, 0)), Vector((0, 0, 0)), lens=35)
panels.append(render(4, txt, 0.03))

imgs = []
for p in panels:
    im = bpy.data.images.load(p)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
    imgs.append(a)
top = np.concatenate([imgs[2], imgs[3]], axis=1)  # pixel rows start at the bottom
bot = np.concatenate([imgs[0], imgs[1]], axis=1)
sheet = np.concatenate([top, bot], axis=0)
h, w = sheet.shape[:2]
img = bpy.data.images.new('sheet', w, h, alpha=True)
img.pixels[:] = sheet.ravel()
img.filepath_raw, img.file_format = out_png, 'PNG'
img.save()
print('STAGE2_SHEET', out_png, 'opening', pick, json.dumps({'w': w, 'h': h}))
