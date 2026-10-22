# TEC26 AC07 — Gate 1 material evidence

**Gate 1 APPROVED by Artem 2026-10-22 (with ID6 to_verify)** Quote: «Принимаю». No VPM/NPM build in this card. Colours of ID1, ID5 and ID11 on the v006 contact sheet reflect the old proposal; this card does not regenerate that sheet. The updated acceptance sheet, with ID6 shown enlarged, comes with the separate VPM/NPM card.

Building title: **Пункт редуцирования газа 2**. PDF physical page 1, printed sheet 3, section 1-1; title block also DWG Layout1 #1059C7 (301.868,25.968) mm. Base main: `442f0b695a91f9abc180783c26978fbe85fefcf9`.

## Inputs and readback

Copies: `C:/x/tec26-oks/AC07`; DWG and PDF hashes:
- `22E.pdf` (69654 bytes), SHA256 `f05a7b539bacc907c5f95c5c846d73b2ef7392d4368d92b58a4343a637dd1c3a`.
- `22E56-АР2-1002-AC.07_R1.dwg` (1902674 bytes), SHA256 `51b355e53288391b439a7aec01627a0cd1962041f12a3a2125cf797ca70edf3d`.

Census: `C:/x/tec26-oks/census/oks.json`, SHA256 `a99de19f1d30633eaab9c52ac44f253ed6ea97e03358755ff2a77458f0f54f2f`. Max 2026.3 application; file version #(26000, 26000); meters, Z up. No DCC was started in this card. Read the existing #558 census and buffers only.

Actual layer **007**, not literal 0.0.0.7/0.0.7: explicit АС.07 object names and 13.5 m section span support correspondence, correspondence is confirmed by the operator (actual census layers govern). 23 geometry objects: main handle 385, glass 388, 21 `Colizii_*` collision candidates. Multi/Sub **Material #59**, handle 4999, Standard submaterials IDs/slots 1..12. Main 5596 triangles; glass 12. No ID gaps; glass uses ID 12 only. Collision IDs have no finish semantics; per-object counts/areas are retained separately in JSON. Native polygon counts and triangulated counts are not interchangeable.

Diagnostic render area/counts recomputed independently from zero-based census vertex/triangle buffers for all 12 render IDs: 12/12 counts and areas agree (<1e-9 m²). Final Gate images use Blender 5.1.2 Cycles CPU with native ray-traced depth. Each full-building ID view has a matching plain-shaded view and magenta datum at +/-0.000 m; collision candidates are not created in the diagnostic scene. Isolated ID views are native renders too. Source vertices, triangles and buffers are preserved; no source materials were changed.

## Drawing evidence

Existing AutoCAD 2025 DXF receipt: `C:/x/tec26-oks/acad-readback-v001/ac07-run.json`; INSUNITS=4 (mm). Strict ezdxf reading failed: missing ENDSEC. Recovery: 0 audit errors / 2 orphan paper-space block fixes. Read top-level and nested text and rendered model-space crops, not merely the PDF text layer (the PDF has no extractable text). Recovered output is inspection evidence, not a replacement DWG.

| Evidence | Locator | Read from source |
|---|---|---|
| legend | 10C71C [22699.66838582569, 65365.49480536217] | Sandwich panels and canopies RAL 5015; sandwich panels RAL 7047; porches, doors, plinth, drainage RAL 7004; pressure-relief frames RAL 9016. |
| title | PDF p1, printed sheet 3 | Пункт редуцирования газа 2; Разрез 1-1; 22E56-АР2-1002-AC.07 |
| section | PDF p1, printed sheet 3 | Three-layer sandwich panel with basalt mineral-wool infill, 120 mm, roof/walls/floor; reinforced-concrete slab; tubular snow retainers; pressure-relief structures. Roof 6 degrees, axes 2500+11000=13500 mm. No roof RAL or membrane specification. |
| roof | 104EB7 [52613.75339042968, 35863.55240563567] | Roof plan, tubular snow retainers, 6-degree slopes; axes 13500 x 10900 mm. No roof coating RAL. |
| panel-legend | 10C71F [21673.52974873521, 57899.76512993906] | Three-layer sandwich panels, basalt mineral wool, 120 mm; #10C725 reinforced concrete slab. |
| excluded-group | FF24D,FF24F,FF251,FF265 [190000, 10000, 250000, 80000] | Separate group crossed by red diagonal lines: axes 1-6, blue-only panels, thickness 150/250 mm. Retained as excluded evidence, not silently substituted for the 1-3 / 120 mm section. |

