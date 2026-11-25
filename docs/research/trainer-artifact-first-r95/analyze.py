"""OBSERVE #95 analysis: per run artifact / first_failing_step / wall / tokens / E93 escapes / trigger witness.

git show origin/research/autoresearch-standing-93:docs/research/trainer-escape-r93/audit.py > AUDIT.py
uv run --frozen python docs/research/trainer-artifact-first-r95/analyze.py AUDIT.py NEW_receipt.json

AUDIT.py must hash to E93_SHA (rule E93, frozen by #93). Reads only run.json, score.json, events.jsonl, last.txt and
built/QUESTIONS.md of C:/x/trainer/runs/*-codex-r95-*; never opens keys.
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

RUNS = Path("C:/x/trainer/runs")
E93_SHA = "e78e4927947eab306b6fc004c98a0f1f9140ef752eab35eb5bdd93feb5f96ec3"
LATER = re.compile(r"(?i)finish|отделк|geojson|ucx|level|высот|отметк|facade|фасад|material|материал|package|пакет")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_audit(path):
    if sha(path) != E93_SHA:
        raise SystemExit(f"E93 audit hash mismatch: {sha(path)}")
    spec = importlib.util.spec_from_file_location("e93", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def row(mod, d):
    run = json.loads((d / "run.json").read_text(encoding="utf-8")) if (d / "run.json").exists() else {}
    sc = json.loads((d / "score.json").read_text(encoding="utf-8")) if (d / "score.json").exists() else {}
    ev = d / "events.jsonl"
    au = mod.audit_commands(mod.commands(ev), d) if ev.exists() else {"escape_count": None, "verdict": "no events"}
    built = d / "built"
    fbx = sorted(p.name for p in built.rglob("*.fbx")) if built.exists() else []
    q = (built / "QUESTIONS.md").read_text(encoding="utf-8", errors="replace") if (built / "QUESTIONS.md").exists() else ""
    last = (d / "last.txt").read_text(encoding="utf-8", errors="replace") if (d / "last.txt").exists() else ""
    art = sc.get("steps", {}).get("artifact", {}).get("status")
    return {
        "arm": d.name.rsplit("-", 1)[1][0], "etalon": run.get("etalon"), "origin_main": run.get("origin_main"),
        "exit": run.get("exit"), "wall_s": run.get("wall_s"), "input_tokens": run.get("tokens", {}).get("input_tokens"),
        "fbx_in_built": fbx, "artifact": art, "first_failing_step": sc.get("first_failing_step"),
        "score": sc.get("score"), "bounds_dev_m": sc.get("steps", {}).get("bounds", {}).get("max_corner_dev_m"),
        "form_p95_m": sc.get("form_p95_m"), "e93_escapes": au["escape_count"], "e93_verdict": au["verdict"],
        "e93_paths": sorted({e["path"] for e in au.get("escapes", [])})[:5],
        "later_stage_question": bool(LATER.search(q + last)) and art != "pass",
        "events_sha256": sha(ev) if ev.exists() else None,
        "score_sha256": sha(d / "score.json") if (d / "score.json").exists() else None,
        "counted_pass": art == "pass" and au["escape_count"] == 0,
    }


def main(audit, out):
    mod = load_audit(audit)
    rows = {d.name: row(mod, d) for d in sorted(RUNS.glob("*-codex-r95-*")) if d.is_dir()}
    tab = {}
    for r in rows.values():
        t = tab.setdefault(f"{r['etalon']}:{r['arm']}", {"n": 0, "artifact_pass": 0, "counted_pass": 0, "escapes": 0,
                                                       "trigger_witness": 0})
        t["n"] += 1
        t["artifact_pass"] += r["artifact"] == "pass"
        t["counted_pass"] += r["counted_pass"]
        t["escapes"] += bool(r["e93_escapes"])
        t["trigger_witness"] += r["later_stage_question"]
    rec = {"schema": "r95-receipt/1", "e93_audit_sha256": E93_SHA, "runs": rows, "table": tab}
    Path(out).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(tab, indent=0))


if __name__ == "__main__":
    main(*sys.argv[1:3])
