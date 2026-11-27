"""Print compact per-view rows of a view_face result.json."""
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
case = sys.argv[2] if len(sys.argv) > 2 else "full"
for v in r["views"]:
    if v.get("case", "") != case and not (case == "partial" and v.get("case", "").startswith("partial")):
        if v.get("status"):
            print("NM", v)
        continue
    s = v["scores"]["V3"]
    print(v["fixture"], v["title"], "gt", v["gt_az"], v["case"], "w", v["view_width_m"], "seg", v["segments"],
          "V0", v["V0"]["best"], v["V0"].get("err"), "|V1", v["scores"]["V1"], "|V2", v["scores"]["V2"],
          "|V3", s, v["V3"]["outcome"], v["V3"]["margin"])
