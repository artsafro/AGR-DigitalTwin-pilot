# Standing #128 — same-camera NPM/VPM cell-diff calibration (OBSERVE)

## Frozen contract (before scoring)

Recheck #125 variant 2, unchanged, on **fresh** native FLAT renders from the two AC08 archive pairs. #125 mixed historical camera generations (v007 predates fixed 400 px/m); #127 showed the unchanged renderer can re-render both, but measured the D171 joint-count gate, not this cell-diff. No proposed production change. The other named jobs enter only if both labels, byte-bound NPM/VPM archives, and the texture reason are established for the same scope; report eligibility separately, never add a synthetic rejection to that denominator.

- H128: on the same renderer/camera policy, rejected v007 must score worse than the v010 visual/panel reference by ≥10%, in each of three independently rendered pairs. Metric: unchanged #125 V2 max across four facades of p95 1 m cell mean CIE76 ΔE, common opacity mask (red datum excluded), 100 px/m evaluation. Report per-view scores, worst cells, median of paired rejected-minus-reference deltas and range. A complete, parity-valid reverse ordering refutes the hypothesis for AC08 and the proposed all-rejections calibration; a missing held-out pair is not measured.
- Fixture: `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v{007,010}/` exact `0000_Nku_1.zip` and `SM_Nku_1.zip` hashes from #127 receipt at `34b5174834a21e1ed516a02439bcd1eec832404b`. Labels: #559 comments 6341991856 and 6345392389; v010 means visual/panel reference, not unconditional delivery approval. Renderer, VPM preview UV owner and spec from `9269c354ad4b2bcb8af03d2308297edfff25f079`. Scorer source from `9e582966c1f454f0924a70a8a386d060ef6a7ce5`, `--variant 2` semantics. Blender 5.1 executable SHA-256 `1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5`. Require exact paired camera fields per view within each version, fresh PNG parity across rounds per version, and pre/postflight archive hashes. Does not require v007 geometry to be byte-identical to v010. Compare clean v010 to #125 V2 separately; report any drift, not a repair.
- Controls: use existing #125 P1 (wrong-colour patch in NPM south), P2 (dark stripes in NPM south), P3 (NPM south UV image shift) on fresh renders in both labels, controlled at the render only. Per label/state count changed RGB pixels; require all three >0, unchanged alpha and VPM pixels; N0 identity ≡0 on each label. Require v010 P1 ≥ clean +5 ΔE; P2/P3 must increase v010 score. Rejected-side delta reported, not an independent rejection. No invariance claim for no-op states. Padding, texel density and shared-profile seam correctness are not measured by these image perturbations.
- Budget: three fresh confirmation pairs; zero new metric candidates. Cap 300 s and first complete pair ≤90 s with ≥2 × first-pair time +15 s remaining; otherwise stop, record completed pairs and wall, no median/KEEP. No edit to delivered packages, other cards, checks or tolerances; no cached substitution or shortened series. No Max. If parity or control fails, inconclusive rather than relaxing it. No production adoption even on pass without independent held-out calibration.

Replay from the branch using Windows Blender and Drive (limited to those with the same inputs):

```bash
python docs/research/autoresearch-npm-vpm-render-diff-r128/replay.py tmp/r128-NEW
```

## Result — refuted (OBSERVE, no PR)

**Итог:** одинаковая камера не исправила обратную сортировку. Во всех трёх свежих прогонах отклонённый AC08 v007 получил **0,8974 ΔE**, принятый визуальный эталон v010 — **1,8381 ΔE**. Так на каждом из четырёх фасадов. Отдельно: наблюдатель реагирует на дефекты, внесённые только в кадр НПМ; он не обнаружил ошибку шага швов, общую для НПМ и ВПМ. Не использовать для приёмки; производственные файлы и пакеты не менялись.

| AC08 | South | East | North | West | Max cell p95 |
|---|---:|---:|---:|---:|---:|
| v007, rejected | 0.8877 | 0.7806 | 0.8974 | 0.7962 | **0.8974** |
| v010, visual reference | 1.6980 | 1.8340 | 1.7608 | 1.8381 | **1.8381** |

