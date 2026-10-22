# AC05 materials — Gate 1 approved

**Building:** Блок-модуль пенного пожаротушения (title block, not inferred from filename).
**Status:** `approved-gate1` (2026-10-22, quote «Принимаю»); `passed=false`.
This is **not a delivery acceptance**. No VPM/NPM, texture maps or modified Max scene were built.
Initial pilot `origin/main`: `442f0b695a91f9abc180783c26978fbe85fefcf9`.

## Artem's Gate-1 answer (2026-10-22)

Quote: «Принимаю» (orchestrator recommendations). Recorded verbatim:

1. Sandwich panels: solid colour without joints (module not confirmed in drawings).
2. Roof: RAL 7004 grey (as KPP 7004), not 5015.
3. Mixed ID: allowed to paint parts differently (roof 7004, frame 7004, plinth/perimeter drop = wall colour) WITHOUT changing geometry - via UV/atlas regions or splitting face groups inside the same ID.
4. Panels RAL 5015 = KPP blue; doors/frames/porches RAL 7004 = KPP grey; glass as KPP; the drop below +-0.000 = wall colour.
AC05 result: ID1-2 blue 5015 (roof part of ID1 -> 7004 per 2-3); ID3-4 metal 7004 including the gate infill.

The Gate-1 line above, "solid colour without joints", is the recorded answer. Two later notes the same day supersede it for the blue panels. Open finish questions from Gate 1 stay closed. Geometry stays the measured mesh.

## superseding_decisions (Artem, 2026-10-22)

These notes supersede only the Gate-1 line "Sandwich panels: solid colour without joints (module not confirmed in drawings)." Roof grey 7004 and ID3–4 grey stay as approved.

1. 2026-10-22: «Не вижу швов на панелях. В КПП есть текстура для VPM со швами... такой же тексель на наших домиках в VPM и NPM» and «ниже ±0.000 без швов (под землёй не видно).»
2. 2026-10-22: «Панели неверные, должны быть вертикальные швы только; текстуру пришлю; если не влезает, можно аккуратно порезать через loop или ring.»
3. 2026-10-22, from the AC08 note, for every TEC26 building: «всё равно говно, почему нельзя сделать как на презе — тут прям всё читается, и швы, и количество». This supersedes the 0.60 m joint step.

Current panel module: **vertical joints only; rib count and step from each facade colour-solution sheet; no horizontal joints; drop below +-0.000 plain**.

`facade_rib_source: found`.

Rule:

1. Blue sandwich panels (ID2, and the ID1 blue wall at and above ±0.000) have **vertical joints only**. No horizontal joints. Rib count and step come from this building's own facade «Цветовое решение» sheet.
2. A darker frame band outlines each panel field. Doors and the А-Б gate are RAL 7004 as on the sheet. The plinth strip is grey. The operator texture gives colour, noise and the look of one joint. Joints are laid out per facade. At 1000 px/m a 0.200 m step is 200 px. The texture's own 600 px period is not the layout step.
3. The perimeter drop below ±0.000 stays plain **without joints**.
4. A 0.20 m step needs no new cut when the UV of a face lies in one 4K tile (4.096 m). A later cut is allowed only as a clean edge loop or ring where a face still does not fit. The 16 faces wider than 4.096 m stay listed. This card does not cut anything.

Operator texture (not committed): `C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png`. Drive copy `G:/Мой диск/AGR-evidence/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png`. SHA-256 `2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece`. Measured 4096×4096, mean RGB (34, 112, 177), 7 vertical joints 8 px wide every 600 px. That 600 px period is the picture of one joint repeat inside the file. It is not the facade layout step.

## Governing operator policy (2026-10-22)

R1 DWG governs finishes; PDF fills only what DWG lacks. Actual #558 layers 004–009 identify buildings. Scene mid-poly geometry is final: note dimensional discrepancies, do not rebuild. Propose ID matches from the same-DWG legend plus measured geometry for Artem to approve visually, not map blind. The undimensioned panel module was first answered solid; the later 2026-10-22 notes replace that with vertical joints only, and the same-day AC08 note replaces the 0.60 m step with the facade sheet count, as in `superseding_decisions`. Empty slots stay empty. If glass is confirmed, use KPP M_Glass_01 (NPM alpha 0.5; VPM standard). No glass is invented here.

## Sources and readback

