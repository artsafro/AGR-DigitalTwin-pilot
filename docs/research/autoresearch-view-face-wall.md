# #153: wall-level view -> face assignment (side + within-side wall) on ELV

## Резюме (по-русски)

Гипотеза H153 (стена, а не только сторона: сторону выбирает D из #149, стену - плоскость глубины под лучшим
сдвигом, отказ если почти-лучшие сдвиги попадают на разные стены): **НЕ ОПРЕДЕЛЕНО**. На ELV каждая сторона
фактически одна стена; внутренних углов/пристроек в выборке всего 2 кадра, оба D отклонил; правило отказа ни разу
не сработало. Ошибок нет: полные фасады 6/0/1, синтетические фрагменты 39/0/23, реальный фрагмент p23 верно
(ошибка 0,97 м). Побочный результат: D указывает место фрагмента на фасаде с точностью до 1,2 м во всех 48
случаях - периодичности, сломавшей #143/#144, здесь нет. Для шага OKS: печатать сторону + интервал на фасаде;
стену во внутреннем углу пока не утверждать. Sokolniki не открывался (#2001 открыт).

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

**H153: INCONCLUSIVE** (re-entrant walls not exercised on ELV; the W1 gate never fired). Review readiness is
separate: harness, parity and receipt are complete.

- **Run.** Measured revision `a2c194f3e3da15e0e625fd1c1ac5df255a607e43`; three fresh runs (ray cast + scoring)
  63.897 / 63.921 / 63.937 s (median 63.921 s, spread 0.040 s), rows byte-identical (`6c7c97bb...` x3).
  Parity: type labels identical to #149 r1b `types-1.npz` on all 4 sides; D side outcomes identical to #149
  r1b `run-1.json` on 80/80 rows; profile max == `face_score` on every answered row.
- **Wall structure (frozen 1.0 m gap).** ELV is one wall per side for practical purposes: az 0 270/276 columns
  on the dominant plane, az 90 442/444, az 270 397/444; az 180 splits into 30 depth clusters (dominant 154/276
  columns) - the annex/recess side. Only **2** synthetic crops are `nontrivial` (GT wall != dominant): both
  `p19 A-I partial25/40@0.0`, both abstained by D. Bound "nontrivial exercised >= 5" not met -> inconclusive.
- **W0 = W1** (correct / wrong / abstain / not_exercised): full 6/0/1/0, synthetic crops 39/0/23/1, real
  fragments 1/0/0/1 (p23 D-G correct, axis error 0.97 m; p24 8-9 not exercised: label `9` found twice on the
  p18 reference band), top-cut 0/0/1, mirrors 2/1/4 (known #149 p19 10-1 mirror side error). All other bounds
  met (full 0 wrong, fragments 0 wrong, crops 0 wrong, 39 >= 30).
- **Gate.** Near sets (U within 0.05 of best) had 1-10 offsets on 50 of the 51 side-answered rows and 46 on one;
  every near set stayed on one wall, so W1 never abstained where W0 answered: **gate not measured**.
- **Secondary (not a keep criterion): within-side localisation by D is not periodic.** On 48 answered rows with
  GT, the best offset lands within 1.0 m of the GT start on 44 and within 1.2 m on all 48 (the 4 at 1.2 m are
  `p18/p21 I-A mirror` and `partial25@0.5`; the GT itself carries the +-0.6 m full-view alignment slack). This
  contrasts with the edge cues (#143/#144), where correct and wrong offsets tied.
- **Not measured:** re-entrant / annex walls as separate answers (2 rows, both D-abstained), the W1 gate,
  p24 8-9 localisation, column-reversed model control, any second pair, Sokolniki (#2001 still open, not opened).

**Recommendation for the shared OKS step 'view<->face map sheet'.** Keep the side answer from D with its
abstain rule, and add per answered view the D best offset as a bay interval (print "covers model u = a..b m,
+-1.2 m" with the depth plane under it). Do not yet claim wall identity in re-entrant corners: on the only
eligible pair those walls were not exercised. The W1 same-wall check costs nothing and should stay as a
reported field, not a trusted gate, until a pair with >= 5 real re-entrant views is measured.

Replay artifacts: [receipt](autoresearch-view-face-wall/receipt.json); all run outputs, label/depth npz and
Blender logs under `G:/Мой диск/AGR-evidence/153-view-face-wall/` + `SHA256SUMS.txt` (15 files, verified).
ELV inputs are the #145 sealed copies (hashes in the pinned #145 fixture). Replay limited to the pilot host.
