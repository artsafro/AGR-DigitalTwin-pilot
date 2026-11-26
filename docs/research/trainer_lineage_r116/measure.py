"""Run C/D against the pinned #114 native trees and synthetic labels, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import tempfile
import time
from typing import Any

PRIOR = "b39ad091504e2524bd711049733287209cd676b5:docs/research/trainer_lineage_r114/measure.py"
PRIOR_SHA = "c37f01bafe5568ad071b24c20d268d35391271f42e9798bed035bbce6de922ec"
BRANCH_WITNESS = "docs/research/autoresearch-trainer-gate1.md"
BANK_REF = re.compile(
    r"(?<![\w./-])(?:origin/|refs/heads/|refs/remotes/origin/)?"
    r"research/issue-1855-trainer-v0(?![\w./-])"
)
ADDED = {
    "bare_ref": ("git show research/issue-1855-trainer-v0:docs/trainer/ledger.json", True),
    "remote_ref": ("`ORIGIN/RESEARCH/ISSUE-1855-TRAINER-V0`", True),
    "full_head": ('"refs/heads/research/issue-1855-trainer-v0"', True),
    "full_remote": (" refs/remotes/origin/research/issue-1855-trainer-v0 ", True),
    "branch_suffix": ("origin/research/issue-1855-trainer-v0-notes", False),
    "path_past_ref": ("origin/research/issue-1855-trainer-v0/notes", False),
    "alien_prefix": ("backup-origin/research/issue-1855-trainer-v0", False),
    "other_namespace": ("other/issue-1855-trainer-v0", False),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def prior() -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[3]
    raw = subprocess.check_output(["git", "-C", str(repo), "show", PRIOR])
    if digest(raw) != PRIOR_SHA:
        raise ValueError("#114 replay blob differs from frozen hash")
    scope: dict[str, Any] = {"__file__": str(Path(__file__).resolve()), "__name__": "frozen_r114"}
    exec(compile(raw, str(Path(__file__).resolve()), "exec"), scope)
    return scope


def classify(tree, old, *, legacy=False):
    b, c = old["compare"](tree)
    # An exact branch hit necessarily contains a B substring. Read only its residual set.
    ref_hits = set() if legacy else {
        name for name in b - c
        if BANK_REF.search((tree / name).read_bytes().decode("utf-8", errors="replace").lower())
    }
    return {"B": b, "C": c, "D": c | ref_hits}


def injected(tree, old, *, legacy=False):
    cases = old["CASES"] | ADDED
    tree.mkdir()
    for name, (text, _) in cases.items():
        (tree / name).write_bytes(text.encode("utf-8"))
    hits = classify(tree, old, legacy=legacy)
    truth = {name for name, (_, label) in cases.items() if label}
    old_truth = truth - set(ADDED)
    controls = {name: {"expected": name in truth, **{arm: name in found for arm, found in hits.items()},
                       "changed_C_to_D": int((name in hits["C"]) != (name in hits["D"])),
                       "D_trigger": "exercised" if name in hits["D"] else "not_exercised"}
                for name in cases}
    errors = {arm: len(found ^ truth) for arm, found in hits.items()}
    correct = hits == {"B": set(cases), "C": old_truth, "D": truth}
    return {"controls": controls, "M116": errors, "injected_expected": correct}


def pair(etalon, out, old):
    with tempfile.TemporaryDirectory(dir=out) as temp:
        tree = Path(temp) / "tree"
        tree.mkdir()
        old["archive"](tree)
        removed = old["trainer"].scrub_worktree(tree, etalon)
        stock_survives = (tree / old["WITNESS"]).is_file()
        hits = classify(tree, old)
        controls = injected(tree / "__r116_synthetic__", old)
    b, c, d = (hits[arm] for arm in ("B", "C", "D"))
    critical = sorted(p for p in b | c | d if p.startswith(old["CRITICAL"])
                      or p in {"AGENTS.md", "CLAUDE.md", "GEMINI.md"})
    tuning = etalon["id"] == "63a-stage1"
    expected_c = b - {BRANCH_WITNESS} if tuning else b
    parity = (b == d and c == expected_c and len(b) == (5 if tuning else 2)
              and (BRANCH_WITNESS in b) == tuning and old["WITNESS"] in b & c & d
              and stock_survives and not critical)
    return {"etalon": etalon["id"], "split": etalon["split"], "practice_ready": etalon["practice_ready"],
            "native": {**{arm: sorted(found) for arm, found in hits.items()}, "stock_removed": len(removed),
                       "stock_witness_survives": stock_survives, "route_critical": critical,
                       "changed_B_to_C": len(b ^ c), "changed_B_to_D": len(b ^ d),
                       "changed_C_to_D": len(c ^ d), "changed_paths_C_to_D": sorted(c ^ d),
                       "native_branch_witness": "exercised" if BRANCH_WITNESS in d else "not_exercised",
                       "parity": parity},
            **controls, "all_expected": parity and controls["injected_expected"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--legacy-control", action="store_true", help="use C as D; expect regression failure")
    args = parser.parse_args()
    old = prior()
    args.out.mkdir(parents=True, exist_ok=False)
    if args.legacy_control:
        result = injected(args.out / "controls", old, legacy=True)
        print(json.dumps(result["M116"]))
        print("Missed branch witnesses:", ", ".join(n for n, row in result["controls"].items()
                                                     if row["expected"] and not row["D"]))
        return int(not result["injected_expected"])

    head, git = old["HEAD"], old["git"]
    archive_trainer = git("show", f"{head}:tools/trainer/trainer.py")
    if Path(old["trainer"].__file__).read_bytes() != archive_trainer:
        raise ValueError("loaded trainer differs from frozen Git blob")
    bank = git("show", f"{head}:docs/trainer/etalons.json")
    ledger = git("show", f"{head}:docs/trainer/ledger.json")
    etalons = {e["id"]: e for e in json.loads(bank)["etalons"]}
    report = {"fixture_head": head, "fixture_tree": git("rev-parse", f"{head}^{{tree}}").decode().strip(),
              "inputs": {"r114_harness": PRIOR_SHA, "trainer": digest(archive_trainer), "bank": digest(bank),
                         "ledger": digest(ledger), "r116_harness": digest(Path(__file__).read_bytes())},
              "pairs": [], "run_status": "finished", "hypothesis": "inconclusive",
              "not_measured": ["live escapes", "artifact passage", "accepted/rejected FBX quality"]}
    start = time.monotonic()
    for i, name in enumerate(old["ETALONS"] * 3):
        if time.monotonic() - start >= 360:
            report["run_status"] = "budget_stop"
            break
        pair_start = time.monotonic()
        item = pair(etalons[name], args.out, old)
        item["wall_s"] = round(time.monotonic() - pair_start, 3)
        report["pairs"].append(item)
        print(name, item["M116"], item["all_expected"], item["wall_s"], flush=True)
        if i == 0:
            report["projected_total_s"] = round(time.monotonic() - start + 6 * item["wall_s"], 3)
            if report["projected_total_s"] > 360:
                report["run_status"] = "budget_stop"
                break
    report["wall_s"] = round(time.monotonic() - start, 3)
    if report["wall_s"] >= 360:
        report["run_status"] = "budget_stop"
    if report["run_status"] == "finished" and len(report["pairs"]) == 6:
        report["hypothesis"] = "confirmed" if all(p["all_expected"] for p in report["pairs"]) else "refuted"
        report["stats"] = {}
        for name in old["ETALONS"]:
            metrics = [p["M116"] for p in report["pairs"] if p["etalon"] == name]
            report["stats"][name] = {"median": {arm: statistics.median(m[arm] for m in metrics)
                                                for arm in ("B", "C", "D")},
                                     "paired_gain_range": {arm: [min(delta), max(delta)] for arm in ("B", "C")
                                                           for delta in [[m[arm] - m["D"] for m in metrics]]}}
    (args.out / "receipt.json").write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    return 0 if report["run_status"] == "finished" else 3


if __name__ == "__main__":
    raise SystemExit(main())
