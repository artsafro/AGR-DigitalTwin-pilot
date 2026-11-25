"""OBSERVE replay: native trainer scores of byte-identical staged submissions."""

import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

from tools.trainer import trainer

NAME = "deliverable.fbx"
CAP = 420


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def verified(path, digest):
    if trainer.sha256(path) != digest:
        raise ValueError(f"SHA-256 mismatch: {path}")
    return path


def preflight(m):
    # Untracked replay files may be present; all production files must match the base.
    subprocess.run(["git", "diff", "--exit-code", m["base"], "--", ".",
                    ":(exclude)docs/research/autoresearch-trainer-named-deliverable.md",
                    ":(exclude)docs/research/trainer_named_deliverable_r98",
                    ":(exclude)docs/architecture/README.md"], check=True)
    for name, digest in m["files"].items():
        verified(Path(name), digest)
    if trainer._blender() not in m["files"] or not trainer._blender().endswith("blender.exe"):
        raise ValueError("Blender executable not pinned")
    root = Path(m["r97_root"])
    verified(root / "SHA256SUMS.txt", m["r97_seal"])
    runs = {}
    for label, files in m["r97"].items():
        folder = f"g22-k2-stage1-codex-r97-{label}"
        inputs = {role: verified(root / folder / f"{folder}_built_{role}_body.fbx", digest)
                  for role, digest in files.items()}
        if set((root / folder).rglob("*.fbx")) != set(inputs.values()):
            raise ValueError(f"Unexpected fixture inventory: {folder}")
        runs[label] = inputs
    return runs


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    verified(target, trainer.sha256(source))


def evidence(rep):
    return {k: rep[k] for k in ("steps", "first_failing_step", "score", "form_p95_m", "passed", "tolerances")}


def score(e, target, work, *, calibration=False):
    elapsed = time.monotonic()
    try:
        r = evidence(trainer.score(e, target, work, allow_key=calibration))
    except trainer.TrainerError as exc:
        r = {"refusal": str(exc).replace(str(target), "<target>")}
    return {**r, "wall_s": round(time.monotonic() - elapsed, 3)}


def parity(a, b):
    return {k: v for k, v in a.items() if k != "wall_s"} == {k: v for k, v in b.items() if k != "wall_s"}


def native(r):
    return all(r.get("steps", {}).get(k, {}).get("status") == "pass" for k in ("artifact", "readback"))


def calibration_row(e, source, decoy, folder, allow_key):
    built = folder / "built"
    top = built / NAME
    copy(source, top)
    clean = score(e, built, folder / "clean", calibration=allow_key)
    nested = built / "intermediate" / NAME
    copy(decoy, nested)
    injected = score(e, built, folder / "injected", calibration=allow_key)
    selected = score(e, top, folder / "selected", calibration=allow_key)
    ok = (native(clean) and native(selected) and "several FBX" in injected.get("refusal", "")
          and trainer.sha256(top) != trainer.sha256(nested) and parity(clean, selected)
          and all(s["status"] != "error" for s in clean["steps"].values()))
    return dict(clean=clean, injected=injected, selected=selected, changed={"nested_added": 1, "root_bytes": 0}, ok=ok)


def practice_row(e, files, folder):
    baseline, candidate = folder / "B" / "built", folder / "C" / "built"
    for name, source in files.items():
        copy(source, baseline / name / "body.fbx")
        copy(source, candidate / (NAME if name == "typical" else f"{name}/body.fbx"))
    b = score(e, baseline, folder / "directory")
    c = score(e, candidate / NAME, folder / "selected")
    oracle = (b if len(files) == 1 else
              score(e, baseline / "typical" / "body.fbx", folder / "oracle"))
    intact = parity(c, oracle) and native(oracle) and all(s["status"] != "error" for s in oracle["steps"].values())
    b_expected = native(b) if len(files) == 1 else "several FBX" in b.get("refusal", "")
    return dict(B=b, C=c, oracle=oracle, parity=intact, baseline_expected=b_expected,
                changed={"path_added": 1, "path_removed": 1, "byte_changes": 0,
                         "preserved_intermediates": len(files) - 1, "injection": "not_exercised"})


