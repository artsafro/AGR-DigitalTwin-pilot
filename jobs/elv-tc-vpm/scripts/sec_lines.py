"""elv-tc-vpm: merge section segments into lines (read-only helper on ref_sections_full_v001.json).

py -3 sec_lines.py <cut> <cats comma> [x0 x1 y0 y1] [minlen]
Prints merged collinear segments: axis-aligned lines as 'X=c  y a..b' / 'Y=c  x a..b', others with endpoints.
For z cuts the plan coords are (x, y); for y cuts (x, z); for x cuts (y, z).
"""
import json, os, sys, math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "..", "outputs", "ref-v002", "ref_sections_full_v001.json"), encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")
cut, cats = sys.argv[1], set(sys.argv[2].split(","))
win = [float(v) for v in sys.argv[3:7]] if len(sys.argv) > 6 else None
minlen = float(sys.argv[7]) if len(sys.argv) > 7 else 0.3
h, v = {"z": (0, 1), "y": (0, 2), "x": (1, 2)}[cut[0]]
segs = []
for s in D[cut]:
    if "*" not in cats and s[0] not in cats:
        continue
    a, b = (s[2 + h], s[2 + v]), (s[5 + h], s[5 + v])
    if win and (max(a[0], b[0]) < win[0] or min(a[0], b[0]) > win[1] or max(a[1], b[1]) < win[2]
                or min(a[1], b[1]) > win[3]):
        continue
    segs.append((s[0], a, b))
lines = defaultdict(list)
other = []
for c, a, b in segs:
    if abs(a[0] - b[0]) < 2e-3:
        lines[("X", round((a[0] + b[0]) / 2, 2), c)].append(tuple(sorted((a[1], b[1]))))
    elif abs(a[1] - b[1]) < 2e-3:
        lines[("Y", round((a[1] + b[1]) / 2, 2), c)].append(tuple(sorted((a[0], b[0]))))
    else:
        other.append((c, a, b))
out = []
for (ax, cc, c), iv in lines.items():
    iv.sort()
    m = [list(iv[0])]
    for p, q in iv[1:]:
        if p <= m[-1][1] + 0.02:
            m[-1][1] = max(m[-1][1], q)
        else:
            m.append([p, q])
    for p, q in m:
        if q - p >= minlen:
            out.append((ax, cc, p, q, c))
for r in sorted(out):
    print("%s=%8.3f  %8.3f .. %8.3f  (%6.2f)  %s" % (r[0], r[1], r[2], r[3], r[3] - r[2], r[4]))
# skew lines: merge by direction + offset
sk = defaultdict(list)
for c, a, b in other:
    L = math.dist(a, b)
    if L < 1e-6:
        continue
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    if d[0] < 0 or (abs(d[0]) < 1e-9 and d[1] < 0):
        d = (-d[0], -d[1])
    n = (-d[1], d[0])
    off = a[0] * n[0] + a[1] * n[1]
    sk[(round(math.degrees(math.atan2(d[1], d[0])), 1), round(off, 2), c)].append((a, b))
for k, ss in sorted(sk.items()):
    pts = [p for s in ss for p in s]
    tot = sum(math.dist(*s) for s in ss)
    if tot < minlen:
        continue
    lo = min(pts)
    hi = max(pts)
    print("SKEW ang %6.2f off %8.3f  %s -> %s len %.2f n%d %s" % (k[0], k[1], [round(x, 3) for x in lo],
                                                                [round(x, 3) for x in hi], tot, len(ss), k[2]))
