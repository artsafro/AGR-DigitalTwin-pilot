"""#1423 KPP1 proof helper (Blender, background): edit one roof part of a master COPY, or export a VPM-style FBX with UCX.

Pattern: n/a | new-case: proof-only Blender driver of the #1423 stale-set test; never touches inputs.

    blender -b --factory-startup -noaudio --python edit_export_1423.py -- roof IN.fbx OUT.fbx REPORT.json
    blender -b --factory-startup -noaudio --python edit_export_1423.py -- vpm  IN.fbx OUT.fbx REPORT.json

roof: the top roof faces (normal z > 0.95 within 5 cm of the highest such face) of the largest mesh go up 0.30 m.
vpm:  the master meshes kept (SM_Kpp_1_Main, MainGlass, UCX_SM_Kpp_1_Main_NNN); render meshes triangulated.
OUT and REPORT must not exist (new files only).
"""
import json
import os
import sys

import bmesh
import bpy

ROOF_LIFT_M = 0.30


def main():
    mode, src, out, rep = sys.argv[sys.argv.index('--') + 1:][:4]
    for p in (out, rep):
        if os.path.exists(p):
            raise SystemExit('exists: ' + p)
    if os.path.normcase(os.path.realpath(src)) in {os.path.normcase(os.path.realpath(p)) for p in (out, rep)}:
        raise SystemExit('output is the input')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    report = {'mode': mode, 'source': os.path.basename(src), 'meshes_in': sorted(o.name for o in meshes)}
    if mode == 'roof':
        obj = max(meshes, key=lambda o: len(o.data.polygons))
        mw = obj.matrix_world
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        up = [f for f in bm.faces if (mw.to_3x3() @ f.normal).normalized().z > 0.95]
        top = max((mw @ f.calc_center_median()).z for f in up)
        roof = [f for f in up if (mw @ f.calc_center_median()).z >= top - 0.05]
        verts = {v for f in roof for v in f.verts}
        lift = mw.inverted().to_3x3() @ __import__('mathutils').Vector((0, 0, ROOF_LIFT_M))
        for v in verts:
            v.co += lift
        bm.to_mesh(obj.data)
        bm.free()
        report.update({'object': obj.name, 'roof_faces': len(roof), 'roof_vertices': len(verts),
                       'roof_top_z_before': round(top, 4), 'lift_m': ROOF_LIFT_M})
    elif mode == 'vpm':
        # the master's own meshes (SM_Kpp_1_Main, MainGlass, UCX_SM_Kpp_1_Main_NNN) are kept; render meshes triangulated
        tris = {}
        for o in meshes:
            if o.name.startswith('UCX_'):
                continue
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.to_mesh(o.data)
            bm.free()
            tris[o.name] = len(o.data.polygons)
        report.update({'triangles': tris, 'ucx': sorted(o.name for o in meshes if o.name.startswith('UCX_'))})
    else:
        raise SystemExit('mode must be roof or vpm')
    bpy.ops.export_scene.fbx(filepath=out, use_selection=False, add_leaf_bones=False, bake_anim=False,
                             mesh_smooth_type='FACE', path_mode='COPY', embed_textures=False)
    with open(rep, 'x', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1)
    print('EDIT-EXPORT-OK', json.dumps(report))


main()