Facade titles: Model #105135 (22812.018,87602.537) A-Д; #105134 (22876.225,78300.466) Д-A; #104EB0 (49444.477,87602.537) 1-3; #104EB2 (49380.270,78300.466) 3-1, all mm. Section title #10CD49 (52128.875,16424.682). Roof title #104EB7 (52613.753,35863.552). Facade/roof printed sheet numbers are not supplied by the single-page PDF and are not invented. Coordinates identify the actual views.

The remote x≈200000 group is visibly crossed in red; its 1-6 axes / 150,250 mm panels are retained separately, not mixed into the matching 1-3 / 120 mm group. No new conflict decision is made.

## Per-ID table

RAL colour is never inferred from Max diffuse or the diagnostic ID colours. Geometry-role descriptions are observations. Finishes below are Gate 1 decisions from Artem on 2026-10-22, except ID 6 (`to_verify`). Map types describe the intended representation only, not generated maps.

| ID | Source material | Native polygons / triangles | Area m² | Observed geometry | Finish | Map type | Status | Evidence |
|---|---|---|---|---|---|---|---|---|
| 1 | Material #62 | 181 / 362 | 177.127565029 | roof panels + upper facade panels | mixed ID, geometry unchanged: roof faces RAL 7004 solid; upper facade panels RAL 5015 vertical_joints | mixed | approved | legend, section, roof; geometry handle 385; panel_rule |
| 2 | Material #60 | 671 / 1290 | 83.268385151 | roof edge trims / canopy plates | metal RAL 5015 | metal | approved | legend; geometry handle 385 |
| 3 | Material #61 | 300 / 444 | 94.417859701 | lower wall sandwich panels | sandwich panels RAL 7047 | solid | approved | legend, panel-legend; geometry handle 385 |
| 4 | Material #63 | 772 / 1576 | 4.984935707 | downpipes and gutter components | metal RAL 7004 | metal | approved | legend; geometry handle 385 |
| 5 | Material #52 | 24 / 48 | 0.697029650 | snow guards (tubular snow retainers) | metal RAL 7004 | metal | approved | roof, section; geometry handle 385 |
| 6 | Material #51 | 200 / 300 | 3.303690907 | round facade inserts / service penetrations | metal RAL 7004; show enlarged on the VPM/NPM acceptance sheet | metal | to_verify | geometry handle 385 |
| 7 | Material #53 | 120 / 204 | 5.655706857 | door leaves | doors RAL 7004 | solid | approved | legend; geometry handle 385 |
| 8 | Material #58 | 504 / 1008 | 21.514531059 | pressure-relief opening frames and mullions | frames RAL 9016 | solid | approved | legend, section; geometry handle 385 |
| 9 | Material #57 | 30 / 60 | 7.950371307 | outer rectangular opening surrounds | frames and surrounds RAL 9016 | solid | approved | legend, section; geometry handle 385 |
| 10 | Material #54 | 88 / 176 | 105.289043543 | visible plinth and required deep perimeter drop | plinth and required perimeter drop RAL 7004 | solid | approved | legend, section; geometry handle 385 |
| 11 | Material #56 | 64 / 128 | 116.797766588 | inner floor / wall shell | Interior (KPP key Interior, id 31, udim 1011) | solid | approved | section; geometry handle 385 |
| 12 | Material #55 | 6 / 12 | 32.651295360 | separate glazing infill | M_Glass_01 (KPP convention) | glass | approved | section; geometry handle 388 |

