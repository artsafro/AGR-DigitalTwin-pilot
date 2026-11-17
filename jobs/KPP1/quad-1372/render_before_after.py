"""new-case: Before (R1) / After (quad master) renders of KPP1 with the same fixed cameras (#1372, #1360 rule).

    blender -b --factory-startup --python render_before_after.py -- <model.fbx> <texture.png> <out_dir> <tag> [default|corners]

Workbench, fixed world-space cameras (numbers below, never derived from the model, so Before and After share them):
two overviews and three close-ups on the v002 union zones / the 5 mm step. Every camera is rendered textured
(the R1 albedo atlas on the R1 UVs: same look check) and as a wire view (a black wireframe copy over a grey model:
triangles vs quads). UCX meshes are hidden. Outputs `<tag>_<camera>_<mode>.png`; an existing output fails the run.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

CAMERAS = {  # name: (location, target, lens mm)
    'overview_se': ((24.0, -26.0, 14.0), (0.0, 0.0, 3.5), 35),
    'overview_nw': ((-26.0, 26.0, 13.0), (0.0, 0.0, 3.5), 35),
    'north_window_x0p3': ((0.9, 7.6, 3.2), (0.3, 5.97, 2.6), 35),
    'north_panel_x12p6': ((11.0, 10.0, 7.5), (12.4, 6.0, 6.4), 35),
    'east_step_x12p42': ((13.4, 0.2, 4.4), (12.42, 0.9, 3.85), 50),
}
CORNER_CAMERAS = {  # #1563: SW / NW corner posts (#1246 readback-v003b centres), v002 vs v003 quad master
    'sw_from_sw': ((-17.2, -8.0, 7.6), (-15.03, -5.73, 5.8), 35),
    'sw_from_s': ((-14.2, -8.8, 6.2), (-15.0, -5.7, 5.9), 35),
    'nw_from_nw': ((-17.2, 8.3, 7.6), (-15.03, 6.02, 5.8), 35),
    'nw_from_n': ((-14.2, 9.1, 6.2), (-15.0, 6.0, 5.9), 35),
}
CAMERA_SETS = {'default': CAMERAS, 'corners': CORNER_CAMERAS}


def look_at(cam, loc, target):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def main(fbx, png, out_dir, tag, cams='default'):
    if cams not in CAMERA_SETS:
        raise SystemExit(f'unknown camera set {cams!r} (known: {", ".join(CAMERA_SETS)})')
    cameras = CAMERA_SETS[cams]
    os.makedirs(out_dir, exist_ok=True)
    outs = {(c, m): os.path.join(out_dir, f'{tag}_{c}_{m}.png') for c in cameras for m in ('tex', 'wire')}
    taken = [p for p in outs.values() if os.path.exists(p)]
    if taken:
        raise SystemExit(f'outputs exist: {taken[:3]}')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    sc = bpy.context.scene
    img = bpy.data.images.load(png)
    meshes = []
    for o in list(sc.objects):
        if o.type != 'MESH':
            bpy.data.objects.remove(o)
        elif o.name.startswith('UCX_'):
            o.hide_render = True
        else:
            meshes.append(o)
    for m in bpy.data.materials:
        m.use_nodes = True
        nt = m.node_tree
        tex = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None) or nt.nodes.new('ShaderNodeTexImage')
        if 'Glass' not in m.name:
            tex.image = img
        nt.nodes.active = tex
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.05, 500
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = 1280, 860
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.show_shadows = False
    sh.show_cavity = False
    wires = []
    for o in meshes:
        w = o.copy()
        w.data = o.data.copy()
        sc.collection.objects.link(w)
        mod = w.modifiers.new('wire', 'WIREFRAME')
        mod.thickness, mod.use_relative_offset, mod.use_replace = 0.004, False, True
        w.color = (0.02, 0.02, 0.02, 1.0)
        wires.append(w)
    for mode in ('tex', 'wire'):
        for w in wires:
            w.hide_render = mode != 'wire'
        if mode == 'tex':
            sh.color_type = 'TEXTURE'
        else:
            sh.color_type = 'OBJECT'
            for o in meshes:
                o.color = (0.78, 0.78, 0.76, 1.0)
        for c, (loc, tgt, lens) in cameras.items():
            look_at(cam, loc, tgt)
            cam.data.lens = lens
            sc.render.filepath = outs[(c, mode)]
            bpy.ops.render.render(write_still=True)
    print('RENDERED', len(outs))


if __name__ == '__main__':
    main(*sys.argv[sys.argv.index('--') + 1:][:5])
