# AC04 — Gate 1 material proposal

**Building (native DWG title):** «Локальные очистные сооружения поверхностных сточных вод».
Job `tec26-oks`, issue #561. Base `origin/main` at intake and resume:
`442f0b695a91f9abc180783c26978fbe85fefcf9`.
**Gate 1: `approved-gate1` (Artem, 2026-10-22, orchestrator relay). `delivery_passed` remains false. Technical QA and publication are separate.**
Only paint is approved. Geometry, topology, UCX and multisub IDs stay exactly as in the source scene. VPM/NPM (UDIM/atlas) of this building are built by a separate build card, not here.

## Sources and precedence

Hash-verified frozen copies: `C:/x/tec26-oks/AC04/sources-v003/`.
Full names, bytes and SHA256 are in `materials.json`; local `SHA256SUMS.txt` accompanies the copies.

| Input | SHA256 | Role |
|---|---|---|
| `22E56-АР2-1002-AC.04_R1.dwg` | `d34638d96ea51046e25b0376f4cd589c0725aeb15f2bccc4800ab3716b1a409b` | Governing finish/colour source, per orchestrator comment on this card, 2026-10-22 |
| `22Е56-АР2-1002-АС.pdf` | `97e324176ffc6c078f27849e98a08b530cbd1d07ddb3fe71b5fe66754dc1ccfe` | Supplemental plans, roof, section; one physical PDF page, printed sheet 2 |

The prior card comment called the DWG sheet 2. **Native readback corrects this:** layout `1`,
`E42B5` at (596.775, 23.6754) is sheet **1**, `E42BD` at (614.088, 23.5147) is the
**total of 2 sheets**. Title entities `E42B7/E42B8` at (508.101,28.4873)/(513.458,24.477)
name this building; `E4341` at (540.153,12.4066) names facades A–В, 1–2, В–A, 2–1 and colour solutions.
Coordinates here are layout millimetres; model coordinates below are drawing millimetres.

AutoCAD 2025 core console, `ACADVER=25.0`, `INSUNITS=4` (mm), opened the authorized copy
read-only through `dcc_batch.py acad --card t_ca2df933`. Native `entget` text readback contains
104 lines including header, title and legend; no extraction error, completion sentinel present.
`native-text-v002.txt` and full `native-run-v002.json` are in the evidence bundle.
Desktop originals remain hash-identical. The AutoCAD-opened v001 working DWG changed to
`253bdb2a9e2e2ddc64d79550b9e56f41035d3d025e1457947cb9e5ac5c4d2b75` after the session;
its bytes are NOT claimed preserved. The wrapper exit 0 did not prove immutability.
The native log shows `_QUIT`, `_N` and the discard prompt; the exact reason for copy mutation is
not established. A fresh v003 package was copied from the original and verified without another DCC open.
Native evidence records text from the original-revision working copy, not a certificate of the resulting DWG.

### Drawing facts and locators

| Evidence | Locator | Reading |
|---|---|---|
| Colour legend | DWG sheet 1; Model `170B10`, XY (52042.211,11555.882) | Sandwich panels and canopy RAL5015; porches/doors RAL7004; metal stair guards RAL1021 |
| Wall construction | Same DWG Model `170A72`, XY (51016.072,5498.213) | Three-layer sandwich panels, mineral-wool basalt infill, 150 mm |
| Enclosure note | Same DWG Model `B59E8`, XY (51016.072,3867.977) | Metal enclosing structures, 100 mm |
| Facade views | Model `1523A0..1523A3`, XY approximately (26073,55936), (26051,42344), (5257,55936), (5235,42344) | Own AC04 facade colour drawings; blue enclosure, yellow safety rail, grey entrance |
| Roof plan | Model `1A06DD`, XY (28962.926,-3242.342) | Roof plan heading; plan geometry supplementary, not a separate proven roof finish schedule |
| Plans / section | PDF physical page 1 / printed sheet 2; top-left plan, top-centre roof plan, top-right section 1–1 | Wall/roof sandwich construction shown; 120 mm appears in section callouts; not a finish override |
| PDF legend | Same page, lower centre, pixel region roughly x1870–2430,y1300–1600 in `pdf-sheet2.png` (3572×1684) | Sandwich with basalt mineral wool; metal enclosure 100 mm; reinforced concrete slab; reference marks |