## Operator clarification (2026-10-22)

Governing finishes/colours: DWG *_R1.dwg; PDF supplements only missing DWG information. Scene geometry is final: 120 versus 150/250 mm drawing differences are noted, not a geometry rebuild or blocker. Crossed-out other-object/template views are excluded. Actual census layers govern. Empty submaterial slots: none (IDs 1..12 all populated and used across main + glass). Artem (2026-10-22) supersedes the earlier solid-panel point for RAL 5015 sandwich panels: vertical joints only. See panel rule below. RAL 7047 panels (ID3) stay a solid colour.

Glass follows KPP: M_Glass_01, NPM alpha 0.5 and no textures; KPP source export_npm.py Base Color (0.75,0.82,0.82), roughness 0.05. VPM remains a separate untextured glass material per standard; KPP package_vpm.py values are proposals, not a substitute for delivery approval. No extra glass question is raised.

ID 1 is a mixed ID: roof faces RAL 7004 (solid) and upper facade panels RAL 5015 (vertical_joints), as regions inside the same ID. Geometry is unchanged. ID 9 white surrounds stay RAL 9016 from the legend. ID 10 below zero is the required perimeter drop and stays RAL 7004 with the adjacent plinth: plain colour, no joints. The only open item is ID 6.

## RAL 5015 panel rule (2026-10-22)

Artem supersedes the earlier solid-panel point for blue sandwich panels only. `panel_rule` in `materials.json` is the record. No geometry change and no cuts in this card.

- Applies to RAL 5015 sandwich panels: ID1 upper facade panels, and any other RAL 5015 panel region. `map_type` is `vertical_joints`. Vertical joints only (`vertical_only`: true). No horizontal joints.
- ID2 metal trims stay `metal`. ID3 RAL 7047 sandwich panels stay `solid`.
- Module 0.60 m, joint 8 mm. Texel is the KPP VPM density, 1000 px/m on a 4K UDIM, so 600 px is 0.60 m and 8 px is 8 mm.
- Texture: `C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png`, 1010080 bytes, SHA256 `2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece`. 4096×4096 RGB. Rounded mean RGB (34, 112, 177); measured mean (33.7033, 112.0103, 177.4277). Seven vertical joints, 8 px wide, period 600 px, first joint starts at x=266.
- 4096 is not a multiple of 600, so the raw image is not tiled. Joints are laid at a 0.60 m period from each panel's start edge. Phase comes from ±0.000 / the panel corner.
- Same look in VPM (Diffuse+Normal) and in the NPM atlas (joints at least 1.5 px). This replaces the KPP cassette tile for these panels.
- Below ±0.000, ID10 and any perimeter drop stay plain colour, no joints (`below_zero_plain`: true).
- If a panel face does not fit a 4K tile, the only allowed cut is a clean edge loop or ring across the panel at a joint. Silhouette, normals, UCX and material IDs stay as they are. Quads are kept. Every such cut is listed in the report. Cuts made in this card: none.

## KPP colour parity

Only colour, not KPP material numbering or cassette geometry, is borrowed. Same-RAL proposals use exact RGB pixels from existing KPP maps. 7047 is the dominant pixel of the textured cassette etalon, not a calibrated RAL conversion; no cassette pattern is imposed on RAL 7047 sandwich panels. RAL 5015 panels no longer use the KPP cassette tile: the user vertical-joint texture replaces it (panel rule above). There is no AC07 evidence for yellow RAL1021.

