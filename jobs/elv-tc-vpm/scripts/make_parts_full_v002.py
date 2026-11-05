"""elv-tc-vpm: PartsList full v002 = v001 + P42_Lights (facade light housings) + P27 single doors from ELV-18/19/20.

py -3 make_parts_full_v002.py   (writes parts/elv_full_parts_v002.json, never overwrites)
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "parts", "elv_full_parts_v001.json")
OUT = os.path.join(HERE, "..", "parts", "elv_full_parts_v002.json")
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
d = json.load(open(SRC, encoding="utf-8"))
for p in d["parts"]:
    if p["id"] == "P27_Doors_New":
        p["legend_item"] = p["legend_item"].replace(
            "3 single doors without an ELV type (FBX bbox, open point)",
            "3 single doors from the library ELV-18 (In-1H 900, west), ELV-19 (In-1H 1100, north skew), "
            "ELV-20 (In-1H 1100 with a 2250 frame, TP annex)")
        p["library_ref"] = "library/windows/window_types.json ELV-08/09/10/18/19/20"
    if p["id"] == "P40_Arktos":
        p["legend_item"] = ("ID 27 (attachments, RAL 7021 like the housings) 6 Arktos boxes kept as geometry WITHOUT "
                            "emission (not booklet luminaires, sheet 38 shows them unlit)")
d["parts"].append({
    "id": "P42_Lights", "part_class": "other",
    "sources": [{"kind": "pdf", "reference": "booklet sheets 33-35 (lighting facades + plan L1), 40 (equipment) -> "
                 "parts/lighting_layout_v001.json (498 fixtures in 63 runs / points)"}],
    "legend_item": "housings ID 27 (RAL 7021); glow faces ID 28 purple, 29 2700K, 30 2000K, 31 4000K (LINE + DECO), "
                   "32 RGB static warm white (FOCUS, PLAT-A4), 33 3000K (TUBE M); colour in Diffuse, ERM R = emission "
                   "strength only on 28-33. Lines as continuous strips per drawn run (30 x 40), cut around anything "
                   "proud of the wall; points as boxes; all open-backed 8 mm off the wall. Sections assumed (sheet 40 "
                   "gives lengths only).",
    "operation": "primitive", "triangle_budget": {"npm": 0, "vpm": 6000}, "build_as": "box"})
d["status"] = "draft"
d.setdefault("history", []).append("v002 2026-11-04: + P42_Lights, P27 single doors from library ELV-18/19/20")
json.dump(d, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("WROTE", OUT, len(d["parts"]))
