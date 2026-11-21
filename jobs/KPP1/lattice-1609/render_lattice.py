"""KPP1 lattice body sheet: unrolled straight elevations S | E | N | W with ring continuity and the local-signal map.

Pattern: new-case | new-case: acceptance sheet of a ring lattice body - the four straight-on facades unrolled
along the envelope ring (so a ring that dies at a corner shows), rings/stations marked closed or broken, lattice
cells with defects highlighted (Artem 2026-11-21: ring continuity; decision 5: local-signal map next to the wire).

uv run python render_lattice.py LATTICE.json OUT.png --model LABEL MESH.npz CHECK.json [--model ...]
       [--z 0 8.65] [--s 0 78.64] [--ppm 24] [--title TEXT]
MESH.npz = dump_mesh.py output, CHECK.json = lattice_check.py output for the same mesh and lattice. Read-only;
OUT.png must not alias an input; written via OUT.png.partial.png.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lattice_check as lc  # noqa: E402

FONT = 'C:/Windows/Fonts/arial.ttf'
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


def main(argv):
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


if __name__ == '__main__':
    main(sys.argv[1:])
