"""Hook `after` stage `body` (#1619 polygon stage 2, Blender 5.1): review sheet of the stage-2 scene (read-only).

Pattern: n/a | new-case: stage-2 review sheet (iso + one window + one capsule + basket status), wire over solid.

blender -b --factory-startup --python stage2_sheet.py -- SCENE.blend STAGE2.json OUT.png [--opening N]

Opens the stage-2 .blend (never saves it), adds black Wireframe-modifier copies of the shown objects (wire over
solid) and renders with Workbench (object material colours): 1 iso of the tower, 2 one window from the street,
3 the same opening without the body (frame + glass + capsule from the side: the capsule depth), 4 the AC basket
status of STAGE2.json (none in the typical band -> the numbers, no invented basket). Tiles 2 x 2 into OUT.png.
Refuses OUT.png next to SCENE.blend. Wire copies, Workbench, camera aim, show-only and 2 x 2 tiling are the owner
tools/blender/stage2_review.py (t_3820c6be); this hook keeps the 63A panels, perspective cameras and captions.
"""
import json
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'tools', 'blender'))
import stage2_review as sr  # noqa: E402

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
wc, cc, out_dir, side = sr.opening_axes(frame, cap, sr.vertex_centre)
black = sr.wire_material('WIRE', (0.02, 0.02, 0.02, 1))
wires = {}

cam_data = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
sr.workbench(scene, 900, 900)
scene.display.shading.show_backface_culling = False
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new('sheet_bg')
scene.world.color = (0.93, 0.93, 0.93)
scene.display.shading.background_type = 'WORLD'
tmp = os.path.join(os.path.dirname(out_png), '_panels')
os.makedirs(tmp, exist_ok=True)


def look(eye, target, lens=35.0, ortho=None):
    sr.aim(cam, eye, (Vector(target) - Vector(eye)).normalized())
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
    sr.show_only(meshes, wires, {o for o in meshes if o.name in names})


def render(i, text, size):
    lb = label(text, size)
    scene.render.filepath = os.path.join(tmp, 'p{}.png'.format(i))
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(lb)
    return scene.render.filepath


meshes = [o for o in scene.objects if o.type == 'MESH']
for o in meshes:
    wires[o] = sr.wire_copy(o, 0.012 if o.name.startswith('SM_Body') else 0.006, black, o.users_collection[0])
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
    wires[o].modifiers['wire'].thickness = 0.03 if o.name.startswith('SM_Body') else 0.015
panels.append(render(1, '63A stage 2 v001: body v005 + {} windows + {} capsules (iso)'.format(
    rep['openings']['ok'], rep['capsules']['made']), 0.018))
for o in meshes:
    wires[o].modifiers['wire'].thickness = 0.012 if o.name.startswith('SM_Body') else 0.004
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

w, h = sr.tile_2x2(panels, out_png)
print('STAGE2_SHEET', out_png, 'opening', pick, json.dumps({'w': w, 'h': h}))
