# Vatutino site slice (Ground + MAF + Flora) — D125 acceptance sheet, 2026-11-09

Verdict: **not passed**. Technical QA has open machine fails (below), the manual rows are unsigned, and
OKS / GeoJSON / lights are not delivered in this slice ([D231], [D126]). User acceptance and publication are
separate statuses; no agent writes the acceptance.

Scope [D231]: option A — Ground v015 + MAF v005 (urns 15E288/15E289 excluded, `jobs/VATUTINO-SITE/ground-exceptions-v015.json`)
+ «Верона» `*T3508` rows 1-10 + light Flora v003. No OKS in the NPM ZIP. Territorial code placeholder `0000`.

Run: `C:/x/t_5e2eb833/v009/` (driver `jobs/VATUTINO-SITE/run_delivery.py`, every command and exit code in
`commands.json`), placement input `C:/x/t_5e2eb833/place-v004/`. Renders: `C:/x/vatutino-site/v005/{npm,vpm}/`
(not in git). Blender 5.1.2 headless for every step; no 3ds Max used.

## Packages (new versioned paths, never in git)

| Package | ZIP | ZIP SHA-256 | FBX SHA-256 |
|---|---|---|---|
| NPM | `C:/x/t_5e2eb833/v009/packages/npm/0000_Vatutino.zip` | `e237dd49711f51c1ec247c362d7920a3444fd4cc57bfe9f79dae5dd532ee42a8` | `698d7afddf8bb9665db4e953e2053ff4f4e6f228d0da59d6ec0813624c0b42e4` |
| VPM | `C:/x/t_5e2eb833/v009/packages/vpm/SM_Vatutino_Ground.zip` | `f1ea6d627b7899924d8845fc81c49f5f4e250acc2be033f420f4b11b0b7ebd66` | `412bd1419a97a2b508f8a427fb91d48b06f99bcdd5f750365b9964a6daf71845` |
| NPM, code 0817 (candidate, see SINTEZ) | `C:/x/t_5e2eb833/v009/packages-0817/0817_Vatutino.zip` | `39944a63cfa4c93baecf6a0d42548f15d57c3465fef1973b0467c2489ab97e64` | same FBX bytes as NPM |

Rename after SINTEZ issues the code (one command, [D231]):
`uv run python jobs/VATUTINO-SITE/npm_code.py C:/x/t_5e2eb833/v009/packages/npm/0000_Vatutino.zip <code4> <out_dir>`.

## Readback of the FBX inside each ZIP (clean Blender process, `readback-{npm,vpm}.json`)

| Profile | Object | Triangles | Materials | Location / scale |
|---|---|---:|---:|---|
| NPM | `SM_Vatutino_Ground` (surface) | 46,479 | 12 | 0,0,0 / 1 |
| NPM | `SM_Vatutino_GroundEl` (MAF) | 56,847 | 1 (`M_Vatutino_GroundEl_1`) | 0,0,0 / 1 |
| NPM | `SM_Vatutino_Flora` | 64,454 | 11 (`M_Vatutino_Flora_ID<id>`) | 0,0,0 / 1 |
| VPM | `SM_Vatutino_Ground` (surface + MAF + Flora) | 559,442 (46,479 / 69,175 / 443,788) | 23 slots | 0,0,0 / 1 |
| VPM | `UCX_SM_Vatutino_Ground_001..727` | 727 pieces | 0 | 0,0,0 / 1 |

One shared pivot, transforms reset ([D100], GND-12). Images: NPM 15, VPM 69 PNG (23 slots × Diffuse/ERM/Normal).

## Rows

