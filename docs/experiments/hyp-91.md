# Hypothesis #91: projected proper crossings

Issue: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/91  
Verdict: **confirmed on the frozen synthetic planar cases only**.  
`delivery_passed=false`. No production adoption or delivery certification.

## Contract and scope

Test whether real `technical_library.mesh_audit.core.inspect_mesh` produces concave
false positives that an isolated projected non-adjacent-edge proper-crossing predicate
removes, retaining crossed outlines and the two unchanged tracked controls. Reject if
baseline has no concave false positive, candidate has any wrong label, controls change,
or candidate verdict varies with shift/reversal/principal plane or between three runs.
Missing experimental inputs/harness would be inconclusive; none was missing.

Timebox: 45 minutes; completed within it. All experiment computation is Python stdlib.
No DCC, pipelines, real-object data, benchmark, production, dependency-manifest or CI edits.
The environment's higher-priority instruction additionally required one full pytest run;
that run is reported separately and is **not** evidence for the hypothesis. It created
an ignored `.venv` via uv; no dependency manifest or lockfile changed.

The external `C:/Users/artsafro/hermes_kanban/profiles/ACCEPTANCE_TABLE.md` was not read:
the worktree-only restriction forbids access. Its four columns supplied in the task are
used below; fidelity to any additional external template requirements is unverified.
This is a reporting-template limitation, not an unavailable geometric input.

## Freeze and snapshot (before audit execution)

Branch: `experiment/hyp-91`; initially clean worktree.  
HEAD: `3cf7c9358591a12813ec5bcbcb8e082ddf5fe342`.  
Interpreter: CPython 3.14.7, Windows; full environment is in result provenance.

`experiments/hyp-91/freeze.py` exclusively created `frozen.json` and `frozen.sha256`
before the first baseline call. It made **no** `inspect_mesh` calls. The JSON contains
all 188 explicit indexed-vertex/face meshes, labels, per-case baseline predictions,
transform metadata and the acceptance table with measurements unset. It has not been
modified after execution. Both run modes verify its hash and the two tracked-source
hashes before execution; results are exclusive-create files.

Tracked functions are extracted through AST from `tests/test_shared_library.py`:
`outward_unit_cube`, `test_mesh_closed_cube_report_counters_are_zero`, and
`test_mesh_bowtie_quad_counts_one_polygon`. Only their unchanged function bodies are
compiled. Cube and bowtie setup data are obtained by executing the original fixture
and the original bowtie setup statements up to the `result` assignment. Neither the
test module's imports nor texture tooling are imported. Both original test functions'
assertions are executed against the real imported `inspect_mesh`.

### Explicit inputs and pre-execution predictions

All coordinates are synthetic, in metres, in the listed boundary order.
Baseline predictions are hypotheses, not acceptance labels or retrospective edits.

| Outline | Explicit 2D boundary | Label / candidate prediction | Baseline prediction for each variant | Variants |
|---|---|---:|---:|---:|
| Square | `[(0,0),(3,0),(3,3),(0,3)]` | 0 | 0 | 24 |
| L | `[(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)]` | 0 | 1 | 36 |
| U | `[(0,0),(3,0),(3,3),(2,3),(2,1),(1,1),(1,3),(0,3)]` | 0 | 1 | 48 |
| Arrow | `[(0,0),(3,0),(1,1),(3,3),(0,3)]` | 0 | 1 | 30 |
| Crossed A | `[(0,0),(3,3),(0,3),(3,0)]` | 1 | 1 | 24 |
| Crossed B | `[(0,0),(4,3),(0,4),(3,0)]` | 1 | 1 | 24 |
| `outward_unit_cube` | Exact tracked 8 vertices / 6 faces, frozen in JSON | 0 | 0 | 1 |
| `test_mesh_bowtie_quad_counts_one_polygon` | Exact tracked cube + 4 vertices / 1 face, frozen in JSON | 1 | 1 | 1 |

For each n-vertex outline: embed `(x,y)` as `(x,y,0)` in XY, `(x,0,y)` in XZ,
and `(0,x,y)` in YZ. For **every** `s=0..n-1`, use boundary indices
`[s,...,n-1,0,...,s-1]`, then also its full reversal. Thus `3 * 2 * n` cases per
outline, 186 transformed single polygons plus two unmodified multi-face controls.
The frozen per-variant baseline prediction overpredicts concave flags in 24 cases
(12 L, 12 arrow); these prediction errors remain visible and were not repaired.

### Acceptance/prediction table

Measurements below are medians of the three separately retained repetitions;
count-based acceptance was checked on **every case in every repetition**, not just medians.

