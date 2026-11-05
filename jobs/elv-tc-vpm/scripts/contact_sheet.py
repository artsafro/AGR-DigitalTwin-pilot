"""elv-tc-vpm: contact sheet of the UDIM texture set (Diffuse / ERM / Normal per tile, plus a 1:1 Diffuse crop).

uv run --no-project --with pillow python contact_sheet.py <textures_dir> <layout.json> <out.png>
"""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont

tex, lay_p, out = sys.argv[1:4]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
lay = json.load(open(lay_p, encoding="utf-8"))
by_udim = {v["udim"]: (k, v) for k, v in lay["tiles"].items()}
C, H = 300, 40
try:
    f = ImageFont.truetype("arial.ttf", 18)
except OSError:
    f = ImageFont.load_default()
rows = sorted(by_udim)
sheet = Image.new("RGB", (4 * C + 5 * 10 + 330, len(rows) * (C + H) + 10), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for r, udim in enumerate(rows):
    key, v = by_udim[udim]
    y = 10 + r * (C + H)
    txt = f"{udim}  {key}  RAL {v.get('ral')}  {v['kind']}"
    if v["kind"] == "full":
        txt += f"  {v['px_per_m']} px/m"
    d.text((10, y), txt, fill=(0, 0, 0), font=f)
    for c, kind in enumerate(("Diffuse", "ERM", "Normal")):
        im = Image.open(os.path.join(tex, f"T_Elevatornaya_1A_{kind}_1.{udim}.png")).convert("RGB")
        lab = f"{kind} {im.size[0]}"
        sheet.paste(im.resize((C, C), Image.NEAREST if im.size[0] <= 256 else Image.LANCZOS), (10 + c * (C + 10), y + 26))
        d.text((14 + c * (C + 10), y + 28), lab, fill=(255, 0, 0), font=f)
    im = Image.open(os.path.join(tex, f"T_Elevatornaya_1A_Diffuse_1.{udim}.png")).convert("RGB")
    n = min(im.size[0], C)
    sheet.paste(im.crop((0, im.size[1] - n, n, im.size[1])).resize((C, C)), (10 + 3 * (C + 10), y + 26))
    d.text((14 + 3 * (C + 10), y + 28), "Diffuse 1:1 crop" if im.size[0] > 256 else "flat", fill=(255, 0, 0), font=f)
sheet.save(out)
print("SAVED", out, sheet.size)
