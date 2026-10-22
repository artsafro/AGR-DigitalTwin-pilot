"""new-case: AC08 acceptance sheets - each facade render NEXT TO the matching presentation facade slide AT THE SAME SCALE,
with the rib count measured on every image written below it (Artem 2026-10-22 rework, PR #574).

Usage: uv run python compare_facades.py <spec.json> <sheet-facades.json> <renders_dir> <vpm.readback.json>
                                        <new_out_dir> [--px-per-m 200]
Per facade one PNG `compare_<view>_<facade>.png` with three panels, all resampled to the same px/m and aligned on ±0.000
(Artem 2026-10-22: the presentation slide is THE authority, the DWG column is dropped) [D171]:
  1. the presentation facade slide (spec presentation: deck slide image, sha256 checked), cropped to that facade, its
     scale from the drawn body width (height_scale_ratio = the same scale measured on the body height);
  2. the VPM render and 3. the NPM render of the delivered readback FBX (render_facades.py, camera in renders.json),
     clipped at the facade's ground line (lowest Ур.з.) like the slide.
Counts: slide = joint lines counted on the slide pixels between the field outlines (slide_count, no DWG positions),
renders = joints measured on the rendered pixels (joint_count.render_row + count_joints) - never the spec value. The
facade legend is validated first (finish_map.validate_legend). Writes compare.json with every count; a facade whose
slide, VPM or NPM count differs from the contract (ribs - 1) is marked MISMATCH in the image and the JSON.
"""
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finish_map  # noqa: E402
import joint_count  # noqa: E402

VIEW = {"+y": "north", "-y": "south", "+x": "east", "-x": "west"}
FONT = "C:/Windows/Fonts/arial.ttf"
Z_TOP, Z_BOT = 2.85, -0.45          # metres shown above / below ±0.000 in every panel


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except OSError:
        return ImageFont.load_default()


