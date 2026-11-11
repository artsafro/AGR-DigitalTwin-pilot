# KPP1 rerun after Gate 1 — issue #1209, run `issue-1209-rerun-v001`

Agent: dt-worker (Hermes Kanban card t_d1f84643), 2026-11-11. Base: `origin/main` c3975c4d. Gate 1 given by
Artem 2026-11-11 («принимаю рекомендации») = [D238]. Max busy (Artem's) -> offline kernel route only, `path: deviation`.
Checklist: `jobs/KPP1/job.yaml`; machine walk: `jobs/KPP1/rerun-1209/walk-v001.json`.

## Result in one line

VPM `SM_Kpp_1.fbx` (6 278 triangles) built first on the offline kernel route, NPM `0000_Kpp_1_01.fbx`
(4 178) derived from it; both read back in Blender 5.1.2. `validate_package --scene` gives **`passed=false`**
for both (exit 1); the exact blockers are listed below. Visual and checker gates wait for the user.

## Levels (answer 5 of [D238])

Storey **3.900** and roof **7.909** (and the roof base 7.700) are **from Revit (`jobs/KPP1/object.json`), not
confirmed by the architect for R1**. АС.03 has no section sheet; the architect question stays open in
`jobs/KPP1/questions.md` (Q-R1-LEVELS).

## Commands (exact)

```
# 0. copies, SHA-256 equal to inputs-manifest.json (L01 cb74ba14..., L03 ad1de2b2...)
cp ".../Downloads/22Е56-АР2-1002-АС.03-R1_L0{1,3}_без подписей.dwg" C:/x/kpp1/r1209/L0{1,3}.dwg
# 1. DWG -> DXF, AutoCAD 2025 accoreconsole, script: _.DXFOUT <dxf> _V _2018 16 _.QUIT _Y
accoreconsole.exe /i C:/x/kpp1/r1209/L01.dwg /s C:/x/kpp1/r1209/L01.scr   # DXF sha256 f2b6dda8...
accoreconsole.exe /i C:/x/kpp1/r1209/L03.dwg /s C:/x/kpp1/r1209/L03.scr   # DXF sha256 72f9397e...
# 2. L03 contour (one --map=<line> per line of cold-run-1172/layer-map-L03.txt)
uv run python tools/methods/body/plan_from_dxf.py extract C:/x/kpp1/r1209/dxf/L03.dxf plan-contours-L03.json \
  plan-account-L03.json --map=... --z0 0 --levels 0,3.9,7.909 --contour-source hatch --origin-mm 25884.5,0 \
  --frame-shift-m=-14.655,-5.355                       # coverage pass, 99.23 %, bbox delta 0.064 m
# 3. kernel prisms + L01 opening schedule
uv run python jobs/KPP1/rerun-1209/build_parts.py plan-contours-L03.json C:/x/kpp1/r1209/dxf/L01.dxf parts-mesh-v002.json
# 4. Blender 5.1.2 (agent-owned, background, no scene file [D233]): union, cuts, fills, UV, FBX VPM then NPM
blender --background --factory-startup --python-exit-code 1 --python jobs/KPP1/rerun-1209/build_blender.py -- \
  parts-mesh-v002.json out-v003 out-v003/build-report.json
# 5. readback, validation, previews (per FBX)
blender --background --factory-startup --python-exit-code 1 --python tools/blender/fbx_readback.py -- <fbx> <fbx>.readback.json
uv run python tools/qa/validate_package.py <fbx> --scene --json > <fbx>.validate.json
blender --background --factory-startup --python jobs/KPP1/rerun-1209/render_preview.py -- <fbx> <fbx>.preview
# 6. walk
uv run python -m dt_ai.procedure jobs/KPP1/job.yaml --root . --output jobs/KPP1/rerun-1209/walk-v001.json
```

Evidence (not in git, rule 57): `G:/Мой диск/AGR-evidence/KPP1/rerun-1209/` — both FBX, readback JSON,
validate JSON, 4 preview PNG, parts-mesh / plan JSON; `SHA256SUMS` sha256
`73ddf514ee545cb5f39b54c2c080fbab2408e344182d1d8a2fa88adfe127da3b` (copy: `evidence-SHA256SUMS.txt`).

## What was built ([D238] answers 1-3)

| Item | Source | Built |
|---|---|---|
| Band 0.000-3.900 | L03 wall hatch (plan_from_dxf, 1 polygon, 268 vertices) cut to the L1 rectangle: 266.68 m², with the south recess 43.91 m² (x -7.725..-2.735, y up to 3.925) | prism |
| Entrance-frame bumps | hatch minus the L1 rectangle: 6 pieces, 0.37-0.44 m² each | prisms 0.000 -> **3.300** (frame top = L01 Южный frame hatch band +2.700..+3.300) |
| Band 3.900-7.700 | L1 rectangle 27.66 x 11.66 m (Revit cassette planes -0.33 / 27.33 x -0.33 / 11.33, frame shift -14.655 / -5.355) | prism; Boolean union with the bands below (Exact) |
| Roof_Plate | rectangle inset 0.35 m, 7.700 -> 7.909 | slab |
| Parapet | rectangle ring 0.35 m, 7.700 -> 8.650 (L01 +8,650 on all four facades) | prism |
| Openings | L01 glazing / door inserts (`A-GLAZ-CURT-OTLN`, `A-GLAZ-____-OTLN`, `A-DOOR-____-OTLN`) per facade view, merged within 40 mm: **53 cut** (Ю 27, С 14, З 8, В 4; 11 doors, 42 windows), 15 dropped (< 300 mm: tags and fragments), each with the removed volume | Boolean difference, depth from the first body face + 0.30 m |
| Windows / Doors | frame ring 60 x 70 mm + glass pane / door leaf in each opening | boxes |
| CurtainWall_Mullions | `A-GLAZ-CWMG-OTLN` inserts: 171 listed, **7 kept** (centre inside an opening) | boxes |
| Stair, Grille | not built (Stair: no time in this run; Grille = to_texture) | — |

Facade view placement on L01 (grid lines): Южный u = X (axis 1 at 0, 4 at 27000); Северный u = 70955 - X;
Западный u = 92848 - X (axis А at 92848); Восточный u = X - 102956. Elevation = drawing Y (mm).

## Triangles vs [D238] answer 4 and BODY-F

| Part | VPM built | VPM budget | NPM built | NPM budget |
|---|---:|---:|---:|---:|
| Body_Walls | 2 970 | 300 000 | 2 970 | 60 000 |
| Roof_Plate | 12 | 20 000 | 12 | 4 000 |
| Parapet | 32 | 40 000 | 32 | 6 000 |
| Windows (frames 2 016 + glass 504) | 2 520 | 250 000 | 504 (glass only) | 30 000 |
| Doors | 660 | 150 000 | 660 | 20 000 |
| CurtainWall_Mullions | 84 | 120 000 | 0 (to texture) | 15 000 |
| Stair | 0 (not built) | 80 000 | 0 | 10 000 |
| Grille | 0 (to_texture) | 0 | 0 | 0 |
| **FBX total** | **6 278** (+48 UCX) | BODY-F 1 000 000 | **4 178** | BODY-F 150 000 |

FBX meshes follow the regulation grammar (V012 pass): VPM `SM_Kpp_1_Main`, `SM_Kpp_1_MainGlass`,
`UCX_SM_Kpp_1_Main_001..004`; NPM `SM_Kpp_1_001_Main`, `SM_Kpp_1_001_MainGlass`. Per-part counts are taken
before the join (`build-report.json`).

## validate_package (`--scene`), exact blockers

VPM `SM_Kpp_1.fbx` — `passed: false`, exit 1 (`SM_Kpp_1.validate.json`):

| Stage | Check | Value | Limit |
|---|---|---|---|
| V004 | topology defects | `SM_Kpp_1_Main` duplicates_and_self_intersections = 170 (parts joined into one mesh touch / intersect: frames, mullions, parapet on the body) | 0 |
| V004 | co-directional clearance | 3 pairs < 5 mm, 14 pairs 5-20 mm | none < 20 mm |
| V007 | textures | not_run: no Diffuse/ERM/Normal PNG | required |
| V009 | texel density | not_run: no diffuse texture | 512..1706 px/m |
| V010 | UCX coverage and offsets | not_run; piece gap advisory review (4 boxes touch) | — |
| V001 / V011 / V013 | archive, GeoJSON, MSK-77 point | not_run: no ZIP, no GeoJSON (MSK-77 placement deferred by the user) | required |
| V003 | master quads | not_run: no quad master (`--master`) | [D021] |
| V015 / V016 / V017 | manual | not signed (waits visual) | signed |

Pass: V002 (binary FBX, 1 unit = 1 m), V005 (shaders), V008 (one UV channel, UDIM 1001), V012 (names).

NPM `0000_Kpp_1_01.fbx` — `passed: false`, exit 1: V004 co-directional clearance (1 pair < 5 mm, 4 in 5-20 mm),
V006 no embedded PNG atlas, V001 / V014 not_run (no ZIP, Moscow coordinates deferred), V003 not_run,
V015 / V017 manual. Pass: V002, V005, V012.

## Gates

| Gate | Status | Receipt | Why |
|---|---|---|---|
| inputs | review | cold-run manifest, object.json, plan-contours.json, `rerun-1209/inputs-v001.json` | DWG copies re-hashed equal; still outside the asset store (G2 of the cold run) |
| parts | review | `rerun-1209/parts-v002.json` (`confirmed`, gate1 Artem 2026-11-11 [D238]) | the walker keeps it review while the architect question (levels) is open — [D238] answer 5 |
| operations | review | `build-report.json`, `build_parts.py`, `build_blender.py` | built on the offline route (`path: deviation`, Max busy); Stair not built, mullions 7 / 171 |
| budgets | review | `build-report.json` | every part and both FBX under [D238] 4 / BODY-F; review until the visual gate |
| export_readback | review | `SM_Kpp_1.validate.json`, `0000_Kpp_1_01.validate.json` | read back; `passed=false` (blockers above) |
| report | review | this file | |
| visual | missing — waits-user | — | previews on the evidence folder, board review not done |
| checker | missing — waits-visual | — | SINTEZ after visual acceptance |

## Procedure gaps found in this run

| # | Where | What | Proposed |
|---|---|---|---|
| R1 | TASK_TO_MODEL `operations` / parts list | The PartsList has per-part budgets, but the VPM/NPM grammar allows only `SM_<A>_Main` + `MainGlass` (+UCX): parts must be joined before export, so per-part triangles are measurable only before the join and the joined mesh then fails V004 self-intersections where parts touch. No rule says whether parts are joined, welded or unioned. | follow-up |
| R2 | L01 opening source | Openings come from Revit-exported block inserts; `plan_from_dxf` reads plans only. There is no shared facade reader (view placement by grid lines, insert bboxes per facade suffix `О_АР_Ф_<Сторона>`); this run wrote one into the job folder. | follow-up |
| R3 | `validate_package` on a single FBX | V001/V011/V013 can only be `not_run` without a ZIP and GeoJSON, so a geometry-only run can never reach `passed=true`; the acceptance "passed=true for each built FBX" is not reachable while MSK-77 placement is deferred. | note in TASK_TO_MODEL |
| R4 | Parapet thickness / roof base | No section sheet: parapet ring 0.35 m and roof base 7.700 (Revit +7,700) are assumptions; not in `mapping-questions.md`. | architect question |
| R5 | Mullions | 164 of 171 mullion inserts lie outside the merged opening boxes (their centres are not inside any cut), so they were not placed; the curtain-wall panels and the mullions use different layer groupings. | follow-up |

## Not done, and why

- `passed=true`: blocked by V004 (self-intersections after the regulation join, clearance), textures (V006/V007/V009),
  ZIP + GeoJSON + MSK-77 (V001/V011/V013/V014, placement deferred by the user) and the manual stages.
- Stair not built; mullions 7 / 171; no textures, no atlas, no quad master.
- No Max: all Max-only steps (AGR Tools stages 1-4, Max export [D212]) are `waits-max`.
