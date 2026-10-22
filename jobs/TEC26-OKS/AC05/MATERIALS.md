# AC05 materials — Gate 1 proposal

**Building:** Блок-модуль пенного пожаротушения (title block, not inferred from filename).
**Status:** awaiting Artem's Gate-1 decision; `passed=false`, no approved ID-to-finish assignment.
This is **not a delivery acceptance**. No VPM/NPM, texture maps or modified Max scene were built.
Initial pilot `origin/main`: `442f0b695a91f9abc180783c26978fbe85fefcf9`.

## Governing operator policy (2026-10-22)

R1 DWG governs finishes; PDF fills only what DWG lacks. Actual #558 layers 004–009 identify buildings. Scene mid-poly geometry is final: note dimensional discrepancies, do not rebuild. Propose ID matches from the same-DWG legend plus measured geometry for Artem to approve visually, not map blind. Undimensioned panel module means solid colour without joints. Empty slots stay empty. If glass is confirmed, use KPP M_Glass_01 (NPM alpha 0.5; VPM standard). No glass is invented here.

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
4. An exploratory ezdxf proxy facade raster was unusable (SHELL face-colour warnings / black output); excluded from the final evidence set. Facade evidence is source DWG text handles/coordinates, not that failed raster. Final ID renders use a per-pixel software z-buffer, not the exploratory painter ordering and not a native Max photoreal renderer.

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

All used IDs below are **proposed, not approved**. Geometry, not source colour, identifies each region. Map types are solid/metal without invented seams. Every measured face remains accounted for; areas include hidden and below-floor faces.

| Face ID | Poly faces | Triangles | Area m² | Proposed finish / RAL | Map type | Evidence / physical region |
|---|---:|---:|---:|---|---|---|
| 1 | 127 | 254 | 82.98113025259933 | **RAL 5015**, blue roof/edge structure and continuous shell | **metal** (solid colour) | DF1 + red diagnostic ID region: roof, perimeter/edge structure and downward shell. Z min **-2.004332** m. Whole-ID colour proposal, not a claim of specified blue concrete on hidden surfaces. |
| 2 | 22 | 44 | 56.48439932962852 | **RAL 5015**, blue sandwich-panel walls | **solid**, no joints | DF1 + DF3 + blue diagnostic ID region: side/end wall panels. No dimensioned seam/profile/module found; no KPP cassette pattern copied. |
| 3 | 476 | 990 | 6.699798207317762 | **RAL 7004**, opaque painted door/frame/hardware | **metal** | DF2 + yellow diagnostic ID region: end-opening frame/hardware and side door. Diagnostic yellow is not a drawing finish. |
| 4 | 1 | 2 | 4.313754850037867 | **RAL 7004**, opaque painted end door/gate infill | **metal** | DF2 + purple rectangular end infill. Proposed door/gate finish, not unproven glass. |
| 5 | 0 | 0 | 0 | ? (unused populated source slot) | ? | No faces; source yellow is not specified in AC05. Leave unused. |
| 6 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 7 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 8 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 9 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |
| 10 | 0 | 0 | 0 | ? (empty slot) | ? | No faces; leave empty. |

DF4 concrete slab remains inventoried, not arbitrarily assigned to an existing mixed blue ID. ID 1's whole-ID blue proposal includes hidden shell geometry but does not certify that hidden concrete is specified blue. Source geometry is final and untouched under operator policy; any disagreement on that whole-ID finish is a Gate-1 colour decision, not permission for a geometry rebuild.

## KPP colour reuse, not KPP finish substitution

`jobs/KPP1/materials.json` identifies `Metal_RAL5015` tile 1013 and `Door_RAL7004` tile 1010. The original `maps_kpp/T_Kpp_1_Diffuse_1.1013.png` has RGB **(34,113,179)** at **all 65536 pixels**; `...1010.png` has RGB **(150,153,146)** at **all 65536 pixels**. These exact solid images are copied and SHA-pinned in Drive, without resampling. They are source colour references, not a calibrated universal RAL-to-sRGB conversion. No generic web RAL palette was used. KPP cassette joints, perforation, grey plinth noise or yellow ladder texture were **not** copied to AC05. ID 1/2 swatches use exact KPP blue and ID 3/4 exact KPP grey, all marked proposed; 5–10 are crossed white unused. No number appears inside a swatch.

## Evidence and tests

Drive evidence directory: `G:/Мой диск/AGR-evidence/tec26-oks/AC05/gate1-v002/`.
Contact sheet: `contact-sheet.png`; individual ID renders: `id-axon-front.png`, `id-axon-back.png`, `id-side-x.png`, `id-end-y.png`, `id-roof.png`.
Two unchanged-geometry finish-colour previews (`finish-axon-front.png`, `finish-axon-back.png`) accompany the diagnostic views; these are Gate-1 colour proposals, not VPM/NPM exports. Previous `gate1-v001` is superseded and retained. Also included: original census JSON, three AC05 geometry buffers, recovered-text inventory with native handles, unmodified DXF, PDF page raster, raw AutoCAD receipts, reproducibility scripts and exact KPP blue/grey reference images. `SHA256SUMS.txt` in this directory and this job pins the published files. Render colours distinguish face IDs and are **not** drawing finish colours.

Focused test seam: this issue's `materials.json` + report; no shared validator or production module added. Tests-first commit `0396035` demonstrated **1 failed** because the AC05 inventory was missing. Operator-policy tests-first commit `3a6a8b9` then demonstrated **1 failed** (`unresolved != proposed`) before the concrete proposal update. Final focused run through `suite_slot.py`: **1 passed in 0.04s**. Independent read-only probes: **22/22 Drive file hashes**, **4/4 source hashes**, **3/3 distinct source/copy files**, **4/4 recomputed ID areas/counts**, **2/2 exact KPP constant-colour images**, **30/30 swatch samples**. `git diff --check` passed. Full suite is deferred until the first code-review request after the human Gate-1 answer. Inventory tests do not imply source completeness, model acceptance or Gate-1 approval.

## Gate 1 — STOP (answers on this card)

1. **Approve the visual proposal:** IDs **1–2 RAL 5015 blue**, IDs **3–4 opaque painted metal RAL 7004 grey**, including ID 1 whole-ID roof/edge/shell colour and ID 4 opaque door/gate infill? If not, identify the changed region on the sheet; the mapping is already proposed, not left to the user blind.
2. **Only missing drawing fact:** no panel seam/profile/module dimension was found. The proposal uses **solid blue without joints**. Keep this, or provide the dimensioned module if joints are required.

No layer-name, dimensional-rebuild, unused-slot or blind ID-mapping questions remain. Record Artem's answer against the current exact contact-sheet hash; then update only the approved statuses and request technical review. No model build is authorized in this card. Technical QA and user acceptance remain separate.
