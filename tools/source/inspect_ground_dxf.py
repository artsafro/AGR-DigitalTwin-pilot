"""Read-only inventory of a SPOZU DXF for Ground: layers, inserted blocks, hatch areas.

Pattern: n/a | new-case: SPOZU DXF inventory for Ground (issue #194); nesting-aware hatch areas
clipped to the plot boundary, per-file textual inventory with total checks.

Hatch area rules (AutoCAD HATCH semantics):

* Every boundary path is converted by ``ezdxf.path.from_hatch`` (OCS -> WCS, arcs, ellipses,
  splines) and flattened with ``tol`` metres.
* The filled region follows the hatch style: style 0 "normal" fills by odd nesting depth
  (even-odd), style 1 "outer" fills depth 0 minus depth 1 islands, style 2 "ignore" fills only
  depth-0 loops. Path flags EXTERNAL/OUTERMOST do not decide the sign; nesting does.
* The plot boundary (2D polyline) must be closed; every bulge is sampled on its exact circle with
  chord-to-arc distance <= ``BOUNDARY_TOL`` (no Bezier step), then OCS -> WCS with the elevation.
* A loop that is not a valid simple ring (self-intersection, fewer than 3 points, zero area) is
  reported in ``issues`` and the hatch area is ``None``; it is never silently repaired.

usage:
    uv run python tools/source/inspect_ground_dxf.py <file.dxf> --boundary <handle> \
        [--label main] [--out <inventory.md>] [--json <hatches.json>]
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely import union_all
from shapely.validation import explain_validity

DEFAULT_TOL = 0.001  # m, flattening distance for curved hatch edges
BOUNDARY_TOL = 0.0001  # m, chord-to-arc distance for the plot boundary (area bias <= 2/3 * tol * arc length)
GRID = 1e-4  # m, precision grid for cross-hatch overlays (GEOS robustness); per-hatch areas are exact


@dataclass
class HatchArea:
    handle: str
    layer: str
    pattern: str
    style: int
    loops: int
    area: float | None  # filled area, m2 (None when a loop is invalid)
    area_in_plot: float | None  # filled area clipped to the boundary
    issues: list[str] = field(default_factory=list)
    geometry: object | None = None  # shapely geometry of the filled region


def _polygonal(g):
    """Keep only the areal part of an overlay result (drop stray lines/points)."""
    if g is None or g.is_empty or g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    parts = []
    for p in getattr(g, "geoms", []):
        if p.geom_type == "Polygon":
            parts.append(p)
        elif p.geom_type == "MultiPolygon":
            parts.extend(p.geoms)
    return MultiPolygon(parts)


def _ring(points) -> tuple[Polygon | None, str | None]:
    pts = [(float(p.x), float(p.y)) for p in points]
    # drop consecutive duplicates (a closing duplicate is implicit in Polygon)
    clean = [pts[0]] if pts else []
    for p in pts[1:]:
        if abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
            clean.append(p)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    if len(clean) < 3:
        return None, f"degenerate loop ({len(clean)} points)"
    poly = Polygon(clean)
    if not poly.is_valid:
        return None, f"invalid loop: {explain_validity(poly)}"
    if poly.area <= 0:
        return None, "zero-area loop"
    return poly, None


def hatch_region(hatch, tol: float = DEFAULT_TOL):
    """Return (shapely geometry of the filled region or None, issues)."""
    from ezdxf import path as ezpath

    rings: list[Polygon] = []
    issues: list[str] = []
    for i, p in enumerate(ezpath.from_hatch(hatch)):
        poly, err = _ring(list(p.flattening(tol)))
        if err:
            issues.append(f"loop {i}: {err}")
        else:
            rings.append(poly)
    if issues:
        return None, issues
    if not rings:
        return None, ["no loops"]
    depth = []
    for i, r in enumerate(rings):
        rp = r.representative_point()
        depth.append(sum(1 for j, o in enumerate(rings) if j != i and o.area > r.area and o.contains(rp)))
    style = int(hatch.dxf.get("hatch_style", 0))
    max_depth = {2: 0, 1: 1}.get(style, len(rings))
    pairs = [(r, d) for r, d in zip(rings, depth) if d <= max_depth]
    region = None
    try:
        for r, d in sorted(pairs, key=lambda t: t[1]):
            if region is None:
                region = r
            elif d % 2 == 0:
                region = region.union(r)
            else:
                region = region.difference(r)
    except Exception as exc:  # GEOS overlay failure: report, do not guess
        return None, [f"overlay error: {exc}"]
    return _polygonal(region), issues


def hatch_area(hatch, boundary: Polygon | None = None, tol: float = DEFAULT_TOL) -> HatchArea:
    region, issues = hatch_region(hatch, tol)
    area = None if region is None else region.area
    clipped = None
    if region is not None and boundary is not None:
        clipped = region.intersection(boundary).area
    return HatchArea(
        handle=hatch.dxf.handle,
        layer=hatch.dxf.layer,
        pattern="SOLID" if hatch.dxf.solid_fill else hatch.dxf.pattern_name,
        style=int(hatch.dxf.get("hatch_style", 0)),
        loops=len(hatch.paths),
        area=area,
        area_in_plot=clipped,
        issues=issues,
        geometry=region,
    )


BOUNDARY_TYPES = ("LWPOLYLINE", "POLYLINE")


def arc_points(p1, p2, bulge: float, tol: float) -> list[tuple[float, float]]:
    """Points strictly between p1 and p2 on the bulge arc, chord-to-arc distance <= tol.

    The points lie exactly on the circle (no Bezier approximation); the segment count is
    ceil(|sweep| / (2 * acos(1 - tol / r))).
    """
    (x1, y1), (x2, y2) = p1, p2
    c = math.hypot(x2 - x1, y2 - y1)
    if not bulge or c == 0.0:
        return []
    sweep = 4.0 * math.atan(bulge)  # signed, CCW positive
    r = abs(c / (2.0 * math.sin(sweep / 2.0)))
    ux, uy = (x2 - x1) / c, (y2 - y1) / c
    off = (c / 2.0) * (1.0 - bulge * bulge) / (2.0 * bulge)  # midpoint -> centre along the left normal
    cx, cy = (x1 + x2) / 2.0 - uy * off, (y1 + y2) / 2.0 + ux * off
    a1 = math.atan2(y1 - cy, x1 - cx)
    step = 2.0 * math.acos(max(-1.0, 1.0 - tol / r)) if tol < 2.0 * r else math.pi
    n = max(1, math.ceil(abs(sweep) / step))
    return [(cx + r * math.cos(a1 + sweep * k / n), cy + r * math.sin(a1 + sweep * k / n)) for k in range(1, n)]


def boundary_polygon(doc, handle: str, tol: float = BOUNDARY_TOL) -> Polygon:
    """Closed plot boundary (2D LWPOLYLINE / POLYLINE) as a WCS polygon, curve-aware.

    Every bulge (including the closing segment's) becomes an arc sampled on the exact circle with
    chord-to-arc distance <= ``tol`` m; vertices are transformed OCS -> WCS with the elevation.
    A boundary that is neither flagged closed nor ends at its start raises ValueError.
    """
    e = doc.entitydb.get(handle)
    if e is None:
        raise ValueError(f"boundary {handle}: no such entity")
    return polyline_polygon(e, tol, handle)


def polyline_polygon(e, tol: float = BOUNDARY_TOL, handle: str | None = None) -> Polygon:
    """``boundary_polygon`` for an entity object (also a virtual WCS copy from a block insert)."""
    handle = handle or e.dxf.handle
    kind = e.dxftype()
    if kind == "LWPOLYLINE":
        verts = [(x, y, b) for x, y, b in e.get_points("xyb")]
        elevation = e.dxf.elevation
    elif kind == "POLYLINE" and e.is_2d_polyline:
        verts = [(v.dxf.location.x, v.dxf.location.y, v.dxf.bulge) for v in e.vertices]
        elevation = e.dxf.elevation.z
    else:
        raise ValueError(f"boundary {handle}: unsupported type {kind}")
    if len(verts) >= 2 and math.isclose(verts[0][0], verts[-1][0], abs_tol=1e-9) and math.isclose(
        verts[0][1], verts[-1][1], abs_tol=1e-9
    ):
        verts = verts[:-1]  # explicit closing vertex; its bulge is irrelevant
    elif not e.is_closed:
        raise ValueError(f"boundary {handle}: not closed (no closed flag, start != end)")
    ocs_pts: list[tuple[float, float]] = []
    for i, (x, y, b) in enumerate(verts):
        ocs_pts.append((x, y))
        nx, ny, _ = verts[(i + 1) % len(verts)]
        ocs_pts.extend(arc_points((x, y), (nx, ny), b, tol))
    ocs = e.ocs()
    from ezdxf.math import Vec2

    wcs = [Vec2(ocs.to_wcs((x, y, elevation))) for x, y in ocs_pts]
    poly, err = _ring(wcs)
    if err:
        raise ValueError(f"boundary {handle}: {err}")
    return poly


def _insert_wcs(e):
    return e.ocs().to_wcs(e.dxf.insert)


def inventory(doc, boundary: Polygon | None = None, tol: float = DEFAULT_TOL) -> dict:
    """Per-file inventory: layers x types, inserted blocks, hatches, total checks."""
    msp = doc.modelspace()
    by_layer: dict[str, Counter] = defaultdict(Counter)
    for e in msp:
        by_layer[e.dxf.layer][e.dxftype()] += 1
    layers = {}
    for lay in doc.layers:
        n = lay.dxf.name
        layers[n] = {
            "on": lay.is_on(),
            "frozen": lay.is_frozen(),
            "types": dict(by_layer.get(n, {})),
        }
    # layers referenced by entities but missing in the table
    for n in by_layer:
        layers.setdefault(n, {"on": None, "frozen": None, "types": dict(by_layer[n])})

    blocks: dict[str, dict] = {}
    for e in msp.query("INSERT"):
        b = blocks.setdefault(
            e.dxf.name,
            {"count": 0, "in_plot": 0, "layers": Counter(), "attribs": Counter(), "attdefs": []},
        )
        b["count"] += 1
        b["layers"][e.dxf.layer] += 1
        for a in e.attribs:
            b["attribs"][a.dxf.tag] += 1
        if boundary is not None:
            x, y = tuple(_insert_wcs(e))[:2]
            if boundary.contains(Point(x, y)):
                b["in_plot"] += 1
    for name, b in blocks.items():
        if name in doc.blocks:
            b["attdefs"] = [a.dxf.tag for a in doc.blocks[name].query("ATTDEF")]
    unused_defs = [
        b.name
        for b in doc.blocks
        if not b.name.lower().startswith(("*model", "*paper")) and b.name not in blocks
    ]

    hatches = [hatch_area(h, boundary, tol) for h in msp.query("HATCH")]

    type_totals = Counter()
    for c in by_layer.values():
        type_totals.update(c)
    checks = {
        "msp_entities": len(msp),
        "sum_layer_type_counts": sum(type_totals.values()),
        "layer_table": len(doc.layers),
        "layers_used_in_msp": len(by_layer),
        "insert_total": type_totals.get("INSERT", 0),
        "sum_block_insert_counts": sum(b["count"] for b in blocks.values()),
        "hatch_total": type_totals.get("HATCH", 0),
        "hatches_measured": len(hatches),
        "hatches_invalid": sum(1 for h in hatches if h.area is None),
    }
    return {
        "layers": layers,
        "type_totals": dict(type_totals),
        "blocks": blocks,
        "unused_block_defs": unused_defs,
        "hatches": hatches,
        "checks": checks,
    }


def layer_unions(hatches: list[HatchArea], boundary: Polygon) -> dict[str, object]:
    """Union of the valid hatch regions per layer, clipped to the boundary."""
    per: dict[str, list] = defaultdict(list)
    for h in hatches:
        if h.geometry is not None:
            per[h.layer].append(h.geometry)
    return {
        k: _polygonal(_polygonal(union_all(v, grid_size=GRID)).intersection(boundary, grid_size=GRID))
        for k, v in per.items()
    }


def overlaps(unions: dict[str, object], layers: list[str], min_area: float = 0.01) -> list[tuple]:
    rows = []
    for i, a in enumerate(layers):
        for b in layers[i + 1 :]:
            if a in unions and b in unions:
                try:
                    ar = _polygonal(unions[a].intersection(unions[b], grid_size=GRID)).area
                except Exception as exc:  # report the failing pair instead of aborting
                    rows.append((a, b, f"overlay error: {exc}"))
                    continue
                if ar >= min_area:
                    rows.append((a, b, ar))
    return rows


def _fmt(x, nd=2):
    return "-" if x is None else f"{x:.{nd}f}"


def render_markdown(label: str, inv: dict, boundary_handle: str | None, tol: float) -> str:
    out = [f"# SPOZU Vatutino inventory: `{label}` file", ""]
    out.append(
        f"Generated by `tools/source/inspect_ground_dxf.py` (flattening tol {tol} m, boundary "
        f"`{boundary_handle}`). Model space only; counts are top-level entities."
    )
    out.append("")
    out.append("## Total checks")
    out.append("")
    out.append("| Check | Value |")
    out.append("|---|---|")
    for k, v in inv["checks"].items():
        out.append(f"| {k} | {v} |")
    out.append("")
    out.append("## Layers (all, entity counts by type in model space)")
    out.append("")
    out.append("| Layer | State | Entities | By type |")
    out.append("|---|---|---|---|")
    for name in sorted(inv["layers"], key=lambda n: (-sum(inv["layers"][n]["types"].values()), n)):
        d = inv["layers"][name]
        state = "frozen" if d["frozen"] else ("off" if d["on"] is False else "on")
        n = sum(d["types"].values())
        types = ", ".join(f"{t} {c}" for t, c in sorted(d["types"].items(), key=lambda t: -t[1])) or "empty"
        out.append(f"| `{name}` | {state} | {n} | {types} |")
    out.append("")
    out.append("## Inserted blocks (model space)")
    out.append("")
    out.append("In plot = WCS insert point inside the boundary. Attributes = tags of attached ATTRIBs (count).")
    out.append("")
    out.append("| Block | Inserts | In plot | Layers | Attributes | ATTDEF tags |")
    out.append("|---|---|---|---|---|---|")
    for name in sorted(inv["blocks"], key=lambda n: (-inv["blocks"][n]["count"], n)):
        b = inv["blocks"][name]
        lays = ", ".join(f"`{k}` {v}" for k, v in b["layers"].most_common())
        att = ", ".join(f"{k} {v}" for k, v in b["attribs"].most_common()) or "-"
        adefs = ", ".join(b["attdefs"]) or "-"
        out.append(f"| `{name}` | {b['count']} | {b['in_plot']} | {lays} | {att} | {adefs} |")
    out.append("")
    named_unused = [n for n in inv["unused_block_defs"] if not n.startswith("*")]
    out.append(
        f"Block definitions never inserted in model space: {len(inv['unused_block_defs'])} "
        f"({len(named_unused)} named, the rest anonymous `*` blocks: tables, dimensions, nested)."
    )
    out.append("")
    out.append("## Hatches by layer and pattern")
    out.append("")
    out.append(
        "Area = nesting-aware filled area (full entity); In plot = the same region clipped to the boundary. "
        "Invalid = hatches with a non-simple loop: excluded from both sums, listed below."
    )
    out.append("")
    out.append("| Layer | Pattern | Hatches | Invalid | Area, m2 | In plot, m2 |")
    out.append("|---|---|---|---|---|---|")
    groups: dict[tuple, list] = defaultdict(list)
    for h in inv["hatches"]:
        groups[(h.layer, h.pattern)].append(h)
    for (layer, pat), hs in sorted(groups.items()):
        valid = [h for h in hs if h.area is not None]
        a = sum(h.area for h in valid)
        ai = sum(h.area_in_plot or 0.0 for h in valid)
        out.append(f"| `{layer}` | {pat} | {len(hs)} | {len(hs) - len(valid)} | {a:.2f} | {ai:.2f} |")
    out.append("")
    bad = [h for h in inv["hatches"] if h.area is None]
    out.append(f"### Invalid hatches ({len(bad)})")
    out.append("")
    if bad:
        out.append("| Handle | Layer | Pattern | Loops | Issue |")
        out.append("|---|---|---|---|---|")
        for h in bad:
            out.append(f"| `{h.handle}` | `{h.layer}` | {h.pattern} | {h.loops} | {'; '.join(h.issues)[:200]} |")
    else:
        out.append("none")
    out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    import ezdxf

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dxf")
    ap.add_argument("--boundary", help="handle of the closed boundary LWPOLYLINE")
    ap.add_argument("--label", default=None)
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL)
    ap.add_argument("--boundary-tol", type=float, default=BOUNDARY_TOL)
    ap.add_argument("--out", help="markdown inventory path")
    ap.add_argument("--json", help="per-hatch JSON path (handle, layer, areas, issues)")
    ap.add_argument("--overlap-layers", nargs="*", default=[], help="layers for pairwise overlap areas")
    ap.add_argument("--overlap-prefix", default=None, help="also every hatch layer starting with this prefix")
    a = ap.parse_args(argv)
    doc = ezdxf.readfile(a.dxf)
    boundary = boundary_polygon(doc, a.boundary, a.boundary_tol) if a.boundary else None
    inv = inventory(doc, boundary, a.tol)
    if a.overlap_prefix:
        a.overlap_layers += sorted({h.layer for h in inv["hatches"] if h.layer.startswith(a.overlap_prefix)})
    label = a.label or Path(a.dxf).stem
    md = render_markdown(label, inv, a.boundary, a.tol)
    if boundary is not None and a.overlap_layers:
        un = layer_unions(inv["hatches"], boundary)
        rows = overlaps(un, a.overlap_layers)
        md += "\n## Covering overlaps inside the plot (geometry intersection of per-layer unions)\n\n"
        md += "| Layer A | Layer B | Overlap, m2 |\n|---|---|---|\n"
        md += "".join(
            f"| `{x}` | `{y}` | {ar:.2f} |\n" if isinstance(ar, float) else f"| `{x}` | `{y}` | {ar} |\n"
            for x, y, ar in rows
        ) or "| none | | |\n"
        cov = union_all([un[k] for k in a.overlap_layers if k in un], grid_size=GRID)
        md += (
            f"\nUnion of these layers inside the plot: {cov.area:.2f} m2 of {boundary.area:.2f} m2; "
            f"sum of per-layer unions {sum(un[k].area for k in a.overlap_layers if k in un):.2f} m2.\n"
        )
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8", newline="\n")
    if a.json:
        rows = [
            {k: v for k, v in h.__dict__.items() if k != "geometry"} for h in inv["hatches"]
        ]
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps(inv["checks"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