def slide_boxes(im):
    """Bounding boxes (x0, y0, x1, y1 px) of the four blue facade bodies of the slide, in reading order
    (top-left, top-right, bottom-left, bottom-right = spec presentation.quadrants)."""
    im = np.asarray(im).astype(int)
    blue = (im[..., 2] > 130) & (im[..., 0] < 60)
    H, W = blue.shape
    boxes = []
    for r0, r1 in ((0, H // 2), (H // 2, H)):
        for c0, c1 in ((0, W // 2), (W // 2, W)):
            ys, xs = np.where(blue[r0:r1, c0:c1])
            if not len(xs):
                raise ValueError(f"no blue facade body in slide quadrant rows {r0}:{r1} cols {c0}:{c1}")
            boxes.append((c0 + xs.min(), r0 + ys.min(), c0 + xs.max() + 1, r0 + ys.max() + 1))
    return boxes


def slide_count(im, box, f, frac=0.9, margin=3):
    """Ribs drawn on the slide itself: dark runs on the row at `frac` of the body height (above the door) between
    the body outline and the panel-field outline on each side. The outermost run per side = body outline, the next
    = field outline (it must lie inside the frame band, < 300 mm from the body edge); every run between the field
    outlines is one joint line. Scale: body width in px / the drawing's body width (sheet size_mm); the same scale
    measured on the body height is returned as height_scale_ratio (1.0 = one drawing scale). No DWG joint
    positions are used. Raises ValueError when the outlines are missing."""
    im = np.asarray(im)
    x0, y0, x1, y1 = box
    pxmm = (x1 - x0) / f["size_mm"][0]
    y = int(round(y1 - frac * (y1 - y0)))
    row = im[y, x0 - margin:x1 + margin].astype(float).sum(-1)
    dark = row < 0.75 * np.median(row)
    cen = [x0 - margin + (a + b - 1) / 2 + 0.5 for a, b in joint_count.runs(dark)]
    band = 300 * pxmm
    if (len(cen) < 4 or not (0 < cen[1] - cen[0] < band) or not (0 < cen[-1] - cen[-2] < band)
            or cen[0] > x0 + 1 or cen[-1] < x1 - 1):
        raise ValueError(f"slide facade {box}: body/field outline not found on row y={y} (runs {len(cen)})")
    joints = cen[2:-2]
    field_mm = (cen[-2] - cen[1]) / pxmm
    return {"joints": len(joints), "field_mm": field_mm, "step_mm": field_mm / (len(joints) + 1), "row_y": y,
            "px_per_mm": pxmm, "height_scale_ratio": ((y1 - y0) / f["size_mm"][1]) / pxmm,
            "joint_x_mm": [round((c - cen[1]) / pxmm, 1) for c in joints]}


def panel_slide(im, box, f, pxm):
    """The slide facade cropped to body +-0.3 m, Z_BOT..Z_TOP around ±0.000 (= bottom of the blue body), resampled
    to pxm with the slide's own scale (body width / drawing body width)."""
    x0, y0, x1, y1 = box
    pxmm = (x1 - x0) / f["size_mm"][0]
    zero_y = y1
    top = zero_y - Z_TOP * 1000 * pxmm
    bot = zero_y - Z_BOT * 1000 * pxmm
    pad = 0.3 * 1000 * pxmm
    crop = Image.fromarray(np.asarray(im)).crop((int(round(x0 - pad)), int(round(top)), int(round(x1 + pad)),
                                                 int(round(bot))))
    w = int(round((f["size_mm"][0] / 1000 + 0.6) * pxm))
    return crop.resize((w, int(round((Z_TOP - Z_BOT) * pxm))), Image.LANCZOS)


def panel_render(png, view, key, lo, hi, pxm, ground_m):
    """Crop the render to the facade body +-0.3 m, Z_BOT..Z_TOP, resampled to pxm (the render's own px/m is fixed).
    Below the slide's ground line (ground_m, the facade's lowest Ур.з. = bottom of the drawn plinth) the building is
    underground: painted white with a black ground line, as on the slide (the model below grade is unchanged)."""
    rgba = Image.open(png).convert("RGBA")
    img = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    img.alpha_composite(rgba)                       # transparent background -> white, like the sheet
    c, r = np.asarray(view["center"]), np.asarray(view["right"])
    W, H = view["res"]
    scale = view["ortho_scale"] / W
    axis = 1 if key in ("+x", "-x") else 0
    # pixel x of world coordinate along the facade axis
    px = lambda s: W / 2 + (s - c[axis]) * r[axis] / scale  # noqa: E731
    py = lambda z: H / 2 - (z - c[2]) / scale  # noqa: E731
    xa, xb = sorted((px(lo - 0.3), px(hi + 0.3)))
    box = (int(round(xa)), int(round(py(Z_TOP))), int(round(xb)), int(round(py(Z_BOT))))
    crop = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (255, 255, 255))   # outside the render = white
    crop.paste(img.convert("RGB").crop((max(box[0], 0), max(box[1], 0), min(box[2], W), min(box[3], H))),
               (max(-box[0], 0), max(-box[1], 0)))
    w = int(round((hi - lo + 0.6) * pxm))
    out = crop.resize((w, int(round((Z_TOP - Z_BOT) * pxm))), Image.LANCZOS)
    g = int(round((Z_TOP - ground_m) * pxm))
    d = ImageDraw.Draw(out)
    d.rectangle([0, g, w, out.height], fill=(255, 255, 255))
    d.line([0, g, w, g], fill=(0, 0, 0), width=2)
    return out


# ------------------------------------------------------------------ several panel fields per facade (AC04)
def slide_boxes_solid(im):
    """slide_boxes for slides whose quadrants also hold thin blue outlines (AC04 slide 31: a pipe drawn in blue
    outline next to facade 1-2): the body = columns/rows holding >= 30 % of the quadrant's densest blue column/row."""
    im = np.asarray(im).astype(int)
    blue = (im[..., 2] > 130) & (im[..., 0] < 60)
    H, W = blue.shape
    boxes = []
    for r0, r1 in ((0, H // 2), (H // 2, H)):
        for c0, c1 in ((0, W // 2), (W // 2, W)):
            b = blue[r0:r1, c0:c1]
            col = b.sum(0)
            if not col.max():
                raise ValueError(f"no blue facade body in slide quadrant rows {r0}:{r1} cols {c0}:{c1}")
            xs = np.where(col >= 0.3 * col.max())[0]
            row = b[:, xs.min():xs.max() + 1].sum(1)
            ys = np.where(row >= 0.3 * row.max())[0]
            boxes.append((c0 + xs.min(), r0 + ys.min(), c0 + xs.max() + 1, r0 + ys.max() + 1))
    return boxes


def _yellow(px):
    px = np.asarray(px, int)
    return (px[..., 0] > 100) & (px[..., 1] > 80) & (px[..., 2] < 60)


def slide_fields_row(im, box, body_mm, frac, merge_px=3.0, margin=3):
    """Panel fields and joint lines on ONE pixel row of a slide facade (no DWG positions). Dark runs (< 0.75 x row
    median) closer than merge_px are one line (a joint drawn next to a door edge). Outermost line per side = body
    outline, the next = field outline (inside the 300 mm frame band). Two neighbouring lines closer than 300 mm inside
    the body = the frame posts between two containers (field end + next field start). A line with RAL 1021 yellow
    within 3 px is a ladder stringer in front of the wall, not a joint (reported as `ladder`). Raises ValueError when
    the outlines are missing."""
    im = np.asarray(im)
    x0, y0, x1, y1 = box
    pxmm = (x1 - x0) / body_mm
    y = int(round(y1 - frac * (y1 - y0)))
    row = im[y, x0 - margin:x1 + margin].astype(float).sum(-1)
    cen = [x0 - margin + (a + b - 1) / 2 + 0.5 for a, b in joint_count.runs(row < 0.75 * np.median(row))]
    merged = []
    for c in cen:
        if merged and c - merged[-1][-1] <= merge_px:
            merged[-1].append(c)
        else:
            merged.append([c])
    lines = [float(np.mean(m)) for m in merged]
    band = 300 * pxmm
    if (len(lines) < 4 or not (0 < lines[1] - lines[0] < band) or not (0 < lines[-1] - lines[-2] < band)
            or lines[0] > x0 + 1 or lines[-1] < x1 - 1):
        raise ValueError(f"slide facade {box}: body/field outline not found on row y={y} ({len(lines)} lines)")
    inner = lines[1:-1]
    fields, cur = [], {"lo_px": inner[0], "joints_px": [], "ladder_px": []}
    i = 1
    while i < len(inner):
        c = inner[i]
        if i < len(inner) - 1 and inner[i + 1] - c < band:      # frame posts between two panel fields
            cur["hi_px"] = c
            fields.append(cur)
            cur = {"lo_px": inner[i + 1], "joints_px": [], "ladder_px": []}
            i += 2
            continue
        if i == len(inner) - 1:
            cur["hi_px"] = c
            fields.append(cur)
            break
        xi = int(round(c))
        (cur["ladder_px"] if _yellow(im[y, xi - 3:xi + 4]).any() else cur["joints_px"]).append(round(c, 1))
        i += 1
    for f in fields:
        f["joints"] = len(f["joints_px"])
        f["field_mm"] = round((f["hi_px"] - f["lo_px"]) / pxmm, 1)
    return {"row_y": y, "px_per_mm": pxmm, "height_scale_ratio": None, "fields": fields}


def slide_fields(im, box, body_mm, fracs):
    """Fields and joints counted on several rows; per field the count seen on most rows wins (a label, a door handle or
    a louvre crosses single rows). Rows that split the body into a different number of fields are reported, not used."""
    rows = {}
    for fr in fracs:
        try:
            rows[f"{fr:.2f}"] = slide_fields_row(im, box, body_mm, fr)
        except ValueError as e:
            rows[f"{fr:.2f}"] = {"error": str(e)}
    good = [r for r in rows.values() if "fields" in r]
    if not good:
        raise ValueError(f"slide facade {box}: no row with outlines: {rows}")
    nf = max(set(len(r["fields"]) for r in good), key=lambda n: sum(len(r["fields"]) == n for r in good))
    use = [r for r in good if len(r["fields"]) == nf]
    out = []
    for k in range(nf):
        cnt = [r["fields"][k]["joints"] for r in use]
        mode = max(set(cnt), key=lambda n: (cnt.count(n), -n))
        if sorted((cnt.count(n) for n in set(cnt)), reverse=True)[:2].count(cnt.count(mode)) > 1:
            raise ValueError(f"slide field {k}: no single most frequent joint count over rows {cnt}")
        ref = next(r["fields"][k] for r in use if r["fields"][k]["joints"] == mode)
        out.append({"joints": mode, "rows": cnt, "field_mm": ref["field_mm"], "ladder_lines": len(ref["ladder_px"]),
                    "joints_px": ref["joints_px"], "ladder_px": ref["ladder_px"]})
    return {"fields": out, "rows": rows}


def field_groups(spec, slide_name):
    """Spec fields of one slide facade merged where they touch (the shared edge is one joint): ordered left -> right
    as seen from outside. Each group: lo, hi (world along the facade), joints expected (ribs - 1 per field + touching
    edges) and their world positions."""
    fs = [(n, f) for n, f in spec["facades"].items() if f.get("slide_facade") == slide_name]
    if not fs:
        raise ValueError(f"no spec field for slide facade {slide_name}")
    keys = {f["normal"] for _, f in fs}
    if len(keys) != 1:
        raise ValueError(f"slide facade {slide_name}: fields face {keys}")
    key = keys.pop()
    fs.sort(key=lambda t: t[1]["span"][0])
    groups = []
    for n, f in fs:
        a, b = f["span"]
        P = (b - a) / f["ribs"]
        js = [a + k * P for k in range(1, f["ribs"])]
        if groups and abs(groups[-1]["hi"] - a) <= 1e-3:
            g = groups[-1]
            g["joints_world"] += [a] + js
            g["hi"] = b
            g["fields"].append(n)
        else:
            groups.append({"lo": a, "hi": b, "joints_world": js, "fields": [n]})
    rev = key in ("+y", "-x")              # facade u grows against the world axis (finish_map.facade_uv)
    if rev:
        groups.reverse()
    for g in groups:
        g["joints_expected"] = len(g["joints_world"])
    return key, groups


def render_group_count(img, view, key, g, z, tol=0.02, edge=0.1):
    axis = 1 if key in ("+x", "-x") else 0
    s, lum = joint_count.render_row(img, view, axis, z, g["lo"], g["hi"])
    ok = np.isfinite(lum)
    if ok.sum() < 10:
        return {"ok": False, "reason": "no panel pixels", "joints_found": 0}
    thr = 0.85 * np.median(lum[ok])
    found = [float(s[a:b].mean()) for a, b in joint_count.runs(ok & (lum < thr))]
    found = [c for c in found if g["lo"] + edge < c < g["hi"] - edge]
    hidden = [e for e in g["joints_world"] if not (ok & (np.abs(s - e) <= max(tol, 0.006))).any()]
    vis = [e for e in g["joints_world"] if e not in hidden]
    # a joint ON the edge of another finish (the door leaf on 1-2): only its 4 mm half on the panel side shows, < 2 px
    # at 400 px/m; reported as at_edge, not missing, when the render has no panel pixel on one side of it
    at_edge = [e for e in vis if not any(abs(f - e) <= tol for f in found)
               and (~ok[np.abs(s - e) <= 0.012]).any()]
    missing = [round(e, 4) for e in vis if e not in at_edge and not any(abs(f - e) <= tol for f in found)]
    extra = [round(f, 4) for f in found if not any(abs(f - e) <= tol for e in g["joints_world"])]
    return {"ok": not missing and not extra, "joints_found": len(found), "joints_expected": g["joints_expected"],
            "hidden_m": [round(e, 4) for e in hidden], "at_edge_m": [round(e, 4) for e in at_edge], "missing_m": missing, "extra_m": extra,
            "found_m": [round(f, 4) for f in found], "z": round(z, 3)}


def main_fields(spec, sheet, rdir, out, pxm, dump_p):
    """AC04 path: several panel fields per facade (spec facades with `span` + `slide_facade`). Spans are source world
    metres; the delivered FBX is shifted by the export pivot (plan centre of the source body bbox, qa_packages)."""
    body = next(n for n in json.load(open(dump_p, encoding="utf-8"))["nodes"] if n["multisub"])
    sv = np.asarray(body["vertices"], float)
    shift = [(sv[:, 0].min() + sv[:, 0].max()) / 2, (sv[:, 1].min() + sv[:, 1].max()) / 2]
    pres = spec["presentation"]
    with open(pres["image"], "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if sha != pres["image_sha256"]:
        raise SystemExit(f"slide image {pres['image']} sha256 {sha} != spec {pres['image_sha256']}")
    names = sorted({f.get("slide_facade") for f in spec["facades"].values()})
    if sorted(pres["quadrants"]) != names:
        raise SystemExit(f"slide quadrants {pres['quadrants']} != spec slide facades {names}")
    meta = json.load(open(os.path.join(rdir, "renders.json"), encoding="utf-8"))
    slide = np.asarray(Image.open(pres["image"]).convert("RGB"))
    boxes = dict(zip(pres["quadrants"], slide_boxes_solid(slide)))
    os.makedirs(out)
    report = {"px_per_m": pxm, "slide": pres["image"], "slide_sha256": sha, "slide_no": pres["slide"], "facades": {}}
    fracs = sheet.get("slide_rows", [0.3, 0.45, 0.6, 0.75])
    for name in pres["quadrants"]:
        f = sheet["facades"][name]
        key, groups = field_groups(spec, name)
        ax = 1 if key in ("+x", "-x") else 0
        for g in groups:                                   # source world -> delivered (pivot-shifted) coordinates
            g["lo"], g["hi"] = g["lo"] - shift[ax], g["hi"] - shift[ax]
            g["joints_world"] = [e - shift[ax] for e in g["joints_world"]]
        sl = slide_fields(slide, boxes[name], f["size_mm"][0], fracs)
        blo, bhi = f["body_m"][0] - shift[ax], f["body_m"][1] - shift[ax]
        counts = {"normal": key, "slide_box_px": [int(v) for v in boxes[name]], "slide_rows": sl["rows"],
                  "slide_fields": sl["fields"], "groups": [], "ground_m": f["ground_m"]}
        x0, y0, x1, y1 = boxes[name]
        counts["slide_height_scale_ratio"] = round(((y1 - y0) / f["size_mm"][1]) / ((x1 - x0) / f["size_mm"][0]), 4)
        imgs = {t: np.asarray(Image.open(os.path.join(rdir, meta[t]["views"][VIEW[key]]["png"])).convert("RGB"))
                for t in ("vpm", "npm")}
        match = len(sl["fields"]) == len(groups)
        tot = {"slide": 0, "vpm": 0, "npm": 0, "contract": 0}
        for k, g in enumerate(groups):
            zlo, zhi = sheet.get("field_z_m", [0.2377, 2.9297])
            gr = {"fields": g["fields"], "lo": round(g["lo"], 4), "hi": round(g["hi"], 4),
                  "contract_joints": g["joints_expected"]}
            for t in ("vpm", "npm"):
                rows = [render_group_count(imgs[t], meta[t]["views"][VIEW[key]], key, g, zlo + fr * (zhi - zlo))
                        for fr in (0.2, 0.95)]
                gr[f"{t}_rows"] = rows
                gr[f"{t}_visible"] = rows[1]["joints_found"]
                gr[f"{t}_hidden"] = len(rows[1].get("hidden_m", []))
                match &= all(r["ok"] for r in rows)
            sf = sl["fields"][k] if k < len(sl["fields"]) else None
            gr["slide_joints"] = sf["joints"] if sf else None
            gr["slide_ladder_lines"] = sf["ladder_lines"] if sf else None
            # the slide count must equal the joints the render SHOWS; joints hidden in the render (door, ladder in
            # front) must be hidden on the slide too (a ladder stringer stands there) - and shown + hidden = contract
            vis_ok = sf is not None and sf["joints"] == gr["vpm_visible"] == gr["npm_visible"]
            hid_ok = gr["vpm_hidden"] == gr["npm_hidden"] and (gr["vpm_hidden"] == 0 or (sf and sf["ladder_lines"] > 0))
            con_ok = gr["vpm_visible"] + gr["vpm_hidden"] == g["joints_expected"]
            gr["match"] = bool(vis_ok and hid_ok and con_ok)
            match &= gr["match"]
            counts["groups"].append(gr)
            tot["slide"] += sf["joints"] if sf else 0
            tot["vpm"] += gr["vpm_visible"]
            tot["npm"] += gr["npm_visible"]
            tot["contract"] += g["joints_expected"]
        counts["totals_visible"] = tot
        counts["match"] = bool(match)
        sizes = {"size_mm": f["size_mm"], "frame_bands_mm": {"left": 0, "right": 0}}
        panels = [(f"Слайд {pres['slide']} презентации", panel_slide(slide, boxes[name], sizes, pxm), tot["slide"])]
        for t in ("vpm", "npm"):
            panels.append((f"{t.upper()} рендер", panel_render(os.path.join(rdir, meta[t]["views"][VIEW[key]]["png"]),
                                                              meta[t]["views"][VIEW[key]], key, blo, bhi, pxm,
                                                              f["ground_m"]), tot[t]))
        per = " + ".join(str(gr["slide_joints"]) for gr in counts["groups"])
        gap, lab = 24, 100
        Wt = sum(p.width for _, p, _ in panels) + gap * (len(panels) + 1)
        Ht = max(p.height for _, p, _ in panels) + lab + 50
        img = Image.new("RGB", (Wt, Ht), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((gap, 10), f"Фасад {name}: слайд и рендеры в одном масштабе {pxm:.0f} px/м, ±0.000 на одной высоте"
               + ("" if counts["match"] else "   MISMATCH"), fill=(0, 0, 0) if counts["match"] else (200, 0, 0),
               font=font(22))
        x = gap
        for i, (title, p, n) in enumerate(panels):
            img.paste(p, (x, 45))
            d.text((x, 45 + p.height + 6), title, fill=(0, 0, 0), font=font(18))
            tag = ["slide", "vpm", "npm"][i]
            parts = " + ".join(str(gr["slide_joints"] if tag == "slide" else gr[f"{tag}_visible"])
                               for gr in counts["groups"])
            d.text((x, 45 + p.height + 30), f"швов: {parts} = {n}", fill=(0, 0, 0), font=font(20))
            hid = sum(gr.get(f"{tag}_hidden", 0) for gr in counts["groups"]) if tag != "slide" else \
                sum(gr["slide_ladder_lines"] or 0 for gr in counts["groups"])
            if hid:
                d.text((x, 45 + p.height + 56), ("стоек лестницы на стене: " if tag == "slide" else
                                                 "швов за лестницей/дверью: ") + str(hid), fill=(0, 0, 0), font=font(18))
            x += p.width + gap
        png = os.path.join(out, f"compare_{VIEW[key]}_{name}.png")
        img.save(png, optimize=True)
        counts["png"] = os.path.basename(png)
        counts["slide_per_field"] = per
        report["facades"][name] = counts
        print("COMPARE", name, json.dumps({"match": counts["match"], "totals": tot,
                                            "per_field": [(gr["slide_joints"], gr["vpm_visible"], gr["npm_visible"],
                                                           gr["vpm_hidden"], gr["contract_joints"])
                                                          for gr in counts["groups"]]}, ensure_ascii=False))
    with open(os.path.join(out, "compare.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    return 0 if all(c["match"] for c in report["facades"].values()) else 1


def main(argv):
    spec_p, sheet_p, rdir, vrb_p, out = argv[:5]
    pxm = float(argv[argv.index("--px-per-m") + 1]) if "--px-per-m" in argv else 200.0
    if os.path.lexists(out):
        raise SystemExit(f"refusing to overwrite {out}")
    spec, sheet = json.load(open(spec_p, encoding="utf-8")), json.load(open(sheet_p, encoding="utf-8"))
    finish_map.validate_legend(spec, finish_map.load_kpp())      # legend checked before anything is shown
    if any("slide_facade" in f for f in spec["facades"].values()):
        if "--dump" not in argv:
            raise SystemExit("several fields per facade: --dump <max-dump.json> is needed for the export pivot shift")
        return main_fields(spec, sheet, rdir, out, pxm, argv[argv.index("--dump") + 1])
    pres = spec["presentation"]
    with open(pres["image"], "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if sha != pres["image_sha256"]:
        raise SystemExit(f"slide image {pres['image']} sha256 {sha} != spec {pres['image_sha256']}")
    if sorted(pres["quadrants"]) != sorted(spec["facades"]):
        raise SystemExit(f"slide quadrants {pres['quadrants']} != spec facades {sorted(spec['facades'])}")
    meta = json.load(open(os.path.join(rdir, "renders.json"), encoding="utf-8"))
    vrb = json.load(open(vrb_p, encoding="utf-8"))
    vmain = next(o for o in vrb["objects"] if not o["name"].startswith("UCX_"))
    V = np.asarray(vmain["vertices"], float)
    uvs = [np.asarray(u, float) for u in vmain["face_uvs"]]
    slide = np.asarray(Image.open(pres["image"]).convert("RGB"))
    boxes = dict(zip(pres["quadrants"], slide_boxes(slide)))
    os.makedirs(out)
    report = {"px_per_m": pxm, "slide": pres["image"], "slide_sha256": sha, "slide_no": pres["slide"], "facades": {}}
    for name, fc in spec["facades"].items():
        f = sheet["facades"][name]
        key = fc["normal"]
        ud = spec["finishes"][fc["finish"]]["udim"]
        keep = lambda t, ud=ud: int(1001 + np.floor(uvs[t].mean(0)[0]) + 10 * np.floor(uvs[t].mean(0)[1])) == ud  # noqa
        tris = joint_count.facade_triangles(V, vmain["faces"], keep, key)
        lo, hi, zlo, zhi = joint_count.field_extent(V, vmain["faces"], tris, key)
        # the body outline (frame outer faces) for the crop: field +- the drawing's frame posts
        blo, bhi = lo - f["frame_bands_mm"]["left"] / 1000, hi + f["frame_bands_mm"]["right"] / 1000
        ground = min(p["bbox_mm"][1] for p in f["plinth"]) / 1000
        sc = slide_count(slide, boxes[name], f)
        counts = {"panels": ["slide", "vpm", "npm"], "slide_joints": sc["joints"], "slide_step_mm": sc["step_mm"],
                  "slide_field_mm": sc["field_mm"], "slide_height_scale_ratio": sc["height_scale_ratio"],
                  "slide_box_px": [int(v) for v in boxes[name]], "contract_ribs": fc["ribs"],
                  "sheet_dwg_joints": f["joints"], "ground_m": ground}
        panels = [(f"Слайд {pres['slide']} презентации", panel_slide(slide, boxes[name], f, pxm), sc["joints"])]
        for tag in ("vpm", "npm"):
            view = meta[tag]["views"][VIEW[key]]
            img = np.asarray(Image.open(os.path.join(rdir, view["png"])).convert("RGB"))
            axis = 1 if key in ("+x", "-x") else 0
            rows = {}
            for frac in (0.2, 0.95):
                z = zlo + frac * (zhi - zlo)
                s, lum = joint_count.render_row(img, view, axis, z, lo, hi)
                rows[f"z={z:.3f}"] = joint_count.count_joints(s, lum, lo, hi, fc["ribs"], tol=0.01, dark=0.85)
            top = rows[f"z={zlo + 0.95 * (zhi - zlo):.3f}"]
            counts[f"{tag}_render_joints"] = top["joints_found"]
            counts[f"{tag}_render_rows"] = rows
            panels.append((f"{tag.upper()} рендер", panel_render(os.path.join(rdir, view["png"]), view, key, blo, bhi,
                                                                 pxm, ground), top["joints_found"]))
        want = fc["ribs"] - 1
        ok = all(c == want for c in (sc["joints"], counts["vpm_render_joints"], counts["npm_render_joints"]))
        counts["match"] = bool(ok and all(r["ok"] for t in ("vpm", "npm") for r in counts[f"{t}_render_rows"].values()))
        gap, lab = 24, 70
        Wt = sum(p.width for _, p, _ in panels) + gap * (len(panels) + 1)
        Ht = max(p.height for _, p, _ in panels) + lab + 50
        sheet_img = Image.new("RGB", (Wt, Ht), (255, 255, 255))
        d = ImageDraw.Draw(sheet_img)
        d.text((gap, 10), f"Фасад {name}: слайд и рендеры в одном масштабе {pxm:.0f} px/м, ±0.000 на одной высоте"
               + ("" if counts["match"] else "   MISMATCH"), fill=(0, 0, 0) if counts["match"] else (200, 0, 0),
               font=font(22))
        x = gap
        for title, p, n in panels:
            sheet_img.paste(p, (x, 45))
            d.text((x, 45 + p.height + 6), title, fill=(0, 0, 0), font=font(18))
            d.text((x, 45 + p.height + 30), f"{n + 1} рёбер / {n} швов", fill=(0, 0, 0), font=font(20))
            x += p.width + gap
        png = os.path.join(out, f"compare_{VIEW[key]}_{name}.png")
        sheet_img.save(png, optimize=True)
        counts["png"] = os.path.basename(png)
        report["facades"][name] = counts
        print("COMPARE", name, {k: v for k, v in counts.items() if not k.endswith("_rows")})
    with open(os.path.join(out, "compare.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    return 0 if all(c["match"] for c in report["facades"].values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
