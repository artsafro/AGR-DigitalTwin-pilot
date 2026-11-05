"""elv-tc-vpm: compose overlay images theirs (red) vs ours (blue) from paired workbench renders + plan sections.

py -3 -I customer_overlay_compose_v001.py <renders_dir> <out_dir> <tag> [dx dy]
Silhouette layer: both = light grey, theirs only = light red, ours only = light blue; edge layer on top:
theirs edges red, ours edges blue. Plan sections (z 1.5 / 6 / 11 m) from sections_v001.npz, theirs shifted by dx dy.
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

rd, out, tag = sys.argv[1], sys.argv[2], sys.argv[3]
dx, dy = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (0.0, 0.0)
stats = {}


def edges(g):
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    return (gx + gy) > 18


for view in ("top", "S_minusY", "N_plusY", "E_plusX", "W_minusX"):
    a = np.asarray(Image.open(os.path.join(rd, f"{view}_theirs.png")).convert("L")).astype(np.int16)
    b = np.asarray(Image.open(os.path.join(rd, f"{view}_ours.png")).convert("L")).astype(np.int16)
    ma, mb = a < 245, b < 245
    img = np.full(a.shape + (3,), 255, np.uint8)
    img[ma & mb] = (215, 215, 215)
    img[ma & ~mb] = (255, 170, 170)
    img[~ma & mb] = (170, 190, 255)
    eb, ea = edges(b), edges(a)
    img[eb] = (0, 60, 230)
    img[ea] = (225, 0, 0)
    img[ea & eb] = (90, 0, 120)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    d.text((10, 10), f"{view}: RED = customer blank SM_Elevatornaya_Vl_1_A_001 ({tag}), BLUE = ours SM_Elevatornaya_1A v002; "
                     f"fill: light red = theirs only, light blue = ours only, grey = both; 20 px/m", fill=(0, 0, 0))
    im.save(os.path.join(out, f"overlay_{tag}_{view}.png"))
    px = 20.0 * 20.0
    stats[view] = {"theirs_only_m2": round(float((ma & ~mb).sum()) / px, 1), "ours_only_m2": round(float((~ma & mb).sum()) / px, 1),
                   "both_m2": round(float((ma & mb).sum()) / px, 1),
                   "iou": round(float((ma & mb).sum()) / float((ma | mb).sum()), 4)}
json.dump(stats, open(os.path.join(out, f"overlay_{tag}_silhouette_stats.json"), "x"), indent=1)
print(json.dumps(stats, indent=1))

# plan sections
S = np.load(os.path.join(out, "sections_v001.npz"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
fig, axs = plt.subplots(3, 1, figsize=(18, 33))
for ax, h in zip(axs, ("1_5", "6_0", "11_0")):
    t = S[f"theirs_{h}"].copy()
    t[:, :, 0] += dx
    t[:, :, 1] += dy
    ax.add_collection(LineCollection(S[f"ours_{h}"], colors="#0040e0", linewidths=1.2, label="ours v002"))
    ax.add_collection(LineCollection(t, colors="#e00000", linewidths=0.8, label="customer blank"))
    ax.set_aspect("equal")
    ax.autoscale()
    ax.grid(True, lw=0.3)
    ax.set_title(f"Plan section z = {h.replace('_', '.')} m (ours frame; theirs shifted dx={dx} dy={dy}); red = customer, blue = ours")
    ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(os.path.join(out, f"plan_sections_{tag}.png"), dpi=110)
print("DONE")
