"""Contact sheet of the guide screenshots (needs Pillow: `uv run --with pillow python ...`).

    python test-polygon/build/guide_sheet.py <guide out dir> [--cols 3] [--width 640]

Reads <dir>/shots.json (written by guide_inside.py), writes <dir>/contact_sheet.jpg and
<dir>/SHA256SUMS.txt over every PNG/JPG in the folder. Refuses an empty shot list.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size):
    for name in ('arial.ttf', 'segoeui.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('folder', type=Path)
    ap.add_argument('--cols', type=int, default=3)
    ap.add_argument('--width', type=int, default=640)
    a = ap.parse_args(argv)
    shots = json.loads((a.folder / 'shots.json').read_text(encoding='utf-8'))
    if not shots:
        sys.exit('no screenshots in ' + str(a.folder))
    font = _font(16)
    tiles = []
    for index, shot in enumerate(shots, 1):
        img = Image.open(a.folder / shot['file']).convert('RGB')
        img = img.resize((a.width, int(img.height * a.width / img.width)))
        tile = Image.new('RGB', (a.width, img.height + 48), 'white')
        tile.paste(img, (0, 48))
        ImageDraw.Draw(tile).text((6, 4), '{}. {}'.format(index, shot['caption'])[:150], fill='black', font=font)
        tiles.append(tile)
    rows = (len(tiles) + a.cols - 1) // a.cols
    cell_h = max(t.height for t in tiles)
    sheet = Image.new('RGB', (a.cols * (a.width + 8), rows * (cell_h + 8)), (230, 230, 230))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % a.cols) * (a.width + 8), (index // a.cols) * (cell_h + 8)))
    target = a.folder / 'contact_sheet.jpg'
    sheet.save(target, quality=82)
    sums = []
    for path in sorted(a.folder.iterdir()):
        if path.suffix.lower() in ('.png', '.jpg'):
            sums.append('{}  {}'.format(hashlib.sha256(path.read_bytes()).hexdigest(), path.name))
    (a.folder / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n', encoding='utf-8')
    print(json.dumps({'sheet': str(target), 'tiles': len(tiles), 'size': sheet.size}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
