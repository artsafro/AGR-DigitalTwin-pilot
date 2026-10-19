# butovskaya-sosh1000 — school for 1000 pupils, Bolshaya Butovskaya vl. 9 (NPM by autoresearch, #118)

Pipeline status: experiment (autoresearch lane 3 of 3, issue artsafro/AGR-DigitalTwin-pilot#118). Not a delivery:
`delivery_passed=false`; technical QA, user acceptance and publication are open.

**Round 3: conforming run on a mesh reference.** Step 0 is the TwinPack mesh export of the open Revit model (user
decision 2026-10-15, option a): every number of the loop is measured against the Revit element meshes. The first
attempt's box run stays non-conforming exploration (review round 1, P1-1; report appendix).

## Source (read only)

- The user's open Revit 2025 model `БУТОВСКАЯ_СОШ1000_АР_В3_ВИЗАМ_2025.rvt` (workshared, 8 levels -3.4 ... 18.6 m).
  Exported once, read only, with `node tools/source/measure_spec_revit_twin.mjs C:/x/butovskaya/twin-v001` (TwinPack
  `twin_floor_manifest` / `twin_export_floor`, under the Revit lock of `revit_exec.py`): 8 storey bands, per band
  `reference.obj` (tessellated element geometry clipped to the band) + `floor.json`, and `twin-data.json`. Document
  modified false before and after; never synced or saved. 81.3 s.
- Snapshot `C:/x/butovskaya-snapshot-twin/` (local, outside the repo; nothing in `data/`): 13 569 elements as
  21 094 band pieces, 1 911 983 triangles (walls, curtain panels and mullions, roofs, floors, windows, doors, wall
  sweeps). Counts, coverage against the box snapshot and hashes: `docs/experiments/autoresearch-butovskaya-npm.md`.

## Scripts

| Script | Does |
|---|---|
| `scripts/snapshot_twin.py` | step 0, mesh route: TwinPack export -> snapshot; fails closed (exit 2, `blocked.json`), also on an export without any triangle (`no_geometry`) |
| `scripts/snapshot_revit.py` | step 0 through the read API; fails closed on a bbox-only answer (the first attempt's route) |
| `scripts/evaluate.py` | metric `silhouette_err_m2` and guard, fixed after step 0; refuses any non-mesh reference |
| `scripts/build_npm.py` | the NPM, built from the snapshot only; the one file the loop edits |
| `scripts/loop_step.py` | one experiment: build, metric, guard when the metric is strictly better, keep / discard |
| `scripts/render_views.py` | five orthographic png views (model; snapshot silhouettes) |
| `scripts/report_experiments.py` | experiment table of the report |
| `scripts/probe_invariants.py` | probes of the issue's guarantees |

```
uv run python jobs/butovskaya-sosh1000/scripts/snapshot_twin.py --src C:/x/butovskaya/twin-v001 --out C:/x/butovskaya-snapshot-twin
uv run python jobs/butovskaya-sosh1000/scripts/build_npm.py --out C:/x/butovskaya-npm-twin/model_dump.json
uv run python jobs/butovskaya-sosh1000/scripts/evaluate.py --model C:/x/butovskaya-npm-twin/model_dump.json
```

Acceptance tests: `tests/test_butovskaya_sosh1000.py` (read-API snapshot, guard), `tests/test_butovskaya_twin_snapshot.py`
(mesh route, keep rule).

## Model (current best, see the report for the loop)

Exp 16 of 21 (round 3): `silhouette_err_m2` 170.512 against the meshes (setup 1029.978), guard pass:
124 976 triangles, 0 open / non-manifold / winding edges, levels exact. One mesh `SM_butovskaya_sosh1000_body`
of 44 separate closed prisms (plan regions from the projected piece meshes per layer, runs of near-equal layers
merged, each offset 5 mm inward and standing 3.1 mm above the one below); flush opening planes (ids 11 / 12);
`LEVEL_<name>` helpers at the snapshot's 8 levels. Report: `docs/experiments/autoresearch-butovskaya-npm.md`.

## Open

- Visual acceptance by the user (renders in `docs/experiments/autoresearch-butovskaya-npm/`).
- The model is a stack of separate closed prisms with 3.1 mm gaps (the only way the loop found to keep the guard's
  manifold checks with 45-degree and curved outlines in the time box); a single closed mesh needs a noded stack
  builder (exps 4-8 of the report show why the snapped one fails).
- Opening planes are flush, not recessed (pattern `opening-plane` asks a 0.4 m reveal in `npm_min`); the metric
  does not see openings.
- Horizontal faces are CDT-triangulated; no FBX export, no materials table, no UV: geometry only.
