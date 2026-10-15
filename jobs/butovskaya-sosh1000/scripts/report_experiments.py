"""Experiment tables of the #118 loop for the report (Markdown).

    uv run python jobs/butovskaya-sosh1000/scripts/report_experiments.py            # round 3, mesh reference
    uv run python jobs/butovskaya-sosh1000/scripts/report_experiments.py --box      # first attempt, box reference
"""
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "autoresearch"


def fmt(v):
    return "" if v is None else str(v)


def main():
    box = "--box" in sys.argv
    rows = json.loads((DIR / ("results.json" if box else "results-twin.json")).read_text(encoding="utf-8"))
    print("| # | Change | silhouette_err_m2 (x / y / top) | Guard: open / nm edges / nm verts / open other / overlaps / "
          "winding | Triangles | Status |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        if r["status"] == "crash":
            print(f"| {r['n']} | {r['description']} | crash: {r.get('error', '')[:120]} | | | crash |")
            continue
        pv = r.get("per_view_m2") or {}
        m = r.get("mesh") or {}
        if r.get("guard_passed") is None:
            guard = r.get("guard_note") or "not run (metric not better)"
        else:
            guard = " / ".join(fmt(m.get(k)) for k in ("boundary", "non_manifold", "non_manifold_vertices",
                                                         "open_loops_not_allowed", "overlaps"))
            guard += f" / {fmt(r.get('winding_bad_edges'))}"
            guard += "" if r["guard_passed"] else " **fail**"
            if r.get("guard_note"):
                guard += f" ({r['guard_note']})"
        tris = r.get("triangles") or (r.get("build") or {}).get("triangles")
        print(f"| {r['n']} | {r['description']} | **{r['silhouette_err_m2']}** ({fmt(pv.get('x'))} / {fmt(pv.get('y'))}"
              f" / {fmt(pv.get('top'))}) | {guard} | {fmt(tris)} | {r['status']} |")


if __name__ == "__main__":
    main()
