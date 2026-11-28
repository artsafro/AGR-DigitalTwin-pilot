# #153: wall-level view -> face assignment (side + within-side wall) on ELV

## Резюме (по-русски)

См. раздел «Round result» ниже; русское резюме дописывается после измерения.

## Frozen contract (committed before any scoring)

- **Why.** #139-#152 measured side-level identity (4 azimuths). Sokolniki STOP 04 (#2001, held out, not opened)
  is wall-level: an untitled partial view in a re-entrant corner must be tied to a *wall*, not just a side. #145
  listed "annex / re-entrant faces as separate candidates" and #143/#144 "within-face localisation" as not
  measured; #143 showed periodic bays make the best offset ambiguous. Idea measured here: periodicity only matters
  if the near-best offsets fall on *different walls* (depth planes); same-wall repeats do not change the answer.
- **H153.** With #149 D (unchanged) choosing the side, the wall = the depth plane under the best slide offset, and
  the gate W1 "answer only if every offset whose U is within `tau_loc` of the best maps to the same wall" gives
  wall-level assignments with zero confident wrong on clean full views and real fragments and at most one wrong on
  synthetic crops, while keeping at least 30 wall-correct synthetic crops (D had 40 side-correct).
- **Inputs (pinned).** ELV TC Sreda PDF `49c10527...9545` + Revit FBX `7ccf502d...b961` (paths and hashes in the
  #145 fixture at `640b3678`); #145 `run.py`/`fixture.json` at `640b3678`; #149 `score.py` and `run.py` at
  `94b74bcaeb2e00d6cdc1d486bf59ac7420bdf854` (git-pinned and SHA-256 recorded at stage time). New:
  `rays_wall.py` = #149 `rays_type.py` + `az###_depth` only. Blender 4.4 hash as #149. No Olimpijsky (D saturates
  there, #151), no OBR22/KPP1/AC08 (no Revit-type partition), no Sokolniki.
- **Walls (frozen).** Per azimuth, model columns are cropped exactly like #149. Column depth = median of first-hit
  `p . n` over hit pixels of the column. Wall planes = clusters of the sorted distinct column depths split where the
  gap exceeds `plane_gap_m = 1.0`; wall id of an interval = mode plane over its columns (ties -> lower id).
  A synthetic crop is `nontrivial` when its GT wall differs from the face's dominant wall (re-entrant / annex /
  recess); nontrivial rows are reported separately.
- **Localisation.** For the side picked by D, profile U(x) = max over the #149 vertical shifts at each horizontal
  offset x of the padded model (same `min_overlap 0.30`, `slack 0.6 m`). x* = first argmax. Near set
  N = {x : U(x) >= U(x*) - tau_loc}, `tau_loc = 0.05`.
  - **W0** (baseline, no gate): wall = wall of [x*-slack, x*-slack+w).
  - **W1** (candidate): W0 wall if all x in N give the same wall, else abstain `wall_ambiguous`.
- **Ground truth (independent of D).** Synthetic crops: GT model start column = crop offset (view tall-span left
  edge == model first-hit column); exercised only when the parent full view width matches the GT-side model width
  within 1.0 m, otherwise `not_exercised`. Real fragments p23 D-G (az 0) and p24 8-9 (az 270): GT model position of
  the two axes = their label x on reference full views p18 I-A (band 255-280 pt) and p18 1-10 (band 515-530 pt),
  converted by the full view scale and left edge; prediction = fragment's own axis labels (#145 bands) shifted by
  x*. A label lookup that is not unique -> that fragment's wall row `not_exercised`. Interval correct if the
  mean axis / start error <= 1.0 m; wall correct if side correct and wall id equal. p20 top-cut: wall only if D
  answers. Full views and mirrors: reported, wall = whole-face mode.
- **Outcome per row.** `correct` (side + wall right), `wrong` (side wrong, or side right and wall wrong),
  `abstain` (D abstains or W1 gate), `not_exercised` (no GT). Abstain rate reported per cohort.
- **Bounds (all must hold for CONFIRMED).** W1: full wall-wrong 0; real fragments wall-wrong 0; synthetic crops
  wall-wrong <= 1 and wall-correct >= 30; nontrivial exercised crops >= 5 with W1 wrong 0 on them (fewer than 5
  -> hypothesis `inconclusive`: re-entrant walls not measured). W1 gate must fire (abstain where W0 answers) on at
  least one row, else the gate is `not measured`. Expected direction: W1 wrong <= W0 wrong, W1 correct <= W0.
- **Parity.** Type labels byte-identical to `G:/Мой диск/AGR-evidence/149-view-face-material/r1b/types-1.npz`;
  D side outcomes row-identical to #149 r1b `run-1.json` (80 rows). Three fresh runs (ray cast + scoring), rows
  byte-identical; report median / min / max wall time.
- **Perturbations.** Mirror rows (from #149 cases) and a column-reversed model control per side are not keep
  criteria; mirror rows reported, reversed control only if exercised.
- **Budget / stop.** One candidate (W1), no retuning of `tau_loc`, `plane_gap_m` or tolerances after scoring.
  First run <= 400 s, series <= 1500 s; otherwise `inconclusive_budget_stop` with completed runs kept.
- **Forbidden.** Editing sources, delivered packages, other cards' files or production code; reading Sokolniki
  while #2001 is open; weakening thresholds; dropping rows.
- **Replay.** `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-wall/run.py
  C:/x/ar153/<fresh>` (pilot host with the mounted ELV inputs and #149 evidence for parity).

## Round result

(filled after measurement)
