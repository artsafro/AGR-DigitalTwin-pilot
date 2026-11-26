"""#113 OBSERVE harness: accepted-lineage folders left in the trainer practice tree.

Baseline = unchanged tools.trainer.trainer.practice_tree at HEAD; candidate = the same call with scan_tokens
extended in-process by the frozen lineage tokens L(e). Product files are never edited.
Usage: uv run --frozen python docs/research/trainer_lineage_r113/measure.py --out C:/x/ev_t_70d0913e/r113-NEW

Fail-closed (review r1): the bank, trainer.py and every stored #111 tree are checked against the frozen SHA-256
below BEFORE the output folder is created or any tree is built; a mismatch exits 1 naming the input. run_status is
`finished` (exit 0) only for the complete frozen 3x3 series; otherwise `partial` / `budget_stop` (exit 3), the
receipt is written at once without the stored/perturbation scans, and the hypothesis is `inconclusive`.
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
FROZEN_REPS = 3
FROZEN_INPUTS = {  # SHA-256 of the bytes measured in r113-1 (receipt "inputs")
    "bank": "016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635",
    "trainer_py": "16fd8edb93be0bb846244498a2490de4f5905f1f34bcacd23fcf22d2e95aa4b5",
}
STORED_ROOT = Path("C:/x/trainer/runs")
STORED_MANIFEST = {  # run -> tree_manifest(<run>/wt), frozen in the r113 rework (host-local, replay limited)
    "63a-stage1-codex-r111-1": "06d0b5d56128f31ccb1c94bed28da36564c0f38e55bcee228efcf6589d346173",
    "63a-stage1-codex-r111-2": "3abf056f34e0a6c78a1fb603522405b3d023c6ca435297ae3305b010067e26a2",
    "63a-stage1-codex-r111-3": "a8f8625231acbde75485168cdbcf61a2d42eece76139d4331bdca60ddfc79fa7",
    "g22-k2-stage1-codex-r111-1": "a9634c91b1f6a41dc86161c9eb722e385ad527b6663e47bf47ff54be128eb779",
    "g22-k2-stage1-codex-r111-2": "6528d13e7c36a50ba6b949eddd96bf0df4a6928484a152f36f09827823ee46a5",
    "g22-k2-stage1-codex-r111-3": "679851197272b6da785d6599841182dbab00468c352af70052a416b52b471b2e",
    "kpp1-v004-codex-r111-1": "d40c9d12ac78e07172125dce8804f93eba27c0fcff99ad02012861fe09450cc4",
    "kpp1-v004-codex-r111-2": "13d95b2c47019c2d69650f4dab17aec95994959a1c95513b6c1e059e15b10109",
    "kpp1-v004-codex-r111-3": "d047bd5fbe2746174dc3fd8b044c644d215f9aac00f890e5857ff6611b67e7b7",
}
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


def tree_manifest(wt):
    """SHA-256 over sorted 'rel<TAB>sha256(bytes)' lines of exactly the files trainer.leaking_files scans."""
    h = hashlib.sha256()
    for f in sorted(Path(wt).rglob("*")):
        rel = f.relative_to(wt)
        if ".git" in rel.parts or not f.is_file() or f.is_symlink():
            continue
        h.update(rel.as_posix().encode() + b"\t" + sha(f).encode() + b"\n")
    return h.hexdigest()


def preflight(bank_path, trainer_path, stored_root, frozen=None, manifest=None):
    """Fail closed before any build. -> (input hashes, stored trees to scan, or None if absent on this host)."""
    frozen = FROZEN_INPUTS if frozen is None else frozen
    manifest = STORED_MANIFEST if manifest is None else manifest
    paths = {"bank": Path(bank_path), "trainer_py": Path(trainer_path)}
    got = {k: sha(p) for k, p in paths.items()}
    bad = [f"{k} {paths[k]}: sha256 {got[k]} != frozen {frozen[k]}" for k in frozen if got[k] != frozen[k]]
    found = sorted(p.parent.name for p in Path(stored_root).glob("*-codex-r111-*/wt"))
    stored = None  # absent -> not_measured: the stored #111 trees live on the measuring host only
    if found and found != sorted(manifest):
        bad.append(f"stored trees {stored_root}: {found} != frozen inventory {sorted(manifest)}")
    elif found:
        stored = [Path(stored_root) / run / "wt" for run in found]
        for wt in stored:
            m = tree_manifest(wt)
            if m != manifest[wt.parent.name]:
                bad.append(f"stored tree {wt.parent.name}: manifest {m} != frozen {manifest[wt.parent.name]}")
    if bad:
        raise SystemExit("PREFLIGHT FAILED (nothing built, no receipt):\n  " + "\n  ".join(bad))
    return {f"{k}_sha256": v for k, v in got.items()}, stored


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


def main(argv=None, clock=time.time):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=FROZEN_REPS)
    ap.add_argument("--cap-s", type=float, default=2400.0)
    ap.add_argument("--bank", default=str(ROOT / "docs/trainer/etalons.json"))
    ap.add_argument("--stored-root", default=str(STORED_ROOT))
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists; new folder only")
    if a.reps < 1:
        raise SystemExit(f"--reps {a.reps}: at least 1 (frozen series = {FROZEN_REPS})")
    bank_path = Path(a.bank)
    inputs, stored = preflight(bank_path, trainer.__file__, a.stored_root)
    out.mkdir(parents=True)
    rec = {"schema": "r113/2", "head": HEAD, "inputs": inputs | {"measure_py_sha256": sha(__file__)},
           "preflight": "passed", "reps_requested": a.reps, "reps_frozen": FROZEN_REPS, "tokens": {}, "series": [],
           "stored_r111": [] if stored is not None else "not_measured (no stored #111 trees on this host)",
           "perturb": {}}
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    t_start, status = clock(), None
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
            if "first_pair_s" not in rec:
                pair_s = clock() - t_start
                rec["first_pair_s"] = round(pair_s, 1)
                rec["derived_cap_s"] = round(min(a.cap_s, 5 * pair_s * len(ETALONS) * FROZEN_REPS), 1)
            if clock() - t_start > rec["derived_cap_s"]:
                status = "budget_stop"
                break
        if status:
            break
    complete = a.reps == FROZEN_REPS and len(rec["series"]) == FROZEN_REPS * len(ETALONS)
    status = status or ("finished" if complete else "partial")
    if status == "finished":
        for wt in stored or []:
            eid = wt.parent.name.split("-codex-")[0]
            n, files, _ = m113(wt, lineage_tokens(trainer.etalon(bank, eid)))
            rec["stored_r111"].append({"run": wt.parent.name, "M113": n, "files": files,
                                       "manifest_sha256": STORED_MANIFEST[wt.parent.name]})
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
    else:
        rec["stored_r111"] = rec["perturb"] = f"not_run ({status})"
    rec["hypothesis"] = "per KEEP rule in the contract" if status == "finished" else "inconclusive"
    rec["inputs_post"] = {"bank_sha256": sha(bank_path), "trainer_py_sha256": sha(trainer.__file__)}
    rec["wall_s"] = round(clock() - t_start, 1)
    rec["run_status"] = status
    (out / "receipt.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("receipt", out / "receipt.json", sha(out / "receipt.json"), "status", status, "wall", rec["wall_s"])
    return 0 if status == "finished" else 3


if __name__ == "__main__":
    sys.exit(main())
