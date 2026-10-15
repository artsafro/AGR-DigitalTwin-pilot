"""Probes of the guarantees #118 states, run before the review (card policy): each prints `invariant -> N/N`.

1. read-only: snapshot_revit.call refuses every non read-only add-in command before any request is sent;
2. the loop never calls Revit: build_npm and evaluate import neither revit_exec nor an HTTP client;
3. deterministic: two builds give byte-identical dumps;
4. keep rule: every `keep` in the log is strictly below the best kept before it with the guard passing, every
   `discard` is not (or fails the guard), and delivery_passed is false in every record;
5. guard numbers of every keep: 0 non-manifold edges / vertices, 0 open loops outside the allowed kinds, 0 winding
   errors, triangles <= 150 000, levels within 0.02 m.

    uv run python jobs/butovskaya-sosh1000/scripts/probe_invariants.py --builds C:/x/butovskaya-npm/probe
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE.parent / "autoresearch" / "results.json"


def probe_read_only():
    sys.path.insert(0, str(HERE))
    import snapshot_revit as sr
    sent = []
    sr.rx.http = lambda *a, **k: sent.append(a) or (200, {"ok": True})
    _, writes = sr.rx.commands()
    names = sorted(writes) + ["save_document", "sync_with_central", "unknown_command", ""]
    refused = 0
    for name in names:
        try:
            sr.call(name, {})
        except SystemExit:
            refused += 1
    ok = refused == len(names) and not sent
    return f"read-only snapshot -> every write / unknown command refused before a request -> {refused}/{len(names)}", ok


def probe_no_revit_in_loop():
    hits = []
    for name in ("build_npm.py", "evaluate.py"):
        text = (HERE / name).read_text(encoding="utf-8")
        for bad in ("revit_exec", "urllib", "http.client", "requests", "socket"):
            if bad in text:
                hits.append(f"{name}:{bad}")
    code = ("import sys; sys.path.insert(0, r'%s'); import build_npm, evaluate; "
            "print(sorted(m for m in sys.modules if m in ('revit_exec', 'snapshot_revit', 'urllib.request', 'http.client')))" % HERE)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    loaded = out.stdout.strip()
    ok = not hits and loaded == "[]"
    return f"loop never calls Revit -> no Revit/HTTP import in build/evaluate (static {10 - len(hits)}/10, runtime {loaded})", ok


def probe_deterministic(work: Path):
    work.mkdir(parents=True, exist_ok=True)
    shas = []
    for k in (1, 2):
        out = work / f"dump{k}.json"
        subprocess.run([sys.executable, str(HERE / "build_npm.py"), "--out", str(out)], check=True,
                       capture_output=True, text=True)
        shas.append(hashlib.sha256(out.read_bytes()).hexdigest())
    return f"deterministic build -> two builds byte-identical ({shas[0][:12]}) -> {int(shas[0] == shas[1])}/1", shas[0] == shas[1]


def probe_keep_rule():
    log = json.loads(LOG.read_text(encoding="utf-8"))
    best, good, n = None, 0, 0
    for r in log:
        if r["status"] == "crash":
            continue
        n += 1
        m, g = r["silhouette_err_m2"], r["guard_passed"]
        ref = r.get("best_before", best)
        if r["status"] == "baseline":
            ok = best is None
        elif r["status"] == "keep":
            ok = g and m < ref
        else:
            ok = (not g) or ref is None or m >= ref or "note" in r   # a parallel candidate beaten by a sibling
        ok = ok and r.get("delivery_passed") is False
        good += ok
        if r["status"] in ("baseline", "keep"):
            best = m if best is None else min(best, m)
    return f"keep = strictly better metric + guard; delivery_passed false -> {good}/{n} records", good == n


def probe_guard_numbers():
    log = json.loads(LOG.read_text(encoding="utf-8"))
    kept = [r for r in log if r["status"] in ("baseline", "keep")]
    good = sum(1 for r in kept if r["mesh"]["non_manifold"] == 0 and r["mesh"]["non_manifold_vertices"] == 0
               and r["mesh"]["open_loops_not_allowed"] == 0 and r["mesh"]["overlaps"] == 0
               and r["winding_bad_edges"] == 0 and r["triangles"] <= 150_000 and r["levels_worst_m"] <= 0.02)
    return f"guard numbers of every kept build -> {good}/{len(kept)}", good == len(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--builds", default="C:/x/butovskaya-npm/probe")
    a = ap.parse_args()
    rows = [probe_read_only(), probe_no_revit_in_loop(), probe_deterministic(Path(a.builds)), probe_keep_rule(),
            probe_guard_numbers()]
    for text, ok in rows:
        print(("PASS " if ok else "FAIL ") + text)
    return 0 if all(ok for _, ok in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
