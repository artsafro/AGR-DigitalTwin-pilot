"""Standing #49 judge runner (= judge47.py with the equivalence question; pair cells only) (evidence-only).
Usage: python judge49.py one|pair [--workers N]

Each call: fresh process, fresh session, isolated dir C:/x/j49/<opaque id>/ holding only X.png and Y.png.
Variant names, paths, contract and truth never reach the judge. Raw prompt/answer per call -> calls/<id>.json.
"""
import json
import random
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMP = ROOT / 'comp'
CALLS = ROOT / 'calls'
JDIR = Path('C:/x/j49')
VARIANTS = ['A', 'N_tri', 'N_sub', 'N_jit_0.005', 'N_jit_0.020', 'R', 'W_recess', 'W_corner', 'P_recess_0.20',
            'P_recess_0.11', 'P_recess_0.06', 'P_recess_0.03', 'P_corner_0.40', 'P_corner_0.20', 'P_corner_0.10',
            'P_corner_0.05']   # A vs 'A' = AA control
CLAUDE = shutil.which('claude')
CODEX = shutil.which('codex')
CODEX_MODEL = 'gpt-6.1-sol'   # same as #41-#47 (config default gpt-6.2-sol is rejected for this account)

SPEC = ('The image shows one floor of a building fragment as four orthographic views of an untextured grey model: '
        'V1 elevation of facade side 1, V2 elevation of facade side 2 (opposite side), V3 elevation of the end wall, '
        'V4 plan seen from above (top cut of the floor). White inside the grey wall means an opening.')


def pair_prompt(files):
    # #49: equivalence question replaces the #41-#47 'better' question; PAIR_SPEC is not shown
    return (f'{SPEC}\nTwo renders of a building fragment, made with the same views: render X = file {files[0]}, render '
            f'Y = file {files[1]} (both in the current directory). Ignore differences that come only from mesh '
            'triangulation, shading or rendering noise, and any geometric difference smaller than about 5 cm. Do X and '
            'Y show the same building form (same walls, openings, recesses and corners)? Answer Same, Different or '
            'Unsure. Reply with one line of JSON only, e.g. {"form":"Same"}.')


def run_one(job):
    cid, judge, imgs = job['id'], job['judge'], job['imgs']
    out = CALLS / f'{cid}.json'
    if out.exists():
        return json.loads(out.read_text(encoding='utf-8'))
    d = JDIR / cid
    d.mkdir(parents=True, exist_ok=True)
    files = []
    for name, v in zip(['X.png', 'Y.png'], imgs):
        shutil.copyfile(COMP / f'{v}.png', d / name)
        files.append(name)
    prompt = pair_prompt(files)
    if judge == 'claude':
        cmd = [CLAUDE, '-p', prompt, '--allowedTools', 'Read', '--no-session-persistence', '--strict-mcp-config']
    else:
        cmd = [CODEX, 'exec', '-m', CODEX_MODEL, '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-C', str(d)]
        for f in files:
            cmd += ['-i', str(d / f)]
        cmd += ['-']   # the npm .cmd shim cuts a multi-line argv prompt at the first newline (#41 repair 2)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=420, input=prompt if judge == 'codex' else None,
                           stdin=None if judge == 'codex' else subprocess.DEVNULL)
        stdout, stderr, rc = p.stdout, p.stderr[-2000:], p.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, rc = '', 'TIMEOUT', -9
    wall = round(time.time() - t0, 1)
    parsed = None
    for s in reversed(re.findall(r'\{[^{}]*\}', stdout)):
        try:
            parsed = json.loads(s)
            break
        except ValueError:
            continue
    rec = {**job, 'prompt': prompt, 'cmd0': Path(cmd[0]).name, 'rc': rc, 'wall_s': wall, 'stdout': stdout[-4000:],
           'stderr': stderr, 'parsed': parsed}
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding='utf-8')
    print(cid, judge, imgs, rc, wall, parsed, flush=True)
    return rec


def jobs(kind):
    rng = random.Random(4949)
    js = []
    for judge in ('claude', 'codex'):
        for v in VARIANTS[1:] + ['A']:
            js.append({'judge': judge, 'kind': 'pair', 'imgs': ['A', v], 'order': 'AB'})
            js.append({'judge': judge, 'kind': 'pair', 'imgs': [v, 'A'], 'order': 'BA'})
    for j in js:
        j['id'] = '%08x' % rng.getrandbits(32)
    assert len({j['id'] for j in js}) == len(js) == 64
    if kind == 'one':
        js = [js[0], js[len(js) // 2]]   # one timed call per judge (A vs N_tri, order AB) -> budget check
    return js


if __name__ == '__main__':
    kind = sys.argv[1]
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 4
    CALLS.mkdir(exist_ok=True)
    js = jobs(kind)
    (ROOT / f'jobs-{kind}.json').write_text(json.dumps(js, indent=1), encoding='utf-8')
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(run_one, js))
    print('JUDGE49_DONE', kind, len(js), round(time.time() - t0, 1))
