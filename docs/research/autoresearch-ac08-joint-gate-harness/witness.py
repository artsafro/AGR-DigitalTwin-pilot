"""#127 witnesses (SYNTHETIC image perturbations of the accepted AC08 v010 NPM south render; they test the joint-count
gate compare_facades.py, not the pipeline). Usage:
  uv run python witness.py <spec.json> <clean renders dir> <clean compare.json> <new out root>
Writes <out>/W1_missing_joint/ and <out>/W2_extra_joint/ = copies of the clean renders dir with npm_south.png edited.
W1: the joint nearest the field centre is painted over with the panel colour sampled 0.05 m left of it (per pixel row).
W2: a copy of the darkest joint column is drawn midway between that joint and the next one."""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

spec_p, rdir, cmp_p, out = sys.argv[1:5]
spec = json.load(open(spec_p, encoding="utf-8"))
cmp_ = json.load(open(cmp_p, encoding="utf-8"))
meta = json.load(open(os.path.join(rdir, "renders.json"), encoding="utf-8"))
name = next(n for n, f in spec["facades"].items() if f["normal"] == "-y")
view = meta["npm"]["views"]["south"]
c, r = np.asarray(view["center"], float), np.asarray(view["right"], float)
W, H = view["res"]
scale = view["ortho_scale"] / W
axis = 0
row = next(v for k, v in cmp_["facades"][name]["npm_render_rows"].items())
found = row["found_m"]
k = len(found) // 2
xs = np.arange(W)
s = c[axis] + r[axis] * ((xs + 0.5 - W / 2) * scale)


def px(m):
    return int(np.argmin(np.abs(s - m)))


half = max(2, int(round(0.012 / scale)))           # +-12 mm around the joint centre (joint = 8 mm)
img = np.asarray(Image.open(os.path.join(rdir, "npm_south.png"))).copy()
j, nxt, src = px(found[k]), px(found[k + 1]), px(found[k] - 0.05)
mid = (j + nxt) // 2
w1, w2 = img.copy(), img.copy()
for x in range(j - half, j + half + 1):           # W1: joint -> panel colour, every row
    w1[:, x] = img[:, src]
for d in range(-half, half + 1):                  # W2: joint columns copied to the midpoint
    w2[:, mid + d] = img[:, j + d]
rec = {"synthetic": True, "facade": name, "view": "npm_south", "joint_m": found[k], "joint_px": j,
       "next_joint_m": found[k + 1], "mid_px": mid, "half_px": half, "m_per_px": scale}
for tag, im in (("W1_missing_joint", w1), ("W2_extra_joint", w2)):
    d = os.path.join(out, tag)
    shutil.copytree(rdir, d)                      # refuses an existing dir
    Image.fromarray(im).save(os.path.join(d, "npm_south.png"))
    print("WITNESS", tag, json.dumps(rec))