- ID 1 roof faces, RAL 7004: RGB [150, 153, 146], `T_Kpp_1_Diffuse_1.1010.png`, SHA256 `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969`.
- ID 1 upper facade panels, RAL 5015: joint map `C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png` (1010080 bytes), SHA256 `2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece`, rounded mean RGB [34, 112, 177]. Prior KPP dominant pixel of tile 1013 remains RGB [34, 113, 179], SHA256 `1d978c478b119565a77a2b503ce8b1f09d95425156ccd83c90021459dc14c4a2`; that tile is not the panel map.
- ID 2, RAL 5015: RGB [34, 113, 179], `T_Kpp_1_Diffuse_1.1013.png`, SHA256 `1d978c478b119565a77a2b503ce8b1f09d95425156ccd83c90021459dc14c4a2`.
- ID 3, RAL 7047: RGB [208, 208, 208], `T_Kpp_1_Diffuse_1.1006.png`, SHA256 `953d54d37cd8b3193afc5d3b973afc87ed06a9949232799a466193b1617efeb9`.
- ID 4, RAL 7004: RGB [150, 153, 146], `T_Kpp_1_Diffuse_1.1010.png`, SHA256 `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969`.
- ID 5 snow guards, RAL 7004: RGB [150, 153, 146], `T_Kpp_1_Diffuse_1.1010.png`, SHA256 `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969`.
- ID 6 round inserts, RAL 7004 metal, to_verify: RGB [150, 153, 146], `T_Kpp_1_Diffuse_1.1010.png`, SHA256 `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969`.
- ID 7, RAL 7004: RGB [150, 153, 146], `T_Kpp_1_Diffuse_1.1010.png`, SHA256 `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969`.
- ID 8, RAL 9016: RGB [246, 246, 246], `T_Kpp_1_Diffuse_1.1009.png`, SHA256 `5a24af09b5c0da12873e6f7cdc170acc6b7b339815ce470dfee5336a81925eda`.
- ID 9, RAL 9016: RGB [246, 246, 246], `T_Kpp_1_Diffuse_1.1009.png`, SHA256 `5a24af09b5c0da12873e6f7cdc170acc6b7b339815ce470dfee5336a81925eda`.
- ID 10, RAL 7004: RGB [150, 153, 146], `T_Kpp_1_Diffuse_1.1010.png`, SHA256 `765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969`.
- ID 11: KPP finish name `Interior` (id 31, udim 1011). No RAL. The library key is Interior; Artem called it KPP Interior. No separate "KPP Interior" material exists in `jobs/KPP1/materials.json`.

## Gate 1 approval

Artem, 2026-10-22. Quote: «Принимаю».

1. RAL 5015 sandwich panels (ID1 upper facade and any other RAL 5015 panel region): vertical joints only, map_type vertical_joints, module 0.60 m, joint 8 mm, no horizontal joints; do not tile the raw 4K image; phase from +-0.000 / panel corner. RAL 7047 sandwich panels stay solid. Metal trims (ID2) unchanged. Below +-0.000 (ID10 drop and any perimeter drop): plain colour, no joints. Supersedes solid-without-joints for blue panels.
2. Roof: RAL 7004 grey (as KPP 7004), not 5015.
3. A mixed ID may be painted per part (roof 7004, frame 7004, plinth/drop = wall colour) without changing geometry - via UV / atlas regions or face-group split inside the same ID.
4. Panels RAL 5015 = KPP blue, doors/frames/porches RAL 7004 = KPP grey, glass as KPP; drop below +-0.000 = wall colour.
5. ID6 round inserts: Artem did not define; set 7004 metal, status to_verify (на проверку), show enlarged on the VPM/NPM acceptance sheet.

Point 4 still names the drop colour as the adjacent wall/plinth colour. For AC07 that colour is ID10 RAL 7004. Point 1 adds that the drop is plain, with no joints.

Open question (ID 6 only): what are the round inserts, is 7004 metal right?

Later scope (Artem): only colouring. Geometry, topology, UCX and multisub IDs stay exactly as source. VPM = UDIM tiles, NPM = one 2048 atlas; geometry checks are only reported. VPM/NPM of this building are a separate card.

## Evidence and limits

