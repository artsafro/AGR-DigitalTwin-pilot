"""elv-tc-vpm: legend picture of the material IDs (flat RAL colours used in the Workbench renders).

uv run --no-project --with pillow python id_legend.py <out.png>
"""
import sys, os, re
from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_full_v003.py"), encoding="utf-8").read()
slots = dict((int(a), b) for a, b in re.findall(r'(\d+): "(ID\d\d_[^"]+)"', src))
cols = dict((int(a), b) for a, b in re.findall(r'(\d+): "(#[0-9A-F]{6})"', src[src.index("COL = {"):]))
f = ImageFont.truetype("arial.ttf", 26)
img = Image.new("RGB", (900, 60 + 40 * len(slots)), (255, 255, 255))
d = ImageDraw.Draw(img)
d.text((20, 15), "SM_Elevatornaya_1A_Main: material ID -> flat colour (build-v003)", fill=(0, 0, 0), font=f)
for k, (i, n) in enumerate(sorted(slots.items())):
    y = 60 + 40 * k
    c = cols.get(i)
    d.rectangle((20, y, 90, y + 30), fill=c or "#FFFFFF", outline=(0, 0, 0))
    d.text((110, y), n + ("" if c else "  (unused)"), fill=(0, 0, 0), font=f)
img.save(out)
print("SAVED", out)
