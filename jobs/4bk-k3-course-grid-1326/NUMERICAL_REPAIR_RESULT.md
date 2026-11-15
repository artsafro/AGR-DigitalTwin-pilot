# Numerical repair of the actual two-tile pilot (#1326)

Historical v166 checkpoint. The current scoped pilot/readback and reusable
execution evidence are in [FINAL_PILOT_RESULT.md](FINAL_PILOT_RESULT.md);
its selected cyclic-anchor repair supersedes the open continuation below.

**Not passed. No replication, delivery acceptance, PR or review request at v166.**

## Answered scope and current visual stage

Artem confirmed v096's restored Normal/joint/course visual direction on
2026-11-15 10:12 [D310]. Keep it; do not ask that question again. Two tiles
[D304], original relief [D295], outer-bevel-support cuts [D303], and the
specific source-stair baseline [D296] remain settled. Opening remains only
on «открой», in a separate versioned copy; daytime Max was not touched.
Scenario `oks-vpm`, level `full`; Blender 5.1.2 background avoids Max ownership.

Artem confirmed the thin Diffuse cores on ends/caps in v160 on 2026-11-15 13:27
[D317]. Keep them and continue technical checks/repairs without replication.
This does not waive area-only pairs, all-map/source-surface/readback checks or
final acceptance. The earlier Normal-direction approval [D310] remains settled.
The historical comparison below records the accepted colour stage, not an open
question to ask again.

Initial pilot policy is now [D309]. Mechanical own-row reconciliation after
external PRs #1419/#1418 changed D302→D309 and D306→D310. D308 was already
reserved by #1420. `next` returned D308 (main + 5 PR heads); active exact scan
and open-PR search `D309 OR D310` returned no hits, pushed registries max D307.
Immutable external v102–165 files keep their original decision spellings.

## Actual artifacts

Root: `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/`.

- Linked repaired scene: `normal-v159/stylobate_two_tiles_repaired_v159.blend`.
- Explicit selected-object export scene: `normal-v160/stylobate_two_tiles_repaired_v160.blend`.
- Freshly reimported FBX: `normal-v160/stylobate_pilot_v160_QA_OPEN.fbx`.
- Six repaired maps: `normal-v157/T_1326_Stylo_{Diffuse,ERM,Normal}.{1001,1002}.png`.
- New four actual lit source/candidate views:
  `normal-v163/source-vs-repaired-four-views.png`; candidate native copy
  `normal-v163/stylobate_two_tiles_repaired_v163.blend`.
- **New colour-edge comparison:** `normal-v165/actual-thin-colour-three-way.png`,
  SHA256 `c59630b61c6fb4161c371ae54718dcf36c5e7b900ecce54c10ea93242e98fa95`.
  Source face1290 is isolated only in the temporary render process to remove
  occlusion; actual saved geometry/UV/materials are used unchanged. Same camera
  and lighting. Columns are frozen source, previously approved-direction v096,
  and repaired v160. The different brick phase was already present in v096.
- Attachment30 is the **actual repaired cap**, not a chart: 400×260 decoded WebP,
  SHA256 `ca1e4dd5bfc57685f5024c7e787e8c7392492864d153efaaf88c5e2580470d1b`.
  Stored attachment bytes were read back and matched to the source file.
- `normal-v164/` is an **occluded, rejected camera diagnostic**, not acceptance
  evidence; retained. `normal-v165/` corrects it with explicit actual-face isolation.

## Fresh results, not historical counts

| Metric | Current measured result | Scope / verdict |
|---|---|---|
| Membership | 771 brick sources; all 2,015 source identities retained | covered, not a complete surface certificate |
| Export association | **6,393/6,393** polygons, both meshes, one UV channel; exact UV delta0; XYZ max **9.004957 µm** | narrow import/native association green |
| Actual imported density | **5,149/5,149**, min **512.002938**, max **516.402080 px/m** | legal 512–1706 directional band green |
| Imported anisotropy / mirrors / degenerates | max **1.008575737**; **0 mirrors**, **0 degenerates** | measured subset green |
| Density p95−p5 / median | **0.0000403117841** ratio | <=2%; extrema above still govern |
| 1001 unique sampled/padded union | **58.497058% / 87.188895%**, 236 classes including shared brick | measured on saved native UVs |
| 1002 unique sampled/padded union | **11.569224% / 50.779407%**, 516 classes | measured on saved native UVs |
| True geometric gap / border | 1001 **33.872931 / 32.813274 px**; 1002 **34.880765 / 49.984375 px** | no unresolved class; raster/mip evidence separate |
| Source PNG correspondence | **771/771**, **0 missing**, **0 false**, **0 piece refusals** at 5mm contour test | v158 oracle, actual saved native UVs + new v157 PNGs |
| Brick phase | all-brick max **0.010218 px**, main max **0.005497 px** | fresh imported FBX triangles, <=0.1px |
| Approved main-wall edges | **365 / 7,665 samples**, max **0.010631 px**, no missing edge | sampled edge subset green; all-map intervals separate |
| Wall xView contact selection / vertices / bow-ties | **0 / 0 / 0** | contact/vertex subset green, NOT whole xView green |
| Wall xView area-only pairs | **3**, original source pairs **(715,62), (725,66), (729,396)** zero-based | **OPEN IN-SCOPE REPAIR**; original source wall report has none |
| Stair xView | 6 selected output faces, 0 close vertices, 0 bow-ties; 4 output pairs | all map to the same approved original source pairs (73,467) and (297,466), zero-based; raw report remains fail |
| Full centre/width/junction and Normal-frame/mip certificate | not completed on this new bitmap | **OPEN**, no borrowed v045 pass |
| Visual | earlier Normal direction confirmed [D310]; new colour-core comparison provided | new colour-edge verdict pending, not final QA acceptance |

