# Roof equipment: delivered-model form study and first library (#1257)

## Scope, decision and status

Research, not a new OKS delivery. [D264] records Artem's answer on card `t_d0a92d95`
(2026-11-12, 14:37): a delivered NPM/VPM **pair is not needed**; use the available profile,
record it, and count Garibaldi `_01`/`_02` as separate objects. The five study units below
are **five delivery exports / four addresses**, not five unrelated architectural commissions.
G02 and VOL each contain two OKS meshes. No other profile is invented.

The study produced a measured **form inventory**, rules proposal, and 12 clean source-derived
form prototypes. It does **not** claim a certified MEP schedule: a cap, shaft body, hood frame,
pipe branch or railing segment is a geometric component, not necessarily one installed device.
Functional names such as aerator/vent/fan are visual candidates unless a project source says so.
This distinction matters: merging source components into guessed devices would invent counts.

- Native application: agent-owned Blender **5.1.2**, factory-empty scene, FBX import in metres;
  background processes only. No live Max, Blender document, bridge or user preferences touched.
- Readback: five original exports hashed, copied, imported, then original/copy hashes checked
  again (10/10 unchanged). Source scenes were never saved. Native snapshots are diagnostic copies.
- Library: [common parent template](../library/TEMPLATE.md), [catalogue/README](../../library/roof_equipment/README.md).
  12 types / 24 profile files; common checker pass with 0 errors; public xView 24/24 exit 0.
- Engineering identity, project finish mapping and Artem's visual acceptance remain unconfirmed.
  `ready` is **library cleanliness**, never `passed=true` for a delivery.

## Frozen evidence and sample qualification

Evidence root: `G:/Мой диск/AGR-evidence/1257-roof-equipment/research-v002/`.
Successful library: sibling `library-v006/` (catalogue release v001).
Final native receipts supplement: sibling `verification-v003/`; the raw research snapshot stays immutable.
Both have SHA256SUMS; the repository contains only small text/index/code, no customer FBX,
BLEND, texture or render. `observations-final-v2.json` is the authoritative detailed research
snapshot; earlier `observations*.json` files are preliminary diagnostics, not competing counts.
`library/roof_equipment/observations.json` retains compact rows, exact member IDs, source
hashes and the hash/path of the complete context/unclassified list.

The historical delivery-export names and directory provenance support the profile labels;
this is **not a fresh SINTEZ pass or proof of a client's formal acceptance**. Garibaldi is the
#352 nominated etalon. Skolkovo also appears in the delivered UCX study
[`ucx-etalon-analysis.md`](ucx-etalon-analysis.md). Other profiles below are historical
export candidates under the mixed-profile research permission, not new project handovers.
Folder names indicate different author streams; individual authorship is not independently verified.

| ID | Delivery export, relative to `C:/Users/artsafro/Desktop/!3D viz/` | Observed profile | Surface triangles | UCX objects / triangles | Roof character |
|---|---|---|---:|---|---|
| G01 | `Alex_World/pravki/0707_Garibaldi_22/0707_Garibaldi_22_01.fbx` | NPM | 148186 | 0 / 0 in this FBX | Stepped residential flat roofs, repeated shafts, hoods, vents, ladders and rail sections |
| G02 | `Alex_World/pravki/0707_Garibaldi_22/0707_Garibaldi_22_02.fbx` | NPM | 124452 (73306 + 51146) | 0 / 0 in this FBX | Two residential OKS, repeated roof heads with different component assembly/detail |
| OLY | `Dima_Andrew/maps/SM_OlimpijskijPrKt_Vld_16_Str_4.fbx` | VPM | 282723 | See source inventory below | Large curved sports-building roof, many service ducts/boxes, round branches and screened units |
| SKO | `NTR/14_Skolkovo/itog/LP/0809_BolshoyBulvar_64_01.fbx` | NPM | 36005 | 0 / 0 in this FBX | Acoustic-screened industrial roof, steel supports/bracing, shaft boxes and access bridge |
| VOL | `NTR/6/0903_VolokolamskoeShosse_Vl_71_22_01.fbx` | NPM | 72629 (17672 + 54957) | 0 / 0 in this FBX | Two roof levels, sparse layered box heads and roof enclosure, not dense MEP detail |

