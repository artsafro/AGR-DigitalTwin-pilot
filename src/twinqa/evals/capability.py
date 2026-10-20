"""new-case: fail-closed B01 benchmark report grading for capability eval A.

Native Codex/DeepSeek events are deliberately not converted to Claude events:
existing procedural graders must report those unsupported transcripts as not measured.
"""
import json
import math

CHECKS = frozenset(('bbox', 'levels', 'floor_areas', 'silhouettes', 'mesh',
                    'triangle_budget', 'opening_planes', 'material_ids', 'decor', 'orientation'))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key: {key}')
        result[key] = value
    return result


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('non-finite value')
    if isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, list):
        for item in value:
            finite(item)


def load_report(path):
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    finite(value)
    if not isinstance(value, dict) or type(value.get('passed')) is not bool:
        raise ValueError('missing boolean passed')
    unknown = set(value) - {'passed', 'failed', 'not_measured', 'checks'}
    if unknown:
        raise ValueError(f'unmapped keys: {sorted(unknown)}')
    rows = value.get('checks')
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('missing checks')
    for row in rows:
        if not {'id', 'status', 'value', 'limit'} <= set(row):
            raise ValueError(f'partial check: {row.get("id")}')
        unknown = set(row) - {'id', 'status', 'value', 'limit', 'details'}
        if unknown:
            raise ValueError(f'unmapped keys: {sorted(unknown)}')
    ids = [r.get('id') for r in rows]
    if len(ids) != len(CHECKS) or any(not isinstance(i, str) for i in ids) or set(ids) != CHECKS:
        raise ValueError(f'expected exactly {sorted(CHECKS)}, got {ids}')
    if any(r.get('status') not in ('pass', 'fail', 'not_measured') for r in rows):
        raise ValueError('unsupported check status')
    for field, status in (('failed', 'fail'), ('not_measured', 'not_measured')):
        expected = [r['id'] for r in rows if r['status'] == status]
        if value.get(field) != expected:
            raise ValueError(f'inconsistent {field}')
    count = sum(r['status'] == 'pass' for r in rows)
    if value['passed'] != (count == len(CHECKS)):
        raise ValueError('inconsistent aggregate passed')
    return count


def capability_b01(evidence):
    counts, problems = [], []
    model, etalon = evidence.get('benchmark', []), evidence.get('self_check', [])
    if len(model) == len(etalon) == 1:
        if model[0].resolve().parent != etalon[0].resolve().parent:
            problems.append('reports belong to different benchmark runs')
    for name in ('benchmark', 'self_check'):
        paths = evidence.get(name, [])
        if len(paths) != 1:
            problems.append(f'{name}: expected one report')
            continue
        try:
            counts.append(load_report(paths[0]))
        except (OSError, ValueError, TypeError) as exc:
            problems.append(f'{name}: {exc}')
    total = sum(counts)
    return {'check': 'B01 all benchmark and etalon-self checks', 'expected': '20/20',
            'measured': f'{total}/20', 'passed': not problems and total == 20,
            'details': problems}
