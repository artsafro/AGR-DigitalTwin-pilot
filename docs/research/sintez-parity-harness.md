# Synthetic SINTEZ 1.6.1 / twinqa parity harness (#432)

This is checker characterization, not delivery acceptance. No real assets are used.
The read-only inventory has **14 same + 1 stricter groups**, not the issue's 13+1.
`tools/sintez_parity.py:CASES` selects one focal requirement per group, with two
boundary variants. This does **not** cover every sub-check within each group.
The `pass`/`fail` fixture suffix describes the vendor-oriented intended stimulus,
not a fabricated verdict. The actual measured verdicts below remain authoritative.

## Reproduction

Default, DCC-free: `uv run python -m tools.sintez_parity --output tmp/parity-new`.
This executes production twinqa functions against synthetic readback/bytes and
explicitly reports vendor `not_measured`; it does not claim parity.

Live: `uv run python -m tools.sintez_parity --dcc --blender "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --output tmp/parity-live-new`.
Requires Blender **5.1.2** with `bl_ext.user_default.sintez_agr_checker` **1.6.1**.
Every output directory must be new. `--case <fixture-id>` selects a subset.
The harness exports a factory synthetic FBX, imports it back for measured facts,
packages it with the synthetic PNG/GeoJSON bytes, runs
`jobs/KPP1/scripts/run_agr_checker.py` in background Blender, and compares an
explicit `req_num`. The Python lane reads the same archived bytes and FBX readback.
Per-fixture output retains seed, readback, raw checklist, commands/exit codes,
ZIP SHA-256, logs and comparison; the root retains `summary.json`.
Exit **0** means agreement (or completed Python-only measurement); **1** means
measured disagreement; invalid/incomplete evidence is an error, never agreement.
Recommendations remain `review`, not hard `fail` or `pass`.

Tests: `uv run pytest tests/qa/test_sintez_parity.py -q` (no DCC).
Opt-in: set `DT_BLENDER` to the explicit executable, then
`uv run pytest tests/dcc/test_sintez_parity_live.py -m dcc -q`.
The live tests assert agreement and deliberately fail on the measured drift;
there is no xfail, waiver, synthetic vendor oracle or production-checker repair.
Default pytest selection excludes `dcc`; no pytest configuration change is needed.
Use a private `--basetemp` on this Windows workstation.

## Measured results

`tmp/parity-live-v003`, Blender 5.1.2 / SINTEZ 1.6.1: **30 fixtures,
23 agreements, 7 disagreements**, CLI exit **1**. Each Blender child exited 0.
The raw evidence bundle accompanies the PR review handoff.

| req_num | Synthetic fixture | SINTEZ | twinqa | Agreement |
|---|---|---|---|---|
| 1.1.1 | `lp_fbx_format-pass` | pass | pass | yes |
| 1.1.1 | `lp_fbx_format-fail` | fail | fail | yes |
| 2.10.3.3 | `lp_naming_masks-pass` | pass | pass | yes |
| 2.10.3.3 | `lp_naming_masks-fail` | fail | fail | yes |
| 2.3.14 | `lp_transforms-pass` | pass | fail | **NO** |
| 2.3.14 | `lp_transforms-fail` | fail | fail | yes |
| 4.1.5 | `lp_pivot-pass` | pass | not_measured | **NO** |
| 4.1.5 | `lp_pivot-fail` | review | not_measured | **NO** |
| 2.3.6 | `lp_polycount-pass` | pass | pass | yes |
| 2.3.6 | `lp_polycount-fail` | fail | fail | yes |
| 2.3.7 | `lp_duplicates-pass` | pass | pass | yes |
| 2.3.7 | `lp_duplicates-fail` | fail | fail | yes |
| 4.1.3 | `lp_uv-pass` | pass | pass | yes |
| 4.1.3 | `lp_uv-fail` | review | fail | **NO** |
| 2.3.18 | `hp_meshes_transforms-pass` | pass | fail | **NO** |
| 2.3.18 | `hp_meshes_transforms-fail` | fail | fail | yes |
| 2.3.9 | `hp_polycount-pass` | pass | review | **NO** |
| 2.3.9 | `hp_polycount-fail` | fail | fail | yes |
| 2.3.11 | `hp_duplicates-pass` | pass | pass | yes |
| 2.3.11 | `hp_duplicates-fail` | fail | fail | yes |
| 2.10.1 | `hp_naming_symbols-pass` | pass | pass | yes |
| 2.10.1 | `hp_naming_symbols-fail` | pass | fail | **NO** |
| 2.10.4.2 | `hp_naming_masks-pass` | pass | pass | yes |
| 2.10.4.2 | `hp_naming_masks-fail` | fail | fail | yes |
| 2.2.6 | `hp_json_properties-pass` | pass | pass | yes |
| 2.2.6 | `hp_json_properties-fail` | fail | fail | yes |
| 2.9.4a | `hp_pivot-pass` | pass | pass | yes |
| 2.9.4a | `hp_pivot-fail` | fail | fail | yes |
| 2.5.3.4 | `hp_png-pass` | pass | pass | yes |
| 2.5.3.4 | `hp_png-fail` | fail | fail | yes |

## Disagreements retained, not fixed

- NPM/VPM transforms: vendor accepts rotation just below sqrt(0.001) radians;
  twinqa's applied-transform check rejects it (two cases).
- NPM pivot: production `scene_findings` has no corresponding measurement;
  vendor pass/recommendation versus explicit `not_measured` (two cases).
- Degenerate NPM UV: vendor recommendation versus twinqa hard failure.
- VPM 1,000,000 triangles: vendor hard-limit pass versus twinqa project-target review.
- Non-ASCII VPM mesh name: vendor req 2.10.1 passes this package while twinqa fails;
  the stimulus survives export/readback. Length req 2.10.2 is not this focal test.

No checker or shared threshold was changed to erase these differences. Missing
checks and UCX gap logic remain outside this harness. Synthetic FBX generation
uses one mesh; this is not evidence about arbitrary real package compositions.
