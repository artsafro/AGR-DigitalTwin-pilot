"""Standing #133 (OBSERVE): why the accepted Vatutino Flora v004 NPM atlas keeps a mip-level residual.

Research harness, not a production check. Frozen contract: docs/research/autoresearch-flora-bleed-residual.md.

Chain per variant (in a NEW scratch run dir, Drive inputs are read-only):
    run-v003/maps (cropped, unbled, rejected run)  --bleed variant-->  <out>/<round>/<variant>/maps
    --> flora_route_a._atlas(run, "npm")  (production atlas builder, 2048)  --> score.py (#129 metric, unchanged)
Variants (frozen): B = production flora_route_a.bleed_rgb; C1 = same push-pull, seeds = plant mask eroded by
ERODE_PX (interior colour only); plant pixels (opacity >= 128) are never changed by either.
Usage:  uv run --frozen python docs/research/autoresearch-flora-bleed-residual-harness/run.py <new out dir>
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EV = Path("G:/Мой диск/AGR-evidence/1146-flora-star")
RUNS = ("run-v003", "run-v004")
SUBTREES = ("./maps/", "./atlas/")
ROUNDS = 3
ERODE_PX = 2          # C1: seeds = mask eroded by 2 px (MinFilter 5x5) at map resolution
EDGE_PX = 2           # diagnostic ring width (plant pixels within 2 px of a transparent pixel)
SCORE_BLOB = "91367d5d6d8912ccd8ff21e1638e889e509b5120"   # git blob of #129 score.py (copied unchanged)


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = load_mod("score129", HERE / "score.py")
JOB = load_mod("flora_route_a", ROOT / "jobs/VATUTINO-SITE/flora_route_a.py")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_blob(p):
    data = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def manifest_check():
    """Full-manifest preflight: every ./maps/ and ./atlas/ row of each run's SHA256SUMS.txt must match."""
    rows, bad = 0, []
    for run in RUNS:
        for line in (EV / run / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            h, _, name = line.partition(" *")
            if not name.startswith(SUBTREES):
                continue
            rows += 1
            if sha(EV / run / name[2:]) != h:
                bad.append(f"{run}/{name}")
    if bad or rows == 0:
        raise SystemExit(f"manifest mismatch ({rows} rows): {bad[:5]}")
    return rows


def eroded_bleed(rgb, opacity, erode=ERODE_PX):
    """C1: production push-pull fill, but seeded from the plant interior only; plant pixels unchanged."""
    mask = np.asarray(opacity) >= 128
    img = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), "L").filter(ImageFilter.MinFilter(2 * erode + 1))
    seeds = np.asarray(img) == 255
    fallback = not seeds.any()
    if fallback:
        seeds = mask
    filled = JOB.bleed_rgb(rgb, np.where(seeds, 255, 0).astype(np.uint8))  # fills everything outside the seeds
    return np.where(mask[..., None], rgb, filled).astype(np.uint8), fallback


VARIANTS = {"B": lambda rgb, op: (JOB.bleed_rgb(rgb, op), False), "C1": eroded_bleed}


def luma(x):
    return 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]


def diagnostic(rgb, op):
    """Plant edge ring vs plant interior luma (map resolution), signed; observe only."""
    mask = op >= 128
    near = np.asarray(Image.fromarray(np.where(mask, 0, 255).astype(np.uint8), "L")
                      .filter(ImageFilter.MaxFilter(2 * EDGE_PX + 1))) == 255
    ring, inner = mask & near, mask & ~near
    y = luma(rgb.astype(np.float64))
    return {"ring_px": int(ring.sum()), "inner_px": int(inner.sum()),
            "ring_luma": round(float(y[ring].mean()), 3) if ring.any() else None,
            "inner_luma": round(float(y[inner].mean()), 3) if inner.any() else None,
            "partial_opacity_px": int(((op > 0) & (op < 255)).sum())}


