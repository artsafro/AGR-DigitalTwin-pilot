# #152: registered keyplan marks for title-blind elevation-to-side assignment

## Frozen contract (before implementation and scoring)

- **H152:** A single explicit red vector mark on a registered situation plan can safely propose an **exterior side**, not a particular wall polygon or bay interval. This is not a solution for sheets without that cue.
- **Inputs:** Exact PDFs from #151 Olimpijsky and #145 ELV, with their pinned PDF hashes and immutable prior model-registration provenance; see `autoresearch-view-face-keyplan/fixture.json`. Freeze all 14 real views from those two fixtures (four eligible Olimpijsky, seven ELV full views and three ELV fragments). Registration/footprint boxes are manually derived from the gray envelope and the prior plan/FBX registration, not the red mark. The classifier does not read elevation pixels or title/axis strings, nor see expected labels; the independent scoring labels use elevation title axis order in the registered model frame (from the prior annotated fixtures). Use physical PDF page numbers. No new model read is being claimed.
- **Arms:** A = identical registered input with keyplan red stroke segments withheld (ablation, not historical D). B = PyMuPDF vector lines: red stroke RGB `r >= .65, g < .35, b < .35`; use near-axis (≤1 pt transverse endpoint delta), within an exterior band of 2 pt to 20% of the footprint's shorter span, clipped tangentially to the side, with union coverage ≥45% on a collinear group (1 pt normal bin). Only one qualifying side may answer. A registered plan must be associated with exactly one elevation on the sheet; otherwise abstain. Project-frame transform is an external prerequisite; no auto-detection of plan, registration, marker semantics or association implied.
- **Metric and budget:** Overall correct assignments / all 14 clean views (abstentions count as unassigned); also report accuracy among answers and abstention by cohort. Run exactly three fresh PDF extractions in paired A/B, median and paired spread, one candidate, no extra search or retuning after scoring. First pair must finish within 20 s to run the two confirmations, with 60 s maximum series budget; on timeout report inconclusive and retain the completed pair(s). Require exact canonical row parity across fresh runs and exact decision/side coverage parity after reversing each exercised input sequence.
- **Bounds:** B improves clean correct count by ≥3, with zero confident wrong and all 10 ELV views abstaining. Prior p8 wrong under #151 D is a named trigger: B must now assign the true side; p5 is an active clean control and must be correct. Failing any bound refutes the bounded hypothesis. No inference about a user-rejected delivery: the rejected prediction is #151 p8, not a rejected building package.
- **Injected controls** on each native marked page: remove observed exterior segments (A); translate the observed mark to the footprint centre to test the exterior gate; add a second, equally supported opposite mark (must abstain); replace it with just that opposite mark (expected confidently wrong, known trust-boundary diagnostic, not a keep criterion). Per-page actual changed segment counts, plus counts in both states for reversal parity. Unexercised controls are not measured. Keep thresholds fixed. Never infer wall-polygon identity, scope, material assignments or handoff readiness from a side proposal.
- **Forbidden:** modifying sources/sheets/deliveries, reading Sokolniki while #2001 is open, changing production code or other cards, weakening tests/tolerances, or treating crafted negatives as customer evidence. No atlas, trainer or form research; #2073 and #2074 own earlier finish-score variants.
- **Replay:** `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-keyplan/run_keyplan.py tmp/ar152-NEW` from the measured revision (fresh output directory). Locked PyMuPDF; SHA-256 preflight and postflight of both mounted PDFs, plus recorded candidate/fixture/lock SHA-256. Durable inputs are reused in place, no recopy required; replay limited to holders of those exact PDF bytes.

## Acceptance table (research harness only)

| Witness | Expected | Regression / receipt |
|---|---|---|
| Registered gray box, fragmented red vector segments spanning top, duplicate strokes and a green decoy | Correct top side, independent of order; duplicates do not inflate coverage | `test_registered_vector_mark`, `test_duplicate_short_stroke_is_not_coverage` |
| Same page: no registration, mark removed, centre shift, two opposite marks | Refuse each; wrong opposite-only documents trust boundary | `test_ablation_and_altered_mark`, `test_unregistered` |
| Real control and prior wrong witness, all 14 clean views | Frozen bounds, both PDF digests unchanged; three canonical paired extractions | `receipt.json` |

## Round result

H152 **confirmed on one marked album only**. Scored revision `088cfe653eb14208c8132b0c2272a4269e414bfe`;
three fresh extractions: 1.8782 / 1.8690 / 1.7987 s (median 1.8690 s, spread 0.0795 s), all canonical rows
byte-identical, both PDFs unchanged. Ablation A: 0 correct, 0 wrong, 14 abstentions. B: 4 correct, 0 wrong,
10 abstentions (4/14 all-view yield, 4/4 answered accuracy, 10/14 abstention). Olimpijsky full: 4/0/0;
ELV full: 0/0/7; ELV fragments: 0/0/3 (correct/wrong/abstain). The p8 historical D error did not recur:
B returned azimuth 0°, the labelled side, while p5 returned 90°. p5/p6/p7/p8 mark coverages were
66.01% / 66.01% / 66.08% / 66.08%; the ablation removed 16/16/7/7 real segments, respectively.

- **Injected**: mask, interior shift and two-opposite-marks each produced 4/4 refusals. Single wrong opposite
  mark produced 4/4 wrong answers, a direct limitation, not evidence of a native wrong keyplan. Reversing
  segment order changed positions in 35/70 row-states; 0 coverage/answer changes in those 35. The other 35
  reversals and the four perturbations on each of the ten ELV views were not exercised.
- **Not measured**: other marked albums (G22/KPP1/AC08/OBR22/Vatutino), automatically finding/associating or
  registering a plan, DWG/raster sources, physical wall/bay identity, native wrong markers, finish transfer or
  STOP 04. #2001 still open; no Sokolniki input or accepted output used. This is a proposal mechanism, not a pass.

**Recommendation for the shared OKS step:** given an explicitly associated, model-registered plan and a trusted mark,
show a side proposal with sheet/page, mark and registration evidence. Require independent title/axis or geometry
corroboration before transferring finish callouts; without a unique mark, registered frame or corroboration,
keep the case unresolved. Never promote a side to a specific wall in a re-entrant corner. Next, measure transfer
on an independently registered marked album and test explicit footprint-edge/return-wall linkage on labelled
real fragments. Do not implement this step in production based on this round.

Replay artifacts: [receipt](autoresearch-view-face-keyplan/receipt.json), SHA-256
`df864b184879e9e013a2a8471c5c68cf762c00f43c0e68afb7d4c8f82d7ecd8a`; paired rows and preview crops under
`G:/Мой диск/AGR-evidence/152-view-face-keyplan/` + `SHA256SUMS.txt`. The two already sealed input PDFs remain
in the #145/#151 evidence directories; replay accepts a relocated evidence root with the same relative layout.
