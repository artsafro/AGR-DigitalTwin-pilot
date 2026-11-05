"""elv-tc-vpm: parts/elv_full_parts_v003.json = elv_full_parts_v002.json + P43_InteriorCapsules + P44_CoverStrips
(user decisions 2026-11-05, TASK.md «User answers 2») + v007 door changes in history. Gate 1 for P43 / P44 pending.

py -3 -I make_parts_full_v003.py <parts_v002.json> <out parts_v003.json>
"""
import json, os, sys

src, out = sys.argv[1:3]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
P = json.load(open(src, encoding="utf-8"))
user = {"kind": "user", "reference": "jobs/elv-tc-vpm/TASK.md «User answers 2» 2026-11-05"}
P["parts"] += [
    {"id": "P43_InteriorCapsules", "part_class": "other",
     "sources": [user, {"kind": "model", "reference": "customer blank SM_Elevatornaya_Vl_1_A_001 fake rooms (tile 1003), "
                        "depth 0.80 m / 0.92 m on the slanted NW wall (outputs/customer-clarify-v001)"}],
     "legend_item": "ID34 dark interior placeholder (new working ID, interior group 31-35). A box behind every window, "
                    "glazed door and curtain wall, the opening side removed; rim 7.5 mm in front of the glass (middle of the "
                    "frame), rim = glass extents + 25 mm; depth 0.80 m (0.92 NW skew wall, 2.30 entrance niche over the "
                    "revolving door), less where geometry is in the way; normals inward.",
     "operation": "primitive", "triangle_budget": {"npm": 0, "vpm": 2000}, "build_as": "box"},
    {"id": "P44_CoverStrips", "part_class": "other",
     "sources": [user, {"kind": "pdf", "reference": "booklet item 14 «нащельник RAL 7021»"},
                 {"kind": "model", "reference": "Revit (SC)-Batten_FS-8P ..._horizontal 165 x 22 mm, 24 outlines "
                                                "(customer-clarify-v001/data/nakl_verts.json)"}],
     "legend_item": "ID20 metal RAL 7021. Closed boxes 165 x 22 mm, 6 mm off the facade [D201], only where the Revit "
                    "outline lies on our sandwich / TP facade (the parts behind the pilot cladding are not built), cut "
                    "around lights / Arktos / joints with G.",
     "operation": "primitive", "triangle_budget": {"npm": 0, "vpm": 1500}, "build_as": "box"},
]
P["questions"].append({"audience": "user", "text": "Gate 1 for P43_InteriorCapsules and P44_CoverStrips (build-v007).",
                       "answer": "pending"})
P["history"].append("v003 2026-11-05: + P43_InteriorCapsules, P44_CoverStrips; doors No 1, 4, 11, 21, 25 -> ELV-21 "
                    "(vision panel), west door No 30 ELV-08 added (build_full_v007.py)")
json.dump(P, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("parts", len(P["parts"]))
