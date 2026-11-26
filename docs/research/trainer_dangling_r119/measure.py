"""#119 OBSERVE harness: route-critical docs in trainer practice trees naming repo files the scrub removed.

Pattern: new-case: docs/research/trainer_dangling_r119 - OBSERVE #119 trainer practice-tree route integrity (research only).

Tree = `git archive HEAD` + unchanged tools.trainer.trainer.scrub_worktree (no product file is edited).
M119 = distinct head files named in route-critical .md/.json of the tree and absent from the tree (contract
docs/research/autoresearch-trainer-dangling-routes.md). Stored runs: the same count on each run's own wt/
against its own origin_main, plus E93 escape verdict, command hit on a dangling basename, FBX presence.

uv run --frozen python docs/research/trainer_dangling_r119/measure.py --audit .r119/AUDIT.py --out C:/x/ev_t_f454aa44/r119-NEW
"""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.trainer import trainer  # noqa: E402

HEAD = "8a2fa635469d346009c60a922c9438e3dc20b77f"
ETALONS = ("g22-k2-stage1", "63a-stage1", "kpp1-v004")  # g22 first: witness + first measured pair
WITNESS = ("g22-k2-stage1", "floor_from_dump.py")
HELD_OUT = ("63a-stage1", "kpp1-v004")
E93_SHA = "e78e4927947eab306b6fc004c98a0f1f9140ef752eab35eb5bdd93feb5f96ec3"
REPS = 3
CAP_S = 45 * 60
STORED_ROOT = Path("C:/x/trainer/runs")
ROUTE_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
ROUTE_DIRS = ("docs/agents/", "routes/", "docs/procedure/", "docs/domain/", "docs/scenarios/", ".agents/skills/")
NAME = re.compile(r"[A-Za-z0-9_.\\/-]+\.(?:py|ps1|ms|json|md|npz|yaml|yml|toml)\b")
TOOL_EXT = (".py", ".ps1", ".ms")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def head_files(head, _cache={}):
    if head not in _cache:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "-z", head],
                             capture_output=True, check=True).stdout.decode("utf-8")
        files = set(f for f in out.split("\0") if f)
        by_base = {}
        for f in files:
            by_base.setdefault(f.rsplit("/", 1)[-1], []).append(f)
        _cache[head] = (files, by_base)
    return _cache[head]


def tree_files(wt):
    wt = Path(wt)
    return {f.relative_to(wt).as_posix() for f in wt.rglob("*")
            if f.is_file() and ".git" not in f.relative_to(wt).parts}


def route_critical(rel):
    return (rel in ROUTE_FILES or rel.startswith(ROUTE_DIRS)) and rel.endswith((".md", ".json"))


def norm(name):
    n = name.replace("\\", "/")
    while n.startswith(("./", "/")):
        n = n[2:] if n.startswith("./") else n[1:]
    return n


def resolve(n, files, by_base):
    """-> (kind, head files the name points to). kind: path | suffix | bare | stale | ignored."""
    if "/" in n:
        if n in files:
            return "path", [n]
        cands = [f for f in by_base.get(n.rsplit("/", 1)[-1], []) if f.endswith("/" + n)]
        return ("suffix", cands) if cands else ("stale", [])
    if not n.endswith(TOOL_EXT):
        return "ignored", []
    cands = by_base.get(n, [])
    return ("bare", cands) if cands else ("stale", [])


def m119(wt, head, tfiles=None):
    files, by_base = head_files(head)
    tfiles = tree_files(wt) if tfiles is None else tfiles
    dangling, refs, stale = set(), {}, set()
    for rel in sorted(r for r in tfiles if route_critical(r)):
        text = (Path(wt) / rel).read_bytes().decode("utf-8", errors="replace")
        for raw in set(NAME.findall(text)):
            n = norm(raw)
            kind, cands = resolve(n, files, by_base)
            if kind == "stale":
                stale.add(n)
            if not cands or any(c in tfiles for c in cands):
                continue
            for c in cands:
                dangling.add(c)
                refs.setdefault(c, set()).add(rel)
    tools = sorted(f for f in dangling if f.endswith(TOOL_EXT))
    return {"M119": len(dangling), "M119_tools": len(tools), "tools": tools, "dangling": sorted(dangling),
            "referenced_by": {k: sorted(v) for k, v in sorted(refs.items())}, "stale": len(stale)}


