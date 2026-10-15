"""Experiment table of the #118 loop from autoresearch/results.json (Markdown, for the report)."""
import json
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "autoresearch" / "results.json"


def main():
    rows = json.loads(LOG.read_text(encoding="utf-8"))
    print("| # | Change | silhouette_err_m2 (x / y / top) | IoU x / y / top | Guard: nm edges / nm verts / open other / overlaps / winding | Triangles | Status |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        if r["status"] == "crash":
            print(f"| {r['n']} | {r['description']} | crash | | | | crash |")
            continue
        m, pv, iou = r["mesh"], r["per_view_m2"], r["iou"]
        guard = (f"{m['non_manifold']} / {m['non_manifold_vertices']} / {m['open_loops_not_allowed']} / {m['overlaps']} / "
                 f"{r['winding_bad_edges']}" + ("" if r["guard_passed"] else " **fail**"))
        status = r["status"] + (f" ({r['note']})" if r.get("note") else "")
        print(f"| {r['n']} | {r['description']} | **{r['silhouette_err_m2']}** ({pv['x']} / {pv['y']} / {pv['top']}) | "
              f"{iou['x']} / {iou['y']} / {iou['top']} | {guard} | {r['triangles']} | {status} |")


if __name__ == "__main__":
    main()
