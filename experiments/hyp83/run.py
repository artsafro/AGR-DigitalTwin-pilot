"""Run with uv run python -m experiments.hyp83.run; writes local tracked evidence."""
import hashlib
import json
import platform
import statistics
import sys
from pathlib import Path
from time import perf_counter_ns
import numpy as np
from .compare import baseline, candidate
from .fixtures import CASES, FACES, ORDERS, arrays


def main():
    root = Path(__file__).resolve().parents[2]
    records = []
    for case in CASES:
        for permutation in range(3):
            reference, observed = arrays(case, permutation)
            for name, method in [('baseline', baseline), ('candidate', candidate)]:
                start = perf_counter_ns()
                result = method(reference, observed, FACES, case.faces)
                elapsed = perf_counter_ns() - start
                records.append(dict(
                    case=case.name, permutation=permutation, method=name,
                    expected=case.expected, accepted=bool(result.accepted),
                    cardinality=result.cardinality,
                    cardinality_kind='reusable_assignments' if name == 'baseline' else 'maximum_matching',
                    distinct_reference_indices=len(set(i for i in result.assignment if i >= 0)),
                    eligible_edges=result.edges, assignment=result.assignment, runtime_ns=elapsed,
                    faces=len(case.faces), degrees={'3': 4}, corners=len(observed),
                ))
    summaries = {}
    for name in ('baseline', 'candidate'):
        selected = [r for r in records if r['method'] == name]
        summaries[name] = dict(
            # Positive means clean/accepted.
            confusion={key: sum(r['expected'] == truth and r['accepted'] == verdict
                                for r in selected)
                       for key, truth, verdict in [('TP', True, True), ('FN', True, False),
                                                   ('FP', False, True), ('TN', False, False)]},
            per_case_median_ns={c.name: statistics.median(
                r['runtime_ns'] for r in selected if r['case'] == c.name) for c in CASES},
            overall_median_ns=statistics.median(r['runtime_ns'] for r in selected),
        )
    evidence = dict(
        synthetic=True, delivery_passed=False,
        python=sys.version, numpy=np.__version__, platform=platform.platform(),
        xyz_radius_m=0.002, uv_max_component_strict_limit=2e-6,
        sha256={str(p): hashlib.sha256((root / p).read_bytes()).hexdigest()
                for p in ['tools/check_facades_max_roundtrip.py', 'experiments/hyp83/fixtures.py',
                          'experiments/hyp83/compare.py']},
        frozen_cases=[dict(name=c.name, expected=c.expected, reference=c.reference,
                           observed=c.observed, faces=c.faces) for c in CASES],
        orders=ORDERS, records=records, summaries=summaries,
    )
    destination = Path(__file__).with_name('results.json')
    destination.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summaries, indent=2))
    assert summaries['baseline']['confusion']['FP'] >= 3
    assert summaries['candidate']['confusion'] == dict(TP=12, FN=0, FP=0, TN=12)


if __name__ == '__main__':
    main()
