"""KPP1 #1609 review sheets of the lattice method (oks-npm stage `verifier`, point `after`; one module for the three sheets, #1614 search-noise budget).

Pattern: new-case | new-case: read-only review sheets of the KPP1 lattice method; never a line or mesh source.

    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_sheets.py lines LINE_LIST.json NPM_DUMP.npz R1_DUMP.npz TEXTURE.png OUT.png
           [--zmin -0.3] [--zmax 4.7] [--ppm 60] [--check OUT_CHECK.json]
    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_sheets.py lattice LATTICE.json OUT.png --model LABEL MESH.npz CHECK.json
           [--model ...] [--z 0 8.65] [--s 0 78.64] [--ppm 24] [--title TEXT]
    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_sheets.py compose RENDER_DIR OUT.png corners|ground|elevations TITLE

`lines` (step 1): the planned lattice lines from `kpp1_lattice.py lines` over straight ground-floor W/S/N elevations of R1 v003.
NPM_DUMP / R1_DUMP: docs/research/body-modelling-1618/dump_mesh.py dumps of the r1-v003 NPM export (same triangles as
r1-v003, atlas UV, texture) and of r1-v003 itself. Frame: Revit = R1 FBX + (14.655, 5.355, 0) (jobs/KPP1/object.json);
the NPM dump is moved onto R1 by its bbox (spans must agree within 2 mm). The check JSON gives, per Revit opening, the
share of its area where R1 v003 is on the body plane (hole: low): a read-only consistency check of the Revit census
against r1-v003, not a line source. Refuses to write over an input; writes OUT via OUT.partial.

`lattice` (step 2): unrolled straight elevations S | E | N | W along the envelope ring (a ring that dies at a corner
shows), rings/stations marked closed or broken, lattice cells with defects highlighted (Artem 2026-11-21: ring
continuity; decision 5: local-signal map next to the wire). MESH.npz = dump_mesh.py output, CHECK.json =
`kpp1_lattice.py check` output for the same mesh and lattice. OUT.png must not alias an input; written via OUT.png.partial.png.

`compose` (step 3 / package): before (quad-v003) / after (v004) per camera from `kpp1_assemble.py render` outputs; rows = cameras
(corner set, the same cameras on the ground floor, or straight-on elevations), columns = v003 wire | v004 wire |
v003 tex | v004 tex. A missing render is an error naming it; an existing OUT fails (never overwrite).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kpp1_lattice as lc  # noqa: E402

R1_TO_REVIT = np.array([14.655, 5.355, 0.0])
FONT = 'C:/Windows/Fonts/arial.ttf'


def load(p):
    d = np.load(p, allow_pickle=True)
    return d['verts'], d['fn'], d['fi'], d['uvf'] if 'uvf' in d else None


def tris(fn, fi):
    if not np.all(fn == 3):
        raise ValueError('dump is not triangulated')
    return fi.reshape(-1, 3)


def view(f, P):
    """screen u (right), z (up), depth (larger = farther) for facade f seen from outside."""
    if f == 'S':
        return P[:, 0], P[:, 2], P[:, 1]
    if f == 'N':
        return -P[:, 0], P[:, 2], -P[:, 1]
    return -P[:, 1], P[:, 2], P[:, 0]  # W


def facing(f, n):
    return {'S': -n[:, 1], 'N': n[:, 1], 'W': -n[:, 0]}[f] > 0.05


def raster(f, V, T, UV, tex, win, ppm):
    u0, u1, z0, z1 = win
    W, H = int((u1 - u0) * ppm), int((z1 - z0) * ppm)
    img = np.full((H, W, 3), 235, np.uint8)
    zb = np.full((H, W), np.inf)
    su, sz, sd = view(f, V)
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    ok = facing(f, n)
    th, tw = tex.shape[:2] if tex is not None else (1, 1)
    for t in np.nonzero(ok)[0]:
        idx = T[t]
        x = (su[idx] - u0) * ppm
        y = (z1 - sz[idx]) * ppm
        if x.max() < 0 or x.min() >= W or y.max() < 0 or y.min() >= H:
            continue
        xa, xb = max(int(np.floor(x.min())), 0), min(int(np.ceil(x.max())), W - 1)
        ya, yb = max(int(np.floor(y.min())), 0), min(int(np.ceil(y.max())), H - 1)
        if xb < xa or yb < ya:
            continue
        gx, gy = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-12:
            continue
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        c = 1 - a - b
        m = (a >= -1e-3) & (b >= -1e-3) & (c >= -1e-3)
        if not m.any():
            continue
        dep = a * sd[idx[0]] + b * sd[idx[1]] + c * sd[idx[2]]
        sub = zb[ya:yb + 1, xa:xb + 1]
        m &= dep < sub - 1e-6
        if not m.any():
            continue
        sub[m] = dep[m]
        if UV is None:
            col = np.array([180, 180, 180])
            img[ya:yb + 1, xa:xb + 1][m] = col
        else:
            uv = UV[3 * t:3 * t + 3]
            uu = a * uv[0, 0] + b * uv[1, 0] + c * uv[2, 0]
            vv = a * uv[0, 1] + b * uv[1, 1] + c * uv[2, 1]
            px = np.clip((uu % 1.0) * tw, 0, tw - 1).astype(int)
            py = np.clip((1 - vv % 1.0) * th, 0, th - 1).astype(int)
            img[ya:yb + 1, xa:xb + 1][m] = tex[py[m], px[m], :3]
    return img, zb


def hole_check(f, F, zb, win, ppm):
    """Per Revit opening: share of its pixels whose visible surface lies on the body plane (+-3 cm) in R1 v003.
    A hole (glazing or door set back, frames only) gives a low share; a solid wall gives about 1."""
    plane = {'S': F['plane'], 'N': -F['plane'], 'W': F['plane']}[f]
    sgn = -1 if f in 'NW' else 1
    out = []
    for o in F['openings']:
        r = o['rect']
        a, b = sorted((sgn * r[0], sgn * r[1]))
        x0, x1 = int((a - win[0]) * ppm) + 2, int((b - win[0]) * ppm) - 2
        y0, y1 = int((win[3] - r[3]) * ppm) + 2, int((win[3] - r[2]) * ppm) - 2
        sub = zb[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)]
        share = float(np.mean(np.abs(sub - plane) < 0.03)) if sub.size else None
        out.append({'opening': '%s %s' % (o['kind'], o['id']), 'rect': r, 'plane_share': share})
    return out


def lines_main(a):
    opts = {}
    for k in ('--zmin', '--zmax', '--ppm', '--check'):
        if k in a:
            i = a.index(k)
            opts[k] = a[i + 1]
            del a[i:i + 2]
    if len(a) != 5:
        raise SystemExit(__doc__)
    ll_p, npm_p, r1_p, tex_p, out_p = a
    ins = {os.path.abspath(p) for p in a[:4]}
    if os.path.abspath(out_p) in ins or (opts.get('--check') and os.path.abspath(opts['--check']) in ins):
        raise SystemExit('output aliases an input')
    zmin, zmax, ppm = float(opts.get('--zmin', -0.3)), float(opts.get('--zmax', 4.7)), float(opts.get('--ppm', 60))
    L = json.load(open(ll_p, encoding='utf-8'))
    Vn, fnn, fin, UV = load(npm_p)
    Vr, fnr, fir, _ = load(r1_p)
    off = Vr.min(0) - Vn.min(0)
    if np.abs((Vr.max(0) - Vn.max(0)) - off).max() > 0.002:
        raise SystemExit('NPM dump does not match R1 by bbox: %s vs %s' % (Vr.max(0) - Vn.max(0), off))
    Vn = Vn + off + R1_TO_REVIT
    Vr = Vr + R1_TO_REVIT
    Tn, Tr = tris(fnn, fin), tris(fnr, fir)
    tex = np.asarray(Image.open(tex_p).convert('RGB'))
    font = ImageFont.truetype(FONT, 15)
    small = ImageFont.truetype(FONT, 12)
    big = ImageFont.truetype(FONT, 20)
    panels, checks = [], {}
    zkept = [r['z'] for r in L['levels'] if r['kept']]
    titles = {'S': 'Фасад S (А-В, вид с юга)', 'N': 'Фасад N (В-А, вид с севера)', 'W': 'Фасад W (1-4, вид с запада)'}
    for f in ('S', 'N', 'W'):
        F = L['facades'][f]
        e = F['extent']
        sgn = (lambda u: -u) if f in 'NW' else (lambda u: u)
        a0, a1 = sorted((sgn(e[0]), sgn(e[1])))
        win = (a0 - 0.6, a1 + 0.6, zmin, zmax)
        rgb, _ = raster(f, Vn, Tn, UV, tex, win, ppm)
        img = Image.fromarray(rgb)
        _, zb = raster(f, Vr, Tr, None, None, (win[0], win[1], -0.3, 8.7), ppm)
        checks[f] = hole_check(f, F, zb, (win[0], win[1], -0.3, 8.7), ppm)
        dr = ImageDraw.Draw(img)

        def X(u):
            return (sgn(u) - win[0]) * ppm

        def Y(z):
            return (win[3] - z) * ppm
        for nb in F['not_body']:
            r = nb['rect']
            if r[2] > zmax:
                continue
            xs = sorted((X(r[0]), X(r[1])))
            for x in range(int(xs[0]), int(xs[1]), 8):
                dr.line([(x, Y(r[3])), (x + 4, Y(r[3]))], fill=(255, 210, 0), width=2)
                dr.line([(x, Y(max(r[2], zmin))), (x + 4, Y(max(r[2], zmin)))], fill=(255, 210, 0), width=2)
            for y in range(int(Y(r[3])), int(Y(max(r[2], zmin))), 8):
                dr.line([(xs[0], y), (xs[0], y + 4)], fill=(255, 210, 0), width=2)
                dr.line([(xs[1], y), (xs[1], y + 4)], fill=(255, 210, 0), width=2)
        for o in F['openings']:
            r = o['rect']
            if r[2] > zmax:
                continue
            xs = sorted((X(r[0]), X(r[1])))
            dr.rectangle([xs[0], Y(r[3]), xs[1], Y(r[2])], outline=(0, 200, 255), width=1)
        for z in zkept:
            if zmin <= z <= zmax:
                dr.line([(X(e[0]), Y(z)), (X(e[1]), Y(z))], fill=(230, 0, 0), width=2)
        for k, s in enumerate(r for r in F['stations'] if r['kept']):
            dr.line([(X(s['u']), Y(max(e[2], zmin))), (X(s['u']), Y(min(e[3], zmax)))], fill=(230, 0, 0), width=2)
        for m in F['moved']:
            x = X(m['from']) if m['edge'] in ('u0', 'u1') else None
            if x is not None:
                for y in range(int(Y(min(e[3], zmax))), int(Y(max(e[2], zmin))), 10):
                    dr.line([(x, y), (x, y + 5)], fill=(255, 120, 0), width=3)
        # margins with labels
        pad_l, pad_b, pad_t = 70, 82, 34
        W = max(img.width + pad_l + 20, 1250)
        canvas = Image.new('RGB', (W, img.height + pad_b + pad_t), 'white')
        canvas.paste(img, (pad_l, pad_t))
        dc = ImageDraw.Draw(canvas)
        nk = sum(r['kept'] for r in F['stations'])
        dc.text((pad_l, 6), '%s: %d станций (вертикали), %d уровней общих для W/S/N; окно z %.1f…%.1f м'
                % (titles[f], nk, len(zkept), zmin, zmax), fill='black', font=big)
        for z in zkept:
            if zmin <= z <= zmax:
                dc.text((4, pad_t + Y(z) - 8), '%.3f' % z, fill=(200, 0, 0), font=font)
        for k, s in enumerate(r for r in F['stations'] if r['kept']):
            dc.text((pad_l + X(s['u']) - 18, pad_t + img.height + 4 + 18 * (k % 3)), '%.3f' % s['u'],
                    fill=(200, 0, 0), font=small)
        us = [r['u'] for r in F['stations'] if r['kept']]
        narrow = ['%.3f–%.3f (%.0f см)' % (a, b, (b - a) * 100) for a, b in zip(us, us[1:]) if b - a < 0.3]
        dc.text((pad_l, pad_t + img.height + 60), 'Узкие полосы между станциями < 30 см: ' + ('; '.join(narrow) or 'нет'),
                fill=(160, 0, 160), font=font)
        for m in F['moved']:
            dc.text((pad_l + X(m['from']) + 4, pad_t + 4), 'сдвиг %s %+.0f мм' % (m['opening'].split()[0],
                    m['delta_m'] * 1000), fill=(255, 120, 0), font=font)
        panels.append(canvas)
    W = max(p.width for p in panels)
    head = 175
    sheet = Image.new('RGB', (W, head + sum(p.height for p in panels)), 'white')
    ds = ImageDraw.Draw(sheet)
    s = L['summary']
    lines = [
        'KPP1 — линии решётки тела (1-й этаж) из списка проёмов и зон Revit, до сборки (#1609, метод решётки BM-00)',
        'Под линиями — R1 v003 (одобренная геометрия) с текстурой НПМ, прямые фасады. Линии НЕ из вершин R1.',
        'Красное = линия решётки: уровни 0 / цоколь 0,9 / низ-верх проёмов / границы отделки 2,7 и 7,1 (стык стен Revit 8,1 внутри одной отделки — убран); станции: углы и края проёмов.',
        'Голубое = проём Revit (рама витража / дверь). Оранжевый пунктир = край проёма сдвинут снапом 10 см (%d шт., макс. %.0f мм).'
        % (s['moved_edges'], s['max_move_m'] * 1000),
        'Жёлтые точки = не тело: порталы, козырьки, облицовка входов, решётки — отдельные врезанные элементы [D336] / текстура.',
        'Правило: линия остаётся, если класс ячейки меняется по ней на >= 1,5 м или >= ширины проёма; ближе 10 см — одна линия.',
    ]
    nop = sum(len(v) for v in checks.values())
    nh = sum(1 for v in checks.values() for c in v if c['plane_share'] is not None and c['plane_share'] <= 0.1)
    lines.append('Проверка списка по R1 v003: %d из %d проёмов Revit — дыры в R1 (доля стены в проёме <= 10 %%); '
                 'стойки на углах — отдельные элементы [D336], стена до угла.' % (nh, nop))
    for i, t in enumerate(lines):
        ds.text((12, 8 + 23 * i), t, fill='black', font=ImageFont.truetype(FONT, 17))
    y = head
    for p in panels:
        sheet.paste(p, (0, y))
        y += p.height
    tmp = out_p + '.partial.png'
    sheet.save(tmp)
    os.replace(tmp, out_p)
    if opts.get('--check'):
        json.dump({'offset_npm_to_r1': off.tolist(), 'holes': checks}, open(opts['--check'], 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    bad = [(f, c['opening'], round(c['plane_share'], 2)) for f in checks for c in checks[f]
           if c['plane_share'] is None or c['plane_share'] > 0.5]
    print('sheet', out_p, sheet.size, 'openings solid in R1 (plane share > 0.5):', bad)


# ---- step 2: lattice sheet ----
SIDE_RU = {'S': 'Фасад S (вид с юга)', 'E': 'Фасад E (вид с востока)', 'N': 'Фасад N (вид с севера)',
           'W': 'Фасад W (вид с запада)'}


def panel(lat, verts, fn, fi, chk, s0, s1, z0, z1, ppm, font):
    segs, perim = lc.ring_frame(lat)
    S, D, K = lc.place(np.asarray(verts, float), segs, perim)
    W, H = int((s1 - s0) * ppm) + 1, int((z1 - z0) * ppm) + 1
    padl, padt, padb = 60, 34, 22
    img = Image.new('RGB', (W + padl + 10, H + padt + padb), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')

    def X(s):
        return padl + (s - s0) * ppm

    def Y(z):
        return padt + (z1 - z) * ppm
    starts = np.concatenate([[0], np.cumsum(fn)[:-1]])
    polys = []
    for a, n in zip(starts, fn):
        f = fi[a:a + n]
        v = verts[f]
        if (np.abs(D[f]) > lc.BAND).any() or v[:, 2].max() < z0 - 1e-3 or v[:, 2].min() > z1 + 1e-3:
            continue
        e1, e2 = v[1] - v[0], v[2] - v[0]
        nrm = np.cross(e1, e2)
        if np.linalg.norm(nrm) < 1e-12 or abs(nrm[2]) / np.linalg.norm(nrm) > 0.1:
            continue
        ss = S[f].copy()
        if ss.max() - ss.min() > perim / 2:
            ss = np.where(ss < perim / 2, ss + perim, ss)
        if ss.max() < s0 or ss.min() > s1:
            continue
        polys.append((float(D[f].mean()), [(X(s), Y(z)) for s, z in zip(ss, v[:, 2])]))
    for d, pts in sorted(polys, key=lambda p: -p[0]):  # deeper first
        g = int(max(120, 232 - 120 * max(0.0, d)))
        dr.polygon(pts, fill=(g, g, g + 8), outline=(40, 40, 40))
    St = list(lat['stations_s']) + [perim]
    Z = lat['levels']
    for c in chk['cells']:
        if any(c[k] for k in ('tri', 'ngon', 'diagonal', 't_vertex', 'non_manifold')):
            a, b = St[c['i']], St[c['i'] + 1]
            za, zb = Z[c['j']], Z[c['j'] + 1]
            if b < s0 or a > s1 or zb < z0 or za > z1:
                continue
            dr.rectangle([X(max(a, s0)), Y(min(zb, z1)), X(min(b, s1)), Y(max(za, z0))], fill=(255, 0, 0, 60),
                         outline=(220, 0, 0, 255), width=2)
    for lv in chk['levels']:
        z = lv['z']
        if not z0 - 1e-6 <= z <= z1 + 1e-6:
            continue
        col = (0, 160, 0) if lv['closed'] else (230, 0, 0)
        dr.text((4, Y(z) - 7), '%.3f' % z, fill=col, font=font)
        dr.line([X(s0) - 8, Y(z), X(s0) - 1, Y(z)], fill=col, width=3)
        for a, b in lv['gaps_s']:
            if b >= s0 and a <= s1:
                dr.line([X(max(a, s0)), Y(z), X(min(b, s1)), Y(z)], fill=(255, 0, 0, 150), width=2)
    for st in chk['stations']:
        s = st['s']
        if not s0 - 1e-6 <= s <= s1 + 1e-6:
            continue
        col = (0, 160, 0) if st['through'] else (230, 0, 0)
        dr.line([X(s), padt - 8, X(s), padt - 1], fill=col, width=3)
        for a, b in st['gaps_z']:
            if b >= z0 and a <= z1:
                dr.line([X(s), Y(min(b, z1)), X(s), Y(max(a, z0))], fill=(255, 0, 0, 150), width=2)
    for k, f in enumerate(lat['sides']):
        c0 = lat['corners_s'][k]
        c1 = lat['corners_s'][k + 1] if k + 1 < len(lat['sides']) else perim
        if c1 >= s0 and c0 <= s1:
            dr.line([X(max(c0, s0)), padt - 30, X(max(c0, s0)), padt + H], fill=(0, 90, 255), width=2)
            dr.text((X(max(c0, s0)) + 4, padt - 30), SIDE_RU[f], fill=(0, 60, 200), font=font)
    return img


def lattice_main(argv):
    a = list(argv)

    def opt(k, n, d):
        if k in a:
            i = a.index(k)
            v = a[i + 1:i + 1 + n]
            del a[i:i + 1 + n]
            return v
        return d
    models = []
    while '--model' in a:
        i = a.index('--model')
        models.append(a[i + 1:i + 4])
        del a[i:i + 4]
    z0, z1 = (float(x) for x in opt('--z', 2, ['nan', 'nan']))
    sr = opt('--s', 2, None)
    ppm = float(opt('--ppm', 1, ['24'])[0])
    title = opt('--title', 1, [''])[0]
    if len(a) != 2 or not models:
        raise SystemExit(__doc__)
    latp, out = a
    ins = [latp] + [p for m in models for p in m[1:]]
    tmp = out + '.partial.png'
    if any(os.path.abspath(out) == os.path.abspath(p) or os.path.abspath(tmp) == os.path.abspath(p) for p in ins):
        raise SystemExit('output aliases input: %s' % out)
    lat = json.load(open(latp, encoding='utf-8'))
    if z0 != z0:
        z0, z1 = lat['levels'][0], lat['levels'][-1]
    s0, s1 = (0.0, lat['perimeter']) if sr is None else (float(sr[0]), float(sr[1]))
    font = ImageFont.truetype(FONT, 13)
    big = ImageFont.truetype(FONT, 18)
    tiles = []
    for label, npz, cj in models:
        m = np.load(npz)
        chk = json.load(open(cj, encoding='utf-8'))
        sm = chk['summary']
        img = panel(lat, m['verts'], m['fn'], m['fi'], chk, s0, s1, z0, z1, ppm, font)
        head = ('%s: граней %d (квадов %d, треуг. %d); диагоналей %d, T-вершин %d, неманиф. %d; кольца замкнуты %d/%d; '
                'станции насквозь %d/%d; ячеек с дефектом %d/%d (%.1f %%)'
                % (label, sm['faces'], sm['quads'], sm['tris'], sm['diagonal_edges'], sm['t_vertices'],
                   sm['non_manifold_edges'], sm['levels_closed'], sm['levels'], sm['stations_through'],
                   sm['stations'], sm['cells_with_defects'], sm['cells_with_faces'], 100 * sm['cells_defect_share']))
        tiles.append((head, img))
    legend = ('Развёртка по кольцу оболочки: прямые фасады S | E | N | W подряд, углы — синие линии. '
              'Зелёный уровень/станция слева и сверху = кольцо/петля замкнуты по всему периметру; красный отрезок = '
              'разрыв. Красные ячейки = локальный сигнал (треугольник, n-гон, диагональ, T-вершина, неманифолд в '
              'ячейке решётки). Серый темнее = глубже (откосы, ниши).')
    W = max(t[1].width for t in tiles) + 20
    Ht = sum(t[1].height + 30 for t in tiles) + 70
    sheet = Image.new('RGB', (W, Ht), 'white')
    dr = ImageDraw.Draw(sheet)
    dr.text((10, 8), title, fill='black', font=big)
    dr.text((10, 34), legend, fill=(60, 60, 60), font=font)
    y = 60
    for head, img in tiles:
        dr.text((10, y), head, fill='black', font=font)
        sheet.paste(img, (10, y + 18))
        y += img.height + 30
    sheet.save(tmp, 'PNG')
    os.replace(tmp, out)
    print('SHEET', out, sheet.size)


# ---- step 3 / package: composed render sheet ----
CAMS = ['sw_from_sw', 'sw_from_s', 'nw_from_nw', 'nw_from_n', 'se_from_se', 'se_from_s', 'ne_from_ne', 'ne_from_n']
COLS = [('before', 'wire', 'ДО: quad-v003 (сетка)'), ('after', 'wire', 'ПОСЛЕ: решётка v004 + стойки (голубые)'),
        ('before', 'tex', 'ДО: quad-v003 (текстура)'), ('after', 'tex', 'ПОСЛЕ: UDIM по отделкам')]
ELEV = ['elev_W', 'elev_S', 'elev_N', 'elev_E']   # package step: straight-on facades (kpp1_assemble.py render elevations)
SW, SH, SHEAD = 640, 430, 28


def compose_main(render_dir, out, which, title):
    out = Path(out)
    if out.exists():
        raise SystemExit(f'refused: {out} exists')
    if which not in ('corners', 'ground', 'elevations'):
        raise SystemExit(f'unknown set {which!r}')
    cams = (CAMS if which == 'corners' else ELEV if which == 'elevations' else [c + '_ground' for c in CAMS])
    paths = {(c, t, m): Path(render_dir) / f'{t}_{c}_{m}.png' for c in cams for t, m, _ in COLS}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise SystemExit(f'missing renders: {missing[:3]}')
    sheet = Image.new('RGB', (SW * len(COLS), SHEAD * 2 + SH * len(cams)), 'white')
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 18)
    d.text((8, 6), title, fill='black', font=font)
    for i, (_, _, label) in enumerate(COLS):
        d.text((i * SW + 8, SHEAD + 6), label, fill='black', font=font)
    for r, c in enumerate(cams):
        for i, (t, m, _) in enumerate(COLS):
            im = Image.open(paths[(c, t, m)]).convert('RGB').resize((SW, SH))
            sheet.paste(im, (i * SW, SHEAD * 2 + r * SH))
        d.text((6, SHEAD * 2 + r * SH + 6), c, fill='yellow', font=font)
    sheet.save(out)
    print('SHEET', out, sheet.size)


def compose_cli(a):
    if len(a) != 4:
        raise SystemExit(__doc__)
    compose_main(*a)


COMMANDS = {'lines': lines_main, 'lattice': lattice_main, 'compose': compose_cli}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2:])
