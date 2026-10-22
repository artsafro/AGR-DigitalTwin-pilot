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


def slide_boxes(im, gap=10, min_px=40):
    """Bounding boxes (x0, y0, x1, y1 px) of the four blue facade bodies of the slide, in reading order
    (top-left, top-right, bottom-left, bottom-right = spec presentation.quadrants)."""
    im = np.asarray(im).astype(int)
    blue = (im[..., 2] > 130) & (im[..., 0] < 60)
    H, W = blue.shape
    boxes = []
    for r0, r1 in ((0, H // 2), (H // 2, H)):
        # AC05 slide 35: the long facade starts left of W/2, so the bodies are not split at the image centre; each
        # body = a group of columns holding blue pixels, groups closer than `gap` px merged (outlines, axis lines)
        groups = []
        for a, b in joint_count.runs(blue[r0:r1].any(0)):
            if groups and a - groups[-1][1] <= gap:
                groups[-1][1] = b
            else:
                groups.append([a, b])
        groups = sorted(sorted(groups, key=lambda g: g[1] - g[0], reverse=True)[:2])
        if len(groups) < 2 or min(b - a for a, b in groups) < min_px:
            raise ValueError(f"slide rows {r0}:{r1}: two blue facade bodies expected, column groups {groups}")
        for a, b in groups:
            ys = np.where(blue[r0:r1, a:b].any(1))[0]
            boxes.append((a, r0 + ys.min(), b, r0 + ys.max() + 1))
    return boxes


def slide_count(im, box, f, frac=0.9, margin=3, skip_inner=0):
    """Ribs drawn on the slide itself: dark runs on the row at `frac` of the body height (above the door) between
    the body outline and the panel-field outline on each side. The outermost run per side = body outline when it sits
    on the box edge (AC05 slide 35 draws the left body outline red, not dark: then there is none), the next = field
    outline (it must lie inside the frame band, < 300 mm from the body edge); `skip_inner` more runs per side are the
    end wall's inner frame (AC05 Б-А), not joints; every run between is one joint line. Scale: body width in px / the
    drawing's body width (sheet size_mm); the same scale
    measured on the body height is returned as height_scale_ratio (1.0 = one drawing scale). No DWG joint
    positions are used. Raises ValueError when the outlines are missing."""
    im = np.asarray(im)
    x0, y0, x1, y1 = box
    pxmm = (x1 - x0) / f["size_mm"][0]
    y = int(round(y1 - frac * (y1 - y0)))
    row = im[y, x0 - margin:x1 + margin].astype(float).sum(-1)
    dark = row < 0.75 * np.median(row)
    cen = [x0 - margin + (a + b - 1) / 2 + 0.5 for a, b in joint_count.runs(dark)]
    if cen and cen[0] <= x0 + 1:
        cen = cen[1:]
    if cen and cen[-1] >= x1 - 1:
        cen = cen[:-1]
    band = 300 * pxmm
    k = 1 + skip_inner
    if (len(cen) < 2 * k or not (0 < cen[0] - x0 < band) or not (0 < x1 - cen[-1] < band)):
        raise ValueError(f"slide facade {box}: body/field outline not found on row y={y} (runs {len(cen)})")
    joints = cen[k:-k]
    field_mm = (cen[-1] - cen[0]) / pxmm
    return {"joints": len(joints), "field_mm": field_mm, "step_mm": field_mm / (len(joints) + 1), "row_y": y,
            "px_per_mm": pxmm, "height_scale_ratio": ((y1 - y0) / f["size_mm"][1]) / pxmm,
            "joint_x_mm": [round((c - cen[0]) / pxmm, 1) for c in joints]}


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


def main(argv):
    spec_p, sheet_p, rdir, vrb_p, out = argv[:5]
    pxm = float(argv[argv.index("--px-per-m") + 1]) if "--px-per-m" in argv else 200.0
    if os.path.lexists(out):
        raise SystemExit(f"refusing to overwrite {out}")
    spec, sheet = json.load(open(spec_p, encoding="utf-8")), json.load(open(sheet_p, encoding="utf-8"))
    finish_map.validate_legend(spec, finish_map.load_kpp())      # legend checked before anything is shown
    pres = spec["presentation"]
    with open(pres["image"], "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if sha != pres["image_sha256"]:
        raise SystemExit(f"slide image {pres['image']} sha256 {sha} != spec {pres['image_sha256']}")
    plain = spec.get("facades_plain") or {}       # AC05 А-Б: a slide facade without a sandwich rib field (gate)
    if set(plain) & set(spec["facades"]) or sorted(pres["quadrants"]) != sorted(list(spec["facades"]) + list(plain)):
        raise SystemExit(f"slide quadrants {pres['quadrants']} != spec facades {sorted(spec['facades'])} + "
                         f"facades_plain {sorted(plain)} (each once)")
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
        sc = slide_count(slide, boxes[name], f, frac=fc.get("slide_row_frac", 0.9),
                         skip_inner=fc.get("slide_skip_inner", 0))
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
    body = V[V[:, 2] > 0.0]
    for name, pc in plain.items():
        f, key = sheet["facades"][name], pc["normal"]
        if key not in VIEW or any(fc["normal"] == key for fc in spec["facades"].values()):
            raise SystemExit(f"facades_plain {name}: normal {key!r} must be a view without a rib facade")
        axis = 1 if key in ("+x", "-x") else 0
        lo, hi = body[:, axis].min(), body[:, axis].max()
        ground = min(p["bbox_mm"][1] for p in f["plinth"]) / 1000
        panels = [(f"Слайд {pres['slide']} презентации", panel_slide(slide, boxes[name], f, pxm))]
        for tag in ("vpm", "npm"):
            view = meta[tag]["views"][VIEW[key]]
            panels.append((f"{tag.upper()} рендер", panel_render(os.path.join(rdir, view["png"]), view, key, lo, hi,
                                                                 pxm, ground)))
        gap, lab = 24, 70
        sheet_img = Image.new("RGB", (sum(p.width for _, p in panels) + gap * (len(panels) + 1),
                                      max(p.height for _, p in panels) + lab + 50), (255, 255, 255))
        d = ImageDraw.Draw(sheet_img)
        d.text((gap, 10), f"Фасад {name}: слайд и рендеры в одном масштабе {pxm:.0f} px/м, ±0.000 на одной высоте",
               fill=(0, 0, 0), font=font(22))
        x = gap
        for title, p in panels:
            sheet_img.paste(p, (x, 45))
            d.text((x, 45 + p.height + 6), title, fill=(0, 0, 0), font=font(18))
            d.text((x, 45 + p.height + 30), pc["label"], fill=(0, 0, 0), font=font(16))
            x += p.width + gap
        png = os.path.join(out, f"compare_{VIEW[key]}_{name}.png")
        sheet_img.save(png, optimize=True)
        report["facades"][name] = {"plain": True, "why": pc.get("why"), "label": pc["label"], "ground_m": ground,
                                   "slide_box_px": [int(v) for v in boxes[name]], "png": os.path.basename(png)}
        print("COMPARE", name, "plain:", pc["label"])
    with open(os.path.join(out, "compare.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    return 0 if all(c["match"] for c in report["facades"].values() if not c.get("plain")) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
