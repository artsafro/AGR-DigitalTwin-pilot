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

(filled after the run)