- Original folder: `C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/2_kotelnya/ИД/ТЭЦ-26 для передачи АГР/Актуальная ПД/Графическая часть/22Е56-АР2-1002-АС.05 (Блок-модуль пенного пожаротушения)/`.
- Pristine DWG/PDF copies: `C:/x/tec26-oks/AC05/sources-v002/`, with `manifest.json` and `SHA256SUMS.txt`. Exact original paths, bytes and SHA-256 are in `materials.json.sources`. Both copies and both originals were hash-compared.
- DWG: `22E56-АР2-1002-AC.05_R1.dwg`; AutoCAD 2025 Core Console reported `ACADVER=25.0`, `INSUNITS=4` (mm). Inspection through shared `dcc_batch.py acad`, on the disposable copy only. Native document identity is in the raw run receipts on Drive.
- PDF: `22Е56-АР2-1002-АС.pdf`; **one raster-only page**, 1786 × 842 page points, title-block **sheet 2**, revision 1 / 07.08.26, drawing code `22E56-АР2-1002-AC.05`. Title: `План на отметке 0.000 / План кровли / Разрез 1-1`. Title-block crop: page points `[1240,660,1786,842]`. A text-only PDF search would miss all notes.
- Facades **Б-А, 2-1, А-Б, 1-2** are in DWG model-space, labelled `Цветовое решение`; their sheet number is not established by the retained layout. They are **not** on the single supplied PDF page. No fabricated facade page number is supplied.
- Scene reused from #558: `C:/x/tec26-oks/census/oks.json`; copy `C:/x/tec26-oks/sources-v001/Vlad_OKS/04-09 Geometry Final.max`, SHA-256 `eb0cffedefa80678cf4ada13db71f2e80795a92212f9fbf60b7c30c54a7852bd`, matched to the original `Vlad_OKS/04-09 Geometry Final.max`.
- Census Max version array `[28000,68,0,28,3,0,30732,2026,".3"]`, file version `#(26000,26000)`, system units metres, scale 1, Z up. No new Max session was launched.
- Census geometry buffer `C:/x/tec26-oks/max-readback-v002/geometry-161.json`: bbox, vertex count, triangle count and all four per-ID areas recomputed against census (4/4). Original Editable Poly polygons and snapshot triangles are separate counts.

### Inspection failures and limits (preserved, not counted as passes)

1. AutoCAD `-DXFOUT` was unsupported, although the wrapper returned exit 0. No DXF was produced; raw `ac05-acad-v001.json` retained.
2. `DXFOUT` (without dash) produced DXF. Strict ezdxf read failed with `missing ENDSEC tag`; recovery yielded 0 remaining audit errors and **one** fix: removed orphaned paper-space layout block `*Paper_Space1`, handle `36D49`. The original DXF is retained, not rewritten. Model-space text including RAL legend is readable; orphaned-layout completeness is not asserted.
3. `QUIT No` means *do not discard* in this console, so AutoCAD saved its disposable **v001 copy**, not the original. That copy is not presented as hash-identical. Fresh pristine **v002** copies were made and rehashed against unchanged originals.
4. An exploratory ezdxf proxy facade raster was unusable (SHELL face-colour warnings / black output); excluded from the final evidence set. Facade evidence is source DWG text handles/coordinates, not that failed raster. Earlier v002 used a per-pixel software z-buffer; these software views were superseded by the native Blender review. v005 applied the first approved split and is superseded by v006.

## Drawing evidence

DWG coordinates below are insert points in millimetres, model-space unless specified. PDF coordinates are page points, top-left origin, physical page 1 / title-block sheet 2. Quotes preserve source language.

