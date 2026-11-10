# Research: is the 80° relief step at Vatutino (-13..-9, -93..-89.5) a real retaining edge or a TIN artefact?

Card t_beed4e70 (research mode, no GitHub issue). Question from PR #1164: the 20 GND-03 zero-drop
outer edges sit on a closed 19-face `TileLight` band sloped 80.1–81.5° (~2 m step between a ramp and
a platform at the south boundary). This report answers whether that step is a drawn retaining
edge/curb or a TIN cliff produced by two close elevation marks, and points at the smallest fix.

## Summary

The ~2 m, 80–81.5° step is **a TIN cliff produced by two close elevation marks**, not a retaining
edge/curb drawn as geometry. The cliff-forming TIN triangle (measured 81.4° slope) is spanned by
three elevation points: spot height **1079ED (Z=145.56)** and spot height **1079EE (Z=141.83)**, 0.75 m
apart (same X, 3.73 m drop), plus contour vertex **1077AA (Z=145.50)** ~10 m away. The pair
1079ED/1079EE is a real retaining wall encoded the usual VP way — top and bottom labels at the same
plan position — but the wall has **no drawn geometry**: `ГП_ПодпорнаяСтенка` and `ГП_Откосы` are
empty, and the nearest curb (`Борт` F4092, the plot-boundary road curb) is 13 m away. `build_tin`
Delaunay-triangulates these marks with no breakline, so the 3.7 m wall is smeared into a ~2 m ramp
over ~10 m. The GND-03 classifier fix of PR #1164 is correct for the QA (the band is a legitimate
steep face, not a missing skirt); the remaining accuracy gap is that the wall is not modeled as a
vertical face. Smallest fix: detect the paired wall marks in the adapter, then model them as a
breakline/vertical face (see Proposed next tasks).

## Findings

### 1. The step band is the western, already-flattened part of one TIN triangle

- Reconstructed the TIN exactly as the build does (`src/dt_ai/geometry/ground_cake.py:575 build_tin`,
  Delaunay over all 5 188 elevation points from the adapter output). Near the step region
  (local x −16…−5, y −96…−86) there is **one** near-vertical triangle, slope **81.4°**:

  | vertex | source | layer | local XY (m) | raw XY (m) | Z (m) |
  |---|---|---|---|---|---|
  | 1079ED | point (spot height) | `ГП_Вертикалка_ОпорнаяТочка_New` | (−5.754, −86.062) | (−7599.788, −15373.807) | 145.56 |
  | 1079EE | point (spot height) | `ГП_Вертикалка_ОпорнаяТочка_New` | (−5.754, −86.812) | (−7599.788, −15374.557) | 141.83 |
  | 1077AA | contour | `ГП_Вертикалка_ГоризонталиОсновные` | (−13.330, −92.770) | (−7607.364, −15380.515) | 145.50 |

  Distances: 1079ED↔1079EE **0.75 m** (ΔZ 3.73 m); 1079ED↔1077AA 10.12 m; 1079EE↔1077AA 9.64 m
  (ΔZ 3.67 m). Local = raw + (7594.034, 15287.745), the same origin the build uses to centre the
  delivery (readback `SM_Vatutino_Ground` bounds x ±106.74, y ±99.38, centred on 0; boundary bbox
  x −7700.78…−7487.29, y −15387.12…−15188.37).
- The card's band (−13…−9, −93…−89.5) is the west end of that triangle, next to the contour vertex
  1077AA; its lower Z (~143.5) is the TIN slope toward the 141.83 road mark 1079EE. There is **no**
  elevation mark at the band itself — the only sub-145.5 elevation point within 20 m of the band
  centre (−11.5, −91) is 1079EE (7.1 m away).
