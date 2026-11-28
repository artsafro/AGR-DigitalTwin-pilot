"""#151 OBSERVE: transfer of the #149 finish-partition score D (unchanged) to a second pair (Olimpijsky FOK).

new-case: docs/research/autoresearch-view-face-transfer/run.py - #151 OBSERVE transfer replay runner

Research only; no product code, no delivery edits. Replay from the repository root (pilot host, inputs mounted):
    git fetch origin research/autoresearch-standing-145 research/autoresearch-standing-149
    uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-transfer/run.py <new_out_dir> [--runs 3]
The #149 runner, scorer and ray script and the #145 helpers are staged from pinned git revisions and executed as
is; the only byte change is the frozen outlier-height literal in rays_type.py (fixture.json `rays_change`).
"""
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from time import monotonic

HERE = Path(__file__).resolve().parent
R149 = '94b74bcaeb2e00d6cdc1d486bf59ac7420bdf854'
R145 = '640b3678fb18ac2e5811742116a92e96ef236ab6'
PINS = {
    'r149.py': (R149, 'docs/research/autoresearch-view-face-material/run.py'),
    'score.py': (R149, 'docs/research/autoresearch-view-face-material/score.py'),
    'rays_type.py': (R149, 'docs/research/autoresearch-view-face-material/rays_type.py'),
    'r145.py': (R145, 'docs/research/autoresearch-view-face-elv/run.py'),
}
RAYS_OLD, RAYS_NEW = b'> 30.0)', b'> 60.0)'
BUDGET_S = 3600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(out):
    out.mkdir(parents=True)
    pins = {}
    for name, (rev, path) in PINS.items():
        data = subprocess.run(['git', 'show', f'{rev}:{path}'], check=True, capture_output=True).stdout
        pins[name] = hashlib.sha256(data).hexdigest()
        if name == 'rays_type.py':
            if data.count(RAYS_OLD) != 1:
                raise ValueError('rays_type.py outlier literal not found exactly once')
            data = data.replace(RAYS_OLD, RAYS_NEW)
            pins['rays_type.py@patched'] = hashlib.sha256(data).hexdigest()
        (out / name).write_bytes(data)
    shutil.copyfile(HERE / 'fixture.json', out / 'fixture.json')
    fx = json.loads((out / 'fixture.json').read_text(encoding='utf-8'))
    for role, row in fx['inputs'].items():
        if sha(row['path']) != row['sha256']:
            raise ValueError(f'input SHA-256 mismatch: {role}')
        shutil.copyfile(row['path'], out / f'elv.{role}')  # #149 measure() reads out/elv.pdf and out/elv.fbx
        if sha(out / f'elv.{role}') != row['sha256']:
            raise ValueError(f'staged copy mismatch: {role}')
        pins[role] = row['sha256']
    pins['fixture.json'] = sha(out / 'fixture.json')
    pins['run.py'] = sha(HERE / 'run.py')
    return fx, pins


def g_wrap(S, log):
    """Pre-declared diagnostic G (contract): D unchanged when the view fits the face (+-slack); when the view is
    wider than the face + 2 slack, slide face-width windows of the view (step 2*slack+1 px = gap-free with the
    +-slack search), trim each window to its own top row and score it with the unchanged D. Records (D, G)."""
    d_score = S.face_score

    def wrapped(view, model, slack, *a, **k):
        d = d_score(view, model, slack, *a, **k)
        h, w = view.shape
        wm = model.shape[1]
        g = d
        if w > wm + 2 * slack:
            g = -1.0
            for x in range(0, w - wm + 1, 2 * slack + 1):
                win = view[:, x:x + wm]
                rows = (win > 0).any(axis=1).nonzero()[0]
                if len(rows):
                    g = max(g, d_score(win[rows[0]:], model, slack, *a, **k))
        log.append((round(float(d), 9), round(float(g), 9), int(w > wm + 2 * slack)))
        return d
    return wrapped


