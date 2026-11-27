"""Compare view_face result.json runs: summary + every per-view score must be identical; print spread and receipt."""
import hashlib, json, sys
runs = [json.load(open(p, encoding="utf-8")) for p in sys.argv[1:]]
def strip(r):
    return {"summary": r["summary"], "views": r["views"], "inputs": r["inputs"], "fixture": r["fixture_sha256"]}
canon = [json.dumps(strip(r), ensure_ascii=False, sort_keys=True) for r in runs]
print("identical", len(set(canon)) == 1, "runs", len(runs))
print("content_sha256", [hashlib.sha256(c.encode()).hexdigest()[:16] for c in canon])
print("total_s", [r["timing_s"]["total"] for r in runs], "median", sorted(r["timing_s"]["total"] for r in runs)[len(runs) // 2])
for k, s in runs[0]["summary"].items():
    if k.split(".")[0] in ("V0", "V1", "V3", "V5"):
        print(k, s["n"], s["answered"], s["correct"], s["wrong"], s["accuracy_answered"], s["abstain_rate"])
