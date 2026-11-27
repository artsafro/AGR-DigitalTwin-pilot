"""#149 OBSERVE: finish-partition agreement (PDF fill colours vs Revit type labels) for view -> face on ELV.

new-case: docs/research/autoresearch-view-face-material/run.py - #149 OBSERVE replay runner

Research only; no product code, no delivery edits. Replay from the repository root (pilot host, inputs mounted):
    uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-material/run.py <new_out_dir> [--runs 3]
Needs `git fetch origin research/autoresearch-standing-145 research/autoresearch-standing-147` (pinned bytes).
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
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score as S  # noqa: E402

BLENDER = Path('C:/Program Files/Blender Foundation/Blender 4.4/blender.exe')
EXE_HASH = 'fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5'
PINS = {
    'fixture.json': ('640b3678fb18ac2e5811742116a92e96ef236ab6', 'docs/research/autoresearch-view-face-elv/fixture.json'),
    'r145.py': ('640b3678fb18ac2e5811742116a92e96ef236ab6', 'docs/research/autoresearch-view-face-elv/run.py'),
    'r147_receipt.json': ('159dffcb33f81c4bf566a1da1ec659603b4fa957', 'docs/research/autoresearch-view-face-veto/receipt.json'),
}
RES, FINE = 0.2, 4  # label raster m/px; fine raster = RES / FINE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_bytes(rev, path):
    return subprocess.run(['git', 'show', f'{rev}:{path}'], check=True, capture_output=True).stdout


def stage(out):
    out.mkdir(parents=True)
    pins = {}
    for name, (rev, path) in PINS.items():
        data = git_bytes(rev, path)
        (out / name).write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    fx = json.loads((out / 'fixture.json').read_text(encoding='utf-8'))
    for role, row in fx['inputs'].items():
        if sha(row['path']) != row['sha256']:
            raise ValueError(f'input SHA-256 mismatch: {role}')
        shutil.copyfile(row['path'], out / f'elv.{role}')
        if sha(out / f'elv.{role}') != row['sha256']:
            raise ValueError(f'staged copy mismatch: {role}')
        pins[role] = row['sha256']
    if sha(BLENDER) != EXE_HASH:
        raise ValueError('Blender 4.4 hash mismatch')
    for name in ('rays_type.py', 'score.py', 'run.py'):
        pins[name] = sha(HERE / name)
    return fx, pins


def polygons(d):
    """Fill polygons of one drawing: re/qu items, l/c chains split where the path is discontinuous."""
    polys, cur = [], []
    for item in d['items']:
        if item[0] == 're':
            r = item[1]
            polys.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        elif item[0] == 'qu':
            q = item[1]
            polys.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)])
        elif item[0] in ('l', 'c'):
            a, b = item[1], item[-1]
            if cur and (abs(cur[-1][0] - a.x) > 1e-3 or abs(cur[-1][1] - a.y) > 1e-3):
                polys.append(cur)
                cur = []
            if not cur:
                cur.append((a.x, a.y))
            cur.append((b.x, b.y))
    if cur:
        polys.append(cur)
    return [p for p in polys if len(p) >= 3]


def view_labels(page, box, s, x0_m, y_top_m, w_px, h_px):
    """Paint fill paths fully inside the box in drawing order at RES/FINE m, reduce to RES by majority."""
    x0, y0, x1, y1 = box
    palette, fills = {}, []
    for d in page.get_drawings():
        r = d['rect']
        if d.get('fill') is None or not (d.get('fill_opacity') or 0) > 0:
            continue
        if not (r.x0 >= x0 and r.x1 <= x1 and r.y0 >= y0 and r.y1 <= y1):
            continue
        key = tuple(round(round(c / 0.02) * 0.02, 2) for c in d['fill'])
        fills.append((d['seqno'], palette.setdefault(key, len(palette) + 1), d))
    img = Image.new('I', (w_px * FINE, h_px * FINE), 0)
    draw = ImageDraw.Draw(img)
    step = RES / FINE
    for _, lab, d in sorted(fills, key=lambda t: t[0]):
        for p in polygons(d):
            draw.polygon([((x / s - x0_m) / step, (y / s - y_top_m) / step) for x, y in p], fill=lab)
    fine = np.array(img, np.int32)
    return S.majority(fine, FINE), {str(k): v for k, v in palette.items()}


def measure(out, run, fx, r145, permute=False):
    npz = out / f'types-{run}.npz'
    cmd = [str(BLENDER), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
           '-P', str(HERE / 'rays_type.py'), '--', str(out / 'elv.fbx'), str(npz), str(RES),
           ','.join(map(str, fx['faces_az']))]
    with (out / f'rays-{run}.log').open('xb') as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1200)
    models = {}
    with np.load(npz) as rays:
        for az in fx['faces_az']:
            lab = rays[f'az{az:03d}_type']
            cols = np.flatnonzero((lab > 0).any(axis=0))
            lab = lab[:, cols[0]:cols[-1] + 1]
            _, inv = np.unique(lab, return_inverse=True)  # R1b: compact labels (0 stays 0: smallest value)
            models[az] = inv.reshape(lab.shape).astype(np.int32)
    slack = round(fx['decision']['width_slack_m'] / RES)
    doc = pymupdf.open(out / 'elv.pdf')
    rows, inv_changed = [], 0
    for title, v in fx['views'].items():
        page = doc[v['page'] - 1]
        s = r145['scale_pt_per_m'](page, v)
        seg = r145['segments'](page, v['box_pt'], s)
        img = r145['raster_view'](seg, fx['res_m'])
        occupied_rows = np.where(img.any(0), img.argmax(0), img.shape[0])
        span = np.flatnonzero((img.shape[0] - occupied_rows) * fx['res_m'] >= fx['decision']['tall_m'])
        x0 = int(span[0]) if len(span) else 0
        x1 = int(span[-1]) + 1 if len(span) else img.shape[1]
        width = x1 - x0
        seg_x0, seg_ytop = seg[:, [0, 2]].min(), -seg[:, [1, 3]].max()
        h_px = int(np.ceil((seg[:, [1, 3]].max() - seg[:, [1, 3]].min()) / RES)) + 1
        w_px = int(np.ceil((seg[:, [0, 2]].max() - seg_x0) / RES)) + 1
        labels, palette = view_labels(page, v['box_pt'], s, seg_x0, seg_ytop, w_px, h_px)
        for kind, offset, length in r145['cases'](v['kind'], width, fx['partials']):
            i0 = int(round((x0 + offset) * fx['res_m'] / RES))
            n = max(1, int(round(length * fx['res_m'] / RES)))
            line_rows = np.flatnonzero(img[:, x0 + offset:x0 + offset + length].any(axis=1))
            top_px = int(round(line_rows[0] * fx['res_m'] / RES)) if len(line_rows) else 0
            view = labels[top_px:, i0:i0 + n]  # row 0 = local top line of this crop (as #140 top alignment)
            changed = None
            if kind == 'mirror':
                changed = int(np.count_nonzero(view != view[:, ::-1]))
                view = view[:, ::-1]
            scores = {az: round(float(S.face_score(view, models[az], slack)), 9) for az in fx['faces_az']}
            if permute:  # invariance witness: relabel view colours by reversed palette order
                k = int(view.max())
                perm = np.concatenate([[0], np.arange(k, 0, -1)]).astype(np.int32)
                pscores = {az: round(float(S.face_score(perm[view], models[az], slack)), 9) for az in fx['faces_az']}
                inv_changed += int(pscores != scores)
            pick = S.decide(scores)
            outcome = 'abstain' if pick is None else 'correct' if pick == v['gt_az'] else 'wrong'
            rows.append(dict(view=title, gt_az=v['gt_az'], case=kind, width_m=round(length * fx['res_m'], 1),
                             palette=len(palette), filled_px=int(np.count_nonzero(view)), pick=pick,
                             outcome=outcome, scores={str(a): sc for a, sc in scores.items()},
                             changed_pixels=changed))
    return rows, (inv_changed if permute else None)


def group(row):
    if row['case'] == 'mirror':
        return 'mirror'
    if row['case'].startswith('partial'):
        return 'synthetic_crop'
    return row['case']


def summarize(rows, key='outcome'):
    out = {}
    for name in ('full', 'synthetic_crop', 'fragment', 'fragment_top_cut', 'mirror'):
        c = Counter()
        for r in rows:
            if group(r) != name:
                continue
            c['not_exercised' if name == 'mirror' and not r['changed_pixels'] else r[key]] += 1
        answered = c['correct'] + c['wrong']
        out[name] = dict(correct=c['correct'], wrong=c['wrong'], abstain=c['abstain'],
                         not_exercised=c['not_exercised'],
                         accuracy=round(c['correct'] / answered, 4) if answered else None)
    return out


def combine(rows, r147):
    """E: #147 verdict C where C answers, D where C abstains. Requires row identity parity."""
    elv = [r for r in r147['rows'] if r.get('fixture') is None and 'case' in r]
    ident = [(r['view'], r['case'], r['width_m']) for r in elv]
    mine = [(r['view'], r['case'], r['width_m']) for r in rows]
    if ident != mine:
        raise ValueError('row identity parity with #147 failed')
    for r, c in zip(rows, elv):
        r['C'] = c['verdict_C']
        r['E'] = c['verdict_C'] if c['verdict_C'] != 'abstain' else r['outcome']
    return True