Full input SHA-256 values, object names, UV layers, material slots, bounds and UCX totals are
in `observations.json` → `sources`, and each `<ID>/census.json` in the evidence root.
A file without UCX does not prove the original MAX or another delivery export has no collisions.
OLY's 916 imported UCX objects are counted separately; they are hidden in `surface-*.png`.
The earlier Cycles `roof.png`/`top.png` views did not hide UCX and are **not** the surface authority.

## How the measurements were obtained

1. Hash originals and copies (`stage.py`, `inputs.json`); import one copy per own Blender process.
2. Store every mesh's native triangle equivalent, world bounds, UV/material inventory and UCX prefix.
3. Candidate census: connected mesh components, exact-coordinate seam equivalence rounded to
   1e-5 import-world metres **for diagnostic grouping only**, upper 35% of each building's height.
   This does not alter the FBX or certify topology. Face indices remain tied to the source hash/object.
4. Component proof sheets group equal triangle counts and approximately equal XYZ extents (0.1 m
   bins), retaining **every member ID**. Manually read the forms; do not interpret the grouping as
   an engineering assembly or infer identity from a filename. The type applies to the visually
   checked representative's geometric family, not a confirmed manufacturer's model.
5. Proof-sheet base cutoffs: G01 263.2; G02 245; OLY 34; SKO 195; VOL 149 import-world metres.
   Components larger than 25 m or with any extent below 3 mm remain outside those component sheets.
   Whole-building surface roof/top views remain available for context. This is an upper-roof study,
   not an inventory of hidden/indoor services or lower facade attachments.
6. Count each candidate once: 1097 typed geometric components + 9877 context/unclassified
   candidates = 10974 candidates. Most context rows are upper facade/window/structure fragments,
   especially OLY; they are **not 9877 missing equipment devices**. Their IDs and explicit reason
   remain in the hash-pinned detailed snapshot. No semantic completeness claim is made for them.
7. Dimensions below are **import-world axis-aligned XYZ bounds**, not oriented device dimensions
   or drawing-verified sizes. A rotated square shaft has larger XY bounds. Large-coordinate FBX
   float32 precision and absent independent control dimensions limit millimetre interpretation.
   The library instead translates linear-transform/local-coordinate differences to the origin.

A complete MEP-device schedule or a universal frequency ranking would need source equipment
schedules and assembly ownership that these joined delivery meshes do not preserve. The first
library is consequently a **common-form starter set**, not a claim to recover every device brand.

## Drawings / source versus delivered geometry

| Source code | Project | Available primary source and actual depiction | Correspondence / limit |
|---|---|---|---|
| S0 | G01 / G02 | #352 names `LP_OKS_01_02_03_Ground.max` and these FBXs. No Garibaldi roof equipment drawing/schedule was established in its nominated folder. | Geometry is measured from the delivery copy. Roof heads are visible as actual meshes; their engineering role and drawing dimensions are unavailable, not invented. |
| S1 | OLY | `Dima_Andrew/АР.2_ Фасады_29.07.2026.pdf`, physical pages 5–8: facade elevations, roof datums +39.320 / +41.600 and upper screen/finish treatment. Native source-page images retained. | The facade album does not provide an itemised roof MEP schedule or independently map each duct/box. Do not call a closed cuboid an AC unit without more authority. Delivery top view exposes much more service geometry than the elevation. |
| S2 | SKO | `NTR/14_Skolkovo/001 - 26.05.2026 - Альбом/20226-АГК_Инженерный центр ПАО Сбербанк.pdf`, physical p.21: roof plan, labelled ventilation shafts, roof aerators, drains, walkway and railing; physical pp.15–16 text specifies acoustic louvre screen AIRO-SOUBD (or analogue). | Visually checked p.21: roof shafts are plan rectangles, aerators small circular symbols, access/railing and the metal roof/walkway have separate symbols. The delivery has 3 rimmed shaft bodies and 3 cap plates, an access bridge, block-mounted screen supports and cross bracing. The 76 post/block components are **screen structure, not 76 aerators**. There is no verified one-to-one mesh mapping for every drawn aerator/drain. |
| S0 | VOL | No roof equipment drawing/schedule was found in the selected `NTR/6` delivery folder. | Layered box heads and the roof enclosure are measured forms; fan/vent/hatch function is unconfirmed. |

Per-row drawing lookup in the typology is S0 for G01/G02/VOL, S1 for OLY, S2 for SKO.
`pdf-index.json` pins both albums by full SHA-256 and records the searched physical pages.
The evidence is the rendered page, not an OCR-inferred dimension. Available source albums
were not silently treated as drawings of a different address.

