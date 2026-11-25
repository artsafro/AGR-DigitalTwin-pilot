# Standing #88 — trainer Revit BodyPlan intake (OBSERVE)

**Кратко.** В ledger чаще всего не появляется артефакт: `artifact` 3/4 против `sources-dwg` 1/4. После #87 все три незагрязнённых прогона 63A/63B остановились на недоступном Revit→BodyPlan. Проверяем, достаточно ли открыть существующий путь на тех же исходниках, не читая ключи и не подбирая параметры под 63B.

## Frozen contract

- Ledger, hook sources, core and schema: `08015022acc2a140994eeb188444f68a4388c15c`. #1855/#1608 record the original DWG stop; #1880 owns that route. #1889 owns practice approval, #1901 owns tower identity, #1859 owns practice isolation. No new agent session: previous sessions could read accepted evidence. Form is closed; atlas fallback is inactive because ledger rows exist.
- Native fixtures: the #87 bank (SHA-256 `0390c1450b14a56f731033ad7983c20daa2801a19731335de7f165ecd57a50c9`) authorizes site FBX `C:/x/body-training/a101-63/source/STLB-04_RR_AR.fbx` (`2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7`) and the approved tower XY map `G:/Мой диск/AGR-evidence/1619-body-training/gate1/boxes63.json` (`e8a41981ecaa7603ec4c8ef28098388ee2fcbf7cc8e341eaf5d08ed4f5d987e7`). Use byte-checked copies. 63A tuning, 63B held out (same site, different approved, disjoint XY regions; not an independent site). Do not read accepted floor plans, keys, rejected models or job-specific parameters; skip quality scoring rather than weaken its calibration.
- One variant, zero new candidates: make the **unchanged** Revit cropper and floor adapter with its unchanged import dependency callable on a new diagnostic copy. Read XY directly from `boxes63.json`, use `--openings` and all other defaults. No hardcoded alternate classifier, finish assignment, contour or opening repair. Compare to the #87 practice tree's existing documented adapter path (per iteration, matching saved A/B snapshots, existence only; past sessions are provenance, not new A/B sessions). Candidate uses the common core, not an alternative pipeline.
- Primary **M88 = source-to-BodyPlan handoff**: 1 only if a fresh crop has triangles, the unmodified adapter emits a nonempty plan with nonzero measured window reveals, JSON Schema and shared `validate_plan` pass, and `build_module` can consume it without error. Otherwise 0 on a witnessed deterministic rejection; timeouts, missing runtime, input hash mismatch are **not measured**, not zeros. Baseline unavailable script = 0. Median of exactly 3 paired observations per fixture, require candidate 3/3 and baseline 0/3 on both, paired gains all +1; report range and absolute wall times. A confirmed result removes one intake stop, not proof of trainer `artifact` passage. A deterministic rejection repeated on either fixture refutes exposure-alone there. A series missing required observations is inconclusive; never KEEP solely on local scratch. Three repetitions re-import and recompute, not rescore dumps.
- Witness: clean 63A should exercise crop and the adapter; 63B must exercise those same operations without adjustments. Injected boundary: give the adapter an independently constructed empty crop with the same array schema (clearly synthetic); expected refusal, no JSON. Source parity: full SHA pre/post, head-pinned code copies, retained raw crop fingerprints (key, shape, bbox and per-array hash) and each output SHA; baseline and candidate use the same authorized source bytes. Not measured: visual/finish fidelity, package checks, blind trainer artifact, isolation adoption, different-site generalization.
- Replay: from this branch use `uv run -q python docs/research/trainer-revit-intake-r88/replay.py .r88-replay` with a new output dir in the worktree, Blender 5.1 installed at `C:/Program Files/Blender Foundation/Blender 5.1/blender.exe`, pinned native inputs above and #87 local snapshots in `C:/x/trainer/runs`. Replay limited to hosts with those assets/snapshots. Stop after one candidate and three pairs; first measured pair fixes remaining measured-time budget at at most twice its wall time per remaining pair, bounded by 8 min from start / card time (whichever is smaller); cap individual crop subprocess at 60 s. If a time stop triggers, receipt is partial and replay continues only in a new directory with an authorized budget; do not interpret a timeout as rejection. No delivery/model edits, no live DCC, no changed tolerances or skipped tests.

### Runtime repair, frozen before the fallback

The first 5.1.2 pair crashed in native corner/custom-normal calculation on both regions (exit 11). Keep that series separate as not measured. Environment repair 1: `mkdir -p tmp && uv run -q python docs/research/trainer-revit-intake-r88/replay.py tmp/r88-blender44 --blender44`. Use installed Blender 4.4 with the same code, original import options, sources and three-pair contract (no disabling normals). This is geometry-intake feasibility in the fallback host only; 5.1.2 parity and normals QA remain not measured.

