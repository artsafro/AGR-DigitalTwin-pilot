"""Typed SPOZU adapter JSON for the UNCUT Ground (site + adjacent stadium), moskovsky-sosh1200 ground-npm v001.

Pattern: n/a | new-case: the DWG has no closed polyline around "GPZU + stadium", so the uncut boundary is DERIVED:
union of the GPZU polygon with every source cover part outside GPZU that lies within ``--join`` metres of it (grown
iteratively), closed by +/-``--join``/2 buffer, exterior ring only. Covers are read by the core reader
(``ground_site.covers_from_dxf``) from the SAME cover rows as the GPZU spec, so IDs/handles/polygons are identical;
the adapter feeds ``agr ground site`` (``adapter`` source) - no geometry is built here.

usage: uv run --extra cad python jobs/moskovsky-sosh1200/scripts/uncut_adapter.py GPZU_SPEC.json NEW_ADAPTER.json [--join 1.0]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ezdxf
from shapely.geometry import mapping
from shapely.ops import unary_union

from dt_ai.geometry import ground_site as gs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--join", type=float, default=1.0)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists: give a new versioned path")
    spec = gs.load_spec(a.spec)
    dxf = Path(spec["dxf"]["path"])
    if gs.sha256(dxf) != spec["dxf"]["sha256"]:
        raise SystemExit("DXF sha256 differs from the spec")
    doc = ezdxf.readfile(str(dxf))
    gpzu = gs.boundary_from_dxf(doc, spec["boundary"]["handle"])
    covers = gs.covers_from_dxf(doc, spec["covers"], max(float(spec["params"].get("chord", 0.02)), 0.002))
    outside = unary_union([p for c in covers for p in c.polygons]).difference(gpzu)
    parts = list(getattr(outside, "geoms", [outside]))
    grown, joined, left = gpzu, [], list(parts)
    changed = True
    while changed:
        changed = False
        for p in list(left):
            if p.distance(grown) <= a.join:
                grown = unary_union([grown, p])
                joined.append(p)
                left.remove(p)
                changed = True
    closed = grown.buffer(a.join / 2, join_style="mitre").buffer(-a.join / 2, join_style="mitre")
    polys = sorted(getattr(closed, "geoms", [closed]), key=lambda g: -g.area)
    boundary = type(polys[0])(polys[0].exterior.coords)
    ring = list(boundary.exterior.coords)[:-1]
    z = 0.0  # flat: skipped relief, confirmed by user 2026-11-26; local Z 0 = ±0.000
    out = {
        "schema": "spozu-adapter-uncut/1 (job-side)",
        "source": {"dxf": str(dxf), "dxf_sha256": spec["dxf"]["sha256"], "gpzu_handle": spec["boundary"]["handle"],
                   "spec": str(a.spec), "spec_sha256": gs.sha256(a.spec)},
        "boundary_rule": f"GPZU union cover parts outside GPZU within {a.join} m (iterative), closed +/-{a.join / 2} m, exterior",
        "boundary_m2": boundary.area, "gpzu_m2": gpzu.area,
        "joined_outside_parts_m2": sorted(round(p.area, 3) for p in joined),
        "left_out_parts": [{"m2": round(p.area, 3), "xy": [round(v, 2) for v in p.representative_point().coords[0]],
                            "distance_m": round(p.distance(grown), 3)} for p in left],
        "boundary": mapping(boundary),
        "coverings": {str(c.id): {"name": c.name, "colour": list(c.colour), "sources": c.sources,
                                  "geometry": mapping(unary_union(c.polygons))} for c in covers},
        "elevations": [{"x": x, "y": y, "z": z, "source": "uncut boundary vertex, flat datum (synthetic, not survey)"}
                       for x, y in ring],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"boundary_m2": round(boundary.area, 2), "joined": out["joined_outside_parts_m2"],
                      "left_out": out["left_out_parts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
