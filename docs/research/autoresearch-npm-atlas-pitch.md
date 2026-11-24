# Standing #73 — NPM atlas joint pitch (OBSERVE)

Card t_b8ec6b71, branch `research/autoresearch-standing-73`, base `origin/main` 36d185ce. Continues #72 (t_82ef7ef0)
next target 1: the same source-bound pitch census, but on the delivered **NPM** 2048 atlas instead of the VPM 4K tiles.
Focus: NPM/VPM texture and atlas quality (Artem 2026-11-24).

## Краткий итог (RU)

См. раздел «Round log» ниже; заполняется только после замера. Контракт ниже заморожен до первого запуска.

## Frozen contract (before any measurement)

Confirm-vs-new budget: two prior loaders reused unchanged (#71 `load`/`crop` at `b105d8bc`, `runs` of
`jobs/TEC26-OKS/scripts/joint_count.py` at base `4288c54d`) and the #72 `pitch` census copied verbatim (rows at 25/50/75 %,
dark = `< 0.8 * row median` of summed RGB, complete runs only, >= 3 per row, median pooled adjacent centre gap). One new
diagnostic only, exactly three fresh paired rounds, no second candidate.

Fixture: TEC26 AC08 `T_Nku_1_001_Main_d_1.png` (2048 px NPM atlas) + `npm_atlas.json` + `SM_Nku_1.zip` from Drive
`G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-<v>/`, v007 (Artem rejected: 600 mm panel pitch / seams) and v010
(visually accepted; not a package QA pass). The #71 hash preflight pins all three files per label (SHA-256 in #71
`PINS`, equal to each folder's `SHA256SUMS.txt`). External atlas = embedded FBX Video bytes for v007/v010 (#70 receipt
`atlas_embedded_byte_parity`); not re-proven here. Target finishes and source periods: `jobs/TEC26-OKS/AC08/vpm_textures.json`
at base `4288c54d` (`PanelVJ30_RAL5015` P 0.195316833 m, `PanelVJ12_RAL5015` P 0.186277667 m, S 4.096 m).
Region binding: v010 regions of the same names; v007 has one shared patterned finish `PanelVJ_RAL5015` (udim 1001, region
origin u0 0.0029296875) used for both targets, same rule as #72 R2; `Panel_RAL5015` (solid, `px_per_m` null) excluded.
Every bound region must have `px_per_m` 96.9 and the 397 px region of a 2048 atlas.

Score E73 = max over the two targets of `|observed_px / expected_px - 1|`, `expected_px = P * region / S`
(18.93 / 18.05 px). Command: `uv run --frozen python docs/research/npm-atlas-pitch-r73/replay.py tmp/r73-NEW`
(writes `receipt.json`). Each round re-reads and re-hashes the Drive bytes and decodes the PNG again (no frozen dump).

Hypothesis H73: the #72 VPM ordering survives on the NPM atlas. Expected: accepted v010 E73 <= 0.05 (wider than #72's
0.03: 397 px region, LANCZOS-resampled 1.5 px joints, integer-ish centres), rejected v007 E73 >= 1.0 (600 mm -> 58.2 px
vs 18.9). Confirmed: those bounds on the medians, every paired difference > 0, median paired difference >= 0.95,
paired range <= 0.01, witnesses valid. Refuted: complete series with valid witnesses that contradicts ordering/bounds.
Otherwise (preflight, unreadable row, < 3 complete runs, budget stop, witness out of bound) inconclusive / not measured.

Positive trigger witness (in memory, both labels): region columns `2*x % 397` (half pitch). Accepted control must cross
its bound: v010 E73 in [0.45, 0.55]; rejected v007 expected in [0.50, 0.70] (29.1 px vs 18.05 -> ~0.61, not a gate).
Illumination control: +8 RGB levels with saturation; record changed pixels per region; |E change| <= 0.01.
Clean score is recomputed after both variants and must be identical (no mutation). Unchanged inputs/regions are labelled
`not_exercised` and reported as not measured.

