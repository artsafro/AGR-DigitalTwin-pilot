"""#161 OBSERVE: view -> wall direction by drawn glass vs model glazing (Silikatny UK350/DO150).

Replay (pilot host, inputs on the owner's PC, Blender 4.4):
  uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-glass/run.py C:/x/ar161/<fresh>

One run = Blender ortho renders of the model per candidate azimuth + PDF re-read + score. The runner refuses an
existing output dir and checks the input SHA-256 before and after. Frozen params live in fixture.json.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

HERE = Path(__file__).resolve().parent
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 4.4/blender.exe')

ORTHO = r'''
import bpy, sys, math, mathutils
import numpy as np
src, outdir, azs, res, glass, hidden = sys.argv[sys.argv.index('--') + 1:][:6]
azs = [int(a) for a in azs.split(',')]; res = float(res); glass = set(glass.split(',')); hidden = set(hidden.split(','))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=src)
sc = bpy.context.scene
for ob in sc.objects:
    if ob.type != 'MESH':
        continue
    if ob.name in hidden:
        ob.hide_render = True
    # raw OBJ millimetres, Blender default import -> (x, z, -y) metres, Z up (proper rotation, no mirror)
    ob.matrix_world = mathutils.Matrix.Diagonal((0.001, 0.001, 0.001, 1)) @ mathutils.Matrix.Rotation(math.radians(-90), 4, 'X') @ ob.matrix_world
    ob.color = (0, 0, 0, 1) if ob.name in glass else (0.6, 0.6, 0.6, 1)
bpy.context.view_layer.update()
mins = np.array([1e9] * 3); maxs = -mins
for ob in sc.objects:
    if ob.type == 'MESH' and not ob.hide_render:
        for c in ob.bound_box:
            w = np.array(ob.matrix_world @ mathutils.Vector(c)); mins = np.minimum(mins, w); maxs = np.maximum(maxs, w)
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'OBJECT'; sh.background_type = 'VIEWPORT'
sh.background_color = (1, 1, 1); sc.view_settings.view_transform = 'Standard'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.sensor_fit = 'HORIZONTAL'; cam.data.clip_end = 1000
ctr = (mins + maxs) / 2; span = float(np.linalg.norm((maxs - mins)[:2])) + 4; Z = float(maxs[2] - mins[2]) + 4
cam.data.ortho_scale = span
sc.render.resolution_x = int(span / res); sc.render.resolution_y = int(Z / res)
zc = float(mins[2]) - 2 + Z / 2
meta = dict(bbox=[mins.round(3).tolist(), maxs.round(3).tolist()], res=res, zc=zc, H=sc.render.resolution_y, W=sc.render.resolution_x)
for az in azs:
    n = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0])
    pos = ctr + n * span; pos[2] = zc
    cam.location = pos.tolist(); cam.rotation_euler = (math.radians(90), 0, math.radians(az + 90))
    sc.render.filepath = f'{outdir}/ortho_az{az:03d}.png'
    bpy.ops.render.render(write_still=True)
import json; open(f'{outdir}/ortho_meta.json', 'w').write(json.dumps(meta))
print('ORTHO_OK')
'''


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def opening(m, k):
    """Binary opening with a k x k square (removes lines / text thinner than k px)."""
    from PIL import ImageFilter
    im = Image.fromarray(m.astype(np.uint8) * 255)
    im = im.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    return np.array(im) > 0


def largest_bbox(m):
    """Bbox of what survives the opening (thin lines / text gone; the clip holds one drawn view)."""
    ys, xs = np.nonzero(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def read_view(page, clip, p, legend):
    z = p['zoom']
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=pymupdf.Rect(*clip), alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(int)
    building = a.sum(-1) < p['page_white_sum']
    box = largest_bbox(opening(building, p['open_px']))
    x0, y0, x1, y1 = box
    c = a[y0:y1, x0:x1]
    b = building[y0:y1, x0:x1]
    dist = np.min([np.sqrt(((c - np.array(s)) ** 2).sum(-1)) for s in legend], axis=0)
    lum = c.mean(-1)
    red = (c[..., 0] > 150) & (c[..., 1] < 90) & (c[..., 2] < 90)
    glass = b & ~red & (dist > p['legend_dist']) & (lum >= p['glass_lum'][0]) & (lum <= p['glass_lum'][1])
    h_m = p['view_height_m']
    rows = int(round(h_m / p['grid_m']))
    px_per_m = (y1 - y0) / h_m
    cols = max(1, int(round((x1 - x0) / px_per_m / p['grid_m'])))
    g = np.array(Image.fromarray(glass.astype(np.uint8) * 255).resize((cols, rows), Image.BILINEAR)) / 255.0
    return g, dict(box_px=[x0, y0, x1, y1], width_m=round((x1 - x0) / px_per_m, 2), glass_frac=round(float(glass[b].mean()), 4))


def model_masks(out, p):
    meta = json.loads((out / 'ortho_meta.json').read_text())
    res, zc, H = meta['res'], meta['zc'], meta['H']
    r_top = int(round(H / 2 - (p['view_height_m'] - zc) / res)); r_bot = int(round(H / 2 - (0.0 - zc) / res))
    masks = {}
    for az in p['azimuths']:
        im = np.array(Image.open(out / f'ortho_az{az:03d}.png').convert('L'))
        occ = (im < 250).any(0); xs = np.nonzero(occ)[0]
        band = im[r_top:r_bot, xs.min():xs.max() + 1]
        glass = (band < 60).astype(np.uint8) * 255
        rows = int(round(p['view_height_m'] / p['grid_m'])); cols = int(round(band.shape[1] * res / p['grid_m']))
        masks[az] = np.array(Image.fromarray(glass).resize((cols, rows), Image.BILINEAR)) / 255.0
    return masks, meta


def ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def best_offset(v, m, p):
    """Max NCC over horizontal offsets; overlap >= min_overlap of the narrower width."""
    wv, wm = v.shape[1], m.shape[1]
    need = int(np.ceil(p['min_overlap'] * min(wv, wm)))
    best = (-1.0, None)
    for s in range(-(wv - need), wm - need + 1):
        a0, a1 = max(0, s), min(wm, s + wv)
        if a1 - a0 < need:
            continue
        sc = ncc(v[:, a0 - s:a1 - s], m[:, a0:a1])
        if sc > best[0]:
            best = (sc, s)
    return best


def decide(scores, p):
    order = sorted(scores, key=lambda az: (-scores[az][0], az))
    top = order[0]
    other = max(scores[az][0] for az in order[1:])
    margin = scores[top][0] - other
    ans = top if scores[top][0] >= p['tau'] and margin >= p['delta'] else None
    return ans, round(scores[top][0], 4), round(margin, 4), top


def outcome(ans, gt):
    if gt is None:
        return 'diagnostic'
    if ans is None:
        return 'abstain'
    return 'correct' if ans in gt else 'wrong'


def one_run(fx, out):
    p = fx['params']
    out.mkdir(parents=True)
    t0 = time.perf_counter()
    r = subprocess.run([str(BLENDER), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
                        '--python-expr', ORTHO, '--', fx['model'], str(out), ','.join(map(str, p['azimuths'])),
                        str(p['render_res_m']), ','.join(p['glass_objects']), ','.join(p['hidden_objects'])],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode or 'ORTHO_OK' not in r.stdout:
        raise RuntimeError(r.stdout[-800:] + r.stderr[-800:])
    masks, meta = model_masks(out, p)
    doc = pymupdf.open(fx['pdf'])
    rows = []
    for v in fx['views']:
        g, info = read_view(doc[v['page'] - 1], v['clip_pt'], p, fx['legend_rgb'])
        scores = {az: best_offset(g, masks[az], p) for az in p['azimuths']}
        ans, top_sc, margin, top = decide(scores, p)
        gt = v['gt_az']
        states = {}
        for sname, gs in (('mirror', np.ascontiguousarray(g[:, ::-1])), ('blank', np.zeros_like(g))):
            ss = {az: best_offset(gs, masks[az], p) for az in p['azimuths']}
            a2, s2, m2, t2 = decide(ss, p)
            states[sname] = dict(changed_cells=int((np.abs(gs - g) > 1e-9).sum()), answer=a2, top=t2, top_score=s2, margin=m2,
                                 true_az_answered=bool(gt and a2 in gt))
        rows.append(dict(view=v['id'], kind=v['kind'], inner=v['inner'], gt_az=gt, answer=ans, top=top, top_score=top_sc,
                         margin=margin, outcome=outcome(ans, gt), opposite_score=round(scores[(top + 180) % 360][0], 4),
                         scores={str(az): round(s[0], 4) for az, s in scores.items()},
                         offsets={str(az): s[1] for az, s in scores.items()}, states=states, **info))
    return rows, meta, round(time.perf_counter() - t0, 3)


def tally(rows):
    t = {}
    for r in rows:
        t[r['outcome']] = t.get(r['outcome'], 0) + 1
    return t


def main():
    out = Path(sys.argv[1])
    if out.exists():
        sys.exit(f'refusing existing output {out}')
    fx = json.loads((HERE / 'fixture.json').read_text(encoding='utf-8'))
    pins = {k: fx['sha256'][k] for k in ('pdf', 'model')}
    for k in pins:
        if sha(fx[k]) != pins[k]:
            sys.exit(f'input hash mismatch: {k}')
    rows, meta, wall = one_run(fx, out)
    for k in pins:
        if sha(fx[k]) != pins[k]:
            sys.exit(f'input changed during run: {k}')
    body = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    rec = dict(status='finished', wall_s=wall, rows_sha256=hashlib.sha256(body.encode()).hexdigest(), tally=tally(rows),
               runner_sha256=sha(__file__), fixture_sha256=sha(HERE / 'fixture.json'), inputs=pins, ortho=meta, rows=rows)
    (out / 'result.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print(json.dumps(dict(wall_s=wall, rows_sha256=rec['rows_sha256'], tally=rec['tally'])))
    for r in rows:
        print(r['view'], r['gt_az'], '->', r['answer'], 'top', r['top'], r['top_score'], 'm', r['margin'], 'opp', r['opposite_score'],
              r['outcome'], 'W', r['width_m'])


if __name__ == '__main__':
    main()
