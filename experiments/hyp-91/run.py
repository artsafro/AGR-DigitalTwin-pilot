"""Small stdlib-only, hash-locked experiment; baseline RED precedes comparison.

Run with python -B experiments/hyp-91/run.py baseline|compare.
Outputs are exclusive-create: never silently replace evidence.
"""
import ast
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter

from freeze import CONTROL_NAMES, ROOT, HERE, control_nodes, sha

sys.path.insert(0, str(ROOT))
from technical_library.mesh_audit.core import inspect_mesh


def save(name, value):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def load():
    path = HERE / 'frozen.json'
    assert sha(path) == (HERE / 'frozen.sha256').read_text().split()[0], 'Input hash changed'
    frozen = json.loads(path.read_text())
    for source, digest in frozen['snapshot']['source_sha256'].items():
        assert sha(ROOT / source) == digest, f'Source changed: {source}'
    return frozen


def tracked_controls():
    # Compile only the exact three tracked functions, not the texture imports.
    scope = {'inspect_mesh': inspect_mesh}
    exec(compile(ast.Module(body=control_nodes(), type_ignores=[]),
                 'tests/test_shared_library.py', 'exec'), scope)
    for name in CONTROL_NAMES[1:]:
        scope[name]()
    return dict(passed=2, failed=0, names=CONTROL_NAMES[1:])


def confusion(cases, counts):
    table = dict(TN=0, FP=0, FN=0, TP=0)
    for case, actual in zip(cases, counts):
        key = ('TP' if actual else 'FN') if case['expected'] else ('FP' if actual else 'TN')
        table[key] += 1
    return table


def main(mode):
    frozen = load()
    cases = frozen['cases']
    controls = tracked_controls()
    provenance = dict(input_sha256=sha(HERE / 'frozen.json'), python=sys.version,
                      platform=platform.platform(), snapshot=frozen['snapshot'],
                      harness_sha256={p: sha(HERE / p) for p in ('freeze.py', 'run.py', 'candidate.py')},
                      delivery_passed=False)
    if mode == 'baseline':
        records = []
        for case in cases:
            report = inspect_mesh(case['vertices'], case['faces'])
            records.append(dict(id=case['id'], expected=case['expected'],
                                actual=report['self_intersecting_polygons'], report=report))
        failures = [r['id'] for r in records if r['expected'] != r['actual']]
        result = dict(provenance=provenance, tracked_controls=controls, cases=records,
                      passed=len(cases)-len(failures), failed=len(failures), failures=failures,
                      confusion=confusion(cases, [r['actual'] for r in records]))
        save('red.json', result)
        print(f"RED baseline: {result['passed']} passed, {result['failed']} failed; tracked controls 2/2")
        return bool(failures)

    from candidate import count, proper_crossings, TOLERANCE_M2
    assert TOLERANCE_M2 == frozen['orientation_tolerance_m2']
    assert (HERE / 'red.json').exists(), 'Run unchanged-baseline RED first'
    repetitions = []
    for repetition in range(frozen['repetitions']):
        start = perf_counter()
        reports = [inspect_mesh(c['vertices'], c['faces']) for c in cases]
        baseline_seconds = perf_counter() - start
        start = perf_counter()
        candidate_counts = [count(c['vertices'], c['faces']) for c in cases]
        candidate_seconds = perf_counter() - start
        records = []
        for case, report, actual in zip(cases, reports, candidate_counts):
            baseline_faces = [inspect_mesh(case['vertices'], [f])['self_intersecting_polygons']
                              for f in case['faces']]
            candidate_faces = [proper_crossings(case['vertices'], f) for f in case['faces']]
            assert sum(baseline_faces) == report['self_intersecting_polygons']
            assert sum(candidate_faces) == actual
            records.append(dict(id=case['id'], expected=case['expected'],
                                baseline=report['self_intersecting_polygons'], candidate=actual,
                                baseline_faces=baseline_faces, candidate_faces=candidate_faces,
                                baseline_report=report))
        repetitions.append(dict(repetition=repetition+1, cases=records,
                                baseline_confusion=confusion(cases, [r['baseline'] for r in records]),
                                candidate_confusion=confusion(cases, candidate_counts),
                                baseline_seconds=baseline_seconds, candidate_seconds=candidate_seconds))
    first = repetitions[0]['cases']
    failures = [dict(repetition=rep['repetition'], **r) for rep in repetitions for r in rep['cases']
                if r['candidate'] != r['expected']]
    clean_concave_fp = [r['id'] for c, r in zip(cases, first)
                        if c['outline'] in ('L', 'U', 'arrow') and r['baseline'] != 0]
    invariance = {}
    baseline_invariance = {}
    for outline in frozen['outlines']:
        name = outline['name']
        group = [r for c,r in zip(cases, first) if c['outline'] == name]
        invariance[name] = len({r['candidate'] for r in group}) == 1
        baseline_invariance[name] = len({r['baseline'] for r in group}) == 1
    identical = sum(rep['cases'] == first for rep in repetitions)
    controls_preserved = all(r['candidate'] == r['baseline'] == r['expected']
                             and r['candidate_faces'] == r['baseline_faces']
                             for r in first[-2:])
    confirmed = (bool(clean_concave_fp) and not failures and all(invariance.values())
                 and identical == 3 and controls_preserved)
    result = dict(provenance=provenance, tracked_controls=controls, repetitions=repetitions,
                  candidate_failures=failures, baseline_clean_concave_counterexamples=clean_concave_fp,
                  candidate_invariance=invariance, baseline_invariance=baseline_invariance,
                  identical_repetitions=identical, controls_preserved=controls_preserved,
                  median_seconds=dict(baseline=median(r['baseline_seconds'] for r in repetitions),
                                      candidate=median(r['candidate_seconds'] for r in repetitions)),
                  verdict='confirmed' if confirmed else 'rejected', delivery_passed=False)
    save('results.json', result)
    print(f"{result['verdict'].upper()}: {len(cases)*3-len(failures)}/{len(cases)*3} candidate checks; "
          f"controls 2/2 x3; identical repetitions {identical}/3; baseline concave FP {len(clean_concave_fp)}")
    print('Median seconds:', result['median_seconds'])
    return not confirmed


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('baseline', 'compare'):
        raise SystemExit('Usage: run.py baseline|compare')
    raise SystemExit(main(sys.argv[1]))
