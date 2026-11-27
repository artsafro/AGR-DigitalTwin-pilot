# Standing #130 — AC08 v006 holdout (OBSERVE)

## Frozen contract

H130: the unchanged #128 score separates a second AC08 texture rejection (v006: horizontal joints on panels, [#559 rejection](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/559#issuecomment-6341401650)) from [v010, the accepted visual reference](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/559#issuecomment-6345392389). This is a different rejection of the same building, not independent building validation. #128 had already refuted a universal calibration claim on the shared wrong-pitch error in v007. This round cannot reverse that finding.

- Metric: unchanged #125 V2 as run by #128: maximum across four facades of p95 of 1 m cell mean CIE76 ΔE, common alpha mask excluding the datum, evaluation at 100 px/m. Same paired FLAT camera for both profiles, 400 px/m native. Report each facade and median/range of three fresh rejected-minus-reference pairs. Confirm H130 only if rejection is ≥10% worse on the primary score in each pair and strictly worse on every facade in each pair; otherwise refute after a complete parity-valid series. Report v010 parity vs #128, and decoded RGBA parity across all three fresh rounds. Failed parity, failed required controls, or partial series are inconclusive.
- Budget: three fresh confirmation pairs, zero new metric candidates. Existing adapter cap 300 s, first pair ≤90 s with ≥2 × first-pair wall +15 s remaining. No shortened series, cached substitution, package edits, removed checks, relaxed tolerances, other cards' files, Max, or production KEEP. Report wall/status separately from H130. Reuse unchanged production renderer/scorer via #128; only the manifest selecting versions changes.
- Positive witness and exercised accepted control, both labels: unchanged #128 P1 wrong-colour patch, P2 dark stripes and P3 horizontal image shift, NPM south only; require changed RGB >0 for each, exact alpha and VPM parity, and v010 P1 ≥ clean +5 ΔE, P2/P3 > clean. Rejected-side response is diagnostic. N0 requires zero score (NPM copied from VPM) and preserved alpha/VPM. East/north/west are `not_exercised` for P1–P3. No native UV, physical padding, density or same-mutation-on-both-profiles witness in this series.
- Inputs: `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v{006,010}/`, manifest in the replay adapter (both archives per label, verified against adjacent SHA256SUMS.txt). #128 replay pinned at `5c15100ee5631e2f5d75e697e14e1977a6361f3d`, and the upstream renderer/spec/UV owner, scorer and Blender binary verified by that adapter. All archive and staged inputs checked before/after. This is limited replay (requires the exact Drive ZIPs and Blender 5.1 on Windows). Python 3.14.9, NumPy 2.5.4, Pillow 13.0.0.
- Cross-job admission is separate: require same element/facade and both profile exports, byte-bound to both a texture-specific rejection and an accepted reference. Do not substitute a geometry rejection, design decision for a library row, or a one-profile delivery.

```bash
python docs/research/autoresearch-npm-vpm-render-diff-r130/replay.py tmp/r130-NEW
```

A clone without the historical objects must first fetch the public-to-project refs `research/autoresearch-standing-125`, `research/autoresearch-standing-127` and `research/autoresearch-standing-128` from `origin`; measurement uses the pinned commits, not the current tips. A load-triggered budget stop remains inconclusive; replay in another new output directory.

## Result — H130 confirmed for AC08 v006 vs v010 only; OBSERVE, no production change

**Итог:** на трёх свежих парах кадров отклонённый AC08 v006 получил **2,0783 ΔE** против **1,8381 ΔE** у визуального эталона v010 (**+13,07%**); направление верное на всех четырёх фасадах. Это подтверждает сравнение этих двух версий, но не доказывает, что метрика измеряет горизонтальные швы: она измеряет расхождение между НПМ и ВПМ. Для другого отказа того же AC08 (v007, неверный шаг швов в обоих профилях) #128 уже получил обратный порядок. Приёмочный порог не предлагаем.

| Version | South | East | North | West | Max of facade p95 |
|---|---:|---:|---:|---:|---:|
| v006 rejected | 2.0597 | 1.8840 | 2.0783 | 1.8842 | 2.0783 |
| v010 visual reference | 1.6980 | 1.8340 | 1.7608 | 1.8381 | 1.8381 |

**Clean.** Median paired delta +0.2402 ΔE, spread 0.0000; all three pairs individually clear the frozen 10% bound. `series_complete` (67.93 s wall, pairs 23.28 / 22.89 / 21.02 s). Camera records equal across profiles, versions and repetitions; common-mask silhouette XOR zero on all eight labelled facade rows. All four original ZIP hashes and staged-file hashes match pre/postflight. All 20 decoded RGBA digests (10 per version, including unscored iso views) match across rounds; all 10 v010 digests and all clean v010 facade rows match #128. Raw PNG hashing is logged separately; Blender metadata is not pixel evidence. Worst-cell coordinates and coverage are in the receipt.

**Injected, synthetic.** N0 = 0 in both labels; preserved alpha/VPM throughout. P1/P2/P3 in NPM south (changed RGB counts and scores identical across rounds):

| Version | Scores (ΔE) | Changed pixels |
|---|---|---|
| v006 | 6.0405 / 2.3965 / 32.7451 | 635,552 / 33,108 / 2,731,554 |
| v010 | 8.9620 / 2.0446 / 15.9828 | 635,685 / 33,108 / 2,797,033 |

v010 P1 = +7.1239 ΔE, above +5; P2 and P3 increased. Other facades are `not_exercised` for P1–P3 (0 changed pixels). No per-facade perturbation claim on those views, no native UV or shared-error intervention, and no padding or density result.

**Not measured — 0/3 eligible cross-job pairs, not 0/3 failures.** KPP1 v004: `1609-kpp1-package-v004/draft-b25-r1` has NPM+VPM, and #1817 documents the manual acceptance/exceptions, but #128's rejected predecessor is a geometry label, not a versioned atlas reject. Vatutino MAF: `C:/x/vatutino-maf/v005-set/{npm,vpm}` exists, but neither D202's Verona library-row acceptance nor #1499's closure provides a before/after export pair bound to a texture refusal. Staropetrovskiy MAF: `final_2026-11-20` has both site ZIPs; `final_2026-11-24` has only VPM. #1500 still waits for the reviewed library set (comment 7054611580); the T02 seat-side ruling is not bound to both profiles before and after. Do not reuse labels from another scope. #1947 owns atlas/master package validation; #1969 owns Ground atlas production, #559 owns the presentation/joint comparison. #1928 has merged, but trainer remains out of scope under this card's focus override.

Measured head `ab5c9d098caf9bedd5eda35dfd3179e223fb7292`; adapter Git LF SHA-256 `d689cfa834447210174f22d303aeb8ca7cd971518b8b1d465e38e46e37b8b874`. [Raw receipt](autoresearch-npm-vpm-render-diff-r130/receipt.json) SHA-256 `dcd35535fe608648792cf159fc0e8f89e8c7240efd530e30d65189fc63a6b6f9`; [decoded parity](autoresearch-npm-vpm-render-diff-r130/decoded-parity.json) SHA-256 `19f0a6ae6b352f9f3ca76f88876583ba8c771bf0769f7ffd06e2df52d5cf9bb1`. Readback: SHA-256 of `Image.open(path).convert("RGBA").tobytes()` in each of the six fresh output directories. No customer packages, production tools or tolerances changed.
