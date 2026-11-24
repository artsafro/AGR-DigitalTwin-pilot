"""Standing #71: per-finish drift of the delivered NPM atlas region vs the VPM UDIM tile (OBSERVE).

Usage: uv run --frozen python docs/research/atlas-npm-vpm-drift-r71/replay.py <new_out_dir>
Contract: docs/research/autoresearch-atlas-npm-vpm-drift.md (frozen before the first run).
"""
from __future__ import annotations

import hashlib
import io
import json
import statistics
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

BASE = "4288c54de328db7a5037b57707862319f7aa6ff0"
DRIVE = Path("G:/Мой диск/AGR-evidence")
VPM_ZIP, ATLAS, PLAN = "SM_Nku_1.zip", "T_Nku_1_001_Main_d_1.png", "npm_atlas.json"
LABELS = {"v007": "rejected_seams", "v010": "accepted_visual", "v006": "unlabelled", "v009": "unlabelled"}
PINS = {  # SHA-256 of SM_Nku_1.zip, atlas, npm_atlas.json (= each folder's SHA256SUMS.txt)
    "v006": ("1adaaa707234078a5b887756608bf05432458cf6ee3bcd6cd1f2764301376988",
             "9ac1768f0e98b4fc6d9aeda3df8f131b3719ebdd3399adf87f89a03fe140d699",
             "e641bc91456b7de3ac3f6f6913b935db8830a7fea711e72a75881e2c23479a42"),
    "v007": ("271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295",
             "772a2768ca396a4c6b404357ad30a676de4bf6928be053db1d956fb3b675a516",
             "9feb8685a71dec4cd2bb746bd3695bccdce3e648199dc0f32cb3738f6c430ea2"),
    "v009": ("d9d8178fd1ebbd06fe961f02d454c94fe013e6afc762e9b2565f0cbb9c5b0b14",
             "88e0392ea057013e4eb33e9240a3856a1728fb8380433cab9662f73052473278",
             "338edcd767c0c6c99f762d4b7a9dcfd9407da030086ccb5b96e551d3bffae0cc"),
    "v010": ("2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb",
             "88e0392ea057013e4eb33e9240a3856a1728fb8380433cab9662f73052473278",
             "338edcd767c0c6c99f762d4b7a9dcfd9407da030086ccb5b96e551d3bffae0cc"),
}
WITNESS_PX, WITNESS_MIN = 5, 0.005
P2_LEVELS, P2_BOUNDS = 8, (0.015, 0.032)


def load(v):
    folder = DRIVE / f"559-tec26-oks-ac08-pilot-{v}"
    raw = [(folder / n).read_bytes() for n in (VPM_ZIP, ATLAS, PLAN)]
    got = tuple(hashlib.sha256(b).hexdigest() for b in raw)
    if got != PINS[v]:
        raise ValueError(f"{v}: input hash mismatch {got}")
    vpm, atlas_png, plan = raw
    plan = json.loads(plan)
    atlas = np.asarray(Image.open(io.BytesIO(atlas_png)).convert("RGB"))
    with zipfile.ZipFile(io.BytesIO(vpm)) as z:
        tiles = {int(n.rsplit(".", 2)[-2]): np.asarray(Image.open(io.BytesIO(z.read(n))).convert("RGB"))
                 for n in z.namelist() if n.startswith("T_Nku_1_Diffuse_1.") and n.endswith(".png")}
    return plan, atlas, tiles


def region_box(plan, entry):
    side, region = plan["atlas"], plan["region"]
    x, top = entry["u0"] * side, (1 - entry["v0"]) * side - region
    if not (x.is_integer() and top.is_integer() and entry["size"] * side == region):
        raise ValueError(f"non-integer region {entry}")
    return int(top), int(x)


def crop(plan, atlas, entry):
    top, x = region_box(plan, entry)
    r = plan["region"]
    return atlas[top:top + r, x:x + r]


def reference(plan, tile):
    r = plan["region"]
    return np.asarray(Image.fromarray(tile, "RGB").resize((r, r), Image.LANCZOS))


def drift(region, ref):
    d = np.abs(region.astype(np.int16) - ref.astype(np.int16)) / 255.0
    return float(d.mean()), float(np.percentile(d, 95))


def textured(plan, tiles):
    return [f for f, e in plan["finishes"].items()
            if e["px_per_m"] is not None and tiles[e["udim"]].shape[:2] == (4096, 4096)]


def score(plan, atlas, tiles, swap=None):
    per = {}
    names = textured(plan, tiles)
    for f in names:
        e = plan["finishes"][f]
        ref_f = swap.get(f, f) if swap else f
        mean, p95 = drift(crop(plan, atlas, e), reference(plan, tiles[plan["finishes"][ref_f]["udim"]]))
        per[f] = {"mean": round(mean, 10), "p95": round(p95, 10), "reference_finish": ref_f}
    m71 = max(v["mean"] for v in per.values()) if per else None
    return m71, per


