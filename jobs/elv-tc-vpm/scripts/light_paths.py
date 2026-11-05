"""elv-tc-vpm: map the booklet fixtures (parts/lighting_layout_v001.json) onto the model plan outlines (pure Python).

Outlines (outward = right of the walking direction, arc length u):
  U - pilot upper face (wood / CW, z >= 4.70), L - pilot ground-floor metal face (z < 4.70), both from
      pilot_outlines.py; W - the new facades N / skew / TP annex / W / S, exactly as build_full_v003.py.
Lines: the elevation coordinate is UNROLLED around the R3.15 arcs (layout choice), so u = cum[i] + t along the straight
  facade segment i (t may run past the segment end into the arc). Points: nearest point on the outline.
Overlapping runs on one outline and one level (corner arcs drawn in both views) are split at the overlap middle.
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pilot_geom import Poly  # noqa: E402
from pilot_outlines import U, L  # noqa: E402

SK0, SKD = (-8.496, -2.427), (49.907, 5.388)
x_nc = SK0[0] + SKD[0] * (2.99 - SK0[1]) / SKD[1]
y_wc = SK0[1] + SKD[1] * (-8.82 - SK0[0]) / SKD[0]
W = Poly([(59.43, 2.99), (x_nc, 2.99), (-8.82, y_wc), (-8.82, -11.13), (-4.42, -11.13), (-4.42, -19.95),
          (-0.42, -19.95), (-0.42, -50.46), (41.88, -50.46)])
POLYS = {"U": U, "L": L, "W": W}
X_PILOT_S, X_PILOT_N = 41.86, 59.42      # pilot zone: x beyond these on S / N (and the whole E facade)


def outline(facade, x, z):
    pilot = facade == "east" or (facade == "south" and x > X_PILOT_S) or (facade == "north" and x > X_PILOT_N)
    if not pilot:
        return "W"
    return "U" if z >= 4.69 else "L"


def unrolled(poly, p):
    """u of p measured along the long straight segment nearest to p, unrolled past its ends"""
    best = None
    for i, (a, b) in enumerate(zip(poly.p, poly.p[1:])):
        if poly.cum[i + 1] - poly.cum[i] < 1.5:
            continue
        t = poly.t[i]
        n = poly.n[i]
        d = abs((p[0] - a[0]) * n[0] + (p[1] - a[1]) * n[1])
        s = (p[0] - a[0]) * t[0] + (p[1] - a[1]) * t[1]
        L_ = poly.cum[i + 1] - poly.cum[i]
        out = max(0.0, -s, s - L_)                         # how far past the segment ends
        key = d + 0.2 * out
        if best is None or key < best[0]:
            best = (key, poly.cum[i] + s)
    return best[1]


def runs_and_points(layout):
    """-> runs [{id, type, poly, u0, u1, z, facade}], points [{id, type, poly, u, z, facade, pieces?}]"""
    runs, pts = [], []
    for f in layout["fixtures"]:
        if "start" in f and f["type"].startswith("LINE"):
            pk = outline(f["facade"], max(f["start"][0], f["end"][0]) if f["facade"] != "east" else 99, f["mount_z"])
            if f["facade"] == "south" and min(f["start"][0], f["end"][0]) < X_PILOT_S - 0.01:
                pk = "W"
            if f["facade"] == "north" and min(f["start"][0], f["end"][0]) < X_PILOT_N - 0.01:
                pk = "W"
            poly = POLYS[pk]
            a, b = unrolled(poly, f["start"]), unrolled(poly, f["end"])
            a, b = min(a, b), max(a, b)
            runs.append({"id": f["id"], "type": f["type"], "poly": pk, "u0": max(0.0, a), "u1": min(poly.length, b),
                         "z": f["mount_z"], "facade": f["facade"]})
        elif f["type"] == "FOCUS":
            pk = outline(f["facade"], 99, f["mount_z"])
            poly = POLYS[pk]
            for k, (y0, y1, ln) in enumerate(f["pieces"]):
                c = (79.03, 0.5 * (y0 + y1))
                pts.append({"id": f"{f['id']}.{k + 1:02d}", "type": "FOCUS", "poly": pk, "u": poly.project(c),
                            "z": f["mount_z"], "facade": f["facade"], "len": ln - 0.02})   # 2 cm between bars
        elif f["type"] == "PLAT_A4":
            pk = outline(f["facade"], 99, f["mount_z"])
            for k, p in enumerate(f["positions"]):
                pts.append({"id": f"{f['id']}.{k + 1:02d}", "type": "PLAT_A4", "poly": pk,
                            "u": POLYS[pk].project(p), "z": f["mount_z"], "facade": f["facade"]})
        else:
            p = f["position"]
            pk = outline(f["facade"], p[0], f["mount_z"])
            pts.append({"id": f["id"], "type": f["type"], "poly": pk, "u": POLYS[pk].project(p), "z": f["mount_z"],
                        "facade": f["facade"]})
    # split overlaps on one outline and one level
    for r in runs:
        r["split"] = []
    for i, a in enumerate(runs):
        for b in runs[i + 1:]:
            if a["poly"] != b["poly"] or abs(a["z"] - b["z"]) > 0.3:
                continue
            lo, hi = max(a["u0"], b["u0"]), min(a["u1"], b["u1"])
            if hi <= lo:
                continue
            m = 0.5 * (lo + hi)
            first, second = (a, b) if a["u0"] < b["u0"] else (b, a)
            first["split"].append([round(first["u1"], 3), round(m, 3), second["id"]])
            second["split"].append([round(second["u0"], 3), round(m, 3), first["id"]])
            first["u1"], second["u0"] = m - 0.01, m + 0.01
    return runs, pts
