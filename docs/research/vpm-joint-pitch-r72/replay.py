"""Observe VPM panel pitch; see docs/research/autoresearch-vpm-joint-pitch.md."""
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

BASE = "4288c54de328db7a5037b57707862319f7aa6ff0"
R71 = "b105d8bcf04c437b3f746a02bc4cf817b5f1265e"
LOADER = "docs/research/atlas-npm-vpm-drift-r71/replay.py"
JOINT = "jobs/TEC26-OKS/scripts/joint_count.py"
SPEC = "jobs/TEC26-OKS/AC08/vpm_textures.json"
FINISHES = {"PanelVJ30_RAL5015": 1001, "PanelVJ12_RAL5015": 1002}
LABELS = {"v007": "rejected_600mm_pitch", "v010": "accepted_visual"}


def git_bytes(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"])


def git_source(rev, path) -> dict[str, Any]:
    namespace = {"__name__": "pinned_research_dependency"}
    exec(compile(git_bytes(rev, path), f"{rev}:{path}", "exec"), namespace)
    return namespace


def pitch(tile, runs):
    gaps, counts = [], []
    for y in (tile.shape[0] // 4, tile.shape[0] // 2, tile.shape[0] * 3 // 4):
        lum = tile[y, :, :3].sum(axis=1)
        centres = [(a + b - 1) / 2 for a, b in runs(lum < 0.8 * np.median(lum))
                   if a > 0 and b < len(lum)]
        if len(centres) < 3:
            raise ValueError(f"pitch not measured: {len(centres)} complete runs on row {y}")
        counts.append(len(centres))
        gaps.extend(np.diff(centres))
    return float(np.median(gaps)), counts


def tile_binding(version, target):
    if version == "v007":
        return "PanelVJ_RAL5015", 1001
    return target, FINISHES[target]


def one_round(load, runs, finishes):
    result = {}
    for version in LABELS:
        plan, _, tiles = load(version)
        detail = {k: {} for k in ("clean", "half_pitch", "brightness_plus8")}
        for name in FINISHES:
            actual, udim = tile_binding(version, name)
            if plan["finishes"][actual]["udim"] != udim or tiles[udim].shape != (4096, 4096, 3):
                raise ValueError(f"unbound 4K tile: {version}/{name}")
            tile, spec = tiles[udim], finishes[name]
            expected = spec["P"][0] * 4096 / spec["S"]
            cols = np.arange(tile.shape[1]) * 2 % tile.shape[1]
            clean = pitch(tile, runs)
            for variant in detail:
                if variant == "half_pitch":
                    img = tile[:, cols]
                elif variant == "brightness_plus8":
                    img = np.minimum(tile, 247) + np.uint8(8)
                else:
                    img = tile
                observed, counts = pitch(img, runs)
                changed = int(np.count_nonzero(np.any(img != tile, axis=-1))) if variant != "clean" else None
                detail[variant][name] = {"udim": udim, "input_finish": actual,
                                         "observed_px": observed, "expected_px": expected,
                                         "relative_error": abs(observed / expected - 1), "runs": counts,
                                         "changed_px": changed if changed else "not_exercised"}
            if pitch(tile, runs) != clean:
                raise ValueError(f"clean score changed: {version}/{name}")
        result[version] = {"label": LABELS[version], "per_finish": detail,
                           "E72": {k: max(f["relative_error"] for f in d.values()) for k, d in detail.items()}}
    return result


def witnesses_ok(rows):
    for version, label in rows.items():
        e = label["E72"]
        lo, hi = (0.47, 0.53) if version == "v010" else (0.50, 0.65)
        if not lo <= e["half_pitch"] <= hi or abs(e["brightness_plus8"] - e["clean"]) > 0.01:
            return False
        for variant in ("half_pitch", "brightness_plus8"):
            if any(f["changed_px"] == "not_exercised" for f in label["per_finish"][variant].values()):
                return False
    return True


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    loader = git_source(R71, LOADER)
    runs = git_source(BASE, JOINT)["runs"]
    finishes = json.loads(git_bytes(BASE, SPEC))["finishes"]
    start, rounds, status, error = time.perf_counter(), [], "complete", None
    for _ in range(3):
        t0 = time.perf_counter()
        if t0 - start >= 60:
            status = "budget_stop"
            break
        try:
            rows = one_round(loader["load"], runs, finishes)
        except (OSError, ValueError, KeyError) as exc:
            status, error = "input_or_measurement_error", str(exc)
            break
        wall = time.perf_counter() - t0
        rounds.append({"rows": rows, "wall_s": wall, "witnesses_ok": witnesses_ok(rows)})
        if (len(rounds) == 1 and wall > 20) or time.perf_counter() - start > 60:
            status = "budget_stop"
            break
    series = {v: [r["rows"][v]["E72"]["clean"] for r in rounds] for v in LABELS}
    paired = [r - a for r, a in zip(series["v007"], series["v010"], strict=True)]
    median, spread, verdict = None, None, "inconclusive"
    if status == "complete":
        median = {v: statistics.median(s) for v, s in series.items()}
        spread = max(paired) - min(paired)
        if all(r["witnesses_ok"] for r in rounds):
            if min(paired) > 0 and statistics.median(paired) >= 0.97 and spread <= 0.01 and (
                median["v010"] <= 0.03 and median["v007"] >= 1.0
            ):
                verdict = "confirmed"
            elif spread <= 0.01:
                verdict = "refuted"
    receipt = {"card": "t_82ef7ef0", "base": BASE, "loader": R71,
               "pins": {v: loader["PINS"][v] for v in LABELS},
               "candidate_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "python": sys.version.split()[0], "numpy": np.__version__,
               "status": status, "error": error, "verdict_H72": verdict, "median_E72": median,
               "paired_differences": paired, "paired_spread": spread,
               "wall_s": time.perf_counter() - start, "rounds": rounds}
    (out / "receipt.json").write_bytes((json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("rounds", "pins")}))
    return 2 if error is not None else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
