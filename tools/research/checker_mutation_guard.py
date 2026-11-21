"""new-case: immutable exact-verdict guard for real-etalon mutation research (#1261)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

STATUSES = {'pass', 'fail', 'review', 'not_run'}


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate(findings):
    if not isinstance(findings, list) or not findings:
        raise ValueError('empty or unsupported findings')
    indexed = {}
    for f in findings:
        if (not isinstance(f, dict) or set(f) != {'code', 'status', 'observed'}
                or not isinstance(f['code'], str) or '/' not in f['code']
                or f['status'] not in STATUSES or not isinstance(f['observed'], str)
                or not f['observed'] or f['code'] in indexed):
            raise ValueError(f'partial, duplicate or unsupported finding: {f!r}')
        indexed[f['code']] = f
    return indexed


def guard(oracle, current):
    if not isinstance(oracle, dict) or not oracle or set(oracle) != set(current):
        raise ValueError('empty, missing, extra or duplicate etalon')
    for name in oracle:
        before, after = validate(oracle[name]), validate(current[name])
        # Exact verdict set, not only the aggregate: removal, relaxation and new review all fail.
        if (any(k not in after or v['status'] != after[k]['status'] for k, v in before.items())
                or any(v['status'] != 'pass' for k, v in after.items() if k not in before)):
            raise ValueError(f'oracle verdict drift: {name}')
    return True


def caught(clean, mutant, expected):
    before, after = validate(clean), validate(mutant)
    if not expected or any(not isinstance(c, str) or '/' not in c for c in expected):
        raise ValueError('empty or invalid expected finding codes')
    return any(c in after and after[c]['status'] in {'fail', 'review'}
               and (c not in before or before[c]['status'] not in {'fail', 'review'}) for c in expected)


def verify_files(root, files):
    root = Path(root).resolve()
    if not isinstance(files, dict) or not files:
        raise ValueError('empty file manifest')
    identities = set()
    for name, expected in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path in identities or not path.is_file():
            raise ValueError(f'unsafe, duplicate or missing file: {name}')
        identity = (path.stat().st_dev, path.stat().st_ino)
        if identity in identities:
            raise ValueError(f'duplicate physical file: {name}')
        identities.add(path)
        identities.add(identity)
        if sha256(path) != expected:
            raise ValueError(f'hash drift: {name}')


def read(path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError(f'duplicate key: {k}')
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(f'nonfinite {s}')))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('oracle', type=Path)
    p.add_argument('current', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    inputs = [args.oracle.resolve(), args.current.resolve()]
    if args.output and (args.output.resolve() in inputs or args.output.exists()):
        p.error('output aliases input or already exists; nothing written')
    snapshots = [x.read_bytes() for x in inputs]
    guard(read(inputs[0]), read(inputs[1]))
    if [x.read_bytes() for x in inputs] != snapshots:
        raise ValueError('input changed during guard')
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump({'guard': 'PASS', 'new_false_alarms': 0}, stream)
    print('guard PASS: 0 new false alarms; exact verdicts')


if __name__ == '__main__':
    main()
