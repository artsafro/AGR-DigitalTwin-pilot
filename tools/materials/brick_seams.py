"""new-case: JSON command for the shared stdlib course/panel seam calculation.

Candidate planning only. No bitmap bake, native mutation or delivery acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.max.agr_tools.seams_core import calculate
from tools.materials.course_grid_pages import _json, _distinct, _reference, _digest


def run(config_path, output):
    """Snapshot inline config or hash-bound data roles; publish one new envelope."""
    config_path, output = Path(config_path), Path(output)
    raw = config_path.read_bytes()
    config = _json(raw)
    if not isinstance(config, dict):
        raise ValueError('config must be an object')
    refs = {}
    # File mode replaces only data, using explicit per-role path/SHA256 references.
    if 'inputs' in config:
        config = dict(config)
        inputs = config.pop('inputs')
        names = {'pages': {'partitions', 'brick_fold', 'placements'}, 'mesh': {'mesh'}}.get(config.get('mode'))
        if 'data' in config or not isinstance(inputs, dict) or set(inputs) != names:
            raise ValueError(f'unmapped/partial inputs: {inputs}')
        refs = {k: _reference(v, config_path.parent) for k, v in inputs.items()}
    _distinct([config_path, output, Path(str(output)+'.partial')]+[p for p, _ in refs.values()])
    if output.exists() or Path(str(output)+'.partial').exists():
        raise ValueError('output/partial already exists')
    def verify():
        if config_path.read_bytes() != raw:
            raise ValueError('config changed during calculation')
        for p, digest in refs.values():
            if _digest(p) != digest:
                raise ValueError(f'stale/changed input: {p}')
    verify()
    if refs:
        loaded = {}
        for name, (p, digest) in refs.items():
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f'input changed while reading: {p}')
            loaded[name] = _json(data)
        config['data'] = loaded['mesh'] if config['mode'] == 'mesh' else loaded
    plan = calculate(config)
    verify()
    envelope = dict(schema='brick-seams-result/1', passed=False, status='candidate_calculated',
                    config_sha256=hashlib.sha256(raw).hexdigest(),
                    inputs={k: dict(path=str(p.resolve()), sha256=d) for k, (p, d) in refs.items()}, plan=plan)
    encoded = json.dumps(envelope, allow_nan=False, indent=2).encode('utf-8')+b'\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    # Private staging, no-replace publication. Windows rename refuses an existing
    # destination (also on DriveFS); POSIX rename overwrites, so use link there.
    # A foreign .partial is never opened or deleted.
    with tempfile.TemporaryDirectory(prefix='.brick-seams-', dir=output.parent) as staging:
        temp = Path(staging)/'candidate.json'
        with temp.open('xb') as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        verify()
        if os.name == 'nt':
            os.rename(temp, output)
        else:
            os.link(temp, output)
    return envelope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.config, args.out)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        print(f'ERROR: brick-seams: {error}', file=sys.stderr)
        return 2
    print(json.dumps(dict(status=result['status'], passed=False, out=str(args.out))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
