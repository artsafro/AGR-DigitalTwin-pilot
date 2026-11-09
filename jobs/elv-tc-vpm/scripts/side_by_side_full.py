"""elv-tc-vpm: booklet render (sheet N) next to our render from a similar camera (one PNG).

uv run --no-project --with pymupdf --with pillow python side_by_side_full.py <booklet.pdf> <sheet> <ours.png> <out.png> <label>
The booklet page is rendered at 110 dpi and cropped to the picture frame (86, 108)-(1776, 1058) px.
"""
import sys, os
import pymupdf
from PIL import Image, ImageDraw, ImageFont

pdf, sheet, ours, out, label = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
pix = pymupdf.open(pdf)[sheet - 1].get_pixmap(dpi=110)
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
d.text((10, 15), f"Буклет АГР, лист {sheet} (рендер, ориентир)", fill=(0, 0, 0), font=f)
d.text((W + 40, 15), label, fill=(0, 0, 0), font=f)
canvas.save(out)
print("SAVED", out, canvas.size)
