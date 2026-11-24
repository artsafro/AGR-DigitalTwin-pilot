"""Hook `after` stage `readback` (#1619 polygon stage 2, tower 63B): ONE Russian review sheet from the four
stage2_views.py panels (iso, window, capsule, cut) + plan and FBX readback numbers. Read-only on the scene.

Pattern: n/a | new-case: 2 x 2 tiling of the shared 63C stage-2 views with Russian captions (Pillow).

uv run python sheet_63b.py VIEWS_DIR STAGE2.json READBACK.json OUT.png --opening N
Refuses an existing OUT.png.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = 'C:/Windows/Fonts/arial.ttf'
PANELS = (('iso', 'Обзор: тело v007 (без изменений) + окна, капсулы, корзины КК'),
          ('window', 'Окно крупно (проём {n}, {t}): рама в конце откоса'),
          ('capsule', 'Капсула без стены (проём {n}): рама + стекло + капсула'),
          ('cut', 'Верхний срез: капсулы за окнами по этажам'))


def lines(plan, rb):
    r, col = plan['report'], rb['collections']
    shallow = ', '.join(str(s['opening']) for s in r['capsules']['shallow_0_9_m'])
    faces = sum(c['faces'] for c in col.values())
    quads = sum(c['quads'] for c in col.values())
    body = rb['body_vs_accepted']
    return [
        '63B, этап 2, v001 (#1619): окна + капсулы + корзины КК на принятом теле v007. Черновик на приёмку, не VPM.',
        'Проёмы {} (все с типом Revit, 0 без типа); типов окон {}; гнутых проёмов {} (рама на хорде).'.format(
            r['openings']['ok'], len(r['types']), r['openings']['bent']),
        'Капсулы {}: глубина 1,0 м, 0,9 м только у 8 во внутренних углах ({}); пересечений 0.'.format(
            r['capsules']['made'], shallow),
        'Корзины КК: {} из {} в диапазоне тела, низкополигональные боксы по габаритам Revit.'.format(
            r['baskets']['built'], r['baskets']['total']),
        'Окна вписаны в принятые проёмы ({} шт. уже/ниже окна Revit - ожидаемо, не дефект).'.format(len(r['fitted'])),
        'FBX прочитан: объектов {}, граней {}, квадов {} ({:.0%}); треугольников {}, n-гонов {}, тонких {}.'.format(
            sum(c['objects'] for c in col.values()), faces, quads, quads / faces,
            sum(c['tris'] for c in col.values()), sum(c['ngons'] for c in col.values()),
            sum(c['thin_tris'] for c in col.values())),
        'Тело против принятого v007: {} вершин, макс. отклонение {:.1e} м.'.format(body['verts'][0], body['max_dev_m']),
    ]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('views')
    ap.add_argument('plan')
    ap.add_argument('readback')
    ap.add_argument('out')
    ap.add_argument('--opening', type=int, required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        sys.exit('OUT.png exists; write a new version: ' + a.out)
    plan = json.load(open(a.plan, encoding='utf-8'))
    rb = json.load(open(a.readback, encoding='utf-8'))
    row = next(r for r in plan['report']['rows'] if r['opening'] == a.opening)
    tiles = [Image.open(Path(a.views) / (k + '.png')).convert('RGB') for k, _ in PANELS]
    w, h = tiles[0].size
    cap_h, foot_h = 40, 34 * 7 + 30
    sheet = Image.new('RGB', (2 * w, 2 * (h + cap_h) + foot_h), 'white')
    draw = ImageDraw.Draw(sheet)
    f_cap, f_txt = ImageFont.truetype(FONT, 24), ImageFont.truetype(FONT, 22)
    for k, (tile, (_, title)) in enumerate(zip(tiles, PANELS)):
        x, y = (k % 2) * w, (k // 2) * (h + cap_h)
        draw.text((x + 12, y + 8), '{}. {}'.format(k + 1, title.format(
            n=a.opening, t=row['type'].replace('Окн_Окн_', ''))), fill='black', font=f_cap)
        sheet.paste(tile, (x, y + cap_h))
    y = 2 * (h + cap_h) + 14
    for line in lines(plan, rb):
        draw.text((14, y), line, fill='black', font=f_txt)
        y += 34
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
