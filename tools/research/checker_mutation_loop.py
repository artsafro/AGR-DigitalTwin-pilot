"""new-case: provenance-bound measurement cache for the #1261 autoresearch control.

Caches only actual completed evaluate() results by all checker/standard source bytes.
The frozen runner, generator, guard, corpus and oracle hashes remain mandatory. The
cache saves repeating unchanged baseline/rejected heads; it never synthesizes findings.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from checker_mutation import ROOT, GENERATOR, GUARD, evaluate
from checker_mutation_guard import guard, read, sha256, verify_files


def fingerprint():
    paths = sorted([*ROOT.glob('src/twinqa/**/*.py'), *ROOT.glob('standards/**/*.yaml'),
                    *ROOT.glob('standards/**/*.json'), *ROOT.glob('standards/**/*.csv')])
    if not paths:
        raise ValueError('empty checker source tree')
    return hashlib.sha256(json.dumps({p.relative_to(ROOT).as_posix(): sha256(p) for p in paths}, sort_keys=True).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['bootstrap', 'metric', 'guard'])
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--manifest-sha256', required=True)
    p.add_argument('--oracle-sha256', required=True)
    args = p.parse_args()
    run = args.run.resolve()
    root = run/'corpus'
    baseline = run/'baseline.json'
    if sha256(root/'manifest.json') != args.manifest_sha256 or sha256(baseline) != args.oracle_sha256:
        raise ValueError('manifest/oracle hash drift')
    manifest = read(root/'manifest.json')
    for path, key in [(GENERATOR,'generator_sha256'), (GUARD,'guard_sha256'), (Path(__file__).with_name('checker_mutation.py'),'runner_sha256')]:
        if sha256(path) != manifest[key]:
            raise ValueError(f'frozen code drift: {key}')
    verify_files(root, manifest['files'])
    key = fingerprint()
    cache = run/'cache'
    cache.mkdir(exist_ok=True)
    target = cache/f'{key}.json'
    if target.resolve().parent != cache.resolve():
        raise ValueError('cache path alias')
    binding = {'fingerprint': key, 'manifest_sha256': args.manifest_sha256, 'oracle_sha256': args.oracle_sha256,
               'wrapper_sha256': sha256(Path(__file__))}
    if args.mode == 'bootstrap':
        subprocess.run(['git','diff','--exit-code','5a9606d58ae79ccc44acc799dc5870eda23ab662','--','src/twinqa','standards'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        result = read(baseline)
        with target.open('x', encoding='utf-8') as f:
            json.dump({'binding': binding, 'result': result}, f, ensure_ascii=False, allow_nan=False)
    elif target.exists():
        stored = read(target)
        if stored.get('binding') != binding or not isinstance(stored.get('result'), dict):
            raise ValueError('stale cache receipt')
        result = stored['result']
    else:
        if args.mode == 'guard':
            raise ValueError('no completed metric receipt for this checker head')
        result = evaluate(root, manifest)
        if fingerprint() != key:
            raise ValueError('checker changed during measurement')
        verify_files(root, manifest['files'])
        with target.open('x', encoding='utf-8') as f:
            json.dump({'binding': binding, 'result': result}, f, ensure_ascii=False, allow_nan=False)
    if args.mode == 'guard':
        guard(read(baseline)['clean'], result['clean'])
        print('guard PASS: exact existing verdicts, 0 new false alarms')
    else:
        print(json.dumps({'score': result['score'], 'caught': result['caught'], 'total': result['total'], 'fingerprint': key}))


if __name__ == '__main__':
    main()
