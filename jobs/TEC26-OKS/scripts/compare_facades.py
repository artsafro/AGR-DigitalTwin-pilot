"""new-case: AC08 acceptance sheets - each facade render NEXT TO the matching colour-solution facade AT THE SAME SCALE,
with the rib count measured on every image written below it (Artem 2026-10-22 rework, PR #574).

Usage: uv run python compare_facades.py <spec.json> <sheet-facades.json> <renders_dir> <vpm.readback.json>
                                        <new_out_dir> [--px-per-m 200]
Per facade one PNG `compare_<facade>.png` with four panels, all resampled to the same px/m and aligned on ±0.000:
  1. Artem's reference JPG (the sheet as he sent it), cropped to that facade (its scale from the drawn body width);
  2. the DWG facade redrawn 1:1 from the colour-solution entities (sheet-facades.json: field, frame bands, joint
     lines, door, plinth; the drawing in mm);
  3. the VPM render and 4. the NPM render of the delivered readback FBX (render_facades.py, camera in renders.json).
Counts: sheet = joint lines in sheet-facades.json (and dark lines measured on the JPG row), renders = joints measured
on the rendered pixels (joint_count.render_row + count_joints) - never the spec value. Writes compare.json with every
count; a facade whose rendered VPM or NPM count differs from the sheet is marked MISMATCH in the image and the JSON.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_count  # noqa: E402

VIEW = {"+y": "north", "-y": "south", "+x": "east", "-x": "west"}
FONT = "C:/Windows/Fonts/arial.ttf"
Z_TOP, Z_BOT = 2.85, -0.45          # metres shown above / below ±0.000 in every panel


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except OSError:
        return ImageFont.load_default()


def jpg_facades(path):
    """Bounding boxes (x0, y0, x1, y1 px) of the four blue facades of the JPG, in sheet reading order."""
    im = np.asarray(Image.open(path).convert("RGB")).astype(int)
    blue = (im[..., 2] > 130) & (im[..., 0] < 60)
    H, W = blue.shape
    boxes = []
    for r0, r1 in ((0, H // 2), (H // 2, H)):
        for c0, c1 in ((0, W // 2), (W // 2, W)):
            ys, xs = np.where(blue[r0:r1, c0:c1])
            boxes.append((c0 + xs.min(), r0 + ys.min(), c0 + xs.max() + 1, r0 + ys.max() + 1))
    return im.astype(np.uint8), boxes


def jpg_joint_count(im, box, f):
    """Joint lines visible on the JPG row at 95 % field height (above the door). At ~47 px/m the last line (38-58 mm
    before the field edge) can merge with the frame-edge line, so lines are CONFIRMED against the DWG positions:
    confirmed = DWG joint lines with a dark JPG run within 2.5 px; extra = dark runs explained neither by a DWG line
    nor by a field edge. Returns (confirmed, extra)."""
    x0, y0, x1, y1 = box
    pxmm = (x1 - x0) / f["size_mm"][0]
    fx0, fy0, fx1, fy1 = f["field_mm"]
    y = int(round(y1 - (fy0 + 0.95 * (fy1 - fy0)) * pxmm))
    row = im[y, x0:x1].astype(float).sum(-1)
    dark = row < 0.75 * np.median(row)
    cen = [((a + b - 1) / 2 + 0.5) / pxmm for a, b in joint_count.runs(dark)]   # run centres, mm from the body edge
    tol = 2.5 / pxmm                                  # 2.5 px = 53 mm < P / 2: the merged last line still counts
    lines = f["joint_lines_mm"]
    confirmed = sum(1 for x in lines if any(abs(c - x) <= tol for c in cen))
    extra = sum(1 for c in cen if fx0 - tol < c < fx1 + tol and not any(abs(c - x) <= tol for x in lines)
                and abs(c - fx0) > tol and abs(c - fx1) > tol)
    return confirmed, extra


def panel_jpg(im, box, f, pxm):
    x0, y0, x1, y1 = box
    pxmm = (x1 - x0) / f["size_mm"][0]
    zero_y = y1                                        # bottom of the drawn body = ±0.000
    top = zero_y - Z_TOP * 1000 * pxmm
    bot = zero_y - Z_BOT * 1000 * pxmm
    pad = 0.3 * 1000 * pxmm
    crop = Image.fromarray(im).crop((int(x0 - pad), int(top), int(x1 + pad), int(bot)))
    w = int(round((f["size_mm"][0] / 1000 + 0.6) * pxm))
    return crop.resize((w, int(round((Z_TOP - Z_BOT) * pxm))), Image.LANCZOS)


def panel_dwg(f, pxm):
    """Redraw of the colour-solution facade from its DXF entities (sheet-facades.json), mm -> px at pxm."""
    W_mm, H_mm = f["size_mm"]
    w = int(round((W_mm / 1000 + 0.6) * pxm))
    h = int(round((Z_TOP - Z_BOT) * pxm))
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    X = lambda mm: (mm / 1000 + 0.3) * pxm  # noqa: E731
    Y = lambda mm: (Z_TOP - mm / 1000) * pxm  # noqa: E731
    for p in f["plinth"]:
        bx = p["bbox_mm"]
        d.rectangle([X(bx[0]), Y(min(bx[3], 0.0)), X(bx[2]), Y(bx[1])], fill=tuple(p["rgb"]))
    d.rectangle([X(0), Y(H_mm), X(W_mm), Y(0)], fill=tuple(f["panel_rgb"]), outline=(0, 0, 0), width=2)
    fx0, fy0, fx1, fy1 = f["field_mm"]
    d.rectangle([X(fx0), Y(fy1), X(fx1), Y(fy0)], outline=(0, 50, 80), width=2)
    door = f.get("door_mm")
    for x in f["joint_lines_mm"]:
        if door and door[0] < x < door[2]:
            d.line([X(x), Y(door[3]), X(x), Y(fy1)], fill=(0, 50, 80), width=2)
        else:
            d.line([X(x), Y(fy0), X(x), Y(fy1)], fill=(0, 50, 80), width=2)
    if door:
        d.rectangle([X(door[0]), Y(door[3]), X(door[2]), Y(door[1])], fill=(155, 155, 155), outline=(0, 0, 0), width=2)
    d.line([0, Y(0), w, Y(0)], fill=(255, 0, 0), width=1)
    return img


def panel_render(png, view, key, lo, hi, pxm):
    """Crop the render to the facade body +-0.3 m, Z_BOT..Z_TOP, resampled to pxm (the render's own px/m is fixed)."""
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
    return crop.resize((w, int(round((Z_TOP - Z_BOT) * pxm))), Image.LANCZOS)


def main(argv):
    spec_p, sheet_p, rdir, vrb_p, out = argv[:5]
    pxm = float(argv[argv.index("--px-per-m") + 1]) if "--px-per-m" in argv else 200.0
    if os.path.lexists(out):
        raise SystemExit(f"refusing to overwrite {out}")
    spec, sheet = json.load(open(spec_p, encoding="utf-8")), json.load(open(sheet_p, encoding="utf-8"))
    meta = json.load(open(os.path.join(rdir, "renders.json"), encoding="utf-8"))
    vrb = json.load(open(vrb_p, encoding="utf-8"))
    vmain = next(o for o in vrb["objects"] if not o["name"].startswith("UCX_"))
    V = np.asarray(vmain["vertices"], float)
    uvs = [np.asarray(u, float) for u in vmain["face_uvs"]]
    jpg, boxes = jpg_facades(spec["sheet"]["artem_reference"])
    order = list(sheet["facades"])                     # sheet reading order = JPG quadrant order
    os.makedirs(out)
    report = {"px_per_m": pxm, "facades": {}}
    for name, fc in spec["facades"].items():
        f = sheet["facades"][name]
        key = fc["normal"]
        ud = spec["finishes"][fc["finish"]]["udim"]
        keep = lambda t, ud=ud: int(1001 + np.floor(uvs[t].mean(0)[0]) + 10 * np.floor(uvs[t].mean(0)[1])) == ud  # noqa
        tris = joint_count.facade_triangles(V, vmain["faces"], keep, key)
        lo, hi, zlo, zhi = joint_count.field_extent(V, vmain["faces"], tris, key)
        # the body outline (frame outer faces) for the crop: field +- the sheet's frame posts
        blo, bhi = lo - f["frame_bands_mm"]["left"] / 1000, hi + f["frame_bands_mm"]["right"] / 1000
        counts = {"sheet_dwg_joints": f["joints"], "sheet_dwg_ribs": f["ribs"],
                  }
        counts["sheet_jpg_joints_confirmed"], counts["sheet_jpg_extra_runs"] = jpg_joint_count(jpg, boxes[order.index(name)], f)
        panels = [("Лист (JPG Артёма)", panel_jpg(jpg, boxes[order.index(name)], f, pxm), counts["sheet_jpg_joints_confirmed"]),
                  ("Лист (DWG, 1:1)", panel_dwg(f, pxm), f["joints"])]
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
                                                                 pxm), top["joints_found"]))
        ok = all(c == f["joints"] for c in (counts["vpm_render_joints"], counts["npm_render_joints"],
                                            counts["sheet_jpg_joints_confirmed"])) and counts["sheet_jpg_extra_runs"] == 0
        counts["match"] = bool(ok and all(r["ok"] for t in ("vpm", "npm") for r in counts[f"{t}_render_rows"].values()))
        gap, lab = 24, 70
        Wt = sum(p.width for _, p, _ in panels) + gap * (len(panels) + 1)
        Ht = max(p.height for _, p, _ in panels) + lab + 50
        sheet_img = Image.new("RGB", (Wt, Ht), (255, 255, 255))
        d = ImageDraw.Draw(sheet_img)
        d.text((gap, 10), f"Фасад {name}: лист и рендер в одном масштабе {pxm:.0f} px/м, ±0.000 на одной высоте"
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
