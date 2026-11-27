"""#135 harness, Blender side: render the stylobate walls of ONE blend from the frozen shots (OBSERVE, read-only).

blender -b --factory-startup <blend> --python render.py -- --kind {source,v045,v096} --out DIR
Never saves the blend. Writes DIR/<variant>_<mode>_<shot>.png and DIR/render_<kind>.json.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

EVID = Path('G:/Мой диск/AGR-evidence/1326-stylobate-course-grid')
DESK = Path('C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/build/textures')
OBJ = 'K3_StylobateWalls.001'
SHOTS = [  # frozen in docs/research/autoresearch-normal-relief-r135.md
    ('straight-wall', (116.7, 50.4, 4.45), (0.87, -0.49, 0.03)),
    ('corner', (112.72, 43.34, 4.05), (0.5, -0.9, 0.04)),
    ('floor-join', (116.7, 50.4, 3.2), (0.87, -0.49, 0.04)),
    ('niche', (112.5, 43.7, 1.7), (0.87, -0.49, 0.08)),
    ('joint-stripe', (116.49096, 49.96561, 3.25667), (0.86919, -0.49448, -0.00037)),
]
MAPS = {
    'source': (DESK / 'T_K3_StyloBrick_Diffuse.png', DESK / 'T_K3_StyloBrick_Normal.png', 0),
    'v045': (EVID / 'cut-v014/T_1326_Stylo_Diffuse.1001.png', EVID / 'cut-v014/T_1326_Stylo_Normal.1001.png', 1),
    'v096': (EVID / 'normal-v092/T_1326_Stylo_Diffuse.1001.png', EVID / 'normal-v092/T_1326_Stylo_Normal.1001.png', 2),
}
# variant -> (normal mode); N0 = source rendered again as candidate, P1 flat, P2 half strength
VARIANTS = {'source': ['S', 'N0'], 'v045': ['v045'], 'v096': ['v096', 'P1', 'P2']}


def load(path, tiles, colorspace):
    img = bpy.data.images.load(str(path), check_existing=False)
    if tiles:
        img.source = 'TILED'
        img.filepath = str(path).replace('.1001.', '.<UDIM>.')
        img.reload()
        got = sorted(t.number for t in img.tiles)
        assert got == list(range(1001, 1001 + tiles)), (path, got)
    img.colorspace_settings.name = colorspace
    assert img.size[0] > 0, path
    return img


def material(name, diffuse, normal, mode, variant):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.8
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    if mode == 'full':
        dt = nt.nodes.new('ShaderNodeTexImage')
        dt.image = diffuse
        nt.links.new(dt.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = 0.5 if variant == 'P2' else 1.0
    if variant != 'P1':  # P1: flat witness, Normal Map node left disconnected
        nt_ = nt.nodes.new('ShaderNodeTexImage')
        nt_.image = normal
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        comb = nt.nodes.new('ShaderNodeCombineColor')
        flip = nt.nodes.new('ShaderNodeMath')
        flip.operation = 'SUBTRACT'
        flip.inputs[0].default_value = 1
        nt.links.new(nt_.outputs['Color'], sep.inputs[0])
        nt.links.new(sep.outputs['Red'], comb.inputs['Red'])
        nt.links.new(sep.outputs['Green'], flip.inputs[1])
        nt.links.new(flip.outputs[0], comb.inputs['Green'])
        nt.links.new(sep.outputs['Blue'], comb.inputs['Blue'])
        nt.links.new(comb.outputs[0], nm.inputs['Color'])
        nt.links.new(nm.outputs[0], bsdf.inputs['Normal'])
    return mat


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    kind = argv[argv.index('--kind') + 1]
    # A1 (amendment before the second measurement): relief-mode light energy; R1 = 120 (saturated)
    relief_energy = float(argv[argv.index('--relief-energy') + 1]) if '--relief-energy' in argv else 120.0
    out = Path(argv[argv.index('--out') + 1])
    assert bpy.app.version_string == '5.1.2', bpy.app.version_string
    assert bpy.context.scene.unit_settings.scale_length == 1
    scene = bpy.context.scene
    obj = bpy.data.objects[OBJ]
    for o in bpy.data.objects:
        o.hide_render = o is not obj
    dpath, npath, tiles = MAPS[kind]
    diffuse = load(dpath, tiles, 'sRGB')
    normal = load(npath, tiles, 'Non-Color')
    slots = [i for i, s in enumerate(obj.material_slots) if s.material and s.material.name.startswith('ID1_Brick')]
    assert len(slots) == 1, [s.material.name if s.material else None for s in obj.material_slots]
    hold = bpy.data.materials.new('r135_holdout')
    hold.use_nodes = True
    hold.node_tree.nodes.clear()
    ho = hold.node_tree.nodes.new('ShaderNodeOutputMaterial')
    hh = hold.node_tree.nodes.new('ShaderNodeHoldout')
    hold.node_tree.links.new(hh.outputs[0], ho.inputs['Surface'])
    for i, s in enumerate(obj.material_slots):
        if i != slots[0]:
            s.link = 'OBJECT'
            s.material = hold
    obj.material_slots[slots[0]].link = 'OBJECT'
    id1_faces = sum(1 for p in obj.data.polygons if p.material_index == slots[0])

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.seed = 0
    scene.cycles.samples = 24
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.render.resolution_x = scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    if scene.world is None:
        scene.world = bpy.data.worlds.new('r135_world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.12, .12, .12, 1)
    camd = bpy.data.cameras.new('r135_cam')
    camd.type = 'ORTHO'
    camd.ortho_scale = 0.6
    cam = bpy.data.objects.new('r135_cam', camd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    ld = bpy.data.lights.new('r135_light', 'AREA')
    ld.energy = 120
    ld.shape = 'DISK'
    ld.size = 0.3
    lamp = bpy.data.objects.new('r135_light', ld)
    scene.collection.objects.link(lamp)
    cam.hide_render = lamp.hide_render = False

    rows = []
    for variant in VARIANTS[kind]:
        for mode in ('relief', 'full'):
            ld.energy = relief_energy if mode == 'relief' else 120
            obj.material_slots[slots[0]].material = material(f'r135_{variant}_{mode}', diffuse, normal, mode, variant)
            for shot, target, direction in SHOTS:
                t = Vector(target)
                d = Vector(direction).normalized()
                right = d.cross(Vector((0, 0, 1))).normalized()
                cam.location = t + d * 3
                cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
                lamp.location = t + d * 0.4 + right * 1.1 + Vector((0, 0, 0.3))
                lamp.rotation_euler = (t - lamp.location).to_track_quat('-Z', 'Y').to_euler()
                path = out / f'{variant}_{mode}_{shot}.png'
                assert not path.exists(), path
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                rows.append(dict(variant=variant, mode=mode, shot=shot, png=path.name))
    rep = dict(kind=kind, blend=bpy.data.filepath, blender=bpy.app.version_string, object=OBJ,
               id1_slot=slots[0], id1_faces=id1_faces, faces=len(obj.data.polygons),
               diffuse=diffuse.filepath, normal=normal.filepath,
               tiles=sorted(t.number for t in diffuse.tiles) if diffuse.source == 'TILED' else None,
               renders=rows)
    (out / f'render_{kind}.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print('R135_RENDER_DONE', kind, len(rows), flush=True)


main()
