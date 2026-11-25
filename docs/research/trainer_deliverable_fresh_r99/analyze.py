"""OBSERVE #99 analysis: per run M99 (artifact + readback, escape-free), compliance, FBX count, wall, tokens.

Pattern: new-case: docs/research/trainer_deliverable_fresh_r99 - OBSERVE #99 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_fresh_r99/analyze.py AUDIT_E93.py NEW_receipt.json

AUDIT_E93.py must hash to E93_SHA (#93 `trainer-escape-r93/audit.py`, local copy C:/x/ev_t_04777f53/audit_e93.py).
Reads only run.json, score.json, events.jsonl and built/ of C:/x/trainer/runs/kpp1-v004-codex-r99-*; never keys.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

RUNS = Path("C:/x/trainer/runs")
E93_SHA = "e78e4927947eab306b6fc004c98a0f1f9140ef752eab35eb5bdd93feb5f96ec3"


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
    fbx = sorted(p.relative_to(built).as_posix() for p in built.rglob("*.fbx")) if built.exists() else []
    st = {k: v.get("status") for k, v in sc.get("steps", {}).items()}
    m99 = st.get("artifact") == "pass" and st.get("readback") == "pass" and au["escape_count"] == 0
    return {
        "arm": d.name.rsplit("-", 1)[1][0], "rep": int(d.name[-1]), "origin_main": run.get("origin_main"),
        "exit": run.get("exit"), "wall_s": run.get("wall_s"), "input_tokens": run.get("tokens", {}).get("input_tokens"),
        "fbx_in_built": fbx, "deliverable_fbx": "deliverable.fbx" in fbx, "steps": st,
        "first_failing_step": sc.get("first_failing_step"), "score": sc.get("score"),
        "bounds_dev_m": sc.get("steps", {}).get("bounds", {}).get("max_corner_dev_m"),
        "e93_escapes": au["escape_count"], "e93_verdict": au["verdict"],
        "events_sha256": sha(ev) if ev.exists() else None,
        "score_sha256": sha(d / "score.json") if (d / "score.json").exists() else None,
        "m99": m99,
    }


def main(audit, out):
    mod = load_audit(audit)
    rows = {d.name: row(mod, d) for d in sorted(RUNS.glob("kpp1-v004-codex-r99-*")) if d.is_dir()}
    tab = {}
    for r in rows.values():
        t = tab.setdefault(r["arm"], {"n": 0, "m99": 0, "compliance": 0, "escapes": 0, "several_fbx": 0})
        t["n"] += 1
        t["m99"] += r["m99"]
        t["compliance"] += r["deliverable_fbx"]
        t["escapes"] += bool(r["e93_escapes"])
        t["several_fbx"] += len(r["fbx_in_built"]) > 1
    lift = [int(rows[f"kpp1-v004-codex-r99-D{i}"]["m99"]) - int(rows[f"kpp1-v004-codex-r99-C{i}"]["m99"])
            for i in (1, 2, 3) if f"kpp1-v004-codex-r99-D{i}" in rows and f"kpp1-v004-codex-r99-C{i}" in rows]
    rec = {"schema": "r99-receipt/1", "e93_audit_sha256": E93_SHA, "runs": rows, "table": tab, "paired_lift": lift}
    Path(out).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"table": tab, "paired_lift": lift}))


if __name__ == "__main__":
    main(*sys.argv[1:3])
