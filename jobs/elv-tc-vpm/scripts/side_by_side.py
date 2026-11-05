"""elv-tc-vpm: booklet sheet 14 render crop vs our render from a similar camera (one PNG).

uv run --no-project --with pymupdf --with pillow python side_by_side.py <booklet.pdf> <our_booklet.png> <out.png> [right label]
The booklet page is rendered at 110 dpi and cropped to the picture frame (86, 108)-(1776, 1058) px.
"""
import sys, os
import pymupdf
from PIL import Image, ImageDraw, ImageFont

pdf, ours, out = sys.argv[1:4]
label = sys.argv[4] if len(sys.argv) > 4 else "Пилот И-А build-v001 (геометрия, плоские цвета RAL, Workbench)"
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
pix = pymupdf.open(pdf)[13].get_pixmap(dpi=110)
page = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
crop = page.crop((86, 108, 1776, 1058))
mine = Image.open(ours).convert("RGB").resize(crop.size)
W, H = crop.size
canvas = Image.new("RGB", (W * 2 + 30, H + 60), (255, 255, 255))
canvas.paste(crop, (0, 60))
canvas.paste(mine, (W + 30, 60))
d = ImageDraw.Draw(canvas)
try:
    f = ImageFont.truetype("arial.ttf", 26)
except OSError:
    f = ImageFont.load_default()
d.text((10, 15), "Буклет АГР, лист 14 «Визуализация. Вид 1» (рендер, ориентир)", fill=(0, 0, 0), font=f)
d.text((W + 40, 15), label, fill=(0, 0, 0), font=f)
canvas.save(out)
print("SAVED", out, canvas.size)
