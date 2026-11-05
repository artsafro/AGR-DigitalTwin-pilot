"""Contact sheet of extracted board images, or a crop of one image.
Usage: py -3 -I pur_contact_sheet_v001.py sheet <dir> <out.png>
       py -3 -I pur_contact_sheet_v001.py crop <img> <x0> <y0> <x1> <y1> <out.png>   (original pixel coords)"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

if sys.argv[1] == "crop":
    im = Image.open(sys.argv[2])
    x0, y0, x1, y1 = map(int, sys.argv[3:7])
    im.crop((x0, y0, x1, y1)).save(sys.argv[7])
else:
    d = Path(sys.argv[2])
    files = sorted(p for p in d.glob("img_*.*") if p.suffix.lower() in (".png", ".jpg"))
    cw, ch, cols, lab = 800, 400, 3, 28
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (ch + lab)), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    for k, p in enumerate(files):
        im = Image.open(p).convert("RGB")
        w, h = im.size
        im.thumbnail((cw - 10, ch - 10))
        x, y = (k % cols) * cw, (k // cols) * (ch + lab)
        sheet.paste(im, (x + (cw - im.width) // 2, y + lab + (ch - im.height) // 2))
        dr.text((x + 8, y + 6), f"{p.name}  {w}x{h}", fill=(255, 255, 255))
    sheet.save(sys.argv[3])
    print(len(files), sheet.size)
