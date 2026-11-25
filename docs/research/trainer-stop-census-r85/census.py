"""Trainer stop census (autoresearch #85, OBSERVE): recover WHY a practice run stopped from its run folder.

No LLM. Reads RUN/built/QUESTIONS.md, RUN/built/**/*.fbx and RUN/run.json; scores against frozen hand labels.
Rules were written from the tuning etalon's texts only (kpp1-v004); see docs/research/autoresearch-trainer-stop-census.md.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

LABELS = ("fbx", "gate1", "bm12", "finish_src", "geo_src", "geom_src", "open_scene")
REQ = re.compile(r"\b(confirm|approve|provide|supply|identify|accept|please|will you|should|can the|which|what|"
                 r"define|say whether|clarify)\b|подтверд|предостав|принять|открывать ли", re.I)
NOT_REQ = re.compile(r"^\s*(recommend\w*|рекомендац\w*|default\w*|proposed scope)\b", re.I)
KW = {
    "gate1": r"partslist|parts list|gate ?1|approval[_ ]sha256|approval hash|состав элемент",
    "bm12": r"\bfirst (measured |typical )?(floor |facade/)?(module|facade|floor)|bm-12|before (replication|the remaining)",
    "finish_src": r"finish|material|отделк",
    "geo_src": r"geojson|msk-77|project zero|datum|levels?\b|units?\b|\baxes\b|\bcrs\b|coordinate|address|oks index|"
               r"\bfno\b|placement|геопривязк|высотн|положени",
    "geom_src": r"contour|opening|niche|recess|depth|roof|inventory|composition|parts and quantities|envelope|"
                r"source (governs|priority|authority)|governs|wall mapping|facade-to-plan|контур",
    "open_scene": r"\bopen(ed)?\b.*\b(scene|stage|acceptance|review)|открыва",
}
KW = {k: re.compile(v, re.I) for k, v in KW.items()}
CLAUSE = re.compile(r"\b(after|once|when)\b[^,.;?]*", re.I)  # preconditions do not request anything


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def items(text):
    """Numbered questions; whole text when the file has none."""
    its = [m.group(1) for m in re.finditer(r"^\s*\d+\.\s*(.+)$", text, re.M)]
    return its or [text]


def sentences(item):
    return [s for s in re.split(r"(?<=[.?!;])\s+", item) if s.strip()]


def census(run):
    run = Path(run)
    built = run / "built"
    out = {"fbx": int(any(built.rglob("*.fbx"))) if built.is_dir() else 0}
    q = built / "QUESTIONS.md"
    out["handoff"] = "present" if q.is_file() else "missing"
    try:
        rj = json.loads((run / "run.json").read_text(encoding="utf-8"))
        out["exit_stop"] = None if rj.get("exit") == 0 else str(rj.get("exit"))
    except (OSError, ValueError):
        out["exit_stop"] = "no run.json"
    for k in LABELS[1:]:
        out[k] = 0
    if not q.is_file():
        return out
    text = q.read_text(encoding="utf-8-sig", errors="replace")
    letters = [c for c in text if not c.isspace()]
    out["unreadable_share"] = round(sum(c == "?" for c in letters) / max(1, len(letters)), 3)
    for it in items(text):
        for s in sentences(it):
            m = NOT_REQ.search(s)
            if m:  # "Recommend X: confirm Y?" -> the request after the colon still counts (kpp1 r83-C2)
                rest = s[m.end():]
                s = rest.split(":", 1)[1] if ":" in rest and not rest.lstrip().startswith(":") else ""
            if not s.strip() or not (REQ.search(s) or s.rstrip().endswith("?")):
                continue
            is_g1 = bool(KW["gate1"].search(s))
            out["gate1"] |= int(is_g1)
            if is_g1:
                continue  # scope words inside a Gate 1 request are not separate source requests
            body = CLAUSE.sub(" ", s)
            for k in LABELS[2:]:
                out[k] |= int(bool(KW[k].search(body if k != "open_scene" else s)))
    return out


def score(labels, preds, split):
    tp = fp = fn = 0
    per = {k: [0, 0] for k in LABELS}  # agree, measured
    for rid, r in labels["runs"].items():
        if r["split"] != split:
            continue
        for k, y in zip(LABELS, r["labels"]):
            if y is None:
                continue
            p = preds[rid][k]
            per[k][0] += int(p == y)
            per[k][1] += 1
            tp += int(p == 1 and y == 1)
            fp += int(p == 1 and y == 0)
            fn += int(p == 0 and y == 1)
    f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return {"micro_f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn, "per_label_agree": per}


def preflight(labels, root):
    bad = []
    for rid, r in labels["runs"].items():
        d = root / rid
        for f, key in (("built/QUESTIONS.md", "questions_sha256"), ("run.json", "run_json_sha256")):
            if not (d / f).is_file() or sha256(d / f) != r[key]:
                bad.append(f"{rid}/{f}")
    return bad


def perturb(root, tmp):
    """-> list of (name, run, field, before, after, expected_after, ok)."""
    res = []

    def clone(rid, name):
        dst = Path(tmp) / f"{rid}-{name}"
        shutil.copytree(root / rid, dst, ignore=shutil.ignore_patterns("wt", "inputs", "events.jsonl", "work*",
                                                                       "readback", "*.dwg", "*.dxf"))
        return dst

    for name, rid, field, exp, act in (
        ("P1_add_fbx", "kpp1-v004-codex-r83-C1", "fbx", 1,
         lambda d: (d / "built" / "x.fbx").write_bytes(b"Kaydara FBX Binary  \x00")),
        ("P2_no_questions", "kpp1-v004-codex-r83-C1", "handoff", "missing",
         lambda d: (d / "built" / "QUESTIONS.md").unlink()),
        ("P3_timeout", "g22-k2-stage1-codex-r83-C2", "exit_stop", "timeout",
         lambda d: (d / "run.json").write_text(json.dumps({**json.loads((d / "run.json").read_text(
             encoding="utf-8")), "exit": "timeout"}), encoding="utf-8")),
        ("P4_gate1_approved", "kpp1-v004-codex-r83-C1", "gate1", 0,
         lambda d: (d / "built" / "QUESTIONS.md").write_text(re.sub(
             r"(?m)^5\..*$", "5. Gate 1 approved: approval_sha256() recorded by the user.",
             (d / "built" / "QUESTIONS.md").read_text(encoding="utf-8-sig")), encoding="utf-8")),
    ):
        d = clone(rid, name)
        before = census(d)
        act(d)
        after = census(d)
        others = {k: (before[k], after[k]) for k in LABELS if k != field and before[k] != after[k]}
        if name == "P2_no_questions":
            ok = after["handoff"] == "missing" and all(after[k] == 0 for k in LABELS[1:])
        else:
            ok = after[field] == exp and not others
        res.append({"name": name, "run": rid, "field": field, "before": before[field], "after": after[field],
                    "expected": exp, "other_changed": others, "ok": ok})
        shutil.rmtree(d)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        sys.exit(f"{out} exists")
    t0 = time.perf_counter()
    labels = json.loads(Path(a.labels).read_text(encoding="utf-8"))
    root = Path(labels["runs_root"])
    bad = preflight(labels, root)
    if bad:
        sys.exit(f"preflight hash mismatch: {bad}")
    preds = {rid: census(root / rid) for rid in labels["runs"]}
    baseline = {rid: {k: 0 for k in LABELS} for rid in labels["runs"]}  # ledger today: `artifact` only
    with tempfile.TemporaryDirectory(dir=None) as tmp:
        pert = perturb(root, tmp)
    rep = {"schema": "trainer-stop-census/1", "labels_sha256": sha256(a.labels),
           "census_sha256": sha256(__file__), "preds": preds,
           "score": {s: score(labels, preds, s) for s in ("tuning", "held_out")},
           "baseline": {s: score(labels, baseline, s) for s in ("tuning", "held_out")},
           "tally_pred": {k: sum(p[k] for p in preds.values()) for k in LABELS},
           "perturbations": pert}
    rep["preds_sha256"] = hashlib.sha256(json.dumps(preds, sort_keys=True).encode()).hexdigest()
    rep["wall_s"] = round(time.perf_counter() - t0, 3)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"tuning": rep["score"]["tuning"]["micro_f1"], "held_out": rep["score"]["held_out"]["micro_f1"],
                      "gate1_held": rep["score"]["held_out"]["per_label_agree"]["gate1"],
                      "pert_ok": [p["ok"] for p in pert], "preds_sha256": rep["preds_sha256"][:12],
                      "wall_s": rep["wall_s"]}))


if __name__ == "__main__":
    main()
