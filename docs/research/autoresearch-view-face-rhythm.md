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