`dwg-ac04-recovered.png` is a **diagnostic rendering of recovered DXF**, not a native plot certificate:
original DXF lacked ENDSEC; `ezdxf.recover` returned zero audit errors, with proxy SHELL face-colour warnings
when rendering. Native extraction independently verifies the actual text. Rendering shows no verified
joint-module dimension. White construction lines are not evidence of RAL9016 or perforation.
Other model-space template groups at x128000–222000 (legends `114EE3/114EE5`, `135AE3/135AE5`,
facades A–Б/Б–A) are excluded: they are not this object's A–В/В–A facade group.

**Dimension discrepancy retained:** DWG 150 mm vs PDF 120 mm. Orchestrator resolved its workflow impact:
existing mid-poly scene geometry is final; this card only proposes textures. No geometry correction
or silent drawing reconciliation. No unrelated standards conflict is decided here.

## Scene readback

Reuse #558 census `C:/x/tec26-oks/census/oks.json` and its existing `geometry-174.json` buffer;
no extra Max session, live scene access or reread of other buildings was needed.
Max 2026.3 census, metre system units, 1 unit/m, Z up. Source file version 26000.
`materials.json` pins hashes of scene copy, census and geometry.

Actual layer **004**, mesh **АС.04**, handle **174**, `Editable_Poly`, Multi/Sub **Material #35**.
2462 vertices, **2552 polygon faces / 5006 snapshot triangles**. UV channel 1 present.
Source IDs remain intact; these are not delivery SlotNumbers, UDIMs or the KPP IDs.
Empty Multi/Sub slots **6–10** have no material and no assigned faces; they stay empty.
17 collision meshes: handles **346–362**, same layer; all retained in the census inventory,
not included in finish-area sums or textured. UCX acceptance is not certified by this material report.

## Approved ID mapping

**Gate 1 paint is approved. Rows are not a delivery pass**, and source diagnostic colours still do not prove RAL.
Areas are snapshot triangle areas in m², not a facade bill of quantities.
`only-N.png` isolates the actual face set for each ID. Blender **5.1.2 Workbench** native renders
use the census world vertices without changing geometry; each image pairs depth-correct ID colours
with a plain shaded view from the same orthographic camera. UCX are excluded. The diagnostic perimeter
line is at **±0.000 m**, not a geometry cut. No .blend or delivery model was saved.

| ID / source material | Polygon faces / triangles | Area m² | Geometric reading | Approved finish | Map type | Evidence / limits |
|---|---:|---:|---|---|---|---|
| 1 / `1` | 439 / 780 | 179.668028 | Outer structural strips/enclosure, roof, canopy and deep base | Mixed, same ID: roof and frame/carcass RAL7004; wall panels RAL5015 with vertical joints; below-grade drop RAL5015 plain. Face groups unresolved | mixed | `170B10`, `only-1.png`; regions below. Geometry JSON does not label these parts |
| 2 / `Material #36` | 19 / 38 | 82.702408 | Broad recessed wall-panel infill | Sandwich RAL5015, vertical joints only | vertical_joints | `170B10`, `only-2.png`; Q4 closed by joint_spec |
| 3 / `Material #37` | 2 / 4 | 0.238398 | Two small panes in the openings | `M_Glass_01`, NPM opacity 0.5, glass as KPP | glass | `only-3.png`, KPP glass policy; not a RAL claim |
| 4 / `Material #38` | 166 / 332 | 2.934883 | Door and small opening frames | RAL7004, including small frames | metal | `170B10`, `only-4.png`; Q3 closed. KPP grey tile 1010 |
| 5 / `Material #39` | 1926 / 3852 | 24.248557 | Roof railings, ladder/cage assembly | RAL1021 | metal | `170B10`, `only-5.png`; railing geometry is already present, no alpha/perforation map invented |

### ID1 regions (paint only)

