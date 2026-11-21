"""KPP1 lattice step 3 renders (#1609): fixed corner / ground-floor cameras, textured (UDIM) and wire views.

Pattern: n/a | new-case: before/after renders of the KPP1 v004 lattice draft against quad-v003 with UDIM textures
(the #1563 corner cameras of jobs/KPP1/quad-1372/render_before_after.py, mirrored to the SE / NE corners).

    blender -b --factory-startup --python render_v004.py -- MODEL.(fbx|blend) TEX_DIR OUT_DIR TAG

Every non-glass material shows TEX_DIR/T_Kpp_1_Diffuse_1.<UDIM>.png as a tiled image (Workbench texture colour).
Wire mode: grey body, separate inset elements (object name containing `_Post_`) light blue, black wireframe on top.
UCX hidden. Outputs `<TAG>_<camera>_<tex|wire>.png`; an existing output fails the run.
"""
import importlib.util
import os
from pathlib import Path
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('rba_1372', HERE.parent / 'quad-1372' / 'render_before_after.py')
rba = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rba)

MIRROR_X = -14.985 + 12.675     # x' = MIRROR_X - x maps the W corners onto the E corners (ring x0 + x1)


def _mirror(cams, a, b):
    out = {}
    for k, (loc, tgt, lens) in cams.items():
        out[k.replace(a, b)] = ((MIRROR_X - loc[0], loc[1], loc[2]), (MIRROR_X - tgt[0], tgt[1], tgt[2]), lens)
    return out


CAMERAS = {}
for _set in (rba.CORNER_CAMERAS, rba.GROUND_CAMERAS):
    CAMERAS.update(_set)
    CAMERAS.update(_mirror({k: v for k, v in _set.items() if k.startswith('sw')}, 'sw', 'se'))
    CAMERAS.update(_mirror({k: v for k, v in _set.items() if k.startswith('nw')}, 'nw', 'ne'))


def main(model, tex_dir, out_dir, tag):
    outs = {(c, m): os.path.join(out_dir, f'{tag}_{c}_{m}.png') for c in CAMERAS for m in ('tex', 'wire')}
    taken = [p for p in outs.values() if os.path.exists(p)]
    if taken:
        raise SystemExit(f'outputs exist: {taken[:3]}')
    if model.lower().endswith('.blend'):
        bpy.ops.wm.open_mainfile(filepath=model, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=model)
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    first = os.path.join(tex_dir, 'T_Kpp_1_Diffuse_1.1001.png')
    if not os.path.isfile(first):
        raise SystemExit(f'missing {first}')
    img = bpy.data.images.load(first, check_existing=False)
    img.source = 'TILED'
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
        if 'Glass' in m.name:
            continue
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        nt.nodes.active = tex
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.05, 500
    sc.render.engine = 'BLENDER_WORKBENCH'
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
                o.color = (0.55, 0.75, 0.95, 1.0) if '_Post_' in o.name else (0.78, 0.78, 0.76, 1.0)
        for c, (loc, tgt, lens) in CAMERAS.items():
            rba.look_at(cam, loc, tgt)
            cam.data.type, cam.data.lens = 'PERSP', lens
            sc.render.resolution_x, sc.render.resolution_y = 1280, 860
            sc.render.filepath = outs[(c, mode)]
            bpy.ops.render.render(write_still=True)
    print('RENDERED', len(outs), sorted(CAMERAS))


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    if len(a) != 4:
        raise SystemExit(__doc__)
    main(*a)