| # | Check | Result | Status |
|---|---|---|---|
| 1 | NPM budget [D097]/[D231] ≤ 180,000 | 167,780 = surface 46,479 + MAF 56,847 + Flora 64,454 (margin 12,220; route estimate 167,856) | pass |
| 2 | VPM budget GND-06, S_ter 25,854.04 − S_pz 9,110.08 = 16,743.96 m² → 4,500,000 | 559,442 non-UCX | pass (validate_package V003 says `review`: `ground_area_m2` not passed to the validator) |
| 3 | Flora atlas FLO-08 (#217 tool on a copy) | one 2048 diffuse `T_Vatutino_Flora_d_1` + one 2048 opacity `T_Vatutino_Flora_o_1`, 11 species → 11 tiles 504 px → IDs 101/103/105/115/120/204/205/212/223/224/230, scale 0.24609375 (504/2048), fill 66.6 %, source scene hash unchanged (`atlas/flora-atlas.json`) | pass |
| 4 | MAF atlas MAF-09/[D020] | one 512 `T_Vatutino_GroundEl_D_1` (6 materials, `atlas_maf.py`), MAF faces outside their slot: 0 (`npm/assembly.json` `maf_uv_outside`) | pass |
| 5 | Face Orientation, NPM, 5 fixed cameras (`face_orientation_*.png`) | red px: top 7,744; ob45 5,324; ob135 5,155; ob225 5,364; ob315 5,338. in the top view the red pixels lie in the planting and MAF areas (single-sided Flora cards), the open Ground surface is blue | review — user |
| 6 | Face Orientation, VPM | red px: top 4,084; ob45 3,625; ob135 3,598; ob225 3,765; ob315 3,933 | review — user |
| 7 | Model over SPOZU (`spozu_overlay.png`, `covering_differences.png`) | boundary, coverings, 568BF MAF and planting points aligned (visual check by the agent; the user signs) | review — user |
| 8 | Covering areas vs SPOZU hatches (`covering_deviations.json`) | 8 of 10 within ±0.5 m²; TileLight +159.2 m² (extra 164.3: transitions/curb strips drawn as TileLight), TileDark −10.4 m²; Decking 0/0 | review — user (TileLight/TileDark deltas) |
| 9 | Material-id render vs legend (`material_ids_top.png`, `material_id_legend.png`) | 24 materials, one colour each | review — user |
| 10 | Sections at spot heights (`section_01..48.png`) | 48 spots: 4 on the Ground, max \|ΔZ\| 0.006 m; 32 inside the 4 OKS footprint holes (no OKS in this slice), 12 just outside the outer edge (1.6–6.1 m) | partial — 44 not checkable on Ground |
| 11 | Counts vs schedule (`summary.json` `counts`) | MAF: 23 types placed = SPOZU count inside 568BF except `*T3510/2` 46 of 48 (2 urns excluded, [D231]); «Верона» rows 1-10 one each. Flora: 11 species placed = SPOZU points; schedule differs for Яблоня (24 vs 21 points) and Сосна горная (99 vs 106 points) — source discrepancy. VPM: Дерен белый (325) has no confirmed VPM model → excluded; 1,813 points without a library model, 77 outside the boundary | review — user |
| 12 | Sinking [D095]/[D096] | MAF sink 0.100 m, 0 mismatches (placement v004 report) | pass |
| 13 | validate_package NPM (package mode) | V001 fail (1 FBX, 2..21 expected: no OKS, [D231]); V012 pass; V002–V006, V014 not_run; V015, V017 manual | fail (recorded) |
| 14 | validate_package NPM `--scene` | V001 fail; V002 pass; V003 fail (Ground skirt drop 0.000 m, GND-03); V004 fail (Flora 430,938 / GroundEl 19,215 duplicate/self-intersection pairs; 8,211 isolated Flora polygons; co-directional overlaps); V005 pass; V006 fail (PNGs not embedded); V012 pass; V014 not_run; V015, V017 manual | fail |
| 15 | validate_package VPM (package mode) | V001 fail (no GeoJSON, [D126]); V007 pass; V012 pass; V002–V005, V008–V011, V013 not_run; V015–V017 manual | fail (recorded) |
| 16 | validate_package VPM `--scene` | V001 fail; V002 pass; V003 review (band) + fail (skirt 0.000 m); V004 fail (8,281,226 duplicate/self-intersection pairs, mostly Flora); V007 pass; V008 fail (one UV channel; 32,801 mirrored); V009 fail (texel density: "no edges"); V010 review (UCX gaps, advisory); V012 pass; V005, V011, V013 not_run | fail |
| 17 | SINTEZ AGR Checker 1.6.1 (Blender 5.1.2, `jobs/KPP1/scripts/run_agr_checker.py`) NPM `0000_Vatutino.zip` | classified LP: verified 34 / failed 10 / undefined 28; HP undefined 120 | fail (evidence) |
| 18 | SINTEZ NPM `0817_Vatutino.zip` | LP verified 35 / failed 9 / undefined 28 (2.10.3.1 archive name clears) | fail (evidence) |
| 19 | SINTEZ VPM `SM_Vatutino_Ground.zip` | classified HP: verified 52 / failed 14 / undefined 54 | fail (evidence) |
| 20 | MAF checks #185, Flora checks #191 | not checked: not run in this card | not checked |
| 21 | UCX (VPM) | 727 pieces from the v015 Ground route; V010 advisory review; NPM has no UCX | review |
| 22 | GeoJSON, light-source FBX [D126] | not delivered in this slice | not checked |
| 23 | OKS in the NPM ZIP [D231] | not delivered; V001 / SINTEZ 2.1.2 fail recorded | not checked |
| 24 | Territorial code [D231] | placeholder `0000`. The local SINTEZ checker says the model centre lies in «ЗАО Тропарёво-Никулино» → code **0817**; the official code comes from the SINTEZ upload | pending SINTEZ code |
| 25 | Flora texture defects (#369, PR #377) | KNOWN LIMITATION, not repaired here | review — user |

## SINTEZ failed items → regulation / V-code

| Profile | Req | Item | Cause | V-code / owner |
|---|---|---|---|---|
| NPM | 2.1.1 | ZIP ≤ 1 GB, УКЭП | no signature (customer's, [D163]) | V001 / not ours |
| NPM | 2.1.2 | 2–21 FBX | no OKS ([D231]) | V001 |
| NPM | 2.3.7 | duplicates and isolated | checker gives no detail; validate_package V004 counts Flora/MAF overlaps | V004 |
| NPM | 2.4.5 | materials = texture sets | 11 Flora ID materials share one atlas (FLO-08 keeps IDs) | V005 — conflict FLO-08 vs SINTEZ, user |
| NPM | 2.5.1 | textures packed in FBX | PNGs referenced, not embedded | V006 — assembly fix |
| NPM | 2.5.11 | OKS sets | `SM_Vatutino_Flora` > 2 materials | V005 — same as 2.4.5 |
| NPM | 2.10.3.1 | archive name | code `0000` (clears with 0817) | V012 — pending SINTEZ code |
| NPM | 2.10.3.4 | texture names | `T_Vatutino_Ground_D_<Slot>` vs `T_Vatutino_Ground_d_N` | V012 — naming fix |
| NPM | 2.10.3.5 | material names | `M_Vatutino_Flora_ID<id>` vs `M_Vatutino_Flora_N` | V012 — naming fix |
| NPM | 4.1.1 | color attributes | checker gives no detail (to inspect) | V005 |
| VPM | 2.1.1 | ZIP size, УКЭП | no signature | V001 / not ours |
| VPM | 2.2.1, 2.10.4.1 | GeoJSON | not delivered ([D126]) | V001 |
| VPM | 2.4.2 | no texture paths | extra Base Color links | V005 |
| VPM | 2.4.5 | ≤ 7 materials per object | 23 slots on one object | V005/V007 — VPM split needed |
| VPM | 2.5.2.1.1/.2/.4/.5 | UDIM: one UV channel, inside tile, no mirrored, padding | 464,631 polygons outside their UDIM, 32,801 mirrored, 19,555 near the edge | V008 — VPM UV remap |
| VPM | 2.6.2 | TD 512–1706 px/m | UDIM 1001 mean 310 px/m | V009 |
| VPM | 2.10.4.3/.4 | texture / material names | `M_Vatutino_Ground_<Slot>` vs `M_Vatutino_Ground_N` | V012 — naming fix |
| VPM | 4.1.1, 4.1.3 | color attributes; unwrapped polygons | checker gives no detail (to inspect) | V005/V008 |

## What remains before `passed`

1. Artem: Face Orientation, overlay, material-id, covering deltas (TileLight +159 m², TileDark −10 m²), counts and
   Flora known limitation (rows 5–11, 25) — sign or reject.
2. Machine fails inside the assembly (follow-up): embed PNGs in the NPM FBX, inspect SINTEZ 4.1.1, numbered
   material/texture names (`_N`), VPM UDIM remap and ≤ 7 materials per object, Ground skirt ≥ 1 m (GND-03, #295 line).
3. Decision for Artem: SINTEZ 2.4.5/2.5.11 (one material per texture set) vs FLO-08 (Flora material IDs per species
   on one atlas).
4. Not in this slice: OKS FBX, GeoJSON, lights ([D126], [D231]); the official territorial code from the SINTEZ upload.
