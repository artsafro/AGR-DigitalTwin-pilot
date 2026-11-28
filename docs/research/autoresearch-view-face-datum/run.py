"""H162 OBSERVE: level-registered drawing vs the unchanged #161 model masks."""

import hashlib
import json
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

REV = 'f4a7f22b107826d5e054f11a5e336c63aed81667'
UPSTREAM = 'docs/research/autoresearch-view-face-glass/'
PINS = {
    'run.py': '978ad7d4ccffa01e90d726b56533ab3a914578ebd84f449265c16dd67bb9c5bf',
    'fixture.json': '9ce8c9eba842de0d299ccc098a80ccee625fe7d68991f68f0ee64cec3630157e',
    'receipt.json': '74a596fde4dddce0fb01604eb319f1ddd9bab688fe5e15371f7eb7cee40b9741',
    'blender': 'fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5',
}
ANCHORS = {
    "p15 A'-K (7 boxes)": ((396.10, 0), (304.66, 12.9)),
    "p14 4'-1 (truss glazed block)": ((412.36, 0), (320.98, 12.9)),
    "p14 1-4' (courtyard, developed)": ((212.32, 0), (120.82, 12.9)),
    'p16 fragment 1 (box bay)': ((337.36, 0), (81.40, 12.9)),
    'p17 fragment 2 (curved stair)': ((328.42, 0), (167.68, 8.1)),
    'p15 K-A': ((194.62, 0), (116.98, 11)),
    'p15 A-G': ((190.66, 0.75), (103.48, 12.9)),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def register(glass, page_y_px, zoom, anchors, height, grid):
    if anchors is None:
        return None
    (y_low, z_low), (y_high, z_high) = anchors
    if y_low <= y_high or z_high <= z_low:
        raise ValueError('reversed anchors')
    px_m = zoom * (y_low - y_high) / (z_high - z_low)
    zero = y_low * zoom + z_low * px_m - page_y_px
    rows = int(round(height / grid))
    cols = max(1, int(round(glass.shape[1] / px_m / grid)))
    # A fixed model Z band, including any missing drawing rows as background.
    box = (0, zero - height * px_m, glass.shape[1], zero)
    src = Image.fromarray((glass * 255).astype(np.uint8))
    # Pad before resize to preserve bilinear antialiasing on the native mask grid.
    pad_top = max(0, int(np.ceil(-box[1])))
    pad_bot = max(0, int(np.ceil(box[3] - glass.shape[0])))
    if pad_top or pad_bot:
        src = Image.fromarray(np.pad(np.asarray(src), ((pad_top, pad_bot), (0, 0))))
    box = (0, box[1] + pad_top, box[2], box[3] + pad_top)
    return np.asarray(src.resize((cols, rows), Image.Resampling.BILINEAR, box=box)) / 255.0


def native_drawing(page, clip, p, legend, api):
    zoom = p['zoom']
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(*clip), alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(int)
    building = rgb.sum(-1) < p['page_white_sum']
    x0, y0, x1, y1 = api.largest_bbox(api.opening(building, p['open_px']))
    c = rgb[y0:y1, x0:x1]
    dist = np.min([np.sqrt(((c - np.array(s)) ** 2).sum(-1)) for s in legend], axis=0)
    lum = c.mean(-1)
    red = (c[..., 0] > 150) & (c[..., 1] < 90) & (c[..., 2] < 90)
    mask = building[y0:y1, x0:x1] & ~red & (dist > p['legend_dist'])
    mask &= (lum >= p['glass_lum'][0]) & (lum <= p['glass_lum'][1])
    return mask, pix.y + y0, [x0, y0, x1, y1], round(float(mask[building[y0:y1, x0:x1]].mean()), 4)


def candidate(api, fx, masks, baseline):
    p = fx['params']
    rows = []
    with pymupdf.open(fx['pdf']) as pdf:
        for view, control in zip(fx['views'], baseline, strict=True):
            name = view['id']
            raw, page_y, bbox, glass_frac = native_drawing(pdf[view['page'] - 1], view['clip_pt'], p, fx['legend_rgb'], api)
            if bbox != control['box_px'] or glass_frac != control['glass_frac']:
                raise RuntimeError(f'drawing crop parity or glass-content failure: {name}')
            anchors = ANCHORS[name]
            args = (raw, page_y, p['zoom'])
            grid = (p['view_height_m'], p['grid_m'])
            clean = register(*args, anchors, *grid)
            assert clean is not None
            states = {}
            for label, g in (
                ('clean', clean), ('mirror', np.ascontiguousarray(clean[:, ::-1])),
                ('blank', np.zeros_like(clean)), ('missing', register(*args, None, *grid)),
                ('shift', register(*args, tuple((y, z + .75) for y, z in anchors), *grid)),
            ):
                if g is None:
                    states[label] = {'answer': None, 'changed_anchors': len(anchors), 'changed_cells': None}
                    continue
                scores = {az: api.best_offset(g, masks[az], p) for az in p['azimuths']}
                verdict = api.decide(scores, p)
                if api.decide(dict(reversed(list(scores.items()))), p) != verdict:
                    raise RuntimeError(f'candidate-order parity failed: {name} {label}')
                answer, value, margin, top = verdict
                n = int(np.count_nonzero(g != clean))
                states[label] = dict(answer=answer, value=value, margin=margin, top=top,
                                     changed_cells=n, exercised=(label == 'clean' or n > 0),
                                     scores={az: round(s[0], 4) for az, s in scores.items()})
            gt = view['gt_az']
            rows.append(dict(view=name, gt=gt, inner=view['inner'], kind=view['kind'], anchors=anchors,
                             outcome=api.outcome(states['clean']['answer'], gt), baseline=control['outcome'],
                             baseline_answer=control['answer'], baseline_width_m=control['width_m'],
                             width_m=round(raw.shape[1] / p['zoom'] * (anchors[1][1] - anchors[0][1]) /
                                           (anchors[0][0] - anchors[1][0]), 2), states=states))
    return rows


def main():
    out = Path(sys.argv[1]).resolve()
    blobs = {name: subprocess.check_output(['git', 'show', f'{REV}:{UPSTREAM}{name}'])
             for name in ('run.py', 'fixture.json', 'receipt.json')}
    for name, data in blobs.items():
        if digest(data) != PINS[name]:
            raise RuntimeError(f'upstream Git blob mismatch: {name} {digest(data)}')
    api = types.ModuleType('ar161_exact')
    api.__file__ = str(out / 'upstream' / 'run.py')
    exec(compile(blobs['run.py'], api.__file__, 'exec'), api.__dict__)
    fx = json.loads(blobs['fixture.json'])
    historical = json.loads(blobs['receipt.json'])

    def preflight():
        for key, path, pin in [('blender', api.BLENDER, PINS['blender']),
                               *((k, fx[k], h) for k, h in fx['sha256'].items())]:
            if api.sha(path) != pin:
                raise RuntimeError(f'input hash mismatch: {key}')

    preflight()
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    pairs = []
    rows = []
    for index in range(1, 4):
        t = time.perf_counter()
        native = []

        def timed_render(*args, **kwargs):
            before = time.perf_counter()
            result = subprocess.run(*args, **kwargs, timeout=100)
            native.append(time.perf_counter() - before)
            return result

        api.__dict__['subprocess'] = types.SimpleNamespace(run=timed_render)
        sub = out / f'pair{index}'
        base, _, wall = api.one_run(fx, sub)
        if len(native) != 1 or base != historical['rows']:
            raise RuntimeError('exact #161 baseline row parity failed')
        masks, _ = api.model_masks(sub, fx['params'])
        before = time.perf_counter()
        rows = candidate(api, fx, masks, base)
        b_time = time.perf_counter() - before
        # Historical receipt hashes JSON ordered by string azimuth keys; canonicalize both arms here.
        body = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()
        (sub / 'rows.json').write_bytes(body)
        pair = dict(index=index, wall_s=round(time.perf_counter() - t, 3), rows_sha256=digest(body),
                    b_minus_a_post_render_s=round(b_time - (wall - native[0]), 3))
        pairs.append(pair)
        print(json.dumps(pair), flush=True)
        preflight()
        elapsed = time.perf_counter() - started
        if elapsed + (3 - index) * (elapsed / index) > 180:
            raise RuntimeError('inconclusive: cannot finish three pairs within 180 seconds')
    if len({p['rows_sha256'] for p in pairs}) != 1:
        raise RuntimeError('new row parity failed')
    scored = [r for r in rows if r['gt']]
    tally = {k: sum(r['outcome'] == k for r in scored) for k in ('correct', 'wrong', 'abstain')}
    controls = all(r['states']['blank']['exercised'] and r['states']['blank']['answer'] is None
                   and r['states']['missing']['answer'] is None for r in rows)
    hypothesis = ('confirmed' if controls and rows[0]['states']['clean']['answer'] == 330
                  and not tally['wrong'] and tally['correct'] >= 3
                  and any(r['inner'] and r['outcome'] == 'correct' for r in scored) else 'refuted')
    times = [p['wall_s'] for p in pairs]
    receipt = dict(status='finished', hypothesis=hypothesis, tally=tally, pairs=pairs, rows=rows,
                   median_s=statistics.median(times), spread_s=round(max(times) - min(times), 3),
                   controls_pass=controls, inputs=fx['sha256'], upstream_pins=PINS, upstream_rev=REV,
                   baseline_rows_sha256=historical['rows_sha256'], runner_sha256=api.sha(__file__))
    (out / 'receipt.json').write_bytes((json.dumps(receipt, indent=2, ensure_ascii=False) + '\n').encode())
    print(hypothesis, tally)


if __name__ == '__main__':
    main()
