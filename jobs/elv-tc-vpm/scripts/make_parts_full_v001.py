"""elv-tc-vpm: write parts/elv_full_parts_v001.json = accepted pilot parts (v002, unchanged) + the new parts of the
whole building, and validate it with dt_ai.parts.model.PartsList.

uv run python jobs/elv-tc-vpm/scripts/make_parts_full_v001.py      (from the repo root; never overwrites)
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
JOB = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(JOB, "parts", "elv_full_parts_v001.json")
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
sys.path.insert(0, os.path.abspath(os.path.join(JOB, "..", "..", "src")))
from dt_ai.parts.model import PartsList  # noqa: E402

pilot = json.load(open(os.path.join(JOB, "parts", "pilot_IA_parts_v002.json"), encoding="utf-8"))
REF = "outputs/ref-v002/ref_objects_full_v001.json + ref_sections_full_v001.json (clean reference, whole building)"
PEND = "Gate 1: pending (pattern of the accepted pilot И-А)."


def part(pid, cls, srcs, legend, op, vpm, build_as=None, lib=None):
    d = {"id": pid, "part_class": cls, "sources": [{"kind": k, "reference": r} for k, r in srcs],
         "legend_item": legend + " " + PEND, "operation": op, "triangle_budget": {"npm": 0, "vpm": vpm}}
    if build_as:
        d["build_as"] = build_as
    if lib:
        d["library_ref"] = lib
    return d


NEW = [
    part("P21_S_Facade", "wall", [("layer", "collection sandwich, south y -50.46 x -0.43..41.88"), ("region", REF)],
         "ID 1 sandwich RAL 7021 (sheet 19 legend 12, D02); op: relief over the outline (openings, reveals ID 6); "
         "SW sign frame 2.0x0.5 ID 16 (D09)", "contour_rebuild", 6000),
    part("P22_W_Facade", "wall", [("layer", "collection sandwich, west x -0.42 y -50.46..-19.95, step x -4.42"),
                                  ("region", REF)],
         "ID 1 sandwich RAL 7021 (facade А-И, sheet 19); op: relief over the outline", "contour_rebuild", 5000),
    part("P23_TP_Annex", "wall", [("region", "TP annex walls x -8.82 (y -2.46..-11.13) and y -11.13 (x -8.82..-4.42)")],
         "ID 5 TP annex paint RAL 7021 [D16]; ELV-11 doors (sheet 18); brick plinth 640 as plinth h 0.45",
         "contour_rebuild", 1500),
    part("P24_N_Facade", "wall", [("layer", "collection sandwich, north straight y 2.99 x 41.68..59.43 (to +15.42), "
                                            "skew 6.16 deg x -8.82..41.68"), ("region", REF)],
         "ID 1 sandwich RAL 7021 (facades 12-1 and 6-1, sheet 19); op: relief over the outline", "contour_rebuild",
         6000),
    part("P25_Plinth_Flashing_New", "band", [("layer", "collection plinth (Ins-100 face 0.20 proud), battens z 0.15-0.42")],
         "ID 4 plinth + ID 18 base flashing RAL 7021 (as pilot P03/P13); 1 m perimeter drop", "contour_rebuild", 3000),
    part("P26_Windows_New", "window", [("object", "(WN)_Blinds 1190x1500, Окно 2-Распашное, (WN)-RD_2H_Vendor Одностворчатое")],
         "ID 11 W72 RAL 7021 + MainGlass; ELV-01 x7, ELV-02 x3, ELV-03 x2, ELV-05 x2 in sandwich holes, reveals ID 6",
         "library_replace", 1500, lib="library/windows/window_types.json ELV-01/02/03/05"),
    part("P27_Doors_New", "door", [("object", "(DR)-2H Ext doors 1600/1200/2200x2050, In-1H 900/1100 on the facade")],
         "ID 14 metal doors RAL 7021; ELV-08 x6 (incl. the added north door x 38.4 [D14]), ELV-09 x2, ELV-10 x1; "
         "3 single doors without an ELV type (FBX bbox, open point)", "library_replace", 1500,
         lib="library/windows/window_types.json ELV-08/09/10"),
    part("P28_Gates_DockShelters", "door", [("object", "(DR)-LG Gate SPU 42 HORMANN, (SEQ)-DS_403M 3400x3400")],
         "ID 15 gates RAL 7040 [D10] ELV-12 x1 + ELV-13 x3; dock shelters DS_403M simplified U frames ID 26",
         "library_replace", 800, lib="library/windows/window_types.json ELV-12/13"),
    part("P29_Canopies_New", "slab", [("object", "Перекрытие (Ext)_metall kasset WOOD [25799101] [10493033]; fascias "
                                                 "(In)_25 at x 10.33-17.42 and 33.56-36.55")],
         "ID 19 canopy RAL 1001 (sheet 19 legend 11); 2 south canopies added per album [D14]; simple boxes",
         "primitive", 300, build_as="box"),
    part("P30_Lamellas_New", "decor", [("object", "rib_lamella (In)_25(DW-25.Fin-3) 29 pcs south / west")],
         "ID 17 lamellas RAL 1001 (sheet 19 legend 15); one box per lamella, back face deleted", "primitive", 600,
         build_as="box"),
    part("P31_Parapets_New", "parapet", [("region", "parapet top +13.92, inner face 0.40, cap +14.04, overhang 0.05")],
         "ID 18 caps (zone RAL 7021, D13) + ID 1 inner faces; as pilot P12/P15", "contour_rebuild", 3000),
    part("P32_Roof_Main", "slab", [("object", "Базовая крыша (Ext)_(Ins-115) ПО БЕТО (+11.92..+12.46)")],
         "ID 21 roof; flat +12.45 (source slope +12.1..+12.46 not modelled); grid of <= 3.9 m cells", "from_face", 6000),
    part("P33_Terrace", "slab", [("object", "Перекрытие эксплуатируемая кровля [67b0a5c] +11.46, [f41f575] +12.41; "
                                            "fence panels y -19.17")],
         "ID 23 terrace deck (lower pit +11.46, upper +12.45 east of x 50.65); sandwich screens ID 1", "from_face",
         1500),
    part("P34_Railings", "railing", [("region", "terrace fence (Сетка-Рабица) y -19.17, x 50.65; pit edge x 58.74")],
         "ID 20 metal RAL 7021; SIMPLE geometry default (posts + top rail, no infill) - geometry vs alpha open "
         "(TASK: decided together later)", "primitive", 1500, build_as="box"),
    part("P35_Skylight", "glazing", [("object", "Основание светоаэрационного фонаря, Системная панель С остеклением "
                                                "(roof, 37.84..62.96 x -27.94..-19.58)")],
         "ID 12 frame + MainGlass; hipped 25.12 x 8.36, eave +12.75, ridge +13.65; ridge/hip/rafter boxes 60x60",
         "contour_rebuild", 2000),
    part("P36_Superstructures", "superstructure", [("region", "T1 x 47.8..59.40 y -1.5..2.99 to +15.42, T2 x 47.8..53.0 "
                                                              "y -11.45..-6.2 to +16.22, pit walls")],
         "ID 1 sandwich + ID 12/MainGlass glazing + ELV-06 doors; flat tops ID 21 (inner roof wells closed)",
         "contour_rebuild", 6000),
    part("P37_RoofBoxes", "superstructure", [("region", "roof_clusters.py: 26 shafts/exits, 16 KPN-S cups, curbs, stair")],
         "ID 22 roof structures RAL 7021; bbox boxes (simplified)", "primitive", 3000, build_as="box"),
    part("P38_FireLadders", "rod_ladder", [("region", "booklet sheet 19: north 6-1 at axes 7 and 4, west near Ж-И")],
         "ID 20 metal RAL 7021; simplified: 2 stringers + rungs every 0.35 + brackets (no cage); geometry vs alpha "
         "open with the railings", "primitive", 4000, build_as="box"),
    part("P39_Downpipes", "decor", [("object", "(SEQ)-G_Gutter_mini at the canopies")],
         "ID 20 metal; 100x100 boxes canopy -> ground", "primitive", 100, build_as="box"),
    part("P40_Arktos", "other", [("object", "(AT)-SG_ARN_Arktos_External 6 pcs")],
         "ID 27 lights kept as simple boxes (TASK lights; _Light.fbx later by the user)", "primitive", 100,
         build_as="box"),
    part("P41_Joints", "wall", [("region", "pilot joints x 41.85/41.88 south, x 59.40/59.43 north")],
         "returns / end faces between the accepted pilot and the new facades (ID 2/3/1/18/19)", "contour_rebuild",
         100),
]
d = dict(pilot)
d["object_id"] = "SM_Elevatornaya_1A"
d["status"] = "draft"
d["triangle_budget"] = {"npm": 0, "vpm": 150000}
d["parts"] = pilot["parts"] + NEW
d["sources"] = pilot["sources"] + [
    {"kind": "model", "reference": "jobs/elv-tc-vpm/outputs/build-v001/elv_pilot_IA_v001.blend (pilot И-А accepted "
                                   "2026-11-04, imported unchanged)"},
    {"kind": "pdf", "reference": "booklet sheet 19 (facades 12-1, А-И, 6-1: fire ladders, added north door)",
     "page": 19, "sha256": pilot["sources"][2]["sha256"]}]
d["gate1"] = pilot["gate1"]
d["gate1"] = dict(pilot["gate1"], note=pilot["gate1"]["note"] + " Applies to P01-P20 only; P21-P41 pending.")
NJ = [("P21_S_Facade", "P02_MetalBase", "weld", "returns J1 at x 41.88; plinth/flashing continue (pilot end caps removed)", 6),
      ("P21_S_Facade", "P01_WoodVolume", "weld", "wood end face J2 at x 41.85", 3),
      ("P24_N_Facade", "P01_WoodVolume", "weld", "wood end face J7 at x 59.40", 3),
      ("P31_Parapets_New", "P12_ParapetCaps", "weld", "cap ends J4/J5/J8 at the joints", 6),
      ("P32_Roof_Main", "P15_RoofEdge", "weld", "roof grid meets the pilot roof strip edge", 20),
      ("P36_Superstructures", "P15_RoofEdge", "weld", "T1 east face at x 59.40 on the pilot roof edge", 4),
      ("P26_Windows_New", "P22_W_Facade", "embed", "library window in a body hole", 4),
      ("P29_Canopies_New", "P21_S_Facade", "embed", "canopy slab enters the facade", 4),
      ("P30_Lamellas_New", "P21_S_Facade", "embed", "lamellas, back face deleted", 58),
      ("P34_Railings", "P33_Terrace", "embed", "posts stand on the deck, bottom faces deleted", 0),
      ("P38_FireLadders", "P24_N_Facade", "embed", "brackets enter the wall 10 mm", 16),
      ("P37_RoofBoxes", "P32_Roof_Main", "embed", "boxes stand on the roof, bottom faces deleted", 0)]
d["joints"] = pilot["joints"] + [
    {"parts": [a, b], "decision": dec, "reason": r, "extra_edges": e, **({"embed_depth_m": 0.01} if dec == "embed" else {})}
    for a, b, dec, r, e in NJ]
d["questions"] = pilot["questions"] + [
    {"audience": "user", "text": "Gate 1 for the new parts P21-P41 (whole building).",
     "answer": "pending (pattern of accepted pilot)"},
    {"audience": "user", "text": "Railings and fire ladders: simple geometry (posts + top rail; stringers + rungs) or "
                                 "alpha planes?", "answer": None},
]
PartsList.model_validate(d)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("PARTS", OUT, len(d["parts"]), "budget", sum(p["triangle_budget"]["vpm"] for p in d["parts"]))
