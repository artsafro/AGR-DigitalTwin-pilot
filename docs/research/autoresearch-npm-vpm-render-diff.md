# Autoresearch #125: NPM atlas vs VPM render-diff (OBSERVE)

Card t_a2ac596e (standing #125), user decision Artem 2026-11-27 «Принимаю рекомендации» = option B:
switch from the parked trainer topic to the atlas fallback, calibrate first on accepted vs rejected packages,
a rejected version must score worse, per element / facade cell. OBSERVE only: nothing is applied to delivered work.

## Contract (frozen before the first measurement)

**Hypothesis H125.** The colour drift between the NPM package (atlas) and the VPM package (UDIM 4K) rendered
from the same orthographic FLAT-lit cameras separates Artem's rejected AC08 version from his accepted one:
`score(v007, rejected) > score(v010, accepted)` with a relative margin of at least 10 %.

**Metric** (one number per package, lower = closer NPM to VPM):
1. Inputs: the four FLAT facade renders `renders/{npm,vpm}_{south,east,north,west}.png` written by
   `jobs/TEC26-OKS/scripts/render_facades.py` (pixel colour = texture colour). The `iso` view is STUDIO-lit and excluded.
2. Mask: pixels with alpha >= 0.5 in BOTH renders. Pixels covered by only one render are counted separately
   as `silhouette_xor` (geometry drift, reported, not part of the score).
3. Common scale: px/m of each view is measured as mask width / bbox width along the view's right axis
   (bbox from `renders.json`); both images are box-resampled to **100 px/m** (about the NPM atlas density,
   92 px/m at PAD=16) so the intended NPM resolution loss is not counted as drift.
4. Per pixel: CIE76 ΔE in CIELAB (sRGB D65) between NPM and VPM.
5. Per facade cell: the facade is cut into 1 m x 1 m cells (100 x 100 px); a cell counts when >= 25 % masked.
6. Score = max over the 4 facades of the **p95 of the cell mean ΔE** (`facade_cell_p95`). Also reported:
   per-facade pixel mean / p95 ΔE, worst cell (index, metres from the facade's lower-left), cell count.

**Command** (replay, no DCC):
`uv run python docs/research/autoresearch-npm-vpm-render-diff-harness/render_diff.py --root "G:/Мой диск/AGR-evidence" --out <new json>`

**Fixture** (frozen, all on Google Drive, each PNG checked against that folder's `SHA256SUMS.txt` before scoring;
a mismatch aborts the run):

| Folder `559-tec26-oks-ac08-*` | Label | Source of label |
|---|---|---|
| `pilot-v007` | **rejected** | `AC08/PILOT_REPORT.md` line 5 «швы 0,60 м, отклонено Артёмом»; `jobs/TEC26-OKS/STATE.md` |
| `pilot-v010` | **accepted** (panel recipe) | `STATE.md`: Artem accepted the v008 panels; v010 = v009 layout + D169-D171 |
| `pilot`, `pilot-v006`, `pilot-v009` | unlabeled (superseded) | reported, not used for the verdict |

**Repeats.** The metric is deterministic: 3 runs, all 3 outputs must be byte-identical in the numbers
(median of 3 = the value). Paired spread is therefore 0 and is checked, not assumed.

**Positive trigger witnesses** (synthetic image perturbations of the accepted v010 NPM south render,
marked synthetic; they test the metric, not the pipeline). Expected direction: score rises above clean v010.
- `P1 wrong_colour_cell`: a 2 m x 2 m patch of the NPM render shifted by +40 in R (an ID with a wrong atlas cell).
  Bound: score >= clean + 5 ΔE.
- `P2 seam_line`: a 3 px dark (RGB 40) vertical line every 1.0 m on the NPM render (visible board/atlas seams).
  Bound: score > clean.
- `P3 uv_shift`: the NPM render content shifted by 0.25 m to the right inside the mask (UV offset).
  Bound: score > clean.
- `N0 identity`: VPM compared with itself. Bound: score == 0.

**Keep rule.** KEEP (as an OBSERVE signal for a later PR, no production change here) only if
(a) H125 holds with the 10 % margin, (b) 3/3 runs identical, (c) P1-P3 all rise and N0 == 0,
(d) the scale estimator reproduces the recorded 400 px/m of v009/v010 within 2 %.
Otherwise the result is `refuted` (a failed) or `inconclusive` (b-d failed).

**Stop rule.** One calibration round + the witnesses; at most 3 metric variants in total, each recorded with
its result; budget = this card run. No tuning of the cell size, scale or mask after seeing v007 vs v010 except
as a new, separately recorded variant.

**Forbidden.** Editing any delivered package or render on Drive; changing `render_facades.py`, `make_npm_atlas.py`,
`export_npm.py` or any checker; changing labels after seeing scores; files of other cards.

**Held-out etalon.** KPP1 v004, Vatutino MAF and Staropetrovskiy MAF have no paired NPM/VPM FLAT renders on Drive,
so a held-out check is **not measured** in this round (next target).

## Results

(appended after measurement)
