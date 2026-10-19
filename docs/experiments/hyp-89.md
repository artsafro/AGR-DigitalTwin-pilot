# Hypothesis #89: bpy 5.1.2 wheel vs headless Blender 5.1.2 on B01/B02/B02t export/readback

**Verdict: CONFIRMED** (narrow scope: synthetic engine dumps, no UVs). `delivery_passed=false`. This is a parity
experiment. It does not approve a wheel lane, and it changes no production code, dependencies or CI. Whether to add
a wheel lane stays a user decision (source report `docs/research/bpy-wheel-viability.md`).

## Claim (issue #89)
For engine-generated B01, B02 and B02t meshes, `bpy==5.1.2` under isolated CPython 3.13 runs the unchanged
mesh exporter and both readback scripts with the same structural, material and helper results as headless
Blender 5.1.2. The maximum world-coordinate disagreement must be ≤ 1e-5 m.

## Setup
- Base: `origin/main` 3cf7c93. Branch `experiment/hyp-89`. Card t_f79d84bd. No live Blender/MCP, no `data/`.
- Executable lane `exe`: `C:/Program Files/Blender Foundation/Blender 5.1/blender.exe` 5.1.2 (bundled CPython 3.13.9,
  NumPy 2.3.4). Flags: `--background --factory-startup --disable-autoexec --python-exit-code 1 --python <script> -- <args>`.
- Wheel lane `whl`: a disposable `uv venv -p 3.13` at `%TEMP%\agr-blender-t_f79d84bd\venv` (CPython 3.13.3,
  `bpy==5.1.2`, `numpy==2.5.3`). Invocation: `venv/Scripts/python.exe <script> -- <args>`. pyproject, uv.lock and
  the repository `.venv` were not touched.
- Scripts, unchanged (sha256 prefix): `tools/export/export_mesh_blender.py` 085664e324b65b3a,
  `tools/blender/fbx_readback.py` 45e323f0b349884f, `tools/source/measure_spec_blender.py` 423b25fd69fa1937,
  `src/dt_ai/geometry/from_spec.py` 0b1ea4c6e200318b.
- Inputs: tracked `benchmark/bench-{b01-box,b02-corner-niche,b02t-terrace}/{spec,object}.json`. They are copied
  and hashed in `evidence/input-hashes.json`, and the hashes were identical after the run (6/6).
- Common dumps (synthetic reference proxies, not etalons): `build(Spec.model_validate(spec), BuildInputs.from_object(obj))`
  gives 1 mesh `body` + 3 `LEVEL_*` helpers. Triangles: B01 282, B02 472, B02t 648.

```
uv run python experiments/hyp-89/build_dumps.py %TEMP%/agr-blender-t_f79d84bd/common
python experiments/hyp-89/run_matrix.py %TEMP%/agr-blender-t_f79d84bd <venv python> 2
python experiments/hyp-89/compare.py  %TEMP%/agr-blender-t_f79d84bd
```

Matrix, run twice in fresh directories (`rep1`, `rep2`). For each model and each exporter lane: export, then
measure the `.blend` in its own lane, then run `fbx_readback` and `measure_spec` on the FBX in both reader lanes.
That is 72 processes, and every one is a separate process with a 300 s timeout and a log.

The comparison excludes only `source`, `sha256` and collection order (lists are sorted by object name). Vertex
and triangle order are **not** normalised.

## Prediction table (frozen from the issue) and results

| Metric | Baseline | Rejection threshold | Measured (worst of all combos) | Result |
|---|---|---|---|---|
| Export and readback completion | exe lane | any nonzero exit, missing or empty output, `readback_ok != true`, missing mesh | 72/72 exit 0. All 12 `.blend`/FBX pairs are non-empty. 24/24 readbacks have `readback_ok=true` with 1 mesh | pass |
| Structural and material facts (`fbx_readback`, 2 exporters × 2 readers × 3 models × 2 reps) | exe export / exe read | any mismatch in names, counts, degree histogram, parent, ordered slot names, UV channels, other objects | 24/24 identical, 0 discrete diffs. B01 156 v / 141 p / 282 t; B02 263 / 236 / 472; B02t 370 / 324 / 648. All polygons are quads, slots `ID_01..ID_21`, uv_channels 0, parent None, 3 EMPTY helpers | pass |
| World geometry and helpers (`measure_spec`): lanes vs exe/exe | exe lane | max XYZ > 1e-5 m; triangles, polygon_sizes, material_ids or helper names not exact | FBX in both readers: 24/24, max ΔXYZ **0**. `.blend` whl vs exe: 6/6, max **0** | pass |
| World geometry vs common engine dump | engine dump | same | FBX: 24/24, max ΔXYZ **1.72e-6 m**, helpers 9.5e-8 m. `.blend`: 12/12, max 3.5e-7 m. Triangles, polygon_sizes and material_ids exact, in the same order | pass |
| Transform parity | exe lane | location/scale > 1e-6, Euler > 1e-4 deg | max 0 / 0 | pass |
| Repeatability rep2 vs rep1 | rep1 | any discrete change | 24/24 identical (readback + measure), max Δ 0 | pass |

`udim_tiles` were not emitted (the dumps have no UVs), so that row is untested rather than passed. The comparator
was checked against itself: a 2e-5 m shift of one vertex and a +1 change of one material id were both flagged as
failures.

Runtime (descriptive only, median seconds per process, cold process every call):

| Script | exe | whl |
|---|---|---|
| export_mesh_blender.py (n=6) | 1.01 | 0.94 |
| fbx_readback.py (n=12) | 0.98 | 1.04 |
| measure_spec_blender.py (n=18) | 0.91 | 0.96 |

## Verdict
**CONFIRMED.** All four rows pass on all 3 models, 2 exporters × 2 readers, and 2 repetitions. The lanes are
bit-identical in every JSON value compared. Against the engine dump, the worst difference is 1.72e-6 m (float32
storage), well under the 1e-5 m threshold.

Limits:
- Synthetic engine proxies only: one mesh per model, quads only, no UVs or images.
- Not a material-finish, normals, UV or delivery certification. `delivery_passed=false`.
- Wheel NumPy (2.5.3) differs from the bundled one (2.3.4). No script used NumPy on this path.

## Adoption scope (if the user chooses it; separate card)
Adopted (issue #89 adoption card): the three prototype scripts moved to `experiments/bpy-benchmark-parity/`
(`build_dumps.py`, `run_matrix.py --wheel`, `compare.py` over `parity_lib.py`); the commands above now run from there.
Evidence stays in `experiments/hyp-89/evidence/`.

- `experiments/bpy-benchmark-parity/`: move `build_dumps.py`, `run_matrix.py` and `compare.py` there as an
  optional, reproducible harness with a parameterised wheel interpreter.
- `tests/dcc/test_bpy_benchmark_parity.py`: skipped unless both `blender.exe` 5.1.2 and a `bpy==5.1.2` interpreter
  are present. It asserts the four rows above for B01/B02/B02t, plus a UV-bearing fixture to cover `udim_tiles`.
- blender.exe stays the default. Do not change `src/twinqa/scene.py`, dependencies, CAPABILITIES policy or CI.

Raw evidence: `experiments/hyp-89/evidence/{runs.json,compare.json,input-hashes.json}`. The per-call logs and FBX
files are in `%TEMP%\agr-blender-t_f79d84bd\rep{1,2}\` (local, not committed).
