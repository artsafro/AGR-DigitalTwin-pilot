"""new-case: read the facade Colour Solution sheet ("Фасад X. Цветовое решение") of one TEC26 building from its DWG
readback (AutoCAD 2025 DXFOUT, ezdxf recover) - joint lines, frame bands, panel field, door and plinth per facade.

Usage: uv run --extra cad python sheet_facades.py <building.dxf> <new_out.json>

Read-only. The drawing is in millimetres (model space, 1:1); facades are located by their solid panel hatch (layer
AC_text) and paired with the paper-space titles by sheet position (row, column). Per facade:
- `field_mm`: the panel field inside the frame bands (SPDS wall proxies: posts and rails), relative to the facade's
  hatch origin (left/bottom of the facade outline);
- `joint_lines_mm`: x of every vertical joint line strictly inside the field (layer 0 LINEs), `joints` = their
  number, `ribs` = joints + 1 (the strips between the frame edges and the lines, the count Artem's operator gave);
- `door_mm`, `plinth`: door outline and the grey hatch below ±0.000 (colour as drawn).
Nothing is invented: every number is an entity coordinate or colour of the DXF; handles are listed.
"""
import json
import os
import re
import sys

TITLE = re.compile(r"^Фасад\s+(\S+)\.\s+Цветовое решение$")


def _bbox(e):
    from ezdxf import bbox
    b = bbox.extents([e])
    return (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y) if b.has_data else None


def _rgb(e):
    return list(e.rgb) if e.has_dxf_attrib("true_color") else None


def _rows(items, key):
    """Sort (x, y)-anchored items into sheet reading order: rows top to bottom, then left to right."""
    ys = sorted({round(key(i)[1], -1) for i in items}, reverse=True)
    rows = []
    for it in items:
        y = key(it)[1]
        r = min(range(len(ys)), key=lambda k: abs(ys[k] - y))
        rows.append((r, key(it)[0], it))
    return [it for _, _, it in sorted(rows, key=lambda t: (t[0], t[1]))]