def attach_g(rows, log, faces, permute, S):
    """Map the wrapper log back to rows: per row len(faces) scoring calls, plus len(faces) on the permuted run."""
    per = len(faces) * (2 if permute else 1)
    if len(log) != per * len(rows):
        raise ValueError(f'G log length {len(log)} != {per} x {len(rows)}')
    for i, r in enumerate(rows):
        calls = log[i * per:i * per + len(faces)]
        if [c[0] for c in calls] != [r['scores'][str(az)] for az in faces]:
            raise ValueError('G log / D score parity failed')
        g = {az: c[1] for az, c in zip(faces, calls)}
        pick = S.decide(g)
        r['G_scores'] = {str(a): v for a, v in g.items()}
        r['G_windowed'] = sum(c[2] for c in calls)
        r['G'] = 'abstain' if pick is None else 'correct' if pick == r['gt_az'] else 'wrong'
        r['G_pick'] = pick


def verdict(sd, rows):
    """Frozen H151 acceptance (contract in autoresearch-view-face-transfer.md)."""
    w = {r['view'] + ' ' + r['case']: r for r in rows}
    return dict(
        full_wrong_0=sd['full']['wrong'] == 0,
        full_correct_ge3=sd['full']['correct'] >= 3,
        crop_wrong_le1=sd['synthetic_crop']['wrong'] <= 1,
        crop_correct_ge15=sd['synthetic_crop']['correct'] >= 15,
        witness_p5_full=w['p5 228.8-86.8 full']['outcome'] == 'correct',
    )


def main():
    out = Path(sys.argv[1]).resolve()
    runs_n = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 3
    if out.exists():
        raise SystemExit(f'output exists: {out}')
    t0 = monotonic()
    fx, pins = stage(out)
    r145 = runpy.run_path(str(out / 'r145.py'), run_name='r145')
    r149 = runpy.run_path(str(out / 'r149.py'), run_name='r149')
    pins['blender_sha256'] = r149['EXE_HASH']
    if sha(r149['BLENDER']) != r149['EXE_HASH']:
        raise ValueError('Blender 4.4 hash mismatch')
    runs, walls, status, inv = [], [], 'finished', None
    for run in range(1, runs_n + 1):
        if run > 1 and (monotonic() - t0) + 1.15 * walls[0] * (runs_n - run + 1) > BUDGET_S:
            status = 'inconclusive_budget_stop'
            break
        t = monotonic()
        S, log = r149['S'], []
        orig = S.face_score
        S.face_score = g_wrap(S, log)
        try:
            rows, changed = r149['measure'](out, run, fx, r145, permute=(run == 1))
        finally:
            S.face_score = orig
        attach_g(rows, log, fx['faces_az'], run == 1, S)
        if run == 1:
            inv = changed
        walls.append(round(monotonic() - t, 3))
        runs.append(rows)
        (out / f'run-{run}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding='utf-8')
        print(f'run {run}: {walls[-1]} s', flush=True)
    keyed = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in runs]
    identical = all(k == keyed[0] for k in keyed)
    rows = runs[0]
    sd = r149['summarize'](rows)
    sg = r149['summarize'](rows, 'G')
    checks = verdict(sd, rows)
    g_checks = dict(full_wrong_0=sg['full']['wrong'] == 0, full_correct_ge3=sg['full']['correct'] >= 3,
                    crop_wrong_le1=sg['synthetic_crop']['wrong'] <= 1,
                    crop_equal_D_where_not_windowed=all(r['G'] == r['outcome'] for r in rows if not r['G_windowed']))
    hyp = 'confirmed' if all(checks.values()) else 'refuted'
    if status == 'finished' and (not identical or len(runs) < runs_n):
        status = 'parity_failed'
    ws = sorted(walls)
    receipt = dict(card="t_a117effc (#151)", g_checks=g_checks, summary_G=sg, status=status, hypothesis=hyp, checks=checks,
                   invariance_rows_changed=inv, invariance_rows=len(rows), pins=pins,
                   uv_lock_sha256=sha('uv.lock'), runs=len(runs), run_wall_s=walls,
                   median_s=ws[len(ws) // 2], min_s=ws[0], max_s=ws[-1],
                   total_wall_s=round(monotonic() - t0, 3), runs_identical=identical,
                   run_content_sha256=[hashlib.sha256(k.encode()).hexdigest() for k in keyed],
                   summary_D=sd, rows=rows)
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(status=status, hypothesis=hyp, checks=checks, g_checks=g_checks, D=sd, G=sg, identical=identical,
                          walls=walls, inv=inv), ensure_ascii=False))


if __name__ == '__main__':
    main()
