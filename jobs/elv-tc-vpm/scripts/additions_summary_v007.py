"""elv-tc-vpm build-v007: print a short table of additions_v007*.json (capsules, glass inside capsules, strips).

py -3 -I additions_summary_v007.py <additions.json>
"""
import json, sys

A = json.load(open(sys.argv[1], encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")
print("SUMMARY", A["summary"])
print("-- capsules")
for c in A["capsules"]:
    print("  D %.2f/%.2f z %s len %.2f  %s" % (c["depth_m"], c["depth_wanted_m"], c["z"], c["rim_len_m"], c["name"]))
for c in A["capsules_skipped"]:
    print("  SKIPPED", c)
print("-- glass inside capsules", len(A["glass_inside_capsule"]))
for g in A["glass_inside_capsule"]:
    print("  ", g)
print("-- strips")
for s in A["strips"]:
    blk = [p for p in s["pieces"] if "blocked_by_parts" in p]
    print("  %s z %s out %s off %smm outline %.2f built %.2f pieces %d %s" % (
        s["name"], s["z"], s["out"], s["facade_offset_from_outline_mm"], s["outline_len_m"], s["built_len_m"],
        sum(1 for p in s["pieces"] if "len_m" in p), [b["blocked_by_parts"] for b in blk]))
for s in A["strips_dropped"]:
    print("  DROPPED", s)
