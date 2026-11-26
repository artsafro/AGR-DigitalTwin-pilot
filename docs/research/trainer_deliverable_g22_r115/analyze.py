"""OBSERVE #115: receipt from the series log, the six run folders and control.json (no scoring, read-only).

Pattern: new-case: docs/research/trainer_deliverable_g22_r115 - OBSERVE #115 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_g22_r115/analyze.py CONTROL_JSON OUT_RECEIPT
"""
import hashlib
import json
import re
import sys
from pathlib import Path

RUNS = Path("C:/x/trainer/runs")
ETALON = "g22-k2-stage1"
NAME = "deliverable.fbx"
# a command that READS outside the practice tree: absolute main checkout jobs/ or bank evidence folders
ESCAPE = re.compile(r'"command":"[^"]*(agr-pilot.{0,4}AGR-DigitalTwin.{0,4}jobs|AGR-evidence.{0,4}(1619|1855))', re.I)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_row(arm, i):
    d = RUNS / f"{ETALON}-codex-r115-{arm}{i}"
    built = d / "built"
    fbx = sorted(p.relative_to(built).as_posix() for p in built.rglob("*.fbx"))
    sc = json.loads((d / "score.json").read_text(encoding="utf-8")) if (d / "score.json").exists() else None
    steps = (sc or {}).get("steps", {})
    art = steps.get("artifact", {}).get("status") if sc else "refused"
    ev = (d / "events.jsonl").read_text(encoding="utf-8", errors="replace")
    return {"run": d.name, "fbx": fbx, "root_deliverable": (built / NAME).is_file(),
            "scored": sc is not None, "artifact": art, "M115": int(sc is not None and art == "pass"),
            "first_failing_step": (sc or {}).get("first_failing_step"), "score": (sc or {}).get("score"),
            "form_p95_m": (sc or {}).get("form_p95_m"), "escape_commands": len(ESCAPE.findall(ev)),
            "events_sha256": sha(d / "events.jsonl")}


def _norm(rep):
    """Drop the refusal text (it names the per-rep folder); keep status, step, score, p95."""
    return json.loads(json.dumps(rep, default=str), object_hook=lambda o: {k: v for k, v in o.items() if k != "error"})


def main(control_json, out):
    rows = {arm: [run_row(arm, i) for i in (1, 2, 3)] for arm in "CD"}
    m = {arm: sum(r["M115"] for r in rows[arm]) for arm in "CD"}
    pairs = [rows["D"][i]["M115"] - rows["C"][i]["M115"] for i in range(3)]
    counted_d_root = all(r["root_deliverable"] for r in rows["D"] if r["M115"])
    esc = sum(r["escape_commands"] for arm in "CD" for r in rows[arm])
    if m["D"] - m["C"] >= 2 and m["D"] >= 2 and min(pairs) >= 0 and counted_d_root and esc == 0:
        verdict = "confirmed"
    elif m["D"] <= m["C"]:
        verdict = "refuted"
    else:
        verdict = "inconclusive"
    ctl = json.loads(Path(control_json).read_text(encoding="utf-8"))
    rep = {"hypothesis": "H115", "verdict": verdict, "M115": m, "pair_lift": pairs,
           "d_compliance_root_deliverable": sum(r["root_deliverable"] for r in rows["D"]),
           "counted_d_runs_scored_root_deliverable": counted_d_root, "escape_commands_total": esc,
           "runs": rows, "control_json_sha256": sha(control_json),
           "control_spread_zero": all(_norm(r) == _norm(ctl["reps"][0]) for r in ctl["reps"]), "control_rep1": ctl["reps"][0]}
    Path(out).write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("verdict", "M115", "pair_lift", "d_compliance_root_deliverable",
                                          "counted_d_runs_scored_root_deliverable", "escape_commands_total",
                                          "control_spread_zero")}))


if __name__ == "__main__":
    main(*sys.argv[1:3])
