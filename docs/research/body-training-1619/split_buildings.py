"""Split a site census (site_census.py JSON) into buildings (#1619 gate 1). new-case: read-only building splitter.

python split_buildings.py CENSUS.json OUT.json [--cell 1.0] [--gap 3] [--zmin Z]
Facade walls (name contains a facade keyword) are rasterised by XY bbox on a CELL grid, dilated by GAP
cells, connected components = buildings. Per building: XY bbox, z range, facade wall count, distinct wall
base levels (storey estimate), off-main facade share (rounded/angled walls), facade types, decor objects
(railings, generic models) inside the bbox. Refuses an output that resolves to the input.
"""
import argparse
import collections
import json
import os
import sys

FACADE = ("вентфас", "шт_фасад", "башня", "фасад")

ap = argparse.ArgumentParser()
ap.add_argument("census")
ap.add_argument("out")
ap.add_argument("--cell", type=float, default=1.0)
ap.add_argument("--gap", type=int, default=3)
ap.add_argument("--zmin", type=float, default=-1e9, help="only walls starting at or above this z (cuts off a joining podium)")
a = ap.parse_args()
if os.path.realpath(a.out) == os.path.realpath(a.census):
    sys.exit("output resolves to the input")
objs = json.load(open(a.census, encoding="utf-8"))["objects"]
if not objs:
    sys.exit("empty census")
walls = [o for o in objs if o["name"].lower().startswith("базовая стена") and any(k in o["name"].lower() for k in FACADE) and o["min"][2] >= a.zmin]
if not walls:
    sys.exit("no facade walls in census")
x0 = min(o["min"][0] for o in walls)
y0 = min(o["min"][1] for o in walls)


def cells(o, g):
    i0 = int((o["min"][0] - x0) / a.cell) - g
    i1 = int((o["max"][0] - x0) / a.cell) + g
    j0 = int((o["min"][1] - y0) / a.cell) - g
    j1 = int((o["max"][1] - y0) / a.cell) + g
    return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]


owner = {}
parent = list(range(len(walls)))


def find(k):
    while parent[k] != k:
        parent[k] = parent[parent[k]]
        k = parent[k]
    return k


for k, o in enumerate(walls):
    for c in cells(o, a.gap):
        if c in owner:
            parent[find(k)] = find(owner[c])
        else:
            owner[c] = k
groups = collections.defaultdict(list)
for k in range(len(walls)):
    groups[find(k)].append(walls[k])
out = []
for g in groups.values():
    bmin = [min(o["min"][i] for o in g) for i in range(3)]
    bmax = [max(o["max"][i] for o in g) for i in range(3)]
    fac = sum(o["facade_m2"] for o in g)
    off = sum(o["off_main_m2"] for o in g)
    levels = sorted({round(o["min"][2], 1) for o in g})
    types = collections.Counter(o["name"].rsplit("_", 1)[0][14:44] for o in g).most_common(4)
    inside = [o for o in objs if all(bmin[i] - 0.5 <= o["min"][i] and o["max"][i] <= bmax[i] + 0.5 for i in (0, 1))]
    decor = collections.Counter(o["name"].split(" ")[0] for o in inside if o["name"].split(" ")[0] in ("Ограждение", "Обобщенные", "ОбщМд", "Семейство1", "Семейство2", "Семейство3", "Стойка", "МРФ-001"))
    out.append({"bbox_min": [round(v, 1) for v in bmin], "bbox_max": [round(v, 1) for v in bmax],
                "walls": len(g), "objects_inside": len(inside), "levels": len(levels),
                "facade_m2": round(fac), "off_main_share": round(off / fac, 3) if fac else None,
                "types": types, "decor": dict(decor)})
out.sort(key=lambda r: -r["facade_m2"])
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, r in enumerate(out):
    print(k, r["bbox_min"], r["bbox_max"], "walls", r["walls"], "lv", r["levels"], "fac", r["facade_m2"], "off", r["off_main_share"])