Drive: `G:/Мой диск/AGR-evidence/tec26-oks/AC07/v006`

- `contact-sheet.png`: one number-free swatch rectangle per ID; labels outside, hatching for unresolved finishes; overview ID render below. Colours of ID1, ID5 and ID11 on this v006 sheet reflect the old proposal (ID1 roof extrapolated as RAL 5015; ID5 and ID11 unresolved). This card does not regenerate the sheet. The updated acceptance sheet, including ID6 enlarged, comes with the VPM/NPM card.
- `depth-correct-views.png`: four native Blender ID/plain-shaded pairs; `ids-isolated.png`: 12 native isolated-ID renders. UCX hidden (not created); magenta geometry marks +/-0.000 m. The 32 original native PNGs and `blender-render-report.json` are included.
- `facades-inline.png`, `roof-inline.png`, `section-inline.png`, `other-group-inline.png`: recovered-DXF crops, with SVG CSS expanded to attributes so colours render correctly.
- `pdf-p1.png`: actual supplied PDF section/title block.
- `SHA256SUMS.txt`: all final image hashes; contact sheet SHA256 `b93f7648ae3cf5aa82b1f7d8915c18a5df4f83f0252cf555398c0f0353ae9bbd`.

Discarded previews remain versioned for traceability: v001 had incorrect triangle indexing; v002 non-inline drawing PNGs failed to apply CSS. All v001-v004 CPU painter projections are withdrawn from Gate approval because they lack correct per-pixel depth. Only v006 native Blender images are current Gate evidence; v005 is superseded by adding plain-shaded partners to all 12 isolated views.

Geometry health, collision compliance, UV/delivery/export checks are not run in Gate 1. No maps, material assignments, VPM or NPM were built. No `passed=true` is claimed. Local focused regression verifies this record, not architectural approval.

## Perimeter drop clarification (2026-10-22)

Artem: the geometry below zero is the required perimeter drop, minimum 1 m down. It is retained without cutting at ground, in both later VPM/NPM derivatives, with the adjacent plinth/wall finish. For AC07 it already has source ID10, approved RAL 7004 throughout (same as the adjacent plinth). This replaces the earlier untreated-foundation interpretation, not the source geometry.

Measured from unchanged census triangles: all 88 lower ID10 wall triangles reach Z <= -1 m; bottom range -2.025107384 .. -2.025095940 m. The 88 upper-band triangles share vertically corresponding bottom vertices: maximum XY mismatch 0.0000039321 m, below the diagnostic 0.0001 m correspondence tolerance. This confirms the existing drop, not a proposal to remodel it.

## Verification receipt

`verification.json` records the earlier 13/13 focused tests green through the suite-slot wrapper. The RAL 5015 vertical-joint update re-ran the same file: 13 failed / 3 passed on the previous record (12 stale answer-1 checks plus a missing `panel_rule`), then 16/16 passed. The two fail-closed probes (solid map on a panel row, horizontal joints) rejected 2/2. The tests-first commit `39d08a6` preserves the missing-record regression (12 failures observed before that commit and before adding the record); a further aggregate-count regression caught 2960 versus the draft typo 2944, then passed after correction. The operator-contract RED rejected the stale glass/question policy before the final record. The depth/drop regression additionally failed on the former CPU renderer record before native Blender publication.

Independent readback: 41/41 final bundle file hashes, 2/2 original/copy hashes, census and geometry-buffer hashes, and exact KPP sampled colours verified. Synthetic record mutations rejected 73/73 (12 missing IDs, 36 invalid areas including zero/NaN/inf, 12 unmapped IDs, 3 unknowns without a question, 1 false approval, 5 native-render contract violations, 3 drop contract violations and 1 untreated-foundation finish). This proves record consistency only. Reproduction scripts, original failures and final focused log are on Drive at `G:/Мой диск/AGR-evidence/tec26-oks/AC07/verification-v002/`, with their own `SHA256SUMS.txt`. No source geometry or material was mutated.

