"""#113 OBSERVE harness: accepted-lineage folders left in the trainer practice tree.

Baseline = unchanged tools.trainer.trainer.practice_tree at HEAD; candidate = the same call with scan_tokens
extended in-process by the frozen lineage tokens L(e). Product files are never edited.
Usage: uv run --frozen python docs/research/trainer_lineage_r113/measure.py --out C:/x/ev_t_70d0913e/r113-NEW
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "trainer"))
from tools.trainer import trainer  # noqa: E402

HEAD = "7762dcfe2e78219155461bb633faaca2015e259b"
ETALONS = ("63a-stage1", "kpp1-v004", "g22-k2-stage1")  # 63a first: tuning + trigger witness
DECLARED = {"63a-stage1": ["1619-body-training"], "g22-k2-stage1": ["1619-body-training"], "kpp1-v004": []}
WITNESS = ("63a-stage1", "docs/research/body-training-1619/README.md")
ROUTE_CRITICAL_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
ROUTE_CRITICAL_DIRS = ("docs/agents/", "routes/", "docs/domain/", "docs/procedure/", ".agents/skills/", "tools/",
                       "src/", "standards/", "schemas/")
STORED = sorted(Path("C:/x/trainer/runs").glob("*-codex-r111-*/wt"))
PERTURB = {
    "p1_backslash": ("63a-stage1", "G:\\Мой диск\\AGR-evidence\\1619-body-training\\tower-A\\v005", True),
    "p2_upper": ("63a-stage1", "see AGR-EVIDENCE/1619-BODY-TRAINING for the accepted versions", True),
    "p3_sibling": ("63a-stage1", "evidence: G:/Мой диск/AGR-evidence/1855-r111-ledger-fresh/", False),
    "p4_repo_folder": ("63a-stage1", "log: docs/research/body-training-1619/ (repo folder only)", False),
    "p5_kpp1_for_kpp1": ("kpp1-v004", "G:/Мой диск/AGR-evidence/1609-kpp1-package-v004/draft-b25/", True),
    "p5_kpp1_for_63a": ("63a-stage1", "G:/Мой диск/AGR-evidence/1609-kpp1-package-v004/draft-b25/", False),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lineage_tokens(e):
    toks = set(DECLARED[e["id"]])
    for item in [e["key"], *e.get("rejected", []), e.get("calibration_accepted") or {}]:
        p = str(item.get("path") or "").replace("\\", "/")
        if "AGR-evidence/" in p:
            toks.add(p.split("AGR-evidence/", 1)[1].split("/", 1)[0])
    return sorted(t.lower() for t in toks)


def route_critical(rel):
    return rel in ROUTE_CRITICAL_FILES or rel.startswith(ROUTE_CRITICAL_DIRS)


def removed_rel(entry):
    return entry.split(" (names ", 1)[0]


def build(e, dst, candidate):
    orig = trainer.scan_tokens
    if candidate:
        trainer.scan_tokens = lambda x: sorted(set(orig(x)) | set(lineage_tokens(x)))
    try:
        t0 = time.time()
        removed = trainer.practice_tree(ROOT, HEAD, dst, e)
        return removed, round(time.time() - t0, 1)
    finally:
        trainer.scan_tokens = orig


def m113(tree, toks):
    hits = trainer.leaking_files(tree, toks)
    per_tok = {t: sum(t in f for f in hits.values()) for t in toks}
    return len(hits), sorted(hits), per_tok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--cap-s", type=float, default=2400.0)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists; new folder only")
    out.mkdir(parents=True)
    bank_path = ROOT / "docs/trainer/etalons.json"
    rec = {"schema": "r113/1", "head": HEAD, "inputs": {
        "bank_sha256": sha(bank_path), "trainer_py_sha256": sha(ROOT / "tools/trainer/trainer.py"),
        "measure_py_sha256": sha(__file__)}, "tokens": {}, "series": [], "stored_r111": [], "perturb": {}}
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    t_start, pair_s = time.time(), None
    status = "finished"
    for rep in range(1, a.reps + 1):
        for eid in ETALONS:
            e = trainer.etalon(bank, eid)
            toks = lineage_tokens(e)
            rec["tokens"][eid] = toks
            row = {"etalon": eid, "rep": rep}
            for arm in ("baseline", "candidate"):
                dst = out / f"{eid}-{arm}-{rep}"
                removed, wall = build(e, dst, arm == "candidate")
                n, files, per_tok = m113(dst, toks)
                row[arm] = {"M113": n, "files": files, "per_token": per_tok, "removed": len(removed),
                            "removed_rel": sorted(removed_rel(r) for r in removed), "wall_s": wall}
                row[arm]["witness_present"] = (dst / WITNESS[1]).is_file() if eid == WITNESS[0] else None
                shutil.rmtree(dst, ignore_errors=True)
            extra = sorted(set(row["candidate"]["removed_rel"]) - set(row["baseline"]["removed_rel"]))
            row["changed"] = len(extra)
            row["changed_files"] = extra
            row["route_critical_removed"] = [r for r in extra if route_critical(r)]
            for arm in ("baseline", "candidate"):
                del row[arm]["removed_rel"]
            rec["series"].append(row)
            print(json.dumps({k: row[k] for k in ("etalon", "rep", "changed")} |
                             {arm: row[arm]["M113"] for arm in ("baseline", "candidate")}), flush=True)
            if pair_s is None:
                pair_s = time.time() - t_start
                rec["first_pair_s"] = round(pair_s, 1)
                rec["derived_cap_s"] = round(min(a.cap_s, 5 * pair_s * len(ETALONS) * a.reps), 1)
            if time.time() - t_start > rec["derived_cap_s"]:
                status = "budget_stop"
                break
        if status != "finished":
            break
    for wt in STORED:
        eid = wt.parent.name.split("-codex-")[0]
        e = trainer.etalon(bank, eid)
        n, files, per_tok = m113(wt, lineage_tokens(e))
        rec["stored_r111"].append({"run": wt.parent.name, "M113": n, "files": files})
    pdir = out / "perturb"
    for name, (eid, text, expect) in PERTURB.items():
        d = pdir / name
        d.mkdir(parents=True)
        (d / "note.md").write_text(text, encoding="utf-8")
        e = trainer.etalon(bank, eid)
        got = bool(trainer.leaking_files(d, sorted(set(trainer.scan_tokens(e)) | set(lineage_tokens(e)))))
        base = bool(trainer.leaking_files(d, trainer.scan_tokens(e)))
        rec["perturb"][name] = {"etalon": eid, "expected_caught": expect, "candidate_caught": got,
                                "baseline_caught": base, "ok": got == expect}
    rec["inputs_post"] = {"bank_sha256": sha(bank_path), "trainer_py_sha256": sha(ROOT / "tools/trainer/trainer.py")}
    rec["wall_s"] = round(time.time() - t_start, 1)
    rec["run_status"] = status
    (out / "receipt.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("receipt", out / "receipt.json", sha(out / "receipt.json"), "status", status, "wall", rec["wall_s"])


if __name__ == "__main__":
    main()
