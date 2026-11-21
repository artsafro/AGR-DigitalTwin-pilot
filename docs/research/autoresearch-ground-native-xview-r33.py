"""Standing #33: #32 near-vertex counter (Blender readback) vs native 3ds Max 2026 xView on Ground. OBSERVE, read-only.

  ../../.venv/Scripts/python.exe docs/research/autoresearch-ground-native-xview-r33.py NEW.json

Contract: docs/research/autoresearch-ground-native-xview.md (frozen before measuring). Inputs are hash-checked before
and after; Max works on staged copies under C:/x/ev_t_304e8c0c/max/<run>/ and never saves a scene.
"""
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT), str(ROOT / 'tools' / 'qa')]
from dt_ai.core.blender_runner import run_blender  # noqa: E402
from dt_ai.ops import inv_xview, xview_gate  # noqa: E402
import xview_parity  # noqa: E402

REV31 = '8ee341f74ef5dd453c4fbcc8d07a13713fd1cf38'
REV32 = 'ebb32458a5673e2b142d7fc5b273733621201d71'
H31 = 'docs/research/autoresearch-ground-quality-harness'
INPUTS = Path('C:/x/ev_t_193a0887/inputs')
DUMPS31 = Path('C:/x/ev_t_193a0887/dumps-v002')
W1 = Path('C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx')
W1_SHA = '94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef'
EV = Path('C:/x/ev_t_304e8c0c')
DCC = Path('C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py')
CAP_S = 45 * 60
MAX_VERSION = '2024'   # amendment 1: the runner's CSharpCodeProvider fails on Max 2026 (.NET 8)
PREFIX = 'm2024d-'
NODES = {'A1': 'SM_Vatutino_Ground', 'A2': 'SM_BolshoyBulvar_64_Ground', 'A3': 'SM_Tup_Skladochnyj_ZU_5_1_Ground',
         'A4': 'SM_5jDonskoyProezd_Vl_15_Ground', 'A5': 'SM_NizhnieMnevniki_ZU_66_Ground',
         'A6': 'SM_Kasatkina_Vl_11_Ground', 'A7': 'SM_VolokolamskoeShosse_Vl_71_22_Ground',
         'A8': 'SM_DerevnyaStolbovo_Uch_23_Ground', 'W1': 'SM_Vatutino_Ground'}


def blob(rev, name):
    return subprocess.check_output(['git', 'show', f'{rev}:{name}'], cwd=ROOT)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(p):
    """#32 measure, unchanged: V = unique vertex ids in repo xView 2 mm pairs, T = fan triangles."""
    verts = np.asarray(p.vertices, dtype=np.float64) - p.location
    t = sum(len(f) - 2 for f in p.faces)
    if not t or not np.isfinite(verts).all():
        raise ValueError(p.name)
    a, b, _ = inv_xview.vertex_pairs(verts, inv_xview.tolerance_for('NPM').vertex_m)
    v = int(np.union1d(a, b).size)
    return dict(V=v, T=t, Qv=1e4 * v / t)


def ground(path):
    p, = (p for p in xview_gate.load_npz(path) if p.name.endswith('_Ground') and not p.name.startswith('UCX_'))
    return p


def inputs():
    frozen = {ln.split()[1].lstrip('*'): ln.split()[0]
              for ln in blob(REV31, f'{H31}/inputs.sha256').decode().splitlines() if ln}
    got = {}
    for name, h in frozen.items():
        if name.endswith('.fbx'):
            iid = name.split('_')[0]
            got[iid] = (INPUTS / name, h)
    got['W1'] = (W1, W1_SHA)
    for iid, (p, h) in got.items():
        if sha(p) != h:
            raise SystemExit(f'input hash mismatch: {iid} {p}')
    return dict(sorted(got.items()))