## UV, atlas, material IDs and collision construction

- G01 has one `Atlas_UV`, one material `M_Garibaldi_22_001_Main_1`, used slot 0.
  Its actual diffuse `maps/0707_Garibaldi_22_01.fbm/T_Garibaldi_22_001_Main_d_1.png`
  was visually read: 2048×2048 modular finish swatches, facade/window elements and a grille area,
  not an individually baked equipment photograph for each roof unit. A swatch is not an AGR ID.
- G02: one `UVChannel_1` and one material per OKS mesh. OLY: one `UVChannel_1` and one
  material on each opaque/glass surface mesh. SKO similarly has opaque and glass surface meshes;
  VOL has two opaque OKS meshes. Exact names are in the native inventories.
- The equipment is joined into the owning Main mesh, not named independently as reusable assets.
  Type counts/triangles come from explicit component face sets, never from the whole-OKS triangle count.
- Joined atlas exports preserve local material slot 0, **not** the original Multi/Sub AGR finish IDs.
  Those IDs are not recovered here. UV-layer presence alone does not prove atlas packing, texel
  density, correct finish placement or VPM map compliance; those checks are not claimed.
- OLY's imported UCX is a separate hull inventory, not one collision per service device. No
  equipment-specific UCX ownership is certified. Other sampled FBXs carry no UCX-prefixed objects.
  Roof equipment prototypes add **no guessed UCX**; integrate within the owning OKS collision policy.

## Typology measurements

`Components` counts the stated geometric form, not fully assembled equipment. All original
member IDs are retained in the compact index; native polygon lists and proof sheets remain on Drive.
The triangle column applies **only to the observed profile** in that row. The other delivery
profile is **not measured**; equal library profile meshes are not counterprofile source evidence.
S0/S1/S2 source depiction and its uncertainty apply to every row of the corresponding object.

