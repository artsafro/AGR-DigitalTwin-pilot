"""#75 replay: MAF 512 atlas v007 r1/r2 patterned-cell effective resolution (R75), OBSERVE only.

Usage: uv run --frozen python docs/research/maf-atlas-sharpness-r75/replay.py <out_dir>
Contract: docs/research/autoresearch-maf-atlas-sharpness.md (frozen at 6a757eae).
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
DRIVE = Path("G:/Мой диск/AGR-assets/maf/atlas/v007")
INPUTS = {
    "r1": (DRIVE / "T_MAF_Atlas_v007_GroundEl_d_512.png",
           "55e654a2e04ce2e828cd1f7a1f585d54263a01050f00cb60d5d3bab4f6d0cf6d", "88535418"),
    "r2": (DRIVE / "T_MAF_Atlas_v007_GroundEl_d_512_r2.png",
           "a30dac001483b42d99afee0fc315e58ddc4ba1ce10d7bb58e8565017e4b3f340", "01e48513"),
}
LAYOUT = "library/maf/atlas_512_v007.json"
REJECTED = ("r1", 18)
INSET = 2


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def layout(rev: str) -> dict:
    txt = subprocess.run(["git", "show", f"{INPUTS[rev][2]}:{LAYOUT}"], cwd=ROOT, check=True,
                         capture_output=True).stdout.decode("utf-8")
    return json.loads(txt)


def luma(rgb: np.ndarray) -> np.ndarray:
    a = rgb.astype(np.float64)
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def S(rgb: np.ndarray) -> float:
    y = luma(rgb)
    lap = 4 * y[1:-1, 1:-1] - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:]
    return float(np.abs(lap).mean() / np.abs(y - y.mean()).mean())


def reup(rgb: np.ndarray, f: float) -> np.ndarray:
    h, w = rgb.shape[:2]
    im = Image.fromarray(rgb, "RGB")
    small = im.resize((round(w / f), round(h / f)), Image.Resampling.LANCZOS)
    return np.asarray(small.resize((w, h), Image.Resampling.LANCZOS), dtype=np.uint8)


def R(rgb: np.ndarray) -> float:
    return S(reup(rgb, 1.1)) / S(rgb)


def perturb(rgb: np.ndarray, kind: str) -> np.ndarray:
    a = rgb.astype(np.float64)
    if kind == "W1":
        return reup(rgb, 1.1)
    if kind == "W2":
        return reup(rgb, 2.0)
    if kind == "P1":
        return np.clip(a + 8, 0, 255).astype(np.uint8)
    if kind == "P2":
        m = a.mean(axis=(0, 1), keepdims=True)
        return np.clip(np.rint(m + 0.8 * (a - m)), 0, 255).astype(np.uint8)
    raise ValueError(kind)


def one_round() -> dict:
    t0 = time.perf_counter()
    cells, crops = [], {}
    for rev, (png, want, _) in INPUTS.items():
        got = sha256(png)
        if got != want:
            raise SystemExit(f"preflight: {png} sha256 {got} != {want}")
        atlas = np.asarray(Image.open(png).convert("RGB"), dtype=np.uint8)
        lay = layout(rev)
        kinds = {s["id"]: s["kind"] for s in lay["slots"]}
        meta = {s["id"]: s for s in lay["slots"]}
        for c in lay["cells"]:
            if kinds.get(c["id"]) != "patterned":
                continue
            x, y, w, h = c["content_px"]
            if x < 0 or y < 0 or x + w > atlas.shape[1] or y + h > atlas.shape[0]:
                raise SystemExit(f"parity: {rev} id {c['id']} content outside atlas")
            crop = atlas[y + INSET:y + h - INSET, x + INSET:x + w - INSET].copy()
            box = meta[c["id"]]["box"]
            crops[(rev, c["id"])] = crop
            cells.append({
                "rev": rev, "id": c["id"], "key": c["key"],
                "label": "rejected" if (rev, c["id"]) == REJECTED else "accepted",
                "content_px": c["content_px"], "crop_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
                "R75": R(crop), "S75": S(crop),
                "meta_src_per_content": (box[2] - box[0]) / w,
            })
    rej = next(c for c in cells if c["label"] == "rejected")
    acc = [c for c in cells if c["label"] == "accepted"]
    r2_18 = next(c for c in cells if (c["rev"], c["id"]) == ("r2", 18))
    wit = {}
    for target in [("r2", 18), ("r1", 18)]:
        base = crops[target]
        for k in ("W1", "W2", "P1", "P2"):
            p = perturb(base, k)
            changed = int((p != base).any(axis=2).sum())
            wit[f"{target[0]}_{target[1]}_{k}"] = {
                "changed_px": changed, "state": "exercised" if changed else "not_exercised",
                "R75": R(p), "dR75": R(p) - R(base)}
    return {
        "cells": cells, "witness": wit,
        "D75": rej["R75"] - r2_18["R75"],
        "max_accepted_R75": max(c["R75"] for c in acc),
        "collateral": sum(c["R75"] >= rej["R75"] for c in acc),
        "wall_s": time.perf_counter() - t0,
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--round":
        print(json.dumps(one_round()))
        return 0
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "tmp/r75-NEW")
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    rounds = []
    for i in range(3):
        p = subprocess.run([sys.executable, __file__, "--round"], cwd=ROOT, check=True,
                           capture_output=True, text=True)
        rounds.append(json.loads(p.stdout))
        (out / f"round{i + 1}.json").write_text(p.stdout, encoding="utf-8")
    d = [r["D75"] for r in rounds]
    w1 = [r["witness"]["r2_18_W1"]["dR75"] for r in rounds]
    w2 = [r["witness"]["r2_18_W2"]["dR75"] for r in rounds]
    inv = [abs(r["witness"]["r2_18_P1"]["dR75"]) <= 0.01 and abs(r["witness"]["r2_18_P2"]["dR75"]) <= 0.02
           for r in rounds]
    rej = [next(c for c in r["cells"] if c["label"] == "rejected")["R75"] for r in rounds]
    above = all(rj > r["max_accepted_R75"] for rj, r in zip(rej, rounds))
    if all(x <= 0 for x in d):
        verdict = "refuted"
    elif above and min(d) >= 0.01 and max(d) - min(d) <= 1e-9 and min(w1) >= 0.01:
        verdict = "confirmed"
    else:
        verdict = "inconclusive"
    summary = {
        "verdict": verdict, "D75_median": statistics.median(d), "D75_range": max(d) - min(d),
        "rejected_above_all_accepted_all_rounds": above,
        "W1_dR75_median": statistics.median(w1), "W1_in_bound": min(w1) >= 0.01,
        "W2_dR75_median": statistics.median(w2), "W2_in_bound": min(w2) >= 0.05,
        "invariance_in_bounds_all_rounds": all(inv),
        "collateral_max": max(r["collateral"] for r in rounds),
        "wall_s_total": time.perf_counter() - t0, "round_wall_s": [r["wall_s"] for r in rounds],
        "cells_round1": rounds[0]["cells"], "witness_round1": rounds[0]["witness"],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith("round1")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
