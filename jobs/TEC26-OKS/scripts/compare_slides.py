"""new-case: TEC26 acceptance picture per facade - the presentation slide facade («Схема фасадов ... Цветовое решение»,
the colour authority, Artem 2026-10-22) NEXT TO the VPM and NPM renders at the SAME scale, ±0.000 aligned, with the
rib (joint) count measured on every image written under it.

Usage: uv run python compare_slides.py <spec.json> <renders_dir> <vpm.readback.json> <new_out_dir> [--px-per-m 100]
spec `presentation`: slide image per facade (sha256 checked); `facades`: normal, ribs. The slide facade is located in
its half of the slide (top = first facade listed for that slide, bottom = second) by the light-grey wall (RGB 208):
wall columns -> horizontal scale (wall width = the model wall field), grey-band bottom/top rows -> +0.120 / +2.500.
Counts: dark runs (< 0.85 x the local panel median) inside the wall on two rows - grey z = 0.30 m, blue z = 3.00 m
(+ roof z = 3.65 m on the eave-side facades) -
never the spec value. A facade whose VPM or NPM count differs from the slide on a row is marked MISMATCH.
"""
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_count  # noqa: E402

VIEW = {"+y": "north", "-y": "south", "+x": "east", "-x": "west"}
ROWS = {"grey": 0.30, "blue": 3.00}
ROOF_Z = 3.65  # the roof slope seen from the eave side (А-Д / Д-А): ribs down the slope (slide 44)
Z_TOP, Z_BOT = 4.2, -0.5
GREY, BLUE = np.array([208, 208, 208]), np.array([0, 124, 176])


def font(sz):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", sz)
    except OSError:
        return ImageFont.load_default()


def slide_wall(im, half):
    """(x0, x1, y_bottom_grey, y_top_grey) px of the light-grey wall in the slide half (0 top, 1 bottom)."""
    H = im.shape[0]
    ys = slice(0, H // 2) if half == 0 else slice(H // 2, H)
    sub = im[ys].astype(int)
    grey = (np.abs(sub - GREY).max(-1) <= 2)
    cols = np.where(grey.sum(0) >= 0.25 * grey.sum(0).max())[0]
    rows = np.where(grey.sum(1) >= 0.25 * grey.sum(1).max())[0]
    if not len(cols) or not len(rows):
        raise ValueError(f"no light-grey wall in slide half {half}")
    off = 0 if half == 0 else H // 2
    return int(cols.min()), int(cols.max()) + 1, int(rows.max()) + 1 + off, int(rows.min()) + off


def slide_row_count(im, x0, x1, y, ribs, colour):
    row = im[y, x0:x1].astype(float)
    ref = GREY if colour == "grey" else BLUE
    near = np.abs(row - ref).max(-1) <= 60
    dark = row.sum(-1) < 0.85 * np.median(row[near].sum(-1)) if near.any() else np.zeros(len(row), bool)
    s = np.arange(x1 - x0) + 0.5
    lum = np.where(dark | near, row.sum(-1), np.nan)
    return joint_count.count_joints(s, lum, 0.0, float(x1 - x0), ribs, tol=0.35 * (x1 - x0) / ribs, dark=0.85)


def crop_render(png, view, key, lo, hi, pxm):
    rgba = Image.open(png).convert("RGBA")
    img = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    img.alpha_composite(rgba)
    c, r = np.asarray(view["center"]), np.asarray(view["right"])
    W, H = view["res"]
    scale = view["ortho_scale"] / W
    axis = 1 if key in ("+x", "-x") else 0
    px = lambda s: W / 2 + (s - c[axis]) * r[axis] / scale  # noqa: E731
    py = lambda z: H / 2 - (z - c[2]) / scale  # noqa: E731
    xa, xb = sorted((px(lo - 0.8), px(hi + 0.8)))
    box = (int(round(xa)), int(round(py(Z_TOP))), int(round(xb)), int(round(py(Z_BOT))))
    out = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (255, 255, 255))
    out.paste(img.convert("RGB").crop((max(box[0], 0), max(box[1], 0), min(box[2], W), min(box[3], H))),
              (max(-box[0], 0), max(-box[1], 0)))
    return out.resize((int(round((hi - lo + 1.6) * pxm)), int(round((Z_TOP - Z_BOT) * pxm))), Image.LANCZOS)


def crop_slide(im, wall, field_m, z_lo, pxm):
    x0, x1, yb, yt = wall
    sx = (x1 - x0) / field_m                       # slide px per metre (horizontal, from the wall width)
    sz = sx                                        # a drawing has ONE scale; the grey-band top is unreliable
    # (gable/canopy/label pixels of the same grey), so only its bottom row (+z_lo) anchors the height
    y0 = yb + z_lo * sz                            # slide row of ±0.000
    box = (int(round(x0 - 0.8 * sx)), int(round(y0 - Z_TOP * sz)), int(round(x1 + 0.8 * sx)),
           int(round(y0 - Z_BOT * sz)))
    c = Image.fromarray(im).crop(box)
    return c.resize((int(round((field_m + 1.6) * pxm)), int(round((Z_TOP - Z_BOT) * pxm))), Image.LANCZOS), sx, sz, y0


