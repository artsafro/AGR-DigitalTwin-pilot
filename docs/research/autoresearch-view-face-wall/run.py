"""#153 OBSERVE runner: wall-level view -> face on ELV (#149 D side + W0/W1 wall localisation).

new-case: docs/research/autoresearch-view-face-wall/run.py - #153 wall-level runner

Usage: uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-wall/run.py <fresh_dir>
Research only: reads pinned inputs, writes only <fresh_dir>.
"""
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import monotonic

import numpy as np
import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wall as WL  # noqa: E402

BLENDER = Path('C:/Program Files/Blender Foundation/Blender 4.4/blender.exe')
EXE_HASH = 'fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5'
R149 = '94b74bcaeb2e00d6cdc1d486bf59ac7420bdf854'
R145 = '640b3678fb18ac2e5811742116a92e96ef236ab6'
PINS = {
    'fixture.json': (R145, 'docs/research/autoresearch-view-face-elv/fixture.json'),
    'r145.py': (R145, 'docs/research/autoresearch-view-face-elv/run.py'),
    'score.py': (R149, 'docs/research/autoresearch-view-face-material/score.py'),
    'r149.py': (R149, 'docs/research/autoresearch-view-face-material/run.py'),
}
EV149 = Path('G:/Мой диск/AGR-evidence/149-view-face-material/r1b')
RES = 0.2
TAU_LOC, PLANE_GAP_M, TOL_M, WIDTH_TOL_M = 0.05, 1.0, 1.0, 1.0
REF = {'p23 frag D-G': ('p18 I-A', (255, 280)), 'p24 frag 8-9': ('p18 1-10', (515, 530))}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(out):
    out.mkdir(parents=True)
    pins = {}
    for name, (rev, path) in PINS.items():
        data = subprocess.run(['git', 'show', f'{rev}:{path}'], check=True, capture_output=True).stdout
        (out / name).write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    fx = json.loads((out / 'fixture.json').read_text(encoding='utf-8'))
    for role, row in fx['inputs'].items():
        if sha(row['path']) != row['sha256']:
            raise ValueError(f'input SHA-256 mismatch: {role}')
        shutil.copyfile(row['path'], out / f'elv.{role}')
        pins[role] = row['sha256']
    if sha(BLENDER) != EXE_HASH:
        raise ValueError('Blender 4.4 hash mismatch')
    for name in ('rays_wall.py', 'wall.py', 'run.py'):
        pins[name] = sha(HERE / name)
    return fx, pins


def load_models(npz, azs, ref_npz):
    models, cplanes, parity = {}, {}, {}
    with np.load(npz) as rays, np.load(ref_npz) as ref:
        for az in azs:
            lab = rays[f'az{az:03d}_type']
            parity[az] = bool(np.array_equal(lab, ref[f'az{az:03d}_type']))
            dep = rays[f'az{az:03d}_depth']
            cols = np.flatnonzero((lab > 0).any(axis=0))
            lab, dep = lab[:, cols[0]:cols[-1] + 1], dep[:, cols[0]:cols[-1] + 1]
            _, inv = np.unique(lab, return_inverse=True)
            models[az] = inv.reshape(lab.shape).astype(np.int32)
            cplanes[az] = WL.planes(WL.column_depth(dep), PLANE_GAP_M)
    return models, cplanes, parity


def view_geom(r145, r149, page, v, res_m):
    s = r145['scale_pt_per_m'](page, v)
    seg = r145['segments'](page, v['box_pt'], s)
    img = r145['raster_view'](seg, res_m)
    occ = np.where(img.any(0), img.argmax(0), img.shape[0])
    span = np.flatnonzero((img.shape[0] - occ) * res_m >= 2.0)
    x0 = int(span[0]) if len(span) else 0
    x1 = int(span[-1]) + 1 if len(span) else img.shape[1]
    seg_x0, seg_ytop = seg[:, [0, 2]].min(), -seg[:, [1, 3]].max()
    h_px = int(np.ceil((seg[:, [1, 3]].max() - seg[:, [1, 3]].min()) / RES)) + 1
    w_px = int(np.ceil((seg[:, [0, 2]].max() - seg_x0) / RES)) + 1
    labels, palette = r149['view_labels'](page, v['box_pt'], s, seg_x0, seg_ytop, w_px, h_px)
    return dict(s=s, img=img, x0=x0, width=x1 - x0, seg_x0=seg_x0, labels=labels, palette=palette)


