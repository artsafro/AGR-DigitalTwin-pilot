# 3ds Max for AGR: preserving engine material semantics

Card `t_8da65809`; experiment branch `experiment/bim-3dsmax-agr`.
Base snapshot `8f48c44452e67eccd25b5901833de7e36aeb50d1`.
Research tested: `origin/docs/research-bim-3dsmax-agr` at
`146d0a6b94c01814855d0edf2fe93f9c4711be2f`, `docs/research/bim-3dsmax-agr.md`, proposal E1.

## Question and scope

Does an explicit Standard/Multi-Sub material table repair the engine-array → Max → FBX semantic loss,
without changing geometry? **Yes on B01/B02: adopt for internal transport, not AGR delivery.**

One method only, two arms. The baseline reproduces the existing geometry-only `create` logic in
`experiments/max-headless-agr-roundtrip/native_job.py`. The prototype adds the seven-line
`if explicit` material table in this experiment's `native.py`; no production implementation is replaced.
The unchanged `from_spec` engine builds both inputs. This extends the previous experiment's missing-material
finding rather than repeating startup optimization or OBJ tests. The current checker has **10 checks**,
including `orientation`, versus the research proposal's historical nine.

E2 (full texture profiles and cross-DCC verification) was not selected: outside this Max-only experiment's
program authorization and too large for the timebox. E3 and live MCP were not run. No authorized live
artist scene was supplied. Offline raster generation remains the existing route, not a new Max generator.

## Setup and execution

- Native host: Max 2026.3, version `[28000,68,0,28,3,0,30732,2026,".3"]`; bundled Python 3.11.12.
- External Python: uv-managed 3.14.7. System units confirmed/then pinned to metres, scale 1.0.
- Each batch process starts with zero objects and empty document name. Cleanup ends with zero objects.
- Copied B01/B02 spec, object, tolerances, manifest and SHA-matching etalon FBX before using them.
  Original binary location is `C:/Users/artsafro/AGR-DigitalTwin/data/benchmark`; no writes there.
  Pre/post SHA256 checks cover all 10 source/copy pairs. No reference scene was saved.
- Card run root (abbreviated `RUN` below):
  `C:/Users/artsafro/.hermes/profiles/dt-experimenter-codex/cache/scratch/agr-exp-t_8da65809/agr-3dsmax-t_8da65809`.
- Three repetitions per fixture/arm: **12 distinct FBXs**. Baseline exports ran before prototype exports.
  One separate fresh Max readback process imports each output into an empty scene, dumps complete arrays,
  then deletes owned nodes. It also reads the two copied etalons: 14 imports total.
- Explicit export/getters: binary FBX201400, Z-up, ConvertUnit=m, Triangulate=true; no animation,
  textures, cameras or lights. All outputs independently checked for binary 7400 headers.
- Diagnostic Standard materials are named `MAT_001`, `MAT_006`, `MAT_011`, `MAT_021`.
  These are synthetic semantic labels, **not** approved facade finishes or PBR assets.

