"""new-case: prepare an explicitly authorized, geometry-preserving R1 benchmark master.

Run in owned Blender 5.1.2 on the staged packet. Adds only exporter finish metadata
recovered from UDIMs; no geometry, UV or transform operations and no quad claim.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy

SOURCE_SHA = '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676'


def fingerprint(o):
    me = o.data
    data = {'vertices': [list(v.co) for v in me.vertices],
            'polygons': [list(p.vertices) for p in me.polygons],
            'uv': [list(p.uv) for p in me.uv_layers['UVMap'].data] if me.uv_layers else [],
            'matrix': [list(v) for v in o.matrix_world]}
    return hashlib.sha256(json.dumps(data, allow_nan=False).encode()).hexdigest()


def main(root):
    source = root / 'source/SM_Kpp_1.fbx'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA
    out = root / 'master-r1-v001.blend'
    report = root / 'preparation.json'
    if out.exists() or report.exists():
        raise ValueError('preparation outputs occupied; use a new version')
    spec = json.loads((root / 'spec.json').read_text())
    by_tile = {t['udim']: name for name, t in spec['finishes'].items()}
    names = list(spec['finishes'])
    # Blender ignores PYTHONDONTWRITEBYTECODE in its embedded interpreter. Seed
    # the exact exporter recipe cache before freezing; subsequent imports are read-only.
    sys.path.insert(0, str(root / 'jobs/TEC26-OKS/scripts'))
    import export_safety
    assert callable(export_safety.validate_atlas)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
    objects = list(bpy.context.scene.objects)
    before = {o.name: fingerprint(o) for o in objects}
    main = bpy.data.objects['SM_Kpp_1_Main']
    uv = main.data.uv_layers['UVMap']
    attr = main.data.attributes.new(name='finish', type='INT', domain='FACE')
    counts = dict.fromkeys(names, 0)
    for p in main.data.polygons:
        points = [uv.data[i].uv for i in p.loop_indices]
        cx = sum(v.x for v in points) / len(points)
        cy = sum(v.y for v in points) / len(points)
        tx, ty = math.floor(cx), math.floor(cy)
        tile = 1001 + tx + 10 * ty
        if tile not in by_tile or any(not (tx <= v.x <= tx+1 and ty <= v.y <= ty+1) for v in points):
            raise ValueError(f'face {p.index}: unsupported or crossing UDIM {tile}')
        name = by_tile[tile]
        attr.data[p.index].value = names.index(name)
        counts[name] += 1
    if any(n == 0 for n in counts.values()):
        raise ValueError(f'empty finish account: {counts}')
    main['finish_names'] = ','.join(names)
    after = {o.name: fingerprint(o) for o in objects}
    assert before == after
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    # Independently reload the new file; compare geometry, transforms and UV bytes.
    bpy.ops.wm.open_mainfile(filepath=str(out))
    reopened = {o.name: fingerprint(o) for o in bpy.context.scene.objects}
    assert before == reopened
    report.write_text(json.dumps({'source_sha256': SOURCE_SHA, 'blender': bpy.app.version_string,
        'unit_scale': bpy.context.scene.unit_settings.scale_length, 'geometry_uv_transform_unchanged': True,
        'before': before, 'reopened': reopened, 'finish_faces': counts,
        'master_type': 'triangulated R1 adapter, not a quad working master',
        'approval': 't_6a32aa3a USER DECISION 2026-11-13 18:43; D280'}, indent=2))
    print('PREPARED', json.dumps(counts))


if __name__ == '__main__':
    main(Path(sys.argv[sys.argv.index('--')+1]))