def axis_cols(r145, page, g, labels, band, v, res_m):
    """Axis label x -> label-raster column relative to the view's tall-span left edge (RES px)."""
    out = []
    for lab in labels:
        x = r145['word_center'](page, lab, band, v.get('x_min_label_pt', -1e9), v.get('x_max_label_pt', 1e9))[0]
        out.append((x / g['s'] - g['seg_x0']) / RES - round(g['x0'] * res_m / RES))
    return out


def measure(out, run, fx, r145, r149):
    S = r149['S']
    npz = out / f'rays-{run}.npz'
    cmd = [str(BLENDER), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
           '-P', str(HERE / 'rays_wall.py'), '--', str(out / 'elv.fbx'), str(npz), str(RES),
           ','.join(map(str, fx['faces_az']))]
    with (out / f'rays-{run}.log').open('xb') as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1200)
    models, cplanes, parity = load_models(npz, fx['faces_az'], EV149 / 'types-1.npz')
    slack = round(fx['decision']['width_slack_m'] / RES)
    res_m = fx['res_m']
    doc = pymupdf.open(out / 'elv.pdf')
    geoms = {t: view_geom(r145, r149, doc[v['page'] - 1], v, res_m) for t, v in fx['views'].items()}
    dominant = {az: WL.interval_wall(cp, 0, cp.size) for az, cp in cplanes.items()}
    rows = []
    for title, v in fx['views'].items():
        g, page = geoms[title], doc[v['page'] - 1]
        gt_az = v['gt_az']
        cp = cplanes[gt_az]
        width_ok = abs(g['width'] * res_m - models[gt_az].shape[1] * RES) <= WIDTH_TOL_M
        for kind, offset, length in r145['cases'](v['kind'], g['width'], fx['partials']):
            i0 = int(round((g['x0'] + offset) * res_m / RES))
            n = max(1, int(round(length * res_m / RES)))
            line_rows = np.flatnonzero(g['img'][:, g['x0'] + offset:g['x0'] + offset + length].any(axis=1))
            top_px = int(round(line_rows[0] * res_m / RES)) if len(line_rows) else 0
            view = g['labels'][top_px:, i0:i0 + n]
            if kind == 'mirror':
                view = view[:, ::-1]
            scores = {az: round(float(S.face_score(view, models[az], slack)), 9) for az in fx['faces_az']}
            pick = S.decide(scores)
            side = 'abstain' if pick is None else 'correct' if pick == gt_az else 'wrong'
            # ground truth start column (model px) and wall
            gt_start, gt_note = None, None
            if kind.startswith('fragment'):
                if title in REF:
                    ref_t, band = REF[title]
                    rg, rv = geoms[ref_t], fx['views'][ref_t]
                    a, b = v['scale'][0], v['scale'][1]
                    try:
                        ref_cols = axis_cols(r145, doc[rv['page'] - 1], rg, (a, b), band, rv, res_m)
                        own_cols = axis_cols(r145, page, g, (a, b), v['scale'][3], v, res_m)
                        ref_ok = abs(rg['width'] * res_m - models[gt_az].shape[1] * RES) <= WIDTH_TOL_M
                        if ref_ok:
                            gt_start = float(np.mean([r - o for r, o in zip(ref_cols, own_cols)]))
                        else:
                            gt_note = 'reference full width mismatch'
                    except ValueError as exc:
                        gt_note = str(exc)
                else:
                    gt_note = 'no reference axes (top-cut)'
            elif width_ok:
                gt_start = float(i0 - round(g['x0'] * res_m / RES))
            else:
                gt_note = 'parent full width mismatch'
            gt_wall = None if gt_start is None else WL.interval_wall(cp, int(round(gt_start)), int(round(gt_start)) + n)
            row = dict(view=title, case=kind, gt_az=gt_az, width_m=round(length * res_m, 1), pick=pick,
                       side=side, scores={str(a): s for a, s in scores.items()},
                       gt_start_px=None if gt_start is None else round(gt_start, 2), gt_wall=gt_wall,
                       gt_note=gt_note, nontrivial=None if gt_wall is None else gt_wall != dominant[gt_az])
            if pick is not None:
                prof = WL.profile(view, models[pick], slack, S.uncertainty)
                if round(float(prof.max()), 9) != scores[pick]:
                    raise ValueError(f'profile parity failed: {title} {kind}')
                start, w0, w1, walls = WL.localise(prof, cplanes[pick], slack, n, TAU_LOC)
                row.update(pred_start_px=start, w0_wall=w0, w1_wall=w1, near_walls=walls,
                           near_n=int(np.count_nonzero(prof >= prof.max() - TAU_LOC)),
                           loc_err_m=None if gt_start is None or pick != gt_az
                           else round(abs(start - gt_start) * RES, 2))
            else:
                row.update(pred_start_px=None, w0_wall=None, w1_wall=None, near_walls=[], near_n=0, loc_err_m=None)
            if gt_wall is None:
                row['W0'] = row['W1'] = 'abstain' if pick is None else 'not_exercised'
            else:
                row['W0'] = WL.outcome(pick, gt_az, row['w0_wall'], gt_wall)
                row['W1'] = WL.outcome(pick, gt_az, row['w1_wall'], gt_wall)
            row['interval_ok'] = None if row['loc_err_m'] is None else row['loc_err_m'] <= TOL_M
            rows.append(row)
    stats = {str(az): dict(width_m=round(models[az].shape[1] * RES, 1),
                           planes=int(cplanes[az].max()) + 1,
                           dominant=dominant[az],
                           plane_cols=Counter(int(p) for p in cplanes[az] if p >= 0).most_common())
             for az in fx['faces_az']}
    return rows, parity, stats


