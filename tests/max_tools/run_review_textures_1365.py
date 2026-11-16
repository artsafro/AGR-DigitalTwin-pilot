"""new-case: isolated Max 2026 synthetic scene fixture for review gate (#1365).

Call run(repo, NEW_evidence_dir) via Python in a fresh, empty batch Max only.
Never execute this scene-building fixture in the user's live scene.
"""
import importlib.util
import json
from pathlib import Path


def run(repo, evidence):
    from pymxs import runtime as rt
    if int(rt.maxVersion()[0]) != 28000 or len(rt.objects):
        raise RuntimeError('requires fresh empty Max 2026; do not reset a user scene')
    root = Path(evidence)
    root.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location('review_textures', Path(repo) / 'tools/review/review_textures.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    path = root / 'synthetic.png'
    bitmap = rt.bitmap(256, 256, filename=str(path), color=rt.color(160, 60, 40))
    rt.save(bitmap)
    rt.close(bitmap)
    material = rt.StandardMaterial(name='SyntheticBrick', diffuseMap=rt.MultiTile())
    obj = rt.mesh(name='SyntheticBrick', vertices=[rt.Point3(0, 0, 0), rt.Point3(1, 0, 0), rt.Point3(0, 1, 0)],
                  faces=[rt.Point3(1, 2, 3)], material=material)
    scope = {'ids': [{'object': str(obj.name), 'id': 1, 'joint_m': .01, 'tile_m': .02}]}
    rt.saveMaxFile(str(root / 'synthetic-multitile-v001.max'))
    failed = gate.check_max(rt, scope)
    assert failed['status'] == 'fail', failed
    assert 'MultiTile' in failed['ids'][0]['reason'], failed
    material.diffuseMap = rt.Bitmaptexture(filename=str(path))
    rt.saveMaxFile(str(root / 'synthetic-bitmap-v002.max'))
    passed = gate.check_max(rt, scope)
    assert passed['status'] == 'pass', passed
    assert gate.check_max(rt, scope) == passed
    probes = {}
    def reject(name, declaration):
        result = gate.check_max(rt, declaration)
        assert result['status'] != 'pass', (name, result)
        probes[name] = result
    reject('unknown_object', {'ids': [dict(scope['ids'][0], object='Absent')]})
    reject('unused_id', {'ids': [dict(scope['ids'][0], id=2)]})
    reject('unmeasured_joint', {'ids': [{'object': str(obj.name), 'id': 1}]})
    reject('threshold', {'ids': [dict(scope['ids'][0], joint_m=2 / 256, tile_m=1)]})
    material.diffuseMap = rt.Bitmaptexture(filename=str(root / 'missing.png'))
    reject('missing_bitmap', scope)
    material.diffuseMap = rt.Checker()
    reject('unsupported_map', scope)
    material.diffuseMap = rt.Bitmaptexture(filename=str(path))
    multi = rt.MultiMaterial(numsubs=2)
    multi.materialIDList = rt.Array(7, 3)
    multi.materialList = rt.Array(material, rt.StandardMaterial(name='Empty'))
    obj.material = multi
    rt.setFaceMatID(obj, 1, 7)
    sparse = {'ids': [dict(scope['ids'][0], id=7)]}
    probes['sparse_id'] = gate.check_max(rt, sparse)
    assert probes['sparse_id']['status'] == 'pass', probes
    rt.setFaceMatID(obj, 1, 8)
    reject('unmapped_id', {'ids': [dict(scope['ids'][0], id=8)]})
    rt.setFaceMatID(obj, 1, 7)
    multi.materialIDList = rt.Array(7, 7)
    reject('duplicate_mapping', sparse)
    for name, declaration in [('empty', {'ids': []}), ('partial', {'ids': [{'id': 1}]}),
                              ('duplicate', {'ids': scope['ids'] * 2}),
                              ('nan', {'ids': [dict(scope['ids'][0], joint_m=float('nan'))]}),
                              ('inf', {'ids': [dict(scope['ids'][0], tile_m=float('inf'))]})]:
        try:
            gate.check_max(rt, declaration)
        except ValueError as exc:
            probes[name] = {'status': 'error', 'reason': str(exc)}
        else:
            raise AssertionError(name)
    result = {'application': '3ds Max', 'version': str(rt.maxVersion()), 'units': str(rt.units.SystemType),
              'synthetic': True, 'multitile': failed, 'bitmap': passed, 'probes': probes}
    gate.write_report(root / 'native-max.json', result, [path])
    return json.dumps(result)
