# Autoresearch #143: self-ambiguity abstain for elevation view -> face (OBSERVE)

**Итог:** _заполняется после замеров (см. Round log)._

## Frozen protocol (committed before any measurement)

Card t_7f65d2eb (standing #143), focus 0 (view <-> face map). #2001 is OPEN, so Sokolniki
(`jobs/sokolniki-uvk1000`) stays held out and is not opened. Continues #139-#142 instead of a new harness:
reuses the pinned #141 raster front end (Git `3716f5395667c17f8be8737313952aaa6285615c`) and the #140 2D
scorer / #139 native front end (Git `ab33b7e4249f41232501d0c05534bd2793a15358`, `38f7d95ee54a677ac744c0148fb1fce33b06d9d3`).

**Why:** #141 R2 and #142 A gave 4 confident-wrong answers on 4.4 m end crops of OBR22 K02 (NCC 0.99,
margin 0.54 to the next face): a short crop of repeating window rhythm fits a long periodic facade at
several offsets. A real untitled partial view of an inner corner is exactly that kind of short crop.
The existing margin compares faces only; it never asks whether the winning face explains the crop at
another, separate position equally well.

**H143:** adding a self-ambiguity gate to an answered decision — abstain when the winning face's best
score at any offset at least `D = max(10 px, ceil(view_px / 2))` (0.1 m/px, i.e. >= 1 m and >= half the
view) away from the best offset is within `TAU = 0.10` of the best — removes every confident-wrong answer
on the OBR22 clean cases while keeping most correct answers of the same scorer on OBR22 and KPP1.
The gate only adds abstentions; it never changes an answer or creates one. Thresholds, slack, smoothing,
MIN_SCORE 0.30 and TAU_MARGIN 0.10 of the upstream scorers stay unchanged.

Arms (one new candidate, applied to two existing scorers):
- **C/R2** = #141 R2 1D window-column NCC (OBR22 K02 raster PDF p14-15 vs accepted NPM v012), and
  **C/R2+SA** = same + gate. 40 clean cases (4 full + 36 synthetic crops) + 4 mirrors.
- **B2D** = #140 B 2D line scorer (KPP1 L01 DXF vs accepted delivered FBX; AC08 symmetric box), and
  **B2D+SA**. 80 clean cases + 8 mirrors.
- Perturbation P1 (reported, no bound): #141 R1 profiles (no tall-run removal, 22 wrong) + SA.
  Expected direction: wrong decreases.

Metric (ONE number): confident-wrong count on clean cases (answered accuracy) with abstain rate; plus
correct retained. Per-variant bounds, all must hold in each of 3 fresh pairs (median reported):
1. Positive trigger witness: the 4 R2 wrong cases (`А.2-Е.2` / `Е.2-А.2` crop0.25 @0.0 and @1.0) all
   abstain with reason `periodic`. Expected direction: wrong 4 -> 0.
2. OBR22 clean C/R2+SA wrong = 0 / 40; long full views 2/2 correct retained (the gate cannot fire
   there by construction: offsets span <= 12 px < D).
3. Accepted controls on which the gate may fire (collateral): OBR22 long crops retain >= 5 of R2's 9
   correct; KPP1 B2D+SA crops retain >= 16 of B's 22 correct (keeps >= +10 over #140 roofline A = 6),
   KPP1 full retains >= 2 of 3, 0 wrong on all 80 B2D+SA clean cases.
4. AC08 is all-abstain in B already: the gate cannot act -> labelled `not_exercised` (not measured).
5. Mirrors are a separate injected control: SA wrong <= baseline wrong per arm (reported, not pooled).
Confirmed if 1-3 hold in all three pairs; refuted if any is measured and missed; inconclusive on
budget stop or parity failure.

Parity proof: each pair re-runs both upstream front ends fresh (new Blender ray casts, new PDF/DXF reads).
OBR22: R1 and R2 cases with the SA field stripped must equal the #141 receipt `R1`/`R2` cases exactly.
KPP1/AC08: (fixture, title, gt, case) -> V1 answer must equal #139 receipt (as #140 does) and B answers
must equal the #140 receipt `views[*].B`. The per-offset maximum used by SA must equal the upstream score.

Budget: 3 fresh pairs, one candidate, no second candidate in this card. After pair 1, continue only if
2 more pairs at 2x pair-1 wall time fit in 15 min. Timeout 300 s per pair. No threshold change after
scoring. Stop on parity mismatch.

Forbidden: changing upstream thresholds/slack, editing delivered packages or the pinned inputs,
deselecting tests, touching other cards' files, opening Sokolniki outputs, scoring with GT or titles.
Inputs pinned by the upstream fixtures' SHA-256 (pre- and postflight), Blender 4.4 by
`fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5`, upstream code by full Git revision.

Replay (repo root, pilot host: Desktop OBR22 PDF, local OBR22 outputs, G: drive KPP1/AC08, Blender 4.4;
`git fetch origin research/autoresearch-standing-139 research/autoresearch-standing-140 research/autoresearch-standing-141`):
`uv run --offline --extra cad --extra pdf-review python docs/research/autoresearch-view-face-self-ambiguity/run.py tmp/r143-NEW`

## Round log

_pending_
