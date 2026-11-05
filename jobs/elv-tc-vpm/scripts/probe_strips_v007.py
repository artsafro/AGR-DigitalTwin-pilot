"""elv-tc-vpm build-v007 probe (read only, plain Python): the horizontal joint cover strips («накладки», booklet
item 14, Revit Batten_FS-8P 165 x 22 mm, family "(SC)-Batten_FS-8P ..._horizontal") among the customer's
outlines (customer-clarify-v001/data/nakl_verts.json, already in OUR delivered frame): 24 outlines, 413.2 m;
z bands +4.535..4.700 and +10.285..10.450 (17) plus +5.915..6.080 / +11.915..12.080 (7, short returns).

py -3 -I probe_strips_v007.py <nakl_verts.json> <out.json>
"""
import json, math, os, sys

src, out = sys.argv[1:3]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
R = json.load(open(src, encoding="utf-8"))
fams = {}
for r in R:
    zs = [v[2] for v in r["verts"]]
    k = (r["fam"], round(min(zs), 3), round(max(zs), 3), r["depth"])
    fams[k] = fams.get(k, 0) + 1
for k, n in sorted(fams.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    print(n, k)
sel = []
for r in R:
    zs = [v[2] for v in r["verts"]]
    z0, z1 = min(zs), max(zs)
    if "FS-8P" in r["fam"] and "horizontal" in r["fam"]:
        xs, ys = [v[0] for v in r["verts"]], [v[1] for v in r["verts"]]
        L = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        sel.append({"name": r["name"], "fam": r["fam"], "z": [round(z0, 4), round(z1, 4)], "depth": r["depth"],
                    "verts": r["verts"], "len": round(L, 3)})
json.dump(sel, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("selected", len(sel), "total length", round(sum(s["len"] for s in sel), 2))
for s in sel:
    print(s["name"], s["fam"][-30:], s["z"], s["depth"], s["len"], [round(c, 3) for c in s["verts"][0]], [round(c, 3) for c in s["verts"][1]])
