"""new-case: count the vertical panel joints of a TEC26 «Фасад X. Цветовое решение» elevation whose sandwich wall is
drawn as colour-band hatches (no AC08-style frame posts), from the AutoCAD readback DXF (ezdxf recover, read-only).

Usage: uv run --extra cad python sheet_ribs.py <building.dxf> <new_out.json> NAME:TITLE:HATCH[+HATCH...] ...
  e.g. "А-Д:105135:1109EB+1109EA" - facade name, its title handle and the hatch handles that make up the wall
  (grey + blue bands). Wall width = the FIRST hatch's x-range (the upper band may overhang at the eaves), height =
  the union of the hatch boxes (mm, model space 1:1).

A joint line is a vertical LINE/LWPOLYLINE segment strictly inside the wall, >= 250 mm long, on the wall's dominant
grid (the modal x mod `step`, `step` = the modal spacing of all candidate lines). Every other vertical line inside the
wall (downpipes, window frames, door jambs) is listed in `excluded_lines_mm` with its y-range; nothing is dropped
silently. Fail-closed: an unknown handle, an empty wall or a facade without lines raises ValueError.
"""
import json
import os
import sys
from collections import Counter


def _segments(msp):
    out = []
    for e in msp.query("LINE LWPOLYLINE"):
        if e.dxftype() == "LINE":
            out.append((e.dxf.handle, e.dxf.layer, e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y))
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if e.closed:
            pts.append(pts[0])
        out += [(e.dxf.handle, e.dxf.layer, a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]
    return out


def read_ribs(dxf_path, facades, min_len=250.0, edge=20.0):
    from ezdxf import bbox, recover
    doc, _audit = recover.readfile(dxf_path)
    msp = doc.modelspace()
    segs = _segments(msp)
    out = {"dxf": os.path.abspath(dxf_path), "units": "mm", "insunits": doc.header.get("$INSUNITS"), "facades": {}}
    for spec in facades:
        name, title, hatches = spec.split(":")
        t = doc.entitydb.get(title)
        if t is None or t.dxftype() not in ("TEXT", "MTEXT"):
            raise ValueError(f"facade {name}: title handle {title} is not a text")
        text = (t.plain_text() if t.dxftype() == "MTEXT" else t.dxf.text).strip()
        boxes = []
        for h in hatches.split("+"):
            e = doc.entitydb.get(h)
            if e is None or e.dxftype() != "HATCH":
                raise ValueError(f"facade {name}: {h} is not a hatch")
            b = bbox.extents([e])
            boxes.append({"handle": h, "rgb": list(e.rgb) if e.has_dxf_attrib("true_color") else None,
                          "bbox_mm": [round(b.extmin.x, 1), round(b.extmin.y, 1), round(b.extmax.x, 1),
                                      round(b.extmax.y, 1)]})
        x0, x1 = boxes[0]["bbox_mm"][0], boxes[0]["bbox_mm"][2]  # wall width: the FIRST hatch (eaves overhang)
        y0 = min(b["bbox_mm"][1] for b in boxes)
        y1 = max(b["bbox_mm"][3] for b in boxes)
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            raise ValueError(f"facade {name}: empty wall")
        cand = {}
        for h, layer, a, b, c, d in segs:
            lo, hi = min(b, d), max(b, d)
            if abs(a - c) < 1e-3 and hi - lo >= min_len and x0 + edge < a < x1 - edge and lo > y0 - 150 \
                    and hi < y1 + 150:
                cand.setdefault(round(a - x0, 1), []).append((h, layer, round(lo - y0), round(hi - y0)))
        xs = sorted(cand)
        if not xs:
            raise ValueError(f"facade {name}: no vertical lines inside the wall")
        step = Counter(round(q - p) for p, q in zip(xs, xs[1:])).most_common(1)[0][0]
        phase = Counter(round(x) % step for x in xs).most_common(1)[0][0]
        joints = [x for x in xs if round(x) % step == phase]
        excl = [{"x_mm": x, "y_mm": [cand[x][0][2], cand[x][0][3]], "handle": cand[x][0][0],
                 "reason": f"off the {step} mm joint grid (downpipe / frame / jamb)"} for x in xs if x not in joints]
        out["facades"][name] = {
            "title_handle": title, "title": text, "hatches": boxes, "wall_origin_mm": [x0, y0],
            "wall_mm": round(x1 - x0, 1), "wall_height_mm": round(y1 - y0, 1),
            "joint_lines_mm": joints, "joints": len(joints), "ribs": len(joints) + 1,
            "drawn_steps_mm": sorted({round(q - p, 1) for p, q in zip(joints, joints[1:])}),
            "first_joint_from_wall_mm": joints[0], "last_joint_to_wall_mm": round(x1 - x0 - joints[-1], 1),
            "joint_layers": sorted({cand[x][0][1] for x in joints}),
            "excluded_lines_mm": excl}
    return out


def main(argv):
    dxf, out, *facades = argv
    if os.path.lexists(out):
        raise SystemExit(f"refusing to overwrite {out}")
    if os.path.realpath(out) == os.path.realpath(dxf):
        raise SystemExit("output aliases the input")
    rep = read_ribs(dxf, facades)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    for k, f in rep["facades"].items():
        print("SHEET", k, "wall", f["wall_mm"], "joints", f["joints"], "ribs", f["ribs"], "steps", f["drawn_steps_mm"],
              "excluded", len(f["excluded_lines_mm"]))


if __name__ == "__main__":
    main(sys.argv[1:])
