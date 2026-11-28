# H166 — Does horizontal glazing rhythm distinguish same-span walls?

## Frozen OBSERVE contract

Continue #165 (immutable `a38d5137c016d9086423512446c353e7d6517fc6`); no production changes, no new wall candidates. Same Silikatny PDF, categorized model, Blender, seven crops, manual kind/datum, and five labelled rows; source hashes inherited and rechecked. K–A is an exclusion (not W19), not a labelled alternative wall. A′–K and fragment 1 are W19 positives. #2001 is open: no Sokolniki source/key/outputs accessed. #2073/#2074/#2075 cover finish partition and wall-exercise validity; not in scope.

- A = exact #165 full-span veto. B = A plus a veto on pre-labelled full views only. Compare mean glazing down each column at the shared datum, linearly sample each profile on 128 equal bins over its complete width, subtract mean and take normalized dot product. No shifts, reflections, fitted scale, candidate reranking, or truth/label features beyond existing `kind`. Require correlation ≥ 0.35 (a fixed exploratory moderate correlation, not a calibrated production tolerance); missing/constant profile abstains.
- Primary metric: correct / answered **on the same five native labelled views**, with abstain / 5 and counts reported; also require no lost correct coverage (2 correct, 0 wrong, 3 abstain after veto). Report K–A exclusion separately. Positive challenge: stretched K–A from #165 passes A but must abstain in B. Native A′–K stays correct; require its shuffled columns to make a real change and cause a veto (active positive control). Native mirror is a measured diagnostic, not a strict bound (bilateral symmetry possible). Native fragment 1 must stay correct but is not exercised by the full-only rule. Blanks must abstain; B cannot create answers.
- Three fresh paired native passes, no extra candidate search (3 confirmation pairs / 0 exploratory rounds after freeze); report median and max–min for paired wall time; require exact #164 baseline body and #165 candidate body digests for A, and stable full B receipt bodies across pairs. 600 s hard launch budget and stop after pair 1 if two more at observed cost cannot fit; timeout/partial/parity failure = inconclusive, complete series missing any strict criterion = refuted. No relaxation, deselection, delivered-package writes, other-card edits, withheld inputs or frozen-dump-only claims.
- Replay in a fresh worktree-local output directory. Pin #165 runner bytes, its native blob chain, `uv.lock`, Blender and PDF/OBJ, before/after each pair. Source access is pilot-host-limited; the measured local fixture is not independent accepted/rejected delivery calibration, nor a blind kind classifier.

```bash
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163 research/autoresearch-standing-165
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-rhythm/run.py tmp/ar166-new
```

## Round log

**Hypothesis: confirmed (8/8 frozen checks). Run: finished. Adoption readiness: no.** Three fresh native pairs
took 23.171 / 25.001 / 27.128 seconds; median 25.001 s, spread 3.957 s, elapsed 76.818 s. Every pair matched the
historical native body and exact #165 outputs; the H166 body was byte-identical across the series. Replay checks the
remaining budget after the first pair; a slower host can stop with an inconclusive series instead of shortening it.

| Witness | #165 A | H166 B | Correlation | Changed cells |
|---|---|---|---:|---:|
| Native A′–K | W19 correct | W19 | 0.3613 | — |
| Native fragment 1 | W19 correct | W19, not exercised | — | — |
| Native K–A (W19 excluded) | abstain | abstain, not exercised | — | — |
| K–A stretched to W19 span | W19 wrong | abstain | −0.1378 | 14,976 output cells, grid resized |
| A′–K, shuffled column blocks | W19 | abstain | 0.1813 | 8,980 |
| A′–K, mirrored | W19 | abstain | 0.0735 | 8,328 |

- **Clean:** 2 correct / 0 wrong / 3 abstain in both arms on the five graded views (answered accuracy 2/2,
  abstain 3/5). Both inner views still abstain; A–G remains ungraded and abstains. Only one clean view actually
  reached the rhythm gate, and it survived by just 0.0113 above the fixed threshold.
- **Injected:** all seven blanks abstained, with 2,067–9,924 changed cells; the rhythm gate itself was not exercised
  on those rows because A already abstained. All seven mirrors and shuffles changed cells (1,770–10,190 and
  1,928–12,007, respectively); only the A′–K mirror and shuffle reached this full-view gate. The receipt
  separately flags changed inputs and gate exercise. Reset is a no-op, not perturbation evidence.
- **Not measured:** independent albums, rejected/accepted delivery calibration, native equal-span wrong walls,
  blind full/fragment classification, fragment/bay localization, finish transfers, and Sokolniki STOP 04.

## Recommendation (OBSERVE)

Keep this as a **diagnostic second signal** for whole views, not an approval or a production veto yet. On a proposed
OKS map sheet, expose the ranked wall candidates, span check, independent section/keyplan evidence and rhythm score.
If evidence disagrees or the view is a partial with no verified wall/interval, leave the assignment blank and ask;
do not transfer finish callouts. Next, freeze independent correct and wrong same-span CAD/PDF views across the named
calibration projects. For inner fragments, measure physical segment and bay interval separately against a section-bound
unrolled candidate. Keep Sokolniki blind until #2001 closes.

Receipt: [receipt.json](autoresearch-view-face-rhythm/receipt.json), SHA-256
`f40cc22d1dabd9dfacc1637209f184c73611f1e72f3c0502da31f1bcd468e6e9`. Runner measured at `ec67ce54`;
SHA-256 `b58f0876a9cf0204c6d7f7906e0698000b9acbb7d0652a9ca17cbb4133834f98`. Mounted Drive evidence:
`G:/Мой диск/AGR-evidence/166-view-face-rhythm/` + `SHA256SUMS.txt` (81 files verified,
manifest SHA-256 `107406a40cff0e3bf8e35c4deaaa589c9ebedfd95f76cbe395408f47c84715c2`). The seal contains native
wall renders and per-pair readbacks; replay needs pilot-host access to the original pinned PDF/OBJ and Blender.

Regression: pass-through RED 3 failed / 1 passed; H166 GREEN 4 passed. No production change, no PR.
Full suite: deferred to merge batch (rule 68).
