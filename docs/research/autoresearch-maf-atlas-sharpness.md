# Autoresearch #75: MAF atlas cell effective resolution (OBSERVE)

Card t_4c80effc, branch `research/autoresearch-standing-75`, base `origin/main` 01e48513.
Frozen before any measurement. OBSERVE only: nothing in `library/`, `tools/` or on Drive changes.

## Краткое содержание (RU)

Цель: пиксельный сигнал «текстура ячейки атласа размыта/апскейлена» на первом НЕ-AC08 объекте с
меткой Артёма. Пара: атлас МАФ 512 v007 r1 («в атласе wood log только не очень» — отклонён ID 18,
остальные ячейки приняты) и r2 («спил норм» — принят). Метрика R75 считается только по пикселям PNG,
без метаданных. Гипотеза: отклонённая ячейка r1 ID 18 получает худший R75, чем каждая принятая
текстурная ячейка. Однотонные ID не измеряются (у них нет требования к текселю, Артём 2026-11-17).

## Fixture (pinned)

| input | location | SHA-256 |
|---|---|---|
| r1 atlas PNG (rejected ID 18) | `G:/Мой диск/AGR-assets/maf/atlas/v007/T_MAF_Atlas_v007_GroundEl_d_512.png` | `55e654a2e04ce2e828cd1f7a1f585d54263a01050f00cb60d5d3bab4f6d0cf6d` |
| r2 atlas PNG (accepted) | `G:/Мой диск/AGR-assets/maf/atlas/v007/T_MAF_Atlas_v007_GroundEl_d_512_r2.png` | `a30dac001483b42d99afee0fc315e58ddc4ba1ce10d7bb58e8565017e4b3f340` |
| r1 layout | `git show 88535418:library/maf/atlas_512_v007.json` | git object, pinned by commit |
| r2 layout | `library/maf/atlas_512_v007.json` at 01e48513 | git object, pinned by commit |

Labels: `library/maf/atlas_512_v007.json` `acceptance.quotes` ([D240]): r1 = all cells accepted except
ID 18 `wood_log_end`; r2 = accepted. Replay preflight refuses on any hash mismatch.

Scope: `kind == "patterned"` cells only (IDs 15, 33, 18). Rejected: r1 ID 18. Accepted: r1 ID 15,
r1 ID 33, r2 ID 15, r2 ID 33, r2 ID 18 (ID 15/33 crops are byte-identical sources in both revisions;
reported, still exercised). Solid cells: `not_exercised` by rule (flat, no texel requirement).

## Metric (one number per cell)

Crop = `cells[].content_px` [x, y, w, h], inset 2 px; luma Y = 0.299 R + 0.587 G + 0.114 B (float64).
`S(img)` = mean |4-neighbour Laplacian| on the interior / mean |Y - mean Y|.
`reup(img, f)` = PIL LANCZOS resize to round(n / f), then LANCZOS back to n (production kernel,
`tools/materials/atlas_maf.py:548`), applied per RGB channel image.

**Primary R75(cell) = S(reup(cell, 1.1)) / S(cell)** — retention after one more 1.1x round trip.
An already-upscaled (soft) cell loses little, so higher R75 = worse. Self-normalised per cell, so the
content of different cells (rings vs grain) is not compared directly.
Secondary (diagnostic, decides nothing): S75 = S(cell) (lower = softer) and the recorded
metadata ratio source_px / content_px from the layout JSON.

## Hypothesis and decision (frozen)

H75: R75(r1 ID 18) > max R75 over the 5 accepted patterned cells, in every round.
- confirmed: holds in 3/3 fresh rounds, paired D75 = R75(r1 ID18) - R75(r2 ID18) >= 0.01, spread
  of D75 across rounds <= 1e-9, and witness W1 fires within bounds.
- refuted: R75(r1 ID18) <= R75(r2 ID18).
- inconclusive: anything else (ordering only vs r2, below the margin, witness does not fire, bug).

## Witnesses and perturbations (expected direction, per-variant bounds)

On accepted r2 ID 18 (positive trigger) and on rejected r1 ID 18 (exercise):
- W1 positive trigger: cell := reup(cell, 1.1) (simulates the r1 1.1x upscale). Expected R75 up,
  bound ΔR75 >= +0.01 on r2 ID 18.
- W2: cell := reup(cell, 2.0). Expected R75 up, bound ΔR75 >= +0.05 on r2 ID 18.
- P1 brightness +8 (clipped 0..255): invariance, |ΔR75| <= 0.01.
- P2 contrast x0.8 around the cell mean (rounded uint8): invariance, |ΔR75| <= 0.02.
Per input the replay records the changed pixel count of each perturbed state; 0 changed = `not_exercised`.

Accepted control where the rule is exercised: all 5 accepted patterned cells (collateral = number of
accepted cells with R75 >= R75(r1 ID 18); expected 0). No threshold or gate is proposed.

## Budget, stop rule, forbidden shortcuts

- 3 fresh rounds, each a separate Python process (`replay.py` spawns them), median and range reported.
  Expected wall < 30 s. Confirm-vs-new budget: R1 frozen; at most one amended R2 if R1 is
  inconclusive for a bug, amendment written here before running. Stop: after R2 or 45 min card time.
- Forbidden: editing the atlas PNGs/JSON or any delivered package, changing the kernel after seeing
  scores, dropping accepted cells, choosing the inset/factor post hoc, touching other cards' files.
- Parity: crops are read from the hash-checked PNGs; layout boxes from git objects; cell
  content_px must lie inside the 512 atlas (refuse otherwise).

## Replay

`uv run --frozen python docs/research/maf-atlas-sharpness-r75/replay.py tmp/r75-NEW`
Needs Drive read access to the two PNGs (replay limited without Drive). Receipt:
`docs/research/maf-atlas-sharpness-r75/receipt.json`.

## Round log

(filled after measurement)