| Evidence | Finish/material actually specified | Locator |
|---|---|---|
| DF1 | `Сэндвич-панели, козырёк - RAL 5015` | DWG MTEXT **276D52**, `(137106.628,19878.504)`; facade colour legend |
| DF2 | `Крыльцо, двери, ворота - RAL 7004` | Same **276D52**, next legend line |
| DF3 | Three-layer sandwich panel filled with basalt mineral-wool slabs, **120 mm** | DWG **276D48**, `(135520.713,11813.496)`; PDF section callouts: roof `[970,150,1200,195]`, wall `[685,230,935,280]`, floor `[1035,435,1265,505]` |
| DF4 | `Железобетонная плита` | DWG **276D59**, `(135520.713,10237.866)`; PDF bottom section callout `[1035,435,1265,505]` |
| F-BA | Facade Б-А, colour solution | DWG TEXT **2713A4**, `(105323.296,35607.436)` |
| F-21 | Facade 2-1, colour solution | DWG TEXT **2713A5**, `(116798.782,35631.497)` |
| F-AB | Facade А-Б, colour solution | DWG TEXT **2713A7**, `(105333.852,45417.205)` |
| F-12 | Facade 1-2, colour solution | DWG TEXT **2713A8**, `(117006.331,45441.265)` |
| P | Floor plan 0.000 | DWG **27141F**, `(117861.159,17344.677)`; PDF upper-left |
| R | Roof plan | DWG **289910**, `(119519.624,7136.412)`; PDF `[145,440,570,610]` |
| S | Section 1-1 | DWG **276CB9**, `(119827.825,-16966.827)`; PDF `[660,50,1290,515]` |
| T | Building name and drawing code | DWG paper-space **28AE0E**, `(501.550,26.051)` and **28AE0F**, `(518.144,52.585)`; PDF title block |
| N | Factory-complete module; 30-foot container analogue; height 2896 mm; corner fittings ГОСТ Р 51891-2008; project 0.000 = absolute 163.20 | DWG paper-space **276C72**, `(247.796,-66.736)`; factual notes, not extra finish specifications |

Only **RAL 5015 and 7004** were found in all 79 recovered TEXT/MTEXT/ATTRIB/ATTDEF records. No yellow RAL, glazing specification, cassette/perforation finish or panel seam module was found in that extraction or the visible PDF. Proxy/removed-layout contents are not certified exhaustive. PDF section gives roof +2.896, width 2438 and length 9125 mm; mesh XY extent is approximately 2.438 × 9.211 m. This is identification evidence, not final geometry QA or a CRS confirmation.

## Scene and Multi/Sub

Actual layer is **005**, accepted under operator policy; no layer-name question remains. Mesh **АС.05**, handle **161**, 784 vertices, **626 Editable Poly polygons / 1290 triangles**. Multi/Sub `Material #27`, handle 4036, ten slots: five populated, five empty. Slots 1–5 are `Material #26`, `#28`, `#24`, `#29`, `#25`; slot 5 looks yellow in the original material parameters but has **no mesh face ID 5**. Slot labels are not proof of custom `materialIDList`: #558 did not record that property. Face IDs below come from measured faces, not guessed slot indices; source slot-to-ID binding remains unverified.

Same-layer collision **candidates**: `Colizii_045` (344) and `Colizii_046` (345), 12 triangles each. They are not named UCX in the source, have no material, and their primitive face IDs 1–6 do **not** define render finishes. No collision rebuild, rename or pairing certification was performed. Full candidate bboxes are in JSON and raw buffers on Drive.

## ID → finish → map type → evidence

Used IDs are **`approved-gate1`** (2026-10-22). Geometry was not edited. ID1 is a mixed ID: two face groups inside the same ID. Roof and ID3–4 stay metal without joints. Blue wall regions are vertical joints only. The perimeter drop stays plain panel colour without joints. Every measured face remains accounted for; areas include hidden and below-floor faces. Region areas sum to the ID1 total.

**ID1 split rule** (geometry-161.json, SHA-256 `22406a97eaf836e47cce92ef871a5cceea3357b3f936ea13ca2764791ac6e500`). Unit normal Z is the triangle cross-product Z divided by the cross-product length. An ID1 polygon is each consecutive triangle pair `(2k, 2k+1)`; every ID1 pair shares an edge.

- **Roof** = unit normal Z > 0.5 and minimum vertex Z > 2.0 m (the roof plane near 2.897 m): 15 polygons, 30 triangles, 22.24778336847559 m², **RAL 7004** exact KPP grey RGB (150, 153, 146).
- **Wall + perimeter drop** = every other ID1 triangle, including faces at and below Z = 0 and the upward plinth ledge near Z = 0.121 m: 112 polygons, 224 triangles, 60.73334688412373 m², **RAL 5015** exact KPP blue RGB (34, 113, 179).
- 15 + 112 = 127 polygons, 30 + 224 = 254 triangles, and the two areas sum to 82.98113025259933 m². No ID1 triangle is in both regions or in neither. No drop triangle (minimum vertex Z <= 0) is in the roof region.

