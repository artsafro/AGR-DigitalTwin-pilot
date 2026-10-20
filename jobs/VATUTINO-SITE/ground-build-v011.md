# Vatutino Ground v011 — #295 / PR #308

Status: **not passed / blocked**, not a delivery acceptance. User approval of the v011 geometry and the site assembly/SINTEZ gates remain separate. This run implements the user's 2026-10-19 curb/stair extraction and duplicate/isolated cleanup decisions. It does not waive V004 clearance or failed UCX generation.

## Source and decisions

- #195 adapter was merged at `322574d`; this branch was refreshed by a merge of `origin/main` at `1dd63ef` (no rebase). #166 was merged by the time this run started, so the old "#166 open" exception is no longer applicable.
- Gate 1 and its corrections remain in `ground-parts.md` / PR #308: paving master, boundary 568BF, footprint holes, placeholders, Vatutino token, method C, 4×4 m grid, VP points+contours, +6/+12 mm vertical levels; tolerance 10 mm and local TIN cuts <1 m allowed only where necessary.
- Latest approval quoted from the card: Artem, 2026-10-19, **"Принимаю"**: extend the ignored curb/stair layers; drive curbs 150 mm high ×150 mm wide, garden 50 mm ×80 mm; stairs from VP; missing geometry skipped and listed. Plate borders and skirt bottom accepted, **not** duplicate or isolated elements.
- Full per-entity Step-8 decisions (481 adapter records, including INSERT group records): [ground-elements-v011.md](ground-elements-v011.md). Modeled: 100 garden curb paths; three staircase instances `1988C0` (3 treads), `1988D2` (2), `198C45` (2). The other stair instances have explicit source-geometry/partitioning/MAF reasons; no dimensions invented. Source endpoint gaps <=2 mm closed, tread endpoints extended <=20 mm. Stairs replace 10.260678 m² of surface and crossing curbs instead of intersecting the Ground.
- Original DWG SHA-256, re-read after all work: main `64e22677454affce7071a823123b13742c8d68cd39c1ec0ee761c4cfa3b546e4`; paving `d24df23219fe1357830b3628ca31fa9acacedb158a9d3c8b9f9bc8a16cc3ece2`. Both equal `orig_before.sha256`. Copies only, no live DCC.
- Input: `C:/x/t_d94665f2/paving_ground_inputs_v4.json`, SHA-256 `3b6b433d718c0292f472293849f3363fd2ae90d4892e598efca52be44cd9d502`. Typed adapter, no second DXF parser. The new paths retain nested WCS transforms and source instance refs. Existing adapter findings and lawn repair evidence remain in the Gate-1/v006 reports; a new parser does not replace them.

## Route, commands and Needs

All DCC routes below use Blender **5.1.2** (`ec6e62d40fa9`), factory startup, metres, copies only. `Needs: headless`; geometry/visual acceptance still `Needs: human`.

