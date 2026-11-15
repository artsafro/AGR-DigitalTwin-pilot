"""new-case: read-only, part-bound accepted geometry file gate (#1445).

This is a point-in-time byte identity check, not geometry QA or an approval service.
Run before a later-stage consumer and keep the verified inputs immutable until read.
Paths in accepted.json are absolute or relative to that manifest's directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


class InvalidRecord(ValueError):
    """An incomplete or ambiguous accepted-set request."""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRecord(f'duplicate key: {key}')
        result[key] = value
    return result


def _constant(value):
    raise InvalidRecord(f'nonfinite JSON value: {value}')


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise InvalidRecord(f'{label}: expected nonempty string')
    return value


def _sha(value, label):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise InvalidRecord(f'{label}: expected lowercase sha256')
    return value


def _fields(value, required, optional=()):
    if not isinstance(value, dict):
        raise InvalidRecord('expected JSON object')
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise InvalidRecord(f'fields missing={sorted(missing)} unknown={sorted(unknown)}')


def _read(path):
    raw = path.read_bytes()
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant), raw


def _hash(path):
    with path.open('rb') as stream:
        if not stream.read(1):
            raise InvalidRecord(f'empty geometry input: {path}')
        stream.seek(0)
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _rows(value, label):
    if not isinstance(value, list) or not value:
        raise InvalidRecord(f'{label}: expected nonempty list')
    return value


def _load(record, job):
    _fields(record, ('schema', 'job', 'accepted'), ('change_decisions', 'evidence'))
    if record['schema'] != 'accepted-set/1' or record['job'] != job:
        raise InvalidRecord('unsupported accepted-set schema or job mismatch')
    by_part = {}
    for row in _rows(record['accepted'], 'accepted'):
        _fields(row, ('part', 'version', 'path', 'sha256'))
        for key in ('part', 'version', 'path'):
            _text(row[key], key)
        _sha(row['sha256'], 'sha256')
        if row['part'] in by_part:
            raise InvalidRecord(f"duplicate accepted part: {row['part']}")
        by_part[row['part']] = row
    return by_part


def check(accepted_set, job, inputs, *, part=None):
    """Check every input; return JSON-safe verdicts without writing any files.

    Bare file arguments require an explicit part. Mixed-part callers can supply
    PART=PATH arguments instead. No filename/version/latest heuristic is used.
    """
    manifest = Path(accepted_set).resolve(strict=True)
    record, original = _read(manifest)
    accepted = _load(record, job)
    _rows(inputs, 'inputs')
    seen = []
    source_snapshots = []
    results = []
    for argument in inputs:
        name, separator, path_text = str(argument).partition('=')
        if separator:
            if part is not None:
                raise InvalidRecord('use --part with bare paths OR PART=PATH, not both')
            source_part = name
        else:
            source_part, path_text = part, name
        if source_part not in accepted:
            raise InvalidRecord(f'unknown accepted part: {source_part!r}; input={argument}')
        candidate = Path(_text(path_text, 'input path')).resolve(strict=True)
        if candidate == manifest or candidate.samefile(manifest):
            raise InvalidRecord(f'input aliases accepted set: {candidate}')
        if any(candidate == old or candidate.samefile(old) for old in seen):
            raise InvalidRecord(f'duplicate input: {candidate}')
        seen.append(candidate)
        row = accepted[source_part]
        expected_path = Path(row['path'])
        if not expected_path.is_absolute():
            expected_path = manifest.parent / expected_path
        # The accepted source itself must still exist with the recorded bytes;
        # a matching candidate cannot conceal a stale approval registry.
        source = expected_path.resolve(strict=True)
        expected = row['sha256']
        actual = _hash(candidate)
        source_hash = _hash(source)
        source_snapshots.append((source, source_hash))
        ok = actual == expected and source_hash == expected
        results.append({'part': source_part, 'version': row['version'],
                        'path': str(candidate), 'sha256': actual,
                        'expected_sha256': expected,
                        'status': 'accepted' if ok else 'rejected',
                        'reason': '' if ok else 'sha256 not in accepted set or accepted source changed'})
        # Re-read both paths to reject observed mutation/replacement during hashing.
        if _hash(candidate) != actual or _hash(source) != source_hash:
            raise InvalidRecord(f'input changed during check: {candidate}')
    # Check the whole inventory again, not just the last input.
    for row, path in zip(results, seen, strict=True):
        if _hash(path) != row['sha256']:
            raise InvalidRecord(f'input changed during check: {path}')
    for source, observed_hash in source_snapshots:
        if _hash(source) != observed_hash:
            raise InvalidRecord(f'accepted source changed during check: {source}')
    if manifest.read_bytes() != original:
        raise InvalidRecord('accepted set changed during check')
    return {'passed': all(row['status'] == 'accepted' for row in results), 'job': job,
            'accepted_set_sha256': hashlib.sha256(original).hexdigest(), 'inputs': results}


def check_brief(accepted_set, job, brief):
    """Validate a structured stage brief against the job's frozen snapshot.

    A referenced user decision permits only the exact new geometry version; it
    never makes that candidate an accepted input for a downstream stage.
    """
    manifest = Path(accepted_set).resolve(strict=True)
    record, original = _read(manifest)
    accepted = _load(record, job)
    brief_path = Path(brief).resolve(strict=True)
    payload, brief_bytes = _read(brief_path)
    _fields(payload, ('schema', 'job', 'accepted_set_sha256', 'actions'))
    if payload['schema'] != 'accepted-brief/1' or payload['job'] != job:
        raise InvalidRecord('unsupported brief schema or job mismatch')
    if _sha(payload['accepted_set_sha256'], 'accepted_set_sha256') != hashlib.sha256(original).hexdigest():
        raise InvalidRecord('brief cites stale accepted set')
    decisions = record.get('change_decisions', [])
    if not isinstance(decisions, list):
        raise InvalidRecord('change_decisions: expected list')
    authorized = set()
    for decision in decisions:
        _fields(decision, ('part', 'from_sha256', 'to_version', 'actor_role', 'decision', 'ref'))
        for key in ('part', 'to_version', 'ref'):
            _text(decision[key], key)
        _sha(decision['from_sha256'], 'from_sha256')
        if decision['part'] not in accepted:
            raise InvalidRecord(f"unknown decision part: {decision['part']}")
        if (decision['actor_role'] != 'user' or decision['decision'] != 'approved'
                or decision['from_sha256'] != accepted[decision['part']]['sha256']):
            raise InvalidRecord('change decision must be approved by user and bind accepted sha256')
        identity = (decision['part'], decision['to_version'])
        if identity in authorized:
            raise InvalidRecord(f'duplicate change decision: {identity}')
        authorized.add(identity)
    results = []
    seen = set()
    stages = {'geometry', 'uv', 'textures', 'ucx', 'export', 'review'}
    for action in _rows(payload['actions'], 'actions'):
        _fields(action, ('part', 'stage', 'version'))
        for key in ('part', 'stage', 'version'):
            _text(action[key], key)
        name, stage, version = action['part'], action['stage'], action['version']
        if name not in accepted or stage not in stages:
            raise InvalidRecord(f'unknown part or stage: {name}/{stage}')
        identity = (name, stage, version)
        if identity in seen:
            raise InvalidRecord(f'duplicate brief action: {identity}')
        seen.add(identity)
        if stage == 'geometry':
            ok = (name, version) in authorized and version != accepted[name]['version']
            reason = '' if ok else 'geometry is frozen; new version requires a bound user decision'
        else:
            ok = version == accepted[name]['version']
            reason = '' if ok else 'later stage must cite the accepted version, not latest'
        results.append({**action, 'status': 'accepted' if ok else 'rejected', 'reason': reason})
    if manifest.read_bytes() != original or brief_path.read_bytes() != brief_bytes:
        raise InvalidRecord('accepted set or brief changed during check')
    return {'passed': all(row['status'] == 'accepted' for row in results), 'job': job,
            'accepted_set_sha256': hashlib.sha256(original).hexdigest(), 'actions': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--job', required=True)
    parser.add_argument('--accepted-set', type=Path, help='explicit historical/test manifest; default jobs/JOB/accepted.json')
    parser.add_argument('--part', help='part identity for bare --inputs paths')
    parser.add_argument('--inputs', nargs='+')
    parser.add_argument('--brief', type=Path, help='accepted-brief/1 JSON stage plan')
    args = parser.parse_args(argv)
    try:
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', args.job) is None:
            raise InvalidRecord('invalid job identifier')
        manifest = args.accepted_set or args.root / 'jobs' / args.job / 'accepted.json'
        if not args.inputs and not args.brief:
            raise InvalidRecord('provide --inputs and/or --brief')
        result = check(manifest, args.job, args.inputs, part=args.part) if args.inputs else None
        if args.brief:
            planned = check_brief(manifest, args.job, args.brief)
            if result is None:
                result = planned
            else:
                if result['accepted_set_sha256'] != planned['accepted_set_sha256']:
                    raise InvalidRecord('accepted set changed between inputs and brief')
                result['actions'] = planned['actions']
                result['passed'] = result['passed'] and planned['passed']
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({'passed': False, 'error': str(error)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
