"""Observe NPM atlas panel pitch; see docs/research/autoresearch-npm-atlas-pitch.md (frozen before the first run)."""
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
TARGETS = ("PanelVJ30_RAL5015", "PanelVJ12_RAL5015")
LABELS = {"v007": "rejected_600mm_pitch", "v010": "accepted_visual"}
BOUNDS = {"v010": (0.45, 0.55), "v007": (0.50, 0.70)}  # half-pitch witness


def git_bytes(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"])


def git_source(rev, path) -> dict[str, Any]:
    namespace = {"__name__": "pinned_research_dependency"}
    exec(compile(git_bytes(rev, path), f"{rev}:{path}", "exec"), namespace)
    return namespace


def pitch(tile, runs):
    """#72 census, verbatim: rows 25/50/75 %, dark < 0.8 * row median, complete runs only."""
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


def half_pitch(region):
    """Amendment A1: 2:1 box downsample of columns (cyclic), so 1-2 px NPM joints survive (plain 2*x sampling drops half)."""
    w = region.shape[1]
    x = np.arange(w)
    pair = region[:, x * 2 % w].astype(np.uint16) + region[:, (x * 2 + 1) % w]
    return (pair // 2).astype(np.uint8)


def region_binding(version, target):
    return ("PanelVJ_RAL5015" if version == "v007" else target)


def one_round(loader, runs, spec):
    result = {}
    for version in LABELS:
        plan, atlas, _tiles = loader["load"](version)
        if atlas.shape != (plan["atlas"], plan["atlas"], 3) or (plan["atlas"], plan["region"]) != (2048, 397):
            raise ValueError(f"unbound atlas: {version}")
        detail = {k: {} for k in ("clean", "half_pitch", "brightness_plus8")}
        for name in TARGETS:
            actual = region_binding(version, name)
            entry = plan["finishes"][actual]
            if entry["px_per_m"] != 96.9:
                raise ValueError(f"untextured region: {version}/{actual}")
            region = loader["crop"](plan, atlas, entry)
            s = spec[name]
            expected = s["P"][0] * plan["region"] / s["S"]
            clean = pitch(region, runs)
            for variant in detail:
                if variant == "half_pitch":
                    img = half_pitch(region)
                elif variant == "brightness_plus8":
                    img = np.minimum(region, 247) + np.uint8(8)
                else:
                    img = region
                observed, counts = pitch(img, runs)
                changed = None
                if variant != "clean":
                    n = int(np.count_nonzero(np.any(img != region, axis=-1)))
                    changed = n if n else "not_exercised"
                detail[variant][name] = {"input_finish": actual, "observed_px": observed, "expected_px": expected,
                                         "relative_error": abs(observed / expected - 1), "runs": counts,
                                         "changed_px": changed}
            if pitch(region, runs) != clean:
                raise ValueError(f"clean score changed: {version}/{name}")
        result[version] = {"label": LABELS[version], "per_finish": detail,
                           "E73": {k: max(f["relative_error"] for f in d.values()) for k, d in detail.items()}}
    return result


def witnesses_ok(rows):
    for version, label in rows.items():
        e = label["E73"]
        lo, hi = BOUNDS[version]
        if not lo <= e["half_pitch"] <= hi or abs(e["brightness_plus8"] - e["clean"]) > 0.01:
            return False
        for variant in ("half_pitch", "brightness_plus8"):
            if any(f["changed_px"] == "not_exercised" for f in label["per_finish"][variant].values()):
                return False
    return True


def verdict(status, rounds):
    series = {v: [r["rows"][v]["E73"]["clean"] for r in rounds] for v in LABELS}
    paired = [r - a for r, a in zip(series["v007"], series["v010"], strict=True)]
    if status != "complete" or len(rounds) != 3:
        return "inconclusive", None, paired, None
    median = {v: statistics.median(s) for v, s in series.items()}
    spread = max(paired) - min(paired)
    if not all(r["witnesses_ok"] for r in rounds) or spread > 0.01:
        return "inconclusive", median, paired, spread
    if min(paired) > 0 and statistics.median(paired) >= 0.95 and median["v010"] <= 0.05 and median["v007"] >= 1.0:
        return "confirmed", median, paired, spread
    return "refuted", median, paired, spread


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    loader = git_source(R71, LOADER)
    runs = git_source(BASE, JOINT)["runs"]
    spec = json.loads(git_bytes(BASE, SPEC))["finishes"]
    start, rounds, status, error = time.perf_counter(), [], "complete", None
    for _ in range(3):
        t0 = time.perf_counter()
        if t0 - start >= 60:
            status = "budget_stop"
            break
        try:
            rows = one_round(loader, runs, spec)
        except (OSError, ValueError, KeyError) as exc:
            status, error = "input_or_measurement_error", str(exc)
            break
        wall = time.perf_counter() - t0
        rounds.append({"rows": rows, "wall_s": wall, "witnesses_ok": witnesses_ok(rows)})
        if (len(rounds) == 1 and wall > 20) or time.perf_counter() - start > 60:
            status = "budget_stop"
            break
    result, median, paired, spread = verdict(status, rounds)
    receipt = {"card": "t_b8ec6b71", "base": BASE, "loader": R71,
               "pins": {v: loader["PINS"][v] for v in LABELS},
               "candidate_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "python": sys.version.split()[0], "numpy": np.__version__,
               "status": status, "error": error, "verdict_H73": result, "median_E73": median,
               "paired_differences": paired, "paired_spread": spread,
               "wall_s": time.perf_counter() - start, "rounds": rounds}
    (out / "receipt.json").write_bytes((json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("rounds", "pins")}))
    return 2 if error is not None else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
