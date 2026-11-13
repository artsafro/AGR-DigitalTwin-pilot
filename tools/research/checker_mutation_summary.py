"""new-case: issue-defined mutation score over immutable #1261 finding observations.

The issue counts any expected fail/review. The frozen optimization controller used
incremental alarms as a stricter auxiliary metric; keep both, never relabel its ledger.
This reducer does not invoke, modify or loosen a checker and does not change stimuli.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checker_mutation_guard import caught, guard, read, sha256, validate

CLASSES = {'unapplied_scale', 'baked_size', 'flipped_normals', 'self_intersections',
           'duplicate_faces', 'missing_ucx', 'wrong_ucx_gap', 'wrong_material',
           'missing_texture', 'oversized_texture', 'wrong_texel', 'wrong_name',
           'wrong_pivot', 'leftover_object', 'maf_zone_merged', 'flora_height',
           'ground_skirt_missing', 'wrong_units'}


def summarize(result):
    if not isinstance(result, dict) or not isinstance(result.get('rows'), list) or not result['rows']:
        raise ValueError('empty or unsupported result')
    unknown = set(result) - {'clean', 'rows', 'score', 'caught', 'total', 'guard', 'per_class'}
    if unknown:
        raise ValueError(f'unmapped result keys: {sorted(unknown)}')
    clean = result.get('clean')
    if not isinstance(clean, dict) or not clean:
        raise ValueError('missing clean observations')
    for values in clean.values():
        validate(values)
        for f in values:
            if f['code'].split('/', 1)[0] not in {f'V{i:03d}' for i in range(1, 18)}:
                raise ValueError(f"unmapped finding code: {f['code']}")
    classes, identities, total, hits, incremental = {}, set(), 0, 0, 0
    for row in result['rows']:
        name, etalon = row.get('class'), row.get('etalon')
        if name not in CLASSES or etalon not in clean:
            raise ValueError(f'unmapped class or etalon: {name!r}, {etalon!r}')
        identity = etalon, name
        if identity in identities:
            raise ValueError(f'duplicate mutant: {identity}')
        identities.add(identity)
        stats = classes.setdefault(name, {'caught': 0, 'missed': 0, 'not_applicable': 0,
                                          'incremental_caught': 0, 'checks': []})
        if row.get('status') == 'not_applicable' and isinstance(row.get('reason'), str) and row['reason']:
            stats['not_applicable'] += 1
            continue
        if row.get('status') != 'generated' or not isinstance(row.get('expected'), list) or not row['expected']:
            raise ValueError(f'partial or unsupported mutant: {identity}')
        findings = validate(row.get('findings'))
        for code in [*findings, *row['expected']]:
            if not isinstance(code, str) or code.split('/', 1)[0] not in {f'V{i:03d}' for i in range(1, 18)}:
                raise ValueError(f'unmapped finding code: {code!r}')
        codes = [c for c in row['expected'] if c in findings and findings[c]['status'] in {'fail','review'}]
        literal = bool(codes)
        delta = caught(clean[etalon], row['findings'], row['expected'])
        if type(row.get('caught')) is not bool or row['caught'] != delta:
            raise ValueError(f'stale incremental receipt: {identity}')
        stats['caught' if literal else 'missed'] += 1
        stats['incremental_caught'] += int(delta)
        stats['checks'] = sorted(set(stats['checks']) | set(codes))
        total += 1
        hits += int(literal)
        incremental += int(delta)
    if not total:
        raise ValueError('no generated mutants')
    score = result.get('score')
    if (type(result.get('total')) is not int or result['total'] != total
            or type(result.get('caught')) is not int or result['caught'] != incremental
            or type(score) not in (int,float) or not math.isfinite(score) or score != incremental/total):
        raise ValueError('stale totals or invalid incremental metric')
    return {'score': hits/total, 'caught': hits, 'missed': total-hits, 'total': total,
            'incremental_score': incremental/total, 'incremental_caught': incremental,
            'per_class': classes}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path)
    p.add_argument('final', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    inputs = [args.baseline.resolve(), args.final.resolve()]
    if args.output.exists() or args.output.resolve() in inputs:
        p.error('existing output or input alias; nothing written')
    before = [sha256(x) for x in inputs]
    baseline, final = [read(x) for x in inputs]
    output = {'baseline': summarize(baseline), 'final': summarize(final)}
    guard(baseline['clean'], final['clean'])
    output['guard'] = 'PASS'
    output['input_sha256'] = before
    if [sha256(x) for x in inputs] != before:
        raise ValueError('input changed during aggregation')
    with args.output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'baseline': output['baseline']['score'], 'final': output['final']['score'],
                      'caught': output['final']['caught'], 'total': output['final']['total'], 'guard': 'PASS'}))


if __name__ == '__main__':
    main()
