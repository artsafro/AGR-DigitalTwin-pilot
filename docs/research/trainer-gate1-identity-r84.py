"""Read-only Gate 1 identity experiment; see autoresearch-trainer-gate1-identity-r84.md."""

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from dt_ai.core.models import PartsList

R83 = "cdca7bc2ac3a4f4ed74616592e466dc103f2aa6f"
R83_SCRIPT = "docs/research/trainer-gate1-request-r83.py"
FIXTURES = {
    "tuning": [f"kpp1-v004-codex-r83-C{i}" for i in (1, 2, 3)],
    "held_out": [f"g22-k2-stage1-codex-r83-C{i}" for i in (3, 4, 5)],
    "historical_negative": [f"g22-k2-stage1-codex-r83-B{i}" for i in (1, 2, 3)],
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def candidate(row, questions):
    tokens = set(re.split(r"[^0-9a-f]+", questions.lower()))
    return int(bool(row["complete_request"]) and any(
        p.get("status") == "draft" and not p["gate1_set"]
        and {p["approval_sha256"], p["file_sha256"]} <= tokens
        for p in row["proposals"]
    ))


def selftest():
    content, file_hash = "1" * 64, "2" * 64
    row = {"complete_request": 1, "proposals": [{"approval_sha256": content, "file_sha256": file_hash,
                                                "status": "draft", "gate1_set": False}]}
    assert candidate(row, f"approval: {content}\nfile: {file_hash}") == 1
    assert candidate(row, f"approval: {content}") == 0, "approval-only handoff must not appear complete"
    assert candidate(row, f"approval: {content}\nfile: {file_hash}a") == 0, "partial token is not an identity"
    assert candidate({**row, "complete_request": 0}, f"{content} {file_hash}") == 0
    print("selftest: 4 assertions passed")


def inventory(path):
    files = [path / k for k in ("last.txt", "run.json", "prompt.txt")]
    built = path / "built"
    if not built.is_dir():
        raise FileNotFoundError(built)
    files.extend(p for p in sorted(built.rglob("*")) if p.is_file())
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in files}


def manifest(root):
    return {name: {key: sha(data) for key, data in inventory(root / name).items()}
            for names in FIXTURES.values() for name in names}


def replay_one(raw, judge, group):
    with tempfile.TemporaryDirectory(prefix="r84-", dir=Path(".venv")) as work:
        dst = Path(work)
        for key, data in raw.items():
            p = dst / key
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        qkey, pkey = "built/QUESTIONS.md", "built/parts.json"
        qpath, ppath = dst / qkey, dst / pkey

        def measure(expected, anchor=None):
            row = judge(dst)
            qbytes = qpath.read_bytes() if qpath.exists() else None
            pbytes = ppath.read_bytes() if ppath.exists() else None
            current = {qkey: qbytes, pkey: pbytes}
            b, c = row["complete_request"], candidate(row, (qbytes or b"").decode("utf-8"))
            if any(row["violations"].values()):
                raise ValueError(f"guard violation: {row['violations']}")
            return {"B": b, "C": c, "expected": expected, "delta_correct": (
                int(c == expected) - int(b == expected) if expected is not None else None),
                "changes_from_native": {key: int(data != raw.get(key)) for key, data in current.items()},
                "changes_from_anchor": ({key: int(data != anchor[key]) for key, data in current.items()}
                                        if anchor else "not_exercised"),
                "violations": row["violations"]}

        if group == "historical_negative":
            return {"native": measure(0)}
        original = ppath.read_bytes()
        questions = qpath.read_bytes()
        parts = PartsList.model_validate_json(original)
        content = parts.approval_sha256()
        file_hash = sha(original)
        # Independent native label: exact whole tokens rather than matching a substring.
        words = set(re.findall(rb"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])", questions.lower()))
        exact = {content.encode(), file_hash.encode()} <= words
        records = {"native": measure(int(exact))}
        if not exact:
            questions += f"\nR84 positive control\napproval: {content}\nfile: {file_hash}\n".encode()
        anchor = {pkey: original, qkey: questions}
        qpath.write_bytes(questions)
        records["exact_anchor"] = measure(1, anchor)
        records["exact_anchor"]["origin"] = "native" if exact else "constructed"
        ppath.write_bytes(formatted := original + b"\n")
        assert sha(formatted) != file_hash
        assert PartsList.model_validate_json(formatted).approval_sha256() == content
        records["stale_format"] = measure(0, anchor)
        qpath.write_bytes(re.sub(re.escape(file_hash.encode()), sha(formatted).encode(), questions, flags=re.I))
        records["rebound_format"] = measure(1, anchor)
        ppath.write_bytes(original)
        qpath.write_bytes(re.sub(re.escape(file_hash.encode()), b"0" * 64, questions, flags=re.I))
        records["wrong_file"] = measure(0, anchor)
        qpath.write_bytes(re.sub(re.escape(file_hash.encode()), b"[omitted]", questions, flags=re.I))
        records["missing_file"] = measure(0, anchor)
        assert all(sum(records[key]["changes_from_anchor"].values()) == count for key, count in (
            ("stale_format", 1), ("wrong_file", 1), ("missing_file", 1), ("rebound_format", 2)))
        return records


def run(root, pins):
    old = subprocess.check_output(["git", "show", f"{R83}:{R83_SCRIPT}"])
    ns = {"__name__": "trainer_r83"}
    exec(compile(old, R83_SCRIPT, "exec"), ns)
    judge = ns["judge"]
    historical = json.loads(subprocess.check_output([
        "git", "show", f"{R83}:docs/research/trainer-gate1-request-r83.json"]))["rows"]
    assert manifest(root) == pins, "raw input manifest mismatch"
    for name, hashes in pins.items():
        row = historical[name]
        recorded = {**row["files"], **{f"built/{p['path']}": p["file_sha256"] for p in row["proposals"]}}
        assert all(hashes.get(key) == value for key, value in recorded.items()), f"r83 evidence drift: {name}"
    receipt = {"r83_blob_sha256": sha(old), "probe_sha256": sha(Path(__file__).read_bytes()),
               "rows": {}, "cells": {}, "run_status": "complete"}
    start = time.perf_counter()
    for group, names in FIXTURES.items():
        cell = {}
        for name in names:
            raw = inventory(root / name)
            assert {key: sha(data) for key, data in raw.items()} == pins[name]
            cell[name] = replay_one(raw, judge, group)
            if name == FIXTURES["tuning"][0]:
                receipt["first_pair_s"] = time.perf_counter() - start
                if 9 * receipt["first_pair_s"] > 120:
                    receipt.update(run_status="budget_stop", rows={group: cell})
                    break
        receipt["rows"][group] = cell
        if receipt["run_status"] == "budget_stop":
            break
        assert len(cell) == 3
        receipt["cells"][group] = {}
        for state in next(iter(cell.values())):
            paired = [row[state]["delta_correct"] for row in cell.values()]
            receipt["cells"][group][state] = {"paired": paired, "median": statistics.median(paired),
                                              "min": min(paired), "max": max(paired)}
    receipt["wall_s"] = time.perf_counter() - start
    if receipt["wall_s"] > 120:
        receipt["run_status"] = "budget_stop"
    assert manifest(root) == pins, "original inputs changed"
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    elif args.inventory:
        print(json.dumps(manifest(args.runs), indent=2))
    else:
        print(json.dumps(run(args.runs, json.loads(args.manifest.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
