# Lab experiment L04: `export.ground_fbx` (AGR Tools 0.8)

Date 2026-11-04. Synthetic scenes only. No GeoAGR code here (rule #853); `GeoAGR.ms:<line>` refers to GeoAGR 13.64.
Evidence: GeoAGR-private branch `lab-exp/L04`, `work/lab-experiments/export.ground_fbx/`.

## Sources checked
- GeoAGR "Export LowPoly" (`File.btn_export_lowpoly`, GeoAGR.ms:66532-66654, Ground branch 66609-66623): Max 2024 batch
  job `20261104-230509-4d1b73d0`, five synthetic cases, readback in Max; Blender readback with this repo's validator
  (`tools/qa/validate_package.py --scene`), runner host job `20261104-231040-ba8bdeb4`.
- Telegram `A101AGRLP.ms`: **not available** (not in any repository). The audit records its double underscore
  `prefix_address__Ground.fbx` (`docs/research/team-scripts-audit.md:458`); the validator rejects that name.

## Findings
1. Flora is not put into `_Ground`: the split is a lowercase substring test for "ground" (GeoAGR.ms:66611), so
   `SM_<Address>_Flora` lands in the OKS `_01.fbx` (measured). Plan text and the Ground triangle budget (D097: Flora part of
   Ground) expect it in `_Ground`.
2. The Ground file name comes from the first selected ground object (GeoAGR.ms:66617-66622): GroundGlass first →
   `0123_TestAddrGlass_Ground.fbx`; `SM_X_Ground_001` → `0123_X_001_Ground.fbx` (measured).
3. Export option Triangulate is off (GeoAGR.ms:66583); Blender readback fails V003 "triangulated" on every mesh, while
   NPM requires triangulation on export (`NPM_STANDARD.yaml` `triangulated_on_export`).
4. Correct: binary FBX 7400, 1 unit = 1 m, scale 1, positions kept, guards stop export with empty OMK code, Physical
   material or pivot within 100 units of origin (measured).
5. Side effects: the user's selection is replaced by the OKS subset (measured); silent overwrite, hidden objects unhidden,
   outer helper `dist` overwritten (static, GeoAGR.ms:66539, 66574, 66622).

Verdict: GeoAGR source **differs** from the row; recommendation **take_fix** (keep FBX settings, fix classification,
naming and triangulation).

## Requirements
NPM-2.1-5.a, VPM-2.1-4 (plan row); `standards/NPM_STANDARD.yaml` `naming.ground_fbx_pattern`
`{territory_code_4}_{Address}_Ground.fbx`, `ground_mesh_pattern`, `triangulated_on_export`; `asset_format` FBX 7.4 binary;
`docs/domain/geometry.md:39-44` suffixes Ground/GroundGlass/GroundEl/GroundElGlass/Flora.

## Minimal acceptance test
Synthetic scene, address `X`, code `0123`: `SM_X_GroundGlass` (created first), `SM_X_Ground`, `SM_X_GroundEl`,
`SM_X_GroundElGlass`, `SM_X_Flora`, `SM_X_001_Main`. Expected: exactly `0123_X_Ground.fbx` with the five Ground-family
meshes and `0123_X_01.fbx` with `SM_X_001_Main`; independent of selection order; all meshes triangulated; second run
does not overwrite; selection restored; `qa.package --scene` V002, V003 "triangulated" and V012 pass on both files.
