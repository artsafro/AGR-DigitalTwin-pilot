"""Aggregate run.py results: per route timings (median/range), parity headless vs live, detection.

    uv run python experiments/bim-blender-agr/analyze.py <S dir>
"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

S = Path(sys.argv[1])
res = json.loads((S / "results.json").read_text(encoding="utf-8"))
out = {}


def med(xs):
    return {"median": round(st.median(xs), 3), "min": round(min(xs), 3), "max": round(max(xs), 3), "n": len(xs)}


for route in ("headless", "live"):
    rs = [r for r in res if r["route"] == route]
    out[route] = {
        "realize_wall_s": med([r["wall_s"] for r in rs]),
        "readback_fbx_s": med([r["readback_fbx_s"] for r in rs]),
        "readback_blend_s": med([r["readback_blend_s"] for r in rs]),
        "max_hd_fbx_vs_src_mm": max(r["hd_fbx_vs_src_mm"] for r in rs),
        "max_hd_blend_vs_src_mm": max(r["hd_blend_vs_src_mm"] for r in rs),
        "blend_eq_fbx_sig": sum(r["blend_eq_fbx_sig"] for r in rs),
        "n": len(rs),
    }
    if route == "live":
        out[route]["in_dcc_build_s"] = med([r["build_s"] for r in rs])
        out[route]["in_dcc_io_s"] = med([r["io_s"] for r in rs])
        out[route]["scene_restored"] = sum(r["clean"] for r in rs)
        out[route]["versions"] = sorted({r["version"] for r in rs})

# detection: clean must pass, flip variants must fail orientation
det = defaultdict(lambda: [0, 0])
for r in res:
    key = f"{r['route']}:{r['variant']}"
    ok = r["checks_passed"] if r["variant"] == "clean" else ("orientation" in r["checks_not_pass"])
    det[key][0] += ok
    det[key][1] += 1
out["detection"] = {k: f"{a}/{b}" for k, (a, b) in sorted(det.items())}

# cross-route parity: same bench/variant/rep -> identical facts, identical signature, same verdict
par = {"facts_equal": 0, "sig_equal": 0, "verdict_equal": 0, "pairs": 0, "max_sig_dev": 0.0, "diffs": []}
idx = {(r["bench"], r["variant"], r["route"], r["rep"]): r for r in res}
for (b, v, route, rep), h in idx.items():
    if route != "headless":
        continue
    lv = idx[(b, v, "live", rep)]
    par["pairs"] += 1
    fe = h["facts_fbx"] == lv["facts_fbx"] and h["facts_blend"] == lv["facts_blend"]
    par["facts_equal"] += fe
    if not fe and len(par["diffs"]) < 3:
        par["diffs"].append([b, v, rep, h["facts_fbx"], lv["facts_fbx"]])
    sh = np.load(S / b / f"{v}-headless-r{rep}" / "sig.npy")
    sl = np.load(S / b / f"{v}-live-r{rep}" / "sig.npy")
    if sh.shape == sl.shape:
        dev = float(np.abs(sh - sl).max())
        par["max_sig_dev"] = max(par["max_sig_dev"], dev)
        par["sig_equal"] += dev < 1e-4
    par["verdict_equal"] += (h["checks_passed"], h["checks_not_pass"]) == (lv["checks_passed"], lv["checks_not_pass"])
out["parity"] = par
# per-bench mesh facts for the table
out["facts"] = {f"{r['bench']}:{r['variant']}": r["facts_fbx"] for r in res if r["route"] == "headless" and r["rep"] == 1}
(S / "summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "facts"}, indent=1))
