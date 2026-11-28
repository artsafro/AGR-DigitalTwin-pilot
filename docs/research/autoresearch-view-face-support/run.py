"""#169 OBSERVE: one-label support refusal in the #149 finish score D, on the pinned #168 ELV fusion runner.

new-case: docs/research/autoresearch-view-face-support/run.py - #169 support-refusal ablation

Research only; no design or finish authority, no production code, no source or delivery writes.
"""
import hashlib
import json
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
R168 = '71fe3bd57764e10c34807d1596c38629baf6a050'
R149 = 'ef84ca410559a5bf7417d7e8803a841e022c5b98'
PINS = {
    '168/run.py': '1aa51f79d44c4c59e9898906a348ddc9909c8cc03cafc044d0db021474c801ef',
    '168/label_tail.py': '800f8de0029e13bd32e5d7e9892f9db8ca8c7d864c6d8efbf4952fa08f869cfb',
    '149/score.py': '4a125268b8c495f15680efe9e8ecf34ae1733de1354403f32f5887d140e2ed24',
}
F168 = '9355a8c728aa40305caaf1b9a74046b283d2aeabc98aabfc52cc5bbdcef6c3a7'
GUARD_OLD = b'    if hv <= 0:\n'
GUARD_NEW = b'    if hv <= 0 or pv.size < 2:\n'
BUDGET_S = 2100
STATES = ('clean', 'blank', 'mirror')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


def pin(key):
    rev, folder = (R168, 'wall-fusion') if key.startswith('168/') else (R149, 'material')
    data = git('show', f'{rev}:docs/research/autoresearch-view-face-{folder}/{key.split("/")[1]}')
    if sha(data) != PINS[key]:
        raise ValueError(f'Wrong bytes: {key}')
    return data


def module(name, source) -> Any:
    mod = types.ModuleType(name)
    mod.__file__ = name
    exec(compile(source, name, 'exec'), mod.__dict__)
    return mod


def variant_source(source):
    if source.count(GUARD_OLD) != 1:
        raise ValueError('Guard line not unique in the pinned scorer')
    return source.replace(GUARD_OLD, GUARD_NEW)


def best_support(score, view, model, slack, shifts=3, min_overlap=0.30):
    """Re-trace D's maximum: (best U, distinct view labels at the first maximising support) — pinned loop, unchanged."""
    filled = view > 0
    total = int(np.count_nonzero(filled))
    if not total or not (model > 0).any():
        return -1.0, 0
    h, w = view.shape
    pad_y = h + 2 * shifts + 2
    mod = np.pad(model, ((pad_y, pad_y), (slack, slack)))
    best, labels = -1.0, 0
    for x in range(mod.shape[1] - w + 1):
        cols = mod[:, x:x + w]
        top = np.flatnonzero((cols > 0).any(axis=1))
        if not len(top):
            continue
        for s in range(-shifts, shifts + 1):
            y = int(top[0]) + s
            crop = cols[y:y + h]
            both = filled & (crop > 0)
            if int(np.count_nonzero(both)) < min_overlap * total:
                continue
            u = score.uncertainty(view[both], crop[both])
            if u > best:
                best, labels = u, int(np.unique(view[both]).size)
    return best, labels


def traced(score, variant):
    log = []

    def face_score(view, model, slack):
        d, labels = best_support(score, view, model, slack)
        if round(d, 9) != round(float(score.face_score(view, model, slack)), 9):
            raise ValueError('Re-trace parity failure against the pinned D')
        dv = float(variant.face_score(view, model, slack))
        log.append(dict(d=round(d, 9), d_support_labels=labels, d_prime=round(dv, 9)))
        return dv

    shim = types.SimpleNamespace(face_score=face_score, decide=variant.decide)
    return shim, log


def aligned(rows, log):
    out, i = [], 0
    for row in rows:
        for state in STATES:
            for wall in row[state]['scores']:
                out.append(dict(view=row['name'], state=state, wall=wall, **log[i]))
                i += 1
    if i != len(log):
        raise ValueError('Score log misaligned')
    return out


def checks(v_rows, entries):
    v = {row['name']: row for row in v_rows}
    changed = [e for e in entries if e['d'] != e['d_prime']]
    win = v['p19 6-1']['clean']['d']
    support = {(e['view'], e['state'], e['wall']): e['d_support_labels'] for e in entries}
    exercised = [(row[s], s) for row in v_rows for s in ('clean', 'mirror') if row[s]['exercised']]
    return {
        'p20_mirror_not_W12': v['p20 frag 9-10']['mirror']['f'] != 'W12',
        'p19_6-1_degenerate_win_gone': win is None or support[('p19 6-1', 'clean', win)] >= 2,
        'retention_p18_I-A': v['p18 I-A']['clean']['f'] == 'W08',
        'clean_wrong_0': all(row['clean']['f_outcome'] != 'wrong' for row in v_rows),
        'blanks_abstain': all(row['blank']['f'] is None for row in v_rows),
        'primary_wrong_le_1': sum(r['f_outcome'] == 'wrong' for r, _ in exercised) <= 1,
        'changed_only_one_label': all(c['d_support_labels'] < 2 for c in changed),
    }


