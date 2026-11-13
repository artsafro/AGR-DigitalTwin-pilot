"""new-case: hash-frozen native dimension autoresearch replay (#1321).

Research only. Source-location scoring follows #1302: native value AND dimension
line/extension endpoints, one-to-one handles, strict <0.5 mm/pt. Registration is
never passed to the production binder. CLI is stdout-only and opens no output,
report or .partial path. The HOLD-OUT is reported but never drives the objective.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / 'tools/research/pdf_album/dimension-autoresearch/corpus.json'
BASELINE = CORPUS.with_name('baseline.json')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf8')


def precision_guard(m: dict) -> str:
    """D277: zero predictions is separate from a numerical precision claim."""
    for key in ('found', 'correct', 'wrong', 'truth', 'missed'):
        if type(m.get(key)) is not int or m[key] < 0:
            raise ValueError(f'invalid count: {key}')
    f, c, w, t = (m[k] for k in ('found', 'correct', 'wrong', 'truth'))
    if not t or c > t or c + w != f or m['missed'] != t - c:
        raise ValueError('inconsistent/empty metrics')
    if m.get('recall') != c / t:
        raise ValueError('inconsistent recall')
    if f == 0:
        if m.get('precision') is not None:
            raise ValueError('zero predictions require precision=null')
        return 'zero_prediction_pass'
    p = m.get('precision')
    if type(p) not in (int, float) or not math.isfinite(p) or p != c / f:
        raise ValueError('inconsistent precision')
    # Integer arithmetic makes the inclusive 0.95 boundary exact.
    return 'pass' if 20 * c >= 19 * f else 'fail'


def validate_truth(truth: list[dict]) -> None:
    if not truth or len({r['handle'] for r in truth}) != len(truth):
        raise ValueError('empty truth or duplicate handle')
    for row in truth:
        if not isinstance(row['handle'], str) or not row['handle']:
            raise ValueError('invalid handle')
        if not math.isfinite(row['measurement']) or row['measurement'] <= 0:
            raise ValueError('invalid native measurement')
        if row['orientation'] not in ('horizontal', 'vertical', 'non_cardinal'):
            raise ValueError(f"unsupported orientation: {row['orientation']}")
        if row['orientation'] != 'non_cardinal':
            a, b = row['ends']
            if not all(math.isfinite(x) for x in (a, b, row['coord'])) or not a < b:
                raise ValueError('invalid native geometry')


def geometry_matches(value: dict, truth: dict) -> bool:
    if truth['orientation'] == 'non_cardinal':
        # Current production contract supports cardinal chains only. A future
        # non-cardinal implementation requires an independently registered oracle;
        # never credit an unsupported prediction by value alone.
        return False
    if value.get('orientation') != truth['orientation'] or not value.get('span'):
        return False
    try:
        points = [value['span'][k] for k in ('p0', 'p1')]
        if any(len(p) != 2 for p in points):
            return False
        if not all(math.isfinite(x) for p in points for x in p):
            return False
        axis = 0 if truth['orientation'] == 'horizontal' else 1
        return (max(abs(a - b) for a, b in zip(sorted(p[axis] for p in points), truth['ends'])) < .5
                and all(abs(p[1 - axis] - truth['coord']) < .5 for p in points))
    except (KeyError, TypeError, ValueError):
        return False


def score(values: list[dict], truth: list[dict]) -> dict:
    validate_truth(truth)
    predictions = [v for v in values if v['kind'] == 'dimension' and v['binding']['type'] != 'unbound']
    if len({v['id'] for v in predictions}) != len(predictions):
        raise ValueError('duplicate prediction id')
    used = set()
    wrong = []
    for value in predictions:
        number = value.get('value')
        valid = (value['binding']['type'] in ('axis_pair', 'level_pair')
                 and type(number) in (int, float) and math.isfinite(number))
        hits = [t for t in truth if valid and t['handle'] not in used
                and geometry_matches(value, t) and abs(t['measurement'] - number) < .5]
        if len(hits) == 1:
            used.add(hits[0]['handle'])
        else:
            wrong.append(value['id'])
    classes = {}
    rows = []
    for t in truth:
        if t['handle'] in used:
            reason = 'correct_semantic_binding'
        elif t['orientation'] == 'non_cardinal':
            reason = 'non_cardinal_chain_unsupported'
        elif abs(float(t['raw']) - t['measurement']) >= .5:
            reason = 'overrides_or_display_rounding'
        else:
            # Match the exact source-located label, including repeated values.
            associated = [v for v in values if v['kind'] == 'dimension' and v.get('raw') == t['raw']
                          and v.get('bbox') and max(abs(a-b) for a,b in zip(v['bbox'], t['bbox'])) < .01]
            if not associated:
                reason = 'text_not_found'
            elif len(associated) > 1:
                reason = 'ambiguous_text_assignment'
            elif geometry_matches(associated[0], t):
                reason = 'filtered_endpoint_identity'
            else:
                reason = 'text_found_not_bound_to_own_line'
        classes[reason] = classes.get(reason, 0) + 1
        rows.append({'handle': t['handle'], 'class': reason})
    f, c, t = len(predictions), len(used), len(truth)
    metrics = dict(found=f, correct=c, wrong=f-c, missed=t-c, truth=t,
                   precision=c/f if f else None, recall=c/t)
    return {'metrics': metrics, 'classes': classes, 'handles': rows, 'wrong_ids': wrong}


def verdict_signature(doc: dict) -> str:
    """Exact semantic axes/levels/verdicts, excluding dimension-dependent IDs."""
    levels = [{k: v for k, v in row.items() if k != 'id'}
              for row in doc['values'] if row['kind'] == 'level']
    axes = [{'id': view['id'], 'axes': view['axes']} for view in doc['views']]
    findings = [f for f in doc['findings'] if f.get('code', '').startswith(('axis_', 'level_'))]
    return digest(canonical({'levels': levels, 'axes': axes, 'findings': findings, 'passed': doc['passed']}))


def guard_document(doc: dict, expected_signature: str) -> bool:
    return (doc.get('passed') is False
            and all(v.get('measured_mm') is None for v in doc['values'])
            and all(v['scale']['status'] == 'unknown' for v in doc['views'])
            and verdict_signature(doc) == expected_signature)


def load_corpus(path: Path = CORPUS) -> dict:
    corpus = json.loads(path.read_text(encoding='utf8'))
    sheets = corpus['sheets']
    if not sheets or len({s['name'] for s in sheets}) != len(sheets):
        raise ValueError('empty corpus or duplicate sheet')
    if {s['split'] for s in sheets} != {'TUNE', 'HOLD-OUT'}:
        raise ValueError('both TUNE and HOLD-OUT required')
    seen = set()
    for sheet in sheets:
        validate_truth(sheet['truth'])
        for item in sheet['files'].values():
            p = Path(item['path']).resolve(strict=True)
            if any(p.samefile(other) for other in seen):
                raise ValueError(f'duplicate/aliased input: {p}')
            seen.add(p)
            if digest(p.read_bytes()) != item['sha256']:
                raise ValueError(f'source hash mismatch: {p}')
    return corpus


def evaluate() -> dict:
    from dt_ai.album.binding import bind_album
    corpus_bytes = CORPUS.read_bytes()
    baseline_bytes = BASELINE.read_bytes()
    baseline = json.loads(baseline_bytes)
    if baseline['corpus_sha256'] != digest(corpus_bytes):
        raise ValueError('stale baseline/corpus')
    corpus = load_corpus()
    rows = []
    total = correct = 0
    guard = True
    for sheet in corpus['sheets']:
        doc = bind_album(sheet['files']['pdf']['path'], pages=[1])
        row = score(doc['values'], sheet['truth'])
        precision = precision_guard(row['metrics'])
        stable = guard_document(doc, baseline['signatures'][sheet['name']])
        row.update(sheet=sheet['name'], split=sheet['split'], precision_guard=precision,
                   document_guard=stable)
        guard &= precision != 'fail' and stable
        if sheet['split'] == 'TUNE':
            correct += row['metrics']['correct']
            total += row['metrics']['truth']
        rows.append(row)
    # Re-hash after the complete replay: a successful binder cannot hide changed
    # DXF, registration, corpus or baseline bytes during a later sheet.
    load_corpus()
    if CORPUS.read_bytes() != corpus_bytes or BASELINE.read_bytes() != baseline_bytes:
        raise ValueError('frozen evaluator inputs changed during replay')
    return {'corpus_sha256': digest(corpus_bytes), 'sheets': rows,
            'guard': bool(guard), 'tune_recall': correct / total}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guard', action='store_true')
    args = parser.parse_args(argv)
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    if args.guard:
        return 0 if result['guard'] else 1
    print(result['tune_recall'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
