"""elv-tc-vpm: query helper over outputs/ref-v002/ref_objects_full_v001.json (plain Python, read-only).

py -3 inv_query.py summary
py -3 inv_query.py cat <category> [x0 x1 y0 y1 z0 z1]      list objects of a category (bbox filter optional)
py -3 inv_query.py name <substring> [box...]               list objects whose name contains the substring
py -3 inv_query.py box x0 x1 y0 y1 z0 z1                   all objects whose bbox intersects the box
"""
import json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "..", "outputs", "ref-v002", "ref_objects_full_v001.json"), encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")


def inbox(r, b):
    if not b:
        return True
    x0, x1, y0, y1, z0, z1 = b
    return not (r["mx"][0] < x0 or r["mn"][0] > x1 or r["mx"][1] < y0 or r["mn"][1] > y1 or r["mx"][2] < z0
                or r["mn"][2] > z1)


def show(rows):
    for r in sorted(rows, key=lambda r: (r["mn"][2], r["mn"][0], r["mn"][1])):
        print("%-14s %-50s mn %8.3f %8.3f %7.3f  mx %8.3f %8.3f %7.3f  t%5d" % (
            r["cat"], r["name"][:50], *r["mn"], *r["mx"], r["t"]))
    print(len(rows), "objects")


a = sys.argv[1:]
if a[0] == "summary":
    mn = [min(r["mn"][i] for r in R) for i in range(3)]
    mx = [max(r["mx"][i] for r in R) for i in range(3)]
    print("bbox", mn, mx)
    d = defaultdict(lambda: [0, 0, [1e9] * 3, [-1e9] * 3])
    for r in R:
        e = d[r["cat"]]
        e[0] += 1
        e[1] += r["t"]
        e[2] = [min(e[2][i], r["mn"][i]) for i in range(3)]
        e[3] = [max(e[3][i], r["mx"][i]) for i in range(3)]
    for k, e in sorted(d.items()):
        print("%-16s n%5d t%7d  %s %s" % (k, e[0], e[1], [round(x, 2) for x in e[2]], [round(x, 2) for x in e[3]]))
elif a[0] == "cat":
    b = [float(x) for x in a[2:8]]
    show([r for r in R if r["cat"] == a[1] and inbox(r, b)])
elif a[0] == "name":
    b = [float(x) for x in a[2:8]]
    show([r for r in R if a[1] in r["name"] and inbox(r, b)])
elif a[0] == "box":
    b = [float(x) for x in a[1:7]]
    show([r for r in R if inbox(r, b)])
elif a[0] == "types":
    b = [float(x) for x in a[2:8]]
    c = Counter()
    for r in R:
        if (a[1] == "*" or r["cat"] == a[1]) and inbox(r, b):
            c[r["name"].rsplit("_", 1)[0][:60]] += 1
    for k, v in c.most_common(80):
        print(v, k)