| Evidence | Object / observed profile | Geometric form | Components | XYZ min..max (m, world AABB) | Triangles/component |
|---|---|---|---:|---|---:|
| G01-01 | G01 / NPM | access_ladder | 10 | 0.577..0.896 / 0.575..0.901 / 4.900..4.900 | 220..272 |
| G01-02 | G01 / NPM | capped_polygon_vent | 25 | 0.330..0.330 / 0.315..0.315 / 0.622..0.622 | 64..64 |
| G01-03 | G01 / NPM | flat_cap_or_shallow_box | 67 | 0.905..4.153 / 0.905..4.880 / 0.057..0.288 | 10..12 |
| G01-04 | G01 / NPM | hipped_hood | 8 | 1.941..2.333 / 1.977..2.422 / 0.500..0.500 | 152..152 |
| G01-05 | G01 / NPM | low_polygon_aerator | 20 | 0.374..0.374 / 0.357..0.357 / 0.182..0.182 | 40..40 |
| G01-06 | G01 / NPM | open_shaft_body | 39 | 1.165..3.740 / 1.166..4.469 / 1.164..3.601 | 8..8 |
| G01-07 | G01 / NPM | pitched_box_head | 12 | 1.275..1.907 / 1.276..1.908 / 1.400..1.494 | 20..20 |
| G01-08 | G01 / NPM | plinth_shaft_body | 6 | 2.086..2.106 / 2.087..2.107 / 1.508..1.673 | 24..24 |
| G01-09 | G01 / NPM | railing_or_handrail_component | 118 | 0.087..15.635 / 0.087..13.600 / 0.020..0.800 | 10..520 |
| G01-10 | G01 / NPM | rimmed_shaft_body | 8 | 1.422..1.773 / 1.456..1.774 / 1.100..2.100 | 24..32 |
| G01-11 | G01 / NPM | roof_enclosure_body | 5 | 11.438..16.929 / 12.373..17.439 / 4.627..4.819 | 184..304 |
| G01-12 | G01 / NPM | stepped_shaft_body | 3 | 2.383..2.388 / 2.787..2.795 / 2.690..3.098 | 34..52 |
| G02-01 | G02 / NPM | access_ladder | 10 | 0.565..0.575 / 0.887..0.896 / 4.856..4.900 | 204..220 |
| G02-02 | G02 / NPM | capped_polygon_vent | 24 | 0.330..0.333 / 0.330..0.333 / 0.622..0.622 | 130..130 |
| G02-03 | G02 / NPM | flat_cap_or_shallow_box | 40 | 0.906..3.789 / 0.905..4.345 / 0.150..0.716 | 10..12 |
| G02-04 | G02 / NPM | flat_capped_shaft_assembly | 18 | 2.048..3.784 / 2.005..3.784 / 1.431..2.935 | 44..76 |
| G02-05 | G02 / NPM | hipped_hood_top | 3 | 1.891..2.203 / 1.924..2.203 / 0.238..0.294 | 16..16 |
| G02-06 | G02 / NPM | hood_support_frame | 3 | 1.328..1.575 / 1.366..1.575 / 0.317..0.390 | 112..112 |
| G02-07 | G02 / NPM | hooded_shaft_assembly | 6 | 1.923..2.179 / 1.889..2.318 / 1.930..1.930 | 192..192 |
| G02-08 | G02 / NPM | low_polygon_aerator | 20 | 0.374..0.378 / 0.374..0.378 / 0.182..0.182 | 82..82 |
| G02-09 | G02 / NPM | open_shaft_body | 12 | 0.929..3.377 / 0.929..3.377 / 1.262..3.852 | 8..8 |
| G02-10 | G02 / NPM | pitched_box_head | 8 | 1.038..1.510 / 1.038..1.478 / 1.321..1.744 | 20..20 |
| G02-11 | G02 / NPM | railing_or_handrail_component | 32 | 1.336..11.099 / 1.217..10.905 / 0.020..0.800 | 12..918 |
| G02-12 | G02 / NPM | rimmed_shaft_body | 13 | 1.140..2.595 / 1.160..3.093 / 1.430..3.258 | 24..50 |
| G02-13 | G02 / NPM | roof_enclosure_body | 3 | 4.722..17.502 / 6.070..11.094 / 0.663..4.297 | 34..288 |
| G02-14 | G02 / NPM | round_vertical_stub | 26 | 0.051..0.502 / 0.051..0.502 / 0.520..1.800 | 34..34 |
| G02-15 | G02 / NPM | stepped_shaft_body | 6 | 1.615..3.425 / 1.358..3.056 / 1.875..2.900 | 30..48 |
| OLY-01 | OLY / VPM | box_fan_candidate | 1 | 0.333..0.333 / 0.348..0.348 / 0.400..0.400 | 64..64 |
| OLY-02 | OLY / VPM | hipped_hood_top | 15 | 1.269..2.319 / 1.199..2.319 / 0.239..0.312 | 6..6 |
| OLY-03 | OLY / VPM | roof_enclosure_body | 1 | 5.175..5.175 / 10.910..10.910 / 4.660..4.660 | 551..551 |
| OLY-04 | OLY / VPM | round_pipe_network | 6 | 0.335..4.931 / 1.637..4.523 / 0.240..3.995 | 216..1344 |
| OLY-05 | OLY / VPM | round_service_disc_or_stub | 24 | 0.100..0.914 / 0.047..0.911 / 0.100..0.587 | 96..114 |
| OLY-06 | OLY / VPM | round_transition_piece | 3 | 0.296..0.430 / 0.989..1.025 / 0.291..0.424 | 180..198 |
| OLY-07 | OLY / VPM | screened_service_enclosure | 9 | 3.089..3.119 / 2.546..9.206 / 3.238..3.276 | 90..258 |
| OLY-08 | OLY / VPM | service_duct_box_or_transition | 325 | 0.040..13.562 / 0.150..24.697 / 0.176..4.250 | 8..572 |
| OLY-09 | OLY / VPM | service_panel_or_frame | 7 | 0.066..2.500 / 0.426..1.080 / 0.380..2.426 | 8..24 |
| OLY-10 | OLY / VPM | shallow_roof_plate_or_plinth | 39 | 0.917..13.005 / 1.149..22.720 / 0.180..0.702 | 8..32 |
| OLY-11 | OLY / VPM | thin_service_network | 28 | 0.152..9.307 / 0.170..24.901 / 0.200..3.024 | 18..420 |
| SKO-01 | SKO / NPM | access_ladder_bridge | 1 | 1.076..1.076 / 1.233..1.233 / 4.730..4.730 | 670..670 |
| SKO-02 | SKO / NPM | flat_cap_or_shallow_box | 3 | 2.977..3.240 / 3.178..3.322 / 0.050..0.050 | 12..12 |
| SKO-03 | SKO / NPM | rimmed_shaft_body | 3 | 2.769..2.770 / 2.848..2.848 / 2.005..2.293 | 50..50 |
| SKO-04 | SKO / NPM | screen_cross_brace | 8 | 2.148..5.087 / 2.287..4.025 / 3.634..3.642 | 44..44 |
| SKO-05 | SKO / NPM | screen_support_on_block | 76 | 0.868..0.869 / 0.868..0.868 / 2.263..2.263 | 32..34 |
| VOL-01 | VOL / NPM | layered_box_head | 2 | 1.296..2.055 / 1.643..1.932 / 0.804..0.804 | 46..46 |
| VOL-02 | VOL / NPM | roof_enclosure_body | 1 | 7.646..7.646 / 5.266..5.266 / 1.895..1.895 | 42..42 |

