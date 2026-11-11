"""KPP1 rerun after Gate 1 [D238] (#1209): kernel part meshes + L01 opening schedule, offline (Max busy).

Pattern: new-case: real-object OKS body from the АС.03 drawings on the offline kernel route (`path: deviation`
from the oks-vpm Max AGR Tools route; reason: Max busy).

    uv run python jobs/KPP1/rerun-1209/build_parts.py <plan-contours-L03.json> <L01.dxf> <out parts-mesh.json>

[D238] answers used here:
1. band 0.000-3.900 = the L03 hatch contour (plan_from_dxf output, band 0), but the 0.70 m entrance-frame bumps
   (hatch minus the L1 rectangle) stop at the frame top read from L01 (`FRAME_TOP_M`, the +3.300 hatch band
   of the facade frames); band 3.900-ROOF_BASE = the L1 rectangle 27.66 x 11.66 m.
2. openings = the L01 facade glazing / door inserts (layers in OPENING_LAYERS), merged per facade into
   rectangles; each becomes an axis-aligned cutter box whose depth starts at the first body face hit along the
   facade normal (so recessed walls are cut too).
5. levels 3.900 / 7.909 from object.json (Revit), not confirmed by the architect for R1.

Fail-closed: a facade without openings, an opening outside every band, a cutter that hits no body face, an
unknown facade suffix, a non-finite coordinate -> SystemExit naming it; output equal to an input -> exit 4.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import ezdxf
import numpy as np
import shapely
from ezdxf import bbox
from shapely.geometry import LineString, box

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.ops.contour import extrude_polygon  # noqa: E402

LEVELS = (0.0, 3.9, 7.909)          # object.json (Revit) [D238] 5
ROOF_BASE_M = 7.700                 # provisional roof slab base [D249]; Revit level, not architect-confirmed
PARAPET_TOP_M = 8.650               # L01 mark +8,650 on all four facades
PARAPET_T_M = 0.35                  # provisional user approval [D249], not an architect-confirmed dimension
ROOF_PROVISIONAL_NOTE = "provisional, not confirmed by drawings/architect [D249]"
FRAME_TOP_M = 3.300                 # L01 Южный: frame hatch band +2,700..+3,300 at the entrance frames
SHIFT = (-14.655, -5.355)           # Revit -> object frame (object.json SM_Kpp_1.fbx inverse)
L1_RECT = (-0.33 + SHIFT[0], -0.33 + SHIFT[1], 27.33 + SHIFT[0], 11.33 + SHIFT[1])  # 27.66 x 11.66 m
OPENING_LAYERS = {"A-GLAZ-CURT-OTLN": "window", "A-GLAZ-____-OTLN": "window", "A-DOOR-____-OTLN": "door"}
MULLION_LAYER = "A-GLAZ-CWMG-OTLN"
MERGE_MM = 40.0                     # inserts closer than this merge into one opening
MIN_OPENING_MM = 300.0
CUT_DEPTH_M = 0.30                  # recess depth behind the first face hit
# facade view placement on L01 (grid lines S-GRID-____-OTLN): drawing X -> Revit u (m), sign, plane
FACADES = {
    "Южный":    {"u": lambda X: X / 1000.0,              "axis": "y", "outer": -0.33, "normal": -1},
    "Северный": {"u": lambda X: (70955.0 - X) / 1000.0,  "axis": "y", "outer": 11.33, "normal": +1},
    "Западный": {"u": lambda X: (92848.0 - X) / 1000.0,  "axis": "x", "outer": -0.33, "normal": -1},
    "Восточный": {"u": lambda X: (X - 102956.0) / 1000.0, "axis": "x", "outer": 27.33, "normal": +1},
}


def _fin(*vals):
    for v in vals:
        if not math.isfinite(v):
            raise SystemExit(f"non-finite coordinate {v!r}")


def bands_from_plan(plan: dict) -> list[tuple[shapely.Polygon, float, float, str]]:
    b0 = plan["bands"][0]
    if len(b0["polygons"]) != 1:
        raise SystemExit(f"band 0 has {len(b0['polygons'])} polygons, expected one footprint")
    p = b0["polygons"][0]
    hatch = shapely.Polygon(p["exterior"], p.get("holes", []))
    rect = box(*L1_RECT)
    core = hatch.intersection(rect)
    bumps = hatch.difference(rect)
    out = [(core, LEVELS[0], LEVELS[1], "core_0_3900")]
    for i, g in enumerate(sorted((g for g in getattr(bumps, "geoms", [bumps]) if g.area > 0.01),
                                 key=lambda g: g.bounds)):
        out.append((g, LEVELS[0], FRAME_TOP_M, f"bump_{i}"))
    out.append((rect, LEVELS[1], ROOF_BASE_M, "l1_rect_3900_7700"))
    return out


def facade_items(dxf_path: Path):
    doc = ezdxf.readfile(str(dxf_path))
    opens, mulls = {f: [] for f in FACADES}, {f: [] for f in FACADES}
    for e in doc.modelspace().query("INSERT"):
        m = re.search(r"О_АР_Ф_(\w+)$", e.dxf.name)
        lay = e.dxf.layer
        if not m or (lay not in OPENING_LAYERS and lay != MULLION_LAYER):
            continue
        f = m.group(1)
        if f not in FACADES:
            raise SystemExit(f"unknown facade suffix {f!r} in block {e.dxf.name!r}")
        b = bbox.extents([e])
        if not b.has_data:
            continue
        r = (b.extmin.x, b.extmax.x, b.extmin.y, b.extmax.y)
        _fin(*r)
        (mulls if lay == MULLION_LAYER else opens)[f].append((r, OPENING_LAYERS.get(lay, "mullion"), e.dxf.name))
    return opens, mulls


def merge_openings(items):
    """Union of the insert boxes (grown by MERGE_MM / 2) -> one rectangle per connected group; kind door wins."""
    polys = [box(r[0], r[2], r[1], r[3]).buffer(MERGE_MM / 2, join_style="mitre") for r, _, _ in items]
    groups = shapely.unary_union(polys)
    out = []
    for g in getattr(groups, "geoms", [groups]):
        x0, z0, x1, z1 = g.buffer(-MERGE_MM / 2, join_style="mitre").bounds
        kinds = {k for (r, k, _), p in zip(items, polys) if p.intersects(g)}
        out.append(((x0, x1, z0, z1), "door" if "door" in kinds else "window"))
    return out


def first_hit(bands, f: str, u: float, z: float) -> float | None:
    """Signed depth (m, inward from the outer cassette plane) of the first body face along the facade normal."""
    cfg = FACADES[f]
    inward = -cfg["normal"]
    far = cfg["outer"] - inward * 2.0
    best = None
    for poly, z0, z1, _ in bands:
        if not (z0 - 1e-6 <= z <= z1 + 1e-6):
            continue
        a = cfg["outer"] - inward * 2.0
        b = cfg["outer"] + inward * 20.0
        pu = u + SHIFT[0] if cfg["axis"] == "y" else u + SHIFT[1]
        sh = SHIFT[1] if cfg["axis"] == "y" else SHIFT[0]
        seg = (LineString([(pu, a + sh), (pu, b + sh)]) if cfg["axis"] == "y"
               else LineString([(a + sh, pu), (b + sh, pu)]))
        hit = seg.intersection(poly.exterior)
        pts = [hit] if hit.geom_type == "Point" else list(getattr(hit, "geoms", []))
        for p in pts:
            c = (p.y - sh) if cfg["axis"] == "y" else (p.x - sh)
            d = (c - cfg["outer"]) * inward
            if best is None or d < best:
                best = d
    del far
    return best


def cutter(f: str, rect_m, d0: float, d1: float) -> dict:
    cfg = FACADES[f]
    u0, u1, z0, z1 = rect_m
    inward = -cfg["normal"]
    c0, c1 = sorted((cfg["outer"] + inward * d0, cfg["outer"] + inward * d1))
    if cfg["axis"] == "y":
        lo, hi = [u0 + SHIFT[0], c0 + SHIFT[1], z0], [u1 + SHIFT[0], c1 + SHIFT[1], z1]
    else:
        lo, hi = [c0 + SHIFT[0], u0 + SHIFT[1], z0], [c1 + SHIFT[0], u1 + SHIFT[1], z1]
    return {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]}


def schedule(bands, opens, mulls):
    sched, report, drops, mboxes = [], [], [], []
    for f in FACADES:
        if not opens[f]:
            raise SystemExit(f"facade {f}: no opening inserts on L01")
        u = FACADES[f]["u"]
        for (x0, x1, z0, z1), kind in merge_openings(opens[f]):
            ua, ub = sorted((u(x0), u(x1)))
            za, zb = max(z0, 0.0) / 1000.0, z1 / 1000.0
            w, h = (ub - ua) * 1000, (zb - za) * 1000
            if w < MIN_OPENING_MM or h < MIN_OPENING_MM:
                drops.append({"facade": f, "rect_m": [ua, ub, za, zb], "reason": f"smaller than {MIN_OPENING_MM} mm"})
                continue
            hits = [first_hit(bands, f, uu, zz) for uu in (ua + 0.05, (ua + ub) / 2, ub - 0.05)
                    for zz in (za + 0.05, (za + zb) / 2, zb - 0.05)]
            hits = [h_ for h_ in hits if h_ is not None]
            if not hits:
                drops.append({"facade": f, "rect_m": [ua, ub, za, zb], "reason": "no body face behind it (outside the plan)"})
                continue
            d0 = min(hits)
            oid = f"{f[:1]}{len(sched):02d}"
            sched.append({"id": oid, **cutter(f, (ua, ub, za, zb), d0 - 0.5, max(hits) + CUT_DEPTH_M)})
            report.append({"id": oid, "facade": f, "kind": kind, "u_m": [round(ua, 3), round(ub, 3)],
                           "z_m": [round(za, 3), round(zb, 3)], "face_depth_m": round(d0, 3),
                           "back_depth_m": round(max(hits) + CUT_DEPTH_M, 3)})
        for (x0, x1, z0, z1), _, _ in mulls[f]:
            ua, ub = sorted((u(x0), u(x1)))
            za, zb = max(z0, 0.0) / 1000.0, z1 / 1000.0
            if ub - ua <= 0 or zb - za <= 0:
                continue
            hit = first_hit(bands, f, (ua + ub) / 2, (za + zb) / 2)
            if hit is None:
                continue
            mboxes.append({"facade": f, **cutter(f, (ua, ub, za, zb), hit + CUT_DEPTH_M - 0.12, hit + CUT_DEPTH_M - 0.02)})
    return sched, report, drops, mboxes


def mesh_dict(m):
    return {"vertices": np.round(np.asarray(m.vertices), 5).tolist(), "triangles": np.asarray(m.triangles).tolist()}


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    plan_p, dxf_p, out_p = (Path(a) for a in argv)
    if out_p.resolve() in (plan_p.resolve(), dxf_p.resolve()):
        print("output resolves to an input", file=sys.stderr)
        return 4
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    bands = bands_from_plan(plan)
    opens, mulls = facade_items(dxf_p)
    sched, report, drops, mboxes = schedule(bands, opens, mulls)
    rect = box(*L1_RECT)
    inner = rect.buffer(-PARAPET_T_M, join_style="mitre")
    gaps = rect.difference(bands[0][0])
    recess = max(getattr(gaps, "geoms", [gaps]), key=lambda g: g.area)   # the south recess under the L1 band
    parts = {
        "body_bands": [{"name": n, "z": [z0, z1], **mesh_dict(extrude_polygon(p, 2, z0, z1 - z0))} for p, z0, z1, n in bands],
        "Parapet": mesh_dict(extrude_polygon(rect.difference(inner), 2, ROOF_BASE_M, PARAPET_TOP_M - ROOF_BASE_M)),
        "Roof_Plate": mesh_dict(extrude_polygon(inner, 2, ROOF_BASE_M, LEVELS[2] - ROOF_BASE_M)),
    }
    out = {"schema": "kpp1-rerun-parts/1", "decision": "D238", "synthetic": False,
           "levels_m": list(LEVELS), "levels_note": "from Revit, not confirmed by the architect for R1 [D238]",
           "roof_provisional_note": ROOF_PROVISIONAL_NOTE,
           "params": {"roof_base_m": ROOF_BASE_M, "parapet_top_m": PARAPET_TOP_M, "parapet_t_m": PARAPET_T_M,
                      "frame_top_m": FRAME_TOP_M, "recess_m": [round(recess.bounds[0], 4), round(recess.bounds[2], 4), round(recess.bounds[3], 4)], "recess_area_m2": round(recess.area, 3), "l1_rect_m": L1_RECT, "merge_mm": MERGE_MM, "cut_depth_m": CUT_DEPTH_M},
           "band_areas_m2": {n: round(p.area, 3) for p, _, _, n in bands},
           "openings": sched, "openings_report": report, "openings_dropped": drops, "mullions": mboxes,
           "parts": parts}
    out_p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8", newline="\n")
    kinds = {}
    for r in report:
        kinds[(r["facade"], r["kind"])] = kinds.get((r["facade"], r["kind"]), 0) + 1
    print(json.dumps({"bands": out["band_areas_m2"], "openings": len(sched), "by_facade": {f"{a}/{b}": n for (a, b), n in kinds.items()},
                      "dropped": len(drops), "mullions": len(mboxes)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