def main(out):
    lock = (REPO / 'uv.lock').read_bytes()
    me = Path(__file__).resolve().relative_to(REPO).as_posix()
    if sha(lock) != sha(git('show', f'{R149}:uv.lock')) or sha(Path(__file__).read_bytes()) != sha(git('show', f'HEAD:{me}')):
        raise ValueError('Lock or measured script bytes differ from the pinned Git revision')
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    host = out / 'r168'
    host.mkdir()
    (host / 'label_tail.py').write_bytes(pin('168/label_tail.py'))
    r168 = module('r168', pin('168/run.py'))
    r168.HERE = host
    m167, ctx, fill, score = r168.stage(out)
    if sha(git('show', f'{R149}:docs/research/autoresearch-view-face-material/score.py')) != PINS['149/score.py']:
        raise ValueError('Scorer pin drift')
    variant = module('score_v', variant_source(pin('149/score.py')))
    fx = ctx[6]
    native = {role: m167.sha_file(row['path']) for role, row in fx['inputs'].items()}
    native['blender'] = m167.sha_file(ctx[1].BLENDER)
    if native != {key: row['sha256'] for key, row in fx['inputs'].items()} | {'blender': m167.BLENDER_SHA}:
        raise ValueError('Pinned native inputs mismatch')
    receipt: dict[str, Any] = dict(schema='support-refusal/1', measured_head=git('rev-parse', 'HEAD').decode().strip(),
                                   pins=PINS, guard=[GUARD_OLD.decode(), GUARD_NEW.decode()], native=native,
                                   lock_sha256=sha(lock), python=sys.version.split()[0], pairs=[])
    status = 'finished'
    for i in range(3):
        pair = out / f'pair-{i + 1}'
        begin = time.monotonic()
        base, timing = m167.one_run(ctx, pair)
        digest_a = sha(r168.canonical(base))
        if digest_a != r168.BASELINE:
            raise ValueError(f'#167 A parity failure: {digest_a}')
        body_f = r168.compare(pair, base, ctx, fill, score)
        (pair / 'f_body.json').write_bytes(r168.canonical(body_f))
        digest_f = sha(r168.canonical(body_f))
        if digest_f != F168:
            (pair / 'unexpected_f.json').write_bytes(r168.canonical(body_f))
            raise ValueError(f'#168 F parity failure: {digest_f}')
        shim, log = traced(score, variant)
        body_v = r168.compare(pair, base, ctx, fill, shim)
        payload = r168.canonical(dict(body=body_v, entries=aligned(body_v['rows'], log)))
        (pair / 'variant.json').write_bytes(payload)
        wall = time.monotonic() - begin
        receipt['pairs'].append(dict(a_sha256=digest_a, f_sha256=digest_f, variant_sha256=sha(payload),
                                     baseline_stage_s=timing, wall_s=wall, scores_logged=len(log)))
        print(f'pair {i + 1}: {wall:.3f} s, A+F parity OK, variant {sha(payload)}', flush=True)
        if i < 2 and time.monotonic() - start + receipt['pairs'][0]['wall_s'] * 1.15 * (2 - i) > BUDGET_S:
            status = 'budget_stop'
            break
    if git('rev-parse', 'HEAD').decode().strip() != receipt['measured_head'] or any(
            m167.sha_file(row['path']) != native[role] for role, row in fx['inputs'].items()):
        raise ValueError('Postflight provenance drift')
    elapsed = time.monotonic() - start
    if elapsed > BUDGET_S:
        status = 'budget_stop'
    if len({p['variant_sha256'] for p in receipt['pairs']}) != 1:
        status = 'parity_failure'
    first = json.loads((out / 'pair-1' / 'variant.json').read_bytes())
    f_rows = json.loads((out / 'pair-1' / 'f_body.json').read_bytes())['rows']
    changed = [e for e in first['entries'] if e['d'] != e['d_prime']]
    result = checks(first['body']['rows'], first['entries'])
    walls = [p['wall_s'] for p in receipt['pairs']]
    receipt.update(status=status, result=('confirmed' if all(result.values()) else 'refuted')
                   if status == 'finished' else 'inconclusive', checks=result,
                   med_s=statistics.median(walls), spread_s=max(walls) - min(walls), elapsed_s=elapsed,
                   counts_f=r168.tally(f_rows), counts_variant=r168.tally(first['body']['rows']),
                   changed=changed,
                   answers={row['name']: {s: [f_row[s]['f'], row[s]['f'], row[s]['f_outcome']] for s in STATES}
                            for row, f_row in zip(first['body']['rows'], f_rows)})
    (out / 'receipt.json').write_bytes(r168.canonical(receipt))
    print(json.dumps({k: receipt[k] for k in ('status', 'result', 'med_s', 'spread_s', 'checks', 'changed')}, indent=1))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