def dump_w1():
    """W1 through the #31 pipeline (fbx_to_blend at REV31 + repo Blender dump + to_metres)."""
    dst = EV / 'dumps' / 'W1_Vatutino_v014_NPM.npz'
    if dst.exists():
        return dst, json.loads((dst.parent / 'W1.info.json').read_text(encoding='utf-8'))
    tmp = EV / 'dumps' / 'W1.tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    f2b = tmp / 'fbx_to_blend.py'
    f2b.write_bytes(blob(REV31, f'{H31}/fbx_to_blend.py'))
    npz, man, blend = tmp / 'parts.npz', tmp / 'manifest.json', tmp / 'scene.blend'
    run_blender(f2b, [W1.resolve(), blend], outputs=[blend], timeout=3600, log_path=tmp / 'fbx_to_blend.log')
    dump = run_blender(xview_gate.DUMP_SCRIPT, [blend, npz, man], output_json=man, outputs=[npz],
                       timeout=3600, log_path=tmp / 'blender.log')
    parts, units = xview_gate.to_metres(xview_gate.load_npz(npz), dump)
    xview_gate.save_npz(dst, parts)
    info = dict(units=units, dropped=dump.get('dropped', []), blender=dump.get('blender'), sha256=sha(dst))
    (dst.parent / 'W1.info.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
    return dst, info


def settle():
    """Amendment 2: start Max only after the previous batch Max 2024 process has exited, plus 20 s.

    The user's interactive 3ds Max 2026 sessions are always open and are ignored (path filter)."""
    ps = ("@(Get-Process 3dsmax,3dsmaxbatch -ErrorAction SilentlyContinue | "
          "Where-Object { $_.Path -like '*3ds Max " + MAX_VERSION + "*' }).Count")
    for _ in range(120):
        n = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True).stdout.strip()
        if n == b'0':
            break
        time.sleep(5)
    time.sleep(20)


def max_run(name, ids, mode, ins):
    name = PREFIX + name
    out = EV / 'max' / name
    if out.exists():
        raise SystemExit(f'run dir exists: {out}')
    out.mkdir(parents=True)
    jobs = [dict(label=f'{i}_{mode}', path=str(ins[i][0]), node=NODES[i], mode=mode, material='', slot='')
            for i in ids]
    xview_parity.prepare_run(jobs, out, EV / 'max' / f'{name}-stage')
    env = dict(os.environ, XVIEW_OUT=str(out), XVIEW_TEMP=str(EV / 'max' / f'{name}-stage'))
    settle()
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, str(DCC), 'max', '--version', MAX_VERSION, '--file',
                           str(ROOT / 'tools/qa/xview_dump.ms'), '--timeout', '2400', '--wait', '1800',
                           '--card', 't_304e8c0c', '--out', str(EV / 'max' / f'{name}.dcc.json')],
                          env=env, capture_output=True, text=True)
    wall = time.monotonic() - t0
    status = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-400:]
    try:
        parsed = xview_parity.check_run(out, [j['label'] for j in jobs])
    except xview_parity.DumpError as exc:
        return dict(ok=False, wall_s=wall, dcc=status, error=str(exc)), {}
    rows = {}
    for i in ids:
        d = parsed[f'{i}_{mode}']
        rows[i] = dict(node=d['node'], sourceClass=d['sourceClass'], verts=d['verts'], faces=d['faces'],
                       tris=d['tris'], ngons=d['ngons'], V_max=d['verticesCheck']['count'],
                       F_max=d['facesCheck']['count'], tolVerts=d['tolVerts'], units=d['units'],
                       sha256_before=d['sha256_before'], sha256_after=d['sha256_after'],
                       V_seconds=d['verticesCheck']['seconds'], F_seconds=d['facesCheck']['seconds'])
    return dict(ok=True, wall_s=wall, dcc=status), rows


