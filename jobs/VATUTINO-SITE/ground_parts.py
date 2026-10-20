"""Gate-1 parts summary for the Vatutino Ground (issue #295, [D125]).

Pattern: n/a | new-case: job script; reads the #195 adapter JSON (`adapters.cad.spozu --json`), builds no mesh.

Reads one or more `ground_inputs.json` files written by `python -m adapters.cad.spozu ... --json` and prints
(or writes) one JSON summary per file: boundary, covering areas and parts, the uncovered remainder of the plot,
the base covering, elevation statistics (duplicate XY, contradictory Z, collinearity) and the adapter findings
grouped by code and layer, each self-intersection tagged inside/outside the boundary bbox. It does not parse
DXF (no second parser) and repairs nothing.

Usage:
    uv run --extra cad python jobs/VATUTINO-SITE/ground_parts.py paving=C:/x/<card>/paving_ground_inputs.json \
        main=C:/x/<card>/main_ground_inputs.json --out jobs/VATUTINO-SITE/ground-parts.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union

# reg p.28-29 §3.10 (GND-06): (upper bound in ha, triangle limit); the last row is "more than 1.5 ha".
GND06_TABLE = [
    (0.05, 300_000),
    (0.1, 705_000),
    (0.25, 1_125_000),
    (0.5, 1_650_000),
    (0.75, 1_950_000),
    (1.0, 2_625_000),
    (1.5, 3_150_000),
    (math.inf, 4_500_000),
]

_XY = re.compile(r"\[(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)\]")


def gnd06_limit(area_m2: float) -> int:
    if not math.isfinite(area_m2) or area_m2 <= 0:
        raise ValueError(f"GND-06 needs a positive finite area, got {area_m2!r}")
    ha = area_m2 / 10_000.0
    for upper, limit in GND06_TABLE:
        if ha <= upper:
            return limit
    raise AssertionError("unreachable")


def _parts(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def elevation_stats(points: list[dict], xy_tol: float = 1e-3) -> dict:
    inside = [p for p in points if p.get("inside")]
    groups: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for p in inside:
        groups[(round(p["x"] / xy_tol), round(p["y"] / xy_tol))].append(p)
    duplicates_same_z = []
    contradictory = []
    for members in groups.values():
        if len(members) < 2:
            continue
        zs = sorted({round(m["z"], 4) for m in members})
        entry = {"x": members[0]["x"], "y": members[0]["y"], "z": zs, "refs": [m["ref"] for m in members]}
        (contradictory if len(zs) > 1 else duplicates_same_z).append(entry)
    distinct = [(m[0]["x"], m[0]["y"]) for m in groups.values()]
    collinear = True
    if len(distinct) >= 3:
        x0, y0 = distinct[0]
        far = max(distinct, key=lambda q: (q[0] - x0) ** 2 + (q[1] - y0) ** 2)
        dx, dy = far[0] - x0, far[1] - y0
        norm = math.hypot(dx, dy)
        if norm > 0:
            collinear = all(abs((q[0] - x0) * dy - (q[1] - y0) * dx) / norm < 0.01 for q in distinct)
    zs = [p["z"] for p in inside]
    return {
        "total": len(points),
        "inside": len(inside),
        "outside": len(points) - len(inside),
        "distinct_xy_inside": len(distinct),
        "duplicates_same_z": duplicates_same_z,
        "contradictory_z": contradictory,
        "collinear": collinear,
        "z_min": min(zs) if zs else None,
        "z_max": max(zs) if zs else None,
        "layers": sorted({p["layer"] for p in points}),
        "containers": sorted({str(p.get("container")) for p in points}),
    }


def summarize(data: dict) -> dict:
    boundary = shape(data["boundary"])
    minx, miny, maxx, maxy = boundary.bounds
    coverings = {}
    geoms = []
    for ctype, cov in data["coverings"].items():
        geom = shape(cov["geometry"]) if cov.get("geometry") else Polygon()
        parts = _parts(geom)
        geoms.append(geom)
        coverings[ctype] = {
            "label": cov["label"],
            "layers": cov["layers"],
            "area_m2": round(cov["area_m2"], 2),
            "sources": len(cov["sources"]),
            "parts": len(parts),
            "holes": sum(len(p.interiors) for p in parts),
            "outside_boundary_m2": round(geom.difference(boundary).area, 4) if parts else 0.0,
        }
    union = unary_union([g for g in geoms if not g.is_empty]).intersection(boundary)
    free = boundary.difference(union)
    free_parts = sorted(_parts(free), key=lambda p: -p.area)
    ranking = sorted(coverings, key=lambda t: -coverings[t]["area_m2"])

    findings = Counter()
    si_side = Counter()
    for f in data["findings"]:
        findings[(f["code"], f["layer"])] += 1
        if f["code"] == "self_intersecting_contour":
            m = _XY.search(f.get("detail") or "")
            side = "unknown"
            if m:
                x, y = float(m.group(1)), float(m.group(2))
                side = "in_bbox" if (minx <= x <= maxx and miny <= y <= maxy) else "outside_bbox"
            si_side[(f["layer"], side)] += 1
    by_code = defaultdict(list)
    for (code, layer), n in sorted(findings.items()):
        by_code[code].append({"layer": layer, "count": n})
    overlaps = [
        {"pair": f["layer"], "area_m2": round(f["area"], 4)}
        for f in data["findings"]
        if f["code"] == "overlapping_coverings"
    ]
    s_ter = boundary.area
    return {
        "project": data["project"],
        "units": data["units"],
        "boundary": {
            "handle": data["boundary_handle"],
            "area_m2": round(s_ter, 2),
            "perimeter_m": round(boundary.length, 3),
            "vertices": len(boundary.exterior.coords) - 1,
            "bbox": [round(v, 2) for v in (minx, miny, maxx, maxy)],
            "size_m": [round(maxx - minx, 2), round(maxy - miny, 2)],
        },
        "base_covering": data["base_covering"],
        "covering_ranking": ranking,
        "coverings": coverings,
        "covered_union_m2": round(union.area, 2),
        "uncovered_m2": round(free.area, 2),
        "uncovered_parts": len(free_parts),
        "uncovered_largest_m2": [round(p.area, 1) for p in free_parts[:6]],
        "uncovered_largest_bbox": [[round(v, 1) for v in p.bounds] for p in free_parts[:4]],
        "elevations": elevation_stats(data["elevations"]),
        "planting": {"total": len(data["planting"]), "inside": sum(1 for p in data["planting"] if p["inside"])},
        "maf": {"total": len(data["maf"]), "inside": sum(1 for p in data["maf"] if p["inside"])},
        "findings_total": len(data["findings"]),
        "findings_by_code": {k: v for k, v in by_code.items() if k != "overlapping_coverings"},
        "self_intersecting_by_side": [
            {"layer": layer, "side": side, "count": n} for (layer, side), n in sorted(si_side.items())
        ],
        "overlaps": overlaps,
        "gnd06": {
            "s_ter_m2": round(s_ter, 2),
            "limit_if_s_pz_0": gnd06_limit(s_ter),
            "limit_if_s_pz_eq_uncovered": gnd06_limit(s_ter - free.area),
            "s_pz_m2_at_which_limit_drops": round(s_ter - 15_000.0, 2),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="+", help="label=path/to/ground_inputs.json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = {}
    for item in args.inputs:
        label, sep, path = item.partition("=")
        if not sep:
            parser.error(f"expected label=path, got {item!r}")
        src = Path(path).resolve()
        if args.out is not None and args.out.resolve() == src:
            parser.error("--out resolves to an input")
        result[label] = summarize(json.loads(src.read_text(encoding="utf-8")))
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
