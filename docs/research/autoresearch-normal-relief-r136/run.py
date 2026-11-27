"""OBSERVE: replay pinned #135 A1 and measure its geometry-gated joint stripe."""
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image

REV = 'a0f333e9225f259a9a5ec60eb47e69f986906e31'
OLD = 'docs/research/autoresearch-normal-relief-r135'
READBACK = '4bcf30ca1a6e079d5c33eded338a4e28de6807acbe565674b54bb202d4975a91'
STRIPE = 'joint-stripe'
N = 600


def ortho(points, target, direction):
    facing = np.array(direction) / np.linalg.norm(direction)
    right = np.cross(-facing, (0, 0, 1))
    right /= np.linalg.norm(right)
    up = np.cross(facing, right)
    p = points - target
    return np.stack((N / 2 + 1000 * (p @ right), N / 2 - 1000 * (p @ up), p @ facing), axis=-1)


def raster(tris):
    depth = np.full((N, N), -np.inf)
    joint = np.zeros((N, N), dtype=bool)
    for t, is_joint in tris:
        lo = np.maximum(0, np.ceil(t[:, :2].min(axis=0) - 0.5).astype(int))
        hi = np.minimum(N, np.floor(t[:, :2].max(axis=0) - 0.5).astype(int) + 1)
        if np.any(hi <= lo):
            continue
        ix, iy = lo
        ex, ey = hi
        d = depth[iy:ey, ix:ex]
        a, b = (t[1:] - t[0])[:, :2]
        det = a[0] * b[1] - a[1] * b[0]
        if abs(det) < 1e-10:
            continue
        x = np.arange(ix, ex)[None, :] + 0.5 - t[0, 0]
        y = np.arange(iy, ey)[:, None] + 0.5 - t[0, 1]
        u, v = (x * b[1] - y * b[0]) / det, (a[0] * y - a[1] * x) / det
        z = t[0, 2] + u * (t[1, 2] - t[0, 2]) + v * (t[2, 2] - t[0, 2])
        hit = (u >= 0) & (v >= 0) & (u + v <= 1) & (z > d)
        d[hit] = z[hit]
        joint[iy:ey, ix:ex][hit] = is_joint
    return np.isfinite(depth), joint


def dilate(mask, r):
    h, w = mask.shape
    p = np.pad(mask, r)
    result = mask.copy()
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            if x*x + y*y <= r*r:
                result |= p[r+y:r+y+h, r+x:r+x+w]
    return result


def self_check():
    p = ortho(np.array([[0, 0.001, 0.001]]), (0, 0, 0), (1, 0, 0))
    assert np.array_equal(p, [[301, 299, 0]])
    t = np.array([[1, 1, 0], [4, 1, 0], [1, 4, 0]])
    cover, joint = raster([(t + [0, 0, 1], False), (t, True)])
    assert cover.sum() == 6 and not joint.any()
    seed = np.zeros((5, 5), dtype=bool)
    seed[2, 2] = True
    assert dilate(seed, 2).sum() == 13


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(name):
    return subprocess.check_output(['git', 'show', f'{REV}:{OLD}/{name}'])


def mask_from(old, source):
    raw = (old.EVID / 'cut-v045/readback.json').read_bytes()
    if sha(raw) != READBACK:
        raise ValueError('joint readback hash mismatch')
    shots = next(ast.literal_eval(node.value) for node in ast.parse(source).body
                 if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'SHOTS')
    _, target, direction = next(row for row in shots if row[0] == STRIPE)
    tris = [(ortho(np.asarray(t['xyz']), target, direction), face['joint'] == 1)
            for face in json.loads(raw)['rows'] if face['object'] == 'K3_StylobateWalls.001'
            and face['material_id'] == 1 for t in face['triangles']]
    cover, seed = raster(tris)
    return cover, seed, dilate(seed, 20), len(tris)