| Face ID | Poly faces | Triangles | Area m² | Approved finish / RAL | Map type | Evidence / physical region |
|---|---:|---:|---:|---|---|---|
| 1 | 127 | 254 | 82.98113025259933 | **Mixed.** Wall at and above ±0.000 **RAL 5015** with vertical joints. Perimeter drop **RAL 5015** plain, no joints (112 / 224 / 60.73334688412373 together). Roof faces **RAL 7004** KPP grey, no joints (15 / 30 / 22.24778336847559). | **mixed** | DF1 + DF2 + red diagnostic ID region. Z min **-2.004332** m. Drop at and below ±0.000 stays wall colour on existing ID1 and has no joints; roof plane is grey metal. Never cut at ground. |
| 2 | 22 | 44 | 56.48439932962852 | **RAL 5015**, blue sandwich-panel walls, vertical joints only | **joints**, vertical only | DF1 + DF3 + blue diagnostic ID region: side/end wall panels. Rib count and step from the facade sheet below: long sides 44 × 0.200 m. No horizontal joints. No KPP cassette pattern copied. |
| 3 | 476 | 990 | 6.699798207317762 | **RAL 7004**, opaque painted door/frame/hardware | **metal** | DF2 + yellow diagnostic ID region: end-opening frame/hardware and side door. Diagnostic yellow is not a drawing finish. |
| 4 | 1 | 2 | 4.313754850037867 | **RAL 7004**, opaque painted end door/gate infill | **metal** | DF2 + purple rectangular end infill. Approved door/gate finish, including the gate infill, not unproven glass. |
| 5 | 0 | 0 | 0 | ? (unused populated source slot) | ? | No faces; source yellow is not specified in AC05. Leave unused. |
| 6 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 7 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 8 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 9 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 10 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |

DF4 concrete slab remains inventoried, not arbitrarily assigned to another ID. **Artem's perimeter-drop clarification, confirmed again on 2026-10-22:** below-zero geometry is required, not a defect. Preserve it in both VPM and NPM, never cut at ground, keep the wall colour and the existing ID. Here all below-minus-one-metre triangles use ID1 and fall in the wall_drop region, so the drop is RAL5015 plain panel colour, the same hue as wall ID2, without joints and without adding an ID.

### Wall faces wider than one 4K tile

Width is the horizontal run of each blue wall-region polygon (ID2, and ID1 polygons that are not the roof split), at 1000 px/m. A vertical face is measured along the wall. A horizontal face uses its longer plan dimension. The drop shell is the 16 ID1 polygons whose vertices stay at or below the 0.01 m gap under the first above-grade band (maximum Z about 0.0014 m). 134 wall-region faces were measured. 118 are within 4.096 m. 16 exceed it; each is about 6.4281 m on a long side. No cut was performed.

| Polygon | ID | Width m | Role | Joints |
|---:|---:|---:|---|---|
| 239 | 1 | 6.4281 | wall | vertical |
| 241 | 1 | 6.4281 | wall | vertical |
| 259 | 1 | 6.4281 | wall | vertical |
| 260 | 2 | 6.4281 | wall | vertical |
| 261 | 1 | 6.4281 | wall | vertical |
| 262 | 2 | 6.4281 | wall | vertical |
| 271 | 2 | 6.4281 | wall | vertical |
| 272 | 2 | 6.4281 | wall | vertical |
| 285 | 2 | 6.4281 | wall | vertical |
| 291 | 2 | 6.4281 | wall | vertical |
| 327 | 1 | 6.4281 | wall (horizontal ledge) | vertical |
| 335 | 1 | 6.4281 | wall (horizontal ledge) | vertical |
| 336 | 1 | 6.4281 | wall (horizontal ledge) | vertical |
| 340 | 1 | 6.4281 | wall (horizontal ledge) | vertical |
| 633 | 1 | 6.4281 | perimeter drop | none |
| 643 | 1 | 6.4281 | perimeter drop | none |

Polygons 633 and 643 are the long drop faces. They exceed 4.096 m and stay plain colour, so no joint-tile cut applies to them. The other 14 would need a later edge loop or ring at joint positions if one 4K tile must cover the face. Cuts performed: none.

**Read-only depth measurement:** intersect source triangles with Z=-1.0 m and merge intervals on each of the four outer rectangular sides. All four side spans are complete (no gaps); bottom-vertex upper bounds: X-min -2.004328966, X-max -2.004328728, Y-min -2.004331589, Y-max -2.004328728 m, each <= -1.0 m. Raw `ac05-drop.json` records intervals and exact bounds; side classification 0.1 mm and interval merge 0.01 mm address source float jitter, not model edits or a relaxation of the one-metre requirement. This is a source measurement, not final exported-profile QA.

## Facade rib count, measured on the R1 colour sheet

