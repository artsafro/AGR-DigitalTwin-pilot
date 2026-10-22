# AC09 — material evidence / Gate 1 (not approved)

Building name read from the title block: **Контейнер системы автоматического контроля вредных выбросов (САКВ)**.
Source: `22Е56-АР2-1002-АС.09.dwg`, layout `2`, handles `3437` and `3438`, insertions
(499.713, 27.7392, 0) and (504.356, 23.9892, 0), paper-space mm.
Pilot main at start: `442f0b695a91f9abc180783c26978fbe85fefcf9`.

**Status: awaiting_gate1; passed=false. No VPM/NPM build, source edits, material reassignment or delivery export.**
This is an evidence checkpoint, not a completed material mapping or a full architectural audit.

## Inputs and readback

- Original drawing was copied to `C:/x/tec26-oks/AC09/drawings-v001/ac09.dwg`.
  Original/copy SHA256: `feb22366bd7270f6912de797d9ffc0cc075d451cb154e3aaa1deaea96c88a5b5`.
  No PDF or R1 drawing was present in the AC09 source directory.
- AutoCAD 2025 Core Engine V.72.0.0 / ACADVER 25.0; INSUNITS=4 (mm).
  Existing #558 DXF and independent DXFOUT both terminate at XRECORD 35B without ENDSEC/EOF.
  `ezdxf.readfile` rejects both: `DXFStructureError: missing ENDSEC tag.`
  Neither nominal wrapper exit 0 nor the incomplete DXF is treated as a successful readback.
- Alternate read-only AutoLISP `entget` on the copy recovered 59 text/insert records (51 non-insert
  text records saved in `drawing-text.json`). A separate block walk recovered 204 lines.
  Initial text attempt failed (`prin1`: too many arguments); corrected to
  `write-line (vl-prin1-to-string ...)`, yielding `AC09_TEXT_DONE count=59`.
  Block extraction completed; optional `layoutlist` failed as unavailable in this core console.
  Nested transform/viewport mapping and native sheet rendering remain unverified.
- #558 census: `C:/x/tec26-oks/census/oks.json`, source copy
  `C:/x/tec26-oks/sources-v001/Vlad_OKS/04-09 Geometry Final.max`.
  3ds Max 2026.3, original Max file version 26000; meters, 1 unit/m, Z up.
  Only census rows on **actual layer `009`** are used; requested `0.0.0.9` / `0.0.9` was not found.
  No new Max session was started. This layer alias needs confirmation, not silent normalization.
- Main handle 173: `АС.09`, Multi/Sub `Material #7` (handle 4439), 10 slots;
  glass handle 369: `АС.09_Glass`, same Multi/Sub;
  collision handle 342: `Colizii_043`, 12 triangles, no material (not renamed UCX).
  Other layers and similarly numbered `Colizii_009` on layer 007 are excluded.
- Native/snapshot bbox error: main 0.000003814697265625 m, glass/collision 0 m.
  Census geometry buffers are reused for diagnostic views only; topology/UV/material delivery QA is not performed.

## Drawing sheets and finishes

Layout 2 / printed sheet 2 is identified by handle `3443` at (596.531,23.75,0).
The sheet contains plan at 0.000 (`2374`, 91.7101,283.955), section 1-1 (`23EA`,269.028,283.955),
roof plan (`2460`,444.483,283.955). Title-block equivalents: `3439`, `343A`, `343B`.
Facade-associated legend is present in Model space; its printed sheet number and viewport placement
are **unverified**, not invented. Coordinates below are native Model-space mm, not PDF pages.

| Drawing finish | RAL | Map-type proposal (not approved) | Evidence handle; Model insertion x,y,z |
|---|---|---|---|
| Sandwich panels | 5015 | joints; module/joint dimensions unknown | D4B; 27521.4,-943.967,0 |
| Porches and doors | 7004 | metal | D4D; 27521.4,-2647.4,0 |
| Window frames | 9016 | solid | 1C5A; 27521.4,-4105.6,0 |
| Three-layer sandwich panels, 100 mm, basalt mineral-wool infill | not specified in this note | joints | FFD; 12472.7,-20445.8,0 |
| Reinforced-concrete slab | not specified | ? visible finish | 1003; 12472.7,-22195.1,0 |
| Concrete | not specified | ? visible finish | 8B0; 56333.5,5967.98,0 |

