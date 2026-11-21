"""One-page gate-1 sheet for #1619. new-case: compose the floor pick list (pictures + captions) for Artem.

python gate1_sheet.py TILES.json OUT.png
TILES.json: {"title": str, "tiles": [{"img": [path, ...], "caption": [line, ...]}, ...]}; 3 columns.
Refuses an output that resolves to any input picture.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

spec_path, out = sys.argv[1:3]
spec = json.load(open(spec_path, encoding="utf-8"))
ins = {os.path.realpath(p) for t in spec["tiles"] for p in t["img"]} | {os.path.realpath(spec_path)}
if os.path.realpath(out) in ins:
    sys.exit("output resolves to an input")
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 30)
cols, tw, ih, cap = 3, 760, 560, 230
rows = (len(spec["tiles"]) + cols - 1) // cols
W = Image.new("RGB", (cols * tw, 70 + rows * (ih + cap)), "white")
d = ImageDraw.Draw(W)
d.text((20, 18), spec["title"], font=bold, fill="black")
for k, t in enumerate(spec["tiles"]):
    x, y = (k % cols) * tw, 70 + (k // cols) * (ih + cap)
    n = len(t["img"])
    for j, p in enumerate(t["img"]):
        im = Image.open(p).convert("RGB")
        im.thumbnail(((tw - 20) // n, ih - 10))
        W.paste(im, (x + 10 + j * ((tw - 20) // n), y + 5))
    for j, line in enumerate(t["caption"]):
        d.text((x + 12, y + ih + 4 + j * 28 + (8 if j else 0)), line, font=bold if j == 0 else font, fill="black")
    d.rectangle([x + 2, y, x + tw - 2, y + ih + cap - 4], outline=(160, 160, 160), width=2)
W.save(out)
print(out, W.size)