`facade_rib_source: found`. Searched, read-only: the pristine R1 DWG and the one-page PDF under `C:/x/tec26-oks/AC05/sources-v002/`; the same two files in `...\Графическая часть\22Е56-АР2-1002-АС.05 (Блок-модуль пенного пожаротушения)\`; presentation `ИД\ТЭЦ26 на РР.pptx` slide «Блок-модуль пенного пожаротушения. Схема фасадов»; `C:/x/tec26-oks/user-refs/` (only `AC08_facades_colour_from_artem.jpg`, which is AC08, not AC05). The PDF page is plan, roof and section. Counts below are from the DWG R1 model-space blocks (recovered DXF of the v001 readback; handles are the DWG handles). The presentation uses the same blue `(0, 124, 176)` and grey `(155, 155, 155)`.

| Facade | Insert | Ribs | Step | Field | Locator |
|---|---|---:|---:|---:|---|
| 1-2 | **278551** | 44 | 0.200 m | 8.800 m | Modules **278522**–**27854D**, x −5600 to 3200 mm, each 200.0 mm, y 0 to 2639.341. Outer **277F0C**, 9125.492 × 2896 mm. Left frame 101.6 mm, right 223.89 mm. |
| 2-1 | **27A88C** | 44 | 0.200 m | 8.800 m | Modules **27A4C0**–**27A495**, x −4600 to 4200 mm. Door hatch **27A4C1**, RGB (155, 155, 155), 1.100 × 2.187 m, RAL 7004. |
| Б-А | **27C3DE** | 13 | 0.149577 m | 1.795 m | Thirteen vertical rib pairs. Twelve steps of 0.149577 m. Outer **27BC92**. Blue hatch **27BC91** only. |
| А-Б | **27E19F** | — | not even | — | Grey gate hatch **27D28A**, RGB (155, 155, 155), 2.287 × 2.547 m, RAL 7004, inside a blue frame. No sandwich rib count. |

No horizontal joints on any facade. 44 × 0.200 m = 8.800 m. (13 − 1) × 0.149577 m = 1.794924 m, which matches the first-to-last rib span 1.794930 m. The comparison sheet is `gate1-v007/contact-sheet.png`: each facade drawing next to the matching mesh elevation at 80 px/m, with the rib count under both. Mesh pairing is by long/short side and by the door or gate, not by a surveyed axis letter.

## KPP colour reuse, not KPP finish substitution

`jobs/KPP1/materials.json` identifies `Metal_RAL5015` tile 1013 and `Door_RAL7004` tile 1010. The original `maps_kpp/T_Kpp_1_Diffuse_1.1013.png` has RGB **(34,113,179)** at **all 65536 pixels**; `...1010.png` has RGB **(150,153,146)** at **all 65536 pixels**. These exact solid images are copied and SHA-pinned in Drive, without resampling. They are source colour references, not a calibrated universal RAL-to-sRGB conversion. No generic web RAL palette was used. KPP cassette joints, perforation, grey plinth noise or yellow ladder texture were **not** copied to AC05. The blue joint source is Artem's texture above, mean RGB (34, 112, 177), not the flat KPP tile. The v006 sheet has one swatch per ID and no number inside a swatch. ID1's swatch is split: a crop of that texture (vertical joints) for the wall, and exact KPP grey for the roof. ID2 is the same texture crop. IDs 3–4 are exact KPP grey, no joints. Slots 5–10 are crossed white unused, which marks the empty gaps.

## Evidence and tests

**Current Gate review:** `G:/Мой диск/AGR-evidence/tec26-oks/AC05/gate1-v007/contact-sheet.png`.
`gate1-v006` is **superseded** (its contact sheet remains trace only: `G:/Мой диск/AGR-evidence/tec26-oks/AC05/gate1-v006/contact-sheet.png`). `gate1-v005` and `gate1-v004` remain superseded.
Every current geometry view is a **native Blender 5.1.2 / Cycles CPU render** carried byte-for-byte from v005, source geometry unchanged, collision meshes excluded. For each of two camera directions the sheet places **ID colours next to a plain neutral shaded view**, plus a colour-only finish view with the ID1 roof in KPP grey and the blue walls in RAL5015. The finish views do **not** draw the 8 mm joints: at ortho scale 14.5 m on a 1200 px frame an 8 mm joint is under one pixel. Vertical joints are shown on the blue swatch crop. A yellow native 3D outline at **Z=0.000** (5 cm outward for visibility) marks the datum without cutting/occluding the required drop. No wireframe triangle overlay. Source: 784 vertices / 1290 triangles, handle161 only; counts/IDs and source buffer hash unchanged. Native renderer receipt: `native-render.json` (`id1_roof_triangles` 30, `finish_views` colour-only).

Old v001/v002 software projections are **superseded and not for Gate approval**; v003 first native framing clipped the extremities and is also superseded. v004 expanded framing and was superseded by v005. v006 keeps that framing and the roof/wall colours, replaces the blue swatches with the operator texture crop, and supersedes v005. These old versions remain trace evidence only.

Current directory also retains the governing drawing raster, original census and three AC05 raw geometry buffers, recovered DWG text/handles, unmodified DXF, raw AutoCAD receipts, exact KPP constant-colour references, native renderer/drop scripts and checksums. All evidence binaries remain on Drive. `SHA256SUMS.txt` here pins the current bundle. Model geometry and original files were never edited, no VPM/NPM was built or exported.

Focused test seam: this issue's `materials.json` + report; no shared validator or production module added. Tests-first commit `0396035` demonstrated **1 failed** because the AC05 inventory was missing. Operator-policy tests-first commit `3a6a8b9` then demonstrated **1 failed** (`unresolved != proposed`) before the concrete proposal update. Final focused run through `suite_slot.py`: **1 passed in 0.04s**. Independent read-only probes: **25/25 current Drive file hashes**, **4/4 source hashes**, **3/3 distinct source/copy files**, **4/4 recomputed ID areas/counts**, **2/2 exact KPP constant-colour images**, **30/30 swatch samples**. `git diff --check` passed. Full suite is deferred until the first code-review request after the human Gate-1 answer. Inventory tests do not imply source completeness, model acceptance or Gate-1 approval.

## Gate 1 — answered 2026-10-22, blue joints superseded the same day

No open Gate-1 question remains. The first answer's solid-panel line is superseded for blue panels, and the 0.60 m step is superseded by the measured sheet. Current rule: **vertical joints only; rib count and step from each facade colour-solution sheet; no horizontal joints; drop below +-0.000 plain**. ID1 roof is KPP RAL7004 metal, no joints; ID1 wall at and above ±0.000 is RAL5015 with vertical joints only; the drop at and below ±0.000 is plain without joints; the plinth strip is grey; ID2 is RAL5015 vertical joints only; IDs 3–4 are KPP RAL7004 metal, including the gate infill, no joints; slots 5–10 stay unused. The current sheet is `gate1-v007/contact-sheet.png`. No model build and no mesh cut is authorized in this card. Technical QA and user acceptance remain separate. `passed=false`.

Native-image follow-up RED: commit `0ae100c`, **1 failed / 1 passed** (missing native-render receipt), prior to the new bundle. Final focused `suite_slot.py` run: **2 passed in 0.08s**. Independent current-bundle probe: **25/25 hashes**, **4/4 source hashes**, **3/3 nonaliased source/copies**, **4/4 ID counts/areas**, **2/2 exact KPP images**, **30/30 swatch samples**. Perimeter-drop span probe: **4/4**. Native Blender process exited **0**, six rendered images read back, final sheet visually checked for whole-object framing and correct depth. Earlier software/framing versions are not current Gate evidence.

## Build legend (slide 35 + binding legend, build-v004)

Artem 2026-10-22: the «Условные обозначения» legend and presentation slide 35 govern colours [D171]. Every ID/region of the build was checked against this table (`finish_map.validate_legend`) before textures and renders; details and rib counts in `BUILD_REPORT.md`.

| Legend row | Material | RAL | Texture | Finish | Source ID / region | Polygons |
|---|---|---|---|---|---|---:|
| Сэндвич-панели (blue ribbed field) | sandwich panel | 5015 | ribbed | PanelVJ45_RAL5015 | ID2, facades 1-2 (+x) / 2-1 (-x) | 16 |
| Сэндвич-панели (blue ribbed field) | sandwich panel | 5015 | ribbed | PanelVJ14_RAL5015 | ID2, facade Б-А (+y) | 3 |
| Обрамление (frame band, posts, rails, А-Б strips, drop) | edging | 5015 | plain | Frame_RAL5015 | ID1 except roof (112) + ID2 -y (3) | 115 |
| Крыльца, двери (door, end gate) | door / gate | 7004 | plain | Door_RAL7004 | ID3 (476) + ID4 (1) | 477 |
| Кровля (Gate 1) | roof | 7004 | plain | Roof_RAL7004 | ID1 up-facing, z >= 2.89 m | 15 |