def build(variant, maps_rows, run_dir):
    maps_dir = run_dir / "maps"
    maps_dir.mkdir(parents=True)
    rows, per = [], {}
    for r in maps_rows:
        src = EV / "run-v003" / "maps" / r["key"]
        rgb = np.asarray(Image.open(src / "diffuse.png").convert("RGB"))
        op = np.asarray(Image.open(src / "opacity.png").convert("L"))
        out, fallback = VARIANTS[variant](rgb, op)
        plant = op >= 128
        if not (out[plant] == rgb[plant]).all():
            raise SystemExit(f"{variant} changed plant pixels in {r['key']}")
        d = maps_dir / r["key"]
        d.mkdir()
        Image.fromarray(out, "RGB").save(d / "diffuse.png")
        Image.fromarray(op, "L").save(d / "opacity.png")
        v4 = np.asarray(Image.open(EV / "run-v004" / "maps" / r["key"] / "diffuse.png").convert("RGB"))
        per[r["key"]] = {"changed_vs_v003": int((out != rgb).any(2).sum()),
                         "diff_vs_v004": int((out != v4).any(2).sum()), "seed_fallback": fallback}
        row = dict(r)
        row["out"] = {"diffuse": str(d / "diffuse.png"), "opacity": str(d / "opacity.png"),
                      "diffuse_sha256": sha(d / "diffuse.png"), "opacity_sha256": sha(d / "opacity.png")}
        rows.append(row)
    JOB.dump(maps_dir / "maps.json", {"schema": "vatutino-flora-route-a-maps-v1", "rows": rows})
    JOB._atlas(run_dir, "npm")
    return per


def arrays(atlas_dir):
    a = Path(atlas_dir)
    return (np.asarray(Image.open(a / "T_VATUTINO_Flora_Diffuse.png").convert("RGB")),
            np.asarray(Image.open(a / "T_VATUTINO_Flora_Opacity.png").convert("L")))


def scored(atlas_dir, perturb=None):
    rgb, a, cells, hashes = S.load(Path(atlas_dir))
    changed = None
    if perturb:
        rgb, changed = S.perturb(rgb, a, perturb)
    res = S.score(rgb, a, cells)
    return {"atlas_score": res["atlas_score"], "worst_cell": res["worst_cell"], "changed_rgb_pixels": changed,
            "cells": {c: {"max_p95": v["max_p95"], "signed_mean": v["signed_mean"]} for c, v in res["cells"].items()}}


def one_round(out):
    maps_rows = json.loads((EV / "run-v003/maps/maps.json").read_text(encoding="utf-8"))["rows"]
    res = {"delivered": {"v003": scored(EV / "run-v003/atlas"), "v004": scored(EV / "run-v004/atlas")}}
    v4_rgb, v4_op = arrays(EV / "run-v004/atlas")
    for var in VARIANTS:
        run_dir = out / var
        per = build(var, maps_rows, run_dir)
        rgb, op = arrays(run_dir / "atlas")
        res[var] = {"maps": per, "atlas_rgb_px_diff_vs_v004": int((rgb != v4_rgb).any(2).sum()),
                    "atlas_opacity_px_diff_vs_v004": int((op != v4_op).sum()), "score": scored(run_dir / "atlas")}
    for p in ("N0", "P1", "P3"):
        res["C1"][f"control_{p}"] = scored(out / "C1" / "atlas", p)
    diag = {}
    for r in maps_rows:
        d = EV / "run-v004/maps" / r["key"]
        diag[r["key"]] = diagnostic(np.asarray(Image.open(d / "diffuse.png").convert("RGB")),
                                    np.asarray(Image.open(d / "opacity.png").convert("L")))
    res["diagnostic_v004_maps"] = diag
    return res


def main(out):
    out = Path(out)
    if out.exists():
        raise SystemExit(f"{out} exists: new dirs only")
    if git_blob(HERE / "score.py") != SCORE_BLOB:
        raise SystemExit("score.py differs from the #129 blob")
    t0 = time.time()
    pre = manifest_check()
    rounds = []
    for i in range(ROUNDS):
        rounds.append(one_round(out / f"r{i + 1}"))
    post = manifest_check()
    canon = [json.dumps(r, sort_keys=True) for r in rounds]
    rec = {"card": "t_b9389ba4", "manifest_rows_pre": pre, "manifest_rows_post": post,
           "score_py_blob": SCORE_BLOB, "erode_px": ERODE_PX, "edge_px": EDGE_PX,
           "rounds_identical": len(set(canon)) == 1, "status": "series_complete",
           "round_sha256": [hashlib.sha256(c.encode()).hexdigest() for c in canon],
           "wall_s": round(time.time() - t0, 2), "env": {"python": sys.version.split()[0], "numpy": np.__version__,
                                                          "pillow": Image.__version__},
           "result": rounds[0]}
    (out / "receipt.json").write_text(json.dumps(rec, indent=1, sort_keys=True), encoding="utf-8")
    r = rounds[0]
    print(json.dumps({k: r[k]["score"]["atlas_score"] for k in VARIANTS} |
                     {"v003": r["delivered"]["v003"]["atlas_score"], "v004": r["delivered"]["v004"]["atlas_score"],
                      "identical": rec["rounds_identical"], "wall_s": rec["wall_s"]}))


if __name__ == "__main__":
    main(sys.argv[1])
