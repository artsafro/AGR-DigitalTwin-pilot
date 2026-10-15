"""Serialized wrapper-only native execution with unique scripts/logs per stage."""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--mode', choices=['baseline', 'prototype', 'readback'], required=True)
    p.add_argument('--wrapper', type=Path, required=True)
    args = p.parse_args()
    source = Path(__file__).with_name('native.py').resolve()
    config = {'run': str(args.run.resolve()), 'mode': args.mode}
    job = args.run / (args.mode+'.py')
    with job.open('x') as f:
        f.write('CONFIG = '+repr(config)+'\n')
        f.write('p = '+repr(str(source))+'\n')
        f.write("exec(compile(open(p, encoding='utf-8').read(), p, 'exec'))\n")
    target = args.run / (args.mode+'-wrapper.json')
    command = ['python', str(args.wrapper), 'max', '--card', 't_8da65809', '--file', str(job),
               '--out', str(target), '--max-chars', '1200']
    result = subprocess.run(command, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode:
        raise RuntimeError('Wrapper exit '+str(result.returncode)+': '+result.stderr[-1200:])
    data = json.loads(target.read_text())
    assert 'AGR_E1_COMPLETE '+args.mode in data['log'], 'No fresh completion marker'
    assert 'AGR_E1_CLEANUP 0' in data['log'], 'Native cleanup missing'
    assert (args.run / args.mode / 'results.json').exists()
    print('VERIFIED_STAGE', args.mode, data.get('seconds'), data.get('exit_code'))


if __name__ == '__main__':
    main()
