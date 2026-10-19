# Hypothesis 83 — corner multiplicity under XYZ/UV tolerances

**Verdict: CONFIRMED (synthetic experiment only).** `delivery_passed=false`.

## Claim and scope

Requiring a bijection under the existing XYZ/UV tolerances detects UV multiplicity
loss at coincident seam vertices that reusable nearest-neighbour comparison accepts,
without rejecting valid reorderings or repeated corners.

The frozen rejection rule was: baseline falsely accepts at least 1/4 malformed
cases; candidate rejects 4/4 malformed and accepts 4/4 clean cases in **each** of
three fixed permutations. Any missed count rejects the claim; an unavailable
harness is inconclusive. Both methods use Euclidean XYZ radius **<= 0.002 m** and
max-component UV error **< 2e-6**. No tolerance changes.

This tests finite synthetic corner arrays, not face connectivity, geometric
validity, finish/material correctness or facade-delivery certification. No DCC,
ignored assets, binary etalons, `data/`, production implementation or dependencies
were added. Work was completed within the 45-minute cap.

## Setup, inputs and source correspondence

- Base revision: `3cf7c9358591a12813ec5bcbcb8e082ddf5fe342`.
- Windows 11 build 26200; CPython 3.14.7, NumPy 2.5.3, pytest 9.1.1.
- Source: `tools/check_facades_max_roundtrip.py`, unchanged; SHA-256
  `a2309338785a49d371bebf999a4182f2d722b8e13e9777c5cab81eb316b7cb64`.
- Experiment: `experiments/hyp83/{fixtures.py,compare.py,run.py,results.json}`.
  Evidence contains source/fixture/implementation hashes, full synthetic arrays,
  expected labels, face indices, orders, 48 raw verdict/timing records and summaries.
- Schema: `[x,y,z,u,v]`, metres for XYZ; 12 corners, four triangles, degree
  histogram `{"3":4}` in **every** frozen case. Face lists partition the corners.

The pure-array baseline transcribes source lines 13–23 without importing its
module or top-level `bpy` code:

| Source operation | Array transcription |
|---|---|
| Lines 13–17: build KDTree, `find_range(c[:3], .002)`, require candidates | Per-row NumPy Euclidean distances, indices with distance <= .002; reject empty set |
| Lines 18–20: minimize maximum absolute UV component, reuse reference indices | `argmin` over the same UV errors; no index consumption; accumulate maximum UV error |
| Line 21: `max_uv < 2e-6` | Identical strict threshold |
| Lines 22–23: face count and string-key degree histogram | Same count and `Counter(str(len(face)))` comparison |

`max_position_error_m` in line 20 is report-only: the radius already supplies the
position gate. Its reporting accumulator is omitted. KDTree candidate ordering is
not reproduced: UV ties cannot change the verdict, but a tied diagnostic reference
index may differ. Baseline intentionally adds **no** corner-count or bijection gate.
This is semantic array-loop evidence, not an execution of Blender's KDTree.

Candidate uses the same eligibility relation, sparse adjacency lists, and iterative
alternating/augmenting paths. Occupied references can be reassigned; no greedy
first-fit consumption and no graph dependency. A perfect matching requires equal
array lengths and matching cardinality equal to both lengths. Existing face/degree
checks remain. Discovery scans one reference row-set per observed corner (O(N*M)
time); graph storage is sparse, not a dense NxM boolean matrix. No production-scale
performance claim follows.

## Frozen labels (before testing)

`fixtures.py` was written before the comparison run; labels were not inferred from
results. All malformed cases derive from `SEAMS`, changing only UV tuples at equal
XYZ. `ORDERS` freezes identity, reordered faces with cyclic corner rotation, and
reversed faces/corners. Both sides are independently reordered for each of three
runs. The reorder case also has an initial face/corner permutation.

| Case | Frozen construction | Expected | Baseline accepts (of 3) | Candidate accepts (of 3) | Candidate cardinality (each run) |
|---|---|---|---:|---:|---:|
| identical | Unique tuples, same arrays | accept | 3 | 3 | 12 |
| face_corner_reorder | Permuted seam triangles/corners | accept | 3 | 3 | 12 |
| legitimate_repeats | Reference and observed both repeat tuple 0 at corner 6 | accept | 3 | 3 | 12 |
| distinct_seam_uv | Coincident XYZ, distinct seam/island UVs | accept | 3 | 3 | 12 |
| replace_one_seam | Corner 0 takes corner 3 UV | reject | 3 | 0 | 11 |
| duplicate_two_tuples | Corners 0,1 take corners 3,4 UVs | reject | 3 | 0 | 10 |
| collapse_vertex_uvs | Corners 3,6 take corner 0 UV | reject | 3 | 0 | 10 |
| replace_island_corner | Island corner 9 takes coincident corner 0 UV | reject | 3 | 0 | 11 |

Baseline records 12 reusable assignments in every run; this is **not** matching
cardinality. Its distinct chosen indices can be fewer even for legitimate repeats.
Candidate records actual maximum matching cardinality. All cases have 12 eligible
edges except legitimate repeats, which has 14; edge count alone cannot detect loss.

## Prediction table

Counts below are medians over N=3 fixed permutation runs, each containing four
clean and four malformed cases. Acceptance requires the counts in every run, not
merely their median; all three runs agree.

