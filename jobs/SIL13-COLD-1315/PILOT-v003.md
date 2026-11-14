# #1315 — constructed partial pilot v003/r3 (not accepted)

Status: **pilot picture / missing-input gate; `passed=false`**. This is now real
Ground and copied-library Flora geometry, not the earlier source-only DXF. It is
not a completed cold reproduction, delivery, approved appearance or readiness gain.
Cells: `ground-npm`, `ground-vpm`. Whole-site scope is unchanged.

## Authority and sources

[D282] records the delegated zero choice and accepted exact pilot plan:
- https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6854271480
- https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6859055997

`parts-pilot-confirmed.json` validates through public `dt_ai.core.models.PartsList`;
the approved draft is retained unchanged. Approval is of the plan, not this result.
Zero **142.10 m**: authorized VP_5 floor-mark MTEXT **33F8EC4=142.10** beside
**33F8EC5=0.000**. 142.70 belongs to another definition. Heights use native design
planning-symbol INSERT Z and project-contour Z, not displaced annotation XY or
black existing marks. Red ACI1 design labels provide the interpretation cross-check.
No earlier Silikatny model, recipe or result was used.

Flora source: `G:/Мой диск/AGR-assets/flora/v003/flora-library-v003.max`, SHA-256
`9942ae2be37c900c3066d791193eb0470cc08933881d9f72db833d42578dfa74`.
A hash-equal disposable copy was opened, never saved. Max **2026.3**, system
centimetres, scale 1: unique Acer_platanoides_NPM/VPM handles **6481 / 6522**,
**10 / 1070 triangles**, native heights **4.538350 / 5.675329 m**. Species is the
catalogue/library label, not independent botanical or cultivar certification.
Native material points to absent `C:/x/flora-library/v001/maps/acer-platanoides/`
`diffuse-v001.png` and `opacity-v001.png`. Neither exists there; the mounted
`flora/v003/maps` has 12 other folders, no Acer folder. Named Drive asset search
and root maps.zip (77 members) found no matching maps. No replacement image,
plant, cultivar or library edit was made. Authoritative maps remain missing input.

## What was built

- Accepted XY window [820,11024]–[850,11046], intersect boundary 33FBCEF:
  **474.385736 m2**. No fitting to a tabulated area.
- Actual hatch regions: seeded lawn **375.690897 m2** (33FBCB2), rubber253
  **48.241895 m2** (33FBCCD, inner ring retained), rubber18 **33.443997 m2**
  (33FC17A). Hatch rings are interpreted by nesting/symmetric difference, not
  individually filled as overlapping polygons. Colours are diagnostic IDs only.
- **17.008947 m2 unresolved**: XY bounds (838.105934,11042.202463)–
  (847.063817,11046). Shown pink on the source overlay; left absent, not silently
  made lawn/rubber. No overlapping hedge60 area supplies its material authority.
- Planting hatch 33FC417 has an invalid source ring: explicitly not repaired or
  scattered. Hedges and the already unresolved flowerbed remain outside this
  two-part pilot; no invented counts/points/materials.
- Flat-first method-C base over the known covering extent, rubber overlays at
  **+6 mm**, then relief projection. Three-metre grid and TIN-edge cuts; no
  source relief smoothing. 1,670 source TIN controls, source Z range
  **140.7–142.467164 m**; control residual **8.74943e-8 m**, zero pilot-corner
  projection misses. This does not certify all project breaklines or curbs.
- Six original position-3 handles/XY, deterministic seed **1315**, same variation
  in both profiles. Visible heights **5.47741, 5.77676, 5.52491, 5.98911,
  6.14993, 6.09665 m** (all >5); sinking **0.10 m**. Actual library mesh copied,
  uniformly scaled and rotated, no newly modelled tree. All source Flora UVs copied.
- Final readback: **938 Ground triangles** per profile; Flora **60 NPM / 6420 VPM**.
  One UV channel on each mesh, unit object scale and near-zero numeric rotation.
  Readback size max error **3.705e-7 m**, sinking error **5.337e-9 m**, six plants
  checked in each profile. Coordinates are recorded pilot-local with recoverable
  offset (835,11035), zero 142.10; this is NOT delivered Moscow georeferencing.

