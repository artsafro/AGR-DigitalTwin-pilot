# Standing #134 — isolated NPM seam sensitivity (OBSERVE)

## Frozen contract

Calibration first: rerun the unchanged #125 V2 comparison on AC08 v007 (rejected for pitch) and v010 (visual reference) via the pinned #128 native replay. Compare the four named facade scores and the case maximum (worst facade p95 of 1 m cell mean CIE76 ΔE at 100 px/m); rejected must be strictly worse on every facade and the case maximum in all three pairs for a pass. #130 previously ordered v006 (horizontal joints) correctly; it is historical evidence only here. It cannot erase a v007 reversal. No improvements or production candidate in this run, regardless of outcome.

H134 (diagnostic, not a new acceptance test): on both labels, V2 south-facade cell p95 responds by at most +0.25 ΔE to one synthetic NPM-only seam, even though the already-reported worst-cell mean increases by at least +2.0 ΔE. A distributed counterpart must increase p95 by at least +2.0 ΔE on both labels. One metric: signed `injected cell_p95 − clean cell_p95`, median of three fresh pairs, individual values/min/max/spread. Require all three pairs to meet the isolated bound for confirmation; a larger isolated delta on an otherwise valid series refutes H134. Missing or failed activation, controls, parity or coverage make this diagnostic inconclusive. No KEEP threshold for production; the thresholds above apply only to this observation.

Fixture, no post-score selection: use the pinned #128 `5c15100ee5631e2f5d75e697e14e1977a6361f3d` renderer/scorer, full manifest hash pre-/postflight, exact staged ZIP member identities, camera metadata, and decoded RGBA parity for both native versions and every view. Use Python 3.14.9, NumPy 2.5.4, Pillow 13.0.0 and its pinned Blender 5.1 hash. On the south facade find the first fully common opaque 400×400 native block, scanning 400-pixel blocks from the top left of the common bounding box, both images excluding red datum. Stamp the central 40×280 rectangle to (40,40,40) in NPM only. For the broad control stamp the same rectangle in every such full block (must affect >=10 blocks). The isolated arm is a ~10 cm by ~70 cm simulated seam at ~400 px/m, not a finding about a real texture. On both arms/labels require changed NPM RGB >0 in every targeted block, unchanged VPM, alpha, datum and RGB outside the footprint. All other views are `not_exercised`. Repeat the same selection across fresh readbacks; the broad control and local worst-cell response are required positive witnesses on both rejected and accepted inputs. Do not tune the stripe geometry or bounds after scoring.

Budget: three fresh paired confirmations, zero candidate improvements. Use the unchanged #128 native budget (first pair ≤90 s, remaining ≥2× first pair +15 s, total 300 s); total wall cap 360 s, and after the first image witness pair require ≥2× that elapsed +5 s remaining. Partial series is inconclusive. If load trips either condition, replay in a new directory; do not silently shorten the series. No Max, delivered-package edits, weakened checks, deselection, or other cards' files.

```bash
python docs/research/autoresearch-npm-vpm-single-seam-r134/replay.py tmp/r134-NEW
```

Replay is limited to the exact Drive ZIPs, Windows/Blender, and the historical Git objects used by #128. The other three calibration rows are **not measured** unless a texture-specific refusal and visual acceptance can be bound to exact two-profile bytes: KPP1 v004 (#1817; #2020 owns the rebuild), Vatutino MAF (#1499 closed without a paired rejection), Staropetrovskiy MAF (#1783 registers material metadata and draft hashes, not paired visual acceptance; #1500 still open). #2014 owns joint-gate binding, #1947 the atlas/master binding check, #1969 Ground, #559 drawings; none are in this experiment. Trainer and form research remain parked.

## Result — calibration refuted; H134 refuted; OBSERVE, no PR

**Итог:** неизменённый render-diff снова поставил отклонённому AC08 v007 более низкий балл, чем визуальному эталону v010: **0,8974 против 1,8381 ΔE**, обратный порядок на всех четырёх фасадах. Зато одиночная синтетическая полоса только в НПМ подняла p95 на **0,3620 / 0,3825 ΔE** соответственно, выше заранее заданных +0,25. Потери сигнала на этой полосе не подтвердились. Приёмочный порог не предлагаем. Пакеты и производственный код не менялись.

| AC08 | Clean south p95 | Isolated Δ p95 | Isolated Δ worst cell | Distributed Δ p95 |
|---|---:|---:|---:|---:|
| v007 rejected | 0.8877 | +0.3620 | +3.4519 | +3.5987 |
| v010 visual reference | 1.6980 | +0.3825 | +2.8956 | +3.5428 |

**Clean:** three fresh pairs, paired spread zero at the scorer's precision. Median rejected-minus-reference margins south/east/north/west: −0.8103/−1.0534/−0.8634/−1.0419 ΔE; case max −0.9407 ΔE. Matched #128 clean, camera and historical-control rows and all 60 decoded digests; 4 archive and 31 staged-file hashes matched pre/post and the prior receipt. `series_complete`: 133.42 s wall (115.99 s native), native pairs 46.48/37.30/29.19 s, witness pairs 3.68/3.37/3.50 s.

**Injected:** in every pair and on both labels, 11,200 NPM RGB pixels changed in the isolated arm and 201,600 in the 18-block distributed arm. Same first anchor `(row=134, col=277)`. VPM, alpha, datum and mask support invariant. Both positive controls cleared their frozen bounds on both labels; isolated responses cleared +0.25 (spread 0), so H134 is **refuted**, not inconclusive. The worst-cell mean is the existing diagnostic, not a proposed substitute score.

**Not measured:** other facades and VPM for the injection; native seam, UV, padding and density effects; the three external label pairs. This image-space result does not classify an actual board seam or establish the minimum detectable size or contrast.

Next: bind a genuine asymmetric NPM texture refusal to accepted NPM and the same VPM bytes before further calibration; if the reviewed #1500 T02 record becomes available, check whether the seat-side decision is texture-specific and covers both exact export versions before admitting it.

Measured head `fe0ac1b2cbec6d9d03bd059e5b5fbd16fe7561b2`. [Receipt](autoresearch-npm-vpm-single-seam-r134/receipt.json) SHA-256 (Git LF bytes): `68aa64fe4c549e9b7c674cdbef11b4cacf27f2a829fd24bb45677d5ec2bf39cd`.