Raw reports: `normal-v160/{fbx-readback,fbx-lineage-readback,xview}.json`,
`normal-v161/{metrics,directional-triangles}.json`,
`normal-v158/independent-all-faces-png-check.json`, `normal-v162/phase.json`.
The diagnostic producer's `status=actual_export_QA_red` remains deliberately
unchanged: zero directional failures does not turn its aggregate status into pass.

**Index-base correction:** xView selections and pair IDs are **one-based**;
Blender face and `agr_source_face` IDs are zero-based. Earlier attempted joins
mistakenly called current stair sources466/467 new. Correct joins prove only the
accepted baseline pairs. The three wall area-only pairs are NOT covered by it
and are not hidden by the zero contact-face selection.

## Repairs and retained failures

1. Added absolute-UDIM float32 encoding. Adding a page offset after local encoding
   invalidated its certificate. Native-representable diagonals now constrain the
   complete triangulation before dynamic programming selects a partition.
2. Extended cut-support tips to source boundaries and removed bounded outward
   raster notches **before** native cells. Refused proposals retain original
   partitions; no source is dropped. Post-tessellation v074 welding was not reused.
3. Shared-face endpoints now use fractions on the SAME original source edge,
   not independent first-triangle projections. Per-face boundary endpoints extend
   2µm outside before clipping, avoiding numerical slits. Native construction uses
   source-local interpolation and reports exact pinch lobes/zero-area cycles.
   The source-affine/storage envelope remains20µm; this is NOT the 5mm PNG gate.
4. Removed retraced, sub-nanometre / <=1e-12m² excursions in the **source chart
   before float32 storage**, retaining forward conforming nodes. Post-storage
   cleanup alone refused the source1281/1286 witnesses; retained, then repaired
   upstream rather than relaxing legal density or anisotropy.
5. Removed only explicitly accounted unused CUT vertices. Source corner prefix
   remains; no protected ID7 trim, source overwrite, extra tile, packing rotation,
   mirror, density fallback or broad plain-brick cut was introduced.
6. Binary source-cell intersection (four separating axes) preserves thin original
   dark cores that centre/bilinear sampling lost. v118 improved696→764 faces;
   blanket boundary admission removed misses but introduced8 false faces, rejected.
   Independent seven-source boundary admission produced771/771, then the complete
   aligned mesh was rebaked and independently rechecked in v157/v158.
7. Exact full-raster GEOS cell intersection and the first unoptimized repeated
   source-mask bake timed out; partial outputs remain. Compute the source mask
   once; use bounded boundary admission only for the measured missing set.
   Library-load list mutation and unevaluated identity world matrices initially
   refused construction; fixed by copying name lists and verifying matrix_basis.

The intended colour convention remains10mm owner-inside, centre5mm inward;
conservative digital cell coverage is not an everywhere-valid width certificate.
Source Bricks1 bytes/repeat remain unchanged, 38 courses per3.15m. Original Normal
relief is retained; no neutral-Normal substitution. Source alpha replay still has
4,976 pixels above1RGB / max28RGB error; passing dark-core correspondence is NOT
proof of exact full-colour or Normal replay.

## Code and verification

Reusable pure helpers are in `tools/materials/course_grid_native.py`, not a new
job-only math implementation. Tests-first RED commits:
`2bd607b9` absolute UDIM, `cf055d0e` boundary support, `a06bb9d0` constrained
triangulation, `e613fd07` raster cell transfer, `e6114109` outward notches,
`234ffdf2` backtracking. Every missing API was executed RED before implementation.
The raster probe compares600 generated rotated cells against independent Shapely
positive-area intersection (seed1326). Existing page-plan CLI remains available.

Affected tests:
`uv run pytest -q tests/test_course_grid*.py tests/test_decisions.py tests/max_tools/test_agr_tools_vpm_layout.py --basetemp=C:/x/t_d517d7c6-affected-v159 -p no:cacheprovider`
→ **360 passed /1 deselected /0 failed**,15.36s before final mechanical renumber;
rerun on the checkpoint head is recorded in the checkpoint JSON.

Full suite: deferred to merge batch (rule68). No eval/PR receipt claimed yet.

## Continuation — still owned by this card

1. Answered by [D317]: retain the thin-Diffuse cores without replication. Do not
   ask this stage again; the current continuation is in FINAL_PILOT_RESULT.md.
2. Repair the three wall **area-only** pairs, retaining current source coverage,
   legal triangles, UV phase, source/protected geometry and hashes; no waiver.
3. Complete independent all-map Normal-frame/support, carrier/junction/centre-width
   and mip measurements on fresh readback; certify full source/protected surface.
4. Land and actually replay reusable **bake/native finalization** around the cores;
   the existing planner + generic math alone is NOT declared to satisfy that.
   Retained versioned drivers and immutable inputs are in the v166 seal. Start new
   experiments at **v167+**; do not modify v102–166.
5. Re-export/read back after any change, refresh final pictures and measurements,
   merge current main without rewriting history, rerun affected tests/probes/evals,
   recheck IDs, push and open the one PR, then request dt-reviewer. Only after every
   required gate is closed may a pilot pass be claimed; final 4BK delivery is outside scope.
