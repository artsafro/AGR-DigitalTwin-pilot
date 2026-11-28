# H162 — Silikatny: datum registration before wall matching (OBSERVE)

Масштаб по высотным отметкам помог на одном из пяти видов, но не устранил уверенную ошибку и не разрешил ни одного из двух видов внутреннего угла. **H162 опровергнута**; перенос отделки по этому сигналу не разрешать. Сокольники не открывались (#2001 открыт).

## Frozen contract

H162 isolates the scale/vertical-registration confound reported in #161 before changing the candidate set. A = exact #161 bounding-box scale. B = same drawn glass extraction, native model direction masks, grid, overlap, NCC and decision thresholds; replace only the PDF transform with manually transcribed geometry-bound levels. Keep all directions (including the 30° neighbour and opposite), fixed clips and held-out policy. No production code; no deliveries changed. This tests direction labels, NOT physical wall or bay identity. In particular the developed courtyard row allows two directions and cannot license an assignment to a single wall.

Fixture: all seven views of #161, five with known direction (two real detail fragments, two inner views); two unlabelled diagnostics never enter the denominator. PDF and OBJ pinned by #161 fixture at `f4a7f22b107826d5e054f11a5e336c63aed81667`; Git blobs run.py SHA-256 `978ad7d4ccffa01e90d726b56533ab3a914578ebd84f449265c16dd67bb9c5bf`, fixture.json `9ce8c9eba842de0d299ccc098a80ccee625fe7d68991f68f0ee64cec3630157e`. Blender 4.4 executable SHA-256 `fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5`. Dependency lock is unchanged. Resolve prior harness via `git fetch origin research/autoresearch-standing-161`. PDF/OBJ remain at its frozen fixture paths; replay limited to pilot host with those original inputs and Blender. No access to Sokolniki while #2001 open. No use of ground truth data in the scorer or anchor selection.

Anchors: physical PDF page, absolute PDF Y points manually transcribed from vector arrow tips or dimension extension lines after visual region inspection (not from title, nominal print scale, glass match or clip edges). Values below are `(Y pts, Z m)`; tested interval model Z `[0,12.9]`, fixed grid 0.25 m. For out-of-drawing rows inside that band use background, not stretch. Preserve the #161 horizontal mask bbox and the #161 classifier within it. Missing registration must abstain (no bbox fallback). F2 uses the adjacent same-sheet section's 0/8.100 marks, not a guessed top; intermediate 4.200 at Y245.08 independently checks linearity (max discrepancy 0.025 m), but no independent proof of same vertical section datum in the rendered detail. F1 uses the 12.900 m dimension chain and adjacent level 12.900; section base is labelled −0.015, so this is a 15 mm datum proxy, not millimetric truth. These are manual oracle inputs for the scale experiment, not a claim of automatic anchor detection.

| PDF page / #161 row | Anchors (Y,Z) | Provenance |
|---|---|---|
| 15 A'-K | (396.10, 0), (304.66,12.9) | left zero arrow and right parapet arrow |
| 14 4'-1 | (412.36, 0), (320.98,12.9) | bottom view, left zero arrow and right parapet arrow |
| 14 1-4' | (212.32, 0), (120.82,12.9) | top view, left zero arrow and right parapet arrow |
| 16 fragment 1 | (337.36, 0), (81.40,12.9) | facade dimension-chain extensions |
| 17 fragment 2 | (328.42, 0), (167.68,8.1) | adjacent section level arrow tips |
| 15 K-A | (194.62,0), (116.98,11) | left arrows of left view |
| 15 A-G | (190.66,0.75), (103.48,12.9) | right arrows of right view |

Score clean placement correct/wrong/abstain on the five scored views; primary metric answered accuracy `correct/(correct+wrong)` (undefined at zero answers), publish abstain rate `abstain/5` and inner/fragment rows separately. **Confirmation threshold:** no wrong, at least three correct, including at least one inner, plus parity and negative controls. Active positive witness A'-K must turn #161's wrong direction 0 into correct 330; publish delta versus the frozen wrong row. No confirmation of transfer without this and all bounds. No KEEP/OKS deployment even if confirmed; this is an oracle scale ablation. Historical wrong #161 assignment is the rejected mapping control, not a rejected delivered model (none identified). Blank and missing-anchor states must abstain on all seven, with real changes counted per view. Mirror and incorrect datum shift `+0.75 m` report changed cells and proposals; expected reduced support for the true direction but no acceptance bound (ambiguous motif); a no-op is `not_exercised`. Candidate-order reversal must not change any verdict.

Replay (write into fresh ignored worktree dir): `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-datum/run.py .venv/ar162-replay`. Three fresh paired runs with fresh shared native renders and fresh PDF reads, exact #161 row hash (`f1209644…6b6d`, exact verified from pinned receipt) and byte-identical new rows across runs. Median wall time and range of three; additionally publish observed B−A scorer time spread, not a performance claim. One new variant, zero retunes and no follow-up candidate in this round; stop inconclusive on parity failure, missing inputs or if 3 runs do not fit 180 s after first full pair (plus preparation), no partial confirmation. No threshold or guard weakening, no GT/clip edits, no replacing drawing/model, no opening held-out outputs, no synthetic-to-real extrapolation. Not measured: wall/bay localization, native Revit re-export, rejected deliveries, automatic datum detection, user finish transfer, #2001.

## Round log — refuted (branch-only, no product change)

Contract `c7940cea`; measured runner `d98acf95`. Three fresh paired reads/renders, status `finished`, wall 13.379 / 12.230 / 12.051 s (median 12.230 s; range 1.328 s). B−A post-render elapsed −0.303 / +0.319 / +0.410 s (median +0.319 s; range 0.713 s; B includes one more perturbation, not a performance comparison). Exact historical baseline rows 3/3; byte-identical B rows 3/3; candidate-order reversal passed in every scored state, including diagnostics. The two input assets and Blender hashes matched before and after the pairs. [Receipt](autoresearch-view-face-datum/receipt.json) SHA-256 `06669d58b0ee009addbd88261aac6ddb0625f947bb84512c7873e48f59e91889`.

| View | Known direction(s) | A answer | B answer or best unaccepted | B margin | A → B width (m) |
|---|---|---|---|---:|---:|
| A'-K | 330 | 0 (wrong) | 0 (wrong) | 0.1520 | 73.36 → 74.21 |
| 4'-1 | 90 | abstain | 90 (correct) | 0.1131 | 91.62 → 92.75 |
| 1-4', inner developed | 240 or 270 | abstain | abstain (240) | 0.0247 | 83.43 → 84.34 |
| Fragment 1 | 330 | abstain | abstain (0) | 0.0033 | 10.72 → 10.75 |
| Fragment 2, inner stair | 240 or 270 | abstain | abstain (240) | 0.0036 | 10.92 → 10.95 |

Clean A → B: **0/1/4 → 1/1/3** (correct/wrong/abstain); answered accuracy 0/1 → 1/2; abstain rate 4/5 → 3/5; both inner views and both fragments abstained. The wrong A'-K decision survives registration, including mirroring and the deliberate Z shift. These measured scale changes (~1% for the three full scored views) do not support the earlier ~8% estimate for the exact scored crops. K-A and A-G stay diagnostic, without inferred truth.

Injected controls: blank removed 2,067–9,924 cells per row and missing removed two anchors per row; both abstained 7/7. Mirror changed 1,770–10,190 cells and abstained 6/7; shift changed 1,426–8,725 cells and abstained 5/7 (one persistent wrong, one unscored). The corrected 4'-1 is an active clean control: both mirror and shift vetoed its clean answer. No no-op perturbations. Collection RED: missing research runner (`FileNotFoundError`), then 3 affected unit tests passed.

**Recommendation for the shared OKS step (not implemented):** use independently paired drawing datum marks for scale, not for identity. Do not accept a view-to-face match from direction-level NCC alone; for ambiguous/untitled views print candidate walls and the reason for abstention, and do not transfer finishes. Next, compare frontal wall-segment-clipped candidates with the same datum transform and freeze wall-identity truth from independent plan/section registration. Use the A'-K neighbour and opposite wall as hard negatives and score developed multi-wall views and bay/interval separately. Blind Sokolniki transfer remains gated by #2001.

Native renders and all three row sets: `G:/Мой диск/AGR-evidence/162-view-face-datum/` (31 SHA-256-verified files on the mounted drive; `SHA256SUMS.txt` SHA-256 `9f916467d150a4851289af60de6dabb463af3525f5d4b78947cb6ecaa5edbd81`). No original assets were copied; the pinned source paths remain necessary for replay.

Full suite: deferred to merge batch (rule 68).
