# Standing #129 — atlas alpha-bleed (transparent-RGB contamination) calibration (OBSERVE)

Card `t_729dea88` (no GitHub issue). Research only: no production check, threshold or delivered file changes.

## Why this target

- Focus (Artem 2026-11-27): a calibrated signal of texture/atlas defects he rejects, per element cell.
- NPM-vs-VPM render-diff on AC08 is already refuted twice (#125 `t_a2ac596e`, #128 `t_741df08c`): the rejected v007
  defect (seam pitch) lives in both profiles. #128 found no bound texture reject for KPP1 v004, Vatutino MAF or
  Staropetrovskiy MAF. Not repeated here.
- New fixture with a true **atlas-only** reject: Vatutino Flora #1146. Artem stopped run v003 at the visual gate
  (`jobs/VATUTINO-SITE/flora-route-a-v003.md`); the fix in run v004 was accepted ([D246], PR #1178). Measured
  cause (`flora-route-a-v004.md`, item 1): the source maps keep white RGB (252) under opacity 0; downscale,
  filtering and mipmaps mix it into the leaves, so planes go pale. v004 bleeds the plant colour into transparent
  pixels. The opacity atlas is byte-identical in both runs; only the diffuse RGB changed.
- No existing check measures this: `tools/derive/npm_atlas.py validate_export` checks padding geometry and edge
  extrusion of the OKS atlas; `twinqa.npm_uv` checks UVs inside cells; the Flora `atlas-check.json`
  reports opacity mismatch at cell resolution (0.0 % in both runs — blind to this defect).
- Owners checked: atlas/master binding #1947, Ground roadmap #1969, Staropetrovskiy library #1500, trainer #1917/#1928.
  None owns alpha bleed.

## Frozen contract (committed before any score)

- **Metric (one, frozen):** transparent-RGB contamination, `score.py` in
  [`autoresearch-atlas-alpha-bleed-harness/`](autoresearch-atlas-alpha-bleed-harness/). Mip levels k = 1..4
  (box 2^k blocks, un-premultiplied as a GPU mip chain); `d_k = Y(mean RGB) − Y(opacity-weighted RGB)`,
  Y = Rec.709 luma on sRGB 0..255. Cell score = max over k of p95 |d_k| over blocks whose centre is in the
  cell (`atlas-check.json` cells) and opacity coverage ≥ 0.5. Atlas score = worst cell. Signed mean reported.
- **H129:** rejected v003 NPM scores worse than accepted v004 NPM: (a) atlas score v003 ≥ 2 × v004 and
  v003 − v004 ≥ 5 luma units; (b) per cell v003 > v004 in ≥ 16/18 cells; (c) v003 atlas score above the accepted
  v004 VPM 4096 atlas too. All three → confirmed; any fails → refuted. Pinned-hash mismatch, round mismatch or a
  failed control → inconclusive.
- **Fixture:** `G:/Мой диск/AGR-evidence/1146-flora-star/run-v00{3,4}/atlas*/T_VATUTINO_Flora_{Diffuse,Opacity}.png`,
  SHA-256 pinned in `replay.py` (match each run's `SHA256SUMS.txt`); 18 species cells.
- **Controls (synthetic, in memory, on v004 NPM):** N0 identity → score equal to clean. P1 white (252) under
  every opacity-0 texel → score rises, signed mean > 0, expected same order as v003. P2 black → score rises,
  signed mean < 0. P3 invariance: white only on opacity-0 texels in aligned 16×16 blocks with no opacity > 0 →
  score exactly unchanged (the mip chain to level 4 never mixes them); report changed texel count, and also run P3
  on v003; 0 changed texels = `not_exercised`, not a pass.
- **Stability:** 3 rounds in one process, results must be byte-identical (computation determinism only; the inputs
  are delivered bytes, there is no render step to vary).
- **Budget / stop:** one metric variant, zero alternatives after the first score; 3 rounds; cap 20 min wall.
  No threshold tuning after scoring, no edits to Drive inputs, delivered packages or other cards' files, no DCC.
- **Not measured by design:** held-out admission (no other Artem-labelled opacity atlas pair found: MAF #524
  atlases have no opacity map; #1411 catalogue sheets are unlabelled previews), render-time specular part of the
  v003 defect, texel density, padding geometry.

Replay (needs the Drive folder):

```bash
python docs/research/autoresearch-atlas-alpha-bleed-harness/replay.py C:/x/ev_t_729dea88/r1
```

## Result — H129 refuted as frozen (OBSERVE, nothing kept)

**Итог (русский):** сигнал «грязного RGB под прозрачностью» правильно упорядочил отклонённый и принятый атлас
флоры Ватутино в **18 из 18** ячеек видов (v003 хуже v004 везде), и принятый ВПМ-атлас v004 тоже лучше v003.
Но замороженный порог «v003 ≥ 2 × v004» не выполнен: **61,29 против 43,83** единиц яркости, отношение **1,40**.
Гипотеза в замороженном виде **опровергнута**; порог задним числом не меняю. Побочная находка: принятый v004
всё ещё светлеет на mip-уровне 4 (+13,9 ед. в худшей ячейке 128) — подкраска прозрачных пикселей убрала
только около трети сдвига. Ничего не внедрено; пакеты и файлы на Drive не менялись. Нужен второй
размеченный Артёмом атлас с прозрачностью, прежде чем делать из этого проверку.

| State | Atlas score (p95 \|Δluma\|, worst cell) | Worst cell | Signed mean there | Cells above reference |
|---|---:|---|---:|---|
| v003 NPM, rejected | **61.2935** | 128 | +18.51 | 18/18 above v004 NPM |
| v004 NPM, accepted | **43.8285** | 128 | +13.93 | — |
| v004 VPM 4096, accepted | 41.6079 | 128 | +11.74 | v003 above it |

- Gates: (a) ratio 1.399 < 2.0 **fail** (difference 17.47 ≥ 5 passes); (b) 18/18 ≥ 16 pass; (c) pass.
- Two cells with real separation: 236 (v003 29.26 vs v004 3.03) and 242 (33.54 vs 5.12); in the other 16 cells
  v004 keeps ~70 % of v003's score. Per-cell, per-level numbers are in the receipt.
- **Clean** stability: 3 rounds byte-identical (`rounds_identical: true`), status `series_complete`, wall 42.36 s,
  pinned input SHA-256 matched before and after. Determinism of computation only.
- **Injected, synthetic** (v004 NPM, in memory): N0 = clean, 0 changed texels. P1 white under opacity 0:
  62.6372, 18/18 cells up, 2,727,930 changed texels, all signed means > 0 (reproduces the v003 level).
  P2 black: 84.4019, 18/18 up, signed means < 0 in 18/18. P3 invariance (opacity-0 texels in empty 16×16
  blocks): score unchanged in 18/18 cells with 2,140,928 changed texels on v004 and 2,139,225 on v003 —
  exercised, not empty.
- **Not measured:** held-out admission (0 eligible, not 0 failures), the render-time specular part of the v003
  defect, padding geometry, texel density. Why v004 keeps a residual is not investigated (one-variant budget).

Environment: Python 3.14.7, NumPy 2.5.3, Pillow 12.3.0 via `uv run --no-project --with numpy --with pillow`.
Receipt [`receipt_r129.json`](autoresearch-atlas-alpha-bleed-harness/receipt_r129.json) SHA-256
`18464ac0b68c1d8b20cf2d350e0a9525f478f71d8057a463328ebfbde7a1c858` (Git LF bytes; the CRLF working copy
written on Windows is `43bcf0ae…f7e9`). Replay is limited to machines with the
Drive folder; inputs are pinned by hash in `replay.py`.
