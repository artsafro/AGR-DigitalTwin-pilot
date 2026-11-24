# Autoresearch #69: same-tile UV island gap on delivered NPM (OBSERVE)

Card t_de9ede95 (standing #69), branch `research/autoresearch-standing-69`, base `origin/main`
`4288c54de328db7a5037b57707862319f7aa6ff0`. Focus: NPM/VPM texture and atlas quality (Artem 2026-11-24).

## Why this target (frozen before measuring)

- Regulation p.9 §5.4: >= 8 px between UV islands (NPM). The existing checkers measure only
  layout rectangles / cell bands: `tools/derive/npm_atlas.py:validate_export` (declared regions of
  `npm_atlas.json`), `twinqa.npm_uv` V006 (faces inside their atlas cell, fails AC08 on a format
  precondition, #65). Nothing measures the gap between two actual islands that share one tile.
- #65 next target 2 / #66 next target 1 asked exactly for this census on real exported UVs.
- Not owned elsewhere: G22 atlas #1649, MAF numbering #1809, Staropetrovskiy #1500, KPP1 #1817
  (none measures same-tile island gaps). Form check is closed (rounds #40-#57).

## Metric

On the NPM FBX `SM_Nku_1.fbx` read back by Blender (`twinqa.scene.readback`, unchanged):
- polygon tile = UDIM of its UV centroid (same `_tile` as #67/#68); tile px = decoded Diffuse PNG side
  of that tile from the same ZIP;
- island = connected faces of ONE tile joined by a shared UV edge (both endpoint UVs equal within
  1e-6), across all meshes of the file;
- pair gap px = shapely distance between the island unions, times tile px; `overlap` = intersection
  area > 0.01 px^2 (a different defect class, reported separately, never counted as a gap).
- **N69** (primary) = number of same-tile island pairs on TEXTURED tiles (4096 px Diffuse) with
  0 <= gap < 8 px and no overlap. Secondary: `min_gap_px`, `overlap_pairs`, island count, pair count,
  the same numbers on solid 256 px tiles (no texel requirement [Artem 2026-11-17], reported only).

## Hypothesis H69 and calibration

H69: the rejected AC08 v007 (rejected for visible seams) scores worse than the visually accepted v010:
N69(v007) > N69(v010). Labels: v007 rejected / v010 visual etalon (as in #58-#68).
- Applicability precondition: each version has >= 2 islands on a textured tile. If not, H69 is
  `inconclusive` (not measured), never refuted or confirmed.
- If N69(v010) > 0, the 8 px rule FIRES on the accepted control: recorded as collateral (a future
  gate would false-fail the etalon), whatever H69 says.

## Witness and perturbations (in-memory on the fresh readback, labelled as such)

- Positive trigger witness W1: on v010, take the textured-tile island pair with the smallest gap
  >= 8 px; translate the smaller island toward the other along the closest-point direction so the gap
  becomes 4 px. Expected: N69 += 1 or more, other islands unchanged (changed_islands = 1).
- W2 (boundary): same move to a 9 px gap. Expected: N69 unchanged.
- If v010 has no pair >= 8 px on a textured tile: W1/W2 `not_exercised` (not measured).
- Native (export-path) perturbation: not measured in this round (named as next target).

## Runs, budget, stop rule

- 3 fresh readbacks per version (fresh Blender process, fresh FBX extraction), order v007, v010 x3.
  Stability: spread of N69 and min_gap_px over the 3 must be 0 (else `inconclusive`).
- Budget: 15 min wall for the series; a single readback > 120 s => budget stop => `inconclusive`
  with the exact next command. Wall time and run status are recorded separately.
- One round only; no keep threshold (OBSERVE: no production code changes, nothing applied to any
  package). A "would change" note is the only output toward production.

## Forbidden shortcuts

No edits to delivered packages or Drive evidence (read-only, hash preflight); no changes in src/,
tools/, standards/, adapters/ (preflight `git diff --quiet BASE`); no deselected tests or weakened
tolerances; no rescoring of an old dump as stability evidence; no other cards' files.

## Replay

`uv run --frozen python docs/research/atlas-island-gap-r69/replay.py tmp/r69-run`
Inputs pinned by SHA-256 in `replay.py` (Blender 5.1 exe, both `SM_Nku_1.zip`). Replay limited to
Windows + Blender 5.1.2 + Drive `AGR-evidence/559-tec26-oks-ac08-pilot-v00{7,10}`.
Receipt: `docs/research/atlas-island-gap-r69/receipt.json`.

## Round log

### R1 (frozen contract, SM_Nku_1.fbx) - wall 6.099 s, status complete, 3 fresh readbacks per version

- Crash before R1 proper: `UCX_SM_Nku_1_Main_001: no polygon_uv` -> UCX collision meshes skipped
  (commit "skip UCX collision meshes"); no metric was computed before that fix.
- Every same-tile island pair on every tile OVERLAPS (v007 textured 3/3 pairs, v010 10/10; solid tiles
  all overlap too). Measured non-overlapping gaps: 0 in both versions -> N69 = 0/0 is an EMPTY check.
  The frozen harness printed `refuted`; by the contract's not-measured rule this is **not measured**:
  H69 (R1) = **inconclusive (not applicable)**; W1/W2 `not_exercised` (no pair >= 8 px exists).
- Overlap count does not calibrate either: rejected v007 3 < accepted v010 10 (wrong direction).
- Side finding: `export_meta.json` binds `SM_Nku_1.zip` to `package-vpm` and `export_npm_meta.json`
  binds `0000_Nku_1.zip` to `package-npm`. SM_Nku_1 is the VPM (UDIM, 4K tiles), not the NPM;
  #65-#68 called it NPM. The NPM is `0000_Nku_1_01.fbx` on the 2048 atlas `T_Nku_1_001_Main_d_1.png`.

### R2 amendment (frozen BEFORE running R2)

Same metric, same code path, on the real NPM: `0000_Nku_1_01.fbx` from `0000_Nku_1.zip`, tile px =
decoded side of `T_Nku_1_001_Main_d_1.png` next to the ZIP (pinned), floor 8 px (NPM, reg p.9 §5.4).
H69b: N69(NPM v007) > N69(NPM v010). Empty gap set -> inconclusive (now enforced in code:
`measured_gaps == 0` -> not applicable). Same witnesses W1/W2 on v010, same 3 fresh readbacks, same budget.
Expected: islands of different atlas cells are disjoint (gap >= 2 x pad of `npm_atlas.json`).

### R2 result (NPM `0000_Nku_1_01.fbx`, 2048 atlas) - wall 6.798 s, status complete, 3 fresh readbacks each

| | v007 (rejected, seams) | v010 (visual etalon) |
|---|---|---|
| islands on the atlas | 21 | 24 |
| island pairs / overlapping (same cell, stacked) / measured gaps | 210 / 123 / 87 | 276 / 130 / 146 |
| N69 (gap < 8 px) | 0, 0, 0 | 0, 0, 0 |
| min gap px | 51.699951 (spread 0) | 51.699951 (spread 0) |
| readback s (round 1) | 1.078 | 1.054 |

- Witness W1 (v010, closest pair 51.70 px moved to 4 px, 1 island changed): N69 0 -> 1 in all 3 rounds.
  W2 (moved to 9 px): N69 stays 0, min gap 9.0. The census is sensitive (in-memory witness only;
  native export-path perturbation **not measured**).
- **H69b refuted** on AC08: the rejected and the accepted NPM have identical min island gap
  (51.70 px = 6.5x the 8 px floor, 1.6x the 32 px gap of D278 16 px/side). The v007 seam rejection is
  not an island-spacing defect; the 8 px rule does not fire on the accepted control (no collateral).
- Overlap (stacked islands of one finish inside one cell) is by design on both and does not calibrate
  (123 < 130, wrong direction).

### Outcome

- H69 (R1, VPM SM_Nku_1): inconclusive - not applicable (all pairs overlap, empty gap set).
- H69b (R2, NPM 0000_Nku_1): refuted (0 = 0, stable, applicable, witness fires).
- Kept: nothing in production (OBSERVE). Would change (not applied): add a same-atlas island-gap
  census to V006 (`twinqa.npm_uv`) so the 8 px floor is measured between real islands, not only cell
  bands - useful as a regulation check, but it is NOT a seam signal and must not be sold as one.
- Correction for #65-#68 consumers: their "NPM" fixture `SM_Nku_1.zip` is the VPM package
  (`export_meta.json` -> `package-vpm`); their seam/texel numbers describe the VPM UDIM tiles.

Receipts: `atlas-island-gap-r69/receipt-r1.json` (VPM), `atlas-island-gap-r69/receipt.json` (NPM, R2).
Replay R2: `uv run --frozen python docs/research/atlas-island-gap-r69/replay.py tmp/r69-run --npm`.
