"""#145 OBSERVE: transfer test of #140 B (2D lines vs ortho mesh edges) on ELV TC Sreda (vector PDF + Revit FBX).

Research only; no product code, no delivery edits. Replay from the repository root (pilot host, inputs mounted):
    uv run --offline --extra pdf-review python docs/research/autoresearch-view-face-elv/run.py <new_out_dir> [--pairs 3]
Needs `git fetch origin research/autoresearch-standing-139 research/autoresearch-standing-140` (pinned upstream bytes).
"""
import hashlib
import json
import math
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
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 4.4/blender.exe')
EXE_HASH = 'fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5'
SKIP_OLD = 'if ob.type != "MESH" or ob.name.upper().startswith(("UCX_", "UBX_", "USP_", "UCP_", "COLIZ")):'
SKIP_NEW = ('if ob.type != "MESH" or ob.name.upper().startswith(("UCX_", "UBX_", "USP_", "UCP_", "COLIZ")) '
            'or (len(ob.data.vertices) > 0 and max((ob.matrix_world @ v.co).z for v in ob.data.vertices) > 30.0):')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def upstream(rev, path):
    return subprocess.run(['git', 'show', f'{rev}:{path}'], check=True, capture_output=True).stdout


def stage(out, fx):
    out.mkdir(parents=True)
    pins = {}
    for role, row in fx['inputs'].items():
        if sha(row['path']) != row['sha256']:
            raise ValueError(f'input SHA-256 mismatch: {role}')
        shutil.copyfile(row['path'], out / f'elv.{role}')
        if sha(out / f'elv.{role}') != row['sha256']:
            raise ValueError(f'staged copy mismatch: {role}')
        pins[role] = row['sha256']
    if sha(BLENDER) != EXE_HASH:
        raise ValueError('Blender 4.4 hash mismatch')
    for name, row in fx['upstream'].items():
        data = upstream(row['rev'], row['path'])
        (out / name).write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    text = (out / 'rays.py').read_text(encoding='utf-8')
    if text.count(SKIP_OLD) != 1:
        raise ValueError('upstream rays.py skip line not found exactly once')
    (out / 'rays_elv.py').write_text(text.replace(SKIP_OLD, SKIP_NEW), encoding='utf-8')
    pins['rays_elv.py'] = sha(out / 'rays_elv.py')
    return pins


def word_center(page, label, band, xmin=-1e9, xmax=1e9):
    hits = [((w[0] + w[2]) / 2, (w[1] + w[3]) / 2) for w in page.get_text('words')
            if w[4] == label and band[0] <= (w[1] + w[3]) / 2 <= band[1] and xmin <= (w[0] + w[2]) / 2 <= xmax]
    if len(hits) != 1:
        raise ValueError(f'scale label {label!r} found {len(hits)} times')
    return hits[0]


def scale_pt_per_m(page, v):
    if 'scale' in v:
        a, b, metres, band = v['scale']
        xa = word_center(page, a, band, v.get('x_min_label_pt', -1e9), v.get('x_max_label_pt', 1e9))[0]
        xb = word_center(page, b, band, v.get('x_min_label_pt', -1e9), v.get('x_max_label_pt', 1e9))[0]
        return abs(xb - xa) / metres
    a, b, metres = v['scale_levels']
    ya = word_center(page, a, (0, 1e9))[1]
    yb = word_center(page, b, (0, 1e9))[1]
    return abs(yb - ya) / metres


def segments(page, box, s):
    x0, y0, x1, y1 = box
    out = []
    for d in page.get_drawings():
        for item in d['items']:
            if item[0] == 'l':
                pts = [item[1], item[2]]
            elif item[0] == 're':
                r = item[1]
                pts = [r.tl, r.tr, r.br, r.bl, r.tl]
            elif item[0] == 'qu':
                q = item[1]
                pts = [q.ul, q.ur, q.lr, q.ll, q.ul]
            elif item[0] == 'c':
                pts = [item[1], item[4]]
            else:
                continue
            for p, q in zip(pts, pts[1:]):
                if not all(x0 <= t.x <= x1 and y0 <= t.y <= y1 for t in (p, q)):
                    continue
                dx, dy = q.x - p.x, q.y - p.y
                length = math.hypot(dx, dy) / s
                ang = math.degrees(math.atan2(abs(dy), abs(dx)))
                if length > 0.05 and (ang <= 2 or ang >= 88):
                    out.append((p.x / s, -p.y / s, q.x / s, -q.y / s))
    return np.array(out, float)


def raster_view(seg, res):
    """Verbatim logic of #139 view_face.raster_view (occupancy mask only)."""
    x0, y0 = seg[:, [0, 2]].min(), seg[:, [1, 3]].min()
    x1, y1 = seg[:, [0, 2]].max(), seg[:, [1, 3]].max()
    W, H = int(math.ceil((x1 - x0) / res)) + 1, int(math.ceil((y1 - y0) / res)) + 1
    img = np.zeros((H, W), bool)
    for xa, ya, xb, yb in seg:
        n = max(2, int(math.hypot(xb - xa, yb - ya) / (res / 2)) + 1)
        xs = ((np.linspace(xa, xb, n) - x0) / res).astype(int).clip(0, W - 1)
        ys = (H - 1 - ((np.linspace(ya, yb, n) - y0) / res).astype(int)).clip(0, H - 1)
        img[ys, xs] = True
    return img