def side_checks(plan, atlas, tiles):
    pad, region = plan["pad"], plan["region"]
    solid, pad_bad = {}, {}
    for f, e in plan["finishes"].items():
        top, x = region_box(plan, e)
        cell = atlas[top - pad:top + region + pad, x - pad:x + region + pad]
        reg = atlas[top:top + region, x:x + region]
        pad_bad[f] = int((np.pad(reg, ((pad, pad), (pad, pad), (0, 0)), mode="edge") != cell).any(-1).sum())
        if f not in textured(plan, tiles):
            solid[f] = int(np.abs(reg.reshape(-1, 3).mean(0) - tiles[e["udim"]].reshape(-1, 3).mean(0)).max().round())
    xs = sorted({e["u0"] for e in plan["finishes"].values()})
    gap = min((b - a - plan["region"] / plan["atlas"]) * plan["atlas"] for a, b in zip(xs, xs[1:]))
    return {"solid_mean_level_diff": solid, "pad_band_mismatch_px": pad_bad, "inter_region_gap_px": round(gap, 6)}


def witnesses(plan, atlas, tiles, clean):
    out = {}
    names = textured(plan, tiles)
    shifted, bright = atlas.copy(), atlas.copy()
    for f in names:
        top, x = region_box(plan, plan["finishes"][f])
        r = plan["region"]
        shifted[top:top + r, x:x + r] = np.roll(atlas[top:top + r, x:x + r], WITNESS_PX, axis=1)
        bright[top:top + r, x:x + r] = np.clip(atlas[top:top + r, x:x + r].astype(np.int16) + P2_LEVELS, 0, 255)
    changed = {f: int((shifted != atlas).any(-1)[region_slice(plan, f)].sum()) for f in plan["finishes"]}
    m, _ = score(plan, shifted, tiles)
    out["shift_u_5px"] = {"m71": m, "delta": round(m - clean, 10), "bound_min": WITNESS_MIN,
                          "ok": m - clean >= WITNESS_MIN,
                          "changed_px": {f: (c if f in names else "not_exercised") for f, c in changed.items()}}
    m, _ = score(plan, bright, tiles)
    out["p2_brightness_8"] = {"m71": m, "delta": round(m - clean, 10), "bounds": P2_BOUNDS,
                              "ok": P2_BOUNDS[0] <= m - clean <= P2_BOUNDS[1]}
    if len(names) >= 2:
        swap = {names[0]: names[1], names[1]: names[0]}
        m, per = score(plan, atlas, tiles, swap)
        out["p1_finish_swap"] = {"m71": m, "delta": round(m - clean, 10), "ok": m > clean, "pairs": swap}
    else:
        out["p1_finish_swap"] = "not_exercised (one textured finish)"
    return out


def region_slice(plan, f):
    top, x = region_box(plan, plan["finishes"][f])
    r = plan["region"]
    return slice(top, top + r), slice(x, x + r)


def one_round():
    res = {}
    for v in PINS:
        plan, atlas, tiles = load(v)
        m71, per = score(plan, atlas, tiles)
        res[v] = {"label": LABELS[v], "m71": m71, "per_finish": per, "side": side_checks(plan, atlas, tiles)}
        if v == "v010":
            res[v]["witness"] = witnesses(plan, atlas, tiles, m71)
    return res


def main(out: Path):
    out.mkdir(parents=True, exist_ok=False)
    t0, rounds = time.perf_counter(), []
    for _ in range(3):
        r0 = time.perf_counter()
        rounds.append({"result": one_round(), "wall_s": round(time.perf_counter() - r0, 3)})
    series = {v: [r["result"][v]["m71"] for r in rounds] for v in PINS}
    spread = max(max(s) - min(s) for s in series.values())
    med = {v: statistics.median(s) for v, s in series.items()}
    d71 = med["v007"] - med["v010"]
    wit = rounds[-1]["result"]["v010"]["witness"]
    wit_ok = all(w["ok"] for w in wit.values() if isinstance(w, dict)) and all(
        r["result"]["v010"]["witness"] == wit for r in rounds)
    verdict = ("inconclusive" if not wit_ok else
               "confirmed" if d71 > 0 and d71 > 3 * spread else "refuted" if d71 <= 0 else "inconclusive")
    receipt = {"card": "t_69818899", "base": BASE, "candidate_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "pins": PINS, "median_m71": med, "series": series, "paired_spread": spread, "D71": round(d71, 10),
               "witness_ok": wit_ok, "verdict_H71": verdict, "wall_s": round(time.perf_counter() - t0, 3),
               "status": "complete", "rounds": rounds}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("median_m71", "paired_spread", "D71", "witness_ok", "verdict_H71",
                                                "wall_s")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