def main(out):
    manifest = Path(__file__).with_name("inputs.json")
    m = json.loads(manifest.read_text(encoding="utf-8"))
    runs = preflight(m)
    bank = trainer.load_bank()
    g22 = trainer.etalon(bank, "g22-k2-stage1")
    tower = trainer.etalon(bank, "63a-stage1")
    accepted, rejected, held = map(Path, (g22["key"]["path"], g22["rejected"][0]["path"], tower["key"]["path"]))
    assert all(str(p.as_posix()) in m["files"] for p in (accepted, rejected, held))
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    rounds = []
    reason = "series_complete"
    for i in range(1, 4):
        root = out / f"R{i}"
        cal, native_rows = {}, {}
        partial = dict(calibration=cal, practice=native_rows)
        for label, etalon, source, decoy, allow in (
            ("accepted", g22, accepted, rejected, True),
            ("rejected", g22, rejected, accepted, False),
            ("heldout_63a", tower, held, rejected, True),
        ):
            if time.monotonic() - start > CAP:
                break
            cal[label] = calibration_row(etalon, source, decoy, root / label, allow)
        if len(cal) != 3:
            reason = "time_cap"
            save(out / "partial.json", partial)
            break
        ranked = all(trainer.rank_ok(cal["accepted"][arm], cal["rejected"][arm]) for arm in ("clean", "selected"))
        if not ranked or not all(row["ok"] for row in cal.values()):
            reason = "calibration_or_transfer_failed"
            save(out / "partial.json", {**partial, "ranked": ranked})
            break
        negative = root / "negative"
        top = negative / "built" / NAME
        copy(held, top.parent / "intermediate" / NAME)
        missing = score(tower, top, negative / "missing-root")
        copy(held, top)
        key = score(tower, top, negative / "copied-key")
        negative_ok = ("built result not found" in missing.get("refusal", "")
                       and "IS the key" in key["steps"]["artifact"].get("reason", "")
                       and key["steps"]["readback"]["status"] == "not_run"
                       and not list((negative / "copied-key").glob("*.readback.json")))
        for label, files in runs.items():
            if time.monotonic() - start > CAP:
                break
            native_rows[label] = practice_row(g22, files, root / label)
        if len(native_rows) != len(runs):
            reason = "time_cap"
            save(out / "partial.json", partial)
            break
        b, c = (sum(native(row[arm]) for row in native_rows.values()) for arm in ("B", "C"))
        elapsed = time.monotonic() - start
        rounds.append(dict(**partial, ranked=ranked, negatives={"missing": missing, "key": key, "ok": negative_ok},
                           B=b, C=c, delta=c-b, elapsed_s=round(elapsed, 3)))
        save(out / f"round-{i}.json", rounds[-1])
        print(f"R{i}: B={b}/3 C={c}/3 elapsed={elapsed:.1f}s", flush=True)
        if elapsed > CAP or (i == 1 and CAP - elapsed < 2 * elapsed + 20):
            reason = "time_cap" if elapsed > CAP else "pilot_budget_stop"
            break
    hypothesis = "inconclusive"
    if reason == "series_complete" and len(rounds) == 3:
        usable = all(row["negatives"]["ok"] and all(p["baseline_expected"] for p in row["practice"].values())
                     for row in rounds)
        if usable and all(row["C"] == 3 and all(p["parity"] for p in row["practice"].values()) for row in rounds):
            hypothesis = "confirmed"
        elif usable and all(row["C"] < 3 for row in rounds):
            hypothesis = "refuted"
    preflight(m)
    deltas = [row["delta"] for row in rounds]
    summary = {"hypothesis": hypothesis, "run_status": reason, "measured_rounds": len(rounds),
               "elapsed_s": round(time.monotonic() - start, 3), "manifest_sha256": trainer.sha256(manifest),
               "candidate_sha256": trainer.sha256(__file__), "paired_lifts": deltas,
               "median_lift": statistics.median(deltas) if len(deltas) == 3 else None,
               "paired_spread": [min(deltas), max(deltas)] if len(deltas) == 3 else None}
    save(out / "summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