def build(e, dst):
    dst = Path(dst)
    dst.mkdir(parents=True)
    t0 = time.time()
    p = subprocess.Popen(["git", "-C", str(ROOT), "archive", "--format=tar", HEAD], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=p.stdout, mode="r|") as tar:
        tar.extractall(dst, filter="data")
    if p.wait() != 0:
        raise SystemExit(f"git archive {HEAD} failed")
    removed = trainer.scrub_worktree(dst, e)
    return removed, round(time.time() - t0, 1)


def perturb(e, wt, base):
    files, by_base = head_files(HEAD)
    tfiles = tree_files(wt)
    hidden = sorted(f for f in files if f not in tfiles and f not in base["dangling"]
                    and any(f.startswith(h.rstrip("/") + "/") for h in e.get("hidden_repo_paths", []))
                    and f.endswith(".md"))
    existing = "tools/trainer/trainer.py"
    cases = {}
    if hidden:
        h = hidden[0]
        cases["P1_hidden_full_path"] = ("docs/agents/r119_probe.md", f"run `{h}`", 1)
        cases["P4_backslash"] = ("docs/agents/r119_probe.md", "run " + h.replace("/", "\\"), 1)
        cases["P5_non_route_file"] = ("docs/research/r119_probe.md", f"run `{h}`", 0)
    cases["P2_existing"] = ("docs/agents/r119_probe.md", f"run `{existing}`", 0)
    cases["P3_nowhere_in_head"] = ("docs/agents/r119_probe.md", "run `tools/none/r119_absent_tool.py`", 0)
    if e["id"] == "g22-k2-stage1":  # first hidden-only .py basename not already counted
        tool = next(b for b, fs in sorted(by_base.items()) if b.endswith(".py") and all(
            f not in tfiles and f not in base["dangling"] and f.startswith("jobs/garibaldi22/") for f in fs))
        cases["P6_bare_hidden_tool"] = ("docs/agents/r119_probe.md", f"then {tool}", 1)
    out = {}
    for name, (rel, line, want) in cases.items():
        f = Path(wt) / rel
        assert not f.exists(), f
        f.write_text(line + "\n", encoding="utf-8")
        try:
            got = m119(wt, HEAD)
        finally:
            f.unlink()
        delta = got["M119"] - base["M119"]
        out[name] = {"file": rel, "line": line, "expected_delta": want, "delta": delta,
                     "stale_delta": got["stale"] - base["stale"], "ok": delta == want}
    for name in ("P1_hidden_full_path", "P4_backslash", "P5_non_route_file", "P6_bare_hidden_tool"):
        out.setdefault(name, {"status": "not_exercised"})
    return out


