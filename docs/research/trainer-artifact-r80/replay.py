"""Read-only, source-only trainer preflight probe; never calls the live trainer."""

import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
TRAINER = "21604729f3b2c1bda5c057f061040b6e21bacf17"
BASE = "c20ef4efd0afe0a60f3507088f46f7fc84a2b89c"
EVIDENCE = Path("G:/Мой диск/AGR-evidence")
SEALS = {
    "1855-trainer-v0": "fd5c925d7188ab279fe97ae4f2e087899f739bd63ffb6dd9743e6ad9d13a3984",
    "1608-kpp1-cold": "2315c0fb373386872ff1626327bc5d4d5b25636fb19af06b81e4973e294a354c",
}


def blob(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sealed_members(folder, members):
    base = EVIDENCE / folder
    manifest = (base / "SHA256SUMS.txt").read_bytes()
    require(digest(manifest) == SEALS[folder], f"manifest mismatch: {folder}")
    entries = {}
    for line in manifest.decode("utf-8").splitlines():
        sha, name = line.split(maxsplit=1)
        entries[name.removeprefix("*").removeprefix("./")] = sha
    result = {}
    for member in members:
        raw = (base / member).read_bytes()
        require(digest(raw) == entries.get(member), f"evidence mismatch: {member}")
        result[member] = raw
    return result


def source_control(path, expected):
    with path.open("rb") as stream:
        first = stream.read(1)
        require(bool(first), "empty source")
        original = hashlib.sha256(first)
        changed = hashlib.sha256(bytes([first[0] ^ 1]))
        for chunk in iter(lambda: stream.read(1048576), b""):
            original.update(chunk)
            changed.update(chunk)
    require(original.hexdigest() == expected, "live source does not match the bank")
    require(changed.hexdigest() != expected, "one-byte mutation not detected")
    return {"source_bytes": path.stat().st_size, "source_sha256": expected,
            "source_changed_bytes_in_stream": 1, "mutant_sha256": changed.hexdigest()}


def paired_round(script, bank_file, work, i, limit):
    started = time.monotonic()
    states = {}
    for tower, expected_rc in (("63a-stage1", 0), ("63b-stage1", 2)):
        out = work / f"{tower}-{i}"
        run = subprocess.run(
            [sys.executable, str(script), "--bank", str(bank_file), "run", tower,
             "--lane", "codex", "--out", str(out), "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"},
            timeout=max(0.01, limit - time.monotonic()), check=False,
        )
        require(run.returncode == expected_rc and not out.exists(),
                f"unexpected dry-run outcome for {tower}: exit {run.returncode}")
        if expected_rc:
            require("not practice_ready" in run.stderr and not run.stdout, "wrong held-out refusal")
        else:
            require(bool(run.stdout.strip()), "no prompt emitted on the positive control")
        states[tower] = {"exit": run.returncode, "eligible": int(run.returncode == 0),
                         "output_directory_written": False,
                         "reason": "not practice_ready" if expected_rc else "prompt emitted"}
    return states, time.monotonic() - started


def main():
    lock = subprocess.check_output(["git", "hash-object", "--path=uv.lock", "uv.lock"], cwd=ROOT).strip()
    base_lock = subprocess.check_output(["git", "rev-parse", f"{BASE}:uv.lock"], cwd=ROOT).strip()
    require(lock == base_lock, "uv.lock differs from the frozen base")
    trainer = blob(TRAINER, "tools/trainer/trainer.py")
    bank_bytes = blob(TRAINER, "docs/trainer/etalons.json")
    bank = {e["id"]: e for e in json.loads(bank_bytes)["etalons"]}
    ledger = json.loads(blob(TRAINER, "docs/trainer/ledger.json"))["rows"]
    reports = {"kpp1-v004": "RUN-STATE.md", "g22-k2-stage1": "REPORT.md", "63a-stage1": "REPORT.md"}
    members = [f"{row['etalon']}/score.json" for row in ledger]
    members.extend(f"{etalon}/{name}" for etalon, name in reports.items())
    scores = sealed_members("1855-trainer-v0", members)
    metrics = json.loads(sealed_members("1608-kpp1-cold", ["metrics.json"])["metrics.json"])
    observed = {}
    for row in ledger:
        score = json.loads(scores[f"{row['etalon']}/score.json"])
        require(score["first_failing_step"] == row["first_failing_step"] == "artifact"
                and not score["passed"] and score["score"] == row["score"] == 0,
                f"score/ledger disagreement: {row['etalon']}")
        report = scores[f"{row['etalon']}/{reports[row['etalon']]}"]
        require(b"Gate 1" in report and b"PartsList" in report, f"missing report attribution: {row['etalon']}")
        observed[row["etalon"]] = {**score["steps"]["artifact"], "gate1_report_sha256": digest(report)}
    skeleton_stop = metrics["first_failing_stage"]
    require(skeleton_stop == "sources-dwg", "unexpected #1608 skeleton stop")

    source = bank["63b-stage1"]["sources"][0]
    require(source == bank["63a-stage1"]["sources"][0]
            and bank["63b-stage1"]["split"] == "held_out", "fixture drift")
    rounds = []
    (ROOT / "tmp").mkdir(exist_ok=True)
    with TemporaryDirectory(dir=ROOT / "tmp", prefix="r80-") as temporary:
        work = Path(temporary)
        script, bank_file = work / "trainer.py", work / "bank.json"
        script.write_bytes(trainer)
        bank_file.write_bytes(bank_bytes)
        limit = time.monotonic() + 120
        for i in range(1, 4):
            started = time.monotonic()
            preflight = source_control(Path(source["path"]), source["sha256"])
            states, dry_s = paired_round(script, bank_file, work, i, limit)
            elapsed = time.monotonic() - started
            require(time.monotonic() <= limit, "budget stop: 120 seconds")
            rounds.append({"round": i, "source_preflight": preflight, "dry_run": states,
                           "delta": states["63b-stage1"]["eligible"] - states["63a-stage1"]["eligible"],
                           "wall_s": round(elapsed, 3), "paired_dry_run_wall_s": round(dry_s, 3)})
    ds = [r["delta"] for r in rounds]
    walls = [r["wall_s"] for r in rounds]
    print(json.dumps({"run_status": "complete_preflight_only", "hypothesis": "inconclusive",
                      "measured_artifact_attempts": 0, "ledger_artifact": observed,
                      "1608_skeleton_stop": skeleton_stop, "rounds": rounds,
                      "median_delta": statistics.median(ds), "delta_min_max": [min(ds), max(ds)],
                      "median_wall_s": statistics.median(walls), "wall_s_min_max": [min(walls), max(walls)],
                      "python": sys.version.split()[0]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        sys.exit(f"not measured: {exc}")