1. Steps 1–3,5: `PYTHONPATH=".;src" uv run python -m adapters.cad.spozu C:/x/t_d94665f2/paving_work/paving.dxf --config adapters/cad/configs/vatutino_dom2.yaml --json C:/x/t_d94665f2/paving_ground_inputs_v4.json` → exit 0. No new DWG export was needed.
2. Steps 4,6–9: `uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/t_d94665f2/paving_ground_inputs_v4.json --snap 0.003 --out C:/x/t_d94665f2/ground_v011` → exit 0, all eight explicit job gates true. 3 mm noding replaces the 1 mm v010 attempt that introduced two internal open edges/one non-manifold edge after stair cutting; no failed v010 mesh was published. Exact point-insertion refinement then restores <=10 mm relief error. This is not a finer uniform grid.
3. Step 9: `"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/blender/ground_json_to_fbx.py -- build <ground_master_{npm,vpm}.json> <profile>/SM_Vatutino_Ground.fbx Vatutino` → 0/0. Independent clean-process `readback ... <px> <lo> <hi>` → 0/0; `render` and `tools/blender/fbx_readback.py` → 0/0 for each profile.
4. Step 10: `uv run python tools/qa/validate_package.py <profile>/SM_Vatutino_Ground.fbx --profile <npm|vpm> --scene --json` → 1/1, **not passed**. `py -3` lacks project dependencies, hence the project's `uv run` interpreter.
5. UCX: shared `tools/blender/ucx_build.py -- <vpm FBX> <new vpm_ucx FBX> Ground` → exit 2: **33,730 pieces exceed 999 / 15,000-triangle budget**. v009 gave 33,862 pieces, exit 2. Stopped after the two same-cause failures, no tool/cap changes and no hand-made UCX. Follow-up [#326](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/326), card `t_d61e1f10`, is a dependency. Failure reports/logs remain at local v009/v011 paths.

## Geometry measurements

| Check | v011 |
|---|---|
| Surface / total triangles, one shared master | 32,821 / 46,343; NPM surface <=50,000; total <150,000 advisory target |
| GND-06 area and limit | S_ter 25,854.04 − S_pz 9,110.08 = 16,743.96 m²; limit 4,500,000 triangles |
| Common 4 m cells / relief-cut cells | 1331 / 363; TIN cuts local, not uniform refinement |
| TIN points / triangles / contradictory Z / misses | 4948 / 9857 / 0 / 0 |
| Relief maximum exact face error | 9.963067 mm; 0 faces >10 mm |
| Layer-gap error at sampled face centres | 0.000534312 mm; minimum gap 5.999656489 mm; same-level overlap 0 m² |
| Base coverage | 99.996211901% raw; 0.633889 m² lies in the <=2.2 mm precision strip, 0 m² missing beyond it; stair footprints excluded and supplied by stair solids. Not an exact 100% raw-area claim. |
| Containment | 0 outside, tolerance 0.024 m (chord + snap budget) |
| Base internal cracks / non-manifold | 0 / 0 |
| Cleanup | 3 near-vertices welded; 6 collapsed faces dissolved; 106 single-triangle plates subdivided without bridges/deletion; winding correction 0 |
| Projection invariant | XY/UV/material unchanged in **project_z** before explicit cleanup/detail construction: True; cleanup is a separately measured representation change, not silently included in this identity claim. |
| Skirt | >=1 m down, material Skirt; source-to-local pivot offset [-7594.0335, -15287.744999999999, 0.0], no rotation/scale; placement sidecar records the reversible MSK-77 drawing-coordinate translation |

## Exported FBX readback

| Profile | Triangles | Raw material mismatch | Density px/m (all non-Skirt faces) | Below/above | Mirrored / VPM straddling | Open edges / down-facing surface faces |
|---|---:|---:|---|---|---|---|
| NPM | 46343 | 0 | 11.555525–30.213726 | 0/0 | 0 / n/a (NPM continuous tiling) | 8307 / 0 |
| VPM | 46343 | 0 | 590.908618–1442.061823 | 0/0 | 0 / 0 | 8307 / 0 |

Both exports: unit scale length 1, object scale 1 and rotation 0, one UV layer, same one-master geometry and material IDs. VPM tile [1001], no straddling. Placeholder materials only; side projections on steep faces are disclosed in ground_report.json and are **not** proof of seam-free real textures.

Regulatory topology on each exported FBX: **0 duplicate vertices, 0 duplicate edges, 0 duplicate polygons, 0 isolated vertices/edges/polygons, 0 zero-length edges; 10 self-intersections** (Mulch/Stairs). V004 topology is within its <=100 count threshold; this is not a zero-self-intersection claim. Accepted open-edge class: **"method-C plate borders, user-accepted 2026-10-19"**, 8,307 boundaries. Only that class is accepted, never the other checks.

Face Orientation back pixels top/45/135/225/315 = **0/2/4/3/1**, both profiles. Fixed cameras, local PNGs `C:/x/vatutino-ground/v011/{npm,vpm}/face_orientation_*.png`. Nonzero back pixels remain visible evidence for human review; no claim of visual acceptance.

Validator: NPM machine pass3/fail1/review1/not_run3, manual not_run V015/V017; VPM pass3/fail2/review1/not_run6, manual not_run V015/V016/V017. NPM all not_run stage IDs: V001,V005,V014,V015,V017. VPM: V001,V005,V007,V009,V011,V013,V015,V016,V017. Do not count any as pass. V012 Ground name grammar remains review (#315). V004 clearance **97 pairs <5 mm**, minimum 0.8415 mm; many distant pairs are reported >20 mm (C30). V010 no UCX fails. Raw outputs are `validate_{npm,vpm}.json`; `validate_*_annotated.json` adds the accepted border class without changing the raw verdict.

## Regression evidence / probes

- New files: 14 passed (5 cleanup +6 details +3 adapter), actual `uv run pytest -q tests/test_ground_cleanup.py tests/test_ground_details.py tests/test_spozu_ground_elements.py ...`, 0.49s. All Ground tests including earlier round-1 regressions: 49 passed before the last added footprint case; full final suite below includes that case.
- Detached pre-fix `0259b0d`, `tmp/red-prev`: printed module paths prove old source imports; same cleanup+adapter tests **8 failed** (missing cleanup features / missing typed element records / missing layer-role conflict check); details collection fails because old ground_details module does not exist. Direct incremental RED cases also captured: vertical UV 1 failed, collinear/T-junction 1 failed, winding 1 failed, 4 m diagonal UV 1 failed, <=2 mm stair closure 1 failed, stair-footprint replacement 1 failed. GREEN follows in recorded runs; no fabricated test output.
- Full final non-DCC suite: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -n 8 -p no:cacheprovider --basetemp=C:/x/t_d94665f2/pytest-final`: **6036 passed, 13 skipped**, 139 upstream dependency warnings, 138.80s. Canonical serial card command was exercised first but timed out, and a diagnostic serial run hit Windows native subprocess exit 3221225794 after 3714 passes. Parallel opt-in rerun passed; no tests disabled/modified for the environment.
- Probe: nested mm DXF transform/provenance -> rotated instance + explicit path width -> 1/1; unsupported primitive -> retained with reason -> 1/1; layer double mapping -> rejects ->1/1; cleanup combined winding/UV/slots/coverage/collinear crack/NaN ->5/5; approved curb + closed volume / unknown section / staircase gaps0,1.9mm / footprint replacement / diagonal UV ->6/6. All new tests synthetic generated geometry, no DCC pytest test added. Real DCC evidence is the actual independent headless commands above.
- Author receipts: Pattern n/a | new-case: typed Step-8 Ground solids (ground_details module docstring); Regression evals `tmp/evals/report.json`: 0 passed /0 failed /10 not measured (no Claude transcript), exit2; CI: not run (billing lock).

## Open gates / next run

1. **Dependency #326**: shared UCX tool cannot export within its own caps. Await repair on main, merge that parent branch only when permitted by the card dependency, generate UCX and validate/read back the new FBX.
2. **Model/spec decision needed (C30)**: 97 co-directional pairs below the mandatory 5 mm clearance are NOT covered by the accepted plate-border exception. How should the 6 mm vertical method-C stack on steep relief be reconciled with the clearance rule while retaining the user's 10 mm relief tolerance? No validator weakening or unilateral waiver was made.
3. Geometry/visual acceptance incl. the explicit missing-element dispositions, 10 Mulch/Stairs intersections and back pixels; placeholders and actual textures, manual/SINTEZ/site packaging remain not passed or out of this card as specified. C36/C37 remain review.

## Artifact SHA-256

- `C:\x\t_d94665f2\ground_v011\npm\SM_Vatutino_Ground.fbx`: `0d9963752276cba45734c4ee2dcff78a9de005ab0a83a6029b719874d1aa95fd`
- `C:\x\t_d94665f2\ground_v011\vpm\SM_Vatutino_Ground.fbx`: `8009922ff2272a7683ee461f71050df22efba5e8f01f0483ef1cbe500c505757`