## Rules proposal — evidence, not newly approved standards

No universal equipment minimum-size or per-device budget can be read from five joined exports.
The following are **starter allocations / choices for review**, subordinate to source fidelity,
BODY-F/G and the owning OKS budget. They do not modify domain rules, C35 or locked standards.

| Proposal | Supporting evidence rows | Consequence / limit |
|---|---|---|
| Use one clean source-derived mid form for both library profiles; measure the actual source profile separately. | [D264]; all five source rows; catalogue R01–R12 | Avoid a duplicate detailed VPM library solely because of the profile label. Do not claim unobserved source triangles. |
| Model the silhouette of shafts, raised heads, hoods, ducts, ladders and safety rails; do not replace them wholesale with texture. | G01-01/02/04/05/06/09; G02-01/07/08/11; OLY service rows; SKO-01/03 | These forms visibly project from the roof, and their source meshes carry real geometry. Integration still needs project source/visibility review. |
| Bake/texture fine grille perforations, panel seams, fasteners and small finish relief where they do not change the required silhouette. | G01 modular atlas + G01-03/06; OLY boxes/ducts | This is a modelling recommendation, not proof that every <=5 cm mechanical object may be deleted. The decorative-detail rule and C35 must not be expanded to all equipment. |
| No blanket 5 cm equipment deletion threshold. Retain thin visible safety/silhouette members, or explicitly approve their alternate representation. | G01-09 includes 20 mm-height rail fragments; G02 thin stubs; SKO-01 | Tiny component thickness is not the assembly's apparent size. 2 mm library spacing is hygiene, not a minimum equipment size. |
| Start simple shaft/cap modules near 8–52 / 10–12 triangles; reserve separate hood/support cost. | G01-03/06/08/10/12, G02-03/09/12/15, SKO-02/03 | Same initial allocation NPM/VPM per D264. Never close a source-open shaft or omit its cap without an assembly check. |
| Prefer a low-segment form where it preserves silhouette: aerator around 40 triangles, capped vent around 64 as first library candidates, not hard maxima. | G01-02/05 versus G02-02/08 (64 vs 130; 40 vs 82) | Different source meshes already implement similar forms at different costs. Topology inflation is not evidence of necessary VPM detail. Compare renders before reducing. |
| Budget ladders and railing by height/length/number of members, not one fixed per-type ceiling. | G01-01/09; G02-01/11; SKO-01 | Ladder examples 204–670 triangles and railing components 10–918. A short section must not be mistaken for a complete perimeter rail. R09/R10 are examples, not safety-design standards. |
| Ducts require shape-specific budgets; keep elbows/risers, texture sheet joints, do not assign every cuboid an AC identity. | OLY service duct/box/transition rows; R11/R12 | Straight box 12 and selected elbow 60 triangles are starting prototypes. Complex source networks are not required to fit 60 triangles. |
| Keep equipment supports distinct from ventilation devices in counts and placement. | S2 roof plan; SKO-03/04/05 | Screen columns on blocks (76 components) are not 76 vents. Acoustic screen is BODY/enclosure context, not a collection of guessed aerators. |
| Pack reusable components separately from a labelled showcase; keep neutral finish and source UV disclosure. | Library checker 24/24; xView 24/24; TEMPLATE | Integration into an OKS atlas/material system is a later project-specific operation, not inferred from a clean library file. |

Budget hierarchy remains: project mid-poly OKS target <=150000 triangles; derived NPM hard
limit <=150000; VPM regulation ceiling <=1000000 (BODY-F/G). These are **whole OKS**, not per
roof device. G01 is already near the shared target; adding equipment without reserving its
cost is not permitted by this research. No source delivery's old triangle total is a new waiver.

