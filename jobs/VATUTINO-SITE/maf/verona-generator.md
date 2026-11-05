# Vatutino «Верона» benches — MAF generator gen-v001 (#790, model-maf step 3)

Status: **stage 3 of 3, `passed=false`** (technical QA green; user acceptance per model and the library entry are
open). Row 1 accepted by Artem (A4, seams by texture); rows 1-10 built with the same script and the proposed v006
material IDs, each row checked separately; showcase scene for Artem's per-model «да». Library entries: none yet.

Artem's answers 2026-11-03 (card t_96a3cc8a): web search for the «Верона» 18694 photo allowed; rows 6 = «пл.
дети1-3лет», 7 = «лестн 2», 8 = «лестн 2.1», 9 and 10 = «лестн 1»; «600» is the seat depth; seat height 0.466 from
MAF_0326, review; solid seat, no backrest «until a photo shows otherwise»; MAF_0326 sections accepted; the NPM MAF
budget overrun goes to a [D167] variants table, not silently.

## Plan shapes (`verona-plan-shapes.json`)

Source: copy `C:/x/vatutino-maf/v001/src/main.dwg` (sha256 `64e22677…46e4`, same as the original recorded in
`site-schedule.md`; the original was not opened) -> DXF copy (sha256 `88ff8730…0ed9`) -> `ezdxf`. The schedule
says «DWG block —», but the benches are drawn as blocks on layer `!_А101_маф`, each one LWPOLYLINE outline + one
HATCH. Inside plot `568BF` there are exactly 10 bench inserts for the 10 rows.