def verdict(sd, se, rows):
    w = {r['view'] + ' ' + r['case']: r for r in rows}
    checks = dict(
        full_wrong_0=sd['full']['wrong'] == 0,
        fragment_wrong_0=sd['fragment']['wrong'] + sd['fragment_top_cut']['wrong'] == 0,
        crop_wrong_le1=sd['synthetic_crop']['wrong'] <= 1,
        crop_correct_ge15=sd['synthetic_crop']['correct'] >= 15,
        witness_p18_IA_full=w['p18 I-A full']['outcome'] == 'correct',
        witness_p19_AI_p25_1=w['p19 A-I partial25@1.0']['outcome'] != 'wrong',
    )
    clean_e = sum(se[k]['wrong'] for k in ('full', 'fragment', 'fragment_top_cut', 'synthetic_crop'))
    e_checks = dict(clean_wrong_le1=clean_e <= 1, crop_correct_ge20=se['synthetic_crop']['correct'] >= 20)
    return checks, e_checks


def main():
    out = Path(sys.argv[1]).resolve()
    runs_n = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 3
    if out.exists():
        raise SystemExit(f'output exists: {out}')
    t0 = monotonic()
    fx, pins = stage(out)
    r145 = runpy.run_path(str(out / 'r145.py'), run_name='r145')
    r147 = json.loads((out / 'r147_receipt.json').read_text(encoding='utf-8'))
    runs, walls, status, inv = [], [], 'finished', None
    for run in range(1, runs_n + 1):
        if run > 1 and (monotonic() - t0) + 1.15 * walls[0] * (runs_n - run + 1) > 3600:
            status = 'inconclusive_budget_stop'
            break
        t = monotonic()
        rows, changed = measure(out, run, fx, r145, permute=(run == 1))
        if run == 1:
            inv = changed
        walls.append(round(monotonic() - t, 3))
        runs.append(rows)
        (out / f'run-{run}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding='utf-8')
        print(f'run {run}: {walls[-1]} s', flush=True)
    keyed = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in runs]
    identical = all(k == keyed[0] for k in keyed)
    rows = runs[0]
    combine(rows, r147)
    sd, se, sc = summarize(rows), summarize(rows, 'E'), summarize(rows, 'C')
    checks, e_checks = verdict(sd, se, rows)
    hyp = 'confirmed' if all(checks.values()) else 'refuted'
    if status != 'finished' or not identical:
        status = status if status != 'finished' else 'parity_failed'
    walls_sorted = sorted(walls)
    receipt = dict(card='t_141c9690 (#149)', status=status, hypothesis=hyp, checks=checks, e_checks=e_checks,
                   invariance_rows_changed=inv, invariance_rows=len(rows), pins=pins, blender_sha256=EXE_HASH,
                   uv_lock_sha256=sha('uv.lock'), runs=len(runs), run_wall_s=walls,
                   median_s=walls_sorted[len(walls) // 2], min_s=walls_sorted[0], max_s=walls_sorted[-1],
                   total_wall_s=round(monotonic() - t0, 3), runs_identical=identical,
                   run_content_sha256=[hashlib.sha256(k.encode()).hexdigest() for k in keyed],
                   summary_D=sd, summary_E=se, summary_C=sc, rows=rows)
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(status=status, hypothesis=hyp, checks=checks, e_checks=e_checks, D=sd, E=se,
                          identical=identical, walls=walls, inv=inv), ensure_ascii=False))


if __name__ == '__main__':
    main()
