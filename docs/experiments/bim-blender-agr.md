# Experiment: Blender for AGR: bpy headless vs live session, which of our tasks it solves

Card `t_c9185662` (dt-experimenter), branch `experiment/bim-blender-agr`. Report under test:
`origin/docs/research-bim-blender-agr:docs/research/bim-blender-agr.md` (proposals E1–E3).

## Question

The report's main claim is "offline geometry/rules → headless Blender I/O → independent readback; live only for
snapshots and review". Its E1 says the headless and live routes are one data-API algorithm in two execution
boundaries, so the same offline twin should come out the same after save/export and a fresh readback, and today's
checker (`checks.run`, including `check_orientation`) should judge both the same way. Is that true here, and what
does each route cost per call?

## Methods chosen

| Report item | Chosen? | Why |
|---|---|---|
| **E1**: twin build + saved/exported readback parity, headless vs live, with negative controls | **yes (M1)**, scaled down | Touches the engine (`from_spec`), exporter (`tools/export/export_mesh_blender.py`), readback (`tools/source/measure_spec_blender.py`) and checker (`twinqa.geometry.checks`); measurable claims; fits the time box |
| E2: reproducible render/QA packet | no | Needs engine/colour/device pinning plus new silhouette and UV-phase probes. It does not fit 60 min, and the outcome is evidence images, not a pipeline change |
| E3: Blender → Max → Blender transport | no | Needs 3ds Max (`dcc_batch.py max`), which is dt-experimenter-codex's program, not mine |

Only one method was measured. A second one could not be done properly in the time box.

## Setup

- Inputs: **copies** of `benchmark/bench-{b01-box,b02-corner-niche,b02t-terrace}/{spec,object,tolerances}.json` in
  `%TEMP%\agr-exp-t_c9185662\v001\`. Spec hashes were checked before and after: unchanged. `data/` was not touched.
- Geometry: engine dump `from_spec.build(spec)` (**SYNTHETIC**, engine-generated). The native `etalon.fbx` files are not
  on disk (the `data/benchmark/` folder is missing), so this experiment does not cover native-etalon extraction. The
  checker's etalon is the clean engine dump itself, so the geometry checks measure round-trip parity.
- Variants per bench (from `experiments/blender-bpy-automation/make_fixtures.py`): `clean`; `flip1`, where one facade
  polygon is reversed; `flipall`, where the whole body is inverted.
- Routes, each run 3 times (3 benches × 3 variants × 2 routes × 3 reps = **54 realizations, 108 fresh readbacks**):
  - **headless (baseline)**: `run_blender(tools/export/export_mesh_blender.py)` on Blender **5.1.2** headless, then `.blend` + FBX.
  - **live (prototype)**: `experiments/bim-blender-agr/live_realize.py` through `blender_exec.py --code`, in **Blender 4.4.0 live**.
    It uses the same data-API realization but no `read_factory_settings`. It creates only owned datablocks, writes the
    `.blend` with `bpy.data.libraries.write` around a temporary scene (the user's open file is never saved), exports the
    owned selection to FBX, and removes everything it created.
  - Readback for both routes: a fresh headless 5.1.2 `measure_spec_blender.py` run on the FBX and on the `.blend`, then
    `checks.run(readback, clean_dump, spec, tolerances.geometry)`.
- Commands: `uv run python experiments/bim-blender-agr/run.py <S> 3`, then `uv run python experiments/bim-blender-agr/analyze.py <S>`.
  Raw output: `experiments/bim-blender-agr/{results,summary}.json`.

## Results

Mesh facts (identical across routes and reps; FBX readback of `clean`): B01 `body` 156 v / 282 tris, B02 263 / 472,
B02t 370 / 648. The material-id histograms {1, 6, 11, 21} and the LEVEL_L0/L1/roof helpers at 0 / 3.3 / 6.6 m were
the same in every pair.

| Metric | headless 5.1.2 (baseline) | Blender 4.4.0 live (prototype) |
|---|---|---|
| Realize + save + export, wall per call (median [min–max], n=27) | **1.07 s** [0.96–1.29] | **0.17 s** [0.12–0.29] |
| of which work inside Blender | not split (mostly process startup) | build 0.002 s, write .blend + FBX 0.013 s |
| Fresh readback FBX / .blend (headless 5.1.2, median) | 1.07 / 0.96 s | 1.02 / 0.98 s |
| Max vertex Hausdorff readback vs source, FBX / .blend | 0.0020 / 0.0004 mm | 0.0020 / 0.0004 mm |
| .blend readback equals FBX readback (centroid+normal signature) | 27/27 | 27/27 |
| Clean passes `checks.run` | 9/9 | 9/9 |
| `flip1` caught by `orientation` | 9/9 | 9/9 |
| `flipall` caught (`mesh`, `opening_planes`, `orientation`) | 9/9 | 9/9 |
| Live scene restored (objects/meshes/materials/scenes/collections counts) | n/a | 27/27, no renamed objects |

Cross-route parity over 27 same-bench/variant/rep pairs: mesh facts equal **27/27**, orientation-sensitive triangle
signature equal **27/27** (max deviation 0.0), checker verdict and failed-check list equal **27/27**.

## Verdicts

| Method | Verdict | Reason |
|---|---|---|
| M1 / E1: the same offline twin realized headless or live gives the same saved/exported twin and the same QA verdict | **adopt** (as a routing rule plus a parity regression) | 27/27 identical facts, signatures and verdicts across 5.1.2 headless and 4.4.0 live. Both routes catch 18/18 injected orientation defects with 0/18 false positives. The route is an execution choice and does not change the result. Live is about 6× faster per call (0.17 s vs 1.07 s) because it skips process startup, but it holds the user's single shared session, and the headless readback (about 1 s) still dominates a QA loop. Headless stays the production default (isolated, version-pinned 5.1.2). Live is justified for interactive iteration and for snapshots of unsaved sources |

Limits: synthetic engine geometry only, with no native etalon, UVs, textures or instancing. Live is 4.4.0 and headless is
5.1.2, so version and route are confounded, yet they still matched exactly. FBX bytes were not compared (timestamps); the
comparison uses readback facts. The test-suite failure the report mentions (`test_a_corner_pilaster_passes_every_check`)
was not re-run. This card changed no `src/` code.

## Proposed follow-up (adopt)

- **Title:** "Route-parity regression: headless vs live realization of B01/B02/B02t"
  **Scope:** move `experiments/bim-blender-agr/live_realize.py` behind a `--route live` flag of a small harness tool
  (not `export_mesh_blender.py` itself). Add a `dcc` + `blender` marked pytest that realizes the clean B01 dump through both
  routes and asserts equal readback facts and signatures. Document in `docs/agents/CAPABILITIES.md` that live realization
  writes owned data only (`libraries.write` + temporary scene + cleanup check). Extend later with UV/material/instanced
  fixtures (E3 inputs) before live is used for textured twins.
