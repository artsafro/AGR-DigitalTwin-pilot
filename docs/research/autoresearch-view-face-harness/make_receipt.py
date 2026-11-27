"""Write a compact, committed receipt from a view_face result.json (+ hashes of the 3 replay runs)."""
import hashlib, json, sys
src, out = sys.argv[1], sys.argv[2]
r = json.load(open(src, encoding="utf-8"))
rows = []
for v in r["views"]:
    if "case" not in v:
        rows.append(v)
        continue
    rows.append({k: v[k] for k in ("fixture", "title", "gt_az", "case", "synthetic", "view_width_m")} |
                {var: {"answer": v[var]["answer"], "outcome": v[var]["outcome"], "margin": v[var].get("margin")}
                 for var in ("V1", "V2", "V3", "V4", "V5")} | {"V0": v["V0"]["outcome"]})
rec = {"schema": "view-face-receipt/1", "source_result": src,
       "source_result_sha256": hashlib.sha256(open(src, "rb").read()).hexdigest(),
       "replay_runs": sys.argv[3:], "fixture_sha256": r["fixture_sha256"], "inputs": r["inputs"],
       "timing_s": r["timing_s"], "summary": r["summary"], "views": rows}
open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
print("ok", out)
