"""#125 OBSERVE: NPM vs VPM render-diff on TEC26 AC08 FLAT facade renders (contract: ../autoresearch-npm-vpm-render-diff.md).

Reads the hash-checked `renders/{npm,vpm}_<view>.png` + `renders.json` of each fixture folder, resamples both renders
to a common 100 px/m, and scores CIE76 Delta E per 1 m x 1 m facade cell. Writes one JSON (refuses to overwrite).
No DCC, no writes outside --out. Synthetic perturbations (P1-P3, N0) are applied to in-memory copies only.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

FIXTURE = {
    "559-tec26-oks-ac08-pilot": "unlabeled",
    "559-tec26-oks-ac08-pilot-v006": "unlabeled",
    "559-tec26-oks-ac08-pilot-v007": "rejected",
    "559-tec26-oks-ac08-pilot-v009": "unlabeled",
    "559-tec26-oks-ac08-pilot-v010": "accepted",
}
VIEWS = ("south", "east", "north", "west")
AXIS = {"south": 0, "north": 0, "east": 1, "west": 1}  # bbox axis along the view's right vector
TARGET_PXM = 100.0
CELL = 100  # px at TARGET_PXM = 1 m
MIN_CELL_COVER = 0.25


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_sums(folder):
    sums = {}
    for line in (folder / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            sums[name.lstrip("*").removeprefix("./")] = digest.lower()
    return sums


def preflight(folder):
    sums = read_sums(folder)
    manifest = {}
    names = ["renders/renders.json"] + [f"renders/{k}_{v}.png" for k in ("npm", "vpm") for v in VIEWS]
    for name in names:
        got = sha256(folder / name)
        if sums.get(name) != got:
            raise SystemExit(f"hash mismatch {folder.name}/{name}: sums={sums.get(name)} file={got}")
        manifest[name] = got
    return manifest


def srgb_to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8).copy()


def resample(rgba, box, scale):
    x0, y0, x1, y1 = box
    im = Image.fromarray(rgba[y0:y1, x0:x1]).convert("RGBa")  # premultiplied: no background bleed
    size = (max(1, round((x1 - x0) * scale)), max(1, round((y1 - y0) * scale)))
    return np.asarray(im.resize(size, Image.Resampling.BOX).convert("RGBA"), dtype=np.float64)


def is_zero_line(rgba):
    # render_facades.zero_line: FLAT pure red (1, 0, 0) loop at Z=0, 0.3 m outside the bbox on every side
    return (rgba[..., 0] >= 200) & (rgba[..., 1] <= 60) & (rgba[..., 2] <= 60)


def score_view(npm, vpm, width_m, variant=1):
    a_n, a_v = npm[..., 3] >= 128, vpm[..., 3] >= 128
    if variant >= 2:  # V2: the red +-0.000 marker is not facade (it widened the V1 px/m estimate)
        a_n, a_v = a_n & ~is_zero_line(npm), a_v & ~is_zero_line(vpm)
        npm, vpm = npm.copy(), vpm.copy()
        npm[..., 3][~a_n], vpm[..., 3][~a_v] = 0, 0
    both, xor = a_n & a_v, a_n ^ a_v
    cols = np.where(both.any(0))[0]
    rows = np.where(both.any(1))[0]
    box = (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)
    pxm = (box[2] - box[0]) / width_m
    scale = TARGET_PXM / pxm
    n, v = resample(npm, box, scale), resample(vpm, box, scale)
    mask = (n[..., 3] >= 127.5) & (v[..., 3] >= 127.5)
    de = np.linalg.norm(srgb_to_lab(n[..., :3]) - srgb_to_lab(v[..., :3]), axis=-1)
    h, w = mask.shape
    cells = []
    for top in range(h, 0, -CELL):  # rows from the bottom (lower-left origin)
        r0 = max(0, top - CELL)
        for c0 in range(0, w, CELL):
            m = mask[r0:top, c0:c0 + CELL]
            if m.size and m.mean() >= MIN_CELL_COVER:
                cells.append({"x_m": c0 / TARGET_PXM, "z_m": (h - top) / TARGET_PXM,
                              "mean": float(de[r0:top, c0:c0 + CELL][m].mean())})
    means = np.array([c["mean"] for c in cells])
    worst = max(cells, key=lambda c: c["mean"])
    return {
        "native_px_per_m": round(pxm, 3), "pixels": int(mask.sum()),
        "silhouette_xor_share": round(float(xor.sum() / max(1, (a_n | a_v).sum())), 6),
        "pixel_mean": round(float(de[mask].mean()), 4), "pixel_p95": round(float(np.percentile(de[mask], 95)), 4),
        "cells": len(cells), "cell_p95": round(float(np.percentile(means, 95)), 4),
        "worst_cell": {k: round(val, 4) for k, val in worst.items()},
    }


def score_package(images, bbox, variant=1):
    views = {}
    for view in VIEWS:
        width = bbox[1][AXIS[view]] - bbox[0][AXIS[view]]
        views[view] = score_view(images["npm", view], images["vpm", view], width, variant)
    return {"score_facade_cell_p95": max(v["cell_p95"] for v in views.values()), "views": views}


def perturb(images, kind, pxm):
    img = {k: a.copy() for k, a in images.items()}
    if kind == "N0":
        for view in VIEWS:
            img["npm", view] = img["vpm", view].copy()
        return img
    n = img["npm", "south"]
    alpha = n[..., 3] >= 128
    rows, cols = np.where(alpha)
    cy, cx = int(rows.mean()), int(cols.mean())
    if kind == "P1":
        half = int(pxm)  # 2 m x 2 m patch
        sl = (slice(cy - half, cy + half), slice(cx - half, cx + half))
        patch = n[sl]
        m = patch[..., 3] >= 128
        patch[..., 0][m] = np.clip(patch[..., 0][m].astype(int) + 40, 0, 255)
    elif kind == "P2":
        step, x = int(round(pxm)), int(cols.min())
        while x < cols.max():
            band = n[:, x:x + 3]
            band[..., :3][band[..., 3] >= 128] = 40
            x += step
    elif kind == "P3":
        rolled = np.roll(n, int(round(0.25 * pxm)), axis=1)
        take = alpha & (rolled[..., 3] >= 128)
        n[..., :3][take] = rolled[..., :3][take]
    return img


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--variant", type=int, choices=(1, 2), default=1)
    args = ap.parse_args(argv)
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    report = {"harness_sha256": sha256(__file__), "variant": args.variant, "target_px_per_m": TARGET_PXM, "cell_m": CELL / TARGET_PXM,
              "packages": {}, "witnesses": {}}
    for name, label in FIXTURE.items():
        folder = args.root / name
        manifest = preflight(folder)
        meta = json.loads((folder / "renders/renders.json").read_text(encoding="utf-8"))
        images = {(k, v): load(folder / f"renders/{k}_{v}.png") for k in ("npm", "vpm") for v in VIEWS}
        res = score_package(images, meta["vpm"]["bbox"], args.variant)
        recorded = {v: meta["vpm"].get("views", {}).get(v, {}).get("px_per_m") for v in VIEWS}
        report["packages"][name] = {"label": label, "inputs_sha256": manifest, "recorded_px_per_m": recorded, **res}
        if label == "accepted":
            pxm = res["views"]["south"]["native_px_per_m"]
            for kind in ("N0", "P1", "P2", "P3"):
                report["witnesses"][kind] = {"synthetic": True, "base": name,
                                             **score_package(perturb(images, kind, pxm), meta["vpm"]["bbox"], args.variant)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    for name, p in report["packages"].items():
        print(f"{name[-12:]:>12} {p['label']:>9} score={p['score_facade_cell_p95']:.3f} "
              + " ".join(f"{v}:{p['views'][v]['cell_p95']:.2f}/{p['views'][v]['native_px_per_m']:.0f}" for v in VIEWS))
    for kind, w in report["witnesses"].items():
        print(f"witness {kind} score={w['score_facade_cell_p95']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