def load_audit(path):
    if sha(path) != E93_SHA:
        raise SystemExit(f"E93 audit hash mismatch: {sha(path)}")
    spec = importlib.util.spec_from_file_location("e93", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stored(audit):
    rows = {}
    for d in sorted(STORED_ROOT.iterdir()):
        rj, ev, wt = d / "run.json", d / "events.jsonl", d / "wt"
        if not (rj.exists() and ev.exists() and wt.is_dir()):
            continue
        run = json.loads(rj.read_text(encoding="utf-8"))
        head = run.get("origin_main")
        try:
            r = m119(wt, head)
        except subprocess.CalledProcessError:
            rows[d.name] = {"status": "not_measured", "reason": f"head {head} not in this repo"}
            continue
        cmds = audit.commands(ev)
        bases = sorted({f.rsplit("/", 1)[-1].lower() for f in r["tools"]})
        hit = sorted({b for b in bases for c in cmds if b in c.lower()})
        esc = audit.audit_commands(cmds, d)
        fbx = any(p.suffix.lower() == ".fbx" for p in (d / "built").rglob("*")) if (d / "built").exists() else False
        rows[d.name] = {"etalon": run.get("etalon"), "head": head, "M119": r["M119"], "M119_tools": r["M119_tools"],
                        "tools": r["tools"], "hit": hit, "escape": esc["verdict"] == "escape",
                        "escape_count": esc["escape_count"], "fbx": fbx}
    meas = [v for v in rows.values() if "M119" in v]

    def rate(group):
        bad = sum(v["escape"] or not v["fbx"] for v in group)
        return {"n": len(group), "escape_or_no_fbx": bad, "rate": round(bad / len(group), 3) if group else None}
    return rows, {"hit": rate([v for v in meas if v["hit"]]), "not_hit": rate([v for v in meas if not v["hit"]])}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--audit", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists; write a NEW folder")
    audit = load_audit(a.audit)
    bank_path = ROOT / "docs/trainer/etalons.json"
    bank = trainer.load_bank(bank_path)
    inputs = {"head": HEAD, "bank_sha256": sha(bank_path), "trainer_py_sha256": sha(ROOT / "tools/trainer/trainer.py"),
              "measure_py_sha256": sha(__file__), "audit_sha256": sha(a.audit)}
    out.mkdir(parents=True)
    t0, series, status = time.time(), [], "finished"
    for e_id in ETALONS:
        e = trainer.etalon(bank, e_id)
        for rep in range(1, REPS + 1):
            if time.time() - t0 > CAP_S:
                status = "budget_stop"
                break
            wt = out / "trees" / f"{e_id}-{rep}"
            removed, wall = build(e, wt)
            r = m119(wt, HEAD)
            row = {"etalon": e_id, "rep": rep, "wall_s": wall, "removed": len(removed),
                   "route_critical_removed": sorted(x for x in removed if route_critical(x.split(" (names ")[0])),
                   **r}
            if rep == 1:
                row["perturb"] = perturb(e, wt, r)
            series.append(row)
            print(e_id, rep, r["M119"], r["M119_tools"], wall, flush=True)
            if rep > 1:
                shutil.rmtree(wt)
    summary = {}
    for e_id in ETALONS:
        v = [s["M119"] for s in series if s["etalon"] == e_id]
        t = [s["M119_tools"] for s in series if s["etalon"] == e_id]
        if v:
            summary[e_id] = {"reps": len(v), "M119_median": sorted(v)[len(v) // 2], "spread": [min(v), max(v)],
                             "M119_tools_median": sorted(t)[len(t) // 2], "tools_spread": [min(t), max(t)]}
    w_rows = [s for s in series if s["etalon"] == WITNESS[0]]
    a_ok = len(w_rows) == REPS and all(any(f.endswith("/" + WITNESS[1]) for f in s["tools"]) for s in w_rows)
    b_ok = any(summary.get(h, {}).get("M119_tools_median", 0) >= 1 for h in HELD_OUT)
    c_ok = all(p.get("ok", True) for s in series if "perturb" in s for p in s["perturb"].values())
    rows, assoc = stored(audit)
    if status != "finished" or not a_ok or not c_ok:
        verdict = "inconclusive"
    else:
        verdict = "confirmed" if b_ok else "refuted"
    rec = {"schema": "r119/1", "inputs": inputs, "series": series, "summary": summary,
           "criteria": {"a_witness_3of3": a_ok, "b_held_out_tools": b_ok, "c_perturbations": c_ok},
           "hypothesis": verdict, "stored_runs": rows, "association": assoc,
           "wall_s": round(time.time() - t0, 1), "run_status": status}
    (out / "receipt.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"summary": summary, "criteria": rec["criteria"], "hypothesis": verdict,
                      "association": assoc, "wall_s": rec["wall_s"], "run_status": status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
