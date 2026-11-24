"""Standing #77: #72 pitch census on the customer-delivered KPP1 VPM; see docs/research/autoresearch-kpp1-vpm-pitch.md."""
import hashlib
import io
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

R72 = "e9179247c4934756170f3db7c8e2e8fe36e05487"
BASE = "01e48513aa9bba11553bc3c0c296414e7ba26c6d"
CENSUS = "docs/research/vpm-joint-pitch-r72/replay.py"
JOINT = "jobs/TEC26-OKS/scripts/joint_count.py"
SPEC = "jobs/KPP1/scripts/vpm_textures.json"
ZIP = Path("G:/Мой диск/AGR-assets/KPP1/delivered-customer-2026-11-14/SM_77_05_0009005_117_002.zip")
ZIP_SHA = "caef3a21acdb8aee1fee9e496e26bd9f9adaeef2a17272e8189bb634aee13ecf"
BOUND, HALF, LIGHT = 0.03, (0.45, 0.55), 0.01
FIRST_LIMIT, TOTAL_LIMIT = 30.0, 120.0


def git_bytes(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"])


def git_source(rev, path):
    ns = {"__name__": "pinned_research_dependency"}
    exec(compile(git_bytes(rev, path), f"{rev}:{path}", "exec"), ns)
    return ns


def bind(tile, finishes):
    flat = tile.reshape(-1, 3).astype(np.uint32)
    packed = int(np.argmax(np.bincount((flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2], minlength=1 << 24)))
    modal = [packed >> 16, (packed >> 8) & 255, packed & 255]  # A1: same argmax as np.unique(axis=0), faster
    names = sorted(k for k, v in finishes.items() if v["kind"] == "full" and v.get("rgb") == modal)
    if not names:
        return modal, names, None
    keys = {(finishes[n]["P"][0], finishes[n]["S"]) for n in names}
    if len(keys) != 1:
        raise ValueError(f"ambiguous binding {names}: {keys}")
    p, s = keys.pop()
    return modal, names, p * 4096 / s


def one_round(pitch, runs, finishes):
    data = ZIP.read_bytes()
    if hashlib.sha256(data).hexdigest() != ZIP_SHA:
        raise ValueError("fixture SHA-256 mismatch")
    zf = zipfile.ZipFile(io.BytesIO(data))
    rows = []
    for name in sorted(n for n in zf.namelist() if "_Diffuse_" in n):
        udim = int(name.rsplit(".", 2)[1])
        tile = np.asarray(Image.open(io.BytesIO(zf.read(name))).convert("RGB"))
        row = {"udim": udim, "size": tile.shape[0]}
        rows.append(row)
        if tile.shape[:2] != (4096, 4096):
            row["state"] = "not_exercised"
            continue
        modal, names, expected = bind(tile, finishes)
        row.update(modal_rgb=modal, finishes=names, expected_px=expected)
        if expected is None:
            row["state"] = "not_exercised"
            continue
        try:
            clean_obs, counts = pitch(tile, runs)
        except ValueError as exc:
            row.update(state="not_measured", reason=str(exc))
            continue
        e = abs(clean_obs / expected - 1)
        row.update(state="measured", observed_px=clean_obs, runs=counts, E=e, flagged=e > BOUND)
        cols = np.arange(4096) * 2 % 4096
        for var, img in (("half_pitch", tile[:, cols]), ("brightness_plus8", np.minimum(tile, 247) + np.uint8(8))):
            changed = int(np.count_nonzero(np.any(img != tile, axis=-1)))
            try:
                obs, c = pitch(img, runs)
                ve = abs(obs / expected - 1)
            except ValueError as exc:
                row[var] = {"state": "not_measured", "reason": str(exc), "changed_px": changed}
                continue
            ok = (HALF[0] <= ve <= HALF[1]) if var == "half_pitch" else abs(ve - e) <= LIGHT
            row[var] = {"state": "exercised" if changed else "not_exercised", "observed_px": obs, "runs": c,
                        "E": ve, "changed_px": changed, "in_bound": ok,
                        "bound_applies": var != "half_pitch" or e <= BOUND}
        if abs(pitch(tile, runs)[0] - clean_obs) > 0:
            raise ValueError("clean tile mutated")
    measured = [r for r in rows if r.get("state") == "measured"]
    return {"rows": rows, "E77": max((r["E"] for r in measured), default=None),
            "measured": len(measured), "flagged": [r["udim"] for r in measured if r["flagged"]]}


def main(out):
    out = Path(out)
    out.mkdir(parents=True)
    pitch = git_source(R72, CENSUS)["pitch"]
    runs = git_source(BASE, JOINT)["runs"]
    finishes = json.loads(git_bytes(BASE, SPEC))["finishes"]
    rounds, status, t0 = [], "complete", time.perf_counter()
    for i in range(3):
        s = time.perf_counter()
        r = one_round(pitch, runs, finishes)
        r["wall_s"] = round(time.perf_counter() - s, 3)
        rounds.append(r)
        if (i == 0 and r["wall_s"] > FIRST_LIMIT) or time.perf_counter() - t0 > TOTAL_LIMIT:
            status = "budget_stop"
            break
    total = round(time.perf_counter() - t0, 3)
    r1 = json.loads((Path(__file__).with_name("attempt-001.json")).read_text(encoding="utf-8"))["round1"]["rows"]
    keys = ("udim", "size", "modal_rgb", "finishes", "expected_px")
    a1_parity = [{k: x.get(k) for k in keys} for x in r1] == [{k: x.get(k) for k in keys} for x in rounds[0]["rows"]]
    e = [r["E77"] for r in rounds]
    sig = [json.dumps(r["rows"], sort_keys=True) for r in rounds]
    receipt = {"card": "t_e8aea693", "r72": R72, "base": BASE, "fixture": {"path": str(ZIP), "sha256": ZIP_SHA},
               "status": status, "wall_total_s": total, "round_wall_s": [r["wall_s"] for r in rounds],
               "E77_per_round": e, "E77_median": float(np.median([x for x in e if x is not None])) if any(
                   x is not None for x in e) else None,
               "spread": (max(e) - min(e)) if all(x is not None for x in e) else None,
               "a1_binding_parity_vs_r1": a1_parity,
               "rows_identical_across_rounds": len(set(sig)) == 1, "round1": rounds[0]}
    m = rounds[0]["measured"]
    if not a1_parity or status != "complete" or len(rounds) < 3 or m < 3:
        receipt["H77"] = "inconclusive"
    else:
        receipt["H77"] = "refuted" if any(r["flagged"] for r in rounds) else "confirmed"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("status", "H77", "E77_median", "spread", "round_wall_s",
                                              "rows_identical_across_rounds")}, default=float))


if __name__ == "__main__":
    main(sys.argv[1])