def cases(kind, width, partials):
    if kind == 'full':
        yield 'full', 0, width
        yield 'mirror', 0, width
        for fraction in partials['fractions']:
            length = max(5, round(fraction * width))
            for position in partials['positions']:
                yield f'partial{int(fraction * 100)}@{position}', round(position * (width - length)), length
    else:
        yield kind, 0, width


def measure(out, pair, fx):
    score = runpy.run_path(str(out / 'score.py'))
    res, dec = fx['res_m'], fx['decision']
    slack = round(dec['width_slack_m'] / res)
    npz = out / f'rays-{pair}.npz'
    cmd = [str(BLENDER), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
           '-P', str(out / 'rays_elv.py'), '--', str(out / 'elv.fbx'), str(npz), str(res),
           ','.join(map(str, fx['faces_az']))]
    with (out / f'rays-{pair}.log').open('xb') as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
    meshes = {}
    with np.load(npz) as rays:
        for az in fx['faces_az']:
            key = f'az{az:03d}'
            depth = rays[key + '_depth']
            occ = np.isfinite(depth)
            cols = np.flatnonzero(occ.any(axis=0))
            span = slice(cols[0], cols[-1] + 1)
            meshes[az] = score['mesh_edges'](depth, rays[key + '_normal'])[:, span], occ[:, span]
    doc = pymupdf.open(out / 'elv.pdf')
    rows, views = [], {}
    for title, v in fx['views'].items():
        page = doc[v['page'] - 1]
        s = scale_pt_per_m(page, v)
        seg = segments(page, v['box_pt'], s)
        img = raster_view(seg, res)
        occupied_rows = np.where(img.any(0), img.argmax(0), img.shape[0])
        span = np.flatnonzero((img.shape[0] - occupied_rows) * res >= dec['tall_m'])
        x0 = int(span[0]) if len(span) else 0
        x1 = int(span[-1]) + 1 if len(span) else img.shape[1]
        views[title] = img[:, x0:x1]
        width = x1 - x0
        for kind, offset, length in cases(v['kind'], width, fx['partials']):
            view = img[:, x0 + offset:x0 + offset + length]
            changed = None
            if kind == 'mirror':
                changed = int(np.count_nonzero(view != view[:, ::-1]))
                view = view[:, ::-1]
            scores = {az: float(score['face_score'](view, *meshes[az], slack)) for az in fx['faces_az']}
            pick = score['decide'](scores)
            outcome = 'abstain' if pick is None else 'correct' if pick == v['gt_az'] else 'wrong'
            rows.append(dict(view=title, page=v['page'], gt_az=v['gt_az'], case=kind, pt_per_m=round(s, 4),
                             width_m=round(length * res, 1), segments=len(seg), pick=pick, outcome=outcome,
                             scores={str(k): round(val, 6) for k, val in scores.items()}, changed_pixels=changed))
    if pair == 1:
        np.savez_compressed(out / 'views-1.npz', **{k.replace(' ', '_'): v for k, v in views.items()},
                            **{f'model_az{az:03d}': m[0] for az, m in meshes.items()})
    (out / f'pair-{pair}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding='utf-8')
    return rows


def group(row):
    if row['case'] == 'mirror':
        return 'mirror'
    if row['case'].startswith('partial'):
        return 'synthetic_crop'
    return row['case']


def summarize(rows):
    out = {}
    for name in ('full', 'synthetic_crop', 'fragment', 'fragment_top_cut', 'mirror'):
        c = Counter()
        for r in rows:
            if group(r) != name:
                continue
            if name == 'mirror' and not r['changed_pixels']:
                c['not_exercised'] += 1
            else:
                c[r['outcome']] += 1
        answered = c['correct'] + c['wrong']
        out[name] = dict(correct=c['correct'], wrong=c['wrong'], abstain=c['abstain'], not_exercised=c['not_exercised'],
                         accuracy=round(c['correct'] / answered, 4) if answered else None)
    return out


def main():
    out = Path(sys.argv[1]).resolve()
    pairs = int(sys.argv[sys.argv.index('--pairs') + 1]) if '--pairs' in sys.argv else 3
    fx = json.loads((HERE / 'fixture.json').read_text(encoding='utf-8'))
    if out.exists():
        raise SystemExit(f'output exists: {out}')
    t0 = monotonic()
    pins = stage(out, fx)
    runs, walls = [], []
    for pair in range(1, pairs + 1):
        t = monotonic()
        runs.append(measure(out, pair, fx))
        walls.append(round(monotonic() - t, 3))
        print(f'pair {pair}: {walls[-1]} s', flush=True)
    keyed = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in runs]
    identical = all(k == keyed[0] for k in keyed)
    for role in ('pdf', 'fbx'):
        if sha(fx['inputs'][role]['path']) != fx['inputs'][role]['sha256']:
            raise ValueError(f'input changed during run: {role}')
    receipt = dict(card='t_6c816f20 (#145)', fixture_sha256=sha(HERE / 'fixture.json'), run_py_sha256=sha(__file__),
                   pins=pins, blender_sha256=EXE_HASH, uv_lock_sha256=sha('uv.lock'), pairs=pairs,
                   pair_wall_s=walls, total_wall_s=round(monotonic() - t0, 3), pairs_identical=identical,
                   pair_content_sha256=[hashlib.sha256(k.encode()).hexdigest() for k in keyed],
                   summary=summarize(runs[0]), rows=runs[0])
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(summary=receipt['summary'], identical=identical, walls=walls), ensure_ascii=False))


if __name__ == '__main__':
    main()
