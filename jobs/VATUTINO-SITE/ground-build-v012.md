# Vatutino Ground v012 — #295 / PR #308

Status: **not passed / blocked on UCX**, not a delivery acceptance. Geometry approval by a person, UCX (#326 / PR #334) and the site assembly / SINTEZ gates remain separate. v012 changes only the layer offsets on steep relief; everything else (input, partition, relief, curbs/stairs, cleanup, UV) is the v011 pipeline, see [ground-build-v011.md](ground-build-v011.md) and [ground-elements-v011.md](ground-elements-v011.md).

## Decision implemented

User decision (Artem, 2026-10-19, card comment): "on steep relief raise a layer LOCALLY so the gap to the base along the face normal is 5-20 mm (V004 band); on flat ground the nominal +6 / +12 mm stays. Report: number of locally raised plates, max raise, min/max normal gap after (must be >= 5 mm, <= 20 mm), V004 co-directional pairs < 5 mm = 0."

Cause of the v011 finding (probe on the v011 master): all 93 sub-5 mm pairs were level 0 / level 1 on VP faces with |n_z| ~ 0.15 (about 81 deg): a 6 mm vertical step gives 6 x 0.15 = 0.9 mm along the normal.

`dt_ai.geometry.ground_cake.raise_steep_layers` (Z only, called by `build_ground.py` after cleanup):

1. Per XY stack, step `s = max(6 mm, 5.5 mm / |n_z|)` over the upper faces at that vertex; offset = level x s. Flat faces (|n_z| > 0.917) keep exactly +6 / +12 mm.
2. The validator's own co-directional test (`twinqa.clearance.co_directional_pairs`) on the master **and** on its exact readback representation (`readback_f32`: XY bbox pivot of `ground_json_to_fbx.py`, float32, 1e-6 m rounding of the JSON and of `fbx_readback.py`), parallel test widened to cos 0.999998: every pair of different levels < 5 mm gets its upper face raised by the deficit to 5.5 mm; pointwise gaps < 5 mm at upper corners (lower face bent within the 10 mm relief tolerance) likewise. A raised vertex lifts the higher levels of its XY stack. Float32 matters: sliver faces (4 m x 6 mm) turn by ~1e-3 rad when Blender stores them, which moved one distance from 6.04 to 4.68 mm.
3. Offsets are tracked per vertex; `measure_steps`, `measure_relief_error`, `measure_stack_gaps` take them, so relief error and gap error stay exact.

## Commands

1. `uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/t_d94665f2/paving_ground_inputs_v4.json --snap 0.003 --out C:/x/t_d94665f2/ground_v012` -> exit 0, all 11 gates true (new: `normal_gap_min_5mm`, `v004_codirectional_below_5mm_0`). Input SHA-256 `3b6b433d718c...` (unchanged since v011).
2. Blender 5.1.2 headless, factory startup, per profile: `ground_json_to_fbx.py -- build`, clean-process `readback <px> <lo> <hi>`, `render`, `tools/blender/fbx_readback.py` -> all exit 0.
3. `uv run python tools/qa/validate_package.py <profile>/SM_Vatutino_Ground.fbx --profile <npm|vpm> --scene --json` -> NPM exit 2, VPM exit 1, **not passed**.
4. Original DWG SHA-256 re-read: main `64e22677454affce...`, paving `d24df23219fe1357...`, equal to `orig_before.sha256`.

## Results

| Check | v011 | v012 |
|---|---|---|
| V004 co-directional pairs < 5 mm, exported FBX (validator) | 97 (min 0.8415 mm), **fail** | **0** (min 5.0 mm), status review (pairs > 20 mm, see below) |
| Same on master f64 / readback-f32 representation (build gate) | 93 / n.a. | 0 / 0 |
| Locally raised upper vertices / faces touching them | 0 | 435 / 1 436 of 11 218 upper faces |
| of these: steep step (phase 1) / pair fix faces / pointwise vertices | – | 46 vertices / 150 faces / 6 vertices |
| Max raise above nominal / max offset | – | 30.94 mm / 36.94 mm |
| Normal gap, upper corner points: min / max | 0.9 mm min | **5.049 mm** / 36.92 mm |
| Normal gap, face centroids: min / max | – | 5.049 mm / 26.62 mm |
| Points below 5 mm (centroid / corner) | – | 0 / 0 |
| Points above 20 mm (centroid / corner) | – | **6 / 18**, at 12 vertices (below) |
| Relief exact max error (offset-aware) | 9.963 mm | 9.963 mm, 0 faces > 10 mm |
| Stack gap error vs. tracked offset / vertical min gap | 0.0005 mm / 6.0 mm | 0.0005 mm / 5.75 mm |
| Triangles surface / total | 32 821 / 46 343 | 32 821 / 46 343 |
| Containment / coverage / cracks / misses | 0 / 99.9962 % (0 m² beyond 2.2 mm) / 0 / 0 | same |

Readback of both FBX (clean process): 46 343 triangles, raw material mismatch 0, surface faces facing down 0, unit scale 1, open = non-manifold edges 8 307 (the user-accepted class "method-C plate borders, user-accepted 2026-10-19"), mirrored UV 0. Density NPM 11.56–30.21 px/m, VPM 589.6–1442.1 px/m, 0 out of band; VPM UV tile [1001], straddling 0. Face Orientation back pixels top/45/135/225/315 = 0/2/4/3/1 (both profiles, unchanged from v011; renders `C:/x/vatutino-ground/v012/`, not committed). FBX SHA-256: NPM `133637004bb2...`, VPM `a55a4a5acb3b...`.

Validator: NPM pass V002/V003/V006, review V004/V012, not_run V001/V005/V014/V015/V017. VPM pass V002/V008/V012, review V003/V004, **fail V010 (no UCX)**, not_run V001/V005/V007/V009/V011/V013/V015/V016/V017. `not_run` is never counted as pass. V004 sub-checks: transforms pass, topology pass (max 10 self-intersections, unchanged), clearance review: 0 below band, 24 928 in band, 17 494 above 20 mm (same order as v011: 17 577; distant parallel overlaps, e.g. skirt vs. plates 152.9 m apart; not part of this decision).

## Open: gap above 20 mm at 12 vertices (needs a decision)

At 12 upper vertices an ~81 deg face (|n_z| 0.149) meets a flatter face. 5 mm on the steep face needs s >= 33-37 mm there; the flatter face allows at most 20.0-23.5 mm (`over_gap_max_bounds_mm` in `ground_report.json`). No continuous Z-only plate satisfies both at the same vertex; it is geometry, not tuning (the gap at a point is offset x n_z of the face it lies on). `gap_min` wins because below 5 mm is a V004 fail and above 20 mm a V004 review. Effect: 6 face centroids 20.1–26.6 mm, corner points up to 36.9 mm; the validator counts none of them (the tilted plates are not parallel to the base). Options: accept these 12 local points; or cut the upper plate at those vertices (a slit, new open border); or move the vertex horizontally (breaks XY unchanged).

## UCX

Not generated. The shared UCX fix (#326, PR #334) passed review round 3 but is **not merged**; its handoff says #295 uses it only after a user-approved merge to `main`. No hand-made UCX. V010 stays fail.

## Tests

- `tests/test_ground_cake.py`: 8 new cases (steep 6:1 synthetic slope with level 1 and level 2): V004 < 5 mm pairs > 0 before and 0 after, corner/centroid normal gaps >= 5 mm, flat vertices exactly nominal, XY/UV/slots/base unchanged, offset-aware steps and relief exact, level 2 never below level 1, infeasible > 20 mm vertices listed, fail closed on bad parameters and offsets. At `c118b00` (old `ground_cake.py`): 8 failed, 19 passed; now 27 passed.
- Full non-DCC suite via `suite_slot.py`: `uv run pytest -q -n 8 -p no:cacheprovider -m "not dcc and not blender"` -> **6045 passed, 14 skipped**, 132.8 s.
