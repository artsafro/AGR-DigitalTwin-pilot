"""elv-tc-vpm: booklet lighting sheet (36-39, top-row renders) above our night renders from similar cameras (one PNG).

uv run --no-project --with pymupdf --with pillow python side_by_side_night.py <booklet.pdf> <sheet> <out.png> <ours1.png> [...]
The page is rendered at 110 dpi; the three picture slots of the top row (same layout on sheets 36-39) are cropped;
our renders are placed under their slots in the given order.
"""
import sys, os
import pymupdf
from PIL import Image, ImageDraw, ImageFont

pdf, sheet, out, ours = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4:]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
pix = pymupdf.open(pdf)[sheet - 1].get_pixmap(dpi=110)
page = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
SLOTS = [(88, 179, 638, 509), (652, 179, 1199, 509), (1215, 179, 1762, 509)][:len(ours)]
W, H = 550, 330
canvas = Image.new("RGB", (len(SLOTS) * (W + 20) + 10, 2 * H + 110), (255, 255, 255))
d = ImageDraw.Draw(canvas)
try:
    f = ImageFont.truetype("arial.ttf", 20)
except OSError:
    f = ImageFont.load_default()
d.text((10, 8), f"Сверху: буклет АГР, лист {sheet} (светотехнический расчёт, ориентир). Снизу: VPM v004 ночь, Eevee "
       "(свечение ERM R + render-only лампы)", fill=(0, 0, 0), font=f)
for i, (box, p) in enumerate(zip(SLOTS, ours)):
    x = 10 + i * (W + 20)
    canvas.paste(page.crop(box).resize((W, H)), (x, 40))
    im = Image.open(p).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)))
    l, t = (im.width - W) // 2, (im.height - H) // 2
    canvas.paste(im.crop((l, t, l + W, t + H)), (x, 60 + H))
    d.text((x, 62 + 2 * H + 10), os.path.basename(p), fill=(0, 0, 0), font=f)
canvas.save(out)
print("SAVED", out, canvas.size)
