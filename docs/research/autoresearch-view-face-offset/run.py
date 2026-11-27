"""Replay three fresh #141 pairs; only the same-face veto differs from R2."""

from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import shutil
from statistics import median
import subprocess
import sys
from time import monotonic
from types import SimpleNamespace

import numpy as np

from offset import match, veto

REV = "3716f5395667c17f8be8737313952aaa6285615c"
UPSTREAM = "docs/research/autoresearch-view-face-raster"


def blob(name):
    return subprocess.check_output(["git", "show", f"{REV}:{UPSTREAM}/{name}"])


def pair(out):
    out.mkdir(parents=True)
    upstream = out / "upstream"
    upstream.mkdir()
    for name in ("run.py", "rays_win.py", "sheet.py", "score.py", "fixture.json"):
        (upstream / name).write_bytes(blob(name))
    baseline = runpy.run_path(str(upstream / "run.py"))
    live = baseline["main"].__globals__
    fx, sha = baseline["FIX"], baseline["sha"]
    hashes = baseline["preflight"]()
    blender = fx["blender"]
    if sha(blender["path"]) != blender["sha256"]:
        raise RuntimeError("Blender SHA-256 mismatch")
    model = out / "input.blend"
    shutil.copyfile(fx["inputs"]["model"]["path"], model)
    if sha(model) != hashes["model"]:
        raise RuntimeError("Staged model SHA-256 mismatch")
    temp = out / "temp"
    temp.mkdir()

    def launch(cmd, **kw):
        cmd = [cmd[0], "--background", "--factory-startup", "--disable-autoexec", "--threads", "1",
               "--python-exit-code", "1", str(model), *cmd[4:]]
        env = dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
        return subprocess.run(cmd, **(kw | {"timeout": 90, "env": env}))

    decisions, reflection_delta = [], {}
    sheet, score = baseline["sheet"], baseline["score"]
    original_read = sheet.read_sheet

    def track_sheet(pdf, index, clip, max_run):
        result = original_read(pdf, index, clip, max_run)
        labels = next(page["views"] for page in fx["pages"] if page["index"] == index)
        for view, label in zip(result["views"], labels, strict=True):
            flipped, _ = sheet.view_profile(view["crop"][:, ::-1], max_run)
            reflection_delta[label["id"]] = int(np.count_nonzero(view["profile"] != flipped))
        return result

    def judge(profile, width_m, faces, gt):
        original = baseline["judge"](profile, width_m, faces, gt)
        a = original["C"]
        az = a["answer"]
        b = {"answer": az, "outcome": a["outcome"], "reason": "baseline_abstain"}
        if az is not None:
            curve = match(profile, faces[az]["profile"], score.smooth, score.ncc, score.SLACK_PX)
            flag, offset, peak, other_offset, other = veto(curve)
            if (offset, round(peak, 4)) != (a["offset_px"][str(az)], a["scores"][str(az)]):
                raise RuntimeError("Winning NCC/offset parity failed")
            b.update(reason="repeated_offset" if flag else "baseline_retained", offset_px=offset,
                     score=peak, second_offset_px=other_offset, second_score=other)
            if flag:
                b.update(answer=None, outcome="abstain")
        decisions.append(b)
        return original

    live.update(subprocess=SimpleNamespace(run=launch), judge=judge)
    sheet.read_sheet = track_sheet
    sys.argv = [str(upstream / "run.py"), str(out / "A"), "R2"]
    baseline["main"]()
    native = json.loads((out / "A/result.json").read_bytes())
    oracle = json.loads(blob("receipt.json"))["R2"]["cases"]
    if len(oracle) != 44 or native["cases"] != oracle:
        raise RuntimeError("Historical R2 case parity failed")
    if (baseline["preflight"]() != hashes or sha(model) != hashes["model"]
            or sha(blender["path"]) != blender["sha256"]):
        raise RuntimeError("Input postflight mismatch")

    recorded = iter(decisions)
    for row in native["cases"]:
        b = next(recorded) if "C" in row else {"outcome": "not_exercised"}
        if row["kind"] == "mirror":
            row["changed_profile_coordinates"] = reflection_delta[row["view"]]
            if not row["changed_profile_coordinates"]:
                b = {"outcome": "not_exercised"}
        row["B"] = b
    if next(recorded, None) is not None:
        raise RuntimeError("Candidate verdict count mismatch")

    summary = {}
    for side in ("long", "short"):
        for kind in ("full", "crop", "mirror"):
            rows = [r for r in native["cases"] if r["view"] in fx[f"{side}_views"] and r["kind"] == kind]
            summary[f"{side}/{kind}"] = {
                arm: dict(Counter(r.get(key, {}).get("outcome", "not_exercised") for r in rows))
                for arm, key in (("A", "C"), ("B", "B"))
            }
    (out / "pair.json").write_bytes(json.dumps({"cases": native["cases"], "summary": summary,
        "hashes": hashes | {"blender": blender["sha256"]}, "parity_cases": 44}, ensure_ascii=False).encode("utf-8"))


def series(out):
    start = monotonic()
    out.mkdir(parents=True, exist_ok=False)
    proof, timings = [], []
    status = "finished"
    for i in range(1, 4):
        tick = monotonic()
        child = out / f"pair-{i}"
        with (out / f"pair-{i}.log").open("xb") as log:
            try:
                subprocess.run([sys.executable, str(Path(__file__).resolve()), str(child), "--pair"],
                               check=True, stdout=log, stderr=subprocess.STDOUT, timeout=120)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                raise RuntimeError(f"Pair {i} failed; read {log.name}") from error
        payload = (child / "pair.json").read_bytes()
        proof.append(sha256(payload).hexdigest())
        elapsed = monotonic() - tick
        timings.append(round(elapsed, 3))
        print(f"Pair {i}: 44/44 baseline parity; {elapsed:.3f} s", flush=True)
        if (i == 1 and monotonic() - start + 4 * elapsed > 240) or monotonic() - start > 240:
            status = "budget_stop"
            break
    if status == "finished" and len(set(proof)) != 1:
        status = "nonidentical_repeats"
    result = json.loads((out / f"pair-{len(proof)}" / "pair.json").read_bytes())
    summary = result["summary"]
    safe = all(not row["B"].get("wrong", 0) for name, row in summary.items() if not name.endswith("/mirror"))
    pass_gate = safe and summary["long/full"]["B"].get("correct", 0) == 2 and summary["long/crop"]["B"].get("correct", 0) >= 7
    result.update(status=status, hypothesis=("confirmed" if pass_gate else "refuted") if status == "finished" else "inconclusive",
                  baseline_revision=REV, measured_head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  pair_sha256=proof, times_s=timings, median_pair_s=median(timings), wall_s=round(monotonic() - start, 3))
    (out / "receipt.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("status", "hypothesis", "summary", "wall_s")}))


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve()
    (pair if sys.argv[2:] == ["--pair"] else series)(target)
