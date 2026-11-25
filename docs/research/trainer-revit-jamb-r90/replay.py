"""Re-use the hash-pinned r89 driver: only the second arm gets plan alignment."""
import copy
import hashlib
from itertools import accumulate
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from candidate import align

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = 'e5a275c8bad74e9f91f875c098477d3a6530b984'
CORE = '08015022acc2a140994eeb188444f68a4388c15c:tools/methods/body/body_lattice.py'
G22 = Path('G:/Мой диск/AGR-evidence/1619-body-training/round4-k2-stage1/floor_k2_v002.json')
G22_SHA = '6a6599168dddfcc7c4af79f0439ccdde609e463c373ed62a908b9224a4a833f9'


def blob(ref):
    return subprocess.check_output(['git', 'show', ref], cwd=ROOT)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verdict(build, plan):
    try:
        return {'closure': build(plan)['report']['rings']}
    except ValueError as exc:
        return {'error': str(exc)}


def synthetic(build, eps):
    variants = {}
    for name, offset in [('near', 0.00015), ('far', 0.0003), ('overlap', 0.00015)]:
        s = 4 - offset
        doc = {'step': 3, 'z0': 0, 'floors': 2, 'loops': [0, 1, 2],
               'rings': [{'xy': [[0, 0], [4, 0], [4, 4], [0, 4]], 'cuts': [2, s]}],
               'windows': [[0, 2, s, 0, 1, 0.2]],
               'materials': {'WALL_A': [1, 1, 1]}}
        if name == 'overlap':
            doc['windows'].append([0, 2, s, 0, 1, 0.2])
        result, changes = align(doc, eps)
        variants[name] = {'changes': changes, 'before': verdict(build, doc), 'after': verdict(build, result)}
    return variants


def preflight_controls(build, eps):
    raw = G22.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == G22_SHA
    doc = json.loads(raw)
    result, changes = align(doc, eps)
    controls = {'native': {'changes': changes, 'equal': result == doc, 'before': verdict(build, doc),
                            'after': verdict(build, result)}}
    injected = copy.deepcopy(doc)
    ring = injected['rings'][0]
    xy = ring['xy']
    corners = list(accumulate(math.dist(a, b) for a, b in zip(xy, xy[1:])))
    for c in corners:
        if not all(abs(c - s) > .01 for s in ring['cuts']) or any(w[1]-.01 <= c <= w[2]+.01 for w in doc['windows'] if w[0] == 0):
            continue
        if any(abs(c - other) < 0.021 for other in [0, *corners, corners[-1] + math.dist(xy[-1], xy[0])] if c != other):
            continue
        s = c - 0.00015
        ring['cuts'] = sorted([*ring['cuts'], c - 0.005, s])
        injected['windows'].append([0, c - 0.005, s, 0, 1, 0.2])
        changed, events = align(injected, eps)
        controls['injected'] = {'changes': events, 'before': verdict(build, injected), 'after': verdict(build, changed)}
        break
    assert sha(G22) == G22_SHA
    return controls


def score_arm(old_score, run, plan, tri, schema, validate, build):
    if run['exit'] != 0 or not plan.is_file():
        return old_score(run, plan, tri, schema, validate, build)
    raw = json.loads(plan.read_text(encoding='utf-8'))
    run['raw_plan_sha256'] = sha(plan)
    run['aligned_jambs'] = []
    if plan.stem == 'candidate':
        modified, events = align(raw, 1e-4)
        run['aligned_jambs'] = events
        baseline = plan.with_name('baseline.json')
        run['raw_arm_parity'] = baseline.read_bytes() == plan.read_bytes()
        plan = plan.with_name('aligned.json')
        plan.write_text(json.dumps(modified, ensure_ascii=False), encoding='utf-8')
    def build_with_receipt(doc):
        result = build(doc)
        run['rings'] = result['report']['rings']
        return result
    return old_score(run, plan, tri, schema, validate, build_with_receipt)


def main(out):
    prior = blob(f'{PRIOR}:docs/research/trainer-revit-intake-r89/replay.py')
    assert subprocess.check_output(['git', 'hash-object', '--stdin'], cwd=ROOT, input=prior).strip() == b'9560d21e0b44b1624ef54a58fcd3fdf8fc8514eb'
    text = prior.decode('utf-8')
    old = "(('baseline', []), ('candidate', ['--keys', KEYS]))"
    assert text.count(old) == 1
    text = text.replace(old, "(('baseline', ['--keys', KEYS]), ('candidate', ['--keys', KEYS]))")
    ns: dict[str, Any] = {'__file__': str(HERE / 'prior.py'), '__name__': 'prior'}
    exec(compile(text, str(HERE / 'prior.py'), 'exec'), ns)
    source = next(iter(ns['INPUTS']))
    ns['check'](source, ns['INPUTS'][source])
    ns['check'](ns['BLENDER'], '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5')
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = out.with_name(out.name + '-source')
    staging.mkdir()
    staged = staging / source.name
    shutil.copyfile(source, staged)
    ns['check'](staged, ns['INPUTS'][source])
    keys = staging / 'keys63.json'
    keys.write_bytes(blob(f'{PRIOR}:docs/research/trainer-revit-intake-r89/keys63.json'))
    ns['check'](keys, 'e13538180229859286c41275df69e86c130b2e944ddb688e07d5cf0712bae11e')
    ns['KEYS'] = keys
    ns['INPUTS'] = {staged: ns['INPUTS'][source], **dict(list(ns['INPUTS'].items())[1:])}
    original = ns['score']
    ns['score'] = lambda *args: score_arm(original, *args)
    core = {}
    exec(compile(blob(CORE), CORE, 'exec'), core)
    controls = {'synthetic': synthetic(core['build_module'], core['EPS_S']),
                'g22': preflight_controls(core['build_module'], core['EPS_S'])}
    ns['main'](out, ns['BLENDER'])
    ns['check'](source, ns['INPUTS'][staged])
    ns['check'](keys, 'e13538180229859286c41275df69e86c130b2e944ddb688e07d5cf0712bae11e')
    receipt = out / 'receipt.json'
    result = json.loads(receipt.read_text(encoding='utf-8'))
    result.update(controls=controls, g22_sha256=G22_SHA, original_source_parity=True,
                  replay_base=PRIOR, candidate_sha256=sha(HERE / 'candidate.py'))
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    if sys.argv[1:] == ['--regression']:
        core = {}
        exec(compile(blob(CORE), CORE, 'exec'), core)
        v = synthetic(core['build_module'], core['EPS_S'])
        print(json.dumps(v, indent=2), flush=True)
        assert 'ring not closed' in v['near']['before']['error']
        assert len(v['near']['changes']) == 1 and 'closure' in v['near']['after']
        assert not v['far']['changes'] and v['far']['before'] == v['far']['after'] and 'closure' in v['far']['after']
        assert 'overlap' in v['overlap']['after']['error']
    else:
        main(Path(sys.argv[1]).resolve())