| metric | baseline | rejection threshold | measured median |
|---|---|---|---|
| Clean concave false positives per repetition | >=1 predicted | <1 baseline FP | baseline 90 |
| Candidate clean false positives per repetition | May flag concave | >0 | candidate 0; baseline 90 |
| Candidate crossed false negatives per repetition | 0 predicted | >0 | candidate 0; baseline 0 |
| Tracked controls preserved per repetition | 2/2 predicted | <2/2 | 2/2 |
| Candidate transform-invariant outline groups | Baseline may vary by shift | <6/6 | candidate 6/6; baseline 4/6 |
| Counter-identical repetitions | 3 predicted | <3 | 3/3 identical (cross-run comparison, not a timing median) |
| Runtime seconds per complete batch (3 runs) | Unmeasured before execution | Descriptive only | baseline 0.0154128000; candidate 0.0075606000 |

## Prototype method

`experiments/hyp-91/candidate.py` scans **all unordered vertex triples**, selects the
nonzero cross product with largest squared magnitude, drops its dominant coordinate,
and projects to the other two coordinates. It does not rely on the first triple or a
Newell normal (which cancels for Crossed A). It enumerates unordered non-adjacent
boundary-edge pairs, explicitly excluding consecutive pairs and the wraparound pair.
An intersection requires strictly opposite orientation signs for both segments, with
each signed determinant beyond `+/-1e-10 m²`. It returns 1 at the first proper crossing,
so it counts polygons rather than crossing pairs. A mesh count sums per-face flags.

The candidate is a standalone scalar classifier, **not** a replacement public API.
Baseline reports and per-face baseline/candidate counts are retained for all cases.
All non-classifier production counters remain untouched; no claim is made that a new
production report implementation was tested.

## Actual results (no failures aggregated away)

Raw evidence: `experiments/hyp-91/red.json` retains all 188 initial baseline reports
and every failed label; `results.json` retains each of 188 cases separately for each
of three runs, including full baseline reports, per-face counts, confusion and timings.

RED against unchanged production: **98 passed, 90 failed**, exit 1. These failures
are actual label mismatches (not import/setup errors). The two original tracked test
functions additionally pass 2/2. GREEN experiment: **564/564** candidate mesh-label
checks pass; original controls pass and their candidate per-face counts are preserved.
There is no production RED-to-GREEN fix or new production regression test in this task.

Each cell below is the sum of polygon flags over the separately retained cases for
that outline, not a hidden replacement for the raw case evidence. Controls are split.

| Input group | Cases/run | Expected sum/run | Run 1 baseline / candidate | Run 2 baseline / candidate | Run 3 baseline / candidate |
|---|---:|---:|---:|---:|---:|
| Square | 24 | 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| L | 36 | 0 | 24 / 0 | 24 / 0 | 24 / 0 |
| U | 48 | 0 | 48 / 0 | 48 / 0 | 48 / 0 |
| Arrow | 30 | 0 | 18 / 0 | 18 / 0 | 18 / 0 |
| Crossed A | 24 | 24 | 24 / 24 | 24 / 24 | 24 / 24 |
| Crossed B | 24 | 24 | 24 / 24 | 24 / 24 | 24 / 24 |
| Cube control | 1 | 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Bowtie control | 1 | 1 | 1 / 1 | 1 / 1 | 1 / 1 |

Confusion includes the clean cube as one negative and the bowtie mesh as one positive.

| Run | Baseline TN / FP / FN / TP | Candidate TN / FP / FN / TP | Baseline seconds | Candidate seconds |
|---|---|---|---:|---:|
| 1 | 49 / 90 / 0 / 49 | 139 / 0 / 0 / 49 | 0.0154128000 | 0.0073094000 |
| 2 | 49 / 90 / 0 / 49 | 139 / 0 / 0 / 49 | 0.0178678000 | 0.0075606000 |
| 3 | 49 / 90 / 0 / 49 | 139 / 0 / 0 / 49 | 0.0149175000 | 0.0096808000 |

`perf_counter` times one complete batch of 188 baseline audit calls separately from
188 candidate mesh calls; imports, JSON serialization, per-face diagnostic baseline
calls, and initial tracked assertion execution are excluded. These are descriptive
single-process timings, fixed baseline-first order, no performance acceptance gate.
The baseline performs a full topology audit while the candidate only classifies
crossings; the timing difference is **not** a production speedup claim.

### Counterexamples and invariants

Candidate counterexamples: **none**. All 90 baseline false positives/run are enumerated
in `baseline_clean_concave_counterexamples` and each repetition's raw case records.
Five examples (expected / baseline / candidate):