Commands from the worktree (replace `RUN` with the absolute path above):

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --ping
uv run python experiments/bim-3dsmax-agr/prepare.py --run RUN --fixtures C:/Users/artsafro/AGR-DigitalTwin/data/benchmark
# Run sequentially, never concurrently:
python experiments/bim-3dsmax-agr/run_native.py --run RUN --mode baseline --wrapper C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py
python experiments/bim-3dsmax-agr/run_native.py --run RUN --mode prototype --wrapper C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py
python experiments/bim-3dsmax-agr/run_native.py --run RUN --mode readback --wrapper C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py
uv run python experiments/bim-3dsmax-agr/analyze.py --run RUN --out NEW_EVIDENCE.json
uv run pytest -q experiments/bim-3dsmax-agr/test_experiment.py
```

Every reproduction needs fresh destinations. `run_native.py` invokes only `dcc_batch.py max --card t_8da65809`;
no direct native executables, Blender, AutoCAD or Revit were run. Wrapper-maintained listener paths are reused
by the external wrapper; archived per-call JSON logs, unique stage markers, new output files and hashes are
used together, never a stale log/exit code alone.

## Baseline versus prototype

Times are medians of **three in-process operations**, not process-startup medians. Export excludes creation
and pre-export diagnostic dump; create+export sums the two timed operations. Independent readback includes
import plus complete native dump, excluding startup. Raw samples/getters/hashes/check values are in
[`evidence.json`](../../experiments/bim-3dsmax-agr/evidence.json).

| Fixture / arm | Engine vertices / triangles | Checks on fresh readback | Correct finish triangles | Correct surface area | Create median, s | Export median, s | Create+export median, s | Import+dump median, s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B01 baseline: face IDs only | 156 / 282 | 8/10 | 220/282 | 68.5257% | 0.00541 | 0.04302 | 0.05083 | 0.07918 |
| B01 explicit material table | 156 / 282 | 10/10 | 282/282 | 100% | 0.01971 | 0.05243 | 0.07369 | 0.12370 |
| B02 baseline: face IDs only | 263 / 472 | 8/10 | 362/472 | 66.0879% | 0.00672 | 0.02667 | 0.03364 | 0.09783 |
| B02 explicit material table | 263 / 472 | 10/10 | 472/472 | 100% | 0.01790 | 0.03237 | 0.05143 | 0.15185 |

All repetitions agree. Engine baselines themselves pass 10/10; median engine build is 0.01619 s / 0.02862 s.
Baseline FBX returns ID1 only, failing `mesh` and `opening_planes`. The explicit table retains raw native
IDs `[1,6,11,21]` without remapping. Native reimport expands the four-entry sparse table to 21 entries with
unused placeholder slots: internal finish semantics survive, but this is **not** a valid VPM slot strategy.

Both arms have **zero vertex/triangle count deltas**, complete oriented triangle bijections, identical
winding and identical geometric error. Maximum bijectively matched corner deviation is **0.00037812 mm**
(B01) / **0.00044090 mm** (B02); maximum bbox delta is **0.00019074 mm**. All level-helper names survive;
maximum helper displacement is **0.00009537 mm**. Helpers are benchmark metadata, forbidden in final main delivery FBX.
The full triangle correspondence compares all corners with cyclic rotations, not sampled surface distances
or a certified continuous Hausdorff claim. Matching tolerance is a declared experiment control, 0.01 mm,
not a regulation. Finish-area correspondence weights each uniquely matched reference triangle by its area.

Cost: the method adds **22.86 ms / 17.79 ms** to median create+export for B01/B02, buying semantic correctness,
not speed. Whole wrapper calls were **50.8 s baseline**, **50.0 s prototype**, **54.2 s readback**; single
observations, deliberately **not** presented as a statistically supported startup improvement. Total harness
is 441 Python lines including 92 lines of controls; production changes: zero.

## Failures, controls and validation

- First prototype failed in diagnostic dumping before export: `MultiMaterial.numsubs` reflected the highest
  sparse ID, exceeding its actual material list length. Fixed inspection to `len(materialIDList)`; preserved
  failed attempt and log. Cleanup still reached zero nodes. Failed wrapper duration: 52.8 s.
- Initial rounded-coordinate correspondence falsely missed seven B02 triangles near float rounding boundaries.
  Replaced it with complete one-to-one tolerant corner matching; missing/ambiguous matches fail closed.
- Eight experiment tests pass: reordering/float noise; reversed, deleted, duplicated and displaced triangles;
  wrong finish despite valid geometry; ambiguous duplicates; assertions over all 12 native results.
- Baseline ordinary suite: `1 failed, 2013 passed, 9 skipped, 12 deselected` in 252.83 s.
  Existing failure: `tests/qa/test_from_spec_decor.py::test_a_corner_pilaster_passes_every_check`, `orientation=1`.
  It occurs with the unchanged engine, not a Max regression. Final repeat: **the same 1 failed, 2013 passed,
  9 skipped, 12 deselected**, 242.96 s; details in `test-results.json`.
- `uv run dt profiles check`: 3 profiles/source hash/traceability OK. `uv run dt schemas --check`: 11 schemas OK.
- All successful native stages retain the installed `polyunwrapper_autoload.mse` startup exception/native
  `-130` (Windows unsigned 4294967166). Completion markers, empty-scene cleanup, output hashes and full
  readback support the component result; this warning is not silently converted into a clean native exit.
- No topology/UV/PBR/package compliance or appearance approval is inferred from import success. Project
  geometry checks include mesh and orientation, but do not establish every delivery topology requirement.
  V001–V017, UV/textures, CRS/world-coordinate precision, visual/manual approval remain unrun.
  `delivery_passed=false`. CI: not run (billing lock).

## Verdict and proposed follow-up

**ADOPT — explicit Standard/Multi-Sub table for engine-array internal FBX transport.** On both actual
benchmark fixtures it restores all intended face finishes and all current geometry checks for a small
measured incremental cost. Do not deploy the throwaway harness or sparse table as a finished delivery adapter.

Proposed follow-up task (not created): **“Max intake: preserve finish IDs through an explicit material-table contract.”**
Scope: implement the verified mapping behind `adapters/max`, preserve source/face provenance in a sidecar,
fail on missing/duplicate finish definitions, use `materialIDList` length for sparse inspection, and test
B01/B02 plus one additional available fixture with fresh FBX readback and tampered-material controls.
Separate internal IDs from regulated delivery slots; profile export must remove helpers and prove texture/UV,
slot-count and placement rules in a separate task. No production-state/capability registry updates here.
