"""Hook `before`/`after` stage `body` (#1619 training polygon): floor contour vs the OUTER facade envelope.

Pattern: n/a | new-case: recess census of a floor contour against a registered etalon envelope (BM-01 outer envelope).

uv run python envelope_check.py FLOOR.json ETALON.npz OUT.json --dz DZ [--mirror-x] [--close 0.5]
    [--texture-depth 0.4] [--pocket-close 3.0] [--png TOP.png] [--fill FILL.json]

Why: round 2 (G22 body 1) took the contour from the wall SECTION; where the section crosses niche returns and
partitions that reach the facade, the ring dives into the building ("polygons going inside", Artem 2026-11-17).
The etalon (Artem's delivered NPM) is cut at the same spandrel height (`contour_section_z` + DZ) and registered
to the contour (zones_from_etalon.register); its outer envelope = exterior ring of the closed cut.
Reports:
  * `inward`: every contour stretch lying more than --texture-depth INSIDE the etalon envelope, with its depth;
  * `pockets`: recesses of the contour = closing(contour, --pocket-close) minus contour; each with width, depth,
    the share the etalon fills, and the decision: depth <= --texture-depth -> fill (texture, BM-08);
    deeper and the etalon fills >= 50 % -> fill (etalon has no geometry there); otherwise keep (etalon geometry);
  * `etalon_recess_depths`: depths of the etalon's own recesses (what the etalon keeps as geometry).
--fill writes the pockets to fill (source-frame polygons, the repair list). Every pocket ends in fill or keep
with its reason. Gate: verdict `fail` and exit 2 when any stretch lies inside the envelope or any pocket must be
filled. Refuses outputs equal to an input.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zones_from_etalon import etalon_cut, register  # noqa: E402


def envelope(segs, close):
    blob = unary_union([LineString(s[:2]).buffer(0.05, cap_style="flat") for s in segs]).buffer(close, join_style="mitre")
    polys = list(getattr(blob, "geoms", [blob]))
    outer = max(polys, key=lambda p: Polygon(p.exterior).area)
    env = Polygon(outer.exterior).buffer(-close - 0.05, join_style="mitre")
    if env.geom_type != "Polygon":
        env = max(env.geoms, key=lambda p: p.area)
    return Polygon(env.exterior)


def pockets_of(poly, r, min_area=0.05):
    closed = poly.buffer(r, join_style="mitre").buffer(-r, join_style="mitre")
    diff = closed.difference(poly)
    geoms = [g for g in getattr(diff, "geoms", [diff]) if g.geom_type == "Polygon" and g.area > min_area]
    out = []
    for g in geoms:
        mouth = g.boundary.difference(poly.exterior.buffer(1e-3))  # the open side of the pocket
        mouth_len = mouth.length
        # depth = farthest pocket point from the mouth line (from the closed outline)
        pts = np.array(g.exterior.coords)
        dep = max(closed.exterior.distance(Point(p)) for p in pts) if mouth_len > 0 else 0.0
        out.append((g, round(float(dep), 3), round(float(mouth_len), 3)))
    return out


def steps_of(ring_xy, simplify=0.03, max_depth=1.0, min_run=1.0):
    """Facade steps (jogs): a short edge between two long, parallel neighbours; returns the step depths, m."""
    p = Polygon(ring_xy).simplify(simplify)
    c = np.array(p.exterior.coords)[:-1]
    n = len(c)
    out = []
    for i in range(n):
        a, b = c[i], c[(i + 1) % n]
        e = b - a
        L = float(np.linalg.norm(e))
        if not (0.02 < L <= max_depth):
            continue
        u = c[i] - c[i - 1]
        w = c[(i + 2) % n] - c[(i + 1) % n]
        lu, lw = np.linalg.norm(u), np.linalg.norm(w)
        if lu < min_run or lw < min_run:
            continue
        if abs(u[0] * w[1] - u[1] * w[0]) / (lu * lw) > math.sin(math.radians(10)) or (u @ w) < 0:
            continue
        out.append(round(abs(u[0] * e[1] - u[1] * e[0]) / lu, 3))
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("floor")
    ap.add_argument("etalon")
    ap.add_argument("out")
    ap.add_argument("--dz", type=float, required=True)
    ap.add_argument("--mirror-x", action="store_true")
    ap.add_argument("--close", type=float, default=0.5, help="closing radius of the etalon cut, m")
    ap.add_argument("--texture-depth", type=float, default=0.4, help="recess depth at or below it = texture, m")
    ap.add_argument("--pocket-close", type=float, default=3.0, help="closing radius that finds contour recesses, m")
    ap.add_argument("--max-rms", type=float, default=0.35)
    ap.add_argument("--png")
    ap.add_argument("--fill", help="JSON: pockets to fill (source-frame polygons), the repair list")
    a = ap.parse_args(argv)
    if not (a.texture_depth > 0 and math.isfinite(a.texture_depth) and a.pocket_close > 0 and math.isfinite(a.pocket_close)):
        sys.exit("refused: --texture-depth and --pocket-close must be finite and > 0")
    ins = {os.path.realpath(p) for p in (a.floor, a.etalon)}
    outs = [p for p in (a.out, a.png, a.fill) if p]
    if any(os.path.realpath(p) in ins for p in outs) or len({os.path.realpath(p) for p in outs}) != len(outs):
        sys.exit("refused: outputs must be new files, distinct from the inputs and from each other")
    spec = json.load(open(a.floor, encoding="utf-8"))
    xy = np.array(spec["rings"][0]["xy"], dtype=float)
    if len(xy) < 3 or not np.isfinite(xy).all():
        sys.exit("refused: ring 0 needs >= 3 finite vertices")
    src_poly = Polygon(xy)
    if not src_poly.is_valid or src_poly.area <= 0:
        sys.exit("refused: ring 0 is not a valid polygon")
    d = np.load(a.etalon)

    class _Img:  # etalon_cut samples a colour; the geometry check needs none
        size = (1, 1)

        def convert(self, _):
            return np.zeros((1, 1, 3), np.uint8)
    segs, _ = etalon_cut(d, float(spec["contour_section_z"]) + a.dz, _Img())
    if len(segs) < 10:
        sys.exit("refused: etalon cut has %d segments" % len(segs))
    ext = LineString(list(map(tuple, xy)) + [tuple(xy[0])])
    perim = ext.length
    ss = np.arange(0.05, perim, 0.1)
    pts = np.array([ext.interpolate(s).coords[0] for s in ss])
    mx = np.array([-1.0, 1.0]) if a.mirror_x else np.array([1.0, 1.0])
    dense = np.concatenate([np.array(s[0])[None] + np.linspace(0, 1, max(2, int(np.linalg.norm(s[1] - s[0]) / 0.25) + 1))[:, None]
                            * (np.array(s[1]) - np.array(s[0]))[None] for s in segs]).reshape(-1, 2)
    R, T, rms = register((pts * mx)[::5], dense[::max(1, len(dense) // 3000)], a.max_rms)

    def to_et(p):
        return (np.asarray(p, float) * mx) @ R.T + T

    def to_src(p):
        return ((np.asarray(p, float) - T) @ R) * mx
    poly = Polygon(to_et(xy))
    lo, hi = np.array(poly.bounds[:2]) - 3, np.array(poly.bounds[2:]) + 3
    near = [s for s in segs if (np.minimum(s[0], s[1]) > lo).all() and (np.maximum(s[0], s[1]) < hi).all()]
    env = envelope(near, a.close)
    # signed offset of each 0.1 m sample: < 0 = inside the etalon envelope
    pe = to_et(pts)
    off = np.array([(-1 if env.contains(Point(p)) else 1) * env.exterior.distance(Point(p)) for p in pe])
    outward = float(((off > a.texture_depth).sum()) * 0.1)
    outward_max = float(max(off.max(), 0.0))

    def stretches(sign):
        out, cur = [], None
        for s, o in zip(ss, sign * off):
            if o < -a.texture_depth:
                if cur is None:
                    cur = [s, s, o]
                cur[1], cur[2] = s, min(cur[2], o)
            elif cur is not None:
                out.append(cur)
                cur = None
        if cur is not None:
            out.append(cur)
        return [{"s0": round(c[0] - 0.05, 2), "s1": round(c[1] + 0.05, 2), "length_m": round(c[1] - c[0] + 0.1, 2),
                 "depth_m": round(-c[2], 2), "at_src": [round(v, 2) for v in ext.interpolate((c[0] + c[1]) / 2).coords[0]]}
                for c in out]
    inward = stretches(1.0)
    outward_list = stretches(-1.0)
    pk = []
    fills = []
    for g, dep, mouth in pockets_of(poly, a.pocket_close):
        et_share = g.intersection(env).area / g.area
        if dep <= a.texture_depth:
            dec, why = "fill", "depth %.2f <= %.2f m: texture (BM-08)" % (dep, a.texture_depth)
        elif et_share >= 0.5:
            dec, why = "fill", "etalon has no recess here (%.0f %% of the pocket inside its envelope)" % (100 * et_share)
        else:
            dec, why = "keep", "etalon keeps this recess as geometry (%.0f %% inside its envelope)" % (100 * et_share)
        c = g.representative_point()
        rec = {"centre_src": [round(v, 3) for v in to_src([c.x, c.y]).tolist()], "area_m2": round(g.area, 3),
               "mouth_m": mouth, "depth_m": dep, "etalon_filled_share": round(et_share, 3), "decision": dec, "reason": why}
        pk.append(rec)
        if dec == "fill":
            fills.append([[round(v, 4) for v in q] for q in to_src(np.array(g.exterior.coords)).tolist()])
    et_pk = [dep for g, dep, mouth in pockets_of(env, a.pocket_close)]
    rep = {
        "floor": os.path.basename(a.floor), "etalon": os.path.basename(a.etalon), "dz": a.dz, "mirror_x": a.mirror_x,
        "register_median_m": round(rms, 3), "texture_depth_m": a.texture_depth, "pocket_close_m": a.pocket_close,
        "contour_vertices": len(xy), "perimeter_m": round(perim, 2),
        "etalon_envelope": {"perimeter_m": round(env.exterior.length, 2), "vertices": len(env.exterior.coords) - 1},
        "inward_total_m": round(sum(i["length_m"] for i in inward), 2), "inward_max_depth_m": max([i["depth_m"] for i in inward], default=0.0),
        "inward": inward, "outward": outward_list, "outward_total_m": round(outward, 2), "outward_max_m": round(outward_max, 2), "pockets": pk,
        "pockets_fill": sum(1 for p in pk if p["decision"] == "fill"), "pockets_keep": sum(1 for p in pk if p["decision"] == "keep"),
        "etalon_recess_depths_m": sorted(et_pk),
        "contour_step_depths_m": steps_of(np.array(poly.exterior.coords)[:-1]),
        "etalon_step_depths_m": steps_of(np.array(env.exterior.coords)[:-1], simplify=0.08),
    }
    # gate (BM-01): no contour stretch inside the outer envelope, no recess that is texture or etalon-flat
    rep["verdict"] = "pass" if not inward and rep["pockets_fill"] == 0 else "fail"
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    if a.fill:
        with open(a.fill, "x", encoding="utf-8") as f:
            json.dump({"frame": "source", "polygons": fills}, f, indent=1)
    if a.png:
        _plot(a.png, env, poly, rep, to_et, off, pe, a.texture_depth)
    print(json.dumps({k: rep[k] for k in ("verdict", "register_median_m", "contour_vertices", "inward_total_m", "inward_max_depth_m",
                                           "outward_total_m", "outward_max_m", "pockets_fill", "pockets_keep", "etalon_recess_depths_m",
                                           "contour_step_depths_m", "etalon_step_depths_m")}))
    if rep["verdict"] != "pass":
        sys.exit(2)


def _plot(path, env, poly, rep, to_et, off, pe, tdep):
    """Top view: grey = etalon envelope, blue = contour, red dots + depth = contour inside the envelope by > tdep,
    orange = outside by > tdep, pocket depths green (keep) / red (fill)."""
    from PIL import Image, ImageDraw
    allp = np.concatenate([np.array(env.exterior.coords), np.array(poly.exterior.coords)])
    lo, hi = allp.min(0) - 3, allp.max(0) + 3
    S = 9.0
    W, H = int((hi[0] - lo[0]) * S), int((hi[1] - lo[1]) * S) + 30
    im = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    f = lambda q: ((q[0] - lo[0]) * S, H - (q[1] - lo[1]) * S)
    dr.polygon([f(q) for q in env.exterior.coords], fill=(225, 225, 225), outline=(90, 90, 90))
    dr.line([f(q) for q in poly.exterior.coords], fill=(0, 90, 200), width=2)
    for p, o in zip(pe, off):
        if abs(o) > tdep:
            x, y = f(p)
            dr.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(220, 0, 0) if o < 0 else (240, 140, 0))
    for st, col in [(s, (200, 0, 0)) for s in rep["inward"]] + [(s, (200, 110, 0)) for s in rep["outward"]]:
        x, y = f(to_et(st["at_src"]))
        dr.text((x + 6, y + 2), "%.1f m" % st["depth_m"], fill=col)
    for p in rep["pockets"]:
        x, y = f(to_et(p["centre_src"]))
        dr.text((x + 4, y - 12), "%.1f" % p["depth_m"], fill=(220, 0, 0) if p["decision"] == "fill" else (0, 140, 0))
    dr.text((8, 6), "grey = etalon envelope, blue = contour (%d v); red = inside by > %.2f m: %.1f m, max %.2f m; "
            "orange = outside: %.1f m" % (rep["contour_vertices"], tdep, rep["inward_total_m"], rep["inward_max_depth_m"],
                                          rep["outward_total_m"]), fill=(0, 0, 0))
    im.save(path)


if __name__ == "__main__":
    main()
