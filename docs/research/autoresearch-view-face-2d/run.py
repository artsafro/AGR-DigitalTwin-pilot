"""Replay one frozen A/B series using the #139 native front end."""

import argparse
from collections import Counter
from hashlib import file_digest, sha256
import json
from pathlib import Path
import runpy
import shutil
from statistics import median
import subprocess
import sys
from time import monotonic
import zipfile

import numpy as np

from score import decide, face_score, mesh_edges

REV = '38f7d95ee54a677ac744c0148fb1fce33b06d9d3'
UPSTREAM = 'docs/research/autoresearch-view-face-harness'
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 4.4/blender.exe')
EXE_HASH = 'fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5'
DRIVE = Path('G:/Мой диск')
KPP_DXF = DRIVE / 'AGR-evidence/139-view-face/inputs/kpp1_L01.dxf'
KPP_ZIP = DRIVE / 'AGR-assets/KPP1/delivered-customer-2026-11-14/SM_77_05_0009005_117_002.zip'


def digest(path):
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def check(path, expected):
    if digest(path) != expected:
        raise ValueError(f'Input SHA-256 mismatch: {path}')


def prepare(out):
    check(BLENDER, EXE_HASH)
    out.mkdir(parents=True, exist_ok=False)
    for name in ('rays.py', 'view_face.py', 'fixture.json', 'receipt_r139.json'):
        (out / name).write_bytes(subprocess.check_output(['git', 'show', f'{REV}:{UPSTREAM}/{name}']))
    config = json.loads((out / 'fixture.json').read_bytes())
    inputs = {}
    for job, f in config['fixtures'].items():
        for role, suffix in [('dxf', '.dxf'), ('model', '.fbx')]:
            expected = f[f'{role}_sha256']
            src = KPP_DXF if (job, role) == ('kpp1', 'dxf') else Path(f[role])
            local = out / (job + suffix)
            member = None
            member_archive_hash = None
            if (job, role) == ('kpp1', 'model'):
                src = KPP_ZIP
                member = Path(f[role]).name
                member_archive_hash = digest(src)
                with zipfile.ZipFile(src) as archive, archive.open(member) as stream, local.open('xb') as target:
                    shutil.copyfileobj(stream, target)
            else:
                check(src, expected)
                shutil.copyfile(src, local)
            check(local, expected)
            inputs[job + suffix] = dict(source=str(src), member=member, sha256=expected,
                                        source_sha256=member_archive_hash or expected)
    # Historical receipt is a parity oracle only; the scoring function never receives it.
    return inputs


def drawing_views(api, doc, f):
    seg = api['segments'](doc, f['layout'], f['exclude_layers'], f['unit_m'])
    if f['views'] == 'auto_gap_x':
        for vs in api['views_auto_gap_x'](seg, f['gap_mm'] * f['unit_m']):
            lo, hi = vs[:, [0, 2]].min(), vs[:, [0, 2]].max()
            labels = [(t, g[2]) for t, g in f['gt_by_axis_x_mm'].items()
                      if lo <= (g[0] + g[1]) / 2 * f['unit_m'] <= hi]
            if len(labels) != 1:
                raise ValueError('Unmatched KPP1 raster to independent GT')
            yield *labels[0], vs
    else:
        m = f['box_margin_mm']
        for title, (x, y, w, h) in f['boxes_mm'].items():
            x0, y0, x1, y1 = np.array([x - m, y - m, x + w + m, y + h + m]) * f['unit_m']
            xs, ys = seg[:, [0, 2]], seg[:, [1, 3]]
            inside = ((xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)).all(1)
            yield title, f['gt_az'][title], seg[inside]


def cases(width, f):
    yield 'full', 0, width
    yield 'mirror', 0, width
    for fraction in f['fractions']:
        length = max(5, round(fraction * width))
        for position in f['positions']:
            yield f'partial{int(fraction * 100)}@{position}', round(position * (width - length)), length


def measure(out, pair):
    api = runpy.run_path(str(out / 'view_face.py'))
    config = json.loads((out / 'fixture.json').read_bytes())
    res = config['res_m']
    decision = config['decision']
    slack = round(decision['width_slack_m'] / res)
    rows = []
    for job, f in config['fixtures'].items():
        path = out / f'{job}-{pair}.npz'
        axes = f['faces_az']
        command = [str(BLENDER), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
                   '-P', str(out / 'rays.py'), '--', str(out / f'{job}.fbx'), str(path), str(res),
                   ','.join(map(str, axes))]
        with (out / f'{job}-{pair}.log').open('xb') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        with np.load(path) as rays:
            features = {az: api['model_signals'](rays, az, res) for az in axes}
            meshes = {}
            for az in axes:
                key = f'az{az:03d}'
                depth = rays[key + '_depth']
                occupied = np.isfinite(depth)
                cols = np.flatnonzero(occupied.any(axis=0))
                span = slice(cols[0], cols[-1] + 1)
                meshes[az] = mesh_edges(depth, rays[key + '_normal'])[:, span], occupied[:, span]
        doc = api['load_dxf'](out / f'{job}.dxf')
        for title, truth, vectors in drawing_views(api, doc, f):
            img, vimg, _ = api['raster_view'](vectors, res)
            roof, rhythm = api['signals_from_masks'](img, vimg, res)
            occupied_rows = np.where(img.any(0), img.argmax(0), img.shape[0])
            span = np.flatnonzero((img.shape[0] - occupied_rows) * res >= 2.0)
            x0 = int(span[0]) if len(span) else 0
            for kind, offset, width in cases(len(roof), config['partials']):
                a = roof[offset:offset + width]
                b = rhythm[offset:offset + width]
                view = img[:, x0 + offset:x0 + offset + width]
                changed = None
                if kind == 'mirror':
                    changed = int(np.count_nonzero(view != view[:, ::-1]))
                    a, b, view = a[::-1], b[::-1], view[:, ::-1]
                baseline = {az: api['slide'](a, b, *features[az], slack)['V1'] for az in axes}
                trial = {az: face_score(view, *meshes[az], slack) for az in axes}
                previous = api['decide'](baseline, truth, decision['tau_margin'], decision['min_score'])
                pick = decide(trial)
                rows.append(dict(fixture=job, title=title, gt_az=truth, case=kind, A=previous,
                                 B=pick, scores_B={str(k): round(float(v), 6) for k, v in trial.items()},
                                 changed_pixels=changed))
    (out / f'pair-{pair}.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')