- `L/XY/shift-0/reverse-1`: 0 / 1 / 0.
- `L/XY/shift-1/reverse-0`: 0 / 1 / 0.
- `L/XY/shift-2/reverse-0`: 0 / 1 / 0.
- `L/XY/shift-2/reverse-1`: 0 / 1 / 0.
- `L/XY/shift-3/reverse-1`: 0 / 1 / 0.

In contrast, `L/XY/shift-0/reverse-0` is 0 / 0 / 0: baseline depends on boundary
start/direction for L and arrow. Square, U and both crossed families have constant
baseline verdicts, but U's constant verdict is wrong.

| Invariant | Exhaustive/generated probe on frozen inputs | Result |
|---|---|---:|
| No clean false positives | All 138 clean single polygons x 3 repetitions | 414/414 |
| Every crossed single polygon counts exactly once | Both crossed families, all 48 variants x 3 | 144/144 |
| First vertex / winding / principal plane do not change candidate verdict | Every cyclic shift, reversal and XY/XZ/YZ embedding; 6 outline groups x 3 | 18/18 groups (558/558 labels) |
| Adjacent shared endpoints do not count | 24 square variants x 3 | 72/72 zero flags |
| Cancelling bowtie normal does not suppress detection | 24 Crossed A variants x 3 | 72/72 one flags |
| Original controls retained | Cube and bowtie, unchanged indexed data and per-face counts, x 3 | 6/6 |
| Repetitions have identical counters | Compare all full baseline reports and candidate per-face/count records to run 1 | 3/3 complete batches (188/188 records each) |

These are bounded probes, not universal proofs beyond the frozen inputs. Maximal-cross
selection and the orientation tolerance are fixed in code, never tuned after results.

## Commands and separate repository test

From the worktree root, in order:

```bash
python -B experiments/hyp-91/freeze.py
python -B experiments/hyp-91/run.py baseline  # expected exit 1: 98 passed, 90 failed
python -B experiments/hyp-91/run.py compare   # exit 0: 564/564
```

Do not overwrite frozen evidence to replay: copy the experiment into another authorized
worktree/versioned folder or retain the existing outputs and use a new output version.

Environment-mandated full-suite command, run once after comparison:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_c410eb55
```

Final line (verbatim):

```text
2026 passed, 9 skipped, 12 deselected, 1 warning in 285.13s (0:04:45)
```

The warning is the existing duplicate ZIP member `same` in an archive rejection test.
No production code changed; this suite run is ancillary and did not execute the new
stdlib experiment runner as pytest tests. No pipeline or DCC was run.

## SHA-256 provenance

| File | SHA-256 |
|---|---|
| `technical_library/mesh_audit/core.py` | `e8e0c762152895d65fb6d910199bb8d2fd9324539559bb51374eb0adeae9949b` |
| `tests/test_shared_library.py` | `2a456a80f328a677000de3bb48e66b969efde9884d28722488c2f35ef77d47ad` |
| `experiments/hyp-91/freeze.py` | `5b0bcb7a44ecf1c2efa677a36b4dfdaeacfc005f4467002067caf273fb55bbc2` |
| `experiments/hyp-91/candidate.py` | `66c4ef6cb1b55fe9e344a68aad3e8dea706a33133d1241321495352190fa712f` |
| `experiments/hyp-91/run.py` | `aae5ccc91829e9037fc6e6600a79af51c4a1804310b6467f2b94f35ab6664107` |
| `experiments/hyp-91/frozen.json` | `fcf04fcc056975b36a3d6d1bffb74fee6be5352633da6be8dbbbd99dbfbd4f88` |
| `experiments/hyp-91/frozen.sha256` | `8831062dda82d77c0f666adcc05d52d4fdda731d4bdfd8d39bb2105e8e0cb556` |
| `experiments/hyp-91/red.json` | `bb1ec17ab7c0871a286383639db8c5a99bafaae1ed8e6f96c8f273901305a50a` |
| `experiments/hyp-91/results.json` | `b9dcc22bb8e1ecfe415fcec8df08b9873ee20fc32e269bba6e28725531ff7775` |

## Remaining work and limits

Separate adoption task only: replace just the bowtie heuristic behind
`self_intersecting_polygons` in `technical_library/mesh_audit/core.py`; add NEW
`tests/test_mesh_audit_planar_polygons.py`; document bounded planar/proper-crossing
semantics in `technical_library/mesh_audit/README.md`. Preserve report-only status,
all other counters, API and `delivery_passed=false`. No adoption was attempted here.

Unsupported degeneracy handling must be specified before widening production scope.
This prototype raises on collinear-only polygons; it does not validate planarity and
makes no supported claims for collinear overlap, non-adjacent touches, repeated
vertices, nonplanar faces, mesh-to-mesh intersections, or general 3D intersection
checking. No new gate and no delivery certification is justified by this result.
