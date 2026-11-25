"""Standing #83 (t_e4cd663a): Gate 1 request completeness of trainer practice runs. OBSERVE, no key access.

run   <B|C> <etalon> <n> : one practice run through PR #1859's trainer (cwd = its pinned worktree);
                           C appends CANDIDATE_LINE to the task text, nothing else differs.
score [--selftest]       : read-only M83 per run folder (3 readbacks, drift refused).
Contract: docs/research/autoresearch-trainer-gate1-request-r83.md
"""

import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from dt_ai.core.models import PartsList

PIN = "4e0de5610633dfb69908cbc0ad1a6aedee07739c"
TRAINER_SHA = "acde59a7dd5bd52176480340a425ffbe49a6e7bbf5e5f5767af4489ff5ad41fa"
BANK_SHA = "4ceb6a63290ce55a0a178542a6d38b7a3358d819eca166e89c89778157a8790c"
RUNS = Path("C:/x/trainer/runs")
HISTORIC = ("kpp1-v004-codex-20261124", "g22-k2-stage1-codex-20261124", "63a-stage1-codex-20261124")
CANDIDATE_LINE = (
    "Gate 1 in a headless run: if Gate 1 (PartsList confirmation) stops you, first finish the Gate 1 handoff of "
    "docs/procedure/TASK_TO_MODEL.md (section \"Gate 1 handoff\") inside the output folder: write parts.json (a valid "
    "PartsList, status draft or review, gate1 empty), and put its file SHA-256 and its approval_sha256() next to your "
    "questions in QUESTIONS.md. Do not confirm Gate 1 yourself and do not build past it.")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_trainer():
    root = Path.cwd()
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    tr, bank = root / "tools/trainer/trainer.py", root / "docs/trainer/etalons.json"
    if head != PIN or sha(tr.read_bytes()) != TRAINER_SHA or sha(bank.read_bytes()) != BANK_SHA:
        raise SystemExit(f"trainer worktree not pinned: head {head}")
    spec = importlib.util.spec_from_file_location("trainer_r83", tr)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_run(variant, etalon, n):
    if variant not in ("B", "C"):
        raise SystemExit("variant must be B or C")
    tr = load_trainer()
    if variant == "C":
        base = tr.task_text
        tr.task_text = lambda e, i, o: base(e, i, o) + CANDIDATE_LINE + "\n"
    out = RUNS / f"{etalon}-codex-r83-{variant}{n}"
    return tr.main(["run", etalon, "--out", str(out), "--timeout-s", "1800"])


def judge(directory):
    built = directory / "built"
    q = built / "QUESTIONS.md"
    qtext = q.read_text(encoding="utf-8", errors="replace") if q.exists() else ""
    row = {"files": {}, "proposals": [], "built_products": sorted(
        p.relative_to(built).as_posix() for p in built.rglob("*") if p.suffix.lower() in (".fbx", ".zip"))}
    for name in ("last.txt", "run.json", "prompt.txt"):
        p = directory / name
        row["files"][name] = sha(p.read_bytes()) if p.exists() else None
    run = json.loads((directory / "run.json").read_text(encoding="utf-8")) if (directory / "run.json").exists() else {}
    row["origin_main"], row["exit"], row["wall_s"] = run.get("origin_main"), run.get("exit"), run.get("wall_s")
    row["new_code_lines"] = run.get("new_code_lines_outside_hooks")
    row["candidate_line_in_prompt"] = CANDIDATE_LINE in (directory / "prompt.txt").read_text(
        encoding="utf-8", errors="replace") if (directory / "prompt.txt").exists() else None
    for p in sorted(built.rglob("*.json")):
        data = p.read_bytes()
        prop = {"path": p.relative_to(built).as_posix(), "file_sha256": sha(data)}
        try:
            pl = PartsList.model_validate_json(data)
        except (ValidationError, ValueError) as exc:
            prop["invalid"] = sorted({e["type"] for e in exc.errors()}) if isinstance(exc, ValidationError) else ["json"]
            row["proposals"].append(prop)
            continue
        prop.update(approval_sha256=pl.approval_sha256(), status=pl.status, gate1_set=pl.gate1 is not None)
        prop["hash_in_questions"] = prop["approval_sha256"] in qtext
        row["proposals"].append(prop)
    valid = [p for p in row["proposals"] if "approval_sha256" in p]
    row["violations"] = {"self_confirmed": sum(p["gate1_set"] or p["status"] == "confirmed" for p in valid),
                         "built_products": len(row["built_products"]),
                         "new_code_lines": row["new_code_lines"] or 0}
    row["complete_request"] = int(any(p["hash_in_questions"] and not p["gate1_set"] and p["status"] != "confirmed"
                                      for p in valid) and not row["built_products"])
    return row


def selftest():
    from tests.contracts.test_parts_list import LISTING  # synthetic fixture of the pinned tree
    ok = {}
    with tempfile.TemporaryDirectory() as td:
        def case(name, mutate):
            d = Path(td) / name
            (d / "built").mkdir(parents=True)
            pl = PartsList.model_validate(LISTING)
            (d / "built/parts.json").write_text(pl.model_dump_json(), encoding="utf-8")
            (d / "built/QUESTIONS.md").write_text(f"1. confirm? approval {pl.approval_sha256()}\n", encoding="utf-8")
            mutate(d, pl)
            r = judge(d)
            return r["complete_request"], r["violations"]
        ok["witness"] = case("w", lambda d, pl: None)
        ok["hash_removed"] = case("h", lambda d, pl: (d / "built/QUESTIONS.md").write_text("1. confirm?\n"))
        ok["fbx_added"] = case("f", lambda d, pl: (d / "built/x.fbx").write_bytes(b"Kaydara FBX Binary"))

        def confirm(d, pl):
            data = json.loads(pl.model_dump_json())
            data.update(status="confirmed", gate1={"parts_sha256": pl.approval_sha256(), "actor": "agent",
                                                   "date": "2026-11-25", "scope": "synthetic_fixture", "note": "self"})
            (d / "built/parts.json").write_text(json.dumps(data), encoding="utf-8")
        ok["self_confirmed"] = case("s", confirm)
    expect = {"witness": 1, "hash_removed": 0, "fbx_added": 0, "self_confirmed": 0}
    bad = {k: v for k, v in ok.items() if v[0] != expect[k]}
    viol = ok["fbx_added"][1]["built_products"] == 1 and ok["self_confirmed"][1]["self_confirmed"] == 1
    print(json.dumps({"selftest": ok, "pass": not bad and viol}, indent=1))
    return 0 if not bad and viol else 1


def cmd_score():
    dirs = [RUNS / h for h in HISTORIC] + sorted(RUNS.glob("*-codex-r83-*"))
    ref = None
    for _ in range(3):
        rows = {d.name: judge(d) for d in dirs if d.is_dir()}
        if ref is not None and rows != ref:
            raise SystemExit("evidence drift between readbacks")
        ref = rows
    cells = {}
    for name, r in ref.items():
        key = "historic-B" if name in HISTORIC else name.split("-codex-r83-")[0] + ":" + name.rsplit("-", 1)[1][0]
        cells.setdefault(key, []).append(r["complete_request"])
    print(json.dumps({"pin": PIN, "rows": ref, "cells": {k: {"runs": len(v), "complete": sum(v),
                      "median": statistics.median(v)} for k, v in sorted(cells.items())}}, indent=1))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["run"] and len(a) == 4:
        sys.exit(cmd_run(a[1], a[2], a[3]))
    if a[:1] == ["score"]:
        sys.exit(selftest() if "--selftest" in a else cmd_score())
    raise SystemExit(__doc__)