- Verified myself: `C:/x/t_d94665f2/paving_ground_inputs_v4.json` (adapter output, sha256
  `3b6b433d…` = the `source_adapter_sha256` in `jobs/VATUTINO-SITE/ground-notch-approval-v015.json`)
  and `C:/x/t_5e2eb833/v009/readback-npm.json` (the PR #1164 reproduction file).

### 2. The pair 1079ED/1079EE is a retaining wall in the survey, not a data-entry error

- The paving VP (`Д2_ВП_2024.10.10`, frozen layer `!_А101_предварительная ВП`, container 107E50)
  carries **48 spot heights**. Eleven of them form 9 pairs with the same X, a 0.75 m Y offset and a
  large Z drop — the standard VP convention for a retaining wall, where the top and bottom elevation
  are written at the same plan position:

  | pair (top / bottom) | local X | Z top / Z bottom | ΔZ (m) |
  |---|---|---|---|
  | 107A05 / 107A06 | −79.22 | 149.59 / 145.88 | 3.71 |
  | 1079E9 / 1079EA | −77.54 | 146.35 / 142.09 | 4.26 |
  | 107A09 / 107A0A | −77.42 | 148.95 / 144.14 | 4.81 |
  | 1079ED / 1079EE | −5.75 | 145.56 / 141.83 | **3.73** |
  | 107A2B / 107A2C | +9.21 | 152.66 / 150.76 | 1.90 |
  | 1079FD / 1079FE | +27.01 | 151.84 / 148.58 | 3.26 |
  | 1079F5 / 1079F6 | +40.94 | 146.72 / 142.11 | 4.61 |
  | 1079F1 / 1079F2 | +76.18 | 147.35 / 142.30 | 5.05 |
  | 1079F9 / 1079FA | +85.88 | 147.84 / 142.57 | 5.27 |

  Two further pairs (107A01/107A02, 107884/107885) differ by 0.04 and 0.36 m — a level reference,
  not a wall. The wall relevant to the band is **1079ED/1079EE** (3.73 m), the only pair in the south
  of the plot whose top/bottom surround the band.
- Both 1079ED and 1079EE are **inside the plot** (`inside=True`), so the road's 141.83 m elevation is
  legitimately part of the Ground relief input.

### 3. No retaining wall, slope or curb geometry is drawn at the step

- The Civil 3D template layers `ГП_ПодпорнаяСтенка` (retaining wall) and `ГП_Откосы` (slopes) are
  **empty** in both DWGs (`docs/research/spozu-vatutino/main-inventory.md` lines 229/221,
  `paving-inventory.md` lines 252/244). The A101 concept has no wall layer.
- `jobs/VATUTINO-SITE/ground-parts.md` line 79 records this: "Retaining walls | — | none found by
  layer or legend | —".
- The nearest `ground_elements` record to the wall marks is **13.08 m** away (`Борт` F4092, the
  plot-boundary road curb); the nearest modelled garden curb is 14.2 m away. Nothing is drawn at the
  wall line itself.
- Covering at the band and both sides of it is `tile_light` (one continuous hatch, 7 348.6 m²) — the
  step is not a covering/material boundary either.

### 4. Conclusion and relationship to PR #1164

- **Decision: two close elevation marks producing a TIN cliff** (the second option in the card). The
  marks are a genuine retaining wall, but the wall is only survey labels; there is no drawn retaining
  edge/curb, and `build_tin` has no breakline, so the 3.7 m wall is smeared into the ~2 m, 80–81.5°
  band.
- **GND-03 QA (PR #1164) is unaffected by this nuance**: the band is a legitimate steep face, so the
  proposed classifier change (slope-independent `nz > 1e-6·|n|`) is the right fix for the 20 zero-drop
  edges; nothing here contradicts it. The architecture-accurate fix (model the wall as a vertical
  face) is a separate, larger task and is not required to close GND-03.

## How it applies to this repository

- `adapters/cad/configs/vatutino_dom2.yaml` — `elevations.layers: [ГП_Вертикалка_ОпорнаяТочка_New]`
  and `contour_layers: [ГП_Вертикалка_ГоризонталиОсновные, …_Вспомогательные]` feed the marks into
  the TIN; `ground_elements` has no wall role.
- `adapters/cad/spozu.py::read_spozu_dxf` (lines ~690–748) — extracts the 48 spot heights and the
  contour vertices; nothing detects the wall pairs today.
- `src/dt_ai/geometry/ground_cake.py::build_tin` (line 575) — merges same-XY points, drops
  contradictory same-XY pairs, then `shapely.delaunay_triangles` with **no breakline constraint**;
  this is where the wall becomes a smeared ramp. `ReliefSampler` (line 603) then samples it.
- `jobs/VATUTINO-SITE/build_ground_v015.py::geometry` (line 196) — `sampler = gc.ReliefSampler(gc.build_tin([…]))`
  is the call that turns `data['elevations']` into the relief.
- `jobs/VATUTINO-SITE/ground-elements-v011.md`, `ground-parts.md` — record that no wall/ramp layer
  exists and all `Борт` curbs were skipped (no visible section); the wall is therefore absent from the
  modelled Ground and only lives in the relief.

## Proposed next tasks

- **Detect retaining-wall mark pairs in the SPOZU adapter** (S). In
  `adapters/cad/spozu.py::read_spozu_dxf`, when two spot heights on `ГП_Вертикалка_ОпорнаяТочка_New`
  share the same X within a few mm, are ≤ ~1 m apart in Y and differ by > 1 m in Z, emit a `Finding`
  (new code, e.g. `retaining_wall_marks`) carrying both handles, XY, Z and the drop. This surfaces all
  9 walls to the pipeline with no geometry change. Value: makes the relief's steep bands auditable and
  gives a hook for the modelling task. Effort S. **Advances #298**.
- **Model retaining walls as a vertical face + TIN breakline** (M). Feed the detected pairs into
  `jobs/VATUTINO-SITE/build_ground_v015.py` / `src/dt_ai/geometry/ground_details.py` so each wall is a
  near-vertical curtain (reusing the existing `add_skirt`/`build_details` machinery) and the Delaunay
  triangulation keeps a sharp breakline instead of a smeared ramp. Value: replaces the ~2 m ramp with
  the correct ~3.7 m wall; improves architectural accuracy for the whole south boundary. Effort M.
  **Advances #298**.
- No task is needed to close GND-03: the PR #1164 classifier fix already resolves the 20 zero-drop
  edges correctly (the band is a real steep face).

## Open questions for the user

1. **Is the preliminary ВП (`Д2_ВП_2024.10.10`, frozen) the final height source for Ground?** The 9
   retaining walls exist only as top/bottom spot labels in this preliminary plan; a later VP sheet may
   draw the walls as geometry (or drop them). This decides whether the M task above is worth doing
   now or should wait. (Same as inventory OQ5.)
2. **Should the 9 retaining walls be modelled as vertical faces, or is the smeared TIN slope
   acceptable for the current concept?** If acceptable, the M task is `Archive`-able and only the S
   detection (transparency) remains.
3. **Is the road at Z ≈ 141.8–142.6 (the bottom of the walls) inside the Ground delivery boundary?**
   Both wall-bottom marks are `inside=True`, so the Ground surface currently includes the road; if the
   road should be a separate surface (or outside Ground), the wall handling changes.
