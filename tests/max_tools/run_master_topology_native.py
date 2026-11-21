"""new-case: native synthetic witnesses for the pre-export master check (#1420).

Run with dcc_batch.py max --file ABSOLUTE_THIS_FILE --card t_c1559f80.
Writes only a new JSON receipt in this worktree's tmp/; never saves a scene.
"""
import importlib.util
import json
import math
from pathlib import Path


def main():
    from pymxs import runtime as rt
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('agr_master_native_test', root / 'adapters/max/agr_tools/runtime.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert not str(rt.maxFileName), 'synthetic test requires an empty headless document'
    print('MASTER_SYNTHETIC_START', flush=True)
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0
    rows = []
    for degree in (3, 4, 5):
        n = rt.convertToPoly(rt.Plane(length=1, width=1, lengthsegs=1, widthsegs=1))
        rt.polyop.deleteFaces(n, rt.execute('#{1}'), delIsoVerts=True)
        rt.polyop.collapseDeadStructs(n)
        n.name = 'synthetic_degree_' + str(degree)
        ids = [rt.polyop.createVert(n, rt.point3(math.cos(i * 2 * math.pi / degree),
                                                math.sin(i * 2 * math.pi / degree), 0))
               for i in range(degree)]
        rt.polyop.createPolygon(n, rt.Array(*ids))
        assert int(rt.polyop.getNumFaces(n)) == 1
        rt.select(n)
        before = str(rt.polyop.getFaceVerts(n, 1)), list(rt.selection), len(list(rt.objects))
        result = mod.master_topology([n])
        assert result['status'] == ('fail' if degree == 5 else 'pass')
        obj = result['objects'][0]
        assert obj['faces'] == 1 and obj['triangle_share'] == (1 if degree == 3 else 0)
        assert before == (str(rt.polyop.getFaceVerts(n, 1)), list(rt.selection), len(list(rt.objects)))
        rows.append(result)
    with (root / 'tmp/master-topology-native-synthetic.json').open('x', encoding='utf-8') as fh:
        json.dump({'synthetic': True, 'version': str(rt.maxVersion()),
                   'units': str(rt.units.SystemType), 'results': rows}, fh, indent=2)
    print('MASTER_SYNTHETIC_PASS 3/3; selection/topology/node inventory unchanged 3/3')


if __name__ == '__main__':
    main()