Artem allowed different colours inside one multisub ID via UV/atlas regions or face groups, without changing geometry. `geometry-174.json` stores vertices, triangles and `material_ids` only, so none of the four parts is an existing face group. Each region is `faces: unresolved` until a face-index or UV-island list already in the evidence names it. Counts and the multisub id stay as read.

| Part | RAL | KPP tile | Why the faces stay unresolved |
|---|---|---|---|
| roof | 7004 (same SHA as ID4, tile 1010) | `T_Kpp_1_Diffuse_1.1010.png` | Upward ID1 triangles sit at several heights (about 0.238, 2.397, 3.227, 3.240, 3.387, 3.419 m) and are not labeled roof |
| frame/carcass | 7004 (same tile 1010) | `T_Kpp_1_Diffuse_1.1010.png` | No frame/carcass subset inside material id 1. ID2 is a different material |
| wall panels | 5015, vertical joints only (`joint_spec`) | `T_Kpp_1_Diffuse_1.1013.png` is colour only | No wall-panel subset inside ID1. Recessed infill is already ID2 |
| below-grade drop/plinth | 5015, wall colour, plain, no joints | `T_Kpp_1_Diffuse_1.1013.png` | 48 ID1 triangles cross z=0, so the drop is not its own face set. `perimeter-drop.json` checks wall bottoms and does not list face indices |

**Perimeter drop resolved by Artem (orchestrator relay, 2026-10-22):** retain the part below ±0.000
in both VPM and NPM; use the same finish as the adjacent wall, not a separate new ID. For AC04
that wall colour is RAL5015, and below ±0.000 it is plain colour with no joints
(«ниже ±0.000 без швов (под землёй не видно)»). The former Q2 about a separate plinth finish is withdrawn.
Which ID1 faces are only the drop is still unresolved (see the region table).
`perimeter-drop.json` checks all four external shell wall planes: their bottom-edge intervals cover
the full wall length at z ≤ −1.0 m (coordinate grouping tolerance 0.0001 m); minima are
−2.003179 to −2.003180 m. **4/4 walls verified.** No cutting, extending, renumbering or fallback assignment. No independent roof membrane brand, frame RAL9016,
perforation, cassette module or hidden interior finish is inferred from KPP.

### KPP colour identity

Use exact existing KPP pixels, not a newly sampled PDF or a new RAL conversion:

| RAL | Exact sRGB byte triplet | Existing `maps_kpp` Diffuse tile | Reuse |
|---|---|---|---|
| 5015 | 34,113,179 | `T_Kpp_1_Diffuse_1.1013.png` | Colour reference only for the blue panels. Joints come from the user texture, not from this tile or from cassette 1007 |
| 7004 | 150,153,146 | `T_Kpp_1_Diffuse_1.1010.png` | Door, porch and ID4 frame grey; same tile for the approved ID1 roof and carcass colour |
| 1021 | 238,201,0 | `T_Kpp_1_Diffuse_1.1004.png` | Stair yellow |

All pixels in each selected solid tile were checked; SHA256 is on each single-colour material and on each ID1 region.
KPP names/UDIM references come from `jobs/KPP1/materials.json` and `scripts/vpm_textures.json`.
These are the existing project's approximate sRGB RAL representations, **not calibrated physical RAL**.
No KPP cassette scale is transferred. Glass uses the named KPP-style material and constant NPM opacity;
VPM separation/no-map constraints remain for the later build, not certified here.

Whole-texture mean versus KPP 5015 is delta approximately (−0.297, −0.990, −1.572), max abs 1.572,
inside tolerance 2.0. The non-joint field mean is about (34.004, 113.008, 179.014); the joints
(RGB 12, 40, 63) pull the whole-image mean down to the rounded (34, 112, 177).

## RAL5015 vertical joints (supersedes Gate-1 point 1)

Live rule for ID1 wall panels and ID2. Roof and frame/carcass stay RAL7004 with no panel joints.
ID5 stays RAL1021 with no panel joints. Geometry is untouched on this card.