## First library and visual gate

R01 open shaft; R02 rimmed shaft; R03 plinth shaft; R04 stepped shaft; R05 flat cap;
R06 hipped hood; R07 low polygon aerator form; R08 capped polygon vent form;
R09 access ladder; R10 railing section; R11 rectangular duct elbow; R12 rectangular service box.
The shaft forms are intentional modular variations; roofs use bodies/caps/hoods in different
combinations. This selection covers the repeated Garibaldi forms and OLY's dominant service
geometry without inventing antennas, solar panels, skylights or named AC products.

No distinct solar array, antenna, skylight or lightning-protection assembly was **positively
identified** in this study. That is not a certified absence. Small round stubs/wires stay
morphological observations where no schedule resolves their function. The library does not
fabricate those missing engineering identities or add generic synthetic devices to reach 12.

All offered assets are exact selected source components after bottom-center translation and
exact split-vertex reunion; no source dimension/face was simplified or repaired. Source UV is
retained; local neutral ID 1 is disclosed and validated explicitly, not an unmapped-slot fallback.
Both profiles have measured triangle counts/sizes and native hash-pinned object/material lists.
The 6×2 sheet is rendered by Blender; cameras/labels exist only in the separate showcase file.
Artem should review **form usefulness**, grouping, neutral appearance and the starter set,
not read this sheet as an approved material/MEP design or one common display scale.

## Execution and verification receipts

- Original/copy hashes rechecked 10/10 unchanged after native inspection.
- Library native readback: 12 ready, 24 variants, 0 errors, no quarantine, delivery_certificate=false.
- Public `dt qa xview` on all 24 native exports, NPM-OKS / VPM-OKS, local coordinates:
  24 exit 0; raw per-asset reports retained in the final supplement `xview-v006/`.
- Fresh-process hostile builder probes: 8/8 rejected with nonzero exit and no output; source
  hashes unchanged. Cases: output=input, duplicate source, no sources, unsupported schema,
  NaN plan, unmapped material slot, unmapped source object, polygon outside source.
- Tests-first plan validation: commit 7e5295cc — 19 failed / 1 passed; validation then 20 passed.
- Tests-first showcase regression: commit 5e37da7f — 1 failed (Blender loader mutates a borrowed
  catalogue list into Object instances); list-copy fix passes. The failed native build/log is kept.
- Tests-first 8..12 inventory bound: commit 95314b56 — 4 failed / 8 passed; inclusive-bound fix passes.
- Focused data/plan/showcase tests and Blender-command documentation guard run before head freeze;
  exact final counts, full-suite head and eval receipts are in the PR, not fabricated in this note.
- Earlier native launch used MSYS `$PWD` and failed before output; retried with native C:/ paths.
  Attempt library-v001 then exposed catalogue mutation; v002 fixed it; v003 added two OLY forms;
  v004 froze those forms; the decision-reference guard then found a missing inline decision-ID anchor
  (1 failed / 94 passed). The metadata-only fix was rebuilt as v005. Pre-push allocation checking
  then found a concurrent D263 in PR #1272: this card renumbered its row to D264 and rebuilt
  metadata as v006. Forms are unchanged; v006 is the final checked offering. Earlier receipts
  keep their original hashes and are not relabelled successful current-head evidence.

Exact commands and retained drivers: `COMMANDS.md`, `stage.py`, `census.py`, `surface.py`,
`components.py`, `pdf_index.py`, `summarize.py`, `hostile.py`, `xview.py` in research evidence.
Production extraction/check commands are in the [library README](../../library/roof_equipment/README.md).
The reusable code is limited to `tools/library/roof_parts.py` and `build_roof_blender.py`;
the common template/checker and the production pipeline are unchanged.

## Limits to carry forward

- Morphological components are not a recovered engineering schedule; joined geometry and
  optional/missing drawings do not establish assembled-device counts or manufacturers.
- Upper-roof diagnostic band and geometric grouping are disclosed; context/unclassified rows
  remain explicit and must be inspected before reuse. This is not a semantic completeness certificate.
- Available historical exports do not establish independent authorship or fresh client acceptance.
- Finish IDs, complete atlas/texel QA, actual device/UCX ownership, lower hidden services and
  precise drawing-controlled dimensions are not silently inferred.
- Library cleanliness and xView are technical checks; Artem's visual acceptance and a future
  project's full delivery QA remain separate. No source scenes, locked standards or pipeline changed.