def read_sheet(dxf_path, panel_layer="AC_text", wall_layer="СПДС_СТЕНЫ", plinth_layer="ac_vid"):
    from ezdxf import recover
    doc, _audit = recover.readfile(dxf_path)
    msp = doc.modelspace()
    titles = []
    for lay in doc.layouts:
        if lay.name == "Model":
            continue
        for e in lay.query("TEXT MTEXT"):
            t = (e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text).strip()
            m = TITLE.match(t)
            if m:
                titles.append({"facade": m.group(1), "handle": e.dxf.handle, "layout": lay.name,
                               "xy": [e.dxf.insert.x, e.dxf.insert.y]})
    hatches = []
    for e in msp.query("HATCH"):
        b = _bbox(e)
        if e.dxf.layer == panel_layer and e.dxf.pattern_name == "SOLID" and b and b[2] - b[0] > 1000 \
                and b[3] - b[1] > 1000:
            hatches.append((e, b))
    if len(titles) != len(hatches) or not titles:
        raise ValueError(f"{len(titles)} colour-solution titles but {len(hatches)} panel hatches")
    titles = _rows(titles, lambda t: t["xy"])
    hatches = _rows(hatches, lambda h: (h[1][0], h[1][1]))
    lines = [e for e in msp.query("LINE") if abs(e.dxf.start.x - e.dxf.end.x) < 1e-3]
    walls = [(e, _bbox(e)) for e in msp if e.dxf.layer == wall_layer]
    others = [(e, _bbox(e)) for e in msp.query("HATCH") if e.dxf.layer == plinth_layer]
    door_parts = [(e, _bbox(e)) for e in msp.query("LWPOLYLINE") if e.dxf.layer == "_0"]
    out = {"dxf": os.path.abspath(dxf_path), "units": "mm", "insunits": doc.header.get("$INSUNITS"), "facades": {}}
    for t, (h, (x0, y0, x1, y1)) in zip(titles, hatches):
        W, H = x1 - x0, y1 - y0
        inside = lambda b, m=50: b and x0 - m <= b[0] and b[2] <= x1 + m and y0 - m <= b[1] and b[3] <= y1 + m  # noqa
        bands = [b for _, b in walls if inside(b, 5)]
        left = [b for b in bands if b[0] - x0 < 5 and b[2] - b[0] < 0.2 * W]
        right = [b for b in bands if x1 - b[2] < 5 and b[2] - b[0] < 0.2 * W]
        bottom = [b for b in bands if b[1] - y0 < 5 and b[3] - b[1] < 0.2 * H]
        top = [b for b in bands if y1 - b[3] < 5 and b[3] - b[1] < 0.2 * H]
        if not (left and right and bottom and top):
            raise ValueError(f"facade {t['facade']}: frame bands incomplete (l/r/b/t {len(left)}/{len(right)}/"
                             f"{len(bottom)}/{len(top)})")
        fx0, fx1 = max(b[2] for b in left) - x0, min(b[0] for b in right) - x0
        fy0, fy1 = max(b[3] for b in bottom) - y0, min(b[1] for b in top) - y0
        jl = [e for e in lines if x0 + fx0 + 1 < e.dxf.start.x < x0 + fx1 - 1 and e.dxf.layer == "0"
              and min(e.dxf.start.y, e.dxf.end.y) >= y0 + fy0 - 1 and max(e.dxf.start.y, e.dxf.end.y) <= y0 + fy1 + 1
              and abs(e.dxf.start.y - e.dxf.end.y) > 50]
        js = sorted({round(e.dxf.start.x - x0, 1) for e in jl})
        full = sorted({round(e.dxf.start.x - x0, 1) for e in jl
                       if abs(e.dxf.start.y - e.dxf.end.y) >= 0.9 * (fy1 - fy0)})
        steps = [round(b - a, 1) for a, b in zip(js, js[1:])]
        door = [b for _, b in door_parts if inside(b, 0)]
        dmm = None
        if door:
            dmm = [round(min(b[0] for b in door) - x0, 1), round(min(b[1] for b in door) - y0, 1),
                   round(max(b[2] for b in door) - x0, 1), round(max(b[3] for b in door) - y0, 1)]
        pl = [(e, b) for e, b in others if b and b[0] < x1 and b[2] > x0 and b[1] < y0 + 1 and b[3] > y0 - 400]
        out["facades"][t["facade"]] = {
            "title_handle": t["handle"], "layout": t["layout"], "hatch_handle": h.dxf.handle,
            "panel_rgb": _rgb(h), "origin_mm": [round(x0, 1), round(y0, 1)], "size_mm": [round(W, 1), round(H, 1)],
            "frame_bands_mm": {"left": round(fx0, 1), "right": round(W - fx1, 1), "bottom": round(fy0, 1),
                               "top": round(H - fy1, 1)},
            "field_mm": [round(fx0, 1), round(fy0, 1), round(fx1, 1), round(fy1, 1)],
            "field_width_mm": round(fx1 - fx0, 1),
            "joint_lines_mm": js, "joints": len(js), "ribs": len(js) + 1,
            "full_height_joints": len(full), "drawn_steps_mm": sorted(set(steps)),
            "first_joint_from_field_mm": round(js[0] - fx0, 1) if js else None,
            "last_joint_to_field_mm": round(fx1 - js[-1], 1) if js else None,
            "door_mm": dmm,
            "plinth": [{"handle": e.dxf.handle, "rgb": _rgb(e), "bbox_mm": [round(b[0] - x0, 1), round(b[1] - y0, 1),
                                                                            round(b[2] - x0, 1), round(b[3] - y0, 1)]}
                       for e, b in pl]}
    return out


def main(argv):
    dxf, out = argv
    if os.path.lexists(out):
        raise SystemExit(f"refusing to overwrite {out}")
    rep = read_sheet(dxf)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    for k, f in rep["facades"].items():
        print("SHEET", k, "field", f["field_width_mm"], "joints", f["joints"], "ribs", f["ribs"],
              "steps", f["drawn_steps_mm"], "door", f["door_mm"])


if __name__ == "__main__":
    main(sys.argv[1:])
