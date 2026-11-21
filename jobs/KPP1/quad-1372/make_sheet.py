"""new-case: compose the #1372 Before/After sheet from render_before_after.py outputs (same cameras, rows).

    uv run python jobs/KPP1/quad-1372/make_sheet.py <render_dir> <out.png> <mode: tex|wire|both> [default|corners]

Rows = cameras, columns = Before (R1) | After (quad master). A missing render is an error naming it; an existing
output fails (never overwrite).
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SETS = {  # camera rows and column labels per camera set of render_before_after.py
    'default': (['overview_se', 'overview_nw', 'north_window_x0p3', 'north_panel_x12p6', 'east_step_x12p42'],
                'BEFORE: R1 master r1-v002 (triangles)',
                'AFTER: quad master v002 (union of R1 overlaps <= 5 mm, 100 % quads)'),
    'corners': (['sw_from_sw', 'sw_from_s', 'nw_from_nw', 'nw_from_n'],  # #1563 SW / NW posts
                'BEFORE: quad master v002 (from r1-v002)',
                'AFTER: quad master v003 (from r1-v003 #1246)'),
    'corners-v004': (['sw_from_sw', 'sw_from_s', 'nw_from_nw', 'nw_from_n'],  # #1609 option A (D357)
                     'BEFORE: quad master v003 (rejected corners)',
                     'AFTER: v004 draft: W/S/N planes rebuilt whole, posts separate'),
    'ground-v004': ([f'{c}_ground' for c in ('sw_from_sw', 'sw_from_s', 'nw_from_nw', 'nw_from_n')],  # #1609 w13
                    'BEFORE: quad master v003', 'AFTER: v004 w16: walls + reveals one conforming body, posts separate'),
    'elevations-v004': (['elev_W', 'elev_S', 'elev_N'],  # #1609: straight-on orthographic elevation per facade
                        'BEFORE: quad master v003', 'AFTER: v004 w16', 'stacked'),
}


def main(src, out, mode, cams='default'):
    if cams not in SETS:
        raise SystemExit(f'unknown camera set {cams!r}')
    CAMS, left, right, *layout = SETS[cams]
    stacked = layout == ['stacked']   # elevations: before above after, full width
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
    if stacked:
        w, h = Image.open(paths[(rows[0][0], rows[0][1], 'before')]).size
        sheet = Image.new('RGB', (w, len(rows) * 2 * (h + head)), 'white')
        d = ImageDraw.Draw(sheet)
        for i, (c, m) in enumerate(rows):
            for j, (t, lab) in enumerate((('before', left), ('after', right))):
                y = (2 * i + j) * (h + head)
                d.text((10, y + 8), f'{c} / {m} - {lab}', fill='black')
                sheet.paste(Image.open(paths[(c, m, t)]).convert('RGB').resize((w, h)), (0, y + head))
        sheet.save(out)
        print('SHEET', out, sheet.size)
        return
    sheet = Image.new('RGB', (2 * w, head + len(rows) * (h + head)), 'white')
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), left, fill='black')
    d.text((w + 10, 8), right, fill='black')
    for i, (c, m) in enumerate(rows):
        y = head + i * (h + head)
        d.text((10, y + 8), f'{c} / {m}', fill='black')
        for j, t in enumerate(('before', 'after')):
            sheet.paste(Image.open(paths[(c, m, t)]).convert('RGB').resize((w, h)), (j * w, y + head))
    sheet.save(out)
    print('SHEET', out, sheet.size)


if __name__ == '__main__':
    main(*sys.argv[1:5])
