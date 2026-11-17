"""new-case: OBSERVE candidate hook for the [D336] split - un-weld parts pressed into the body (#1616).

Blender 5.1.2 headless:
  blender -b --factory-startup --python split_welded_parts_candidate.py -- SRC.blend OUT_DIR ANGLE_DEG
Splits every concave crease edge (dihedral > ANGLE_DEG, the same test as the score's ``weld_share``)
of the non-glass, non-UCX meshes, so a welded post/frame becomes its own inset element; positions are
unchanged. Writes OUT_DIR/master.fbx (quads kept, not a delivery) and OUT_DIR/hook.json. OUT_DIR must
be new; the source is opened read-only and never saved.
"""
import json
import math
import os
import re
import sys

import bmesh
import bpy


def main():
    src, out_dir, angle = sys.argv[sys.argv.index('--') + 1:]
    angle = float(angle)
    if not math.isfinite(angle) or not 0 < angle < 180:
        raise SystemExit('angle must be in (0, 180)')
    if os.path.exists(out_dir):
        raise SystemExit('output exists; use a new round directory: ' + out_dir)
    if os.path.abspath(out_dir).lower().startswith(os.path.abspath(os.path.dirname(src)).lower() + os.sep):
        raise SystemExit('output inside the source directory')
    os.makedirs(out_dir)
    bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
    cos_t = math.cos(math.radians(angle))
    stats = {}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or obj.name.startswith('UCX_') or re.search(r'(?i)glass', obj.name):
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.normal_update()
        split = []
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            f1, f2 = e.link_faces
            n1 = f1.normal
            if n1.dot(f2.normal) < cos_t and n1.dot(f2.calc_center_median() - f1.calc_center_median()) > 1e-9:
                split.append(e)
        if split:
            bmesh.ops.split_edges(bm, edges=split)
        bm.to_mesh(obj.data)
        bm.free()
        stats[obj.name] = len(split)
    fbx = os.path.join(out_dir, 'master.fbx')
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=False, object_types={'MESH'}, use_triangles=False,
                             apply_unit_scale=True, bake_space_transform=False)
    with open(os.path.join(out_dir, 'hook.json'), 'x', encoding='utf-8') as fh:
        json.dump({'hook': 'split_welded_parts', 'angle_deg': angle, 'split_edges': stats,
                   'source': src, 'blender': bpy.app.version_string}, fh, indent=2)


if __name__ == '__main__':
    main()
