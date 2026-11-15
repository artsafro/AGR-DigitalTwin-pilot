"""new-case: compose the #1372 Before/After sheet from render_before_after.py outputs (same cameras, rows).

    uv run python jobs/KPP1/quad-1372/make_sheet.py <render_dir> <out.png> <mode: tex|wire|both>

Rows = cameras, columns = Before (R1) | After (quad master). A missing render is an error naming it; an existing
output fails (never overwrite).
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

CAMS = ['overview_se', 'overview_nw', 'north_window_x0p3', 'north_panel_x12p6', 'east_step_x12p42']


def main(src, out, mode):
    src, out = Path(src), Path(out)
    if out.exists():
        raise SystemExit(f'{out} exists; use a new name')
    modes = ['tex', 'wire'] if mode == 'both' else [mode]
    rows = [(c, m) for c in CAMS for m in modes]
    paths = {(c, m, t): src / f'{t}_{c}_{m}.png' for c, m in rows for t in ('before', 'after')}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise SystemExit(f'missing renders: {missing}')
    w, h = 640, 430
    head = 28
    sheet = Image.new('RGB', (2 * w, head + len(rows) * (h + head)), 'white')
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), 'BEFORE: R1 master r1-v002 (triangles)', fill='black')
    d.text((w + 10, 8), 'AFTER: quad master v002 (union of R1 overlaps <= 5 mm, 100 % quads)', fill='black')
    for i, (c, m) in enumerate(rows):
        y = head + i * (h + head)
        d.text((10, y + 8), f'{c} / {m}', fill='black')
        for j, t in enumerate(('before', 'after')):
            sheet.paste(Image.open(paths[(c, m, t)]).convert('RGB').resize((w, h)), (j * w, y + head))
    sheet.save(out)
    print('SHEET', out, sheet.size)


if __name__ == '__main__':
    main(*sys.argv[1:4])
