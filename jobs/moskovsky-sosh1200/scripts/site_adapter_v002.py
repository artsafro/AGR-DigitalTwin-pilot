"""Typed SPOZU adapter JSONs (GPZU + uncut) for Ground v002, moskovsky-sosh1200.

Pattern: n/a | new-case: v002 merges two DWGs (main SPOZU + architects' rubber spec `_ резинаV1_1.dwg`) and the
user's 2026-11-26 v001 review (one lawn cover, no footprint hole, rubber zones by colour). The DXF route of
`agr ground site` reads one DXF and one bg colour per cover, so covers are read here by the core reader
(``ground_site._placed_hatch_polygon``), merged per cover and written as the core's typed adapter
(``coverings`` / ``boundary`` / ``elevations``). No geometry is built here.

usage: uv run --extra cad python jobs/moskovsky-sosh1200/scripts/site_adapter_v002.py COVERS.json NEW_DIR [--join 1.0]
COVERS.json: {"main_dxf": {path, sha256}, "rubber_dxf": {path, sha256}, "gpzu_handle", "region_xy": [x0, y0, x1, y1],
              "covers": [{"id", "name", "colour", "colour_reason", "main": [{handle, insert_chain, self_touching?}],
                          "rubber_layer": "..."}]}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ezdxf
from shapely.geometry import box, mapping, Polygon
from shapely.ops import unary_union

from dt_ai.geometry import ground_site as gs


def hatch_poly(doc, h, chain, policy):
    try:
        return gs._placed_hatch_polygon(doc, doc.entitydb[h], chain, 0.02), None
    except ValueError:
        if policy != "even-odd":
            raise
        return gs._placed_hatch_polygon(doc, doc.entitydb[h], chain, 0.02, "even-odd"), "even-odd"


def derived_uncut(gpzu, parts, join):
    grown, left = gpzu, list(parts)
    changed = True
    while changed:
        changed = False
        for p in list(left):
            if p.distance(grown) <= join:
                grown = unary_union([grown, p]); left.remove(p); changed = True
    closed = grown.buffer(join / 2, join_style="mitre").buffer(-join / 2, join_style="mitre")
    big = max(getattr(closed, "geoms", [closed]), key=lambda g: g.area)
    return Polygon(big.exterior.coords), left


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("covers", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--join", type=float, default=1.0)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists: give a new versioned path")
    cfg = json.loads(a.covers.read_text(encoding="utf-8"))
    docs = {}
    for key in ("main_dxf", "rubber_dxf"):
        p = Path(cfg[key]["path"])
        if gs.sha256(p) != cfg[key]["sha256"]:
            raise SystemExit(f"{p}: sha256 differs")
        docs[key] = ezdxf.readfile(str(p))
    main_doc, rub = docs["main_dxf"], docs["rubber_dxf"]
    region = box(*cfg["region_xy"])
    gpzu = gs.boundary_from_dxf(main_doc, cfg["gpzu_handle"])
    cov, rows, seen = {}, [], set()
    for c in cfg["covers"]:
        polys, src = [], []
        for r in c.get("main", []):
            g, pol = hatch_poly(main_doc, r["handle"], r["insert_chain"], r.get("self_touching"))
            polys.append(g); src.append({"dxf": "main", "handle": r["handle"], "insert_chain": r["insert_chain"],
                                         "policy": pol, "m2": round(g.area, 3)})
        if c.get("rubber_layer"):
            for e in rub.modelspace().query("HATCH"):
                if e.dxf.layer != c["rubber_layer"]:
                    continue
                g, pol = hatch_poly(rub, e.dxf.handle, [], "even-odd")
                if not g.intersects(region):  # legend samples far from the site
                    src.append({"dxf": "rubber", "handle": e.dxf.handle, "skipped": "outside site region (legend)"})
                    continue
                polys.append(g); src.append({"dxf": "rubber", "handle": e.dxf.handle, "policy": pol, "m2": round(g.area, 3)})
        for s in src:
            key = (s["dxf"], s["handle"])
            if key in seen:
                raise SystemExit(f"hatch {key} named twice")
            seen.add(key)
        cov[c["id"]] = unary_union(polys)
        rows.append({"id": c["id"], "name": c["name"], "colour": c["colour"], "colour_reason": c["colour_reason"],
                     "sources": src, "m2": round(cov[c["id"]].area, 3)})
    outside = unary_union(list(cov.values())).difference(gpzu)
    uncut, left = derived_uncut(gpzu, list(getattr(outside, "geoms", [outside])), a.join)
    a.out.mkdir(parents=True)
    summary = {}
    for name, bnd in (("gpzu", gpzu), ("uncut", uncut)):
        ring = list(bnd.exterior.coords)[:-1]
        d = {"schema": "spozu-adapter-v002/1 (job-side)", "covers_config": str(a.covers),
             "covers_config_sha256": gs.sha256(a.covers),
             "sources": {k: cfg[k] for k in ("main_dxf", "rubber_dxf")}, "gpzu_handle": cfg["gpzu_handle"],
             "boundary_rule": "GPZU LWPOLYLINE" if name == "gpzu" else
             f"GPZU union cover parts outside GPZU within {a.join} m (iterative), closed +/-{a.join / 2} m, exterior",
             "boundary_m2": bnd.area, "rows": rows,
             "left_out_parts": [{"m2": round(p.area, 3), "xy": [round(v, 2) for v in p.representative_point().coords[0]]}
                                for p in left] if name == "uncut" else [],
             "boundary": mapping(bnd),
             "coverings": {str(i): {"geometry": mapping(g)} for i, g in cov.items()},
             "elevations": [{"x": x, "y": y, "z": 0.0, "source": "boundary vertex, flat datum (synthetic, not survey)"}
                            for x, y in ring]}
        (a.out / f"adapter_{name}.json").write_text(json.dumps(d, ensure_ascii=False) + "\n", encoding="utf-8")
        summary[name] = {"boundary_m2": round(bnd.area, 2),
                         "cover_m2_in": {r["id"]: round(cov[r["id"]].intersection(bnd).area, 2) for r in rows}}
    summary["left_out"] = [round(p.area, 1) for p in left]
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
