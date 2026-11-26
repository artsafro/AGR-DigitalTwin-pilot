"""OBSERVE #120: run unchanged native exporter with a clean and an occupied slot."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
BASE = "8a2fa635469d346009c60a922c9438e3dc20b77f"
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
BLENDER_SHA = "1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5"
PLANS = {
    "g22-k2-stage1": "5cf2bdbb51178900ef22362126fccb15df43a4637f8c23632e6f6747d1f25895",
    "63a-stage1": "6f9c6d143d18febc7033f848505859bd2f50bd611c12f1f8147d1822eb6a7d66",
}
NATIVE = ["src", "tools", "docs/trainer/etalons.json", "docs/trainer/ledger.json", "uv.lock", "pyproject.toml"]
SENTINEL = b"pre-existing unrelated file\n"
READBACK = ROOT / "tools/blender/fbx_readback.py"
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from dt_ai.core.blender_runner import blender_command  # noqa: E402
from tools.trainer.trainer import bounds_step  # type: ignore[import-not-found]  # noqa: E402


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require(condition, error):
    if not condition:
        raise ValueError(error)


def main(output):
    started = time.monotonic()
    require(output.is_relative_to(ROOT / ".venv"), "output must be inside this worktree's .venv")
    subprocess.run(["git", "diff", "--exit-code", BASE, "--", *NATIVE], cwd=ROOT, check=True)
    bank = json.loads((ROOT / "docs/trainer/etalons.json").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in bank["etalons"] if e["id"] in PLANS}
    inputs = {BLENDER: BLENDER_SHA}
    plans = {i: Path(f"C:/x/trainer/runs/{i}-codex-r111-1/built/plan.json") for i in PLANS}
    inputs.update({p: PLANS[i] for i, p in plans.items()})
    for e in entries.values():
        for v in [e["key"], *e["rejected"]]:
            inputs[Path(v["path"])] = v["sha256"]
    for path, digest in inputs.items():
        require(sha(path) == digest, f"preflight mismatch: {path}")
    output.mkdir(parents=False)
    temp = output / "temp"
    temp.mkdir()
    env = {**os.environ, **dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(temp))}
    result = {"base": BASE, "input_sha256": {p.as_posix(): h for p, h in inputs.items()},
              "rounds": [], "malformed": {}, "labels": {}, "status": "inconclusive"}

    def run(command, log):
        remaining = 180 - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("series wall budget exhausted")
        with log.open("xb") as f:
            return subprocess.run(command, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT,
                                  timeout=min(remaining, 25)).returncode

    def build(plan, out, log):
        return run([sys.executable, "-m", "dt_ai.cli.agr", "body", "--blender", str(BLENDER),
                    str(plan), str(out)], log)

    def native(fbx, dest):
        rc = run(blender_command(READBACK, [fbx, dest], executable=BLENDER), dest.with_suffix(".readback.log"))
        require(rc == 0 and dest.is_file(), f"readback failed: {fbx}, exit={rc}")
        report = json.loads(dest.read_text(encoding="utf-8"))
        meshes = report["meshes"]
        require(meshes and all(m["vertices"] > 0 and m["polygons"] > 0 for m in meshes), f"empty readback: {fbx}")
        return report

    def inspect(out, row, name, key_sha):
        fbx = out / "body.fbx"
        with fbx.open("rb") as f:
            require(f.read(23).startswith(b"Kaydara FBX Binary"), f"not a binary FBX: {fbx}")
        digest = sha(fbx)
        require(digest != key_sha, f"FBX is the key: {fbx}")
        report = native(fbx, row / f"{name}.json")
        meshes = report["meshes"]
        return {"fbx_sha256": digest, "mesh_sha256": json_sha(meshes),
                "polygons": sum(m["polygons"] for m in meshes),
                "vertices": sum(m["vertices"] for m in meshes),
                "bounds_m": [m["bounds_m"] for m in meshes]}

    try:
        for idx in range(3):
            t0 = time.monotonic()
            trial: dict[str, object] = {}
            rows = {}
            trial["rows"] = rows
            result["rounds"].append(trial)
            for label, plan in plans.items():
                d = output / f"round-{idx+1}-{label}"
                occupied = d / "occupied"
                occupied.mkdir(parents=True)
                sentinel = occupied / "original.txt"
                sentinel.write_bytes(SENTINEL)
                entry = {}
                rows[label] = entry
                entry["baseline_exit"] = build(plan, occupied, d / "baseline.log")
                entry["baseline_changed_existing"] = int(sentinel.read_bytes() != SENTINEL)
                entry["baseline_paths"] = sorted(p.name for p in occupied.iterdir())
                require(entry["baseline_exit"] != 0 and entry["baseline_paths"] == [sentinel.name]
                        and entry["baseline_changed_existing"] == 0
                        and "OUT_DIR exists" in (d / "baseline.log").read_text(encoding="utf-8", errors="replace"),
                        f"occupied-slot witness failed: {d}")
                clean, child = d / "clean", occupied / "stage1"
                for name, out in [("clean", clean), ("candidate", child)]:
                    entry[f"{name}_exit"] = build(plan, out, d / f"{name}.log")
                    require(entry[f"{name}_exit"] == 0, f"export failed: {out}")
                    entry[name] = inspect(out, d, name, entries[label]["key"]["sha256"])
                entry["candidate_changed_existing"] = int(sentinel.read_bytes() != SENTINEL)
                entry["candidate_paths"] = sorted(p.name for p in occupied.iterdir())
                clean_files = sorted(p.name for p in clean.iterdir())
                child_files = sorted(p.name for p in child.iterdir())
                require(entry["candidate_changed_existing"] == 0 and entry["candidate_paths"] == [sentinel.name, child.name]
                        and clean_files == child_files == ["body.blend", "body.fbx", "build.json", "module.blend"]
                        and entry["clean"]["mesh_sha256"] == entry["candidate"]["mesh_sha256"], f"parity failed: {d}")
                entry["clean_created_files"] = len(clean_files)
                entry["candidate_created_files"] = len(child_files)
            round_wall = round(time.monotonic() - t0, 3)
            trial.update(B=0, C=len(rows), paired_delta=len(rows), wall_s=round_wall)
            if idx == 0:
                projected = time.monotonic() - started + 2 * round_wall + 30
                result["projected_series_s"] = round(projected, 3)
                if projected > 180:
                    raise TimeoutError("frozen first-round projection exceeds budget")
        for label, plan in plans.items():
            path = output / f"{label}-floors-zero.json"
            original = json.loads(plan.read_text(encoding="utf-8"))
            modified = {**original, "floors": 0}
            changed = [k for k in original if original[k] != modified[k]]
            path.write_text(json.dumps(modified), encoding="utf-8")
            out = output / f"{label}-invalid"
            log = output / f"{label}-invalid.log"
            rc = build(path, out, log)
            result["malformed"][label] = {"exit": rc, "changed_fields": changed, "created_dir": out.exists(),
                                           "variant_sha256": sha(path)}
            require(changed == ["floors"] and rc != 0 and not out.exists()
                    and "floors must" in log.read_text(encoding="utf-8", errors="replace"), f"malformed accepted: {label}")
        for label, e in entries.items():
            reports = {}
            for tag, variant in [("accepted", e["key"]), *[("rejected-" + v["version"], v) for v in e["rejected"]]]:
                d = output / f"label-{label}-{tag}"
                d.mkdir()
                copied = d / "input.fbx"
                shutil.copyfile(variant["path"], copied)
                require(sha(copied) == variant["sha256"], f"copied label bytes changed: {label}/{tag}")
                reports[tag] = native(copied, d / "readback.json")
            result["labels"][label] = {tag: {"native_import": True, "bounds_vs_key": bounds_step(rb, reports["accepted"])}
                                       for tag, rb in reports.items()}
            for i, trial in enumerate(result["rounds"], 1):
                rb = json.loads((output / f"round-{i}-{label}" / "candidate.json").read_text(encoding="utf-8"))
                trial["rows"][label]["candidate_bounds_vs_key"] = bounds_step(rb, reports["accepted"])
        result["input_changes"] = [p.as_posix() for p, h in inputs.items() if sha(p) != h]
        require(not result["input_changes"], "read-only input changed")
        deltas = [r["paired_delta"] for r in result["rounds"]]
        result.update(status="confirmed", median=statistics.median(deltas), spread=[min(deltas), max(deltas)])
    except (OSError, TimeoutError, ValueError, subprocess.TimeoutExpired) as exc:
        result["diagnostic"] = str(exc)
    finally:
        result["wall_s"] = round(time.monotonic() - started, 3)
        (output / "receipt.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in ("status", "median", "spread", "diagnostic", "wall_s")}))
    return 0 if result["status"] == "confirmed" else 2


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
