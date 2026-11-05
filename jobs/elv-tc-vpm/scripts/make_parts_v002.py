"""elv-tc-vpm: parts v002 = v001 + Gate 1 confirmation (user, 2026-11-04) + Q1 change (F50 caps are geometry).

uv run python jobs/elv-tc-vpm/scripts/make_parts_v002.py
Reads parts/pilot_IA_parts_v001.json, writes parts/pilot_IA_parts_v002.json (never overwrites), validates it with
the dt_ai PartsList model (dt_ai.core.models.PartsList).
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.core.models import PartsList  # noqa: E402

JOB = ROOT / "jobs" / "elv-tc-vpm"
src = JOB / "parts" / "pilot_IA_parts_v001.json"
out = JOB / "parts" / "pilot_IA_parts_v002.json"
if out.exists():
    raise SystemExit(f"output exists: {out}")
d = json.loads(src.read_text(encoding="utf-8"))
v2 = copy.deepcopy(d)
v2["status"] = "confirmed"
v2["gate1"] = {"actor": "Artem (user)", "date": "2026-11-04", "scope": "project",
               "note": "Gate 1 of pilot И-А parts v001 confirmed in chat 2026-11-04 with one change: F50 mullion/"
                       "transom caps are geometry, not texture (Q1). All other questions resolved as recommended "
                       "(jobs/elv-tc-vpm/TASK.md, Gate 1 paragraph)."}
v2["sources"][3]["reference"] = ("jobs/elv-tc-vpm/TASK.md decisions 2026-11-04 (D01-D14, D16 accepted as recommended); "
                                 "Gate 1 confirmed by the user 2026-11-04 (F50 caps = geometry)")
P = {p["id"]: p for p in v2["parts"]}

P["P05_CW_Upper"]["legend_item"] = (
    "ID 12 F50 frame + ID 13 stemalit RAL 5024 (sheet 18 'стемалит RAL 5024', 'ALT F50'), frames RAL 7021 (Gate 1); "
    "op: relief over the CW base line: F50 mullion/transom caps as GEOMETRY [Gate 1 Q1] - simple boxes 50 mm wide, "
    "20 mm proud of the frame plane, quads, welded into one relief (no overlaps, no back faces); one recessed cell per "
    "glass panel (cap sides 35 mm down to the glass plane), stemalit cells as faces ID 13 10 mm behind the frame "
    "plane; glass in P20 [D06]")
P["P05_CW_Upper"]["triangle_budget"] = {"npm": 0, "vpm": 7000}
P["P06_CW_Lower"]["legend_item"] = (
    "ID 12 F50 frame + ID 13 stemalit RAL 5024, frames RAL 7021 (Gate 1); op: as P05 - F50 caps as geometry boxes "
    "50x20 mm welded in the relief [Gate 1 Q1]; door cells recessed to the door plane with reveals ID 6 (P09); "
    "glass in P20")
P["P06_CW_Lower"]["triangle_budget"] = {"npm": 0, "vpm": 3000}
P["P07_EntranceNiche"]["legend_item"] = (
    "ID 2 metal cassette RAL 7021 returns + ID 12/13 back CW ELV-16 with F50 caps as geometry (as P05, Gate 1 Q1); "
    "reveal faces of the door and revolving-door openings ID 6 (grey) [TASK reveals]; op: niche walls from the plan "
    "outline, back CW as P05")
P["P07_EntranceNiche"]["triangle_budget"] = {"npm": 0, "vpm": 1500}
P["P10_Ribs"]["legend_item"] = (
    "ID 17 ribs RAL 1001 (sheet 18 'ламели, метал. панели с фактурой дерева, цвет сосна, RAL 1001') [D05]; op: one "
    "box per rib extruded from its F50 mullion cap (430 mm from the frame plane, 50 mm), welded into the P05 relief, "
    "no back face")
P["P10_Ribs"]["triangle_budget"] = {"npm": 0, "vpm": 2500}
P14 = P["P14_FlushDetails_Texture"]
P14["sources"] = [s for s in P14["sources"] if "F50 caps" not in s["reference"]]
P14["legend_item"] = ("ID 2/3 joint grid, ID 18 flush flashings (incl. the CW base flashing RAL 5024, Gate 1); op: "
                      "baked into texture, reg p.32 §7 (<= 5 cm). F50 caps are NOT here any more: geometry in "
                      "P05/P06/P07 [Gate 1 Q1]")
P["P20_MainGlass"]["legend_item"] = (
    "MainGlass, clear (sheet 18 'стекло закаленное типа триплекс, прозрачное нетонированное') [D11, WIN-11..14]; op: "
    "one quad per panel in the P05/P06/P07 cells (arcs keep their facets, D172), 15 mm behind the frame plane "
    "(35 mm behind the F50 cap face), edges 10 mm under the frame, UV in 1001")
P["P04_Soffit_Canopy"]["legend_item"] += "; confirmed at Gate 1: soffit and niche ceiling wood ID 19 RAL 1001"
P["P08_RevolvingDoor"]["legend_item"] += "; Gate 1: height 2.72 (niche transom line), library ELV-17"
P["P13_BaseFlashing"]["legend_item"] += "; Gate 1: the flush CW base flashing ('RAL 5025' in FBX) is RAL 5024 (texture, P14)"

for j in v2["joints"]:
    if set(j["parts"]) == {"P10_Ribs", "P05_CW_Upper"}:
        j.update(decision="weld", reason="each rib is the outward extrusion of its F50 mullion cap (Gate 1 Q1: caps "
                 "are geometry); welding avoids coplanar rib/cap sides", extra_edges=0)
        j.pop("embed_depth_m", None)
    if "P20_MainGlass" in j["parts"]:
        j["reason"] = ("glass 15 mm behind the frame plane (35 mm behind the F50 cap face), edges run 10 mm under the "
                       "caps (inset-glass-trim, docs/methods/windows-glazing/WHEN.md: 0 overlaps on KPP1)")

answers = [
    "Confirmed by the user 2026-11-04 (TASK.md Gate 1).",
    "User 2026-11-04: GEOMETRY, not texture. F50 caps are simple boxes 50 mm wide, 20 mm proud of the frame plane, "
    "quads, welded into the CW relief without overlaps (P05/P06/P07); budgets raised accordingly.",
    "Accepted as recommended: soffit under the cantilever +4.70 and the niche ceiling built as wood ID 19 RAL 1001.",
    "Accepted as recommended: revolving door height 2.72 (niche transom line); library type ELV-17.",
    "Accepted as recommended: RAL 5024 (D13), flush, texture (P14).",
    "Accepted as recommended: F50 frames RAL 7021.",
    "Accepted as recommended: the 34 m south return is in the pilot.",
    "Accepted as recommended: sign frames 20 mm off the facade, no brackets.",
    "Budget raised for the F50 caps as geometry (P05 7000, P06 3000, P07 1500, P10 2500); pilot total 24 700 of 40 000.",
    "Accepted: facade lighting is a separate part after the pilot.",
]
for q, a in zip(v2["questions"], answers):
    q["answer"] = a
v2["questions"][0]["text"] = "Gate 1 (parts list) user confirmation."
v2["questions"][8]["text"] = v2["questions"][8]["text"].replace("15 900", "24 700 (v002)")

model = PartsList.model_validate(v2)
total = sum(p.triangle_budget.vpm for p in model.parts)
out.write_text(json.dumps(v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OK {out.name}: {len(model.parts)} parts, {len(model.joints)} joints, status={model.status}, "
      f"vpm parts total {total} / {model.triangle_budget.vpm}")
