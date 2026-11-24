"""Stage-2 review views (polygon stage 2, #1619): iso + one window + one capsule, black wire over Workbench solid.

Pattern: n/a | new-case: the one owner of the stage-2 review render (t_3820c6be, harvest #1804). Moved from
jobs/POLY63-C/hooks/stage2_views.py (63B/63C, now a shim) and the shared parts of
jobs/POLY63-A/stage2-1619/hooks/stage2_sheet.py (63A, now calls these blocks). Read-only on the scene: nothing is
saved. This is not the verifier stage: tools/blender/verifier_views.py keeps its fixed 6-view VLM contract (#1739).

blender -b SCENE.blend --python tools/blender/stage2_review.py -- OUT_DIR FRAME_ID [ISO_ORTHO_SCALE]
writes OUT_DIR/iso.png, window.png, capsule.png, cut.png (objects SM_Body_Main, SM_Win_<ID>_Frame/_Glass,
CAPSULE_*_<ID>). Runs inside Blender (bpy).
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def bbox_centre(ob):
    """World centre of the object's bounding box."""
    return sum([ob.matrix_world @ Vector(c) for c in ob.bound_box], Vector()) / 8


def vertex_centre(ob):
    """World mean of the mesh vertices."""
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return sum(vs, Vector()) / len(vs)


def opening_axes(frame, cap, centre=bbox_centre):
    """(window centre, capsule centre, horizontal street direction, horizontal side direction) of one opening."""
    wc, cc = centre(frame), centre(cap)
    out = wc - cc
    out.z = 0
    out.normalize()
    return wc, cc, out, Vector((-out.y, out.x, 0))


def workbench(scene, width, height, percent=None, cavity=None):
    """Workbench render in object material colours with studio light; None leaves the scene's setting."""
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.light = 'STUDIO'
    if cavity is not None:
        scene.display.shading.show_cavity = cavity
    scene.render.resolution_x, scene.render.resolution_y = width, height
    if percent is not None:
        scene.render.resolution_percentage = percent


def wire_material(name, rgba):
    m = bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


def wire_copy(ob, thickness, material, collection):
    """Black Wireframe-modifier copy of a mesh object (own mesh data, one material), linked to `collection`."""
    w = ob.copy()
    w.data = ob.data.copy()
    w.name = ob.name + '_wire'
    collection.objects.link(w)
    w.data.materials.clear()
    w.data.materials.append(material)
    m = w.modifiers.new('wire', 'WIREFRAME')
    m.thickness, m.use_replace, m.use_even_offset = thickness, True, False
    return w


def show_only(meshes, wires, visible=None):
    """Render only `visible` of `meshes` (None = all) and their wire copies (dict mesh -> wire)."""
    for ob in meshes:
        ob.hide_render = visible is not None and ob not in visible
        if ob in wires:
            wires[ob].hide_render = ob.hide_render


def aim(cam, eye, direction):
    """Put the camera at `eye` looking along `direction`, up = +Z."""
    cam.location = eye
    cam.rotation_euler = Vector(direction).to_track_quat('-Z', 'Y').to_euler()


def tile_2x2(paths, out_png):
    """Tile four equal panels (1 2 / 3 4, top row first) into one PNG; returns (width, height)."""
    import numpy as np
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p)
        imgs.append(np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4))
    top = np.concatenate([imgs[2], imgs[3]], axis=1)  # pixel rows start at the bottom
    bot = np.concatenate([imgs[0], imgs[1]], axis=1)
    sheet = np.concatenate([top, bot], axis=0)
    h, w = sheet.shape[:2]
    img = bpy.data.images.new('sheet', w, h, alpha=True)
    img.pixels[:] = sheet.ravel()
    img.filepath_raw, img.file_format = out_png, 'PNG'
    img.save()
    return w, h


def render_views(scene, folder, key, iso_scale=65.0):
    """The four 63B/63C review panels (iso, window, capsule, cut) as separate PNGs in `folder` (ortho cameras)."""
    folder = Path(folder)
    folder.mkdir(exist_ok=True)
    objs = bpy.data.objects
    body, frame, glass = objs['SM_Body_Main'], objs[f'SM_Win_{key}_Frame'], objs[f'SM_Win_{key}_Glass']
    cap = next(o for o in objs if o.name.startswith('CAPSULE_') and o.name.endswith(f'_{key}'))  # 63C/63B
    workbench(scene, 960, 720, percent=100, cavity=True)
    cam = bpy.data.objects.new('Review camera', bpy.data.cameras.new('Review camera'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    pts = [body.matrix_world @ Vector(c) for c in body.bound_box]
    mid = sum(pts, Vector()) / 8
    wc, cc, out, side = opening_axes(frame, cap)
    z = Vector((0, 0, 1))
    meshes = [o for o in scene.objects if o.type == 'MESH']
    black = wire_material('Graphite wire', (.014, .021, .03, 1))
    wire = {ob: wire_copy(ob, .014 if ob == body else .007, black, scene.collection)
            for ob in (body, frame, glass, cap)}

    def render(name, target, delta, scale, visible=None):
        show_only(meshes, wire, visible)
        aim(cam, target + delta, -delta)
        cam.data.type, cam.data.ortho_scale, cam.data.clip_end = 'ORTHO', scale, 300
        scene.render.filepath = str(folder / (name + '.png'))
        bpy.ops.render.render(write_still=True)

    render('iso', mid, Vector((-45, -75, 40)), iso_scale)
    render('window', wc, out * 3 + side * .75 + z * .5, 4.6)
    render('capsule', (wc + cc) * .5, out * 2 + side * 3 + z * 1.5, 4.7, {frame, glass, cap})
    render('cut', Vector((mid.x, mid.y, max(p.z for p in pts) - .4)), Vector((-35, -50, 60)), 45)
    return [str(folder / (n + '.png')) for n in ('iso', 'window', 'capsule', 'cut')]


def main(argv):
    """OUT_DIR FRAME_ID [ISO_ORTHO_SCALE] on the open scene."""
    folder, key = argv[:2]
    iso_scale = float(argv[2]) if len(argv) > 2 else 65  # 63B: taller tower
    return render_views(bpy.context.scene, folder, key, iso_scale)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:])