## Revisions and real failures (no erased evidence)

1. Strict source extraction refused invalid ring 33FC417. It remains a named gap,
   not `buffer(0)`-repaired production input. A diagnostic summary initially
   accessed its absent area key; fixed to display the explicit invalid status.
2. Source-control TIN test initially exceeded its 1e-6 m diagnostic tolerance:
   **2.19832e-6 m**. Local-origin Delaunay/barycentric computation reduced the
   maximum to **8.74943e-8 m**, without relaxing the assertion or changing source Z.
3. Initial build **954 Ground triangles**; public xView **262 overlapping faces**,
   538 overlapping vertices in both profiles (Flora 0/0). Repair attempt 1, r2:
   weld exact derived seams at 1e-6 m and dissolve numerical degeneracy;
   xView faces became 0 but **12 vertices / 6 pairs** remained. Fresh FBX readback
   refused the **948 -> 946** face discrepancy. A separate diagnostic identified
   two repeated-index zero-area triangles; these were not counted as a pass.
4. Repair attempt 2, r3: explicit repeated-index face removal and normalization of
   tiny crop/TIN seams, weld 0.0013 m. Maximum derived vertex displacement
   **0.001183943 m**, disclosed (not source-file editing or an acceptance waiver).
   Final **938** matches fresh readback; public xView on each actual FBX:
   **0 overlapping faces, 0 overlapping vertices, 0 bow-ties**, exit 0.
5. First Blender readback crashed in custom-normal import (0xC0000005), crash log
   retained. Retry with `use_custom_normals=False` read the geometry successfully;
   this does not certify imported custom normals. Native shading review remains open.
6. Doc tests initially **1 failed / 34 passed** (then-called D279 inserted before D275; now [D282]).
   Corrected row order: **35 passed / 0 failed**. No shared production-code fix.

## Real public validator results, not delivery passes

`validate_package.py --scene --json` was run on byte-equal exports named
`NPM/SM_SIL13_Ground.fbx` and `VPM/SM_SIL13_Ground.fbx` so the Ground role is
actually selected. Both exit **1**, `passed=false`.

| Profile | Stage results | Important measured failures / remaining work |
|---|---|---|
| NPM | 4 fail, 2 review, 4 not_run | FBX header UnitScaleFactor=1 (cm), despite correct metre-sized importer result; skirt 0.999999 m vs >=1 m; library Flora topology counter 162 vs <=100; missing diffuse/opacity and Ground maps; absent complete package/manual gates |
| VPM | 6 fail, 1 pass, 8 not_run | Same header/skirt; footprint 457.398644 vs pilot 474.385736 m2 (16.987092 m2 deficit, not claimed identical to source-gap area); library vegetation topology counter 29242 vs <=100; 117 mirrored Ground UV triangles; 0 UCX; diagnostic vegetation name not the final mask; no final UDIM/textures/pivot/GeoJSON/visual/SINTEZ |

The first validator diagnostic used `pilot-NPM.fbx`, which selects the wrong role;
that report is retained but is not the evidence for the table above. No validator
was patched, suppressed or treated as passing. xView clean is not V004 clean,
architectural accuracy, appearance acceptance or a whole-Ground delivery.
Technical failures remain worker-owned for subsequent authorized construction;
the current stop is the required image gate plus missing source maps/materials.

## Route / tool calls and per-area accounting