| Row | Schedule L×W×H mm | Block (insert handle) | Polyline handle | Generated plan m | Deviation m | Status |
|---|---|---|---|---|---|---|
| 1 | 2500×3900×600 | Скамья индивид общ отд 2 (`18AA78`) | `18AA77` | 3.919 × 2.501 (L) | 0.019 / 0.001 | found |
| 2 | 2500×6700×600 | Скамья индивид общ отд 1 (`18AA68`) | `18AA67` | 6.699 × 2.500 (L) | 0.001 / 0.000 | found |
| 3 | 6250×600×— | Скамья верона (`132D24`) | `132D23` | 6.250 × 0.600 (straight) | 0.000 / 0.000 | found |
| 4 | 5800×2900×600 | скамья индивид под андромедой (`195E1A`) | `195E19` | 5.800 × 2.896 (U) | 0.000 / 0.004 | found |
| 5 | 6080×600×— | Скамья верона 2 (`132D32`) | `132D31` | 6.085 × 0.600 (straight) | 0.005 / 0.000 | found |
| 6 | 4960×5530×600 | Скамья индивид пл. дети1-3лет (`18AA61`) | `18AA60` | 4.957 × 5.526 (5 segments, ~45° turns) | 0.004 / 0.003 | found |
| 7 | 4960×5530×600 | Скамья Индивид лестн 2 (`198ADB`) | `198ADA` | 4.921 × 0.600 (straight) | size from the DWG (Artem's mapping) | found |
| 8 | 4960×5530×600 | Скамья Индивид лестн 2.1 (`198BAC`) | `198C88` | 4.249 × 0.600 (straight) | size from the DWG (Artem's mapping) | found |
| 9 | 4960×5530×600 | Скамья индивид лестн 1 (`19865D`) | `19865C` | 2.000 × 0.600 (straight) | size from the DWG (Artem's mapping) | found |
| 10 | 4960×5530×600 | Скамья индивид лестн 1 (`19865E`) | `19865C` | 2.000 × 0.600 (straight) | size from the DWG (Artem's mapping) | found |

Rows 7–10: the schedule repeats 4960×5530 for all five
rows; that size fits only row 6, so rows 7–10 are checked against their DWG outline.

Each block has a second insert outside `568BF` (the drawing repeats the site); those are listed, not used.
Method: centreline = the outer (longer) side of the drawn strip offset inward by 0.3 m (drawn inner sides and end
caps are skewed by up to 0.45 m; the outer legs carry the schedule sizes). The third schedule value «600» equals
the drawn seat depth of every outline, so it is read as depth, not height (Artem confirmed).

## Section table (library analogue `MAF_0326`)

Analogue: `MAF_0326` (steel-loop legs + seat board + back panel; already used for `*T3510/1`), FBX
`C:/x/t_3e6ff1b3/library/fbx/MAF_0326_…_006.fbx` read in a factory Blender 5.1.2 (per connected part bbox;
`C:/x/vatutino-maf/gen-v001/probe/m0326.py`, exit 0; FBX sha256 identical before/after). Values Artem
disputes are changed only by him.

| Generator value | Catalogue id | Measured | Proposed |
|---|---|---|---|
| `seat_top` (seat height) | MAF_0326 | seat top 0.4465 − lowest −0.0196 = 0.466 m | 0.466 |
| `seat_thickness` | MAF_0326 | seat part z 0.3815..0.4465 = 0.065 m | 0.065 |
| `post` (leg tube section) | MAF_0326 | leg parts 0.0437 / 0.0391 / 0.0410 m thick | 0.040 |
| `post_inset` (leg from seat side) | MAF_0326 | leg frame 0.4417 under seat 0.4566 -> 0.0075 m | 0.0075 |
| `end_overhang` | MAF_0326 | seat end to leg centre 0.336 / 0.335 m | 0.335 |
| `max_leg_span` | MAF_0326 | leg centres 1.130 m apart | 1.130 |
| `depth` | DWG outlines (not the analogue) | 0.600 m in all ten outlines (MAF_0326 seat is 0.457) | 0.600 |
| board width, slat pitch | MAF_0326 | not measurable: solid seat, no slats | question |
| backrest | MAF_0326 | back panel 1.408 × 0.049 × 0.445, top 0.80 | question (depends on «Верона») |

## Module reference (model-maf step 2, web search allowed by Artem)

Manufacturer: **Hobbyka (Хоббика)**, «Скамейка стальная «Верона»», article **18694** (the schedule names the
maker «Города»; the article number matches Hobbyka, the maker name does not — question to Artem).
- Product page: https://hobbyka.ru/product/skamya_verona/ («артикул 18694»)
- Passport PDF: https://hobbyka.ru/upload/iblock/6c5/hbet36336ro66b2qcaivn19drci2hcay.pdf — L 8.0, **B 0.6, H 0.45**,
  3 sections, steel powder-coated (standard RAL 9005 / 7016), timber beams with stain + lacquer.
- Copies (outside git): `C:/x/vatutino-maf/gen-v001/web/` (`verona.pdf`, `img1..4.jpg`, hashes in `SHA256SUMS.txt`).

What the passport shows, against the accepted MAF_0326 sections: a **closed box** 0.6 × 0.45, all four sides clad
with four horizontal timber courses, a slatted top, no backrest, low steel feet under the section joints — not a
0.065 slab on 0.04 tube legs. B 0.6 equals the DWG depth (independent confirmation). H 0.45 replaces the 0.466
(card fallback: a missing height comes from the module reference). Because this contradicts an accepted answer,
row 1 is built in both forms and Artem chooses.

## Generator

`tools/library/maf_gen_bench.py` (pure, no bpy), one form, config key `form` = `clad_box` (`build_clad_box`,
Artem 2026-11-03: «Верона» = variant A, board seams by texture): closed timber box, one top quad per segment mitred
through the corners, one side ring, the board layout (`top_boards` + 2 frame boards across the top, `courses` on the
sides) in the generator's `face_uv`, steel foot plates let into the bottom. One welded quad mesh: no T-junction (bottom
bands whose edges carry different vertex counts get a 3-to-1 quad reduction with interior points only), convex quads,
closed manifold, pivot bbox centre / Z 0, longest segment on +X. The rejected forms (slab on posts, variant B
`build_bench` + `verona-gen-b.config.json`; seams as geometry, `seams: geometry`) were removed in #819; git history
keeps them, and the A3 / B results below are history. The writer exits 4 on any other `form`.
`centreline_from_outline` turns a DWG strip outline into the run. Writer `tools/blender/maf_gen_bench_build.py`
(atlas v005 materials, box UV inside the 512 slots, triangulated FBX per MAF-18, hard edges by angle 40°, NPM + VPM,
refuses overwrite); checks `tools/library/maf_gen_bench_checks.py` (readback -> `maf_findings`, dimensions within
0.10 m [D094] of the per-row reference `verona-reference-sizes.json` given with `--reference` (rows 1-6 schedule,
7-10 DWG outline; without it only the generator's own dims), atlas-slot count; exit 0 only when every row/role
passes, 1 on any fail, 2 on an input error, #817); overlap gate `dt qa xview`. Tests: `tests/test_maf_gen_bench.py` (synthetic straight /
L / U / skewed / random runs, clad box with seams by texture).

| Config | Form | Parameters (source) |
|---|---|---|
| `verona-gen.config.json` (A4.1, current) | `clad_box` | every value with its source in `param_sources`; summary below |

A3 parameters (passport `verona.pdf` p.1 at 0.0041 m/px in the end view, Artem's photo
`C:/x/vatutino-maf/ref/verona_hobbyka_photo_artem.jpg`): H 0.45, depth 0.6, 4 courses of 0.100 + 3 ring seams
**0.010 wide** (end view: course 24 px, gap 2-3 px) × 0.020 deep (not dimensioned, review); top frame 0.045 +
**9 slats** 0.0456 + 10 seams 0.010 × 0.020 — Artem's «~11» read as 11 equal boards across the top = 2 frame boards +
9 slats (the passport render shows 5-6 seams near the end at low resolution, review); steel plates 0.10 × 0.54 ×
0.02 (end view: plate inset 0.03 per side) at 0.15 from the free ends and <= 2.67 m apart (3 sections in 8.0 m).
Materials: body `larch_light_oak`, plates `steel_ral7047` (placeholder: the passport's RAL 7016 is not in v005).

## Row 1, first piece (draft, `C:/x/vatutino-maf/gen-v001/{a,b}`)

Commands (all exit 0):
```
blender --background --factory-startup --python-exit-code 1 --python tools/blender/maf_gen_bench_build.py -- jobs/VATUTINO-SITE/maf/verona-gen[-b].config.json jobs/VATUTINO-SITE/maf/verona-plan-shapes.json C:/x/vatutino-maf/v005-set/atlas/vatutino_maf_atlas_512.json C:/x/vatutino-maf/v005-set/atlas/vatutino_maf_atlas_512.png C:/x/vatutino-maf/gen-v001/<a|b> 1
blender ... --python tools/blender/fbx_readback.py -- C:/x/vatutino-maf/gen-v001/<a|b>/<npm|vpm>/VAT_MAF_T3508_01.fbx C:/x/vatutino-maf/gen-v001/<a|b>/readback/<npm|vpm>_VAT_MAF_T3508_01.json
uv run python tools/library/maf_gen_bench_checks.py C:/x/vatutino-maf/gen-v001/<a|b>/build-report.json C:/x/vatutino-maf/gen-v001/<a|b>/readback C:/x/vatutino-maf/gen-v001/<a|b>/checks.json
uv run dt qa xview C:/x/vatutino-maf/gen-v001/<a|b>/<npm|vpm>/VAT_MAF_T3508_01.fbx --out .../readback/xview_<npm|vpm>_VAT_MAF_T3508_01.json --profile <NPM|VPM>
```

| Variant | Role | Tris | Readback size m | vs schedule 3.9 × 2.5 | `maf_findings` | xView faces | UV faces outside slot | FBX sha256 |
|---|---|---|---|---|---|---|---|---|
| A | NPM | 388 | 3.919 × 2.501 × 0.450 | 0.019 / 0.001 pass | 3 pass, 0 fail, 0 not_run | 0 | 0 / 388 | `829179a0…d3da` |
| A | VPM | 388 | 3.919 × 2.501 × 0.450 | 0.019 / 0.001 pass | 3 pass | 0 | 0 / 388 | `4894c759…` |
| B | NPM | 516 | 3.919 × 2.501 × 0.466 | 0.019 / 0.001 pass | 3 pass | 0 | 0 / 516 | `1bc34618…29ab` |
| B | VPM | 516 | 3.919 × 2.501 × 0.466 | 0.019 / 0.001 pass | 3 pass | 0 | 0 / 516 | `f07f7b2d…` |

Full hashes: `C:/x/vatutino-maf/gen-v001/SHA256SUMS.txt`. Picture for Artem:
`C:/x/vatutino-maf/gen-v001/renders/row1_variants_v002.png` (A top, B bottom, NPM left, VPM right, text labels).
Originals unchanged: `main.dwg` copy `64e22677…46e4`, MAF_0326 FBX `f3f9653c…2edc` (same as before).

## Row 1, A3 with modelled seams (`C:/x/vatutino-maf/gen-v001/a3-seams`) - superseded by A4

Same four commands as above with `<a|b>` = `a3-seams` (all exit 0). Readback NPM = VPM: 648 tris,
3.919 × 2.501 × 0.450 m (deviation from the generator < 1e-6 m; schedule 3.9 × 2.5: 0.019 / 0.001, pass);
`maf_findings` 3 pass, 0 fail, 0 not_run (smoothing 40°, outward normals, dimensions); `dt qa xview` NPM and VPM:
0 overlapping faces, 0 overlapping vertices; UV faces outside their 512 slot 0 / 648 (wood 598, steel 50).
FBX sha256 NPM `4d2112a4…2562`, VPM `709568b3…53f2`. Picture for Artem (photo | close-up, NPM | VPM, caption):
`C:/x/vatutino-maf/gen-v001/renders/row1_a3_vs_photo_v003.png` (`5458abd8…8ad8`); render/compose scripts in
`gen-v001/probe/`, all hashes in `gen-v001/SHA256SUMS.txt`.

| Row | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Sum |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A3 tris (pure generator; row 1 = FBX) | 648 | 672 | 484 | 836 | 484 | 1244 | 460 | 460 | 428 | 428 | 6 144 |

NPM MAF share [D097]: v005 set 57 628 + row 1 648 = 58 276 (under 60 000); + all ten rows 6 144 = **63 772, over the
share by 3 772**. A light NPM without modelled seams would be the earlier box A (row 1 388, ten rows 3 704 -> 61 332); [D164]
allows it only as a separate light version, never a substitute, and only if Artem chooses it; decision pending with the colour ID (RAL 7016).

## Budget [D097], [D167] (variants A/B before the seams, superseded by A3 above)

| Variant | Ten rows NPM tris (pure generator, same as FBX for row 1) | NPM MAF total with v005 set 57 628 | vs share 60 000 |
|---|---|---|---|
| A passport box | 3 704 | 61 332 | over by 1 332 |
| B MAF_0326 slab | 5 176 | 62 804 | over by 2 804 |

Per row A / B: 388/516, 452/708, 300/428, 540/796, 300/428, 908/1100, 236/364, 236/364, 172/236, 172/236.
Both exceed the share; NPM = VPM (no light version: a box of 388 tris has nothing to remove [D164]). Options for
Artem [D167]: (1) accept the overrun inside the shared 180 000 NPM Ground budget; (2) light NPM for other v005
positions; (3) take the 1 332 from another MAF share. Not decided here.

## Row 1, A4: seams by texture (`C:/x/vatutino-maf/gen-v001/a4-texture`), current

Artem 2026-11-03 correction (replaces «seams as geometry»): «wood seams like these are shown BY TEXTURE, not geometry.
Keep the box as simple geometry (no board gaps modelled)». Config `verona-gen.config.json` = `gen-v001-A4`,
`params.seams` = `texture`: `build_clad_box` makes one top quad per segment and one side ring from `foot_height` to
`height` (steel plates let into the bottom as before) and returns `face_uv` on a pattern of 11 equal boards
(`top_boards` 9 + 2 frame boards): top t = lateral / depth (mitred, the boards turn the corner), sides and ends
t over 4 / 11 (4 courses), so every texture seam falls on a board joint. Writer: `face_uv` mapped into the slot
without inset (an inset would shift the seams off the joints).

Atlas `C:/x/vatutino-maf/gen-v001/atlas-a4/` (copy; v005 atlas unchanged, sha `41e8f983…`, `5099d135…`, `5aaf8b55…`
before and after): `tools/materials/atlas_maf.py material-list.json` = the four v005 entries + patterned
`larch_light_oak_boards` (256 px cell, content 248 px), texture `verona_boards_11.png` from `make_boards.py`
(SYNTHETIC: base v005 larch `#C49A6C` ±5 % per board, grain lines, seam `#5A4026` 6 px of 512 = 0.0071 m on a top
board 0.0545 m, 0.014 m on a side course 0.1075 m). The packer moved the four solid cells to x 256..384 in this copy.

Commands (all exit 0): the build / readback / checks / xview lines above with `<a|b>` = `a4-texture` and the atlas
`gen-v001/atlas-a4/vatutino_maf_atlas_512_a4.{json,png}`.

| Role | Tris | Readback m | vs 3.9 × 2.5 | `maf_findings` | xView faces / verts | UV outside slot | FBX sha256 |
|---|---|---|---|---|---|---|---|
| NPM | 160 | 3.919 × 2.501 × 0.450 | 0.019 / 0.001 pass | 3 pass, 0 fail, 0 not_run | 0 / 0 | 0 / 160 | `a877ec89…0e76` |
| VPM | 160 | 3.919 × 2.501 × 0.450 | 0.019 / 0.001 pass | 3 pass, 0 fail, 0 not_run | 0 / 0 | 0 / 160 | `8f3b4d58…1033` |

Picture for Artem (photo | end close-up, NPM | VPM, caption): `C:/x/vatutino-maf/gen-v001/renders/row1_a4_vs_photo_v004.png`
(`0bdf3324…900a`); scripts `gen-v001/probe/{render_row1,compose}_a4.py`; all hashes in `gen-v001/SHA256SUMS.txt`.

| Row | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Sum |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A4 tris (pure generator; row 1 = FBX) | 160 | 184 | 124 | 220 | 124 | 372 | 100 | 100 | 68 | 68 | 1 520 |

NPM MAF share [D097]: v005 set 57 628 + row 1 160 = 57 788; + all ten rows 1 520 = **59 148, under 60 000 by 852**.
NPM = VPM, no light version needed [D164]. Open for Artem: row 1 «да»; the board cell as a new material ID or a
pattern of `larch_light_oak` (v005 list unchanged until he decides); RAL 7016 steel ID (plates still `steel_ral7047`).

## Rows 1-10 with the proposed v006 IDs (`C:/x/vatutino-maf/gen-v001/rows-v006p-2`), current

Artem 2026-11-03 (card t_96a3cc8a): «Row 1 (render row1_a4_vs_photo_v004, simple box 160 tris, seams in texture)
ACCEPTED - build rows 2-10 with the same script. Board texture = NEW material ID `larch_light_oak_boards` (D152: one
material ID per texture), added to the atlas copy and the ID list as a proposed v006 entry. Supports = NEW ID
`steel_ral7016` per the passport, replacing the temporary steel_ral7047.»

- Config `verona-gen.config.json` = `gen-v001-A4.1`: materials seat `larch_light_oak_boards`, frame `steel_ral7016`;
  geometry parameters unchanged from the accepted A4.
- ID list: `verona-material-ids-v006-proposal.json` (proposed; site-set atlas v005 and `library/maf/material_ids_v005.json`
  unchanged, sha `5099d135…82b8` / `21a605c7…1ff9` before and after). Atlas copy `gen-v001/atlas-v006/`
  (`tools/materials/atlas_maf.py`): boards 256 px at slot (0, 0), `steel_ral7016` #383E42 64 px. Note for Artem: the
  library list v005 already has id 2 `paint_ral7016` (#383E42).
- Bug found on row 2 and fixed test-first: the first build (`gen-v001/rows-v006p`, stopped at row 2, exit 1) refused
  the top UV, s = 1.0000336, because a corner a hair wider than 90° puts the mitre past `length + depth/2`. Regression
  `test_texture_box_uv_stays_inside_unit_square_at_any_corner`: RED 2 failed (`509fdb86`) -> GREEN
  101 passed (`0028f7e3`): s is now normalised over the top quad's own extent. `gen-v001/v006-rows` (row 1 only, from
  the interrupted previous run) is superseded and not used.

Commands (all exit 0; Blender 5.1.2, factory startup):
```
blender --background --factory-startup --python-exit-code 1 --python tools/blender/maf_gen_bench_build.py -- jobs/VATUTINO-SITE/maf/verona-gen.config.json jobs/VATUTINO-SITE/maf/verona-plan-shapes.json C:/x/vatutino-maf/gen-v001/atlas-v006/vatutino_maf_atlas_512_v006p.json C:/x/vatutino-maf/gen-v001/atlas-v006/vatutino_maf_atlas_512_v006p.png C:/x/vatutino-maf/gen-v001/rows-v006p-2
blender ... --python tools/blender/fbx_readback.py -- <rows-v006p-2>/<npm|vpm>/VAT_MAF_T3508_<NN>.fbx <rows-v006p-2>/readback/<npm|vpm>_VAT_MAF_T3508_<NN>.json   (20 runs)
uv run python tools/library/maf_gen_bench_checks.py <rows-v006p-2>/build-report.json <rows-v006p-2>/readback <rows-v006p-2>/checks.json --reference jobs/VATUTINO-SITE/maf/verona-reference-sizes.json   (#817: exit 0 = verdict pass, 10/10 rows, max deviation 0.019 m)
uv run dt qa xview <rows-v006p-2>/<npm|vpm>/VAT_MAF_T3508_<NN>.fbx --out <rows-v006p-2>/readback/xview_<npm|vpm>_VAT_MAF_T3508_<NN>.json --profile <NPM|VPM>   (20 runs)
```

One verify line per generated MAF (hard edges by angle 40°; materials in the readback: only
`larch_light_oak_boards` 2 080 faces and `steel_ral7016` 960 faces over all 20 FBX):

| Row | Set id | Tris NPM / VPM | Readback m | Reference m | Deviation m [D094] | `maf_findings` NPM | xView faces / verts | UV outside slot NPM / VPM | FBX sha256 NPM / VPM |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `VAT_MAF_T3508_01` | 160 / 160 | 3.919 × 2.501 × 0.450 | 3.9 × 2.5 (schedule) | 0.019 / 0.001 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `9399331f…` / `485fd6aa…` |
| 2 | `VAT_MAF_T3508_02` | 184 / 184 | 6.699 × 2.500 × 0.450 | 6.7 × 2.5 (schedule) | 0.001 / 0.000 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `b1a9e281…` / `25a69836…` |
| 3 | `VAT_MAF_T3508_03` | 124 / 124 | 6.250 × 0.600 × 0.450 | 6.25 × 0.6 (schedule) | 0.000 / 0.000 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `d859e106…` / `7a992eca…` |
| 4 | `VAT_MAF_T3508_04` | 220 / 220 | 5.800 × 2.896 × 0.450 | 5.8 × 2.9 (schedule) | 0.000 / 0.004 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `f526a93a…` / `665f5ef5…` |
| 5 | `VAT_MAF_T3508_05` | 124 / 124 | 6.085 × 0.600 × 0.450 | 6.08 × 0.6 (schedule) | 0.005 / 0.000 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `6df0c5e6…` / `bd761aef…` |
| 6 | `VAT_MAF_T3508_06` | 372 / 372 | 4.957 × 5.526 × 0.450 | 4.96 × 5.53 (schedule) | 0.003 / 0.004 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `db0b3aa7…` / `458c1e44…` |
| 7 | `VAT_MAF_T3508_07` | 100 / 100 | 4.921 × 0.600 × 0.450 | 4.921 × 0.6 (DWG outline (Artem's mapping)) | 0.000 / 0.000 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `e010fb2e…` / `8ee7c255…` |
| 8 | `VAT_MAF_T3508_08` | 100 / 100 | 4.249 × 0.600 × 0.450 | 4.249 × 0.6 (DWG outline (Artem's mapping)) | 0.000 / 0.000 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `bd96d825…` / `1d6d458f…` |
| 9 | `VAT_MAF_T3508_09` | 68 / 68 | 2.000 × 0.600 × 0.450 | 2.0 × 0.6 (DWG outline (Artem's mapping)) | 0.000 / 0.000 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `2fa07725…` / `e27aa92c…` |
| 10 | `VAT_MAF_T3508_10` | 68 / 68 | 2.000 × 0.600 × 0.450 | 2.0 × 0.6 (DWG outline (Artem's mapping)) | 0.000 / 0.000 pass | 3 pass, 0 fail, 0 not_run / VPM same=True | 0 / 0 | 0 / 0 | `1e2bc70d…` / `31f34ed0…` |

Height 0.45 m (passport) for every row; the schedule's third value «600» is the depth (Artem). Full hashes in
`C:/x/vatutino-maf/gen-v001/SHA256SUMS.txt`.

### Budget [D097]

| | Raw | NPM tris | VPM tris | Count |
|---|---|---|---|---|
| Rows 1-10 «Верона» | = NPM (no heavier source) | 1520 | 1520 | 10 |
| v005 set (13 positions, unchanged) | — | 57 628 | — | 13 |
| **NPM MAF total** | | **59 148** of the MAF share 60 000 (NPM 180 000) | | 23 |

Under the share by 852. NPM = VPM, no light version [D164].

### Showcase (review-showcase practice)

Scene `C:/x/vatutino-maf/gen-v001/showcase-3/showcase_rows_v006p.blend` (`79f19478…`): ten NPM | VPM pairs, a text
object right of each pair with the schedule row (`*T3508/<n>`, size, tris, set id). Renders
`showcase_rows_v006p_top.png` (`6cd9b7ef…`), `showcase_rows_v006p_oblique.png`, close-ups of rows 2, 4, 6
(`closeup_VAT_MAF_T3508_0{2,4,6}_NPM.png`). Scripts `gen-v001/probe/showcase_{rows,closeups}_v006p.py`.

### Library

No library entry yet. The card allows one per model only after Artem's «да» on that model; row 1's «да» was given on
the A4 render with the temporary `steel_ral7047`, and both IDs it now uses are proposed v006, not in the library list
v005. `catalogue.json` is generated from the library `.max` scene (counts, clusters), so a generated entry also needs a
decision on how it is recorded («generated, gen-v001»). Open for Artem: per-model «да» on the showcase (rows 1-10),
and whether the library entry uses the proposed names or library id 2 `paint_ral7016`.

Originals unchanged before/after: `main.dwg` copy `64e22677…46e4`, MAF_0326 FBX `f3f9653c…2edc`, site atlas v005
`5099d135…` / `5aaf8b55…`, `material_ids_v005.json` `21a605c7…`.