**Clean:** median paired delta −0.9407 ΔE; range 0.0000; #125 historical v007 → fresh +0.0896, v010 unchanged. Status `series_complete`, 129.30 s wall, pair times 37.02 / 40.58 / 50.01 s. Four ZIPs and all staging files passed pre/postflight. Each NPM view and corresponding VPM view had identical camera fields. The 20 decoded RGBA image hashes matched across all three rounds and matched the two shared #127 reference directories (`G:/Мой диск/AGR-evidence/127-ac08-joint-gate/pilot-v{007,010}/renders_r127/`). Fresh raw PNG hashes differ: a checked sample contained different Blender `Date` / `RenderTime` text chunks. Pixel parity, not container-byte equality, is the stated render evidence. All clean and control score rows were identical across the three rounds. Per-facade worst cells, coordinates and camera fields are in the signed-by-hash receipt.

**Injected, synthetic:** N0 = 0 on both sides with equal alpha and unmodified VPM. For P1/P2/P3 respectively:

| AC08 | Scores | Changed south NPM RGB pixels |
|---|---|---|
| v007 | 5.8488 / 1.2353 / 32.4502 | 635,552 / 33,108 / 2,734,092 |
| v010 | 8.9620 / 2.0446 / 15.9828 | 635,685 / 33,108 / 2,797,033 |

All P1–P3 states preserved alpha and VPM pixels; east/north/west have zero changed NPM RGB pixels by design and are `not_exercised` for the perturbation. v010 P1 exceeded clean by 7.1239 ΔE (>5); both other scores increased. This is image-response evidence, not a native mutation or a user rejection. D171 joint counts (#127) are a separate measurement; no padding, texel-density or same-defect-on-both-profiles intervention was run.

**Not measured — held-out admission (0/3 eligible, not 0/3 failures):**

| Case | Read-only admission evidence and missing side |
|---|---|
| KPP1 v004 | #1817 / D382 binds `draft-b25-r1` NPM and VPM. The etalon ledger's explicit rejection is the step-3 master with a 110 mm NW corner step, not a same-scope texture-atlas reject of two exports. Earlier package drafts exist but were not promoted to user rejects. |
| Vatutino MAF / Verona | A4 row 1 was accepted as a visual pattern; A3 had seam geometry superseded by textured A4. The generator report keeps library/visual acceptance distinct from NPM/VPM delivery QA; the C:/x generator root is no longer readable here. #1499 is closed unless the customer asks. No bound before/after pair of both profile exports was found. |
| Staropetrovskiy MAF | The local November 20 folder has both site profiles; November 24 has only VPM. The November 12 v003 showcase review names an actual material correction (T02 seat side → cream), but does not bind that label to exact paired package bytes; the v008 planter note is not acceptance of those bytes. #1500 awaits Artem's reviewed library set/retro. T02 is a candidate for an element-scoped holdout only after that binding. |

Measured adapter commit `1cc2577db810c34857c38adcdc7c13b25fe0d656`; Python 3.14.9 / NumPy 2.5.4 / Pillow 13.0.0. [Raw receipt](autoresearch-npm-vpm-render-diff-r128/receipt.json) SHA-256 `0bf110ec48de754a0021863e0e93912c79289593b80082d88fedd6d2edac53f4`; [decoded readback](autoresearch-npm-vpm-render-diff-r128/decoded-parity.json) SHA-256 `14643826df4694e59cc045a1f695f1549877a0d989b32f3fc9d766ba9a8f868b`. For decoded readback, hash `Image.open(path).convert("RGBA").tobytes()` with SHA-256 for each sorted `*.png` in `tmp/r128-NEW/r{1,2,3}-pilot-v{007,010}/`. Native replay always requires the pinned inputs; partial series under load stay inconclusive. No new raster files needed in Git: shared #127 raster content matches the measured fresh pixels.