| Area | Actual route and evidence | Limit / owner / next action |
|---|---|---|
| Ground | Read-only ezdxf hatch/VP extraction; scipy local TIN + Shapely cell/TIN cuts; Blender 5.1.2 headless flat-first/projection; fresh FBX readback, xView and public validator | 17.008947 m2 material unmapped / no default allowed: Artem identifies pink region. Worker then completes all source contours, breaklines, curbs, budgets, UV/textures/export corrections |
| UCX | No construction; public VPM validator correctly fails 0 hulls | Required for full VPM only, closed/convex, gap 2–10 mm, deviation <=100 mm, D012 budget. Worker after pilot picture approval; not a zero-hull pass |
| MAF | v002 accounts for 32 schedule rows; no new placement or same-site historical library usage | Exact article/dimension/point mapping or explicit library gap required; worker continues manifest identity audit after pilot gate, no PDF modelling/substitution |
| Flora | Locked Max read-only copy census/export, two named Acer meshes; Blender copies at six source XY in each profile; source UV and size/seating controls, public topology findings | Missing original maps: asset owner supplies authoritative pair/path. Appearance/species independent verification and source/library topology not approved; worker retains 52 point plants/4535 hedge count/flowerbed gap for remainder |

Command ledger (all from this worktree; full logs/scripts retained under evidence):
`max_exec.py --ping` unreachable; `dcc_batch.py max --ping` successful;
`dcc_batch.py max --file extract_flora.py --card t_d9ae7dc0` successful (native
missing mental-ray custom-attribute plugin warning retained); `uv run --extra cad`
source inspections; scoped `--with scipy --with shapely` buffers; Blender
`--background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1`
build/repair/diagnostics/readback/render; public `dt qa xview` (initial, r2, r3)
and `tools/qa/validate_package.py --scene`; affected doc tests. No live-user scene
mutated. No total tool-call/time metric was instrumented; no invented aggregate.
No new tracked Python module or shared production code; job-local drivers remain
hashed external evidence. Full suite deferred until a completed PR is ready.

## Historical comparison (read only AFTER this independent pilot build)

- **#906**, merged Vatutino Ground: user-accepted NPM/VPM, 12 fixed IDs, 46,479
  triangle-equivalent per profile; native Max plus Blender xView 0/0; source-bound
  texel exception D193. Here: a different site's partial pilot, 938 surface/skirt
  triangles, Blender xView 0/0 only; no user acceptance or inherited exception.
- **#969**, merged ELV: accepted VPM **OKS**, not a Ground/MAF/Flora reproduction;
  historical example 38,909 Main + 800 MainGlass, 960 UCX / 11,520 triangles.
  Its source-coverage/export/user/checker distinctions are relevant, not its
  geometry or a transferable acceptance. This pilot has no constructed UCX.
- **#1178**, merged Flora route A: placed stars, profile-specific atlas and
  independent texture/readback/visual decisions, with explicitly retained failed
  checks. This pilot copies six maples but has no original maps, accepted atlas
  or appearance. It is not equivalent to the accepted historical Flora case.

These comparisons use published PR summaries, not their recipes/models as build
hints. They do not increase readiness or waive any check on this new site.

## Review image and next gate

Evidence root: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v003/`, checksum manifest
and compact `evidence-v003.json`. Full review image:
`r3/pilot-review-sheet.png`, SHA-256
`58502b6e8d1d330c2ca3b0d1eddf8ad3a91be8d2ce8f497b44dc4189157460d5`.
Native depth-buffer images render the exact r3 FBX, not a stale pre-repair scene.
The overlay is source hatch/point geometry, explicitly not a native CAD plot.
Board attachment 12 is a small readable JPEG preview, not the authoritative sheet
or a hash-equal copy of the intermediate thumbnail (inline transfer bytes differ;
actual attachment separately hashed in evidence).

Exact r3 FBX hashes:
- NPM `d1f9c181bc549391882be8ffd35696889c5d963cd3d7c34df8a3f9eac945c579`
- VPM `f29cd3a1ebe54463b72f0ad4f03a2c79af22ef5b4c35bcc511554b352cfce6d9`

Ask once on #1315: review this partial layout/relief/size picture, identify the
pink source gap's covering, and give the missing authoritative Acer map pair/path.
Do not ask again for boundary/VP authority, zero or the already accepted 5.6 m plan.
Do not build the remainder or claim complete acceptance before the picture answer.
No PR/reviewer handoff yet: issue construction acceptance remains incomplete.
