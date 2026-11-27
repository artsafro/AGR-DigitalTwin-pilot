"""OBSERVE #97 analysis: per run artifact / first failing step / adapter use / E93 escapes -> receipt.json.

Pattern: new-case: docs/research/trainer-g22-adapter-r97 - OBSERVE #97 trainer practice series (research only).

git show origin/research/autoresearch-standing-93:docs/research/trainer-escape-r93/audit.py > AUDIT.py
uv run --frozen python docs/research/trainer-g22-adapter-r97/analyze.py AUDIT.py NEW_receipt.json

Reads only run.json, score.json, events.jsonl, the scorer stdout in series.log and built/ file names of
C:/x/trainer/runs/g22-k2-stage1-codex-r97-*; never opens keys. A scorer refusal (no score.json) is a fail.
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

RUNS = Path("C:/x/trainer/runs")
E93_SHA = "e78e4927947eab306b6fc004c98a0f1f9140ef752eab35eb5bdd93feb5f96ec3"
ADAPTER = re.compile(r"floor_from_dump\.py")
PROMOTED = re.compile(r"tools[/\\]+methods[/\\]+body[/\\]+floor_from_dump\.py")


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


def adapter_runs(cmds):
    """Commands that RUN the adapter (python ... floor_from_dump.py ...), not reads of it."""
    ran = [c for c in cmds if ADAPTER.search(c) and re.search(r"(?i)python|uv run", c)
           and not re.search(r"(?i)get-content|\brg\b|select-string|cat |type ", c)]
    return {"ran": len(ran), "promoted_path": sum(bool(PROMOTED.search(c)) for c in ran)}


def row(mod, d):
    run = json.loads((d / "run.json").read_text(encoding="utf-8")) if (d / "run.json").exists() else {}
    sc = json.loads((d / "score.json").read_text(encoding="utf-8")) if (d / "score.json").exists() else {}
    ev = d / "events.jsonl"
    cmds = mod.commands(ev) if ev.exists() else []
    au = mod.audit_commands(cmds, d) if ev.exists() else {"escape_count": None, "verdict": "no events"}
    built = d / "built"
    fbx = sorted(str(p.relative_to(built)) for p in built.rglob("*.fbx")) if built.exists() else []
    art = sc.get("steps", {}).get("artifact", {}).get("status")
    return {
        "arm": d.name.rsplit("-", 1)[1][0], "etalon": run.get("etalon"), "origin_main": run.get("origin_main"),
        "exit": run.get("exit"), "wall_s": run.get("wall_s"), "input_tokens": run.get("tokens", {}).get("input_tokens"),
        "commands": len(cmds), "fbx_in_built": fbx, "scored": bool(sc), "artifact": art,
        "first_failing_step": sc.get("first_failing_step") if sc else ("artifact" if not fbx else "scorer_refusal"),
        "score": sc.get("score"), "form_p95_m": sc.get("form_p95_m"),
        "bounds": sc.get("steps", {}).get("bounds", {}).get("status"),
        "adapter": adapter_runs([c if isinstance(c, str) else str(c) for c in cmds]),
        "scrubbed_files": len(run.get("scrubbed_files", [])),
        "e93_escapes": au["escape_count"], "e93_verdict": au["verdict"],
        "e93_paths": sorted({e["path"] for e in au.get("escapes", [])})[:6],
        "events_sha256": sha(ev) if ev.exists() else None,
        "score_sha256": sha(d / "score.json") if (d / "score.json").exists() else None,
        "counted_pass": art == "pass" and au["escape_count"] == 0,
    }


def main(audit, out):
    mod = load_audit(audit)
    rows = {d.name: row(mod, d) for d in sorted(RUNS.glob("g22-k2-stage1-codex-r97-*")) if d.is_dir()}
    tab = {}
    for r in rows.values():
        t = tab.setdefault(r["arm"], {"n": 0, "fbx_any": 0, "artifact_pass": 0, "counted_pass": 0, "escapes": 0,
                                      "adapter_ran": 0, "adapter_promoted": 0})
        t["n"] += 1
        t["fbx_any"] += bool(r["fbx_in_built"])
        t["artifact_pass"] += r["artifact"] == "pass"
        t["counted_pass"] += r["counted_pass"]
        t["escapes"] += bool(r["e93_escapes"])
        t["adapter_ran"] += r["adapter"]["ran"] > 0
        t["adapter_promoted"] += r["adapter"]["promoted_path"] > 0
    b, c = tab.get("B", {}).get("counted_pass", 0), tab.get("C", {}).get("counted_pass", 0)
    full = tab.get("B", {}).get("n") == 3 and tab.get("C", {}).get("n") == 3
    verdict = ("inconclusive (series incomplete)" if not full else "confirmed" if c >= 2 and c > b
               else "refuted" if c <= b else "inconclusive")
    rec = {"schema": "r97-receipt/1", "e93_audit_sha256": E93_SHA, "runs": rows, "table": tab, "h97": verdict}
    Path(out).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"table": tab, "h97": verdict}, indent=0))


if __name__ == "__main__":
    main(*sys.argv[1:3])