def local(old, out, cover, seed, band):
    variants = ('S', *old.CANDS)
    paths = {k: out / f'{k}_relief_{STRIPE}.png' for k in variants}
    rgba = {k: np.asarray(Image.open(path).convert('RGBA')) for k, path in paths.items()}
    ys, ms = {}, {}
    for k in variants:
        ys[k], ms[k] = old.score._load(paths[k])
    opaque = np.logical_and.reduce(list(ms.values()))
    guard = np.pad(opaque, 1)
    common = np.logical_and.reduce([guard[y:y+N, x:x+N] for y in range(3) for x in range(3)])
    overlap = float((cover & opaque).sum() / cover.sum()) if cover.any() else 0.0
    inside, outside = common & band, common & ~band
    clipping = {k: float((ys[k][ms[k]] >= 0.999).mean()) if ms[k].any() else None for k in variants}
    counts = dict(visible_seed=int(seed.sum()), projected_id1=int(cover.sum()), opaque_overlap=overlap,
                  band=int(inside.sum()), off_band=int(outside.sum()))
    if (not seed.any() or overlap < 0.9 or min(counts['band'], counts['off_band']) < 1000
            or any(v is None or v > 0.01 for v in clipping.values())):
        return dict(status='not_measured', counts=counts, clipping=clipping)
    grad = {k: old.score._sobel(y) for k, y in ys.items()}
    rows = {}
    for k in old.CANDS:
        ref = 'v096' if k in ('P1', 'P2') else 'S'
        changed = np.any(rgba[k][..., :3] != rgba[ref][..., :3], axis=-1)
        def loss(m):
            return float(np.log((grad['S'][m].mean() + old.score.EPS) / (grad[k][m].mean() + old.score.EPS)))
        rows[k] = dict(loss=loss(inside), off_band_loss=loss(outside), rgb_changed_band=int((changed & inside).sum()),
                       rgb_changed_off_band=int((changed & outside).sum()),
                       alpha_changed=int((rgba[k][..., 3] != rgba[ref][..., 3]).sum()),
                       rgba_sha256=sha(rgba[k].tobytes()))
    return dict(status='measured', counts=counts, clipping=clipping, rows=rows, source_sha256=sha(rgba['S'].tobytes()))


def main():
    self_check()
    if sys.argv[1:] == ['--self-check']:
        print('3 geometry checks passed')
        return
    out = Path(sys.argv[1]).resolve()
    if not out.is_relative_to(Path.cwd().resolve()):
        raise ValueError('output must be inside the worktree')
    out.mkdir(parents=True)
    lib = out / 'r135'
    lib.mkdir()
    names = ('run.py', 'render.py', 'score.py', 'receipt_a1.json')
    blobs = {k: git_blob(k) for k in names}
    for k, data in blobs.items():
        (lib / k).write_bytes(data)
    spec = importlib.util.spec_from_file_location('r135', lib / 'run.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    pins = old.preflight()
    expected = json.loads(blobs['receipt_a1.json'])['runs'][0]['shots']
    cover, seed, band, triangles = mask_from(old, blobs['render.py'])
    start = time.perf_counter()
    rounds = []
    rec = dict(revision=REV, blobs={k: sha(v) for k, v in blobs.items()}, blender=str(old.BLENDER),
               pins=pins, readback_sha256=READBACK, triangles=triangles, rounds=rounds)
    receipt = out / 'receipt.json'
    def save():
        receipt.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    for i in range(1, 4):
        t = time.perf_counter()
        trial = out / f'run{i}'
        native_wall, base = old.one_run(trial, 10)
        mismatches = [k for k in sorted(base.keys() | expected.keys()) if base.get(k) != expected.get(k)]
        row = local(old, trial, cover, seed, band)
        duration = time.perf_counter() - t
        rounds.append(dict(round=i, native_seconds=round(native_wall, 3), seconds=round(duration, 3),
                           a1_parity=f'{len(expected)-len(mismatches)}/{len(expected)}', a1_mismatches=mismatches, **row))
        print(i, round(duration, 2), rounds[-1]['a1_parity'], row['status'],
              {k: round(v['loss'], 6) for k, v in row.get('rows', {}).items()}, flush=True)
        save()
        if i == 1 and time.perf_counter() - start + 2 * duration > 360:
            break
    rec.update(wall_seconds=round(time.perf_counter()-start, 3), result='inconclusive', status='complete',
               postflight=old.preflight() == pins and sha((old.EVID / 'cut-v045/readback.json').read_bytes()) == READBACK)
    if len(rounds) != 3 or rec['wall_seconds'] > 360:
        rec['status'] = 'budget_stop'
    elif all(r['status'] == 'measured' and not r['a1_mismatches'] for r in rounds) and rec['postflight']:
        rows = [r['rows'] for r in rounds]
        values = {k: median(r[k]['loss'] for r in rows) for k in old.CANDS}
        gaps = [r['v045']['loss'] - r['v096']['loss'] for r in rows]
        spread = max(gaps) - min(gaps)
        controls = all(abs(r['N0']['loss']) <= 1e-9 and not r['N0']['rgb_changed_band']
                       and r['P1']['loss'] - r['v096']['loss'] >= 0.10
                       and r['v096']['loss'] <= r['P2']['loss'] <= r['P1']['loss'] + 0.05
                       and all(r[k]['rgb_changed_band'] > 0 for k in ('P1', 'P2', 'v045', 'v096'))
                       and not (r['P1']['alpha_changed'] or r['P2']['alpha_changed']) for r in rows)
        rec.update(medians=values, gap_median=median(gaps), gap_spread=spread, controls=controls)
        if controls and spread <= 1e-9:
            rec['result'] = 'confirmed' if values['v045'] > 0 and values['v045']-values['v096'] >= 0.10 else 'refuted'
    save()
    print(rec['status'], rec['result'], sha(receipt.read_bytes()), receipt)


if __name__ == '__main__':
    main()
