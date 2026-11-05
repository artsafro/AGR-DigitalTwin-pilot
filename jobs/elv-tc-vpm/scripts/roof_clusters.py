"""elv-tc-vpm: cluster small roof objects (vent shafts, exits, equipment) into boxes (plain Python, read-only).

py -3 roof_clusters.py [out.json]
Objects with bottom >= 11.85 m, plan size < 6 m, not in the excluded zones (skylight, superstructures, pit, fence,
pilot zone x > 72), merged when their bboxes touch (5 cm). Prints one line per cluster: bbox, names.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "..", "outputs", "ref-v002", "ref_objects_full_v001.json"), encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")
EXCL = [(37.5, 63.3, -28.2, -19.3),      # skylight
        (41.5, 59.5, -11.6, 3.5),        # pit, T1, T2
        (50.5, 76.0, -19.9, -18.9),      # terrace fence line
        (72.0, 80.0, -52.0, 4.0)]        # pilot strip (built in the pilot)


def excluded(r):
    cx, cy = (r["mn"][0] + r["mx"][0]) / 2, (r["mn"][1] + r["mx"][1]) / 2
    return any(a <= cx <= b and c <= cy <= d for a, b, c, d in EXCL)


cand = []
for r in R:
    dx, dy = r["mx"][0] - r["mn"][0], r["mx"][1] - r["mn"][1]
    if r["mn"][2] < 11.85 or r["mx"][2] > 16.6 or max(dx, dy) > 6.0 or excluded(r):
        continue
    if r["cat"] in ("mullion", "glass", "lights_arktos"):
        continue
    cand.append(r)
n = len(cand)
par = list(range(n))


def f(i):
    while par[i] != i:
        par[i] = par[par[i]]
        i = par[i]
    return i


T = 0.05
for i in range(n):
    a = cand[i]
    for j in range(i + 1, n):
        b = cand[j]
        if all(a["mn"][k] - T <= b["mx"][k] and b["mn"][k] - T <= a["mx"][k] for k in range(2)):
            par[f(i)] = f(j)
cl = {}
for i in range(n):
    cl.setdefault(f(i), []).append(cand[i])
out = []
for k, rows in cl.items():
    mn = [round(min(r["mn"][i] for r in rows), 3) for i in range(3)]
    mx = [round(max(r["mx"][i] for r in rows), 3) for i in range(3)]
    out.append({"mn": mn, "mx": mx, "n": len(rows), "names": sorted({r["name"][:30] for r in rows})[:4],
                "cats": sorted({r["cat"] for r in rows})})
out.sort(key=lambda c: (c["mn"][0], c["mn"][1]))
for c in out:
    print("%7.2f %7.2f | %7.2f %7.2f | z %6.2f %6.2f  n%3d %s %s" % (c["mn"][0], c["mx"][0], c["mn"][1], c["mx"][1],
                                                                 c["mn"][2], c["mx"][2], c["n"], c["cats"],
                                                                 c["names"][:2]))
print(len(out), "clusters")
if len(sys.argv) > 1:
    p = os.path.abspath(sys.argv[1])
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
