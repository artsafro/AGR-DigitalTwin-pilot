"""Standing #79: frozen #78 row-median pitch census on held-out TEC26 AC09 VPM.

Contract: docs/research/autoresearch-ac09-vpm-pitch.md (frozen in e09ac465 before any AC09 score).
"""
import hashlib
import io
import json
import statistics
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

R78 = "1358b8262ce2f93a15d3125443c308305d31b8cf"
P78 = "docs/research/vpm-row-pitch-r78/replay.py"
SPEC_REV = "b735e90f"
SPEC = "jobs/TEC26-OKS/AC09/vpm_textures.json"
ZIP = Path("G:/Мой диск/AGR-evidence/tec26-oks/FINAL-2026-10-22/AC09_SAKV/VPM/SM_Sakv_1.zip")
ZIP_SHA = "e41c89a150434145ff8576216b09f71af95564882afea81f0b4ed9d9569ae832"
EXPECTED_TILES = [1001, 1002, 1008, 1009]
CONTROL_E78 = 2.220998038374616
BOUND, HALF, LIGHT, SPREAD = 0.03, (0.45, 0.55), 0.01, 0.001
FIRST_LIMIT, TOTAL_LIMIT = 60.0, 240.0


def git_bytes(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"])


def git_source(rev, path):
    ns = {"__name__": "pinned_r79_dependency"}
    exec(compile(git_bytes(rev, path), f"{rev}:{path}", "exec"), ns)
    return ns


def modal_rgb(tile):
    flat = tile.reshape(-1, 3).astype(np.uint32)
    packed = int(np.argmax(np.bincount((flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2], minlength=1 << 24)))
    return [packed >> 16, (packed >> 8) & 255, packed & 255]


def score_tile(tile, expected, pitch, runs):
    clean_obs, counts = pitch(tile, runs)
    e = abs(clean_obs / expected - 1)
    row = {"state": "measured", "observed_px": clean_obs, "runs": counts, "E": e, "flagged": e > BOUND}
    cols = np.arange(tile.shape[1]) * 2 % tile.shape[1]
    for var, img in (("half_pitch", tile[:, cols]), ("brightness_plus8", np.minimum(tile, 247) + np.uint8(8))):
        changed = int(np.count_nonzero(np.any(img != tile, axis=-1)))
        if not changed:
            row[var] = {"state": "not_exercised", "changed_px": 0}
            continue
        try:
            obs, c = pitch(img, runs)
        except ValueError as exc:
            row[var] = {"state": "not_measured", "reason": str(exc), "changed_px": changed}
            continue
        ve = abs(obs / expected - 1)
        applies = var != "half_pitch" or e <= BOUND
        ok = (HALF[0] <= ve <= HALF[1]) if var == "half_pitch" else abs(ve - e) <= LIGHT
        row[var] = {"state": "exercised", "observed_px": obs, "runs": c, "E": ve, "changed_px": changed,
                    "in_bound": ok, "bound_applies": applies}
    if pitch(tile, runs)[0] != clean_obs:
        raise ValueError("clean tile score changed after witnesses")
    return row


def ac09_round(pitch, runs, finishes):
    data = ZIP.read_bytes()
    if hashlib.sha256(data).hexdigest() != ZIP_SHA:
        raise ValueError("AC09 fixture SHA-256 mismatch")
    zf = zipfile.ZipFile(io.BytesIO(data))
    by_udim = {v["udim"]: (k, v) for k, v in finishes.items()}
    rows = []
    for name in sorted(n for n in zf.namelist() if "_Diffuse_" in n):
        udim = int(name.rsplit(".", 2)[1])
        tile = np.asarray(Image.open(io.BytesIO(zf.read(name))).convert("RGB"))
        row = {"udim": udim, "size": tile.shape[0]}
        rows.append(row)
        finish, spec = by_udim.get(udim, (None, {}))
        row["finish"] = finish
        if spec.get("kind") != "full" or tile.shape[:2] != (4096, 4096):
            row["state"] = "not_exercised"
            continue
        row["modal_rgb"] = modal_rgb(tile)
        if row["modal_rgb"] != spec["rgb"]:
            row["state"] = "not_exercised"
            row["reason"] = "modal RGB differs from spec rgb"
            continue
        row["expected_px"] = spec["P"][0] * 4096 / spec["S"]
        try:
            row.update(score_tile(tile, row["expected_px"], pitch, runs))
        except ValueError as exc:
            row.update(state="not_measured", reason=str(exc))
    measured = [r for r in rows if r["state"] == "measured"]
    return {"rows": rows, "E79": max((r["E"] for r in measured), default=None),
            "measured_udims": [r["udim"] for r in measured],
            "flagged": [r["udim"] for r in measured if r["flagged"]]}


def control_round(pitch, runs, loader, ac08_spec):
    _, _, tiles = loader["load"]("v007")
    tile = tiles[1001]
    spec = ac08_spec["PanelVJ12_RAL5015"]
    obs, counts = pitch(tile, runs)
    e = abs(obs / (spec["P"][0] * 4096 / spec["S"]) - 1)
    return {"tile": "AC08 v007 1001", "observed_px": obs, "runs": counts, "E": e,
            "parity_vs_r78": abs(e - CONTROL_E78) <= 1e-9, "fires": e >= 1.0}


def witnesses_ok(rows):
    for r in rows:
        if r["state"] != "measured":
            continue
        for var in ("half_pitch", "brightness_plus8"):
            w = r.get(var, {})
            if w.get("state") == "exercised" and w["bound_applies"] and not w["in_bound"]:
                return False
            if w.get("state") != "exercised":
                return False
    return True


def verdict(status, rounds):
    if status != "complete" or len(rounds) != 3:
        return "inconclusive"
    if not all(r["control"]["fires"] and r["control"]["parity_vs_r78"] for r in rounds):
        return "inconclusive"
    if any(len(r["ac09"]["measured_udims"]) < 3 for r in rounds):
        return "inconclusive"
    es = [r["ac09"]["E79"] for r in rounds]
    if max(es) - min(es) > SPREAD:
        return "inconclusive"
    if any(r["ac09"]["flagged"] for r in rounds):
        return "refuted"
    if statistics.median(es) <= BOUND and all(witnesses_ok(r["ac09"]["rows"]) for r in rounds):
        return "confirmed"
    return "inconclusive"


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    r78 = git_source(R78, P78)
    pitch = r78["candidate"]()
    ac = r78["load_source"](r78["R72"], r78["P72"])
    loader = r78["load_source"](ac["R71"], ac["LOADER"])
    runs = git_source(ac["BASE"], ac["JOINT"])["runs"]
    ac08_spec = json.loads(git_bytes(ac["BASE"], ac["SPEC"]))["finishes"]
    finishes = json.loads(git_bytes(SPEC_REV, SPEC))["finishes"]
    rounds, status, error, t0 = [], "complete", None, time.perf_counter()
    for i in range(3):
        s = time.perf_counter()
        try:
            r = {"ac09": ac09_round(pitch, runs, finishes), "control": control_round(pitch, runs, loader, ac08_spec)}
        except (OSError, ValueError, KeyError) as exc:
            status, error = "input_or_measurement_error", str(exc)
            break
        r["wall_s"] = round(time.perf_counter() - s, 3)
        rounds.append(r)
        if (i == 0 and r["wall_s"] > FIRST_LIMIT) or time.perf_counter() - t0 > TOTAL_LIMIT:
            status = "budget_stop" if i < 2 else status
            break
    es = [r["ac09"]["E79"] for r in rounds]
    sig = {json.dumps(r["ac09"]["rows"], sort_keys=True, default=float) for r in rounds}
    receipt = {"card": "t_724b61aa", "candidate": "r78 median_of_row_medians",
               "replay_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
               "revisions": {"r78": R78, "spec": SPEC_REV, "r72": r78["R72"], "r71": ac["R71"], "joint": ac["BASE"]},
               "fixture": {"path": str(ZIP), "sha256": ZIP_SHA, "expected_tiles": EXPECTED_TILES},
               "uv_lock_sha256": hashlib.sha256(Path("uv.lock").read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
               "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pillow": PIL.__version__},
               "status": status, "error": error, "wall_total_s": round(time.perf_counter() - t0, 3),
               "round_wall_s": [r["wall_s"] for r in rounds], "E79_per_round": es,
               "E79_median": statistics.median(es) if len(es) == 3 and None not in es else None,
               "spread": max(es) - min(es) if es and None not in es else None,
               "rows_identical_across_rounds": len(sig) == 1,
               "H79": verdict(status, rounds), "rounds": rounds}
    with (out / "receipt.json").open("x", encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, indent=1, default=float)
        fh.write("\n")
    print(json.dumps({k: receipt[k] for k in ("status", "H79", "E79_median", "spread", "round_wall_s",
                                              "rows_identical_across_rounds")}, default=float))
    return 2 if error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