The receipt above is the pre-approval record (status was awaiting Artem). Gate 1 colour approval is now recorded in this file and in `materials.json`. ID 6 stays `to_verify`. VPM/NPM of this building remain a separate card; this card still does not build them. CI: not run (billing lock).

## Build legend check (presentation authority, 2026-10-22 16:1x/16:2x)

Colour authority for the build: `ТЭЦ26 на РР (1).pptx` slides 44 (А-Д, Д-А) and 45 (1-3, 3-1)
(`C:/x/tec26-oks/pptx/facades/slide44.png` sha256 0d8d6e5b…, `slide45.png` a2e8fed4…); DWG/PDF only where a slide is
silent. The «Условные обозначения» legend is binding; same RAL = the KPP colour.

| Hatch / legend line | Material | RAL (KPP colour) | Texture in the build |
|---|---|---|---|
| Сэндвич-панели, козырьки (blue) | sandwich panel, canopy | 5015 (34,113,179 = KPP Metal_RAL5015) | ribbed sandwich (Artem's vertical-joint texture), band above +2.500 incl. gables; roof ribbed down the slope; canopies/trims plain 5015 metal |
| Сэндвич-панели (light grey) | sandwich panel | 7047 (208,208,208 = KPP Cassette_RAL7047) | the SAME ribbed sandwich texture recoloured, +0.120..+2.500, never flat |
| Крыльца, двери, цоколь, водосток | porches, doors, plinth, gutters/downpipes | 7004 (150,153,146 = KPP Door_RAL7004) | plain |
| Рамы светопрозрачных конструкций | window/relief frames | 9016 (246,246,246 = KPP Frame_RAL9016) | plain |

| Source ID / region | Slide reading | Legend line | Build finish (vpm_textures.json) | Check |
|---|---|---|---|---|
| ID3 lower walls +0.120..+2.500 | light grey, vertical ribs, full height | Сэндвич-панели 7047 | PanelVJ68 / PanelVJ55 `lower_band` 7047, ribbed | ribs 67/54 joints per facade = sheet; compare grey row |
| ID1 vertical faces (+2.500..eaves, gables) | blue band with vertical ribs | Сэндвич-панели 5015 | PanelVJ68 / PanelVJ55 (5015 above z 2.5) | compare blue row 66+1 hidden / 54 |
| ID1 non-vertical (roof) | blue, ribs down the slope (54-55 dark runs on the slide roof rows, same step as the wall) | Сэндвич-панели 5015 | Roof_RAL5015 ribbed, plan UV u = y (rib contract of А-Д) | compare roof row: slide 54/53, VPM 54, NPM 54. Supersedes Gate-1 «ID1 кровля 7004» |
| ID2 roof edge / canopies | blue | козырьки 5015 | Trim_RAL5015 plain | visual |
| ID4 gutters/downpipes, ID5 snow guards | grey | водосток 7004 | Metal_RAL7004 | visual |
| ID6 round vents | drawn as circles with a dark inner shadow | (not in the legend) | Insert_RAL7004 | **question 1** |
| ID7 doors | grey | двери 7004 | Door_RAL7004 | visual |
| ID8/ID9 frames, surrounds | white | рамы 9016 | Frame_RAL9016 | visual |
| ID10 plinth + required drop | dark grey band 0.000..+0.120 | цоколь 7004 | Plinth_RAL7004 plain (below ±0.000 plain) | BUILD-DROP 4/4 sides covered |
| ID11 interior | not visible | - | Interior (KPP) | - |
| ID12 glazing | light glass | - | SM_Prg_2_MainGlass, M_Glass (no maps) | - |

Every sandwich-hatched wall surface carries the ribbed texture in its legend RAL; no flat grey wall remains
(build-v005 renders, `C:/x/tec26-oks/AC07/build-v005/compare/`, Drive `AGR-evidence/tec26-oks/AC07/build-v005/`).