def parity(out, rows):
    historical = json.loads((out / 'receipt_r139.json').read_bytes())['views']
    keys = ('fixture', 'title', 'gt_az', 'case')
    expected = {tuple(row[k] for k in keys): (row['V1']['answer'], row['V1']['outcome']) for row in historical}
    actual = {tuple(row[k] for k in keys): (row['A']['answer'], row['A']['outcome']) for row in rows}
    if len(rows) != 88 or len(expected) != len(rows) or actual != expected:
        raise ValueError(f'Historical baseline parity failed: {len(actual)}/{len(expected)} distinct cases; '
                         f'{list(actual.items() ^ expected.items())[:5]}')


def summarize(rows):
    groups = {}
    for arm in ('A', 'B'):
        for job in ('kpp1', 'ac08'):
            for scope in ('full', 'partial', 'mirror'):
                count = Counter()
                for row in rows:
                    if row['fixture'] != job or not row['case'].startswith(scope):
                        continue
                    if scope == 'mirror' and not row['changed_pixels']:
                        count['not_exercised'] += 1
                        continue
                    pick = row[arm]['answer'] if arm == 'A' else row[arm]
                    count['abstain' if pick is None else 'correct' if pick == row['gt_az'] else 'wrong'] += 1
                count = {k: count[k] for k in ('correct', 'wrong', 'abstain', 'not_exercised')}
                answered = count['correct'] + count['wrong']
                total = answered + count['abstain']
                groups[f'{arm}.{job}.{scope}'] = dict(**count, accuracy=count['correct'] / answered if answered else None,
                                                      abstain_rate=count['abstain'] / total if total else None)
    return groups


def series(out):
    start = monotonic()
    inputs = prepare(out)
    timings, pair_hashes, summaries = [], [], []
    status = 'finished'
    for i in (1, 2, 3):
        pair_start = monotonic()
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(out), '--pair', str(i)],
                       check=True, timeout=300)
        file = out / f'pair-{i}.json'
        rows = json.loads(file.read_bytes())
        parity(out, rows)
        pair_hashes.append(digest(file))
        summaries.append(summarize(rows))
        elapsed = monotonic() - pair_start
        timings.append(round(elapsed, 3))
        print(f'PAIR {i}: 88/88 V1 parity; {elapsed:.2f} s', flush=True)
        if i == 1 and monotonic() - start + 4 * elapsed > 900:
            status = 'budget_stop'
            break
    for name, row in inputs.items():
        check(out / name, row['sha256'])
        check(Path(row['source']), row['source_sha256'])
    check(BLENDER, EXE_HASH)
    if len(set(pair_hashes)) != 1:
        status = 'nonidentical_repeats'
    result = 'inconclusive'
    if status == 'finished':
        gain = median(s['B.kpp1.partial']['correct'] - s['A.kpp1.partial']['correct'] for s in summaries)
        wins = all(r['B'] == r['gt_az'] for r in rows if r['fixture'] == 'kpp1' and r['case'] == 'full'
                   and r['title'] in ('1-4', '4-1'))
        safe = all(not s[k]['wrong'] for s in summaries for k in s if k.startswith('B.') and not k.endswith('.mirror'))
        ac08_abstains = all(s['B.ac08.full']['abstain'] == 4 and s['B.ac08.partial']['abstain'] == 36 for s in summaries)
        result = 'confirmed' if gain >= 4 and wins and safe and ac08_abstains else 'refuted'
    receipt = dict(status=status, hypothesis=result, upstream=REV, inputs=inputs, blender_sha256=EXE_HASH,
                   uv_lock_sha256=digest(Path('uv.lock')), candidate_sha256={
                       name: digest(Path(__file__).with_name(name)) for name in ('run.py', 'score.py')},
                   timings_s=timings, median_s=median(timings), total_s=round(monotonic() - start, 3),
                   pair_sha256=pair_hashes, summary=summaries[0], views=rows)
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + '\n',
                                      encoding='utf-8', newline='\n')
    print(result, status, out / 'receipt.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--pair', type=int, choices=(1, 2, 3))
    args = parser.parse_args()
    if args.pair is None:
        series(args.out.resolve())
    else:
        measure(args.out.resolve(), args.pair)


if __name__ == '__main__':
    main()
