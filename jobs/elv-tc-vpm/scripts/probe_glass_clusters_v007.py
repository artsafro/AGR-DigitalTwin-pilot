"""elv-tc-vpm build-v007 probe (read only, plain Python): cluster the glass faces of probe_glass_v006b.json into
openings (same plane within 3 cm, same normal, in-plane gap <= 0.40 m) and list them.

py -3 -I probe_glass_clusters_v007.py <probe_glass.json> <out.json>
"""
import json, math, os, sys

src, out = sys.argv[1:3]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
F = json.load(open(src, encoding="utf-8"))["faces"]
F = [f for f in F if f["part"] != "P35_Skylight"]


def frame(n):
    if abs(n[2]) > 0.7:
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    r = (-n[1], n[0], 0.0)
    L = math.hypot(r[0], r[1])
    return (r[0] / L, r[1] / L, 0.0), (0.0, 0.0, 1.0)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


# group by quantised normal + plane offset
groups = {}
for f in F:
    n = f["n"]
    key = (round(n[0], 2), round(n[1], 2), round(n[2], 2))
    groups.setdefault(key, []).append(f)
clusters = []
for key, fs in groups.items():
    r, up = frame(key)
    for f in fs:
        f["_d"] = dot(f["c"], key)
        f["_u"] = dot(f["c"], r)
        f["_v"] = dot(f["c"], up)
        f["_h"] = math.sqrt(f["a"]) / 2
    # union-find on (plane, in-plane distance)
    par = list(range(len(fs)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for i in range(len(fs)):
        for j in range(i + 1, len(fs)):
            a, b = fs[i], fs[j]
            if abs(a["_d"] - b["_d"]) > 0.03:
                continue
            if abs(a["_u"] - b["_u"]) > a["_h"] + b["_h"] + 0.9 or abs(a["_v"] - b["_v"]) > a["_h"] + b["_h"] + 1.2:
                continue
            par[find(i)] = find(j)
    comp = {}
    for i in range(len(fs)):
        comp.setdefault(find(i), []).append(fs[i])
    for cs in comp.values():
        clusters.append({"n": list(key), "d": round(sum(c["_d"] for c in cs) / len(cs), 3), "faces": len(cs),
                         "area": round(sum(c["a"] for c in cs), 2),
                         "u": [round(min(c["_u"] for c in cs), 2), round(max(c["_u"] for c in cs), 2)],
                         "v": [round(min(c["_v"] for c in cs), 2), round(max(c["_v"] for c in cs), 2)],
                         "c": [round(sum(c["c"][k] for c in cs) / len(cs), 2) for k in range(3)],
                         "parts": sorted({c["part"] for c in cs}),
                         "behind": sorted({(c["hit"]["part"] + "@" + str(c["hit"]["d"])) if c["hit"] else "void" for c in cs})})
clusters.sort(key=lambda c: (c["n"], c["c"]))
json.dump(clusters, open(out, "w", encoding="utf-8"), indent=1)
for i, c in enumerate(clusters):
    print(i, c["n"], "d", c["d"], "c", c["c"], "faces", c["faces"], "area", c["area"], "u", c["u"], "v", c["v"],
          c["parts"], c["behind"][:3])
