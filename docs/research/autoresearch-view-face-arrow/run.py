"""#155 OBSERVE: view -> face by the keyplan arrow on untitled raster sheets (Savelovskaya, Sokolniki template).

new-case: docs/research/autoresearch-view-face-arrow/run.py - #155 OBSERVE keyplan-arrow replay runner

Research only; no product code, no delivery edits. Replay from the repository root (pilot host, inputs mounted):
    uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-arrow/run.py <new_out_dir> [--runs 3]
Contract and frozen parameters: docs/research/autoresearch-view-face-arrow.md and fixture.json next to this file.
"""
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter, deque
from pathlib import Path
from time import monotonic

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 4.4/blender.exe')
BUDGET_S = 3600
GREY_FILL = (208, 209, 210)
DUMP = r'''
import bpy, sys, numpy as np
fbx, out = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
dg = bpy.context.evaluated_depsgraph_get()
tris = []
for ob in sorted(bpy.context.scene.objects, key=lambda o: o.name):
    if ob.type != 'MESH':
        continue
    ev = ob.evaluated_get(dg); me = ev.to_mesh(); me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    m = np.array(ob.matrix_world); co = co @ m[:3, :3].T + m[:3, 3]
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64); me.loop_triangles.foreach_get('vertices', t)
    tris.append(co[t.reshape(-1, 3)]); ev.to_mesh_clear()
np.save(out, np.concatenate(tris).astype(np.float32))
print('TRIS', sum(len(t) for t in tris))
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- raster primitives
def components(mask, reverse=False):
    """8-connected components of a bool mask -> list of (ys, xs) arrays, deterministic order."""
    seen = np.zeros(mask.shape, bool)
    h, w = mask.shape
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)]); seen[y0, x0] = True; ys, xs = [], []
        while q:
            y, x = q.popleft(); ys.append(y); xs.append(x)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True; q.append((yy, xx))
        out.append((np.array(ys), np.array(xs)))
    return out[::-1] if reverse else out


def red_mask(img, p):
    r, g, b = p['red']
    return (img[..., 0] >= r) & (img[..., 1] <= g) & (img[..., 2] <= b)


def grey_mask(img, p):
    lo, hi, chroma = p['grey']
    i = img.astype(int)
    return (i[..., 0] >= lo) & (i[..., 0] <= hi) & (i.max(-1) - i.min(-1) <= chroma)


def triangles(img, p, reverse=False):
    out = []
    for ys, xs in components(red_mask(img, p), reverse):
        h, w = int(np.ptp(ys)) + 1, int(np.ptp(xs)) + 1
        area, fill = len(ys), len(ys) / (h * w)
        asp = max(h, w) / min(h, w)
        lo, hi = p['tri_area_px']; flo, fhi = p['tri_fill']; alo, ahi = p['tri_aspect']
        if not (lo <= area <= hi and flo <= fill <= fhi and alo <= asp <= ahi):
            continue
        if w > h:   # base horizontal -> arrow vertical; apex where rows are narrow
            prof = np.bincount(ys - ys.min(), minlength=h); n = max(1, h // 3)
            d = (0, -1) if prof[:n].mean() < prof[-n:].mean() else (0, 1)
        else:
            prof = np.bincount(xs - xs.min(), minlength=w); n = max(1, w // 3)
            d = (-1, 0) if prof[:n].mean() < prof[-n:].mean() else (1, 0)
        c = (float(xs.mean()), float(ys.mean()))
        apex = (c[0] + d[0] * (w if d[0] else h) / 2, c[1] + d[1] * (h if d[1] else w) / 2)
        out.append(dict(c=c, d=d, apex=apex, px=(ys, xs), box=(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)))
    return out


def find_line(img, tri, p, reverse=False):
    best = None
    d = tri['d']
    for ys, xs in components(red_mask(img, p), reverse):
        h, w = int(np.ptp(ys)) + 1, int(np.ptp(xs)) + 1
        if min(h, w) > p['line_max_thick_px'] or max(h, w) < p['line_min_len_px']:
            continue
        horizontal = w > h
        if horizontal != (d[1] != 0):   # line must be perpendicular to the arrow
            continue
        mid = (float(xs.mean()), float(ys.mean()))
        ahead = (mid[0] - tri['c'][0]) * d[0] + (mid[1] - tri['c'][1]) * d[1]
        if 0 < ahead <= p['line_max_gap_px'] and (best is None or ahead < best[0]):
            best = (ahead, dict(mid=mid, px=(ys, xs), box=(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)))
    return None if best is None else best[1]


def find_icon(img, tri, p, reverse=False):
    r = p['icon_max_dist_px']
    cx, cy = (int(v) for v in tri['c'])
    y0, x0 = max(0, cy - r), max(0, cx - r)
    win = grey_mask(img[y0:cy + r, x0:cx + r], p)
    best = None
    for ys, xs in components(win, reverse):
        if len(ys) < p['icon_min_area_px']:
            continue
        ys, xs = ys + y0, xs + x0
        c = (float(xs.mean()), float(ys.mean()))
        ahead = (c[0] - tri['c'][0]) * tri['d'][0] + (c[1] - tri['c'][1]) * tri['d'][1]
        dist = math.hypot(c[0] - tri['c'][0], c[1] - tri['c'][1])
        if ahead > 0 and dist <= r and (best is None or dist < best[0]):
            best = (dist, dict(px=(ys, xs), box=(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)))
    return None if best is None else best[1]


# ---------------------------------------------------------------- model footprint
def footprint(tris, p):
    res = p['fp_res_m']
    lo = tris.reshape(-1, 3).min(0); hi = tris.reshape(-1, 3).max(0)
    W, H = int((hi[0] - lo[0]) / res) + 2, int((hi[1] - lo[1]) / res) + 2
    img = Image.new('I', (W, H), 0); dr = ImageDraw.Draw(img)
    zmax = tris[:, :, 2].max(1)
    order = np.argsort(zmax, kind='stable')
    xy = np.stack([(tris[order, :, 0] - lo[0]) / res, (hi[1] - tris[order, :, 1]) / res], -1)
    for t, z in zip(xy.tolist(), ((zmax[order] - lo[2]) * 100).astype(int) + 1):
        dr.polygon([tuple(q) for q in t], fill=int(z))
    hm = np.array(img)
    occ = hm[hm > 0]
    ground = float(np.percentile(occ, p['fp_ground_pct']))   # amendment A1 (pre-score)
    fp = hm >= ground + p['fp_min_above_ground_m'] * 100
    ys, xs = np.nonzero(fp)
    fp = fp[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return fp, dict(ground_m=round((ground - 1) / 100 + float(lo[2]), 3), shape=list(fp.shape),
                    fill=round(float(fp.mean()), 4), tris=int(len(tris)))


def concavity(mask, side, res, min_depth):
    """Per-column (or row) depth of the first filled cell from the given bbox side; returns (index range, depths)."""
    m = {'top': mask, 'bottom': mask[::-1], 'left': mask.T, 'right': mask.T[::-1]}[side]
    has = m.any(0)
    depth = np.where(has, m.argmax(0), m.shape[0]) * res
    idx = np.nonzero(depth > min_depth)[0]
    return idx, depth


# ---------------------------------------------------------------- registration and answer
SIDE_OF_AZ = {0: 'right', 90: 'top', 180: 'left', 270: 'bottom'}   # footprint image: row 0 = +Y


def transforms():
    for flip in (False, True):
        for k in range(4):
            yield flip, k


def apply_mask(m, flip, k):
    return np.rot90(np.fliplr(m) if flip else m, k)


def apply_vec(v, flip, k):
    x, y = v
    if flip:
        x = -x
    for _ in range(k):
        x, y = y, -x
    return x, y


def apply_uv(u, v, flip, k):
    if flip:
        u = 1 - u
    for _ in range(k):
        u, v = v, 1 - u
    return u, v


def answer(icon_mask, d, origin_uv, fp, p):
    H, W = fp.shape
    rows = []
    for flip, k in transforms():
        mg = apply_mask(icon_mask, flip, k)
        ratio = (mg.shape[1] / mg.shape[0]) / (W / H)
        iou = 0.0
        if 1 / p['reg_aspect_tol'] <= ratio <= p['reg_aspect_tol']:
            rs = np.array(Image.fromarray(mg.astype(np.uint8) * 255).resize((W, H), Image.NEAREST)) > 0
            iou = float((rs & fp).sum() / max(1, (rs | fp).sum()))
        vx, vy = apply_vec(d, flip, k)
        az = int(round(math.degrees(math.atan2(vy, -vx)) / 90.0)) * 90 % 360   # n = -v, model y = -image y
        rows.append(dict(flip=flip, k=k, iou=round(iou, 6), az=az))
    best = max(rows, key=lambda r: (r['iou'], -r['k'], r['flip']))
    other = max([r['iou'] for r in rows if r['az'] != best['az']] or [0.0])
    margin = best['iou'] - other
    out = dict(best_iou=round(best['iou'], 6), margin=round(margin, 6), transform=[best['flip'], best['k']])
    if best['iou'] < p['reg_min_iou'] or margin < p['reg_min_margin']:
        return dict(out, az=None, wall=None, depth_m=None)
    u, v = apply_uv(*origin_uv, best['flip'], best['k'])
    vx, vy = apply_vec(d, best['flip'], best['k'])
    x, y = u * W, v * H
    hit = None
    for _ in range(int(4 * (W + H))):
        xi, yi = int(math.floor(x)), int(math.floor(y))
        if 0 <= xi < W and 0 <= yi < H and fp[yi, xi]:
            hit = (xi, yi); break
        x += vx * 0.5; y += vy * 0.5
    depth = None
    if hit is not None:
        res = p['fp_res_m']
        depth = {0: (W - 1 - hit[0]), 180: hit[0], 90: hit[1], 270: (H - 1 - hit[1])}[best['az']] * res
        depth = round(depth, 3)
    wall = None if depth is None else 'outer' if depth <= p['outer_wall_depth_m'] else 'inner'
    return dict(out, az=best['az'], wall=wall, depth_m=depth)


def read(img, key_xy, fp, p, reverse=False):
    """Reader R on one raster: the triangle nearest key_xy (zoom px) -> answer row."""
    tris = triangles(img, p, reverse)
    if not tris:
        return dict(status='no_arrow', az=None)
    tri = min(tris, key=lambda t: (math.hypot(t['c'][0] - key_xy[0], t['c'][1] - key_xy[1]), t['c']))
    icon = find_icon(img, tri, p, reverse)
    if icon is None:
        return dict(status='no_icon', az=None, d=list(tri['d']))
    line = find_line(img, tri, p, reverse)
    origin = line['mid'] if line else tri['apex']
    x0, y0, x1, y1 = icon['box']
    m = np.zeros((y1 - y0, x1 - x0), bool); m[icon['px'][0] - y0, icon['px'][1] - x0] = True
    uv = ((origin[0] - x0) / (x1 - x0), (origin[1] - y0) / (y1 - y0))
    a = answer(m, tri['d'], uv, fp, p)
    return dict(a, status='read', d=list(tri['d']), line=line is not None, icon_px=int(len(icon['px'][0])))


# ---------------------------------------------------------------- states
def patch_of(img, parts, pad=20):
    xs0 = min(b[0] for b in parts) - pad; ys0 = min(b[1] for b in parts) - pad
    xs1 = max(b[2] for b in parts) + pad; ys1 = max(b[3] for b in parts) + pad
    xs0, ys0 = max(0, xs0), max(0, ys0)
    return img[ys0:ys1, xs0:xs1].copy(), (xs0, ys0)


def on_canvas(patch, pad=300):
    c = np.full((patch.shape[0] + 2 * pad, patch.shape[1] + 2 * pad, 3), 253, np.uint8)
    c[pad:pad + patch.shape[0], pad:pad + patch.shape[1]] = patch
    return c, pad


def states(img, key_xy, fp, fp_gt_inner, gt_az, p):
    """Return {state: (raster, key_xy, changed_px, expected)}; expected = 'gt' | 'abstain' | ('inner', depth)."""
    tris = triangles(img, p)
    tri = min(tris, key=lambda t: (math.hypot(t['c'][0] - key_xy[0], t['c'][1] - key_xy[1]), t['c'])) if tris else None
    icon = find_icon(img, tri, p) if tri else None
    out = {'clean': (img, key_xy, 0, 'gt')}
    if tri is None or icon is None:
        return out
    line = find_line(img, tri, p)
    parts = [tri['box'], icon['box']] + ([line['box']] if line else [])
    patch, (ox, oy) = patch_of(img, parts)
    loc = lambda xy: (xy[0] - ox, xy[1] - oy)  # noqa: E731
    kc = loc(tri['c'])
    for name, arr, key in (('rotated', np.rot90(patch), (kc[1], patch.shape[1] - 1 - kc[0])),
                           ('mirrored', np.fliplr(patch), (patch.shape[1] - 1 - kc[0], kc[1]))):
        c, pad = on_canvas(np.ascontiguousarray(arr))
        out[name] = (c, (key[0] + pad, key[1] + pad), int(arr.size // 3), 'gt')
    iy, ix = icon['px'][0] - oy, icon['px'][1] - ox
    no_icon = patch.copy(); no_icon[iy, ix] = 253
    c, pad = on_canvas(no_icon); out['no_icon'] = (c, (kc[0] + pad, kc[1] + pad), int(len(iy)), 'abstain')
    sym = no_icon.copy(); bx0, by0, bx1, by1 = (v - o for v, o in zip(icon['box'], (ox, oy, ox, oy)))
    sym[by0:by1, bx0:bx1] = GREY_FILL
    c, pad = on_canvas(sym)
    out['symmetric'] = (c, (kc[0] + pad, kc[1] + pad), int((sym != patch).any(-1).sum()), 'abstain')
    # inner: shift arrow + line along the icon side to the centre of the icon's concavity on the arrow side
    x0, y0, x1, y1 = icon['box']
    m = np.zeros((y1 - y0, x1 - x0), bool); m[icon['px'][0] - y0, icon['px'][1] - x0] = True
    side = {(0, 1): 'top', (0, -1): 'bottom', (1, 0): 'left', (-1, 0): 'right'}[tuple(tri['d'])]
    idx, _ = concavity(m, side, 1.0, 0.15 * (m.shape[0] if side in ('top', 'bottom') else m.shape[1]))
    if len(idx) and fp_gt_inner.get(gt_az) is not None:
        centre = float(np.median(idx))
        if side in ('bottom', 'right'):
            centre = centre  # mask flipped only along the depth axis; the index axis is unchanged
        ref = line['mid'] if line else tri['apex']
        if side in ('top', 'bottom'):
            delta = (int(round(x0 + centre - ref[0])), 0)
        else:
            delta = (0, int(round(y0 + centre - ref[1])))
        inner = patch.copy()
        moved = [tri['px']] + ([line['px']] if line else [])
        for ys, xs in moved:
            inner[ys - oy, xs - ox] = 253
        changed = 0
        for ys, xs in moved:
            ty, tx = ys - oy + delta[1], xs - ox + delta[0]
            ok = (ty >= 0) & (ty < inner.shape[0]) & (tx >= 0) & (tx < inner.shape[1])
            inner[ty[ok], tx[ok]] = img[ys[ok], xs[ok]]; changed += int(ok.sum())
        c, pad = on_canvas(inner)
        out['inner'] = (c, (kc[0] + delta[0] + pad, kc[1] + delta[1] + pad), changed, ('inner', fp_gt_inner[gt_az]))
    return out


def fp_inner_depths(fp, p):
    """Model-side GT for the injected inner rows: median concavity depth per side (None if no concavity)."""
    out = {}
    for az, side in SIDE_OF_AZ.items():
        idx, depth = concavity(fp, side, p['fp_res_m'], p['outer_wall_depth_m'])
        idx = idx[depth[idx] < (fp.shape[0] if side in ('top', 'bottom') else fp.shape[1]) * p['fp_res_m'] * 0.9]
        out[az] = round(float(np.median(depth[idx])), 3) if len(idx) else None
    return out


def outcome(row, expected, gt_az, p):
    if expected == 'abstain':
        return 'abstain_ok' if row.get('az') is None else 'wrong'
    if row.get('az') is None:
        return 'abstain'
    if row['az'] != gt_az:
        return 'wrong'
    if isinstance(expected, tuple):
        ok = row['wall'] == 'inner' and abs(row['depth_m'] - expected[1]) <= p['inner_depth_tol_m']
        return 'correct' if ok else 'wrong_wall'
    return 'correct'


# ---------------------------------------------------------------- run
def raster(page, zoom):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).copy()


def one_run(fx, out):
    p = fx['params']; z = p['zoom']; root = Path(fx['root'])
    out.mkdir(parents=True)
    rows, models = [], {}
    for name, al in fx['albums'].items():
        tri_path = out / f'{name}.tris.npy'
        r = subprocess.run([str(BLENDER), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
                            '--python-expr', DUMP, '--', str(root / al['fbx']), str(tri_path)],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode:
            raise RuntimeError(f'blender failed on {name}: {r.stdout[-500:]} {r.stderr[-500:]}')
        fp, info = footprint(np.load(tri_path), p)
        tri_path.unlink()
        gt_inner = fp_inner_depths(fp, p)
        models[name] = dict(info, gt_inner_depth_m={str(k): v for k, v in gt_inner.items()})
        with pymupdf.open(root / al['pdf']) as pdf:
            cache = {}
            for page, key, view, gt_az in al['arrows']:
                if page not in cache:
                    cache[page] = raster(pdf[page - 1], z)
                img = cache[page]
                kxy = (key[0] * z, key[1] * z)
                st = states(img, kxy, fp, gt_inner, gt_az, p)
                row = dict(album=name, page=page, view=view, gt_az=gt_az, states={})
                for sname in ('clean', 'rotated', 'mirrored', 'symmetric', 'no_icon', 'inner'):
                    if sname not in st:
                        row['states'][sname] = dict(outcome='not_exercised')
                        continue
                    ras, k2, changed, expected = st[sname]
                    res = read(ras, k2, fp, p)
                    if sname == 'clean':
                        rev = read(ras, k2, fp, p, reverse=True)
                        res['reversal_parity'] = rev == res
                    if sname != 'clean' and changed == 0:
                        res = dict(res, outcome='not_exercised')
                    else:
                        res['outcome'] = outcome(res, expected, gt_az, p)
                    res['changed_px'] = changed
                    res['expected'] = list(expected) if isinstance(expected, tuple) else expected
                    row['states'][sname] = res
                rows.append(row)
    ctrl = []
    c = fx['control_no_arrow']
    with pymupdf.open(c['pdf']) as pdf:
        for pg in c['pages']:
            n = len(triangles(raster(pdf[pg - 1], z), p))
            ctrl.append(dict(page=pg, triangles=n, outcome='abstain_ok' if n == 0 else 'triggered'))
    return rows, ctrl, models


def tally(rows):
    t = {}
    for r in rows:
        for s, v in r['states'].items():
            t.setdefault(s, Counter())[v['outcome']] += 1
            if s == 'clean' and v.get('wall'):
                t.setdefault('clean_wall', Counter())[v['wall']] += 1
    return {k: dict(sorted(v.items())) for k, v in t.items()}


def verdict(t, rows, ctrl):
    g = lambda s, k: t.get(s, {}).get(k, 0)  # noqa: E731
    inner_ex = sum(v for k, v in t.get('inner', {}).items() if k != 'not_exercised')
    w = next(r for r in rows if r['album'] == 'B3' and r['view'] == 'p1 upper long')
    return dict(
        clean_wrong_0=g('clean', 'wrong') == 0, clean_correct_ge14=g('clean', 'correct') >= 14,
        rotated_wrong_0=g('rotated', 'wrong') == 0, rotated_correct_ge14=g('rotated', 'correct') >= 14,
        mirrored_wrong_0=g('mirrored', 'wrong') == 0, mirrored_correct_ge14=g('mirrored', 'correct') >= 14,
        symmetric_wrong_0=g('symmetric', 'wrong') == 0 and g('symmetric', 'abstain_ok') > 0,
        no_icon_abstain_16=g('no_icon', 'abstain_ok') == 16,
        inner_wrong_az_0=g('inner', 'wrong') == 0,
        inner_wall_ge75=inner_ex > 0 and g('inner', 'correct') >= 0.75 * inner_ex,
        clean_outer_ge14=t.get('clean_wall', {}).get('outer', 0) >= 14,
        control_abstain_4=all(c['outcome'] == 'abstain_ok' for c in ctrl),
        witness_B3_p1_upper=w['states']['clean'].get('az') == 270,
    )


def main():
    out = Path(sys.argv[1]).resolve()
    runs_n = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 3
    if out.exists():
        raise SystemExit(f'output exists: {out}')
    fx = json.loads((HERE / 'fixture.json').read_text(encoding='utf-8'))
    root = Path(fx['root'])
    pins = {}
    for name, al in fx['albums'].items():
        for role in ('pdf', 'fbx'):
            h = sha(root / al[role])
            if h != al[f'{role}_sha256']:
                raise SystemExit(f'input SHA-256 mismatch: {name} {role}')
            pins[f'{name}.{role}'] = h
    if sha(fx['control_no_arrow']['pdf']) != fx['control_no_arrow']['sha256']:
        raise SystemExit('control PDF SHA-256 mismatch')
    pins.update({'run.py': sha(HERE / 'run.py'), 'fixture.json': sha(HERE / 'fixture.json'),
                 'blender': sha(BLENDER), 'uv.lock': sha('uv.lock')})
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    t0, runs, digests, status = monotonic(), [], [], 'finished'
    for i in range(runs_n):
        if i and (monotonic() - t0) + 1.15 * runs[0]['wall_s'] * (runs_n - i) > BUDGET_S:
            status = 'inconclusive_budget'; break
        s = monotonic()
        rows, ctrl, models = one_run(fx, out / f'run{i + 1}')
        blob = json.dumps(dict(rows=rows, control=ctrl, models=models), sort_keys=True, ensure_ascii=False)
        (out / f'run{i + 1}' / 'rows.json').write_text(blob, encoding='utf-8')
        digests.append(hashlib.sha256(blob.encode()).hexdigest())
        runs.append(dict(wall_s=round(monotonic() - s, 3), digest=digests[-1]))
        print(f'run {i + 1}: {runs[-1]}', flush=True)
    if len(set(digests)) != 1:
        status = 'parity_failed'
    t = tally(rows)
    walls = [r['wall_s'] for r in runs]
    receipt = dict(schema='view-face-arrow-receipt/1', card='t_436d52d6 (#155)', head=head, status=status,
                   runs=runs, median_s=statistics.median(walls), spread_s=round(max(walls) - min(walls), 3),
                   pins=pins, tally=t, verdict=verdict(t, rows, ctrl), control=ctrl, models=models,
                   rows=[dict(album=r['album'], view=r['view'], gt_az=r['gt_az'],
                              states={k: {kk: v.get(kk) for kk in ('outcome', 'az', 'wall', 'depth_m', 'best_iou',
                                                                    'margin', 'transform', 'line', 'changed_px',
                                                                    'reversal_parity', 'status')}
                                      for k, v in r['states'].items()}) for r in rows])
    text = json.dumps(receipt, indent=1, sort_keys=True, ensure_ascii=False) + '\n'
    (out / 'receipt.json').write_text(text, encoding='utf-8')
    print(json.dumps(dict(status=status, tally=t, verdict=receipt['verdict'], median_s=receipt['median_s']),
                     ensure_ascii=False))
    print('receipt sha256', hashlib.sha256(text.encode()).hexdigest())


if __name__ == '__main__':
    main()
