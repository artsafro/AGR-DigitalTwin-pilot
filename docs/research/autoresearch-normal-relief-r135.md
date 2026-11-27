# Autoresearch #135: same-camera Normal relief render-diff on the 4BK stylobate (#1326)

Card `t_33b1b86c`, OBSERVE mode. Nothing here changes production code, maps or delivered packages.

## Кратко (по-русски)

**Гипотеза H135 опровергнута (refuted), стабильно; ничего не оставлено, код production не менялся.**
Впервые проверена асимметричная пара с меткой Артёма по текстуре: стилобат 4BK (#1326), v045 с плоской
нормалью шва (отклонена, D295) против v096 с восстановленным рельефом (принята, D310); эталон — исходник, общий
для обоих. Рендер «только рельеф» с одних и тех же 5 ортокамер, энергия градиента по ячейкам 100 мм.
R1 оказался пересвечен (до 70 % пикселей в клипе) — исправлено поправкой A1 (свет 10 Вт, защита от клипа),
выбранной только по исходнику. A1: отклонённая 0.678 против принятой 0.639 — направление верное, но запас 0.038
меньше замороженного 0.10; на 4 из 5 видов версии совпадают до 1e-4, различие только на полосе шва.
Контрольные проверки прошли (N0 = 0, плоская нормаль на принятой даёт 2.38, половинная сила 0.93), 3 из 3
прогонов идентичны. Вывод: дефект D295 — полоса 10–20 мм, ячейка 100 мм его размывает. Следующий шаг (новая
карточка): считать только пиксели у шва (маска `agr_joint`).

## Why this target

Rounds #125/#128/#130/#132/#134 spent the AC08 NPM-vs-VPM render-diff: the AC08 rejection (seams) lives in
BOTH profiles, so a drift metric cannot see it; every round asked for an ASYMMETRIC, Artem-labelled texture
reject whose reference stays fixed. KPP1 v004, Vatutino MAF and Staropetrovskiy still have none (#1500 open,
#2020 rebuild). Not owned elsewhere: #2014 (joint-gate binding), #1947 (atlas/master), #1969 (Ground),
#559 (drawing checks); trainer parked.

The 4BK stylobate brick pilot (#1326) has exactly such a pair, never used by autoresearch:

| Label | Version | Authority | Maps |
|---|---|---|---|
| **rejected** | `cut-v045` (flat neutral joint Normal) | [D295] 2026-11-14 22:13: «a flat neutral joint Normal is not the pilot target»; the comparison file is `cut-v045/joint-normal-comparison-NOT-ACCEPTED.png` | `cut-v014/T_1326_Stylo_{Diffuse,Normal}.1001.png` |
| **accepted** | `normal-v096` (restored original relief, two UDIM) | [D310] 2026-11-15 10:12: visual direction of the restored Normal/joints confirmed | `normal-v092/T_1326_Stylo_{Diffuse,Normal}.{1001,1002}.png` |
| reference | delivered source (`1326_source_v001.blend`) | frozen source, read-only | `T_K3_StyloBrick_{Diffuse,Normal}.png` (intake rows 7, 9) |

The reference is identical for both labels, so the score difference can only come from the candidate. This is a
VPM texture-fidelity signal (Normal relief), the fallback focus «NPM/VPM texture and atlas quality»; it is not
an NPM atlas claim. D310 is a visual-direction acceptance, not technical QA (`passed` stays false everywhere).

## Frozen contract (before any measurement)

**Inputs** (all under `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/` unless noted; preflight
re-hashes every file and refuses on a mismatch; all equal the sealed `SHA256SUMS.txt` rows):

| Input | SHA-256 |
|---|---|
| `cut-v045/stylobate_cut_candidate_v045.blend` | `38979c31de1d23086d7b67078ca5b14343cd3db51c70cf4a89b3b0dd61a7bad6` |
| `normal-v096/stylobate_two_tiles_textured_v096.blend` | `070f292765d09756b2d82acffe7e5a5047e16ad9847e081c74bc1d66f02fea58` |
| `normal-v166/inputs/1326_source_v001.blend` | `e3fdb9193706059fd75bd42819280f140f512c6cc8a206e905b819fc3ce64a18` |
| `cut-v014/T_1326_Stylo_Diffuse.1001.png` | `46b271f2fec85802b9ba54a9fba379c91545794bbd5e3c92f6e57529f0a6192e` |
| `cut-v014/T_1326_Stylo_Normal.1001.png` | `5c5887d426b71c786e8f9784449e36a379a9e07ae451b08eb21a32bd87d2e428` |
| `normal-v092/T_1326_Stylo_Diffuse.1001.png` | `4f5b1cd7abd46bad3465bc127a56b62dcdd640dcdf16f61f7d9731c95e93af4e` |
| `normal-v092/T_1326_Stylo_Diffuse.1002.png` | `78d5a0e6809d49c4a22fff82d9c1132745ecfa27af5e4f96cc01fde503ca83fe` |
| `normal-v092/T_1326_Stylo_Normal.1001.png` | `a594651923ea7e9f2f82cc6d726f1afb2639a50598ba87055cec55e2cccba38a` |
| `normal-v092/T_1326_Stylo_Normal.1002.png` | `e191115f2062ef9340354a9b4093b50f3706fb87b9c9f0fa8af044f73202d138` |
| Desktop `63_4BK_vlad/build/textures/T_K3_StyloBrick_Diffuse.png` | `ff846d8e4f97eb9df4f9f1b069cacc5c3f67b86c323945e7c4d379f06e0a884d` |
| Desktop `63_4BK_vlad/build/textures/T_K3_StyloBrick_Normal.png` | `fee4b9729673835c524130eaf562a088d5560322c0e370feb89bb1a8f93b847b` |

Blender 5.1.2 headless (`--factory-startup`), blends opened read-only, never saved.

**Render (harness `render.py`, one Blender process per blend).** Only object `K3_StylobateWalls.001`
renders. Its ID1 slot (material name starting `ID1_Brick`) gets one uniform harness material for every
variant: Principled BSDF, roughness 0.8, Normal image (Non-Color, green flipped as in the #1326
`1326_lit_comparison_v045.py` driver) -> Normal Map node; base colour = Diffuse image (mode `full`) or constant
0.5 grey (mode `relief`). Every other slot = Holdout. UDIM maps load as tiled images. Cycles CPU, seed 0,
24 samples, no denoise, Standard view transform, transparent film, 600 x 600 px, world 0.12 grey. Orthographic
camera, `ortho_scale` 0.6 m (1 mm/px), placed at `target + dir * 3` looking at `target`; one grazing area light
per shot exactly as the v045 driver (energy 120, disk 0.3 m at `target + dir*0.4 + right*1.1 + (0,0,0.3)`).

Shots (5 element views, fixed before measuring): the four D310 review shots from `normal-v096/review-scene.json`
(`straight-wall`, `corner`, `floor-join`, `niche`: target and direction as recorded) and the D295 stripe
`joint-stripe` (target `[116.49096, 49.96561, 3.25667]`, direction `[0.86919, -0.49448, -0.00037]`).

**Metric (harness `score.py`).** Per shot, candidate render C vs source render S of the same mode. Mask =
alpha > 0.99 in both. Y = Rec.709 luminance of sRGB-decoded RGB. G = Sobel gradient magnitude of Y. Cells
100 x 100 px (100 mm, longer than one 83 mm course, so brick-phase shifts stay inside a cell); a cell is
eligible when >= 90 % of its pixels are masked in both. Cell value r = |ln((E_C + 1e-4) / (E_S + 1e-4))| with
E = mean G over masked pixels; also recorded signed. Shot score = p95 of r over eligible cells; shot with
< 4 eligible cells = **not measured**. Version score **V135 = max over measured shots** (relief mode).
`full` mode is recorded as a secondary number only, no decision.

**Hypothesis H135 (calibration).** In `relief` mode: V135(v045 rejected) - V135(v096 accepted) >= 0.10, AND
v045 > v096 on >= 4 of the measured shots (at least 4 measured), AND the signed median of v045 is negative
(relief lost, E_C < E_S) in the `joint-stripe` shot.

**Witnesses / controls (relief mode, same run, expected direction, bounds):**
- N0 accepted-free control: source vs source (source mesh + source maps rendered as the candidate in the same
  process) -> every shot score exactly 0 (determinism); bound <= 1e-9.
- P1 positive trigger: v096 with the Normal Map node disconnected (flat) -> V135 > V135(v096) + 0.10
  (fires on the accepted control; collateral check that the rule reacts to relief loss on an accepted mesh).
- P2 perturbation: v096 with Normal Map strength 0.5 -> V135(v096) <= V135(P2) <= V135(P1) + 0.05 (monotone).
- Invariance: per shot, count of eligible cells and of masked pixels per variant; a shot with 0 eligible cells
  for a variant is `not_exercised` and reported as not measured.

**Repeats / budget.** 3 fresh full runs (new Blender processes, new output dir each); paired spread of every
shot score across runs must be <= 1e-9 or the result is `inconclusive (unstable)`. One run is estimated at
<= 6 min; budget 3 runs + 1 retry, stop at 45 min wall. No new candidate is tried before calibration passes;
if calibration passes, at most ONE improvement candidate (none planned: OBSERVE only).

**Stop rule.** Stop after the 3 runs (or budget). Calibration fail = H135 refuted; no tuning of cell size,
light, shots or thresholds afterwards (that would be a new contract, new card).

**Forbidden.** Editing the blends, maps or any #1326 evidence; saving blends; touching other cards' files;
changing thresholds after seeing numbers; dropping shots after the fact; reporting not-measured as a result.

**Replay.** `uv run --frozen python docs/research/autoresearch-normal-relief-r135/run.py <new out dir>`
(Windows, Blender 5.1.2 at the default path, Drive mount `G:/Мой диск`, Artem's Desktop source maps).
Replay is limited to this PC (Desktop maps are outside git; hashes pinned above).

## Results

### R1 (frozen contract, commit `feeae31f`): H135 refuted as frozen, instrument INVALID (saturated)

`run.py C:/x/ev_t_33b1b86c/m1`, 3 fresh runs, wall 80.5 / 75.3 / 83.5 s, max paired spread 0.0, verdict identical.
Receipt `autoresearch-normal-relief-r135/receipt_r1.json` (SHA-256 `3d47aa7ca79f564194d9205320945416aaa321cd6c4fb207ab2decd26e4dd772`).

| relief mode | V135 | straight | corner | floor-join | niche | stripe |
|---|---:|---:|---:|---:|---:|---:|
| v045 rejected | 0.6719 | 0.6259 | 0.4808 | 0.5165 | 0.6719 | 0.6250 |
| v096 accepted | 0.6718 | 0.6259 | 0.4809 | 0.5165 | 0.6718 | 0.6489 |
| N0 / P1 / P2 | 0 / 8.273 / 7.140 | | | | | |

Checks: margin 0.00006 < 0.10 (fail), v045 worse on 2/5 (fail), stripe signed median +0.0703 (fail);
N0 = 0, P1 fires, P2 monotone (pass). Inspection after scoring: the `relief` renders are **saturated** — on the
source, 68.4 / 46.8 / 67.5 / 16.8 / 69.6 % of masked pixels are clipped (Y >= 0.999; p50 = 1.0 on three
shots), because the v045 driver's 120 W grazing light was tuned for the dark brick Diffuse, not for 0.5 grey.
Clipped faces have no gradient, so R1 measures joint edges only; this is an instrument defect, not evidence
about the labels. `full` mode (not clipped, 0-6.5 %) also gives v045 = v096 to 4 decimals (secondary, no decision).

### Amendment A1 (frozen before the second measurement, label-blind)

Only two changes, chosen on the SOURCE render alone (no candidate looked at):
1. `relief` light energy 120 -> **10** W (`run.py --a1 10`). Source-only probes: E=15 left niche 1.17 % clipped,
   E=30 16.4 % on corner; E=10 gives 0.00 % on all five shots (p99 0.31-0.69).
2. **Clip guard**: a shot whose masked pixels are > 1 % clipped in the candidate or the source is
   `not_measured_clipped` (it was silently scored in R1).

Metric, cells, shots, thresholds, witnesses and decision rule unchanged. A1 is the last repair on this
contract; if it refutes, the hypothesis is refuted and the next idea needs a new card.

### A1 result: H135 REFUTED (stable), witnesses pass

`run.py C:/x/ev_t_33b1b86c/a1 --a1 10`, 3 fresh runs, wall 70.3 / 70.0 / 71.1 s, max paired spread 0.0,
verdict identical. Clip fraction 0.0 on every relief shot of every variant (guard exercised, nothing dropped).
Receipt `autoresearch-normal-relief-r135/receipt_a1.json` (on disk SHA-256
`acd9351e776e97d90421e1644be7512d504d306455728cd114e6932e1e9285a8`; Git stores it with LF).

| relief mode, A1 | V135 | straight | corner | floor-join | niche | stripe |
|---|---:|---:|---:|---:|---:|---:|
| v045 rejected | **0.6777** | 0.5360 | 0.3277 | 0.5519 | 0.5402 | **0.6777** |
| v096 accepted | **0.6394** | 0.5361 | 0.3276 | 0.5519 | 0.5402 | **0.6394** |
| stripe signed median v045 / v096 | | | | | | +0.0394 / +0.0795 |
| N0 source vs source | 0 | 0 | 0 | 0 | 0 | 0 |
| P1 flat Normal on v096 | 2.3790 | 2.3205 | 2.3790 | 2.2534 | 1.7418 | 2.1589 |
| P2 half-strength on v096 | 0.9278 | 0.8345 | 0.8132 | 0.9262 | 0.9278 | 0.7681 |

Checks: margin +0.0384 < 0.10 (**fail**); v045 worse on 4/5 shots (pass, but three of those «wins» are
<= 1e-4, i.e. ties); stripe signed median +0.0394, not negative (**fail**). N0 = 0, P1 fires (+1.74),
P2 monotone (v096 <= 0.928 <= P1) — the instrument reacts to relief loss on an accepted mesh, so the miss is not
a dead instrument.

**What it means.** The rejected and accepted candidates are identical (to 1e-4) on four of five 0.6 m element
views; they differ only on the D295 joint stripe, in the right direction (+0.038) but below the frozen margin,
and both have MORE gradient energy than the source (positive signed medians), so «relief lost» is not visible at
100 mm cell scale. The D295 defect is a 10-20 mm joint bevel band: a 100 mm cell dilutes it ~5-10x, exactly the
«area-weighted scores dilute local defects» warning. Same-camera render-diff on whole cells is not a calibrated
signal for this defect class. Nothing is kept; no production code changed.

Not measured: NPM atlas padding / texel density (not in scope); any held-out (no second labelled Normal pair);
`full` mode (secondary: A1 full-mode numbers in the receipt, no decision).

Evidence (renders run1 of R1 and A1, both receipts): `G:/Мой диск/AGR-evidence/135-normal-relief/`
(`SHA256SUMS.txt` 128 rows, SHA-256 `177e7675a16dab6ee63f08e4e94c8c90d60d012d91d77a6ae6eb47f3e09e67f7`).

## Next (not run)

1. Joint-band localisation on the same pair (new card, new contract): render an `agr_joint` face-ID pass from
   the same cameras and score only pixels within 20 mm of a joint; expected v045 signed < 0 on the stripe.
2. Second labelled Normal pair for a held-out (another course-grid pilot or a Normal rebake Artem refused).
