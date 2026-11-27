"""Replay for standing #129: 3 rounds x (v003 NPM, v004 NPM, v004 VPM clean; v004 NPM N0/P1/P2/P3) -> receipt.

    python docs/research/autoresearch-atlas-alpha-bleed-harness/replay.py <out_dir>

Inputs are pinned by SHA-256 (preflight and postflight); a mismatch aborts before any score is written.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score as S  # noqa: E402

ROOT = Path("G:/Мой диск/AGR-evidence/1146-flora-star")
PINNED = {
    "run-v003/atlas/T_VATUTINO_Flora_Diffuse.png": "af5c6f93ab0c841dac800f430edf9a8ce84e6c5f8c321c02bff8a144a459157b",
    "run-v003/atlas/T_VATUTINO_Flora_Opacity.png": "357f8a2f51a0bf22047711ac85a83bdcf2b4a5f642b6e4c135ac9da573ea9684",
    "run-v004/atlas/T_VATUTINO_Flora_Diffuse.png": "b2f71a8cb104f78100c19d46eff37a3073a2cd730be5373c5262b29dde0bb6ee",
    "run-v004/atlas/T_VATUTINO_Flora_Opacity.png": "357f8a2f51a0bf22047711ac85a83bdcf2b4a5f642b6e4c135ac9da573ea9684",
    "run-v004/atlas-vpm/T_VATUTINO_Flora_Diffuse.png": "c58b7033671bbaaa64d2a2987436b21d2931b0066d2f9e55c9c3b33bdd1fc64f",
    "run-v004/atlas-vpm/T_VATUTINO_Flora_Opacity.png": "f31d41df15add81ed4e978f83e60a8621fce4ac20b0beb2b70c7af45b71ab758",
}
STATES = [("v003_npm", "run-v003/atlas", None), ("v004_npm", "run-v004/atlas", None),
          ("v004_vpm", "run-v004/atlas-vpm", None)] + [
          (f"v004_npm_{p}", "run-v004/atlas", p) for p in ("N0", "P1", "P2", "P3")] + [
          ("v003_npm_P3", "run-v003/atlas", "P3")]


def flight():
    bad = {k: h for k, h in PINNED.items() if S.sha256(ROOT / k) != h}
    if bad:
        raise SystemExit(f"pinned input mismatch: {sorted(bad)}")


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    flight()
    t0 = time.perf_counter()
    rounds = []
    for r in (1, 2, 3):
        rows = {}
        for name, rel, kind in STATES:
            rgb, a, cells, hashes = S.load(ROOT / rel)
            changed = None
            if kind:
                rgb, changed = S.perturb(rgb, a, kind)
            res = S.score(rgb, a, cells)
            res.update(inputs_sha256=hashes, changed_rgb_pixels=changed, perturb=kind)
            rows[name] = res
            print(r, name, res["atlas_score"], res["worst_cell"], changed, flush=True)
        rounds.append(rows)
    flight()
    wall = time.perf_counter() - t0
    canon = [json.dumps(x, sort_keys=True) for x in rounds]
    receipt = {"card": "t_729dea88", "standing": 129, "wall_s": round(wall, 2), "status": "series_complete",
               "rounds_identical": len(set(canon)) == 1, "pinned": PINNED,
               "round_sha256": [hashlib.sha256(c.encode()).hexdigest() for c in canon], "result": rounds[0]}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    print("wall", round(wall, 2), "identical", receipt["rounds_identical"])


if __name__ == "__main__":
    main()
