"""KPP1 lattice step 3 sheet (#1609): before (quad-v003) / after (v004 lattice draft) per camera, wire + tex.

Pattern: n/a | new-case: compose the step-3 corner / ground-floor sheet from render_v004.py outputs.

    uv run python jobs/KPP1/lattice-1609/sheet_v004.py RENDER_DIR OUT.png corners|ground TITLE

Rows = cameras (corner set or the same cameras on the ground floor), columns = v003 wire | v004 wire | v003 tex |
v004 tex. A missing render is an error naming it; an existing OUT fails (never overwrite).
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = 'C:/Windows/Fonts/arial.ttf'   # Cyrillic labels; the PIL default bitmap font has no Cyrillic

CAMS = ['sw_from_sw', 'sw_from_s', 'nw_from_nw', 'nw_from_n', 'se_from_se', 'se_from_s', 'ne_from_ne', 'ne_from_n']
COLS = [('before', 'wire', 'ДО: quad-v003 (сетка)'), ('after', 'wire', 'ПОСЛЕ: решётка v004 + стойки (голубые)'),
        ('before', 'tex', 'ДО: quad-v003 (текстура)'), ('after', 'tex', 'ПОСЛЕ: UDIM по отделкам')]
W, H, HEAD = 640, 430, 28


def main(render_dir, out, which, title):
    out = Path(out)
    if out.exists():
        raise SystemExit(f'refused: {out} exists')
    if which not in ('corners', 'ground'):
        raise SystemExit(f'unknown set {which!r}')
    cams = CAMS if which == 'corners' else [c + '_ground' for c in CAMS]
    paths = {(c, t, m): Path(render_dir) / f'{t}_{c}_{m}.png' for c in cams for t, m, _ in COLS}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise SystemExit(f'missing renders: {missing[:3]}')
    sheet = Image.new('RGB', (W * len(COLS), HEAD * 2 + H * len(cams)), 'white')
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 18)
    d.text((8, 6), title, fill='black', font=font)
    for i, (_, _, label) in enumerate(COLS):
        d.text((i * W + 8, HEAD + 6), label, fill='black', font=font)
    for r, c in enumerate(cams):
        for i, (t, m, _) in enumerate(COLS):
            im = Image.open(paths[(c, t, m)]).convert('RGB').resize((W, H))
            sheet.paste(im, (i * W, HEAD * 2 + r * H))
        d.text((6, HEAD * 2 + r * H + 6), c, fill='yellow', font=font)
    sheet.save(out)
    print('SHEET', out, sheet.size)


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) != 4:
        raise SystemExit(__doc__)
    main(*a)
