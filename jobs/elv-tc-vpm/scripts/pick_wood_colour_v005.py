"""elv-tc-vpm tex-v005: warm-beige wood colour replacing #C4ABAA (user 2026-11-05: «reads pink»), + old/new swatch.

uv run --no-project --with pillow --with numpy python pick_wood_colour_v005.py <out.json> <swatch.png>

Rule (user brief): HSV hue 30-40 deg (yellow-orange, not red), CIE L* of #C4ABAA (72.1), low-moderate saturation
(RAL 1001 family, more muted than RAL 1001: HSV S 0.24 vs 0.38). Pick HSV hue 35 deg, S 0.24, V solved for L* 72.1.
Nearest RAL by CIE76 on the sample_wood_colour_v007.py list (+ the second common sRGB approximations of 1001 / 1019).
RAL sRGB values are published approximations (RAL is defined for paint) - indicative only.
"""
import colorsys
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

out, swatch = sys.argv[1:3]
for p in (out, swatch):
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
OLD = (196, 171, 170)
RAL = {"1000": (190, 189, 127), "1001": (194, 176, 120), "1002": (198, 166, 100), "1011": (138, 102, 66),
       "1013": (234, 230, 202), "1014": (225, 204, 79), "1015": (230, 214, 144), "1019": (158, 151, 100),
       "1024": (174, 160, 75), "3012": (193, 135, 107), "3014": (211, 110, 112), "3015": (234, 137, 154),
       "8023": (166, 94, 46), "8024": (121, 85, 61), "8025": (117, 92, 72), "7032": (184, 183, 153),
       "7044": (202, 196, 176), "9001": (250, 244, 227), "1006": (228, 160, 16), "3022": (212, 101, 77),
       "1001 (alt #D0B084)": (208, 176, 132), "1019 (alt #A48F7A)": (164, 143, 122)}


def lab(rgb):
    c = np.array(rgb, float) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    x, y, z = M @ c / np.array([0.95047, 1.0, 1.08883])
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    return np.array([116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))])


def desc(rgb):
    L = lab(rgb)
    h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    return {"srgb": list(rgb), "hex": "#%02X%02X%02X" % tuple(rgb), "lab": [round(float(x), 2) for x in L],
            "chroma": round(float(np.hypot(L[1], L[2])), 2), "hsv": [round(h * 360, 1), round(s, 3), round(v, 3)],
            "nearest_ral_dE76": [[r, round(d, 1)] for d, r in sorted((float(np.linalg.norm(L - lab(c))), r)
                                                                    for r, c in RAL.items())[:3]]}


H, S, L_T = 35.0, 0.24, float(lab(OLD)[0])
V = min(range(500, 1000), key=lambda V: abs(lab([round(255 * c) for c in colorsys.hsv_to_rgb(H / 360, S, V / 1000)])[0] - L_T))
NEW = tuple(round(255 * c) for c in colorsys.hsv_to_rgb(H / 360, S, V / 1000))
res = {"rule": "HSV hue 35 deg, S 0.24, CIE L* of #C4ABAA; nearest RAL CIE76 (indicative sRGB approximations)",
       "old": desc(OLD), "new": desc(NEW), "dE76_old_new": round(float(np.linalg.norm(lab(OLD) - lab(NEW))), 1)}
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False))

# swatch: flat fields + the ID03 joint colour (rgb * 0.30) as in make_textures_full_v007.py
os.makedirs(os.path.dirname(os.path.abspath(swatch)), exist_ok=True)
W, Hh = 1200, 560
im = Image.new("RGB", (W, Hh), (255, 255, 255))
d = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 26)
except OSError:
    font = ImageFont.load_default()
for i, (lbl, c) in enumerate((("v003 old", OLD), ("v004 new", NEW))):
    x0 = 40 + i * 580
    d.rectangle([x0, 40, x0 + 540, 440], fill=c)
    j = tuple(round(v * 0.30) for v in c)
    for k in (1, 2):  # cassette joint lines, 1000 x 1530 grid look
        d.rectangle([x0 + k * 180 - 3, 40, x0 + k * 180 + 3, 440], fill=j)
    d.rectangle([x0, 40 + 262 - 3, x0 + 540, 40 + 262 + 3], fill=j)
    D = desc(c)
    d.text((x0, 455), f"{lbl}: {D['hex']}  sRGB {c[0]}/{c[1]}/{c[2]}", fill=(0, 0, 0), font=font)
    d.text((x0, 495), f"nearest RAL {D['nearest_ral_dE76'][0][0]}  dE76 {D['nearest_ral_dE76'][0][1]}", fill=(0, 0, 0), font=font)
im.save(swatch)
