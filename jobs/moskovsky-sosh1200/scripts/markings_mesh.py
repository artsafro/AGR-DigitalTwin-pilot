"""Sport / game markings as a separate closed mesh over the Ground (moskovsky-sosh1200 ground-npm v002).

Pattern: n/a | new-case: the user's v001 review (2026-11-26) asks for markings as their own mesh, not Ground covers:
flat strips of the real line width, top +8 mm over the Ground plane (inside the 5 mm - 2 cm spacing of co-directional
polygons, reg p.29 §3.13), bottom embedded −10 mm (user default; no Ground marking rule in docs/domain). Linework is
read from the DXFs (nested INSERTs resolved), buffered to strips, merged per material, clipped to each Ground boundary,
triangulated (constrained Delaunay, no Steiner points) and closed with walls. Text glyphs (MTEXT) are not built.

usage: uv run --extra cad python jobs/moskovsky-sosh1200/scripts/markings_mesh.py CONFIG.json NEW_DIR OBJNAME=ADAPTER.json [...]
CONFIG: {"origin_xy", "top_m", "bottom_m", "sources": [{"name", "dxf", "sha256", "layers", "types"?, "width_m",
          "use_const_width"?, "roots"?: [INSERT handles], "material", "colour", "region_wkt"?,
          "dedupe_against"?: [names], "dedupe_tol_m"?}]}  (width_m = default when an entity has no constant width)
Each OBJNAME=ADAPTER writes NEW_DIR/OBJNAME/OBJNAME.obj (+ .mtl, markings-report.json) clipped to that adapter boundary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import ezdxf
import shapely
import shapely.geometry.polygon
from ezdxf.path import make_path
from shapely import wkt
from shapely.geometry import LineString, Polygon, shape
from shapely.ops import unary_union

from dt_ai.geometry import ground_site as gs

LINE_TYPES = ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE", "ELLIPSE")


def walk(space, m, inh, want, depth=0):
    """(entity in world XY, effective layer); only entities ``want(layer, type)`` are copied and transformed."""
    for e in space:
        eff = inh if (e.dxf.layer == "0" and inh) else e.dxf.layer
        t = e.dxftype()
        if t == "INSERT":
            if depth <= 8 and e.block() is not None:
                yield from walk(e.block(), e.matrix44() if m is None else e.matrix44() * m, eff, want, depth + 1)
            continue
        if not want(eff, t):
            continue
        if m is None:
            yield e, eff
        else:
            try:
                c = e.copy(); c.transform(m); yield c, eff
            except Exception:  # noqa: BLE001 - entity types that cannot be transformed are not linework
                continue


def layer_lines(doc, layers, roots=None):
    """{layer: [(centreline, const_width)]} from model space, or only from the INSERTs named by ``roots``."""
    out = {k: [] for k in layers}
    want = lambda lay, t: lay in out and t in LINE_TYPES  # noqa: E731
    if roots is None:
        it = walk(doc.modelspace(), None, None, want)
    elif roots == "msp":  # top-level model space entities only
        it = ((e, e.dxf.layer) for e in doc.modelspace() if want(e.dxf.layer, e.dxftype()))
    else:
        def it_roots():
            for h in roots:
                ins = doc.entitydb[h]
                yield from walk(ins.block(), ins.matrix44(), ins.dxf.layer, want, 1)
        it = it_roots()
    for e, lay in it:
        try:
            pts = [(v.x, v.y) for v in make_path(e).flattening(0.01)]
        except Exception:  # noqa: BLE001
            continue
        if len(pts) >= 2 and LineString(pts).length >= 1e-3:
            w = float(e.dxf.get("const_width", 0) or 0) if e.dxftype() == "LWPOLYLINE" else 0.0
            out[lay].append((LineString(pts), w))
    return out


def solid(polys, top, bottom):
    """Closed prism per polygon: CCW top (+Z), reversed bottom, walls with outward normals (orient: interior left)."""
    V, F, key = [], [], {}

    def vid(x, y, z):
        k = (round(x, 6), round(y, 6), z)
        if k not in key:
            key[k] = len(V); V.append((x, y, z))
        return key[k]
    for poly in polys:
        poly = shapely.geometry.polygon.orient(poly, 1.0)
        for t in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
            c = list(shapely.geometry.polygon.orient(t, 1.0).exterior.coords)[:3]
            if Polygon(c).area < 1e-9:
                continue
            F.append([vid(x, y, top) for x, y in c])
            F.append([vid(x, y, bottom) for x, y in c[::-1]])
        for ring in [poly.exterior, *poly.interiors]:
            cs = list(ring.coords)
            for (x0, y0), (x1, y1) in zip(cs, cs[1:]):
                t0, t1, b0, b1 = vid(x0, y0, top), vid(x1, y1, top), vid(x0, y0, bottom), vid(x1, y1, bottom)
                F.append([t0, b0, b1]); F.append([t0, b1, t1])
    return V, F


def main() -> int:
    cfg_p, out = Path(sys.argv[1]), Path(sys.argv[2])
    targets = [a.split("=", 1) for a in sys.argv[3:]]
    if out.exists():
        raise SystemExit(f"{out} exists: give a new versioned path")
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    ox, oy = cfg["origin_xy"]
    top, bottom = float(cfg["top_m"]), float(cfg["bottom_m"])
    docs = {}
    lines, rows = {}, []
    for src in cfg["sources"]:
        p = src["dxf"]
        if p not in docs:
            if gs.sha256(Path(p)) != src["sha256"]:
                raise SystemExit(f"{p}: sha256 differs")
            docs[p] = ezdxf.readfile(p)
        got = layer_lines(docs[p], src["layers"], src.get("roots"))
        region = wkt.loads(src["region_wkt"]) if src.get("region_wkt") else None
        pairs = [(g, w) for lay in src["layers"] for g, w in got[lay]]
        if region is not None:
            pairs = [(g.intersection(region), w) for g, w in pairs if g.intersects(region)]
            pairs = [(g, w) for g, w in pairs if g.length > 1e-3]
        widths = [w if (src.get("use_const_width") and w > 0) else src["width_m"] for _, w in pairs]
        ls = [g for g, _ in pairs]
        dropped = 0
        if src.get("dedupe_against"):
            near = unary_union([g for n in src["dedupe_against"] for g in lines[n]]).buffer(src.get("dedupe_tol_m", 0.05))
            kept = []
            for g, w in zip(ls, widths):
                if g.intersection(near).length > 0.8 * g.length:
                    dropped += 1
                else:
                    kept.append((g, w))
            ls, widths = [g for g, _ in kept], [w for _, w in kept]
        lines[src["name"]] = ls
        src["_widths"] = {str(round(w, 3)): widths.count(w) for w in set(widths)}
        strips = unary_union([g.buffer(w / 2, cap_style="flat", join_style="mitre", mitre_limit=3)
                              for g, w in zip(ls, widths)]) if ls else Polygon()
        rows.append((src, ls, strips, dropped))
    out.mkdir(parents=True)
    summary = {}
    for name, adapter in targets:
        boundary = shape(json.loads(Path(adapter).read_text(encoding="utf-8"))["boundary"])
        report = {"config": str(cfg_p), "config_sha256": gs.sha256(cfg_p), "adapter": adapter,
                  "boundary_m2": boundary.area, "origin_xy_msk77": [ox, oy], "top_m": top, "bottom_m": bottom,
                  "sources": [], "materials": {}}
        mats = {}
        for src, ls, strips, dropped in rows:
            clip = strips.intersection(boundary)
            mats.setdefault(src["material"], []).append(clip)
            report["sources"].append({"name": src["name"], "dxf": src["dxf"], "layers": src["layers"],
                                      "width_m": src["width_m"], "widths_used": src["_widths"], "roots": src.get("roots"),
                                      "material": src["material"], "colour": src["colour"],
                                      "entities": len(ls), "duplicates_dropped": dropped,
                                      "centreline_m": round(sum(g.length for g in ls), 2),
                                      "centreline_in_boundary_m": round(sum(g.intersection(boundary).length for g in ls), 2),
                                      "strip_m2": round(strips.area, 3), "strip_in_boundary_m2": round(clip.area, 3)})
        d = out / name
        d.mkdir()
        obj = [f"# markings: local XY = MSK-77 - ({ox}, {oy}); Z top {top}, bottom {bottom}", f"mtllib {name}.mtl", f"o {name}"]
        mtl, voff, tris = [], 0, 0
        colours = {s["material"]: s["colour"] for s in cfg["sources"]}
        for mat, geoms in mats.items():
            g = shapely.make_valid(shapely.set_precision(unary_union(geoms), 0.0005))
            polys = [p for p in shapely.get_parts(g) if p.geom_type == "Polygon" and p.area > 1e-6]
            if not polys:
                continue
            V, F = solid(polys, top, bottom)
            report["materials"][mat] = {"polygons": len(polys), "area_m2": round(sum(p.area for p in polys), 3),
                                        "triangles": len(F), "colour": colours[mat]}
            obj += [f"v {x - ox:.6f} {y - oy:.6f} {z:.6f}" for x, y, z in V]
            obj += [f"g {mat}", f"usemtl {mat}"]
            obj += [f"f {a + 1 + voff} {b + 1 + voff} {c + 1 + voff}" for a, b, c in F]
            voff += len(V); tris += len(F)
            r, gg, b = (v / 255 for v in colours[mat])
            mtl += [f"newmtl {mat}", f"Kd {r:.4f} {gg:.4f} {b:.4f}", ""]
        (d / f"{name}.obj").write_text("\n".join(obj) + "\n", encoding="utf-8")
        (d / f"{name}.mtl").write_text("\n".join(mtl) + "\n", encoding="utf-8")
        report["triangles"] = tris
        (d / "markings-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        summary[name] = {"triangles": tris, "materials": report["materials"],
                         "sources": [{k: s[k] for k in ("name", "entities", "duplicates_dropped", "centreline_in_boundary_m",
                                                        "strip_in_boundary_m2")} for s in report["sources"]]}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
