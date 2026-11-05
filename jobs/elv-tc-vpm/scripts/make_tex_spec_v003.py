"""elv-tc-vpm tex-v004: write tex_spec_v003.json = tex_spec_v002.json with the user's 2026-11-05 changes.

py -3 -I make_tex_spec_v003.py <tex_spec_v002.json> <wood_colour_sample_v004.json> <out tex_spec_v003.json>
- address -> Elevatornaya_Vl_1_A_001 (customer stem);
- ID02 metal cassette RAL 7024 instead of 7021 (only the cassette; sandwich, frames, flashings keep their RAL);
- wood IDs (ID03 cassette, ID07 reveal, ID17 ribs, ID18_1001 flashing, ID19 soffit/canopy): colour from the site photo
  (target_srgb of the sample), smooth painted metal (pattern 'cassette', no grain); ID03 keeps the cassette joint
  grid 1000 x 1530 (joint 20 mm), ID17 / ID19 without joints (as before, no joint lattice);
- new ID34 interior capsule placeholder, dark (RGB 30, roughness 0.9), appended last (UDIMs of v002 stay).
Order of the v002 tiles is kept, so their UDIM numbers do not move.
"""
import json, os, sys

src, sample, out = sys.argv[1:4]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
S = json.load(open(src, encoding="utf-8"))
W = json.load(open(sample, encoding="utf-8"))
wood = W["target_srgb"]
RAL7024 = [71, 74, 81]    # RAL 7024 graphite grey, common sRGB approximation (#474A51)
S["address"] = "Elevatornaya_Vl_1_A_001"
S["_doc"] = ("elv-tc-vpm tex-v004 (tex_spec_v003) = tex_spec_v002 + user decisions 2026-11-05: stem Elevatornaya_Vl_1_A_001; "
             "metal cassette ID02 RAL 7024; wood IDs smooth (no grain) in the site-photo colour %s (%s, %s); new ID34 dark "
             "interior capsule placeholder. Joint grids and all other tiles as v002. " % (W["target_hex"], W["target_rule"],
             "nearest RAL %s dE76 %s" % tuple(W["target_nearest_ral_dE76"][0])) + S["_doc"])
for t in S["tiles"]:
    k = t["key"]
    if k == "ID02":
        t["rgb"], t["ral"] = RAL7024, "7024 (customer TZ / user 2026-11-05)"
    elif k == "ID03":
        t.update({"pattern": "cassette", "rgb": wood, "rough": 0.45, "ral": "site photo " + W["target_hex"]})
        t.pop("grain", None)
    elif k in ("ID07", "ID18_1001"):
        t.update({"rgb": wood, "ral": "site photo " + W["target_hex"]})
    elif k in ("ID17", "ID19"):
        t.update({"pattern": "cassette", "rgb": wood, "rough": 0.45, "ral": "site photo " + W["target_hex"]})
        t.pop("grain", None)
S["tiles"].append({"key": "ID34", "ids": [34], "kind": "placeholder", "rgb": [30, 30, 30], "rough": 0.9, "metal": 0.0,
                   "ral": "interior capsule, dark placeholder (working ID, v007)"})
json.dump(S, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print([(t["key"], t.get("pattern"), t["rgb"]) for t in S["tiles"]])
