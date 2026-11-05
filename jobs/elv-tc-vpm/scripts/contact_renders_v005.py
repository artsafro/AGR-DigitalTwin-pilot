"""elv-tc-vpm renders-v005 contact sheet (render_closeups_v005.py output): before (delivery v004) | after (delivery v005)
pairs, 2 columns, labelled. uv run --no-project --with pillow python contact_renders_v005.py <renders_dir> <out.png>"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

d, out = sys.argv[1:3]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
ROWS = [
    ("1. Joints, upper row under the parapet, south facade (ID01 sandwich)", "before_j_upper_s", "after_j_upper_s"),
    ("1. Joints, upper row under the parapet, north slanted facade (ID01)", "before_j_upper_n", "after_j_upper_n"),
    ("1. Joints, metal cassette ID02 RAL 7024, south base", "before_j_id02", "after_j_id02"),
    ("2. Cover strip P44 (orange): SW convex corner, ladder, DECO lights moved out 28 mm", "before_strip_sw", "after_strip_sw"),
    ("2. Cover strip P44 under the Arktos box (box raised 6 mm)", "before_strip_arktos", "after_strip_arktos"),
    ("3. Concave corner glazing, plan cut z 8.0 (cyan = glass faces; after: 6 mm two-face shell)",
     "before_glass_cut_concave", "after_glass_cut_concave"),
    ("3. After: convex R3.15 arc (left), T1 convex 90 deg corner (right), plan cuts", "after_glass_cut_s", "after_glass_cut_t1"),
]
W, H, LAB = 900, 580, 34
try:
    font = ImageFont.truetype("arial.ttf", 22)
except OSError:
    font = ImageFont.load_default()
sheet = Image.new("RGB", (2 * W + 30, len(ROWS) * (H + LAB + 10) + 60), (245, 245, 245))
dr = ImageDraw.Draw(sheet)
dr.text((10, 15), "elv-tc-vpm delivery v005 vs v004 — Max review rework (left: v004, right: v005)", fill=(0, 0, 0), font=font)
y = 60
for title, a, b in ROWS:
    dr.text((10, y), title, fill=(0, 0, 0), font=font)
    for i, n in enumerate((a, b)):
        im = Image.open(os.path.join(d, n + ".png")).convert("RGB")
        im.thumbnail((W, H))
        sheet.paste(im, (10 + i * (W + 10), y + LAB))
    y += H + LAB + 10
sheet.save(out)
print("SHEET", out, sheet.size)
