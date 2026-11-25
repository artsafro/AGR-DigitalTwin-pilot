"""Refresh artifact coverage for fixed trainer outputs, without writing the ledger."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from tools.trainer import trainer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAP = 480
IDS = ("kpp1-v004", "g22-k2-stage1", "63a-stage1")
HELD = "63b-stage1"


def digest(p):
    with Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}


def preflight(m):
    tracked = subprocess.check_output(["git", "diff", "--name-only", m["base"], "--", "tools", "src", "docs/trainer", "uv.lock"], cwd=ROOT)
    if tracked:
        raise ValueError(f"Scoring dependency drift: {tracked!r}")
    for path, sha in m["files"].items():
        if digest(path) != sha:
            raise ValueError(f"Input hash changed: {path}")
    for path, files in m["historical"].items():
        if not Path(path).is_dir() or inventory(Path(path)) != files:
            raise ValueError(f"Historical built inventory drift: {path}")


def save(path, obj):
    path.write_bytes((json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode())


def worker(eid, built, out, mode):
    if mode == "header":
        new = out.with_suffix(".fbx")
        with Path(built).open("rb") as f:
            header = f.read(23)
        with new.open("xb") as f:
            f.write(header)
        built = new
    if mode == "copy":
        new = out.with_suffix(".fbx")
        with new.open("xb") as f:
            f.write(Path(built).read_bytes())
        built = new
    e = trainer.etalon(trainer.load_bank(), eid)
    rep = trainer.score(e, built, out.with_suffix(""), allow_key=(mode == "accepted"))
    save(out, {k: rep[k] for k in ("steps", "score", "first_failing_step")})


def native(r):
    return all(r["steps"][k]["status"] == "pass" for k in ("artifact", "readback"))


def main(out):
    m = json.loads((HERE / "inputs.json").read_bytes())
    preflight(m)
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    rows = {"pairs": [], "controls": {}, "status": "started"}
    report = out / "receipt.json"
    env = dict(os.environ, TWINQA_BLENDER=m["blender"])

    def elapsed():
        return time.monotonic() - start

    def score(eid, path, label, mode="normal"):
        remaining = CAP - elapsed()
        if remaining < 20:
            raise TimeoutError(f"No launch budget for {label}")
        target = out / f"{label}.json"
        cmd = [sys.executable, "-m", __spec__.name, "--score", eid, path, str(target), mode]
        begin = time.monotonic()
        with (out / f"{label}.log").open("xb") as log:
            subprocess.run(cmd, check=True, env=env, stdout=log, stderr=subprocess.STDOUT,
                           timeout=min(90, remaining), cwd=ROOT)
        result = json.loads(target.read_bytes())
        result["wall_s"] = round(time.monotonic() - begin, 3)
        return result

    try:
        for label, path, mode in (
            ("accepted", m["accepted"], "accepted"), ("rejected", m["rejected"], "normal"),
            ("accepted-header", m["accepted"], "header"), ("rejected-header", m["rejected"], "header"),
            ("key-submission", m["accepted"], "copy"),
        ):
            rows["controls"][label] = score(HELD, path, label, mode)
            save(report, rows)
        ctl = rows["controls"]
        state = lambda label, step: ctl[label]["steps"][step]["status"]
        rows["calibration_ok"] = (
            all(native(ctl[k]) for k in ("accepted", "rejected"))
            and ctl["accepted"]["score"] > ctl["rejected"]["score"]
            and state("accepted", "bounds") == "pass" and state("rejected", "bounds") == "fail"
            and all(state(k, "artifact") == "pass" and state(k, "readback") == "fail"
                    for k in ("accepted-header", "rejected-header"))
            and state("key-submission", "artifact") == "fail" and state("key-submission", "readback") == "not_run"
        )
        if not rows["calibration_ok"]:
            raise ValueError("Label or admission control disagrees")
        for i in range(3):
            if i and elapsed() + (3 - i) * rows["pairs"][0]["wall_s"] + 30 > CAP:
                raise TimeoutError("Pilot estimates remaining pairs exceed frozen budget")
            begin = time.monotonic()
            pair = {"baseline": {}, "candidate": {}, "held_out": {}, "complete": False}
            rows["pairs"].append(pair)
            for eid in IDS:
                pair["baseline"][eid] = score(eid, m["baseline"][eid], f"{i+1}-{eid}-baseline")
                save(report, rows)
                pair["candidate"][eid] = score(eid, m["candidate"][eid][i], f"{i+1}-{eid}-recovered")
                save(report, rows)
            pair["held_out"] = score(HELD, m["candidate"][HELD][i], f"{i+1}-{HELD}-recovered")
            pair["wall_s"] = round(time.monotonic() - begin, 3)
            pair["complete"] = True
            pair["lift"] = sum(map(native, pair["candidate"].values())) - sum(map(native, pair["baseline"].values()))
            save(report, rows)
        preflight(m)
        if elapsed() > CAP:
            raise TimeoutError("Postflight exceeded series budget")
        rows["input_parity"] = True
        rows["status"] = "finished"
        lifts = [p["lift"] for p in rows["pairs"]]
        rows["paired_lift"] = {"median": statistics.median(lifts), "min": min(lifts), "max": max(lifts)}
        calibrated = all(all(r["steps"]["artifact"].get("reason") == "no FBX in the built result"
                             for r in p["baseline"].values()) for p in rows["pairs"])
        errors = any(r["steps"]["readback"]["status"] == "error" or
                     (r["steps"]["artifact"]["status"] == "pass" and not native(r))
                     for p in rows["pairs"] for r in (*p["candidate"].values(), p["held_out"]))
        rows["hypothesis"] = ("inconclusive" if errors or not calibrated else "confirmed" if lifts == [3, 3, 3]
                              and all(native(p["held_out"]) for p in rows["pairs"]) else "refuted")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        rows.update(status="budget-stop" if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)) else "incomplete",
                    hypothesis="inconclusive", error=str(exc))
    rows["wall_s"] = round(elapsed(), 3)
    rows["inputs_sha256"] = digest(HERE / "inputs.json")
    save(report, rows)
    print(json.dumps({k: v for k, v in rows.items() if k not in ("pairs", "controls")}, ensure_ascii=False))
    return 0 if rows["status"] == "finished" else 2


if __name__ == "__main__":
    if sys.argv[1] == "--score":
        _, _, eid, built, out, mode = sys.argv
        worker(eid, built, Path(out), mode)
    else:
        sys.exit(main(Path(sys.argv[1]).resolve()))
