"""r87: scratch bank = r81 held-out bank + tower map source and one task sentence for 63a/63b (OBSERVE)."""
import hashlib, json, sys
src, box, out = sys.argv[1:4]
b = json.load(open(src, encoding="utf-8"))
h = hashlib.sha256(open(box, "rb").read()).hexdigest()
ets = b["etalons"] if isinstance(b, dict) else b
for e in ets:
    if e["id"] in ("63a-stage1", "63b-stage1"):
        t = e["id"][2].upper()
        e["sources"].append({"path": box, "sha256": h,
                             "role": "user-approved tower map of site 63: tower ids and world-metre boxes"})
        e["task"] = e["task"].rstrip() + (
            " Tower identity: boxes63.json (inputs) is the user-approved tower map of this site; each entry gives a"
            " tower id and its axis-aligned box (min/max, source world metres); tower %s = id \"63%s\"." % (t, t))
        print(e["id"], e["practice_ready"])
json.dump(b, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(hashlib.sha256(open(out, "rb").read()).hexdigest())
