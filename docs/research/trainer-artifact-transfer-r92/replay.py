"""Transfer #90 unchanged to a third tower; score new FBXs with the existing trainer."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.trainer import trainer  # noqa: E402

BASE = 'cf4efcbba169541d7163a83f7b28d054f0649db1'
R90 = '171a77a29938b688def45cfb71633c433f0580c0'
R89 = 'e5a275c8bad74e9f91f875c098477d3a6530b984'
EV = Path('G:/Мой диск/AGR-evidence')
BANK = EV / '1855-trainer-v0/bank'
B_V4 = BANK / '63b-stage1/v004.fbx'
C_KEY = EV / '1619-body-training/tower-C/v002/63C_stage1_v002_QUAD.fbx'
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
PINS = {
    Path('C:/x/body-training/a101-63/source/STLB-04_RR_AR.fbx'): '2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7',
    EV / '1619-body-training/gate1/boxes63.json': 'e8a41981ecaa7603ec4c8ef28098388ee2fcbf7cc8e341eaf5d08ed4f5d987e7',
    EV / '1619-body-training/round4-k2-stage1/floor_k2_v002.json': '6a6599168dddfcc7c4af79f0439ccdde609e463c373ed62a908b9224a4a833f9',
    BANK / '63a-stage1/63A_Stage1_v005.fbx': 'f3769c62a7e9fdbfcf7a59624269bcd0374ca494f593e2e85c08474a0007798a',
    BANK / '63b-stage1/v007.fbx': '53189b830418a328f3159172c5c1c7eff826c5a9eff568cad0b9187b63332bd7',
    B_V4: '6d22c572ab18d9722dcf2296dcca77525ae26265114ba6ff922c3d82f4ce26ae',
    C_KEY: '462ba61b2c379de53a72667635fd0714703764b2409407cc67ff28d8684de1da',
    BLENDER: '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5',
}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def preflight():
    actual = {p: sha(p) for p in PINS}
    if actual != PINS:
        raise ValueError(f'native pin mismatch: {[str(p) for p in PINS if actual[p] != PINS[p]]}')
    git('diff', '--exit-code', BASE, '--', 'src', 'tools', 'schemas', 'docs/trainer', 'uv.lock', 'pyproject.toml')
    return {str(p): digest for p, digest in actual.items()}


def staged_crop_driver(out):
    """Substitute only the read-only blob of the tower loop; keep the #90 candidate exact."""
    here = out / 'driver/docs/research/r92'
    here.mkdir(parents=True)
    for name in ('candidate.py', 'replay.py'):
        (here / name).write_bytes(git('show', f'{R90}:docs/research/trainer-revit-jamb-r90/{name}'))
    sys.path.insert(0, str(here))
    # The pinned driver resolves ROOT relative to its file; point it back to this checkout.
    ns = {'__name__': 'r90', '__file__': str(here / 'replay.py')}
    exec(compile((here / 'replay.py').read_bytes(), ns['__file__'], 'exec'), ns)
    ns['ROOT'] = ROOT
    original_blob = ns['blob']
    prior_ref = f'{R89}:docs/research/trainer-revit-intake-r89/replay.py'

    def patched_blob(ref):
        raw = original_blob(ref)
        if ref != prior_ref:
            return raw
        if git('rev-parse', ref).strip() != b'9560d21e0b44b1624ef54a58fcd3fdf8fc8514eb':
            raise ValueError('unexpected #89 base blob')
        old = b"for tower in ('63A', '63B'):"
        if raw.count(old) != 1:
            raise ValueError('unexpected fixture loop')
        result = raw.replace(old, b"for tower in ('63A', '63C'):")
        (here / 'paired_driver.py').write_bytes(result)
        return result

    ns['blob'] = patched_blob
    text = (here / 'replay.py').read_text(encoding='utf-8')
    check = "    assert subprocess.check_output(['git', 'hash-object', '--stdin'], cwd=ROOT, input=prior).strip() == b'9560d21e0b44b1624ef54a58fcd3fdf8fc8514eb'\n"
    if text.count(check) != 1:
        raise ValueError('unexpected #90 verification line')
    # patched_blob verifies the original object SHA before the one substitution.
    start, end = text.index('def main(out):'), text.index("if __name__ == '__main__':")
    exec(compile(text[start:end].replace(check, ''), ns['__file__'], 'exec'), ns)
    ns['main'](out / 'crops')
    return {p.name: sha(p) for p in here.glob('*.py')}


def score(entry, built, directory, allow_key=False):
    report = trainer.score(entry, built, directory, allow_key=allow_key)
    save(directory / 'score.json', report)
    return {k: report[k] for k in ('steps', 'first_failing_step', 'score')}


