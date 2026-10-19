"""Compare native/offline readbacks to unchanged engine and copied etalons."""
import json
import statistics
import time
from collections import Counter
from pathlib import Path
import numpy as np

from dt_ai.spec.model import Spec
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump
from offline import read_fbx, read_obj
from prepare import SCRATCH, NATIVE, BENCHES, ROOT


def point_surface_max(points, triangles):
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    ab, ac = b-a, c-a
    normal = np.cross(ab, ac)
    nn = (normal*normal).sum(axis=1)
    worst = 0.0
    for p in points:
        signed = ((p-a)*normal).sum(axis=1) / np.maximum(nn, 1e-30)
        projection = p - signed[:, None]*normal
        v = projection-a
        d00, d01, d11 = (ab*ab).sum(axis=1), (ab*ac).sum(axis=1), (ac*ac).sum(axis=1)
        d20, d21 = (v*ab).sum(axis=1), (v*ac).sum(axis=1)
        den = np.maximum(d00*d11-d01*d01, 1e-30)
        u, w = (d11*d20-d01*d21)/den, (d00*d21-d01*d20)/den
        inside = (u >= -1e-9) & (w >= -1e-9) & (u+w <= 1+1e-9) & (nn > 1e-25)
        distances = np.where(inside, signed*signed*nn, np.inf)
        for x, y in [(a,b), (b,c), (c,a)]:
            edge = y-x
            t = np.clip(((p-x)*edge).sum(axis=1)/np.maximum((edge*edge).sum(axis=1),1e-30),0,1)
            distances = np.minimum(distances, ((p-(x+t[:,None]*edge))**2).sum(axis=1))
        worst = max(worst, float(np.sqrt(distances.min())))
    return worst


def compare(a, b):
    a, b = from_dump(a), from_dump(b)
    av, bv = a.vertices, b.vertices
    def near(x, y):
        return max(float(np.sqrt(((y - p)**2).sum(axis=1)).min()) for p in x)
    return {'vertices': len(av), 'triangles': len(a.triangles),
            'bbox': [av.min(axis=0).tolist(), av.max(axis=0).tolist()],
            'bbox_max_mm': float(np.max(np.abs(np.array([av.min(axis=0), av.max(axis=0)]) -
                                                  np.array([bv.min(axis=0), bv.max(axis=0)])))) * 1000,
            'symmetric_vertex_max_mm': max(near(av, bv), near(bv, av)) * 1000,
            'symmetric_sampled_surface_max_mm': max(
                point_surface_max(np.vstack([av, a.corners().mean(axis=1)]), b.corners()),
                point_surface_max(np.vstack([bv, b.corners().mean(axis=1)]), a.corners())) * 1000}


def main():
    results = []
    check_results = {}
    for bench in BENCHES:
        folder = SCRATCH / bench
        engine = json.loads((folder / 'engine.json').read_text())
        etalon = json.loads((NATIVE / (bench + '-etalon-dump.json')).read_text())
        spec = Spec.model_validate_json((folder / 'spec.json').read_text())
        tol = json.loads((folder / 'tolerances.json').read_text())['geometry']
        # Engine and mesh export intentionally carry identical level metadata.
        def check(data):
            return checks.run(from_dump(data), from_dump(etalon), spec, tol)
        check_results[bench + '-baseline'] = check(engine)
        results.append({'bench': bench, 'operation': 'engine_vs_etalon', **compare(engine, etalon)})
        for rep in range(3):
            for fmt, reader in [('fbx', read_fbx), ('obj', read_obj)]:
                stem = bench + '-r' + str(rep)
                native = json.loads((NATIVE / (stem + '-' + fmt + '-readback.json')).read_text())
                row = {'bench': bench, 'rep': rep, 'format': fmt, 'operation': 'native_vs_engine', **compare(native, engine)}
                results.append(row)
                check_results[stem + '-' + fmt] = check(native)
                times = []
                try:
                    for _ in range(3):
                        t = time.perf_counter()
                        offline = reader(NATIVE / (stem + '.' + fmt))
                        times.append(time.perf_counter() - t)
                    results.append({'bench': bench, 'rep': rep, 'format': fmt, 'operation': 'offline_vs_engine',
                                    'seconds': times, 'median_seconds': statistics.median(times),
                                    **compare(offline, engine)})
                except Exception as exc:
                    results.append({'bench': bench, 'rep': rep, 'format': fmt, 'operation': 'offline_vs_engine',
                                    'error': str(exc)})
                if fmt == 'obj' and 'offline' in locals():
                    corrected = json.loads(json.dumps(offline))
                    for m in corrected['meshes']:
                        m['vertices'] = [[x, -z, y] for x, y, z in m['vertices']]
                    results.append({'bench': bench, 'rep': rep, 'format': fmt,
                                    'operation': 'offline_yup_to_zup_vs_engine', **compare(corrected, engine)})
                results.append({'bench': bench, 'rep': rep, 'format': fmt,
                                'operation': 'native_vs_etalon', **compare(native, etalon)})
    out = ROOT / 'experiments/max-headless-agr-roundtrip'
    (out / 'comparisons.json').write_text(json.dumps(results, indent=2))
    (out / 'checker-results.json').write_text(json.dumps(check_results, indent=2))
    for row in results:
        print(json.dumps(row))
    for key, value in check_results.items():
        print(key, Counter(c['status'] for c in value['checks']))


if __name__ == '__main__':
    main()
