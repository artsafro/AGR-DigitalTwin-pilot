"""Hook `before` stage `body` (#1619 polygon, site 63 tower A): contour recesses without an etalon (D341).

Pattern: n/a | new-case: recess census of a floor contour against its own outer envelope (no etalon for site 63).

uv run python pockets_self.py FLOOR.json OUT.json --fill FILL.json [--texture-depth 0.4] [--pocket-close 3.0]
    [--png TOP.png]

D341: the body contour is the OUTER envelope; a recess shallower than --texture-depth is texture (filled); a deeper
niche stays geometry only where the approved reference has it. Site 63 has no etalon: the reference is the Revit
facade itself (the full-height niches are design, gate 1 picked tower A for them), so a deeper pocket is KEPT with
that reason and listed for Artem. Pockets = closing(contour, --pocket-close) minus contour (envelope_check.pockets_of).
--fill gets the pockets to fill as source-frame polygons (floor_from_dump --fill). Verdict `fail` + exit 2 while any
pocket must be filled (the repair list is not applied yet); `pass` when none. Refuses outputs equal to the input.
"""
import argparse
import json
import os
import sys

import numpy as np
from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "garibaldi22",
                                "body-training-1619", "hooks"))
from envelope_check import pockets_of  # noqa: E402


def census(xy, texture_depth=0.4, pocket_close=3.0):
    """Pockets of a contour -> (rows, fill polygons). Every pocket ends in fill or keep with its reason."""
    poly = Polygon(xy)
    if not poly.is_valid or poly.area <= 0:
        raise ValueError("contour is not a valid polygon")
    rows, fills = [], []
    for g, dep, mouth in pockets_of(poly, pocket_close):
        c = g.representative_point()
        row = {"at": [round(c.x, 2), round(c.y, 2)], "depth_m": dep, "mouth_m": mouth, "area_m2": round(g.area, 3)}
        if dep <= texture_depth:
            row["decision"], row["reason"] = "fill", "recess <= %.2f m is texture (D341)" % texture_depth
            fills.append([[float(x), float(y)] for x, y in list(g.exterior.coords)[:-1]])
        else:
            row["decision"] = "keep"
            row["reason"] = "deeper than %.2f m; no etalon for site 63, the Revit facade has it (design niche)" % texture_depth
        rows.append(row)
    return rows, fills


def _plot(path, xy, rows, fills):
    from PIL import Image, ImageDraw
    p = np.array(xy)
    lo, hi = p.min(0) - 2, p.max(0) + 2
    S = 14.0
    W, H = int((hi[0] - lo[0]) * S), int((hi[1] - lo[1]) * S)
    im = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(im)
    P = lambda q: ((q[0] - lo[0]) * S, H - (q[1] - lo[1]) * S)
    for f in fills:
        dr.polygon([P(q) for q in f], fill=(255, 150, 150))
    dr.line([P(q) for q in list(xy) + [xy[0]]], fill=(0, 0, 200), width=2)
    for r in rows:
        dr.text(P(r["at"]), "%.2f" % r["depth_m"], fill=(200, 0, 0) if r["decision"] == "fill" else (0, 140, 0))
    im.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("floor")
    ap.add_argument("out")
    ap.add_argument("--fill")
    ap.add_argument("--texture-depth", type=float, default=0.4)
    ap.add_argument("--pocket-close", type=float, default=3.0)
    ap.add_argument("--png")
    a = ap.parse_args(argv)
    outs = [p for p in (a.out, a.fill, a.png) if p]
    if os.path.realpath(a.floor) in {os.path.realpath(p) for p in outs}:
        sys.exit("refused: an output equals the input")
    spec = json.load(open(a.floor, encoding="utf-8"))
    xy = spec["rings"][0]["xy"]
    rows, fills = census(xy, a.texture_depth, a.pocket_close)
    verdict = "fail" if fills else "pass"
    rep = {"floor": os.path.basename(a.floor), "texture_depth_m": a.texture_depth, "pocket_close_m": a.pocket_close,
           "pockets": rows, "fill": len(fills), "keep": sum(r["decision"] == "keep" for r in rows), "verdict": verdict,
           "reference": "Revit facade (site 63 has no etalon)"}
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    if a.fill and fills:
        with open(a.fill, "x", encoding="utf-8") as f:
            json.dump({"frame": "source", "polygons": fills}, f)
    if a.png:
        _plot(a.png, xy, rows, fills)
    print(json.dumps({k: rep[k] for k in ("fill", "keep", "verdict")}))
    if verdict == "fail":
        sys.exit(2)


if __name__ == "__main__":
    main()
