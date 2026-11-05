"""elv-tc-vpm: one-sided Main -> UCX distance per part (read-only diagnostic, [D134] R12/R13).

blender -b <elv_full_v004_tex.blend> --factory-startup --python ucx_dev_by_part_v001.py -- <export_tri.blend> <export_meta.json> <out.json>
Samples every Main vertex + face centre of the master (part_idx kept there), shifts them by the delivery pivot
offset and measures the distance to the union of the UCX boxes of the delivery export copy.
"""
import bpy
import json
import math
import os
import sys

import numpy as np

exp_blend, meta_path, out = sys.argv[sys.argv.index("--") + 1:][:3]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
meta = json.load(open(meta_path, encoding="utf-8"))
off = np.array(meta["pivot"]["offset_subtracted_m"])
ang = math.radians(meta["ucx"]["facade_angle_deg"])
c, s = math.cos(-ang), math.sin(-ang)
R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])  # world -> facade frame
with bpy.data.libraries.load(exp_blend) as (src, dst):
    dst.meshes = [n for n in src.meshes if n.startswith("UCX_")]
lo, hi = [], []
for me in dst.meshes:
    v = np.array([tuple(x.co) for x in me.vertices]) @ R.T
    lo.append(v.min(0))
    hi.append(v.max(0))
lo, hi = np.array(lo), np.array(hi)
main = bpy.data.objects["SM_Elevatornaya_1A_Main"]
ids = main["part_ids"]
ids = json.loads(ids) if isinstance(ids, str) else list(ids)
me = main.data
pidx = np.array([a.value for a in me.attributes["part_idx"].data])
V = np.array([tuple(x.co) for x in me.vertices])
pts, parts = [], []
for p in me.polygons:
    vv = V[list(p.vertices)]
    for q in list(vv) + [vv.mean(0)]:
        pts.append(q)
        parts.append(pidx[p.index])
P = (np.array(pts) - off) @ R.T
parts = np.array(parts)
d = np.full(len(P), np.inf)
for k in range(0, len(P), 4000):
    q = P[k:k + 4000, None, :]
    dd = np.maximum(np.maximum(lo[None] - q, 0), q - hi[None])
    d[k:k + 4000] = np.sqrt((dd ** 2).sum(2)).min(1)
res = {}
for i in sorted(set(parts.tolist())):
    m = parts == i
    j = np.argmax(np.where(m, d, -1))
    res[ids[i]] = {"n": int(m.sum()), "max_m": round(float(d[m].max()), 3), "gt_0.3": int((d[m] > 0.3).sum()),
                   "gt_1.0": int((d[m] > 1.0).sum()), "worst_delivered_xyz": [round(float(x), 3) for x in (np.array(pts[j]) - off)]}
json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
for k, v in sorted(res.items(), key=lambda kv: -kv[1]["max_m"])[:15]:
    print("DEV", k, v)
