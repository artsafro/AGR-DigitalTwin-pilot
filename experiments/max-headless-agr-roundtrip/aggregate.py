"""Aggregate retained measurements; no synthetic benchmark results."""
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from analyze import compare
from prepare import ROOT, SCRATCH, NATIVE, BENCHES
from dt_ai.spec.model import Spec
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump

OUT = ROOT / 'experiments/max-headless-agr-roundtrip'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    sessions = {}
    for p in sorted(OUT.glob('*-session.json')):
        d = read(p)
        sessions[p.stem] = {k: d[k] for k in ['status', 'exit_code', 'seconds', 'warnings']}
        sessions[p.stem]['markers'] = [line for line in d['log'].splitlines()
                                      if line.startswith('AGR_') or line.startswith('MAX_COMPONENT_')]
    native = read(NATIVE / 'native-results.json')
    grouped = defaultdict(list)
    for r in native['rows']:
        grouped['/'.join([r['bench'], r['operation'], r.get('format', '')])].append(r['seconds'])
    medians = {k: {'runs': v, 'median_seconds': statistics.median(v)} for k, v in grouped.items()}
    existing_seconds = [sessions[k]['seconds'] for k in ['existing-configured-session',
                       'existing-repeat1-session', 'existing-repeat2-session']]
    batch_seconds = [sessions['batched-' + str(i) + '-session']['seconds'] for i in range(3)]
    baseline_median = statistics.median(existing_seconds)
    batch_median = statistics.median(batch_seconds)
    fresh = read(NATIVE / 'readback-set-0/fresh-results.json')
    fresh_rows = []
    for row in fresh:
        path = Path(row['path'])
        data = read(row['dump'])
        etalon = read(NATIVE / 'bench-b01-box-etalon-dump.json')
        is_existing = path.parent.name.startswith(('existing-', 'batched-'))
        if is_existing:
            ref = etalon
        else:
            bench = next(b for b in BENCHES if path.name.startswith(b))
            ref = read(SCRATCH / bench / 'engine.json')
        c = compare(data, ref)
        if is_existing:
            spec = Spec.model_validate_json((SCRATCH / 'bench-b01-box/spec.json').read_text())
            tol = read(SCRATCH / 'bench-b01-box/tolerances.json')['geometry']
            report = checks.run(from_dump(data), from_dump(ref), spec, tol)
            c['checker_statuses'] = {x['id']: x['status'] for x in report['checks']}
        c.update({'file': str(path.relative_to(NATIVE)), 'seconds_import_dump': row['seconds'],
                  'reference': 'B01 etalon' if is_existing else bench + ' engine',
                  'material_ids': sorted({i for m in data['meshes'] for i in m['material_ids']})})
        fresh_rows.append(c)
    hashes = {str(p.relative_to(NATIVE)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(NATIVE.rglob('*.fbx'))}
    result = {'native': native, 'sessions': sessions,
              'pings': [{k: read(OUT / ('ping-' + str(i) + '.json'))[k] for k in ['seconds','status','exit_code']} for i in range(3)],
              'operation_medians': medians,
              'same_input_batch_comparison': {'isolated_seconds': existing_seconds, 'batch_three_jobs_seconds': batch_seconds,
                'isolated_median_seconds_per_job': baseline_median,
                'batched_median_seconds_per_three_jobs': batch_median,
                'batched_seconds_per_job': batch_median/3,
                'speedup_per_job': baseline_median/(batch_median/3)},
              'fresh_readback': fresh_rows, 'fbx_sha256': hashes,
              'baseline_tests': read(OUT / 'baseline-tests-repaired.json'),
              'final_tests': read(OUT / 'final-tests.json'),
              'delivery_passed': False}
    (OUT / 'evidence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['same_input_batch_comparison'], indent=2))
    print(json.dumps(medians, indent=2))
    print('fresh count', len(fresh_rows), 'existing/batch exact surface max mm',
          max(r['symmetric_sampled_surface_max_mm'] for r in fresh_rows if r['reference']=='B01 etalon'))
    print('fresh', [(r['file'], r['vertices'], r['triangles'], r['material_ids']) for r in fresh_rows])


if __name__ == '__main__':
    main()