def side_parity(rows):
    ref = json.loads((EV149 / 'run-1.json').read_text(encoding='utf-8'))
    a = [(r['view'], r['case'], r['pick'], r['side']) for r in rows]
    b = [(r['view'], r['case'], r['pick'], r['outcome']) for r in ref]
    return a == b, len(b)


def main():
    out = Path(sys.argv[1]).resolve()
    runs_n = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 3
    if out.exists():
        raise SystemExit(f'output exists: {out}')
    t0 = monotonic()
    fx, pins = stage(out)
    r145 = runpy.run_path(str(out / 'r145.py'), run_name='r145')
    r149 = runpy.run_path(str(out / 'r149.py'), run_name='r149')
    runs, walls, status, parity, stats = [], [], 'finished', None, None
    for run in range(1, runs_n + 1):
        elapsed = monotonic() - t0
        if run == 2 and walls[0] > 400:
            status = 'inconclusive_budget_stop'
            break
        if run > 1 and elapsed + 1.15 * walls[0] * (runs_n - run + 1) > 1500:
            status = 'inconclusive_budget_stop'
            break
        t = monotonic()
        rows, par, st = measure(out, run, fx, r145, r149)
        walls.append(round(monotonic() - t, 3))
        parity = parity or par
        stats = stats or st
        runs.append(rows)
        (out / f'run-{run}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding='utf-8')
        print(f'run {run}: {walls[-1]} s', flush=True)
    keyed = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in runs]
    identical = all(k == keyed[0] for k in keyed)
    rows = runs[0]
    sp_ok, sp_n = side_parity(rows)
    w0, w1 = WL.summarize(rows, 'W0'), WL.summarize(rows, 'W1')
    nt = (lambda r: bool(r['nontrivial']))
    w0_nt, w1_nt = WL.summarize(rows, 'W0', nt), WL.summarize(rows, 'W1', nt)
    hyp, checks, gate = WL.verdict(rows, w1, w1_nt)
    if status == 'finished' and not (identical and all(parity.values()) and sp_ok):
        status = 'parity_failed'
    ws = sorted(walls)
    receipt = dict(card='t_ebb8205e (#153); t_2acb7a29 (#2075)', status=status, hypothesis=hyp,
                   checks=checks, gate=gate,
                   tau_loc=TAU_LOC, plane_gap_m=PLANE_GAP_M, tol_m=TOL_M, width_tol_m=WIDTH_TOL_M,
                   type_parity_149={str(k): v for k, v in parity.items()}, side_parity_149=sp_ok,
                   side_parity_rows=sp_n, pins=pins, blender_sha256=EXE_HASH, uv_lock_sha256=sha('uv.lock'),
                   runs=len(runs), run_wall_s=walls, median_s=ws[len(ws) // 2], min_s=ws[0], max_s=ws[-1],
                   total_wall_s=round(monotonic() - t0, 3), runs_identical=identical,
                   run_content_sha256=[hashlib.sha256(k.encode()).hexdigest() for k in keyed],
                   face_stats=stats, summary_side=WL.summarize(rows, 'side'), summary_W0=w0, summary_W1=w1,
                   summary_W0_nontrivial=w0_nt, summary_W1_nontrivial=w1_nt, rows=rows)
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(status=status, hypothesis=hyp, checks=checks, gate=gate, W0=w0, W1=w1,
                          W1_nontrivial=w1_nt, identical=identical, walls=walls, side_parity=sp_ok,
                          type_parity=parity), ensure_ascii=False))


if __name__ == '__main__':
    main()