Budget: core 60 s; after the first paired round stop `budget_stop` if it took > 20 s; never start a round after 60 s.
Wall time and status recorded separately. A budget stop is inconclusive for this run, not a hypothesis result.

Keep threshold: none (OBSERVE). Even if confirmed: candidate diagnostic only, no gate, no production change, no PR to
delivery code. Forbidden: RGB tuning, image alignment, dynamic threshold fitting, tolerance relaxation, test deselection,
new exports, edits to delivered bytes or to other cards' files.

Not measured (no byte-bound label pair on Drive for this lane): KPP1 v004, Vatutino MAF, Staropetrovskiy MAF. Not this
lane: G22 #1649, Staropetrovskiy #1500, KPP1 #1817/#1818, MAF numbering #1809, closed form research. Joint width,
visibility, UV placement and renders are not covered.

## Amendment A1 (before any real measurement, no score read)

The frozen half-pitch witness `2*x % 397` drops every second joint when joints are 1 px wide: synthetic 397 px region with
1 px joints at pitch 19 -> RED (`test_half_pitch_witness_on_397_region_halves_period`, 1 failed / 4 passed). NPM joints are
~1.5 px after LANCZOS, so the copied #72 witness would fail for a resolution reason, not a metric reason. Replaced by a 2:1
cyclic box downsample of columns (mean of columns 2x and 2x+1 mod 397); test GREEN 5/5. Bounds, metric, thresholds and
the brightness control are unchanged.

## Round log

- R1 (only round set, after A1): `uv run --frozen python docs/research/npm-atlas-pitch-r73/replay.py tmp/r73-run1`,
  status `complete`, three fresh paired rounds 0.732 / 0.624 / 0.645 s, total wall 2.001 s, all witnesses valid.
  v007 shared `PanelVJ_RAL5015` region: 58.0 px for both targets (6 complete runs per row) -> E73 2.212452.
  v010: VJ30 19.0 px vs 18.931 expected (20 runs/row), VJ12 18.0 px vs 18.055 (21 runs/row) -> E73 0.003652.
  Median paired difference +2.208799, range 0. **H73 confirmed (OBSERVE), AC08 NPM only.**
- Half-pitch witness: v010 0.501516 (in [0.45, 0.55], 150,268 / 150,873 px changed), v007 0.606226 (in [0.50, 0.70],
  147,860 px changed). Brightness +8: 157,609 px changed per region, E73 unchanged on both labels. Clean score identical
  after both variants. Excluded `Panel_RAL5015` / solid regions: not measured.
- Receipt: `npm-atlas-pitch-r73/receipt.json` (copied from `tmp/r73-run1`, SHA-256
  1149562de0a28fc2b8a54fea8a0d6486aa7214e01c93fb3bf358fa89f222c47b). Candidate SHA-256 7ffd8a6c…bdef77 (replay.py at 4c3c02d0).

Interpretation and limits: the NPM atlas is regenerated from the same spec as the VPM tile (`make_npm_atlas.py:43-45`),
so E73 repeats #72 (2.2125 vs 2.2210) at 397 px; it is not independent evidence of a separate NPM defect. Resolution is
~1 px of a ~19 px pitch (VJ30/VJ12 differ by 0.9 px), so E73 can tell 600 mm from ~190 mm but not small pitch drift.
One labelled pair only; KPP1 v004, Vatutino, Staropetrovskiy not measured. No keep, no gate, no production change.

## Краткий итог (RU, финал)

Шаг вертикальных швов в NPM-атласе AC08 (регион 397 px) совпал с выводом #72 по VPM: отклонённая v007 — шаг 58 px
(600 мм) против нужных 18,9/18,1 px, E73 = 2,21; принятая v010 — 19/18 px, E73 = 0,0037. Три свежих прогона, разброс 0,
2 с. Гипотеза H73 подтверждена только на этой паре AC08. Это та же ошибка дизайна текстуры, что и в VPM (NPM строится из
той же спецификации), а не отдельный дефект NPM. Ничего не применено, PR в продакшен нет.
