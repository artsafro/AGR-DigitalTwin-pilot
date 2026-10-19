"""One experiment of the #118 autoresearch loop (round 3, mesh reference): build, metric, guard, keep / discard.

    uv run python jobs/butovskaya-sosh1000/scripts/loop_step.py --n 3 --desc "..." [--guard-always]

Builds the model with scripts/build_npm.py into C:/x/butovskaya-npm-twin/exp<n>_dump.json, scores it with
scripts/evaluate.py's metric() against the step-0 mesh reference (unchanged) and appends a row to
autoresearch/results-twin.json. Keep = strictly lower silhouette_err_m2 than the best kept row AND evaluate.guard()
passes (unchanged). The guard takes minutes on a ~140 000-triangle model, so it is run only when the metric is
strictly better (a discard by metric needs no guard; --guard-always runs it anyway). The decision is the same as
running both every time. The caller commits build_npm.py on keep and restores it on discard.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "autoresearch" / "results-twin.json"
OUT = Path("C:/x/butovskaya-npm-twin")


def best(rows):
    kept = [r for r in rows if r["status"] in ("baseline", "keep")]
    return min(r["silhouette_err_m2"] for r in kept) if kept else None


def guard_summary(gd):
    v = gd["mesh"]["value"]
    return {"guard_passed": gd["guard_passed"], "delivery_passed": gd["delivery_passed"],
            "mesh": {k: v.get(k) for k in ("non_manifold", "non_manifold_vertices", "boundary", "open_loops_not_allowed",
                                           "overlaps", "ngons")},
            "mesh_status": gd["mesh"]["status"],
            "per_mesh_status": {k: m["status"] for k, m in gd["mesh_per_mesh"].items()},
            "winding_bad_edges": int(sum(gd["winding_bad_edges"].values())), "triangles": gd["triangles"],
            "budget_status": gd["budget_status"], "levels_worst_m": gd["levels"]["worst_m"],
            "levels_status": gd["levels"]["status"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", required=True)
    ap.add_argument("--desc", required=True)
    ap.add_argument("--guard-always", action="store_true")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--prebuilt", help="model dump already written by the current build_npm.py")
    ap.add_argument("--prebuilt-info", help="the build's stdout JSON line for --prebuilt")
    a = ap.parse_args()
    rows = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else []
    model_p = OUT / f"exp{a.n}_dump.json"
    t0 = time.time()
    if a.prebuilt:          # a dump this same build_npm.py wrote (deterministic): copied, info from its stdout
        model_p.write_bytes(Path(a.prebuilt).read_bytes())
        b = subprocess.CompletedProcess([], 0, stdout=a.prebuilt_info, stderr="")
    else:
        b = subprocess.run([sys.executable, str(HERE / "build_npm.py"), "--out", str(model_p)], capture_output=True,
                           text=True)
    row = {"n": a.n, "description": a.desc, "build_seconds": round(time.time() - t0, 1), "delivery_passed": False}
    if b.returncode:
        row.update(status="crash", error=b.stderr[-600:])
    else:
        row["build"] = json.loads(b.stdout.strip().splitlines()[-1])
        t1 = time.time()
        model = from_dump(json.loads(model_p.read_text(encoding="utf-8")))
        m = ev.metric(model, ev.etalon_silhouettes(ev.SNAP))
        row.update(m, metric_seconds=round(time.time() - t1, 1))
        prev = best(rows)
        better = prev is None or m["silhouette_err_m2"] < prev
        row["best_before"] = prev
        if better or a.guard_always or a.baseline:
            t2 = time.time()
            gd = guard_summary(ev.guard(model, ev.SNAP))
            row.update(gd, guard_seconds=round(time.time() - t2, 1))
        else:
            row.update(guard_passed=None, guard_note="not run: metric not strictly better (discard by metric)")
        if a.baseline:
            row["status"] = "baseline"
        else:
            row["status"] = "keep" if better and row.get("guard_passed") else "discard"
    rows.append(row)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in row.items() if k not in ("per_mesh_status",)}, ensure_ascii=False))
    print(f"EXP {a.n} {row['status']} err={row.get('silhouette_err_m2')} best_before={row.get('best_before')} "
          f"guard={row.get('guard_passed')} tris={row.get('build', {}).get('triangles')}")


if __name__ == "__main__":
    main()