| Metric | Inputs | Baseline (current code) | Rejection threshold | Measured (median of N) | Verdict |
|---|---|---|---|---|---|
| Baseline false accepts | 4 malformed x 3 orders | Reusable neighbour can lose multiplicity | Reject claim if <1/4 | 4/4 (N=3); 12/12 pooled | Met |
| Candidate rejects | Same malformed arrays | Baseline rejects 0/4 | Reject claim if <4/4 in any order | 4/4 (N=3); 12/12 pooled | Met |
| Candidate accepts | 4 clean x 3 orders | Baseline accepts 4/4 | Reject claim if <4/4 in any order | 4/4 (N=3); 12/12 pooled | Met |
| Threshold relation | Generated boundary probes | XYZ <= .002; UV < 2e-6 | Any relation mismatch fails | 108/108 checks | Met |
| Runtime (descriptive only) | 24 paired inputs, 12 corners each | 277,450 ns median | No speed threshold | Candidate 230,250 ns median (N=24) | Informational |

Raw nanosecond runtimes are in `results.json`; one timed call per method/case/order,
including graph discovery and metadata gates, excluding fixture construction.
No warmup, repeated timing batches or KDTree timings: do not interpret these tiny
array runtimes as production speedup evidence. Per-case medians (N=3), in ns:

| Case | Baseline | Candidate |
|---|---:|---:|
| identical | 275800 | 253200 |
| face_corner_reorder | 279100 | 226200 |
| legitimate_repeats | 271600 | 239400 |
| distinct_seam_uv | 267600 | 230200 |
| replace_one_seam | 270300 | 221800 |
| duplicate_two_tuples | 287300 | 230500 |
| collapse_vertex_uvs | 265000 | 230300 |
| replace_island_corner | 281400 | 226500 |

Confusion table, positive = clean/accepted, N=24 decisions per method:

| Method | TP | FN | FP | TN |
|---|---:|---:|---:|---:|
| Baseline | 12 | 0 | 12 | 0 |
| Candidate | 12 | 0 | 0 | 12 |

## RED, GREEN and probes

Commands from the worktree root (no DCC):

```bash
# Same affected-test command before and after the experiment-only change:
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_0df63c9e tests/test_hyp83.py
uv run python -m experiments.hyp83.run
# Full suite, once:
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_0df63c9e
```

- **RED:** before implementing matching, `candidate = baseline` exercised the
  unchanged comparison semantics. **12 failed, 21 passed in 0.24s**. All 12 assertion
  failures were malformed false accepts (4 cases x 3 orders), not import/setup
  failures. Production source was unchanged throughout. Initial 33 tests comprised
  frozen verdicts, baseline characterization and fixture contract.
- **GREEN:** same frozen regressions pass after replacing that alias with the
  experiment-only matcher; with additional probes: **150 passed in 0.30s**.
- **Full suite final line:** `2176 passed, 9 skipped, 12 deselected, 1 warning in 279.64s (0:04:39)`.
  Warning: pre-existing duplicate ZIP member test; skipped/deselected tests do not
  constitute DCC or delivery validation.

| Invariant | Generated / brute-force probe | Result |
|---|---|---:|
| Frozen clean/malformed verdicts in all orders | 8 cases x 3 independent order pairs | 24/24 |
| XYZ <= radius, UV strict max-component threshold | `nextafter` below/equal/above each limit; 3 XYZ axes x 2 UV axes x 3 x 3 x 2 methods | 108/108 |
| Each reference used at most once; maximum cardinality, not greedy | Every square bipartite graph of sizes 0–3; compare to exhaustive partial injective assignments; check every returned edge | 531/531 |
| Legitimate repeats accepted, multiplicity loss rejected | All pairs of length-3 sequences over 3 UV labels at coincident XYZ; compare to multiset equality and inspect assignment uniqueness/eligibility | 729/729 |
| Reassignment rescues an early occupied candidate | Geometric graph `[0,1]`, `[0]`, all independent two-corner permutations | 4/4 |
| Face count / degree guards unchanged | Wrong face count and same-count wrong degrees, both methods | 4/4 |
| Perfect matching requires equal corner counts | Too few / too many observed identical corners; cardinality equals min(counts), verdict reject | 2/2 |
| Frozen face/corner counts and fixed permutations | One fixture-contract test over all cases and orders | 1/1 |
| Baseline behavior remains reproducible | 8 fixtures x 3 permutations, still accepts all | 24/24 |

The baseline can also replay RED against the final frozen-verdict tests without
editing any file:

```bash
uv run python -c "import experiments.hyp83.compare as c; c.candidate=c.baseline; import pytest; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','--basetemp=C:/x/pi-t_0df63c9e','tests/test_hyp83.py::test_frozen_verdict']))"
```

This is a reproduction recipe, not an additional claimed test run.

## Decision and separate adoption scope

**CONFIRMED:** baseline false accepts **4/4 >= 1/4**; candidate rejects **4/4**
malformed and accepts **4/4** clean cases in **3/3** fixed permutations. No rejection
threshold was missed. The result is bounded to these frozen synthetic cases and
small generated probes, not arbitrary asset certification.

A separate adoption task should:

1. Add a pure helper such as `technical_library/uv/corner_match.py`; decide spatial
   indexing/scalability without changing eligibility or using a greedy matcher.
2. Integrate into `tools/check_facades_max_roundtrip.py`, preserving radius .002 m,
   strict UV <2e-6, face count and degree histogram checks.
3. Add `tests/test_facade_corner_match.py`: the frozen clean/malformed fixtures,
   independent reorderings, repeats, strict boundary probes, graph oracle,
   augmenting-path trap and corner-count guards.
4. Validate the integration separately; face connectivity and finish/material
   certification remain separate concerns.

Nothing was adopted into production here. Tracker updates were not performed
(`gh` prohibited by this task harness). `delivery_passed=false` remains mandatory.
