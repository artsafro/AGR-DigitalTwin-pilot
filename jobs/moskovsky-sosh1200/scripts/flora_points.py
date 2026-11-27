"""Job-local Flora extraction from the SPOZU DXF: tree/shrub points, bed and hedge polygons (moskovsky-sosh1200).

Pattern: n/a | new-case: model-flora steps 1-2 for this job (ledger = species truth, drawing = positions).
Points: INSERTs of the greening block A$C7f310a12 (inserted at 0,0, identity) on ГП_Деревья / ГП_Кусты, XY only.
Beds/hedge: HATCHes on 240_Озел_Живая Изгородь, 253_..._Стефанандра..., _Кустаринки_Цветники; each hatch gets the
position of a planting MULTILEADER whose arrow point lies inside it (attrib 1 = position, attrib 2 = qty/area);
hatches without a bed label are hedge (pos 8) on the 253 hedge layer; the rest is resolved in RESOLVE by the
ledger area balance, else `unassigned`. Inside = point (polygon
area) in the ГПЗУ ring 2B6. Run: uv run --extra cad python jobs/moskovsky-sosh1200/scripts/flora_points.py OUT.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import ezdxf
from ezdxf import path as ezpath
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

DXF = Path("G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/intake/school.dxf")
RING = Path("G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/inspect/v001/gpzu_ring_2B6.json")
BLOCK = "A$C7f310a12"
ORIGIN = (-9840.0, -7150.0)
POS_BY_BLOCK = {"Пихта сибирская_105_М5.1": 1, "Клен остролистный_22_М5": 2, "Сосна обыкн": 3,
                "Клен Гиннала_96": 4, "Сирень обыкновенная_110": 5}
BED_LAYERS = ["240_Озел_Живая Изгородь", "253_Озел_Кустарники_Живая изгородь_№250_Стефанандра надрезаннолистная_S",
              "_Кустаринки_Цветники"]
HEDGE_LAYERS = BED_LAYERS[1:2]  # 253 Стефанандра hatches = hedge; 240 = perennial beds 9-11
# Unlabelled / double-labelled hatches resolved by the ledger area balance (pos 6 = 95, pos 11 = 132 m2):
RESOLVE = {"A008FB": 6, "A00902": 11, "A0090D": 11, "A00947": 11}
BED_POS = {6, 7, 8, 9, 10, 11}


def hatch_polygon(h):
    rings = []
    for p in ezpath.from_hatch(h):
        pts = [(v.x, v.y) for v in p.flattening(0.02)]
        if len(pts) >= 3:
            rings.append(Polygon(pts).buffer(0))
    if not rings:
        return None
    rings.sort(key=lambda g: -g.area)
    poly = rings[0]
    for r in rings[1:]:  # even-odd: inner loops are holes
        poly = poly.difference(r) if poly.contains(r.representative_point()) else poly.union(r)
    return poly


def geo(g):
    polys = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    return [{"exterior": [[round(x, 3), round(y, 3)] for x, y in p.exterior.coords],
             "holes": [[[round(x, 3), round(y, 3)] for x, y in r.coords] for r in p.interiors]}
            for p in polys if p.geom_type == "Polygon" and p.area > 0]


def main(out):
    doc = ezdxf.readfile(DXF)
    blk = doc.blocks[BLOCK]
    gpzu = Polygon(json.loads(RING.read_text()))
    points = []
    for e in blk.query("INSERT"):
        pos = POS_BY_BLOCK.get(e.dxf.name)
        if pos is None:
            continue
        x, y = e.dxf.insert.x, e.dxf.insert.y
        points.append({"handle": e.dxf.handle, "pos": pos, "block": e.dxf.name, "layer": e.dxf.layer,
                       "x": round(x, 3), "y": round(y, 3), "inside": gpzu.contains(Point(x, y))})
    labels = []
    for lay in ["253_Озел_Подписи_Многолетники", "253_Озел_Подписи_Деревья и Кустарники"]:
        for m in blk.query(f'MULTILEADER[layer=="{lay}"]'):
            at = [a.text for a in m.block_attribs]
            try:
                pos = int(at[0])
            except (ValueError, IndexError):
                continue
            arrows = [(ln.vertices[0].x, ln.vertices[0].y) for L in m.context.leaders for ln in L.lines if ln.vertices]
            labels.append({"handle": m.dxf.handle, "layer": lay, "pos": pos, "qty": at[1] if len(at) > 1 else None,
                           "arrows": [[round(a, 3), round(b, 3)] for a, b in arrows]})
    beds = []
    for lay in BED_LAYERS:
        for h in blk.query(f'HATCH[layer=="{lay}"]'):
            g = hatch_polygon(h)
            if g is None or g.area <= 0:
                continue
            beds.append({"handle": h.dxf.handle, "layer": lay, "geom": g})
    for b in beds:
        hits = []
        for lb in labels:
            if lb["pos"] not in BED_POS:
                continue
            for a in lb["arrows"]:
                if b["geom"].buffer(0.3).contains(Point(a)):
                    hits.append((lb["pos"], lb["handle"]))
        poss = sorted({p for p, _ in hits})
        if b["handle"] in RESOLVE:
            b["pos"], b["assigned_by"] = RESOLVE[b["handle"]], f"ledger area balance (labels hit: {poss or 'none'})"
        elif len(poss) == 1:
            b["pos"], b["assigned_by"] = poss[0], "label " + ",".join(sorted({hd for _, hd in hits}))
        elif len(poss) > 1:
            b["pos"], b["assigned_by"] = None, f"conflict {poss}"
        elif b["layer"] in HEDGE_LAYERS:
            b["pos"], b["assigned_by"] = 8, "hedge layer, no bed label"
        else:
            b["pos"], b["assigned_by"] = None, "unassigned"
    out_beds, area_by_pos = [], {}
    for b in beds:
        g = b["geom"]
        inside = g.intersection(gpzu)
        b_out = {k: v for k, v in b.items() if k != "geom"}
        b_out.update(area_m2=round(g.area, 2), area_in_gpzu_m2=round(inside.area, 2),
                     polygons_in_gpzu=geo(inside))
        out_beds.append(b_out)
        key = str(b["pos"])
        area_by_pos[key] = round(area_by_pos.get(key, 0) + inside.area, 2)
    # overlap between bed polygons (double planting risk)
    geoms = [b["geom"].intersection(gpzu) for b in beds]
    overlap = sum(geoms[i].intersection(geoms[j]).area for i in range(len(geoms)) for j in range(i + 1, len(geoms)))
    counts = {}
    for p in points:
        c = counts.setdefault(str(p["pos"]), {"inside": 0, "outside": 0})
        c["inside" if p["inside"] else "outside"] += 1
    data = {
        "schema": "agr.job.flora_points/1", "job": "moskovsky-sosh1200",
        "crs": "MSK-77 metres (DXF $INSUNITS=6); local = MSK - origin_xy (Ground v001 OBJ)",
        "origin_xy": list(ORIGIN),
        "source": {"dxf": str(DXF).replace("\\", "/"), "dxf_sha256": hashlib.sha256(DXF.read_bytes()).hexdigest(),
                   "block": BLOCK, "gpzu": "LWPOLYLINE 2B6 on _GL_01_Границы_ГПЗУ, area %.1f m2" % gpzu.area},
        "rules": "points XY only, no rotation [D100]; ledger = species, drawing = positions (TASK decision 4-5)",
        "point_counts": counts, "bed_area_in_gpzu_by_pos": area_by_pos,
        "bed_overlap_m2": round(overlap, 2),
        "points": sorted(points, key=lambda p: (p["pos"], p["handle"])),
        "labels": labels, "beds": out_beds,
    }
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"point_counts": counts, "bed_area_in_gpzu_by_pos": area_by_pos, "beds": len(out_beds),
                      "labels": len(labels), "overlap_m2": round(overlap, 2)}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
