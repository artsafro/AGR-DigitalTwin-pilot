"""KPP1 R1 rerun #1230 (after #1209): kernel parts + L01 openings + ALL L01 mullions + the east Stair, offline.

Pattern: new-case: real-object OKS body from the АС.03 drawings on the offline kernel route (`path: deviation`,
Max busy); extends jobs/KPP1/rerun-1209/build_parts.py (bands, openings, cutters are reused unchanged).

    uv run python jobs/KPP1/rerun-1230/build_parts.py <plan-contours-L03.json> <L01.dxf> <L03.dxf> <out parts.json>

Changes against #1209 (issue #1230):
- mullions: every `A-GLAZ-CWMG-OTLN` 'Прямоугольный импост' insert of L01 becomes a box. A zero-width insert
  bbox (a line in the view) takes the face width of its profile (`200х75` -> 75 mm, `50х100` -> 50 mm). A
  mullion whose facade centre lies in an opening sits in that opening's glass plane (depth = profile depth,
  centred); any other mullion stands on the first body face (profile depth outward, 10 mm embedded so the
  union is solid). An insert that hits no body face is reported in `mullions_dropped` with its reason;
  nothing is dropped silently (#1209 dropped zero-width inserts and kept 7 of 171).
- Stair: the exterior stair at the east facade from L03 `S-STRS-____-OTLN` (plan: flight 1 treads x 55215..57215,
  y 2320..3680 mm) and L01 (Восточный / Южный views: landing +2.100, upper flight along the wall to the
  landing +3.600..+3.900, width 1 200 mm, 300 mm from the wall). Rises are approximations of the facade
  rungs (flight 1: 2.100 / 9, flight 2: 1.800 / 9); stringers and railings are not modelled.
Fail-closed: a stair source with no S-STRS lines in the plan window, an unknown mullion profile with a
zero-width bbox, a non-finite coordinate -> SystemExit naming it; output equal to an input -> exit 4.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from pathlib import Path

import ezdxf
import numpy as np
from ezdxf import bbox
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("kpp1_r1209_parts", HERE.parent / "rerun-1209" / "build_parts.py")
R9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R9)

GLASS_BACK = 0.08                    # glass plane in front of the recess back (build_blender FRAME / GLASS)
PROFILES = {"200х75": (0.075, 0.200), "50х100": (0.050, 0.100)}   # face width, depth (m)
EMBED_M = 0.010
L03_ORIGIN_MM = 25884.5              # plan_from_dxf --origin-mm (Revit x = (X - origin) / 1000)
STAIR_WINDOW_MM = (54000.0, 1500.0, 58000.0, 4500.0)   # L03 plan window east of the wall (x0, y0, x1, y1)


def profile_of(name: str) -> tuple[float, float]:
    for key, val in PROFILES.items():
        if key in name:
            return val
    raise SystemExit(f"unknown mullion profile in block {name!r}")


def mullion_items(dxf_path: Path):
    doc = ezdxf.readfile(str(dxf_path))
    out = []
    for e in doc.modelspace().query("INSERT"):
        if e.dxf.layer != R9.MULLION_LAYER:
            continue
        m = re.search(r"О_АР_Ф_(\w+)$", e.dxf.name)
        if not m:
            continue
        f = m.group(1)
        if f not in R9.FACADES:
            raise SystemExit(f"unknown facade suffix {f!r} in block {e.dxf.name!r}")
        b = bbox.extents([e])
        if not b.has_data:
            out.append({"facade": f, "block": e.dxf.name, "rect": None})
            continue
        r = (b.extmin.x, b.extmax.x, b.extmin.y, b.extmax.y)
        R9._fin(*r)
        out.append({"facade": f, "block": e.dxf.name, "rect": r})
    return out


def place_mullions(bands, items, sched, report):
    rep = {r["id"]: r for r in report}
    boxes, drops = [], []
    for it in items:
        f, name = it["facade"], it["block"]
        if it["rect"] is None:
            drops.append({"facade": f, "block": name, "reason": "insert has no geometry (empty bbox)"})
            continue
        width, depth = profile_of(name)
        x0, x1, z0, z1 = it["rect"]
        u = R9.FACADES[f]["u"]
        ua, ub = sorted((u(x0), u(x1)))
        za, zb = max(z0, 0.0) / 1000.0, z1 / 1000.0
        if ub - ua < 1e-4:
            c = (ua + ub) / 2
            ua, ub = c - width / 2, c + width / 2
        if zb - za < 1e-4:
            c = (za + zb) / 2
            za, zb = c - width / 2, c + width / 2
        cu, cz = (ua + ub) / 2, (za + zb) / 2
        host = next((r for r in report if r["facade"] == f and r["u_m"][0] - 1e-3 <= cu <= r["u_m"][1] + 1e-3
                     and r["z_m"][0] - 1e-3 <= cz <= r["z_m"][1] + 1e-3), None)
        if host is not None:
            # clip to the opening so the member stays inside the reveal
            ua, ub = max(ua, host["u_m"][0]), min(ub, host["u_m"][1])
            za, zb = max(za, host["z_m"][0]), min(zb, host["z_m"][1])
            plane = host["back_depth_m"] - GLASS_BACK
            d0, d1, mode = plane - depth / 2, plane + depth / 2, f"in opening {host['id']}"
        else:
            hit = R9.first_hit(bands, f, cu, cz)
            if hit is None:
                span = (-0.33, 27.33) if R9.FACADES[f]["axis"] == "y" else (-0.33, 11.33)
                edge_on = ub <= span[0] + 1e-3 or ua >= span[1] - 1e-3
                drops.append({"facade": f, "block": name, "rect_m": [ua, ub, za, zb],
                              "reason": ("edge-on view beyond the facade end: a member of the perpendicular facade"
                                         if edge_on else "no body face behind it (outside the plan)")})
                continue
            d0, d1, mode = hit - depth, hit + EMBED_M, "on the facade"
        if ub - ua <= 0 or zb - za <= 0:
            drops.append({"facade": f, "block": name, "rect_m": [ua, ub, za, zb], "reason": "empty after clipping"})
            continue
        boxes.append({"facade": f, "block": name, "placement": mode, **R9.cutter(f, (ua, ub, za, zb), d0, d1)})
    del rep
    return boxes, drops


def stair_boxes(l03_path: Path):
    """East exterior stair (object frame, m). Plan treads from L03; heights from the L01 facades."""
    doc = ezdxf.readfile(str(l03_path))
    x0w, y0w, x1w, y1w = STAIR_WINDOW_MM
    lines = []
    for e in doc.modelspace().query('LINE[layer=="S-STRS-____-OTLN"]'):
        s, t = e.dxf.start, e.dxf.end
        if x0w <= min(s.x, t.x) and max(s.x, t.x) <= x1w and y0w <= min(s.y, t.y) and max(s.y, t.y) <= y1w:
            lines.append((s.x, s.y, t.x, t.y))
    if not lines:
        raise SystemExit("L03: no S-STRS-____-OTLN lines in the east stair window")
    risers = sorted({round(a) for a, b, c, d in lines if abs(a - c) < 1 and abs(b - d) > 500})
    xs = [x for x in risers if 55200 <= x <= 57300]
    tread_y = sorted({round(b) for a, b, c, d in lines if abs(b - d) < 1 and abs(a - c) < 300})
    if len(xs) < 2 or not tread_y:
        raise SystemExit(f"L03 stair: risers {xs} / tread edges {tread_y} not readable")
    y0, y1 = min(tread_y) / 1000.0, max(tread_y) / 1000.0           # 2.400 .. 3.600 (tread width 1.2 m)
    rx = lambda X: (X - L03_ORIGIN_MM) / 1000.0
    out = []
    n1 = len(xs) - 1                                                   # treads of flight 1
    for k in range(n1):                                                # from the east (low) end westwards
        xa, xb = rx(xs[-2 - k]), rx(xs[-1 - k])
        out.append(("F1", (xa, y0, 0.0), (xb, y1, 2.1 * (k + 1) / (n1 + 1))))
    land_x0 = 27.63                                                    # L01 Южный: upper flight u 27.630..28.830
    out.append(("Landing_2100", (land_x0, y0, 0.0), (rx(xs[0]), y1, 2.1)))
    n2 = 8
    run = (5.60 - y1) / n2                                             # L01 Восточный: flight 2 u 3.600 .. 5.600
    for k in range(n2):
        top = 2.1 + 1.8 * (k + 1) / (n2 + 1)
        out.append(("F2", (land_x0, y1 + run * k, top - 0.35), (28.83, y1 + run * (k + 1), top)))
    out.append(("Landing_3900", (27.30, 5.60, 3.6), (28.83, 8.58, 3.9)))  # 30 mm into the east wall plane 27.33
    sx, sy = R9.SHIFT
    res = []
    for name, lo, hi in out:
        R9._fin(*lo, *hi)
        res.append({"name": name, "min": [round(lo[0] + sx, 4), round(lo[1] + sy, 4), round(lo[2], 4)],
                    "max": [round(hi[0] + sx, 4), round(hi[1] + sy, 4), round(hi[2], 4)]})
    return res, {"risers_x_mm": xs, "tread_y_mm": [min(tread_y), max(tread_y)], "lines": len(lines)}


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    plan_p, l01_p, l03_p, out_p = (Path(a) for a in argv)
    if out_p.resolve() in (plan_p.resolve(), l01_p.resolve(), l03_p.resolve()):
        print("output resolves to an input", file=sys.stderr)
        return 4
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    bands = R9.bands_from_plan(plan)
    opens, _ = R9.facade_items(l01_p)
    sched, report, drops, _ = R9.schedule(bands, opens, {f: [] for f in R9.FACADES})
    items = mullion_items(l01_p)
    mboxes, mdrops = place_mullions(bands, items, sched, report)
    stair, stair_src = stair_boxes(l03_p)
    rect = box(*R9.L1_RECT)
    inner = rect.buffer(-R9.PARAPET_T_M, join_style="mitre")
    gaps = rect.difference(bands[0][0])
    recess = max(getattr(gaps, "geoms", [gaps]), key=lambda g: g.area)
    md = R9.mesh_dict
    ext = R9.extrude_polygon
    parts = {
        "body_bands": [{"name": n, "z": [z0, z1], **md(ext(p, 2, z0, z1 - z0))} for p, z0, z1, n in bands],
        "Parapet": md(ext(rect.difference(inner), 2, R9.ROOF_BASE_M, R9.PARAPET_TOP_M - R9.ROOF_BASE_M)),
        "Roof_Plate": md(ext(inner, 2, R9.ROOF_BASE_M, R9.LEVELS[2] - R9.ROOF_BASE_M)),
    }
    out = {"schema": "kpp1-rerun-parts/2", "issue": 1230, "decision": "D238", "synthetic": False,
           "levels_m": list(R9.LEVELS), "levels_note": "from Revit, not confirmed by the architect for R1 [D238]",
           "roof_provisional_note": R9.ROOF_PROVISIONAL_NOTE,
           "params": {"roof_base_m": R9.ROOF_BASE_M, "parapet_top_m": R9.PARAPET_TOP_M, "parapet_t_m": R9.PARAPET_T_M,
                      "frame_top_m": R9.FRAME_TOP_M, "recess_m": [round(recess.bounds[0], 4), round(recess.bounds[2], 4),
                                                                  round(recess.bounds[3], 4)],
                      "l1_rect_m": R9.L1_RECT, "merge_mm": R9.MERGE_MM, "cut_depth_m": R9.CUT_DEPTH_M},
           "band_areas_m2": {n: round(p.area, 3) for p, _, _, n in bands},
           "openings": sched, "openings_report": report, "openings_dropped": drops,
           "mullion_inserts": len(items), "mullions": mboxes, "mullions_dropped": mdrops,
           "stair": stair, "stair_source": stair_src,
           "stair_note": "rises approximated from the L01 facade rungs; stringers / railings not modelled",
           "parts": parts}
    for b in mboxes + stair:
        for v in b["min"] + b["max"]:
            if not math.isfinite(v):
                raise SystemExit(f"non-finite coordinate in {b}")
    out_p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(json.dumps({"openings": len(sched), "dropped": len(drops), "mullion_inserts": len(items),
                      "mullions": len(mboxes), "mullions_dropped": len(mdrops), "stair_boxes": len(stair),
                      "placement": {k: sum(1 for b in mboxes if b["placement"].startswith(k[:2]))
                                    for k in ("in opening", "on the facade")}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":

    sys.exit(main(sys.argv[1:]))