Environment repair 2 (frozen after the 4.4 first crop's 60 s timeout): `mkdir -p tmp && uv run -q python docs/research/trainer-revit-intake-r88/replay.py tmp/r88-blender51-native --blender51-native`. On a scratch copy replace just the legacy Python import call by Blender 5.1.2's built-in `bpy.ops.wm.fbx_import`. Keep the defaults, same source hashes, crop logic, adapter and three-pair contract. Record the changed cropper SHA alongside the pinned blob. This can measure M88 conditionally on that importer; unsupported cross-importer parity, custom normals and material fidelity are not measured. Do not substitute this route into the product.

## Environment runs (not counted as BodyPlan results)

| Run | 63A | 63B | Result |
| --- | --- | --- | --- |
| Blender 5.1.2 (legacy Python importer) | exit 11 × 3 (15.051, 18.003, 16.610 s) | exit 11 × 3 (15.985, 27.787, 13.954 s) | 108.842 s series; crashed in `normals_calc_corners` / `mesh_normals_corner_custom_set`; BodyPlan **not measured**. |
| Blender 4.4.0 (legacy Python importer) | 60.363 s timeout | 60.430 s timeout | first pair incomplete for M88, stopped before the second pair could complete to leave card time for the native importer; BodyPlan **not measured**. |

Receipts: `trainer-revit-intake-r88/blender51-receipt.json`, `trainer-revit-intake-r88/blender44-partial.json`. The latter is the last complete checkpoint before the operator stopped the fallback. Runtime setup also hit a missing parent directory before any 4.4 invocation; creating `tmp/` resolved it.

Read-only `twinqa.fbx_header` on the pinned copy: Autodesk Revit 2024, source `UnitScaleFactor=30.48 cm`, `OriginalUnitScaleFactor=1.0`; tower boxes and Blender crop world coordinates are in metres. Both input files from all six saved #87 snapshots match the declared hashes, independent of the candidate source-copy check.

## Controls and limits

- Positive interface control: `test_revit_route_floor_from_dump_is_a_body_plan` runs the same adapter on a synthetic crop with matching labels, requires nonzero openings, validates the plan and builds an all-quad module. This is not a native 63A/63B quality control.
- Injected negative: the synthetic empty crop reaches the adapter, exits 1 with `no window objects: check --keys`, and emits no JSON. It is not an Artem-rejected model and is not counted in M88.
- No source, deliverable, bank, product code, gate or tolerance changed. No review scene was opened. Finish or custom-normal fidelity and visual calibration against accepted/rejected models remain not measured. The bounding box crop is by **object centre in XY**, not mesh containment; the crop bbox overhangs both specified rectangles. An imported object is not proof of tower ownership.
- Next (not run): build a source-authoritative window-family mapping using Revit categories and explicit exclusions (do not glob every `Окн_` label); freeze on 63A and run the identical mapping on 63B. Keep exact opening count, false positives and zero silent drops as evidence. If input parity is established, measure valid fresh-agent FBX with the isolated practice lane, not by seeding an accepted plan.

Affected tests: `uv run -q pytest -q tests/test_body_lattice_1736.py tests/test_body_training_1619.py tests/test_body_training_1619_stage2.py tests/test_trainer_inspect.py tests/tools/test_trainer.py` → 191 passed; `uv run -q pytest -q tests/test_blender_exit_code_guard.py` → 37 passed.

Full suite: deferred to merge batch (rule 68).

## M88 result — built-in importer, no KEEP

**Гипотеза опровергнута для измеренного маршрута.** Встроенный импортёр Blender 5.1.2 дал непустые вырезки 6/6, но доступный штатный адаптер не распознал ни одного окна и не выдал BodyPlan ни на 63A, ни на отложенной 63B. Доступность скрипта сама по себе не решает остановку. Прохождение `artifact` свежим агентом — **inconclusive / not measured**, не 0/6 запусков тренажёра.

| Fixture | Baseline adapter absent | Native crops | Candidate M88 | Median paired gain (range) | Crop + adapter s, median (range) |
| --- | --- | --- | --- | --- | --- | --- |
| 63A tuning | 3/3 | 3/3 | 0/3 | 0 (0–0) | 26.961 (25.154–26.967) |
| 63B held out | 3/3 | 3/3 | 0/3 | 0 (0–0) | 21.613 (21.586–23.562) |

- Series finished in 151.166 s; first pair 50.300 s. All six attempts reached the adapter (exit 1, `no window objects: check --keys`, no plan). No candidate plan reached schema or mesh checks. Baseline is a path-availability check, not a timed modelling run.
- Native cropper SHA-256 `11b6462575bd67a90ae6178beb3699cc716ec4dac81671712b8d11bef590d72a`. Source pre/post parity passed. `tri`, `obj`, `names` each had three distinct array hashes per tower, while `mat` and `mats` each had one; byte/deterministic ordering parity is not claimed. Per-array fingerprints, bounds and timings: `trainer-revit-intake-r88/blender51-native-receipt.json` (Git LF SHA-256 `26eabec5178fb66275584f21490032ddb9c819576f72defe7d98eb5d99723589`).
- Post-run name census, identical counts across the three crops per tower: 63A 9,795 names, 63B 5,370. Each had zero exact substring hits for either default window key (`Окно`, `балконная дверь`); `Окн_Окн_` had 725 / 553 hits, `Окн_Вит_` had 265 / 99. These are string counts, not approved window counts. Independent replay requires the pinned sources and #87 local snapshots; branch receipts are readable without those inputs.
