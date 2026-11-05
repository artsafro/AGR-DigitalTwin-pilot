"""elv-tc-vpm tex-v004: sample the as-built cassette colour from the customer's site photo (TZ board img_008) and the
booklet render crop (img_009); nearest RAL Classic by CIE76 (Lab) from a short beige / brown list.

uv run --no-project --with pillow --with numpy python sample_wood_colour_v007.py <img_008.png> <img_009.png> <out.json>
Patches are pixel boxes on the ORIGINAL images (x0, y0, x1, y1), chosen on lit, joint-free cassette areas (photo:
the rounded corner above the cantilever, below the sign frame) and soffit panels; per patch the median sRGB.
RAL sRGB values: common published approximations (RAL is defined for paint, not sRGB) - indicative only.
"""
import json, os, sys
import numpy as np
from PIL import Image

p8, p9, out = sys.argv[1:4]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
PATCH = {
    "img_008 cassette, upper corner, lit (left)": (p8, (870, 150, 1040, 330)),
    "img_008 cassette, upper corner, lit (right)": (p8, (1080, 160, 1300, 330)),
    "img_008 cassette, above the cantilever": (p8, (1090, 360, 1330, 420)),
    "img_008 soffit panels (shade)": (p8, (900, 620, 1300, 760)),
    "img_009 booklet render cassette": (p9, (450, 150, 650, 350)),
}
RAL = {"1000": (190, 189, 127), "1001": (194, 176, 120), "1002": (198, 166, 100), "1011": (138, 102, 66),
       "1013": (234, 230, 202), "1014": (225, 204, 79), "1015": (230, 214, 144), "1019": (158, 151, 100),
       "1024": (174, 160, 75), "3012": (193, 135, 107), "3014": (211, 110, 112), "3015": (234, 137, 154),
       "8023": (166, 94, 46), "8024": (121, 85, 61), "8025": (117, 92, 72), "7032": (184, 183, 153),
       "7044": (202, 196, 176), "9001": (250, 244, 227), "1006": (228, 160, 16), "3022": (212, 101, 77)}


def lab(rgb):
    c = np.array(rgb, float) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    x, y, z = M @ c / np.array([0.95047, 1.0, 1.08883])
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    return np.array([116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))])


rows = {}
for k, (p, box) in PATCH.items():
    im = np.asarray(Image.open(p).convert("RGB"))[box[1]:box[3], box[0]:box[2]].reshape(-1, 3)
    med = [int(v) for v in np.median(im, axis=0)]
    L = lab(med)
    near = sorted(((float(np.linalg.norm(L - lab(v))), r) for r, v in RAL.items()))[:3]
    rows[k] = {"box": box, "image": os.path.basename(p), "median_srgb": med, "hex": "#%02X%02X%02X" % tuple(med),
               "nearest_ral_dE76": [[r, round(d, 1)] for d, r in near]}
    print(k, rows[k])
json.dump(rows, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# The photo is taken upwards against a bright sky: the cassettes are under-exposed (Y 0.17 vs 0.44 of the accepted
# RAL 1001 texture). Target = hue / chroma of the two lit photo patches, lightness of the accepted wood colour
# (linear scale to the RAL 1001 luminance). An assumption to confirm with the user / the act (TZ note N5).
def lin(c):
    c = np.array(c, float) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb(l):
    l = np.clip(l, 0, 1)
    return [int(round(v * 255)) for v in np.where(l <= 0.0031308, l * 12.92, 1.055 * l ** (1 / 2.4) - 0.055)]


Yw = np.array([0.2126, 0.7152, 0.0722])
lit = [rows[k]["median_srgb"] for k in list(PATCH)[:2]]
mean_lin = np.mean([lin(c) for c in lit], axis=0)
target = srgb(mean_lin * (lin(RAL["1001"]) @ Yw) / (mean_lin @ Yw))
Lt = lab(target)
near = sorted(((float(np.linalg.norm(Lt - lab(v))), r) for r, v in RAL.items()))[:3]
res = {"patches": rows, "photo_lit_mean_srgb": srgb(mean_lin),
       "target_srgb": target, "target_hex": "#%02X%02X%02X" % tuple(target),
       "target_rule": "hue/chroma of the lit photo patches, luminance of RAL 1001 (accepted wood colour)",
       "target_nearest_ral_dE76": [[r, round(d, 1)] for d, r in near]}
os.remove(out)
json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("TARGET", res["photo_lit_mean_srgb"], res["target_srgb"], res["target_hex"], res["target_nearest_ral_dE76"])
