"""Independent offline comparison of complete fresh native readbacks."""
import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
import numpy as np
from dt_ai.spec.model import Spec
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump


def load(path):
    return json.loads(path.read_text())


def correspondence(actual, expected, tolerance_m=1e-5):
    """Complete oriented triangle bijection; fail on missing/ambiguous candidates.

    Cyclic rotations allowed, reversed winding forbidden. The 0.01 mm matching
    budget is an experiment control, not a regulatory threshold.
    """
    ac, ec = actual.corners(), expected.corners()
    remaining = set(range(len(ac)))
    matches, maximum = [], 0.0
    for triangle in ec:
        distances = np.min([np.linalg.norm(ac-np.roll(triangle, i, axis=0), axis=2).max(axis=1)
                            for i in range(3)], axis=0)
        candidates = [i for i in remaining if distances[i] <= tolerance_m]
        if len(candidates) != 1:
            return None, None
        index = candidates[0]
        remaining.remove(index)
        matches.append(index)
        maximum = max(maximum, float(distances[index]))
    return (matches, maximum*1000) if not remaining else (None, None)


def compare(data, reference):
    a, b = from_dump(data), from_dump(reference)
    av, bv = a.vertices, b.vertices
    def nearest(x, y):
        return max(float(np.sqrt(((y-v)**2).sum(axis=1)).min()) for v in x)
    areas = np.linalg.norm(np.cross(a.corners()[:, 1]-a.corners()[:, 0],
                                    a.corners()[:, 2]-a.corners()[:, 0]), axis=1)/2
    b_areas = np.linalg.norm(np.cross(b.corners()[:, 1]-b.corners()[:, 0],
                                      b.corners()[:, 2]-b.corners()[:, 0]), axis=1)/2
    face_ids = [mid for m in data['meshes'] for mid in m['material_ids']]
    ref_ids = [mid for m in reference['meshes'] for mid in m['material_ids']]
    matches, corner_max = correspondence(a, b)
    total = len(b.triangles)
    correct = np.array(face_ids)[matches] == np.array(ref_ids) if matches is not None else np.zeros(total, dtype=bool)
    retained = int(correct.sum())
    correct_area = float(b_areas[correct].sum())
    helpers_a = {h['name']: np.array(h['location']) for h in data['helpers']}
    helpers_b = {h['name']: np.array(h['location']) for h in reference['helpers']}
    helper_names_equal = helpers_a.keys() == helpers_b.keys()
    helper_max_mm = max(float(np.linalg.norm(helpers_a[k]-helpers_b[k]))*1000 for k in helpers_b) if helper_names_equal and helpers_b else None
    return {'vertices': len(av), 'triangles': len(a.triangles),
            'vertex_delta': len(av)-len(bv), 'triangle_delta': len(a.triangles)-len(b.triangles),
            'bbox_max_mm': float(np.abs(np.array([av.min(0), av.max(0)])-np.array([bv.min(0), bv.max(0)])).max())*1000,
            'symmetric_nearest_vertex_max_mm': max(nearest(av,bv),nearest(bv,av))*1000,
            'geometry_winding_equal': matches is not None, 'bijective_corner_max_mm': corner_max,
            'finish_triangles_correct': retained, 'finish_triangles_total': total,
            'finish_area_correct_percent': correct_area/float(b_areas.sum())*100,
            'material_histogram': dict(Counter(face_ids)),
            'reference_material_histogram': dict(Counter(ref_ids)),
            'area_by_id_m2': {str(mid): float(areas[np.array(face_ids)==mid].sum()) for mid in sorted(set(face_ids))},
            'helpers_names_equal': helper_names_equal, 'helpers_max_mm': helper_max_mm}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    base = args.run
    inputs = load(base/'inputs.json')
    for item in inputs['sources']:
        for key in ['source', 'copy']:
            assert hashlib.sha256(Path(item[key]).read_bytes()).hexdigest() == item['sha256']
    rows, engine_checks = [], []
    for bench in ['bench-b01-box', 'bench-b02-corner-niche']:
        engine = load(base/bench/'engine.json')
        etalon = load(base/'readback'/(bench+'-etalon.json'))
        spec = Spec.model_validate_json((base/bench/'spec.json').read_text())
        tol = load(base/bench/'tolerances.json')['geometry']
        def check(data):
            result = checks.run(from_dump(data), from_dump(etalon), spec, tol)
            return [{'id': c['id'], 'status': c['status'], 'value': c['value'], 'limit': c['limit']} for c in result['checks']]
        engine_checks.append({'bench': bench, 'checks': check(engine)})
        for arm in ['baseline', 'prototype']:
            timings = [r for r in load(base/arm/'results.json')['rows'] if r['bench']==bench]
            for rep in range(3):
                data = load(base/'readback'/(bench+'-'+arm+'-r'+str(rep)+'.json'))
                fbx = base/arm/(bench+'-r'+str(rep)+'.fbx')
                assert fbx.read_bytes()[:23] == b'Kaydara FBX Binary  \x00\x1a\x00'
                assert int.from_bytes(fbx.read_bytes()[23:27], 'little') == 7400
                rows.append({'bench': bench, 'arm': arm, 'rep': rep,
                             'sha256': hashlib.sha256(fbx.read_bytes()).hexdigest(),
                             'checks': check(data), **compare(data,engine),
                             'create_seconds': timings[rep]['create_seconds'],
                             'export_seconds': timings[rep]['export_seconds']})
    summary = []
    for bench in ['bench-b01-box', 'bench-b02-corner-niche']:
        for arm in ['baseline', 'prototype']:
            group = [r for r in rows if r['bench']==bench and r['arm']==arm]
            summary.append({'bench': bench, 'arm': arm,
                            'median_create_s': statistics.median(r['create_seconds'] for r in group),
                            'median_export_s': statistics.median(r['export_seconds'] for r in group),
                            'median_create_export_s': statistics.median(r['create_seconds']+r['export_seconds'] for r in group),
                            'checks_pass_each': [sum(c['status']=='pass' for c in r['checks']) for r in group],
                            'finish_correct_each': [r['finish_triangles_correct'] for r in group],
                            'finish_total': group[0]['finish_triangles_total'],
                            'max_vertex_mm': max(r['symmetric_nearest_vertex_max_mm'] for r in group),
                            'max_bbox_mm': max(r['bbox_max_mm'] for r in group)})
    evidence = {'inputs': inputs, 'engine_checks': engine_checks, 'summary': summary,
                'rows': rows, 'native': {mode: load(base/mode/'results.json') for mode in ['baseline','prototype','readback']},
                'wrappers': {mode: {k: load(base/(mode+'-wrapper.json')).get(k) for k in ['status','exit_code','seconds','warnings']} for mode in ['baseline','prototype','readback']},
                'sources_unchanged': True, 'delivery_passed': False}
    # Compact lines keep machine evidence readable without thousands of repeated lines.
    with args.out.open('x') as f:
        f.write(json.dumps(evidence, separators=(',', ':'))+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
