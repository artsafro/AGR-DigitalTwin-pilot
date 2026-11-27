"""Standing #129 (OBSERVE): transparent-RGB contamination (TRC) of an atlas with an opacity map.

Research harness, not a production check. Measures how much the RGB stored under opacity 0 leaks into the
visible colour once the atlas is mip-mapped without premultiplication (box 2x2 per level, as a GPU mip chain):

    for k in 1..4, f = 2**k, per f x f block:
        straight = mean(RGB)                       # what an un-premultiplied mip shows
        weighted = sum(RGB * a) / sum(a)           # the colour of the visible texels only
        cov      = mean(a)
    d_k = Y(straight) - Y(weighted)                # Y = 0.2126 R + 0.7152 G + 0.0722 B, 0..255 sRGB units
    cell score = max_k p95(|d_k|) over blocks whose centre lies in the cell and cov >= 0.5
    atlas score = max over cells

Positive d = paler/brighter than the plant (the #1146 v003 'pale crossing plane' class).

CLI:
    python score.py --atlas <dir with T_*_Diffuse.png, T_*_Opacity.png, atlas-check.json> [--perturb N0|P1|P2|P3]
                    [--out result.json]
Perturbations are synthetic, in memory only; inputs are never written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

LEVELS = (1, 2, 3, 4)
COV_MIN = 0.5
FAR_BLOCK = 16  # P3: opacity==0 texels inside an aligned 16x16 block with no opacity>0 at all


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(atlas_dir: Path):
    diff = next(atlas_dir.glob("T_*_Diffuse.png"))
    opac = next(atlas_dir.glob("T_*_Opacity.png"))
    check = atlas_dir / "atlas-check.json"
    hashes = {p.name: sha256(p) for p in (diff, opac, check)}
    rgb = np.asarray(Image.open(diff).convert("RGB"), dtype=np.float64)
    a = np.asarray(Image.open(opac).convert("L"), dtype=np.float64) / 255.0
    cells = json.loads(check.read_text(encoding="utf-8"))["cells"]
    if rgb.shape[:2] != a.shape or rgb.shape[0] != rgb.shape[1]:
        raise ValueError("diffuse/opacity must be the same square size")
    return rgb, a, cells, hashes


def perturb(rgb, a, kind):
    out = rgb.copy()
    zero = a == 0
    if kind == "N0":
        pass
    elif kind == "P1":
        out[zero] = 252.0
    elif kind == "P2":
        out[zero] = 0.0
    elif kind == "P3":
        n = a.shape[0] // FAR_BLOCK
        blk = a.reshape(n, FAR_BLOCK, n, FAR_BLOCK).max(axis=(1, 3)) == 0
        far = np.repeat(np.repeat(blk, FAR_BLOCK, 0), FAR_BLOCK, 1) & zero
        out[far] = 252.0
    else:
        raise ValueError(kind)
    changed = int((np.abs(out - rgb).sum(axis=2) > 0).sum())
    return out, changed


def luminance(x):
    return 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]


def block_mean(x, f):
    n = x.shape[0] // f
    shp = (n, f, n, f) + x.shape[2:]
    return x.reshape(shp).mean(axis=(1, 3))


def score(rgb, a, cells):
    size = a.shape[0]
    per_cell = {c: {"max_p95": 0.0, "signed_mean": None, "blocks": 0, "levels": {}} for c in cells}
    for k in LEVELS:
        f = 2 ** k
        n = size // f
        straight = block_mean(rgb, f)
        sa = block_mean(a, f)
        sw = block_mean(rgb * a[..., None], f)
        with np.errstate(invalid="ignore", divide="ignore"):
            weighted = sw / sa[..., None]
        d = luminance(straight) - luminance(weighted)
        centre = (np.arange(n) + 0.5) / n  # block centre in [0,1]; row 0 = top = v 1
        uu, vv = np.meshgrid(centre, 1.0 - centre)
        for c, (u0, v0, u1, v1) in cells.items():
            m = (uu >= u0) & (uu < u1) & (vv >= v0) & (vv < v1) & (sa >= COV_MIN)
            vals = d[m]
            row = per_cell[c]
            if vals.size == 0:
                row["levels"][k] = None
                continue
            p95 = float(np.percentile(np.abs(vals), 95))
            row["levels"][k] = {"p95_abs": round(p95, 4), "mean": round(float(vals.mean()), 4), "n": int(vals.size)}
            row["blocks"] += int(vals.size)
            if p95 >= row["max_p95"]:
                row["max_p95"] = p95
                row["signed_mean"] = float(vals.mean())
    for row in per_cell.values():
        row["max_p95"] = round(row["max_p95"], 4)
        row["signed_mean"] = None if row["signed_mean"] is None else round(row["signed_mean"], 4)
    worst = max(per_cell, key=lambda c: per_cell[c]["max_p95"])
    return {"atlas_score": per_cell[worst]["max_p95"], "worst_cell": worst, "cells": per_cell}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument("--perturb", default=None, choices=["N0", "P1", "P2", "P3"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    rgb, a, cells, hashes = load(args.atlas)
    changed = None
    if args.perturb:
        rgb, changed = perturb(rgb, a, args.perturb)
    res = {"atlas": str(args.atlas), "inputs_sha256": hashes, "perturb": args.perturb,
           "changed_rgb_pixels": changed, "size": a.shape[0], "cov_min": COV_MIN, "levels": list(LEVELS)}
    res.update(score(rgb, a, cells))
    text = json.dumps(res, indent=1, sort_keys=True)
    if args.out:
        if args.out.resolve().parent == args.atlas.resolve():
            raise ValueError("--out must not be inside the input atlas dir")
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("atlas", "perturb", "changed_rgb_pixels", "atlas_score", "worst_cell")}))


if __name__ == "__main__":
    main()
