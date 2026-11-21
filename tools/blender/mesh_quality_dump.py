"""new-case: read-only master geometry dump for the OKS mesh quality score (#1616).

Blender 5.1.2; launched by tools/qa/mesh_quality_score.py (autoexec disabled).
Writes world-space vertices, polygon vertex indices and polygon material names of every
evaluated mesh object BEFORE triangulation. Active triangulation modifiers are refused.
Non-mesh objects are reported in ``dropped`` with their reason; nothing is saved.
Opt-in --rejoin-rectangles reconstructs coplanar rectangle-like triangle pairs within
1 degree for calibration only (#1634); material boundaries stay, UV delimiters do not.
"""
import json
import math
import sys

import bpy


def dump(rejoin_rectangles=False):
    rows, dropped = [], []
    normalized = []
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if obj.type != 'MESH':
            dropped.append({'name': obj.name, 'type': obj.type, 'reason': 'not a mesh object'})
            continue
        for mod in obj.modifiers:
            if mod.type == 'TRIANGULATE' and mod.show_viewport:
                raise ValueError(f'{obj.name}: active triangulation modifier {mod.name}')
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        try:
            world_mesh = rejoin_rectangles and any(len(p.vertices) == 3 for p in mesh.polygons)
            if world_mesh:
                # Same diagnostic representation as #1618; never edits the source object.
                import bmesh
                bm = bmesh.new()
                try:
                    bm.from_mesh(mesh)
                    bm.transform(obj.matrix_world)
                    before = len(bm.faces)
                    bmesh.ops.join_triangles(
                        bm, faces=bm.faces[:], angle_face_threshold=math.radians(1),
                        angle_shape_threshold=math.radians(1), cmp_seam=False, cmp_sharp=False,
                        cmp_uvs=False, cmp_vcols=False, cmp_materials=True)
                    normalized.append({'name': obj.name, 'faces_before': before,
                                       'faces_after': len(bm.faces)})
                    bm.to_mesh(mesh)
                finally:
                    bm.free()
            mw = obj.matrix_world
            verts = []
            for v in mesh.vertices:
                co = v.co if world_mesh else mw @ v.co
                if not all(math.isfinite(c) for c in co):
                    raise ValueError('non-finite master vertex: ' + obj.name)
                verts.append([round(co.x, 6), round(co.y, 6), round(co.z, 6)])
            slots = [s.material.name if s.material else '' for s in obj.material_slots]
            mats = []
            for p in mesh.polygons:
                mats.append(slots[p.material_index] if p.material_index < len(slots) else '')
            rows.append({'name': obj.name, 'verts': verts,
                         'faces': [list(p.vertices) for p in mesh.polygons], 'materials': mats})
        finally:
            evaluated.to_mesh_clear()
    result = {'objects': rows, 'dropped': dropped, 'blender': bpy.app.version_string}
    if rejoin_rectangles:
        result['normalization'] = {'mode': 'rejoin_rectangles_1deg', 'objects': normalized,
                                   'material_boundaries': 'preserved',
                                   'uv_boundaries': 'ignored for geometry diagnostics only'}
    return result


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    src, dest = args[:2]
    if args[2:] not in ([], ['--rejoin-rectangles']):
        raise ValueError('unsupported dump arguments: ' + repr(args[2:]))
    low = src.lower()
    if low.endswith('.blend'):
        bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if low.endswith('.fbx'):
            bpy.ops.import_scene.fbx(filepath=src)
        elif low.endswith('.obj'):
            bpy.ops.wm.obj_import(filepath=src, forward_axis='Y', up_axis='Z')
        else:
            raise ValueError('unsupported master format: ' + src)
    result = dump(rejoin_rectangles=bool(args[2:]))
    with open(dest, 'x', encoding='utf-8') as fh:
        json.dump(result, fh, allow_nan=False)


if __name__ == '__main__':
    main()
