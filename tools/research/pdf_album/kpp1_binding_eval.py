"""KPP1 AS.03 L01 DWG -> card-plotted PDF -> album binding precision/recall (#1234).

Pattern: n/a | new-case: score dt_ai.album.binding against an independent DWG reference set (levels, axes).

Research tool, not production. Inputs (never committed): the L01 DXF made from the hashed customer DWG by
``tools/methods/body/dwg_to_dxf.py`` (receipt passed in). Steps:

1. ``plot``: every Layout1 viewport whose model window is >= 5 m high becomes one PDF page. Model LINE / LWPOLYLINE /
   ARC / CIRCLE and the same entities inside INSERTs (exploded with ezdxf ``virtual_entities``) become vector
   paths; MTEXT becomes real text (PyMuPDF CJK font, Cyrillic kept). HATCH fills are dropped (counted).
   The model->page transform is recorded per page; the binder never sees it.
2. ``truth`` from the DWG alone: a level text ``+2,100`` is true at model y = 2100 mm only when a dimension-layer
   LINE lies at that y (+-1 mm) within 6 m of the text; an axis is a grid LINE (``S-GRID``) with the grid label
   MTEXT nearest its lower end. Dimension values: the L01 DWG holds none (Revit export; no DIMENSION entity, no
   numeric dimension MTEXT), so the dimension-value truth set is empty and is reported as such.
3. ``score``: a predicted level is correct when its bound level line maps back to the true y within 1 pt; an axis
   when its label matches and its position maps back within 1 pt. Precision = correct / predicted,
   recall = correct / truth. Calibration is attempted with the DWG grid distances as anchors.

Usage: uv run --extra pdf-review --with ezdxf python tools/research/pdf_album/kpp1_binding_eval.py
       <L01.dxf> <dxf-receipt.json> <new-output-dir>
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

LEVEL = re.compile(r"^[+\-]?\d+,\d{3}$")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _plain(e) -> str:
    t = e.plain_text().strip()
    return re.sub(r"\\U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), t)


def _flatten(msp):
    from ezdxf.entities import Insert

    def walk(ents, depth=0):
        for e in ents:
            if isinstance(e, Insert) and depth < 6:
                try:
                    yield from walk(e.virtual_entities(), depth + 1)
                except Exception:  # noqa: BLE001 - counted as dropped by caller
                    continue
            else:
                yield e
    yield from walk(msp)


def plot(dxf: Path, pdf: Path) -> dict:
    import ezdxf
    import pymupdf

    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    windows = []
    for vp in doc.layouts.get("Layout1").query("VIEWPORT"):
        h = vp.dxf.view_height
        if h < 5000:
            continue
        w = h * vp.dxf.width / vp.dxf.height
        c = vp.dxf.view_center_point
        windows.append((c.x - w / 2, c.y - h / 2, c.x + w / 2, c.y + h / 2))
    windows.sort()
    ents = list(_flatten(msp))
    out = pymupdf.open()
    pages, dropped = [], {}
    font = pymupdf.Font("cjk")
    for x0, y0, x1, y1 in windows:
        W, H = 1190.0, 842.0
        k = min((W - 80) / (x1 - x0), (H - 80) / (y1 - y0))
        ox, oy = 40.0, 40.0

        def P(x, y):
            return (ox + (x - x0) * k, oy + (y1 - y) * k)

        page = out.new_page(width=W, height=H)
        page.insert_font(fontname="F0", fontbuffer=font.buffer)
        sh = page.new_shape()
        for e in ents:
            t = e.dxftype()
            try:
                if t == "LINE":
                    a, b = e.dxf.start, e.dxf.end
                    if not (x0 <= a.x <= x1 and y0 <= a.y <= y1 or x0 <= b.x <= x1 and y0 <= b.y <= y1):
                        continue
                    sh.draw_line(P(a.x, a.y), P(b.x, b.y))
                elif t == "LWPOLYLINE":
                    pts = [P(p[0], p[1]) for p in e.get_points("xy")]
                    if e.closed:
                        pts.append(pts[0])
                    if any(x0 <= (q[0] - ox) / k + x0 <= x1 for q in pts):
                        for a, b in zip(pts, pts[1:]):
                            sh.draw_line(a, b)
                elif t == "CIRCLE":
                    c = e.dxf.center
                    if x0 <= c.x <= x1 and y0 <= c.y <= y1:
                        sh.finish(color=(0, 0, 0), width=0.25)
                        sh.draw_circle(P(c.x, c.y), e.dxf.radius * k)
                        sh.finish(color=(0, 0, 0), width=0.25)
                elif t == "ARC":
                    c = e.dxf.center
                    if x0 <= c.x <= x1 and y0 <= c.y <= y1:
                        pts = [P(c.x + e.dxf.radius * math.cos(math.radians(a)), c.y + e.dxf.radius * math.sin(math.radians(a)))
                               for a in [e.dxf.start_angle + i * ((e.dxf.end_angle - e.dxf.start_angle) % 360) / 8 for i in range(9)]]
                        for a, b in zip(pts, pts[1:]):
                            sh.draw_line(a, b)
                elif t == "MTEXT":
                    ins = e.dxf.insert
                    if not (x0 <= ins.x <= x1 and y0 <= ins.y <= y1):
                        continue
                    txt = _plain(e)
                    if not txt or "\n" in txt:
                        txt = txt.split("\n")[0] if txt else ""
                    if not txt:
                        continue
                    size = max(e.dxf.char_height * k, 1.0)
                    att = e.dxf.get("attachment_point", 1)
                    width = font.text_length(txt, fontsize=size)
                    x, y = P(ins.x, ins.y)
                    x -= {1: 0, 2: 0.5, 3: 1}[(att - 1) % 3 + 1] * width
                    y += {0: size * 0.8, 1: size * 0.3, 2: 0.0}[(att - 1) // 3]
                    page.insert_text((x, y), txt, fontsize=size, fontname="F0")
                else:
                    dropped[t] = dropped.get(t, 0) + 1
            except Exception as exc:  # noqa: BLE001
                dropped[f"{t}:error:{type(exc).__name__}"] = dropped.get(f"{t}:error:{type(exc).__name__}", 0) + 1
        sh.finish(color=(0, 0, 0), width=0.25)
        sh.commit()
        pages.append({"window_mm": [x0, y0, x1, y1], "pt_per_mm": k, "origin_pt": [ox, oy]})
    if pdf.exists():
        raise SystemExit(f"exists: {pdf}")
    out.save(pdf)
    return {"pages": pages, "dropped_entities": dropped}


def truth(dxf: Path, transforms: list[dict]) -> dict:
    import ezdxf

    msp = ezdxf.readfile(dxf).modelspace()
    dims = [e for e in msp.query("LINE") if "DIMS" in e.dxf.layer and abs(e.dxf.start.y - e.dxf.end.y) < 0.5]
    grids = [e for e in msp.query("LINE") if "GRID" in e.dxf.layer and abs(e.dxf.start.x - e.dxf.end.x) < 0.5]
    labels = [e for e in msp.query("MTEXT") if "GRID" in e.dxf.layer]
    out = {"levels": [], "axes": [], "dimension_values": [], "unverified_levels": []}
    for n, tr in enumerate(transforms, 1):
        x0, y0, x1, y1 = tr["window_mm"]
        for e in msp.query("MTEXT"):
            t = _plain(e)
            ins = e.dxf.insert
            if not LEVEL.match(t) or not (x0 <= ins.x <= x1 and y0 <= ins.y <= y1):
                continue
            want = float(t.replace(",", ".")) * 1000.0
            ok = any(abs(d.dxf.start.y - want) <= 1.0 and min(abs(d.dxf.start.x - ins.x), abs(d.dxf.end.x - ins.x)) <= 6000 for d in dims)
            (out["levels"] if ok else out["unverified_levels"]).append({"page": n, "text": t, "model_y": want, "text_x": ins.x})
        for g in grids:
            x = g.dxf.start.x
            if not x0 <= x <= x1:
                continue
            low = min(g.dxf.start.y, g.dxf.end.y)
            best = min(labels, key=lambda m: math.dist((m.dxf.insert.x, m.dxf.insert.y), (x, low)), default=None)
            if best is not None and math.dist((best.dxf.insert.x, best.dxf.insert.y), (x, low)) <= 2000:
                out["axes"].append({"page": n, "label": _plain(best), "model_x": x})
    return out


def score(dims: dict, ref: dict, transforms: list[dict]) -> dict:
    rows = {}
    pred_levels = [v for v in dims["values"] if v["kind"] == "level" and v.get("level_y") is not None]
    correct = 0
    for v in pred_levels:
        tr = transforms[v["page"] - 1]
        model_y = tr["window_mm"][3] - (v["level_y"] - tr["origin_pt"][1]) / tr["pt_per_mm"]
        tol = 1.0 / tr["pt_per_mm"]
        v["_model_y"] = model_y
        if any(t["page"] == v["page"] and t["text"].lstrip("+") == v["raw"].lstrip("+") and abs(t["model_y"] - model_y) <= tol
               for t in ref["levels"]):
            correct += 1
    rows["level -> level line"] = {"truth": len(ref["levels"]), "predicted": len(pred_levels), "correct": correct}
    pred_axes = [(vw["page"], a) for vw in dims["views"] for a in vw["axes"] if a["orientation"] == "vertical"]
    correct = 0
    for page, a in pred_axes:
        tr = transforms[page - 1]
        x = tr["window_mm"][0] + (a["position"] - tr["origin_pt"][0]) / tr["pt_per_mm"]
        if any(t["page"] == page and t["label"] == a["label"] and abs(t["model_x"] - x) <= 1.0 / tr["pt_per_mm"] for t in ref["axes"]):
            correct += 1
    rows["axis label + position"] = {"truth": len(ref["axes"]), "predicted": len(pred_axes), "correct": correct}
    bound_dims = [v for v in dims["values"] if v["kind"] == "dimension" and v["binding"]["type"] != "unbound"]
    rows["dimension value -> axis pair/opening/level pair"] = {"truth": 0, "predicted": len(bound_dims), "correct": 0}
    for r in rows.values():
        r["precision"] = round(r["correct"] / r["predicted"], 3) if r["predicted"] else None
        r["recall"] = round(r["correct"] / r["truth"], 3) if r["truth"] else None
    return rows


def main(argv: list[str]) -> int:
    dxf, receipt, outdir = Path(argv[0]), Path(argv[1]), Path(argv[2])
    if outdir.exists():
        print(f"output_exists: {outdir}")
        return 2
    rec = json.loads(receipt.read_text(encoding="utf-8"))
    if rec.get("status") != "pass" or rec["dxf"]["sha256"] != _sha(dxf):
        print("dxf receipt does not match the DXF")
        return 2
    outdir.mkdir(parents=True)
    pdf = outdir / "L01-plotted.pdf"
    plotted = plot(dxf, pdf)
    ref = truth(dxf, plotted["pages"])
    from dt_ai.album import binding as B

    anchors = []
    for n, _ in enumerate(plotted["pages"], 1):
        axes = sorted((a for a in ref["axes"] if a["page"] == n), key=lambda a: a["model_x"])
        for a, b in zip(axes, axes[1:]):
            anchors.append({"page": n, "axes": [a["label"], b["label"]], "model_mm": round(b["model_x"] - a["model_x"], 3)})
    apath = outdir / "anchors.json"
    apath.write_text(json.dumps({"source": {"sha256": rec["source"]["sha256"], "kind": "dwg",
                                            "path": rec["source"]["path"]}, "anchors": anchors}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    dims = B.bind_album(pdf, anchors=apath)
    (outdir / "L01-dimensions.json").write_text(B.dimensions_to_json(dims), encoding="utf-8")
    table = score(dims, ref, plotted["pages"])
    report = {"dwg": rec["source"], "dxf": rec["dxf"], "pdf": {"path": str(pdf), "sha256": _sha(pdf)},
              "plot": plotted, "reference": {k: len(v) for k, v in ref.items()}, "table": table,
              "scales": [{"view": vw["id"], **{k: vw["scale"][k] for k in ("status", "reason")}} for vw in dims["views"]],
              "summary": dims["summary"], "passed": False}
    (outdir / "reference.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "score.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"table": table, "reference": report["reference"], "scales": report["scales"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
