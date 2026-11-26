"""OBSERVE #121: isolation preflight + post-run read audit for the one 63B A/B (Artem 2026-11-26 ~22:00).

Not product code. Rule from the decision: the accepted-version path is never in the builder context, and a
post-run audit of reads fails the run if the builder touched it.

  preflight BANK HEAD OUT_JSON  -> admits 63b-stage1 via bank_problems, checks task_text and a real scrubbed
                                    practice tree for every FAIL pattern (0 files left = pass)
  audit RUN_DIR BANK OUT_JSON   -> scans events.jsonl commands + agent messages + files the agent wrote
                                    (wt untracked/modified, built/) for FAIL/WARN patterns; fail closed
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/trainer"))
import trainer as T  # noqa: E402

EID = "63b-stage1"
# Where Artem's accepted / rejected 63B versions live (Drive), the hidden key dir, and the unscrubbed repo.
FAIL = ["1619-body-training", "1855-trainer-v0", "stage2-63b", "poly63-b", "agr-pilot/agr-digitaltwin",
        "agr-digitaltwin/jobs", "c:/x/trainer/runs"]
WARN = ["agr-evidence", "agr-assets", "g:/"]


def norm(s):
    return s.replace("\\\\", "/").replace("\\", "/").lower()


def patterns(e):
    return sorted(set(FAIL) | {norm(t) for t in T.scan_tokens(e)})


def hits(text, pats):
    low = norm(text)
    return [p for p in pats if p in low]


def preflight(bank_path, head, out_json):
    bank = T.load_bank(bank_path)  # raises on any bank_problems (current Drive manifest validation)
    e = T.etalon(bank, EID)
    pats = patterns(e)
    rep = {"schema": "r121-preflight/1", "bank": str(bank_path), "bank_sha256": T.sha256(bank_path), "head": head,
           "practice_ready": e["practice_ready"], "patterns": pats}
    text = T.task_text(e, Path("C:/x/inputs"), Path("C:/x/built"))
    rep["task_text_hits"] = hits(text, pats)
    with tempfile.TemporaryDirectory(dir="C:/x") as td:
        dst = Path(td) / "wt"
        rep["scrubbed"] = T.practice_tree(T.ROOT, head, dst, e)
        left = {}
        for rel, found in T.leaking_files(dst, pats).items():
            left[rel] = found
        rep["files_left"] = left
        rep["files_scanned"] = sum(1 for p in dst.rglob("*") if p.is_file() and ".git" not in p.parts)
    rep["pass"] = not rep["task_text_hits"] and not left and e["practice_ready"]
    Path(out_json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("pass", "task_text_hits", "files_scanned")} |
                     {"scrubbed_n": len(rep["scrubbed"]), "files_left_n": len(left)}))
    return 0 if rep["pass"] else 1


def audit(run_dir, bank_path, out_json):
    e = T.etalon(T.load_bank(bank_path), EID)
    pats = patterns(e)
    run = Path(run_dir)
    ev = run / "events.jsonl"
    rep = {"schema": "r121-audit/1", "run_dir": str(run), "fail": {}, "warn": {}}
    if not ev.is_file():
        rep["status"] = "error"
        rep["reason"] = "no events.jsonl (fail closed)"
    else:
        _, cmds, msgs = T.parse_events(ev.read_text(encoding="utf-8", errors="replace").splitlines())
        for i, c in enumerate(cmds):
            for bucket, ps in (("fail", pats), ("warn", WARN)):
                h = hits(c, ps)
                if h:
                    rep[bucket][f"cmd[{i}]"] = {"hits": h, "cmd": c[:300]}
        for i, m in enumerate(msgs):
            h = hits(m, pats)
            if h:
                rep["fail"][f"msg[{i}]"] = {"hits": h}
        wt = run / "wt"
        written = []
        if wt.is_dir():
            out = subprocess.run(["git", "-C", str(wt), "status", "--porcelain", "-uall"], capture_output=True,
                                 text=True).stdout
            written = [wt / ln[3:].strip().strip('"') for ln in out.splitlines() if ln[3:].strip()]
        written += [p for p in (run / "built").rglob("*") if p.is_file()] if (run / "built").is_dir() else []
        for p in written:
            if p.is_file() and p.stat().st_size < 20_000_000:
                h = hits(p.read_bytes().decode("utf-8", errors="replace"), pats)
                if h:
                    rep["fail"][f"file:{p.relative_to(run).as_posix()}"] = {"hits": h}
        rep["commands"] = len(cmds)
        rep["files_checked"] = len(written)
        rep["status"] = "fail" if rep["fail"] else "pass"
    Path(out_json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"status": rep["status"], "fail_n": len(rep["fail"]), "warn_n": len(rep["warn"]),
                      "commands": rep.get("commands"), "files_checked": rep.get("files_checked")}))
    return 0 if rep["status"] == "pass" else 1


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    sys.exit(preflight(*args) if cmd == "preflight" else audit(*args))