Artem, later than Gate 1: «Панели неверные, должны быть вертикальные швы только; текстуру пришлю; если не влезает, можно аккуратно порезать через loop или ring» and «ниже ±0.000 без швов (под землёй не видно)».

| Rule | Value |
|---|---|
| `map_type` | `vertical_joints` |
| orientation | vertical only; no horizontal joints |
| step | `joint_spec.per_facade`, measured on this building's own colour sheet. No fixed module. The texture period is not a fallback |
| joint width | 8 mm |
| texel | 1000 px/m (KPP VPM on a 4K UDIM). A 0.20 m step is about 200 px. NPM atlas joints at least 1.5 px |
| phase | symmetric in the panel field, not from tiling the source |
| below ±0.000 | plain colour, no joints |
| source | `C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png` |
| SHA256 | `2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece` |

Measured on that file (PIL/numpy): 4096×4096 RGB, 1010080 bytes, mean RGB (33.703318, 112.010291, 177.427655), rounded (34, 112, 177). Seven vertical joints, each 8 px, period 600 px, x0 at 266, 866, 1466, 2066, 2666, 3266, 3866. No horizontal joint run. 4096 is not a multiple of 600, so the image does not wrap. It is the colour, noise and one-joint profile only. It is not a tiling source. The build lays joints out per facade.

### Per facade (measured, not invented)

Source: recovered `C:/x/tec26-oks/acad-readback-v001/ac04.dxf` (`ezdxf.recover`, the file has no ENDSEC, auditor errors 0, fixes 1). Titles from `native-text-v002.txt`. Model units are millimetres. The census folder has no DXF; this is the readback the gate-1 diagnostic plot used. No facade on this sheet has one even rib step across its whole blue panel field, so every entry is `unresolved`. `gate_1_status` stays `approved-gate1`. `joint_report.unresolved_facades` lists them. The build must not invent a count.

| Facade on the sheet | Field | What was counted | Evidence |
|---|---|---|---|
| Фасад А-В. Цветовое решение | blue hatch `17BA5A`, 14.238923 m × 3.456626 m, XY mm (2467.96, 48891.24)–(16706.89, 52347.86) | not one even step. 1.00203 m repeats in two separate runs only | TEXT `1523A2`; insert `184E3E`; lines `17BA52`…`17BA54` and `17A794`…`17A796` |
| Фасад 1-2. Цветовое решение | blue hatch `1854A2`, 2.96608 m × 3.26517 m, XY mm (29011.58, 48892.45)–(31977.66, 52157.62) | no repeating interior rib. Outer edges and two returns about 0.288 m | TEXT `1523A0`; insert `184E70`; lines `185588`, `185589`, `18558B`, `18558A` |
| Фасад В-А. Цветовое решение | blue hatch `17D200`, 14.238923 m × 3.456626 m, XY mm (2468.79, 35300.83)–(16707.72, 38757.45) | mirror of А-В; 1.00203 m in two runs, not one grid | TEXT `1523A3`; insert `185AD0`; lines `17D321`…`17D329` and `17E599`…`17E595` |
| Фасад 2-1. Цветовое решение | blue hatch `185FC2`, 2.96608 m × 3.26517 m, XY mm (29011.58, 35300.83)–(31977.66, 38566.00) | no repeating interior rib. Centre is the yellow stair hatch `13CAC5` | TEXT `1523A1`; insert `185AD6`; lines `186017`, `186018`, `185FDA`, `18601A`, `186019` |

Horizontal joint lines inside those fields: none. The bottom outline is a grey strip, true colour `0x9B9B9B` (155, 155, 155), 24.77 mm, handles `17BA5D` (А-В), `17D1FF` (В-А), `185FC1` (2-1). On Фасад 1-2 the grey hatch `1854A3` (2969.9 × 2328.86 mm) is the door fill and starts 24.8 mm below the blue field. Legend `170B10`: doors RAL7004, sandwich panels RAL5015, stair rails RAL1021. The drawn blue is RGB (0, 124, 176), true colour `0x007CB0`, which is the sheet blue for RAL5015, not the KPP byte triple. No taller plinth course is drawn. Corner returns sit about 0.288 m in from the outer edges.

