"""new-case: evidence-preserving PDF/model mode-A diagnostic comparison [D274].

Reusable normalized-observation seam, not an automatic raster-to-BIM claim.
Input observations must already share a documented facade frame in metres.
Neither source is corrected and ``passed`` is always false (architect review).
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
import re

CATEGORIES = {'level': 'm', 'axis': 'm', 'opening_size': 'm',
              'opening_count': 'count', 'finish': 'text', 'mark': 'text'}
STATUSES = ('match', 'mismatch', 'needs manual check')


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'non-finite or non-numeric value: {value!r}')
    return value


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f'unsupported or missing keys: {value!r}')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('nonempty text required')


def _records(records, pdf):
    if not isinstance(records, list) or (pdf and not records):
        raise ValueError('observations must be a list; PDF facts cannot be empty')
    ids = set()
    for r in records:
        required = ('id', 'category', 'mark', 'facade', 'position_m', 'value', 'unit', 'verified', 'evidence')
        _keys(r, required + (('tolerance', 'calibrated') if pdf else ('object_id', 'object_name')), ('note',))
        for k in ('id', 'mark', 'facade') + (() if pdf else ('object_id', 'object_name')):
            _text(r[k])
        if r['id'] in ids:
            raise ValueError(f'duplicate observation id {r["id"]}')
        ids.add(r['id'])
        if r['category'] not in CATEGORIES:
            raise ValueError(f'unmapped category {r["category"]}')
        if r['unit'] != CATEGORIES[r['category']]:
            raise ValueError(f'unsupported unit for {r["id"]}: {r["unit"]}')
        if type(r['verified']) is not bool or (pdf and type(r['calibrated']) is not bool):
            raise ValueError('verified/calibrated must be bool')
        if r['position_m'] is not None:
            if not isinstance(r['position_m'], list) or len(r['position_m']) != 2:
                raise ValueError('position_m must be [u,z] in documented frame or null')
            for x in r['position_m']:
                _number(x)
        if r['value'] is not None:
            if r['unit'] == 'text':
                _text(r['value'])
            else:
                _number(r['value'])
                if r['unit'] == 'count' and (type(r['value']) is not int or r['value'] < 0):
                    raise ValueError('count must be a nonnegative integer')
                if r['category'] == 'opening_size' and r['value'] <= 0:
                    raise ValueError('opening size must be positive')
        if pdf:
            tol = _number(r['tolerance'])
            if (r['unit'] == 'm' and tol <= 0) or (r['unit'] != 'm' and tol != 0):
                raise ValueError('metric tolerance must be positive; count/text tolerance must be zero')
        e = r['evidence']
        common = ('path', 'sha256', 'method')
        _keys(e, common + (('page', 'sheet', 'bbox') if pdf else ('locator',)))
        for k in common + (('sheet',) if pdf else ('locator',)):
            _text(e[k])
        if not re.fullmatch('[0-9a-f]{64}', e['sha256']):
            raise ValueError('invalid evidence SHA256')
        if pdf:
            if type(e['page']) is not int or e['page'] < 1:
                raise ValueError('physical PDF page must be >= 1')
            box = e['bbox']
            if not isinstance(box, list) or len(box) != 4:
                raise ValueError('missing PDF bbox')
            for x in box:
                _number(x)
            if not (0 <= box[0] < box[2] and 0 <= box[1] < box[3]):
                raise ValueError('invalid PDF bbox')


def validate(bundle):
    """Fail closed on malformed facts; explicit nulls remain manual checks."""
    _keys(bundle, ('schema', 'trust_rule', 'frame', 'pdf', 'models', 'match_tolerance_m'))
    if bundle['schema'] != 'album-model-audit-input/1':
        raise ValueError('unsupported audit input schema')
    if not isinstance(bundle['trust_rule'], str) or not re.fullmatch(r'D\d+', bundle['trust_rule']):
        raise ValueError('trust rule citation required')
    _keys(bundle['frame'], ('name', 'placement'))
    for x in bundle['frame'].values():
        _text(x)
    if _number(bundle['match_tolerance_m']) <= 0:
        raise ValueError('positive geometry matching tolerance required')
    _records(bundle['pdf'], True)
    if not isinstance(bundle['models'], list) or not bundle['models']:
        raise ValueError('at least one model required')
    ids = set()
    for model in bundle['models']:
        _keys(model, ('id', 'observations'))
        _text(model['id'])
        if model['id'] in ids:
            raise ValueError(f'duplicate model {model["id"]}')
        ids.add(model['id'])
        _records(model['observations'], False)


def compare(bundle: dict) -> dict:
    """Compare source facts with one uniquely located, same-mark model observation."""
    validate(bundle)
    rows, unmatched = [], []
    for model in bundle["models"]:
        used = set()
        for fact in bundle["pdf"]:
            candidates = [o for o in model["observations"]
                          if (o["category"], o["mark"], o["facade"]) ==
                          (fact["category"], fact["mark"], fact["facade"])
                          and o['position_m'] is not None and fact['position_m'] is not None
                          and math.dist(o['position_m'], fact['position_m']) < bundle['match_tolerance_m']]
            observation = candidates[0] if len(candidates) == 1 else None
            delta, status, reason = None, 'needs manual check', 'missing or ambiguous geometry + mark correspondence'
            if observation:
                used.add(observation['id'])
                if not fact['verified'] or not observation['verified']:
                    reason = 'unverified extraction or correspondence'
                elif fact['value'] is None or observation['value'] is None:
                    reason = 'source or model value unavailable'
                elif fact['unit'] != observation['unit']:
                    reason = 'incompatible units'
                elif fact['category'] == 'opening_size' and not fact['calibrated']:
                    reason = 'opening size pending calibrated album extraction (#1302)'
                else:
                    if fact['category'] in ('finish', 'mark'):
                        same = fact['value'] == observation['value']
                    else:
                        delta = observation['value'] - fact['value']
                        same = delta == 0 if fact['category'] == 'opening_count' else abs(delta) < fact['tolerance']
                    status = 'match' if same else 'mismatch'
                    reason = 'compared without correcting either source'
            rows.append(dict(pdf=deepcopy(fact), model=deepcopy(observation),
                             candidates=[o['id'] for o in candidates], reason=reason,
                             model_id=model["id"], difference=delta,
                             tolerance=fact["tolerance"], status=status))
        unmatched.extend(dict(model_id=model['id'], observation=deepcopy(o),
                              reason='no unique PDF correspondence in selected facade/schedule')
                         for o in model['observations'] if o['id'] not in used)
    counts = Counter(row["status"] for row in rows)
    return dict(schema="album-model-audit/1", trust_rule=bundle["trust_rule"],
                frame=deepcopy(bundle["frame"]), rows=rows,
                unmatched_model_observations=unmatched,
                counts={s: counts[s] for s in ("match", "mismatch", "needs manual check")},
                passed=False)


def markdown(report):
    """Short human report; full source boxes/object locators stay in JSON."""
    def cell(x):
        return str(x).replace('|', '\\|').replace('\n', ' ')
    lines = ['# PDF/model mode-A audit', '', f"Trust hierarchy: [{report['trust_rule']}]. Diagnostic only; passed=false.",
             '', f"Counts: {report['counts']}", '',
             '| Model | Sheet/page | Fact/mark | PDF | Model | Difference | Tolerance | Status | Reason |',
             '|---|---|---|---|---|---|---|---|---|']
    for row in report['rows']:
        f, m = row['pdf'], row['model']
        e = f['evidence']
        values = [row['model_id'], f"{e['sheet']} p{e['page']}", f"{f['category']}/{f['mark']}",
                  f['value'], m['value'] if m else None, row['difference'], row['tolerance'],
                  row['status'], row['reason']]
        lines.append('| ' + ' | '.join(map(cell, values)) + ' |')
    return '\n'.join(lines) + '\n'


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key {key}')
        result[key] = value
    return result


def run(input_path, output_dir):
    """Verify file-backed evidence twice; exclusively publish to a NEW directory.

    Exit 0 = measured matches only, 1 = discrepancies, 2 = manual checks,
    never a delivery-approval exit. Existing output directories are refused.
    No temp paths, replacements or deletions are used.
    """
    import hashlib
    import json
    from pathlib import Path
    src, out = Path(input_path).resolve(), Path(output_dir).resolve()
    raw = src.read_bytes()
    bundle = json.loads(raw, object_pairs_hook=_unique_pairs)
    validate(bundle)
    inventory = {src: hashlib.sha256(raw).hexdigest()}
    records = bundle['pdf'] + [o for m in bundle['models'] for o in m['observations']]
    for record in records:
        evidence = record['evidence']
        path = Path(evidence['path'])
        path = (src.parent / path).resolve() if not path.is_absolute() else path.resolve()
        expected = evidence['sha256']
        if path in inventory and inventory[path] != expected:
            raise ValueError(f'conflicting evidence hash {path}')
        inventory[path] = expected
    # Existing directory/file, including a symlink/junction/hardlink, is never reused.
    if out.exists() or out.is_symlink() or any(out == p or out in p.parents for p in inventory):
        raise ValueError('output aliases input/evidence or already exists')

    def verify():
        for path, expected in inventory.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f'changed/stale evidence: {path}')
    verify()
    report = compare(bundle)
    report['input_sha256'] = inventory[src]
    report['input_inventory'] = [{'path': str(p), 'sha256': h} for p, h in inventory.items()]
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    text = markdown(report)
    verify()
    out.mkdir()  # exclusive directory creation, even against competing writers
    with (out / 'report.json').open('x', encoding='utf-8') as stream:
        stream.write(payload)
    with (out / 'report.md').open('x', encoding='utf-8') as stream:
        stream.write(text)
    return 1 if report['counts']['mismatch'] else 2 if report['counts']['needs manual check'] else 0


def main(argv=None):
    """CLI seam for future agr compare; importing dt_ai.album stays lightweight."""
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='normalized source/model observations JSON')
    parser.add_argument('--output-dir', required=True, help='new directory (parent must exist)')
    args = parser.parse_args(argv)
    try:
        return run(args.input, args.output_dir)
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f'audit error: {error}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
