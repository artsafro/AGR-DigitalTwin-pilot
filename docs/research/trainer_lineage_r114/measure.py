"""Replay the frozen #114 static OBSERVE comparison; no agent or model is opened."""
import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.trainer import trainer  # noqa: E402

HEAD = "55b885c1b9ccdbe53df2c0d6ade9d4e5bd8ca364"
TOKENS = ("1619-body-training", "1855-trainer-v0")
ETALONS = ("63a-stage1", "63b-stage1")
WITNESS = "docs/research/body-training-1619/README.md"
CRITICAL = ("docs/agents/", "docs/domain/", "docs/procedure/", "routes/", ".agents/skills/", "tools/",
            "src/", "schemas/", "standards/")
CASES = {
    "exact_slash": ("AGR-evidence/1619-body-training/tower-A/v005", True),
    "exact_quoted_backslash": ('"G:\\AGR-evidence\\1619-BODY-TRAINING"', True),
    "exact_json": (json.dumps({"path": r"G:\AGR-evidence\1855-trainer-v0\bank"}), True),
    "sibling_dash": ("AGR-evidence/1619-body-training-notes/", False),
    "sibling_underscore": ("AGR-evidence/1855-trainer-v0_notes/", False),
    "sibling_prefix": ("AGR-evidence/copy-1619-body-training/", False),
    "sibling_dot": ("AGR-evidence/1855-trainer-v0.backup/", False),
}
PATTERN = re.compile(r"(?<![\w.-])(?:" + "|".join(map(re.escape, TOKENS)) + r")(?![\w.-])")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def component_hits(tree):
    return {
        f.relative_to(tree).as_posix()
        for f in tree.rglob("*")
        if ".git" not in f.relative_to(tree).parts and f.is_file() and not f.is_symlink()
        and PATTERN.search(f.read_bytes().decode("utf-8", errors="replace").lower())
    }


def compare(tree):
    b = set(trainer.leaking_files(tree, TOKENS))
    c = component_hits(tree)
    return b, c


def archive(tree):
    with subprocess.Popen(["git", "-C", str(ROOT), "archive", HEAD], stdout=subprocess.PIPE) as proc:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as data:
            data.extractall(tree, filter="data")
        if proc.wait() != 0:
            raise RuntimeError("git archive failed")


def pair(etalon, out):
    with tempfile.TemporaryDirectory(dir=out) as temp:
        tree = Path(temp) / "tree"
        tree.mkdir()
        archive(tree)
        native_removed = trainer.scrub_worktree(tree, etalon)
        stock_survives = (tree / WITNESS).is_file()
        b, c = compare(tree)
        critical = sorted(f for f in b | c if f in {"AGENTS.md", "CLAUDE.md", "GEMINI.md"} or f.startswith(CRITICAL))
        injected = tree / "__r114_synthetic__"
        injected.mkdir()
        for name, (value, _) in CASES.items():
            (injected / name).write_bytes(value.encode("utf-8"))
        ib, ic = compare(injected)
    controls = {name: {"label": label, "B": name in ib, "C": name in ic,
                       "changed_B_to_C": int((name in ib) != (name in ic)),
                       "candidate_trigger": "exercised" if name in ic else "not_exercised"}
                for name, (_, label) in CASES.items()}
    truth = {name for name, (_, label) in CASES.items() if label}
    return {"etalon": etalon["id"], "bank_practice_ready": etalon["practice_ready"],
            "native": {"stock_removed_count": len(native_removed), "stock_witness_survives": stock_survives,
                       "B": sorted(b), "C": sorted(c), "changed_B_to_C": len(b ^ c),
                       "B_only": sorted(b - c), "C_only": sorted(c - b), "route_critical": critical,
                       "candidate_additional_flags_vs_stock": len(c),
                       "candidate_trigger": "exercised" if c else "not_exercised"},
            "injected": controls, "M114": {"B": len(ib ^ truth), "C": len(ic ^ truth)},
            "all_expected": stock_survives and WITNESS in b & c and b == c and not critical
            and ib == set(CASES) and ic == truth}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    archived = git("show", f"{HEAD}:tools/trainer/trainer.py")
    loaded = Path(trainer.__file__).read_bytes()
    if loaded != archived:
        raise SystemExit("loaded trainer.py does not match the frozen Git blob")
    bank_raw = git("show", f"{HEAD}:docs/trainer/etalons.json")
    ledger = git("show", f"{HEAD}:docs/trainer/ledger.json")
    etalons = {e["id"]: e for e in json.loads(bank_raw)["etalons"]}
    args.out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    report = {"head": HEAD, "inputs": {"trainer": digest(loaded), "bank": digest(bank_raw),
              "ledger": digest(ledger), "harness": digest(Path(__file__).read_bytes())}, "pairs": [],
              "run_status": "finished", "not_measured": ["live escapes", "artifact passage", "FBX quality"]}
    for index, etalon in enumerate(ETALONS * 3):
        if time.monotonic() - start >= 360:
            report["run_status"] = "budget_stop"
            break
        begin = time.monotonic()
        item = pair(etalons[etalon], args.out)
        item["wall_s"] = round(time.monotonic() - begin, 3)
        report["pairs"].append(item)
        print(etalon, item["M114"], item["all_expected"], item["wall_s"], flush=True)
        if index == 0:
            elapsed = time.monotonic() - start
            report["projected_total_s"] = round(elapsed + item["wall_s"] * 5 * 1.2, 3)
            if report["projected_total_s"] > 360:
                report["run_status"] = "budget_stop"
                break
    report["wall_s"] = round(time.monotonic() - start, 3)
    if report["wall_s"] >= 360:
        report["run_status"] = "budget_stop"
    pairs = report["pairs"]
    report["hypothesis"] = "inconclusive"
    if report["run_status"] == "finished" and len(pairs) == 6:
        report["hypothesis"] = "confirmed" if all(p["all_expected"] for p in pairs) else "refuted"
        report["stats"] = {}
        for e in ETALONS:
            s = [p["M114"] for p in pairs if p["etalon"] == e]
            delta = [p["B"] - p["C"] for p in s]
            report["stats"][e] = {"B_median": statistics.median(p["B"] for p in s),
                                  "C_median": statistics.median(p["C"] for p in s),
                                  "gain_range": [min(delta), max(delta)]}
    (args.out / "receipt.json").write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    return 0 if report["run_status"] == "finished" else 3


if __name__ == "__main__":
    raise SystemExit(main())