The exact questions are on each `per_facade` entry.

### Acceptance picture

The build card places each facade render next to the same facade of this sheet, at the same scale, with the rib count written under both. A render whose rib count differs from the sheet count is not sent to Artem. This Gate-1 card does not make that picture.

### Geometry

No new cuts are needed for a 0.20 m step when the UV of a face lies in one 4K tile (4096 px at 1000 px/m covers 4.096 m). A ring cut or an edge loop is allowed only where a face still does not fit one 4K tile, and that cut is reported in the build card. This card does not cut geometry. Quads, silhouette, normals, UCX and multisub IDs stay.

## Gate-1 approval (verbatim)

Source: orchestrator relay of Artem, 2026-10-22 («Принимаю»).

1. Sandwich panels: solid colour without joints (module not confirmed by the drawings). **Superseded** by the vertical-joint rule above. This line is the Gate-1 wording, not the live panel rule.
2. Roof: RAL 7004 grey (as KPP 7004), not 5015.
3. Mixed ID: allowed to paint parts differently (roof 7004, frame/carcass 7004, plinth/drop = wall colour) WITHOUT changing geometry - via UV/atlas regions or splitting face groups inside the same ID.
4. Panels RAL 5015 = KPP blue, doors/frames/porches RAL 7004 = KPP grey, glass as KPP; the drop below +-0.000 = wall colour.
AC04: small frames of ID4 = RAL 7004.

Scope from Artem: only paint. Geometry, topology, UCX and multisub IDs stay exactly as in the source scene. VPM/NPM of this building are a separate build card.

## Evidence and closed questions

Drive: **`G:/Мой диск/AGR-evidence/tec26-oks/AC04/gate1-v005/`**.
Open **`contact-sheet.png`** first: unnumbered finish swatches, ID labels outside swatches,
empty slots marked separately, ID-colour views and isolated face groups. The glass swatch is a schematic
translucency cue, not a measured/approved KPP glass tint or a rendered opacity test.
`iso.png`, `reverse.png`, `roof.png`, `only-1.png` … `only-5.png`, drawing diagnostic and PDF
are full-size companions. Diagnostic colours are deliberately distinct from finish swatches.
`evidence.json` lists the exact files, byte counts and hashes; Drive `SHA256SUMS.txt` is the checksum list.
The local native-render folder is `C:/x/tec26-oks/AC04/evidence-v005/`.
Earlier v002–v004 software diagnostic images are superseded by native Blender v005 pairs and are
not published as final Gate images. `blender-context.json` and the native render log record version,
engine and context. The render and verification scripts are included for reproducibility. Binary evidence is not committed and no LFS is used.

1. **Q1 — closed.** Approved with the quote above: panels RAL5015, doors/frames/porches RAL7004, glass as KPP, roof RAL7004 (not 5015), drop = wall colour.
3. **Q3 — closed.** Small frames of ID4 = RAL7004.
4. **Q4 — closed.** Answered by `joint_spec`: vertical joints only, rib count and step from `per_facade` on this sheet, joint 8 mm, 1000 px/m, phase symmetric in the panel field, plain below ±0.000. The four facades are unresolved and listed in `joint_report`. Supersedes Gate-1 point 1. The texture period is not a fallback step.

The 150 mm (DWG) versus 120 mm (PDF) sandwich thickness remains an open dimension note. It does not block this paint approval and it does not authorise a geometry edit.

Stop at Gate 1 paint. `delivery_passed` is false. Technical QA, user acceptance and publication are separate.

## Swatch sheet (post-approval)

`G:/Мой диск/AGR-evidence/tec26-oks/AC04/gate1-v006/swatches.png` (+ `SHA256SUMS.txt`): one swatch per ID/region, no numbers inside swatches, empty slots 6-10 crossed out. Blue = mean of KPP tile 1013 (34,113,179); grey = mean of KPP tile 1010 (150,153,146). `contact-sheet-ids.png` is the unchanged v005 depth-correct ID render sheet. Facade-vs-sheet acceptance pictures are made by the build card; 4 facade rib counts stay open (see joint_report).