def main(argv):
    spec_p, rdir, vrb_p, out = argv[:4]
    pxm = float(argv[argv.index("--px-per-m") + 1]) if "--px-per-m" in argv else 100.0
    if os.path.lexists(out):
        raise SystemExit(f"refusing to overwrite {out}")
    spec = json.load(open(spec_p, encoding="utf-8"))
    pres = spec["presentation"]
    meta = json.load(open(os.path.join(rdir, "renders.json"), encoding="utf-8"))
    vmain = next(o for o in json.load(open(vrb_p, encoding="utf-8"))["objects"] if o["name"].endswith("_Main"))
    V = np.asarray(vmain["vertices"], float)
    uvs = [np.asarray(u, float) for u in vmain["face_uvs"]]
    imgs = {}
    for k, d in pres["images"].items():
        raw = open(d["path"], "rb").read()
        if hashlib.sha256(raw).hexdigest() != d["sha256"]:
            raise SystemExit(f"slide {k}: sha256 mismatch")
        imgs[k] = np.asarray(Image.open(d["path"]).convert("RGB"))
    os.makedirs(out)
    seen = {}
    report = {"px_per_m": pxm, "rows_z_m": ROWS, "facades": {}}
    for name, fc in spec["facades"].items():
        sl = str(pres["slides"][name])
        half = seen.get(sl, 0)
        seen[sl] = half + 1
        key, ribs = fc["normal"], fc["ribs"]
        ud = spec["finishes"][fc["finish"]]["udim"]
        keep = lambda t, ud=ud: int(1001 + np.floor(uvs[t].mean(0)[0]) + 10 * np.floor(uvs[t].mean(0)[1])) == ud  # noqa
        tris = joint_count.facade_triangles(V, vmain["faces"], keep, key)
        lo, hi, zlo, _ = joint_count.field_extent(V, vmain["faces"], tris, key)
        wall = slide_wall(imgs[sl], half)
        sc, sx, sz, y0 = crop_slide(imgs[sl], wall, hi - lo, zlo, pxm)
        counts = {"slide": sl, "slide_half": ["top", "bottom"][half], "slide_wall_px": list(wall),
                  "slide_px_per_m": [round(sx, 2), round(sz, 2)], "ribs_expected": ribs, "rows": {}}
        under = {"slide": [], "vpm": [], "npm": []}
        ok = True
        rows = list(ROWS.items()) + ([("roof", ROOF_Z)] if key in ("+x", "-x") else [])  # eave side: roof ribs
        for colour, z in rows:
            rs = slide_row_count(imgs[sl], wall[0], wall[1], int(round(y0 - z * sz)), ribs, colour)
            row = {"slide": {k: rs[k] for k in ("joints_found", "hidden_by_other_finish", "missing", "extra")
                             if k in rs}}
            for tag in ("vpm", "npm"):
                view = meta[tag]["views"][VIEW[key]]
                img = np.asarray(Image.open(os.path.join(rdir, view["png"])).convert("RGB"))
                s, lum = joint_count.render_row(img, view, 1 if key in ("+x", "-x") else 0, z, lo, hi, mask="grey" if colour == "grey" else "blue")
                r = joint_count.count_joints(s, lum, lo, hi, ribs, tol=0.01, dark=0.85)
                row[tag] = {k: r[k] for k in ("ok", "joints_found", "missing", "extra") if k in r}
                row[tag]["hidden"] = len(r.get("hidden_by_other_finish", []))
                ok &= bool(r.get("ok"))
            for tag in under:
                h = row[tag].get("hidden", len(row[tag].get("hidden_by_other_finish", [])))
                under[tag].append(f"{colour} z={z:.2f}: {row[tag].get('joints_found')} швов (+{h} скрыто)")
            row["slide"]["hidden"] = len(rs.get("hidden_by_other_finish", []))
            counts["rows"][f"{colour}_z={z:.2f}"] = row
        counts["match"] = bool(ok)
        report["facades"][name] = counts
        panels = [(f"Слайд {sl} презентации", sc, under["slide"])]
        for tag in ("vpm", "npm"):
            view = meta[tag]["views"][VIEW[key]]
            panels.append((f"{tag.upper()} рендер", crop_render(os.path.join(rdir, view["png"]), view, key, lo, hi,
                                                                 pxm), under[tag]))
        gap, lab = 24, 110
        Wt = sum(p.width for _, p, _ in panels) + gap * (len(panels) + 1)
        Ht = max(p.height for _, p, _ in panels) + lab + 50
        im = Image.new("RGB", (Wt, Ht), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.text((gap, 10), f"Фасад {name}: слайд и рендеры в одном масштабе {pxm:.0f} px/м, ±0.000 на одной высоте; "
                          f"по чертежу {ribs} рёбер = {ribs - 1} швов" + ("" if ok else "   MISMATCH"),
               fill=(0, 0, 0) if ok else (200, 0, 0), font=font(20))
        x = gap
        for title, p, lines in panels:
            d.text((x, 40), title, fill=(0, 0, 0), font=font(18))
            im.paste(p, (x, 70))
            yz = 70 + int(round(Z_TOP * pxm))
            d.line([(x, yz), (x + p.width, yz)], fill=(220, 0, 220), width=1)
            for i, t in enumerate(lines):
                d.text((x, 76 + p.height + 22 * i), t, fill=(0, 0, 0), font=font(16))
            x += p.width + gap
        fn = os.path.join(out, f"compare_{VIEW[key]}_{name}.png")
        im.save(fn)
        print("COMPARE", name, "match" if ok else "MISMATCH", json.dumps(
            {k: {t: v[t].get("joints_found") for t in v} for k, v in counts["rows"].items()}, ensure_ascii=False))
    json.dump(report, open(os.path.join(out, "compare.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0 if all(f["match"] for f in report["facades"].values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
