"""new-case: element-wise copy of a KPP1 quad master for the element-wise xView/V003 checks of [D336] (#1609).

D336: inset elements (posts, rebuilt wall planes, windows) may share a delivery object but are never welded, and
"quads are judged per element (inset elements validated element-wise)". 3ds Max xView judges one object, so two
unwelded elements that touch inside one object always show as overlapping. This writes a NEW blend in which every
mesh object is split into its loose parts (one object per element, named `<object>.e<NNNN>` by descending face count);
`dt qa xview` on it is the element-wise xView. The input is never written.
    blender -b --factory-startup --python split_elements.py -- <master.blend> <new out.blend> <report.json>
"""
import json
import os
from pathlib import Path
import sys

import bpy


def main(src, out, report):
    src, out, report = Path(src).resolve(), Path(out).resolve(), Path(report).resolve()
    if len({src, out, report}) != 3:
        raise ValueError('input, output and report must be three different files')
    for p in (out, report):
        if os.path.lexists(p):
            raise ValueError(f'{p} exists; never overwrite')
    bpy.ops.wm.open_mainfile(filepath=str(src))
    rep = {'input': str(src), 'output': str(out), 'objects': {}}
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    for o in meshes:
        faces_before = len(o.data.polygons)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        parts = sorted(bpy.context.selected_objects, key=lambda x: -len(x.data.polygons))
        base = o.name
        for i, p in enumerate(parts):
            p.name = f'{base}.e{i:04d}'
        counts = [len(p.data.polygons) for p in parts]
        if sum(counts) != faces_before:
            raise ValueError(f'{base}: {sum(counts)} faces after the split, {faces_before} before')
        rep['objects'][base] = {'faces': faces_before, 'elements': len(parts), 'largest': counts[:10]}
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), copy=True)
    report.write_text(json.dumps(rep, indent=1))
    print('SPLIT', json.dumps({k: (v['faces'], v['elements']) for k, v in rep['objects'].items()}))


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    main(*args[:3])