def main(out):
    if out.exists():
        raise SystemExit(f'{out} exists')
    t_start = time.monotonic()
    ins = inputs()
    report = dict(max_version=MAX_VERSION, contract='docs/research/autoresearch-ground-native-xview.md', rev31=REV31, rev32=REV32,
                  inputs={i: dict(path=p.as_posix(), sha256=h) for i, (p, h) in ins.items()})
    # Repo side: A from the frozen #31 dumps (parity with the #32 receipt), W1 freshly dumped.
    r32 = json.loads(blob(REV32, 'docs/research/autoresearch-ground-near-vertices-r32.json'))['rows']
    repo, parity32 = {}, {}
    for i in [k for k in ins if k.startswith('A')]:
        path = DUMPS31 / r32[i]['dump']
        if sha(path) != r32[i]['sha256']:
            raise SystemExit(f'dump mismatch {path}')
        reps = [measure(ground(path)) for _ in range(3)]
        repo[i] = dict(runs=reps, V=reps[0]['V'], T=reps[0]['T'], Qv=statistics.median(r['Qv'] for r in reps),
                       spread=max(r['Qv'] for r in reps) - min(r['Qv'] for r in reps))
        parity32[i] = all(r['V'] == r32[i]['clean_runs'][0]['V'] and r['T'] == r32[i]['clean_runs'][0]['T']
                          for r in reps)
    w1, info = dump_w1()
    reps = [measure(ground(w1)) for _ in range(3)]
    repo['W1'] = dict(runs=reps, V=reps[0]['V'], T=reps[0]['T'], Qv=statistics.median(r['Qv'] for r in reps),
                      spread=max(r['Qv'] for r in reps) - min(r['Qv'] for r in reps), dump=w1.as_posix(), info=info)
    report.update(repo=repo, parity32=parity32)
    # Native side.
    runs = {}
    meta, rows = max_run('pair', ['A1', 'W1'], 'plain', ins)
    runs['pair'] = dict(meta=meta, rows=rows)
    if not meta['ok']:
        report.update(hypothesis='inconclusive', reason='first pair failed', runs=runs)
        return finish(out, report, ins)
    faces = {i: repo[i]['T'] for i in ins}
    t_full = meta['wall_s'] * sum(faces.values()) / (faces['A1'] + faces['W1'])
    report['budget'] = dict(first_pair_s=meta['wall_s'], projected_full_s=t_full, projected_series_s=4 * t_full,
                            cap_s=CAP_S)
    if 4 * t_full > CAP_S:
        report.update(hypothesis='inconclusive', reason='projected series exceeds cap', runs=runs)
        return finish(out, report, ins)
    ids = list(ins)
    for name, mode in (('run1', 'plain'), ('run1wp', 'weldpoly'), ('run2', 'plain'), ('run3', 'plain')):
        meta, rows = max_run(name, ids, mode, ins)
        runs[name] = dict(meta=meta, rows=rows)
        if not meta['ok'] or time.monotonic() - t_start > CAP_S + 600:
            report.update(hypothesis='inconclusive', reason=f'{name} failed or over cap', runs=runs)
            return finish(out, report, ins)
    report['runs'] = runs
    keys = ('verts', 'faces', 'tris', 'V_max', 'F_max', 'sourceClass')
    stable = {i: all(runs[r]['rows'][i][k] == runs['run1']['rows'][i][k] for r in ('run2', 'run3') for k in keys)
              for i in ids}
    vmax = {i: statistics.median(runs[r]['rows'][i]['V_max'] for r in ('run1', 'run2', 'run3')) for i in ids}
    rule = {i: (repo[i]['V'] > 0) == (vmax[i] > 0) for i in ids}
    unchanged = all(row['sha256_before'] == row['sha256_after'] == ins[i][1]
                    for r in runs.values() for i, row in r['rows'].items())
    report.update(stable=stable, V_max_median=vmax, presence_rule=rule, inputs_unchanged=unchanged,
                  Qv_max={i: 1e4 * vmax[i] / runs['run1']['rows'][i]['tris'] if runs['run1']['rows'][i]['tris']
                          else None for i in ids})
    ok = all(stable.values()) and unchanged and all(parity32.values())
    report['hypothesis'] = ('confirmed' if ok and all(rule.values()) else 'refuted' if ok else 'inconclusive')
    return finish(out, report, ins)


def finish(out, report, ins):
    for i, (p, h) in ins.items():
        if sha(p) != h:
            raise SystemExit(f'input changed: {p}')
    report['numpy'] = np.__version__
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=1)
        stream.write('\n')
    print(report['hypothesis'], report.get('reason', ''), report.get('budget'))
    return 0


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1])))
