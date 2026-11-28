# H169 — refuse one-label support in the finish-partition score D (OBSERVE)

## Кратко для Артёма

_(заполняется после измерения)_

## Frozen contract (written before the runner and before any score)

**Question.** #168 found that the #149 finish scorer `U(V|M)` returned 1.0 on overlaps that contain exactly one
drawing label: true `H(V) = 0`, but float summation gave `H(V) = 1.1e-16`, so the `hv <= 0` guard missed it. Two
answers came from such supports: the clean slanted full view `p19 6-1` (`W16`, side-correct, the only full gain of
F over A) and the injected top-cut mirror `p20 frag 9-10` (`W12`, wrong side). Does an explicit refusal of
one-label supports remove the degenerate answers while leaving every multi-label score unchanged?

**Arms (one variant, no search).** F = #168 fusion, unchanged (A = #167 C166 glass stack + D = #149 score).
F' = the same fusion with D' = D whose `uncertainty()` also returns -1.0 when the overlap holds fewer than two
distinct drawing labels (`pv.size < 2`); this is a one-token source change of the pinned #149 `score.py` blob
(`if hv <= 0:` -> `if hv <= 0 or pv.size < 2:`), applied in memory. No threshold, margin, overlap floor, slack or
candidate changes. Both arms are computed in the same fresh pair on the same native label maps.

**Fixture.** ELV TC Sreda, the #145/#167/#168 pinned PDF (`49c10527…`) and FBX (`7ccf502d…`), Blender 4.4
(`fd21f4b9…`); all 7 full views and 3 real fragments, 34 wall candidates, states clean / blank / mirror exactly as
#168. Side-level truth from the #145 oracle (within-project ablation, not external validation). Sokolniki is not
opened (#2001 OPEN).

**Parity.** Each pair must reproduce the #167 A digest `04f67ea6…` (inside the pinned #168 runner) and the #168 F
body digest `9355a8c728aa40305caaf1b9a74046b283d2aeabc98aabfc52cc5bbdcef6c3a7` with the original scorer; F' body
must be byte-identical over the three pairs. Every per-wall score that differs between D and D' is listed; a
difference is admissible only where the D maximum came from a one-label support, i.e. by construction of D'.

**Metric.** Primary: confident-wrong answers of the fused arm over exercised rows (clean + injected mirror,
full + fragments); F has 0 clean + 2 mirror = 2. Secondary: correct / wrong / abstain per cohort, full-view
coverage (F 3/7), changed per-wall score count.

**Frozen predictions and acceptance.** H169 is **confirmed** iff all hold:
1. `p20 frag 9-10` mirror no longer answers `W12` (expected: abstain) — positive trigger witness;
2. `p19 6-1` clean no longer wins by a one-label support (expected: abstain or a different, multi-label winner;
   its side-correct answer may be lost — this is an expected coverage cost, F' full 2/7 is predicted);
3. retention control `p18 I-A` clean keeps `W08` (glass route; D' must not create a conflict);
4. clean wrong stays 0 on all ten views, blanks 10/10 abstain;
5. primary metric F' <= 1 (expected 1: `p24 frag 8-9` mirror keeps `W16`, five labels — support refusal is not a
   handedness check; recorded as the known residual, not a failure of H169);
6. every changed per-wall score has D = 1.0 or came from a one-label support (the runner records, for each changed
   score, the D value; any changed score with a multi-label D maximum refutes the "invariance" claim).
Otherwise refuted. A budget/parity stop is `inconclusive`.

**Budget and stop.** One variant, three fresh pairs (one budget-setting + two confirmations), no new candidate.
Budget 2100 s elapsed (#168: median 338 s/pair); stop as inconclusive if `elapsed + 1.15 × first pair × remaining`
exceeds it. No report-based tuning, no second variant in this card.

**Forbidden.** Editing delivered packages, source files, other cards' files or production code; weakening checks;
deselecting tests; opening Sokolniki outputs; rescoring the #168 dump as stability evidence.

**Replay.**

```
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163 research/autoresearch-standing-165 research/autoresearch-standing-166 research/autoresearch-standing-167 research/autoresearch-standing-168
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-support/run.py C:/x/ar169/<fresh>
```

Pinned blobs: #168 `run.py` (71fe3bd5, SHA-256 `1aa51f79…01ef`), `label_tail.py` (`800f8de0…9cfb`), #149
`score.py` (ef84ca41, `4a125268…ed24`). Replay is limited to a host with the #145 named-folder inputs and Blender 4.4.

## Result

_(after measurement)_
