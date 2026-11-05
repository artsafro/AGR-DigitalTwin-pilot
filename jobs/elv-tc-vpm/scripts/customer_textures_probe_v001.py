"""elv-tc-vpm: describe the customer blank PNG set (size, mode, mean colour, flat or not) + previews of real tiles.

py -3 -I customer_textures_probe_v001.py <pkg_dir> <out_dir>
"""
import sys, os, glob, json
import numpy as np
from PIL import Image

pkg, out = sys.argv[1], sys.argv[2]
rep = {}
for f in sorted(glob.glob(os.path.join(pkg, "*.png"))):
    im = Image.open(f)
    a = np.asarray(im.convert("RGB"))
    flat = bool((a == a[0, 0]).all())
    rep[os.path.basename(f)] = {"size": im.size, "mode": im.mode, "bytes": os.path.getsize(f), "flat": flat,
                                "mean_rgb": [round(float(x), 1) for x in a.reshape(-1, 3).mean(0)],
                                "min_rgb": a.reshape(-1, 3).min(0).tolist(), "max_rgb": a.reshape(-1, 3).max(0).tolist()}
    if not flat:
        im.convert("RGB").resize((1024, 1024), Image.LANCZOS).save(os.path.join(out, "tex_preview_" + os.path.basename(f)))
        w, h = im.size
        im.convert("RGB").crop((w // 2 - 512, h // 2 - 512, w // 2 + 512, h // 2 + 512)).save(
            os.path.join(out, "tex_crop1to1_" + os.path.basename(f)))
        # joint lines: darkest rows/cols profile
        g = a.mean(axis=2)
        rep[os.path.basename(f)]["dark_rows_px"] = np.where(g.mean(1) < g.mean() - 15)[0][:60].tolist()
        rep[os.path.basename(f)]["dark_cols_px"] = np.where(g.mean(0) < g.mean() - 15)[0][:60].tolist()
json.dump(rep, open(os.path.join(out, "textures_probe_customer.json"), "x"), indent=1)
for k, v in rep.items():
    print(k, v["size"], v["mode"], v["flat"], v["mean_rgb"], v.get("dark_rows_px", "")[:20] if not v["flat"] else "",
          v.get("dark_cols_px", "")[:20] if not v["flat"] else "")
