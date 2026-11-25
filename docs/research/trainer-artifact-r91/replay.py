"""Standing #91 (#1855): score the #90 Revit route through the unchanged `agr body` + `agr trainer score`. OBSERVE.

    uv run --frozen python docs/research/trainer-artifact-r91/replay.py C:/x/<NEW_DIR>

Fresh crops come from the pinned #90 replay (extracted into ignored tmp/, run unchanged). Each plan arm is built
with `agr body` and scored against Artem's key; controls are hash-checked read-only inputs. Writes OUT/receipt.json.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
R90 = '171a77a29938b688def45cfb71633c433f0580c0'
R90_DIR = 'docs/research/trainer-revit-jamb-r90'
R90_BLOBS = {'replay.py': None, 'candidate.py': '51fac9c597732a26a853a7ea12124b212db61a35ac98e6c9a0b7fa36e4100d5c'}
BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
EV = 'G:/Мой диск/AGR-evidence/'
PINS = {
    EV + '1855-trainer-v0/bank/63a-stage1/63A_Stage1_v005.fbx': 'f3769c62a7e9fdbfcf7a59624269bcd0374ca494f593e2e85c08474a0007798a',
    EV + '1855-trainer-v0/bank/63b-stage1/v007.fbx': '53189b830418a328f3159172c5c1c7eff826c5a9eff568cad0b9187b63332bd7',
    EV + '1855-trainer-v0/bank/63b-stage1/v004.fbx': '6d22c572ab18d9722dcf2296dcca77525ae26265114ba6ff922c3d82f4ce26ae',
    EV + '1619-body-training/tower-A/v005/floor_v005.json': '6f9c6d143d18febc7033f848505859bd2f50bd611c12f1f8147d1822eb6a7d66',
    EV + '1619-body-training/round4-k2-stage1/floor_k2_v002.json': '6a6599168dddfcc7c4af79f0439ccdde609e463c373ed62a908b9224a4a833f9',
    EV + '1855-trainer-v0/bank/63a-stage1/STLB-04_RR_AR.fbx': '2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7',
}
STOP_S = 1800
ETALON = {'63A': '63a-stage1', '63B': '63b-stage1'}
KEEP = ('status', 'first_failing_step', 'score', 'form_p95_m')


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def run(argv, log):
    t = time.perf_counter()
    with open(log, 'w', encoding='utf-8') as f:
        rc = subprocess.run(argv, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=ENV).returncode
    return rc, round(time.perf_counter() - t, 3)


def build_and_score(plan, etalon, d):
    """plan -> agr body -> agr trainer score. Returns a compact row; the full score json stays in d."""
    d.mkdir(parents=True)
    row = {'plan': str(plan), 'plan_sha256': sha(plan) if plan and Path(plan).is_file() else None, 'etalon': etalon}
    fbx = None
    if plan is not None:
        rc, s = run(['uv', 'run', '--frozen', 'agr', 'body', str(plan), str(d / 'body')], d / 'body.log')
        row.update(body_exit=rc, body_s=s)
        if (d / 'body' / 'body.fbx').is_file():
            fbx = d / 'body' / 'body.fbx'
            row['fbx_sha256'] = sha(fbx)
    built = fbx if fbx else d / 'body'
    if not built.exists():
        built.mkdir()  # empty result dir: the scorer reports `artifact: fail, no FBX`
    rc, s = run(['uv', 'run', '--frozen', 'agr', 'trainer', 'score', etalon, '--built', str(built),
                 '--out', str(d / 'score.json')], d / 'score.log')
    row.update(score_exit=rc, score_s=s)
    rep = json.loads((d / 'score.json').read_text(encoding='utf-8'))
    st = rep['steps']
    row.update(first_failing_step=rep['first_failing_step'], score=rep['score'],
               steps={k: v['status'] for k, v in st.items()},
               bounds_dev_m=st['bounds'].get('max_corner_dev_m'), form_p95_m=st['form'].get('p95_m'),
               form_max_m=st['form'].get('max_m'), polygons=st['topology'].get('polygons'),
               key_polygons=st['topology'].get('key_polygons'))
    return row


def main(out):
    t0 = time.perf_counter()
    out.mkdir(parents=True, exist_ok=False)
    pre = {p: sha(p) for p in PINS}
    assert pre == PINS, {p: h for p, h in pre.items() if PINS[p] != h}
    base = ROOT / 'tmp' / ('r91-base-' + out.name) / R90_DIR
    base.mkdir(parents=True, exist_ok=False)
    for name, want in R90_BLOBS.items():
        (base / name).write_bytes(subprocess.check_output(['git', 'show', f'{R90}:{R90_DIR}/{name}'], cwd=ROOT))
        assert want is None or sha(base / name) == want, name
    crops = out / 'r90'
    rc, s = run([sys.executable, str(base / 'replay.py'), str(crops)], out / 'r90.log')
    receipt = {'schema': 'trainer-artifact-r91/1', 'revision': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'r90_pin': R90, 'r90_exit': rc, 'r90_s': s,
        'blender': BLENDER, 'inputs_pre': pre, 'runs': [], 'controls': {}}
    assert rc == 0, 'pinned #90 replay failed - see r90.log'
    for tower in ('63A', '63B'):
        for i in (1, 2, 3):
            for arm in ('baseline', 'aligned'):
                if time.perf_counter() - t0 > STOP_S:
                    receipt['status'] = 'budget_stop'
                    break
                plan = crops / f'{tower}-{i}' / f'{arm}.json'
                row = build_and_score(plan if plan.is_file() else None, ETALON[tower], out / f'{tower}-{i}-{arm}')
                row.update(tower=tower, rep=i, arm=arm)
                receipt['runs'].append(row)
    c = receipt['controls']
    c['ceiling-63A'] = build_and_score(Path(EV + '1619-body-training/tower-A/v005/floor_v005.json'), '63a-stage1',
                                       out / 'ceiling-63A')
    c['g22-accepted'] = build_and_score(Path(EV + '1619-body-training/round4-k2-stage1/floor_k2_v002.json'),
                                        'g22-k2-stage1', out / 'g22-accepted')
    d = out / 'calib-63B-v004'
    d.mkdir()
    rc, s = run(['uv', 'run', '--frozen', 'agr', 'trainer', 'score', '63b-stage1', '--built',
                 EV + '1855-trainer-v0/bank/63b-stage1/v004.fbx', '--out', str(d / 'score.json')], d / 'score.log')
    rep = json.loads((d / 'score.json').read_text(encoding='utf-8'))
    c['calib-63B-v004-rejected'] = {'score_exit': rc, 'score_s': s, 'first_failing_step': rep['first_failing_step'],
                                    'score': rep['score'], 'steps': {k: v['status'] for k, v in rep['steps'].items()}}
    post = {p: sha(p) for p in PINS}
    receipt.update(inputs_post_equal=post == pre, wall_s=round(time.perf_counter() - t0, 3))
    receipt.setdefault('status', 'finished')
    summ = {}
    for tower in ('63A', '63B'):
        for arm in ('baseline', 'aligned'):
            rows = [r for r in receipt['runs'] if r['tower'] == tower and r['arm'] == arm]
            summ[f'{tower}/{arm}'] = {'artifact_pass': sum(r['steps']['artifact'] == 'pass' for r in rows),
                                      'n': len(rows), 'first_failing': [r['first_failing_step'] for r in rows],
                                      'form_p95_m': [r['form_p95_m'] for r in rows]}
    receipt['summary'] = summ
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                      newline='\n')
    print(json.dumps({'status': receipt['status'], 'wall_s': receipt['wall_s'], 'summary': summ,
                      'controls': {k: (v['first_failing_step'], v['score']) for k, v in c.items()}},
                     ensure_ascii=False, indent=1))


ENV = {**os.environ, 'TWINQA_BLENDER': BLENDER, 'PYTHONUTF8': '1'}

if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
