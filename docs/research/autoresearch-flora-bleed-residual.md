# Standing #133 — Flora atlas bleed residual: edge-seeded push-pull (OBSERVE)

Card `t_b9389ba4` (no GitHub issue). Research only: no production check, threshold, builder or delivered file
changes. Contract frozen in its own commit before any measurement.

## Why this target

- Focus (Artem 2026-11-27): NPM atlas vs VPM render-diff as a calibrated texture/atlas signal. Labelled data for
  it is spent: AC08 refuted for v007 (#125, #128), confirmed for v006 only (#130), common-mode cancellation
  shown (#132); KPP1 v004, Vatutino MAF and Staropetrovskiy have no bound texture reject (#128 census, #1500 still
  open). The joint gate is owned by #2014; #131 next (2) is not executable (only AC08 has `vpm_textures.json`).
- Fallback focus (texture/atlas quality) with a calibrated metric: #129 transparent-RGB contamination ordered
  Artem's rejected Vatutino Flora v003 above accepted v004 in **18/18** cells. Its side finding is open:
  accepted v004 NPM still scores **43.83** (worst cell 128, signed mean **+13.93**, paler) although
  `bleed_rgb` fills every transparent pixel. #129 did not investigate why.
- Owners checked: #1947 atlas/master binding, #1969 Ground, #2014 joint gate, #1500 MAF library, #411 Flora star
  rebuild lane (no bleed work), trainer parked. Nobody owns the bleed residual.

## Hypothesis H133

`bleed_rgb` seeds its push-pull from every plant pixel (opacity ≥ 128), so the pale edge ring of the cut-out
(white-matte fringe kept inside the mask) is what spreads into the transparent pixels. Seeding from the plant
interior only (C1) lowers the residual.

## Frozen contract

- **Metric (unchanged #129):** `score.py` (copied byte-for-byte, git blob `91367d5d…120` checked at start):
  worst-cell max over mip levels 1..4 of p95 |Y(mean RGB) − Y(opacity-weighted RGB)|, blocks with coverage ≥ 0.5.
- **Chain:** `run-v003/maps` (cropped, unbled) → variant bleed → production `flora_route_a._atlas(run, "npm")`
  (2048, `tools/library/flora_atlas_from_scene.build_atlas`) in a new scratch dir → score.
- **Variants (one candidate, frozen):** B = production `bleed_rgb`; C1 = same push-pull, seeds = plant mask
  eroded by 2 px (5×5 MinFilter at map resolution), fallback to the full mask if erosion empties it (recorded).
  Both keep every plant pixel byte-equal (asserted) and never touch opacity.
- **Parity P0 (chain reproduces the delivered accepted atlas):** B maps pixel-equal to `run-v004/maps` in 18/18,
  B atlas diffuse and opacity pixel-equal to delivered `run-v004/atlas`. If P0 fails → **inconclusive**.
- **H133 confirmed** iff P0 holds and all of: (1) C1 atlas score ≤ B − 3.0 and ≤ 0.9 × B; (2) C1 ≤ B + 0.5
  in ≥ 16/18 cells; (3) C1 < delivered v003 in 18/18 cells (calibrated order kept); (4) C1 opacity atlas
  pixel-equal to B; (5) sensitivity kept: P1 (white under opacity 0) on C1 raises the score by ≥ 10, N0 equals
  clean, P3 leaves the score unchanged with > 0 changed texels. (1) or (2) fails with P0 and (5) good →
  **refuted**. Round mismatch, manifest mismatch or a failed control → **inconclusive**.
- **Diagnostic (observe, no gate; expected direction recorded before the run):** per species on `run-v004/maps`,
  mean luma of the plant edge ring (plant pixels within 2 px of a transparent pixel) vs the plant interior.
  Expected if H133 holds: ring brighter than interior in the majority of the 18 species.
- **Invariance / exercised counts:** per species changed-pixel counts vs v003 maps for B and C1, and C1 vs v004;
  a species with 0 changed pixels is `not_exercised`, never a pass.
- **Fixture and pinning:** `G:/Мой диск/AGR-evidence/1146-flora-star/run-v00{3,4}/{maps,atlas}/` — full-manifest
  preflight and postflight against each run's `SHA256SUMS.txt` (every `./maps/` and `./atlas/` row).
- **Stability:** 3 rounds in one process, full chain each round, receipt JSON must be byte-identical.
- **Budget / stop:** one candidate, zero alternatives after the first score; 3 rounds; cap 30 min wall. If the
  series cannot finish in the cap → **inconclusive** with the replay command; no shortened series.
- **Forbidden:** threshold or metric changes after scoring, edits to Drive inputs, delivered packages, the
  production `bleed_rgb` / atlas builder, or other cards' files; no DCC.
- **Not measured by design:** render-time look (no Blender), VPM 4096 atlas, held-out admission (no second
  Artem-labelled opacity atlas pair exists, #129), whether Artem sees any C1 difference. Even a confirmed H133
  is a metric improvement, not an accepted visual improvement.

Replay (needs the Drive folder; inputs hash-checked):

```bash
uv run --frozen python docs/research/autoresearch-flora-bleed-residual-harness/run.py C:/x/ev_t_b9389ba4/<new>
```

## Result — H133 confirmed (OBSERVE, nothing applied to production or delivered files)

**Итог (русский):** остаточное «посветление» принятого атласа флоры Ватутино v004 объяснено. Края вырезанных
растений в исходных картах светлые (белая кайма внутри маски): яркость кромки 2 px **≈180** против **≈110**
внутри, светлее в **18 из 18** видов. `bleed_rgb` заливает прозрачные пиксели цветом соседних пикселей
растения, то есть именно этой каймой. Вариант C1 — та же заливка, но цвет берётся из внутренней части растения
(маска, сжатая на 2 px); сами пиксели растения и прозрачность не меняются. Метрика #129 на атласе НПМ 2048:
**43,83 → 9,69** (худшая ячейка 128, знак +13,9 → −0,4), лучше или не хуже в **18/18** ячейках, порядок
«отклонённый v003 хуже» сохранён **18/18**. Цепочка воспроизводит принятый v004 побайтно (паритет). Это
улучшение метрики, а не принятое Артёмом визуальное улучшение: рендера и приёмки не было. Сама светлая кайма
видимых пикселей не исправлялась — это отдельная задача.

| State | Atlas score (worst cell) | Worst cell | Signed mean there |
|---|---:|---|---:|
| v003 NPM delivered, rejected | 61.2935 | 128 | +18.51 |
| v004 NPM delivered, accepted | 43.8285 | 128 | +13.93 |
| B = production `bleed_rgb` rebuilt | **43.8285** | 128 | +13.93 |
| C1 = interior-seeded bleed | **9.6865** | 128 | −0.40 |

- **P0 parity:** B maps differ from `run-v004/maps` in 0 pixels (18/18 species); B atlas differs from delivered
  v004 in 0 RGB and 0 opacity pixels.
- **Gates:** (1) 9.6865 ≤ 40.83 and ≤ 39.45 — pass; (2) C1 ≤ B + 0.5 in 18/18 cells (two near-floor A101 cells
  move 236: 3.03 → 3.39, 242: 5.12 → 3.06) — pass; (3) C1 < v003 in 18/18 — pass; (4) C1 opacity atlas = B
  (0 pixels differ) — pass; (5) controls on C1: N0 = 9.6865, 0 changed; P1 = 65.7772 (+56.1), 2,728,056
  changed texels, 18/18 cells up; P3 = 9.6865, 0/18 cells changed with 2,140,928 changed texels (exercised).
- **Exercised:** every species changes 553,255–3,063,881 transparent pixels vs v003 maps under both B and C1;
  C1 differs from v004 maps in all 18 species; erosion fallback used 0 times. No `not_exercised` input.
- **Diagnostic (expected direction confirmed):** ring luma > interior luma in 18/18 species; partial-opacity
  pixels in the maps 0 (all maps are binary 0/255 — the fringe is RGB, not alpha). The two A101 species
  (`pos09_242`, `pos16_236`) have the smallest ring excess (+25, +5) and were already the low cells in #129.
- **Clean stability:** 3 full-chain rounds byte-identical (round SHA-256 `efda449b…54ce`), status
  `series_complete`, wall **413.31 s** (cap 1800 s), manifest preflight and postflight 86/86 rows matched.
  Determinism of computation only.
- **Not measured:** render-time look and Artem's visual acceptance, VPM 4096 atlas, held-out (no second labelled
  opacity pair), the visible pale ring itself (C1 keeps plant pixels byte-equal by design).

What a follow-up PR would change (OBSERVE, not done here): seed `flora_route_a.bleed_rgb` from the plant mask
eroded by 2 px; regression = this harness's parity + the 43.83 → ≤ 40.83 bound on the pinned fixture; then a
Blender render pair for Artem before any re-delivery.

Evidence: `G:/Мой диск/AGR-evidence/133-flora-bleed-residual/` (C1 atlas PNGs + receipt, `SHA256SUMS.txt`).
Receipt [`receipt_r133.json`](autoresearch-flora-bleed-residual-harness/receipt_r133.json) SHA-256
`e2ac0fac3bd06a7bbf931d748702f66efbe1d12a43d62fb5915022a6fcddeab0` (Git LF bytes; Drive CRLF copy
`b98bf719…59db`). Environment: Python 3.14.7, NumPy 2.5.3, Pillow 12.3.0 (`uv run --frozen`). Replay is limited
to machines with the Drive folder; inputs are hash-checked by the full-manifest preflight.
