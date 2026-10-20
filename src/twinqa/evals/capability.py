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
    metadata = {'model', 'etalon', 'spec', 'tolerances'}
    unknown = set(value) - {'passed', 'failed', 'not_measured', 'checks'} - metadata
    for key in metadata & set(value):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f'invalid provenance: {key}')
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
    counts, problems, supplementary = [], [], []
    models, etalons = evidence.get('benchmark', []), evidence.get('self_check', [])
    if len(etalons) != 1:
        problems.append('self_check: expected one report')
    else:
        paired = [p for p in models if p.resolve().parent == etalons[0].resolve().parent]
        if len(paired) != 1:
            problems.append('benchmark: expected one report beside etalon-self')
        for name, paths in (('benchmark', paired), ('self_check', etalons)):
            for path in paths:
                try:
                    counts.append(load_report(path))
                except (OSError, ValueError, TypeError) as exc:
                    problems.append(f'{name}: {exc}')
        for path in models:
            if path in paired:
                continue
            try:
                count = load_report(path)
                supplementary.append({'path': str(path), 'measured': f'{count}/10'})
                if count != 10:
                    problems.append(f'supplementary report failed: {path}')
            except (OSError, ValueError, TypeError) as exc:
                problems.append(f'supplementary report {path}: {exc}')
    total = sum(counts)
    return {'check': 'B01 all benchmark and etalon-self checks', 'expected': '20/20',
            'measured': f'{total}/20', 'passed': not problems and total == 20,
            'details': problems, 'supplementary': supplementary}