def arm(out, entry, plan, plan_result):
    out.mkdir()
    built = out / 'body'
    if not plan.is_file():
        # A missing plan due to a runtime error is not a measured refused build.
        return {'m92': None, 'plan_result': plan_result}
    with (out / 'build.log').open('w', encoding='utf-8') as log:
        rc = subprocess.run(['uv', 'run', '--frozen', 'agr', 'body', str(plan), str(built)], cwd=ROOT,
                            stdout=log, stderr=subprocess.STDOUT, timeout=30).returncode
    built.mkdir(exist_ok=True)
    fbx = built / 'body.fbx'
    report = score(entry, fbx if fbx.is_file() else built, out / 'score')
    steps = {k: v['status'] for k, v in report['steps'].items()}
    log = (out / 'build.log').read_text(encoding='utf-8', errors='replace').lower()
    measured_refusal = not fbx.is_file() and 'ring not closed' in log
    value = None if steps['readback'] == 'error' or (rc != 0 and not measured_refusal) else int(
        fbx.is_file() and rc == 0 and steps['artifact'] == steps['readback'] == 'pass')
    return {'m92': value, 'exit': rc, 'plan_sha256': sha(plan), 'fbx_sha256': sha(fbx) if fbx.is_file() else None,
            'plan_result': plan_result, **report}


def main(out):
    start = time.perf_counter()
    os.environ['TWINQA_BLENDER'] = str(BLENDER)
    out.mkdir(parents=True)
    receipt_path = out / 'receipt.json'
    report = {'runtime': sys.version, 'head': git('rev-parse', 'HEAD').decode().strip(), 'driver_sha256': sha(__file__),
              'base': BASE, 'pins_before': preflight(), 'rows': [], 'controls': {}, 'status': 'running'}
    save(receipt_path, report)
    bank = trainer.load_bank()
    a, b, c = (trainer.etalon(bank, entry) for entry in ('63a-stage1', '63b-stage1', '63c-stage1-2'))
    c = {**c, 'target': 'body', 'key': {'path': str(C_KEY), 'sha256': PINS[C_KEY]}}
    try:
        report['crop_driver'] = staged_crop_driver(out)
        receipt = json.loads((out / 'crops/receipt.json').read_text(encoding='utf-8'))
        report['crop_status'] = receipt['status']
        report['first_pair_wall_s'] = receipt.get('first_pair_wall_s')
        deadline = start + min(480, 5 * receipt.get('first_pair_wall_s', 96))
        for row in receipt['rows']:
            if time.perf_counter() > deadline:
                break
            tower, rep = row['fixture'], row['iteration']
            name = f'{tower}-{rep}'
            crop = out / 'crops' / name
            variant = row.get('candidate_run', {})
            changes = variant.get('aligned_jambs')
            result = {'tower': tower, 'rep': rep, 'crop_sha256': row.get('crop_sha256'),
                      'changed_jambs': None if changes is None else len(changes),
                      'exercise': 'not_measured' if changes is None else 'exercised' if changes else 'not_exercised',
                      'raw_arm_parity': variant.get('raw_arm_parity')}
            for arm_name, old in [('baseline', 'baseline'), ('aligned', 'candidate')]:
                result[arm_name] = arm(out / f'{name}-{arm_name}', a if tower == '63A' else c,
                                       crop / f'{arm_name}.json', row[old])
            report['rows'].append(result)
            save(receipt_path, report)
        for label, entry, asset, allow in [('accepted_c', c, C_KEY, True), ('rejected_b', b, B_V4, False),
                                            ('same_key', c, C_KEY, False)]:
            if time.perf_counter() > deadline:
                break
            report['controls'][label] = score(entry, asset, out / label, allow)
        witness = out / '63A-1-aligned/body/body.fbx'
        if witness.is_file() and time.perf_counter() <= deadline:
            truncated = out / 'truncated.fbx'
            truncated.write_bytes(witness.read_bytes()[:23])
            report['controls']['truncated'] = score(a, truncated, out / 'truncated')
        report['status'] = ('finished' if len(report['rows']) == 6 and len(report['controls']) == 4
                            and time.perf_counter() <= deadline else 'budget_stop')
        report['pins_after'] = preflight()
    finally:
        report['wall_s'] = round(time.perf_counter() - start, 3)
        save(receipt_path, report)
    print(report['status'], report['wall_s'], [(r['tower'], r['rep'], r['changed_jambs'], r['baseline']['m92'],
          r['aligned']['m92']) for r in report['rows']], flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
