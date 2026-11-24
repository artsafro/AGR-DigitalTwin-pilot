"""Standing #51 POST-HOC diagnostic (not part of the frozen metric): raw source wall segments
(`modules.A.reference` of source_sections_and_openings.json) on the outer facade line of ring seg 18-19,
t = 2.0..6.2 m, versus the v007 extra gap [3.444, 4.715] m. Prints the outer-line (|d| <= 0.03 m) wall intervals.
usage: python posthoc51.py <source_sections_and_openings.json>"""
import json
import math
import sys

A, B = (85.519, 16.334), (95.936, 27.133)
L = math.dist(A, B)
u = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)


def loc(p):
    dx, dy = p[0] - A[0], p[1] - A[1]
    return dx * u[0] + dy * u[1], -dx * u[1] + dy * u[0]   # t along seg 18, d inward (ring is CCW)


ref = json.load(open(sys.argv[1], encoding="utf-8"))["modules"]["A"]["reference"]
outer, inner = [], []
for name, (p, q) in ref:
    (t0, d0), (t1, d1) = loc(p), loc(q)
    if max(t0, t1) < 2.0 or min(t0, t1) > 6.2 or not (-0.3 < d0 < 1.6 and -0.3 < d1 < 1.6):
        continue
    if abs(d0) <= 0.03 and abs(d1) <= 0.03:
        outer.append((round(min(t0, t1), 3), round(max(t0, t1), 3), name[-9:]))
    else:
        inner.append((round(min(d0, d1), 3), round(max(d0, d1), 3)))
outer.sort()
print(json.dumps({"outer_line_wall_intervals_t_m": outer,
                  "outer_line_gaps_t_m": [[outer[i][1], outer[i + 1][0]] for i in range(len(outer) - 1)
                                          if outer[i + 1][0] - outer[i][1] > 0.2],
                  "set_back_depths_d_m": sorted({x for x in inner})[:12]}, ensure_ascii=False))
