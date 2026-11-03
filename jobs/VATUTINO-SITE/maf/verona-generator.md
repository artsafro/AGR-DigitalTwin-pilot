# Vatutino «Верона» benches — MAF generator gen-v001 (#790, model-maf step 3)

Status: **stage 2 of 3, `passed=false`** — plan shapes of all ten rows, the module passport, the Blender writer and
row 1 (two variants, draft) are done; the variant choice, the module reference and the first piece wait for Artem's
«да». Rows 2–10 are not built.

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

`tools/library/maf_gen_bench.py` (pure, no bpy), two forms selected by the config key `form`:
- `slab_on_posts` (`build_bench`): plan run + sections -> slab with square posts let in (variant B, MAF_0326).
- `clad_box` (`build_clad_box`, Artem 2026-11-03: «Верона» = variant A, seams are geometry): closed timber box,
  `courses` side boards with ring seams wrapping the whole outline, a top frame around `top_boards` lengthwise slats
  with seams that stop at the end frames and turn mitred through the corners, steel foot plates let into the bottom.
  One welded quad mesh: no T-junction (bands whose edges carry different vertex counts get a 3-to-1 quad reduction
  with interior points only), convex quads, closed manifold, pivot bbox centre / Z 0, longest segment on +X.
`centreline_from_outline` turns a DWG strip outline into the run. Writer `tools/blender/maf_gen_bench_build.py`
(atlas v005 materials, box UV inside the 512 slots, triangulated FBX per MAF-18, hard edges by angle 40°, NPM + VPM,
refuses overwrite); checks `tools/library/maf_gen_bench_checks.py` (readback -> `maf_findings`, dimensions within
0.10 m [D094], atlas-slot count); overlap gate `dt qa xview`. Tests: `tests/test_maf_gen_bench.py` (synthetic straight /
L / U / skewed / random runs for both forms), 81 passed.

| Config | Form | Parameters (source) |
|---|---|---|
| `verona-gen.config.json` (A3, current) | `clad_box` | every value with its source in `param_sources`; summary below |
| `verona-gen-b.config.json` (B, not chosen) | `slab_on_posts` | the MAF_0326 section table above, height 0.466 |

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

## Row 1, A3 with modelled seams (`C:/x/vatutino-maf/gen-v001/a3-seams`)

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