No yellow RAL is specified in the recovered AC09 text. Do not borrow KPP yellow or other-building finishes.
Drawing handle `36B1`, Model (25439.7,-10124.7,0), says the roof level did not match facades/section,
formerly +2.330; handle `36B0` says `ИСПРАВЛЕНО!`. The replacement level was not independently
read from geometry/dimensions. No level is silently chosen.
Layout-2 note `259F` at (304.027,-18.1194,0) gives floor 0.000 = absolute 171.27 and factory-ready
modular construction; it is not a material specification or approval of source placement.

## Per-ID table — unknowns are deliberate

Area is summed triangle surface area in m², not projected/visible area. Main polygon counts and
triangulated counts remain separate. Collision IDs are topology-face IDs, not visible finish assignments.
Source diagnostic colours and generic material names do not establish RAL correspondence.

| ID | Main polygons | Main triangles | Main area m² | Glass triangles / area m² | Finish | Map type | Evidence / exact question |
|---|---:|---:|---:|---|---|---|---|
| 1 | 188 | 376 | 38.713608 | 0 / 0 | ? | ? | census 173 ID1: which faces are RAL5015 sandwich panels; panel/joint dimensions? |
| 2 | 50 | 100 | 18.757031 | 0 / 0 | ? | ? | census 173 ID2: same RAL5015 as ID1, or a different finish? |
| 3 | 40 | 80 | 1.901034 | 0 / 0 | ? | ? | census 173 ID3: window-frame RAL9016, porch/door RAL7004, or another grey? |
| 4 | 39 | 66 | 1.771651 | 0 / 0 | ? | ? | census 173 ID4: porch/door RAL7004, window-frame RAL9016, or another finish? |
| 5 | 12 | 24 | 0.940521 | 0 / 0 | ? | ? | census 173 ID5: specify finish/RAL/map type. |
| 6 | 0 | 0 | 0 | 8 / 3.216858 | ? | ? | census 369 ID6: confirm glass, tint and transparency. |
| 7 | 18 | 36 | 27.345944 | 0 / 0 | ? | ? | census 173 ID7: specify roof/underside/interior finish. |
| 8 | 0 | 0 | 0 | 0 / 0 | ? | ? | empty Multi/Sub slot: keep empty? |
| 9 | 0 | 0 | 0 | 0 / 0 | ? | ? | empty Multi/Sub slot: keep empty? |
| 10 | 0 | 0 | 0 | 0 / 0 | ? | ? | empty Multi/Sub slot: keep empty? |

`materials.json` retains unrounded areas and exact per-ID questions. Geometry is unchanged.

## KPP colour reuse, not an inferred RAL conversion

Hash-pinned references in JSON come from the user's `maps_kpp` and the finish-to-tile table in
`jobs/KPP1/materials.json`: RAL5015 tile1007, RAL7004 tile1001, RAL9016 tile1009.
Their modal RGBs are respectively (34,113,179), (150,153,146), (246,246,246).
These are measured modes of existing textures, **not calibrated RAL values** and not replacements
for the original KPP image pixels. No reference is applied to an unknown AC09 ID.

## Visual evidence and reproducibility

Drive folder: `G:/Мой диск/AGR-evidence/tec26-oks/AC09/gate1-v001/`.
`contact-sheet.png`: ten ID swatches, labels outside, pink hatch = unknown; empty slots marked.
`id-colours.png`: four orthographic source-census projections, coloured by actual source material ID;
these are software diagnostic projections, **not native Max renders**, nor approved finish previews.
Native facade/roof sheet captures and top/bottom diagnostic views remain open.
A contact sheet visually inspected with the image tool shows readable labels and projections.
Raw geometry-173/342/369, native text and block extraction are stored beside images.
`SHA256SUMS.txt` pins the evidence. JSON pins the source/census/buffers and manifest.
No binary is committed. No LFS is used.

## Gate-1 questions for Artem — STOP

1. Confirm that actual layer `009`, handles 173/342/369, is the intended AC09 scope.
2. Approve/correct the per-ID finish correspondence above, especially ID1 versus ID2,
   grey ID3 versus ID4, and dark ID5 / roof-or-underside ID7. The colours in the diagnostic
   views are ID markers, not proposed finishes. Confirm glass ID6 and leave empty slots 8–10?
3. Specify sandwich-panel module and joint appearance; for IDs without a drawing finish,
   provide the manufacturer specification or exact intended finish/RAL. Do not default to KPP.
4. Which facade sheet/revision and corrected roof level govern? The recovered text includes a
   correction note but does not independently establish the replacement dimension.

After these answers: complete drawing/viewport/native visual verification, update the mapping,
add approved KPP-colour swatches, obtain explicit approval of the resulting exact sheet.
Focused tests validate this checkpoint only; no full suite/PR/review is claimed at this blocked stage.
