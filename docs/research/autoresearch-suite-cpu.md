# Autoresearch: default-suite CPU (#1227)

Status: **final validation resumed after the orchestrator's scheduling clarification**.
Retained code is unchanged. Final serial CI/whole-suite CPU and capacity repetitions are
pending; no acceptance is claimed before their actual results. See the interruption evidence.
After validation, exact-head final receipts, per-file tables and capacity results belong
in the PR body's **Final measurements** section and attached CSV, without changing the
SHA they certify. This file is the committed search/round log.

## Frozen experiment contract

- Worktree/branch: `t_4c32b36e` / `research/autoresearch-suite-cpu`.
- Baseline revision: `a4621a56` (pilot main at start).
- Reused the previous worker's live round-0 process, slot PID 403828; did not restart it.
- Default selection remains the `pyproject.toml` addopts, including the absence of a `native_max` exclusion.
- Per-test CPU is `time.process_time()` across setup/call/teardown in the serial pytest process.
  It excludes child-process CPU and collection; it is not whole-machine CPU, and is not perfectly
  deterministic under load. Wall time is informational, not the selection metric.
- Metric: median of three serial target-set pytest invocations, summing per-test CPU in each.
  Keep only at least 5% improvement versus the previous retained median, with exact node/outcome parity.
- Stop at 8 hours, three consecutive experiments below 2% gain, or at least 40% target CPU reduction.
- No test selection, marker, assertion, tolerance, production input, CI, runner, or coordination-policy change.
- Raw measurements and frozen harness: `C:/x/autoresearch-suite/` (not committed).

## Round 0

Exact retained command, recovered from `proc_42bc4c645430.json` (native Hermes process receipt):

```bash
python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --card t_4c32b36e -- env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL PYTHONPATH=C:/x/autoresearch-suite AR_CPU_OUT=C:/x/autoresearch-suite/baseline.jsonl uv run pytest -q -p no:xdist -p no:cacheprovider --durations=0 -p ar_cpu_plugin --basetemp=C:/x/t_4c32b36e
```

Run from the card worktree; stdout/stderr were retained as `baseline_stdout.txt`.
The plugin is conftest-free. Baseline was reused, not repeated.

Final summary: `20439 passed, 114 skipped, 435 deselected, 49 xfailed, 102 warnings in 2963.19s (0:49:23)`.
The authoritative selected node count is **20600**, from collection and 20600 unique test records;
per-node outcomes are 20439 passed / 112 skipped / 49 xfailed. Pytest's phase-summary skipped count
is not the selected-node count. Session CPU: **1766.562 s**; summed test CPU: **1731.13778 s**.

### Frozen hashes (SHA-256)

| Artifact | SHA-256 |
| --- | --- |
| `ar_cpu_plugin.py` | `12b43cf3bbd0d5fa28abd2539490114bf821e23511701ed3663e0997afd4626a` |
| `baseline.jsonl` | `1ce7788c55d4aeb2ca23f25b861b5ad8a6099c0a715a8d92a5a740b99fd5a78f` |
| `guard.py` | `f1ab91f051886ac0843deeefcd507507f8040590076a62fb6574a2a262593f46` |
| `targets.txt` | `7da989d70259b35fb1e31a1ed394e1f8834084db68744168afef1b549ebc140a` |

Before freeze, `guard_probes.py` exposed 9 false passes in the inherited draft guard. Repaired event
ordering, completeness, finite/nonnegative timings, allowed outcomes, and mandatory candidate runs.
Synthetic probe output: **24 checks**, unittest PASS; RED and GREEN logs are local. No optimization was
measured or selected with the draft guard. The frozen diff-token check is only a heuristic: manual review
must also verify unchanged assertions, tolerances and fixture inputs; a token count cannot prove semantics.

### Frozen target set: 1052.17124 s, 60.77917% of baseline test CPU

| File | Baseline CPU s |
| --- | ---: |
| `tests/test_ucx_build.py` | 237.98436 |
| `tests/ops/test_opacity.py` | 130.39058 |
| `tests/test_bind_ground_textures.py` | 120.65623 |
| `tests/test_evals_handoff.py` | 64.89058 |
| `tests/test_spec_contour_shapes.py` | 63.12508 |
| `tests/qa/test_orientation_scaling.py` | 56.76555 |
| `tests/qa/test_scene_clearance.py` | 56.70295 |
| `tests/max_tools/test_agr_tools_ui_qt.py` | 46.90625 |
| `tests/test_ci_receipt.py` | 45.54686 |
| `tests/max_tools/test_agr_tools_uv.py` | 36.79685 |
| `tests/evals/test_geometry_mutation.py` | 33.62498 |
| `tests/test_ground_recipes.py` | 33.01553 |
| `tests/max_tools/test_agr_tools_tex.py` | 31.43742 |
| `tests/qa/test_from_spec.py` | 24.54684 |
| `tests/test_model_maf_skill.py` | 24.48435 |
| `tests/max_tools/test_polygon_expected.py` | 23.64062 |
| `tests/test_flora_catalogue.py` | 21.65621 |

## Acceptance/probe plan (before optimization)

| Invariant | Concrete input | Expected | Probe |
| --- | --- | --- | --- |
| Guard fails closed | Empty/partial/reordered/duplicate events, NaN/inf/negative CPU, failing/unknown outcomes | nonzero; valid control zero | `python C:/x/autoresearch-suite/guard_probes.py` |
| PNG fixture equivalence | Sizes 2048/4096 and repeated calls into independent output files | original PNG bytes; one encode per size; mutation of one file cannot change another | fixture-cache probe, to be executed before/after change |
| Cached layered fixture equivalence | Existing synthetic 200 x 190 m layered site, original builder parameters | identical source/mesh/result data, no cross-test mutation | layered-fixture parity probe, to be executed before/after change |
| Selection/outcomes unchanged | All 17 target files, 3 runs each | identical selected ids and per-node outcomes | frozen `guard.py` |
| Default selection unchanged | Final full default serial suite | 20600 selected, zero failures | slot + CPU plugin |

## Experiment ledger

| Round | Hypothesis / files | CPU before / after (3-run medians) | Guard | Decision |
| --- | --- | --- | --- | --- |
| 0 | Unmodified baseline; target-set runs CPU 1292.23367 / 977.17120 / 842.18663 s; wall 1904.1 / 1256.3 / 1089.5 s | median 977.17120 s | PASS, 1729/1729 IDs and outcomes in every run | baseline |
| 1 | Reuse generated setup in four target files: immutable PNG/icon bytes, a layered-site build with deep per-test copies, and a synthetic Git template with independent file/ref copies; commit `44c31bd4` | 977.17120 -> 688.38978 s (**29.55280%**); runs 619.48327 / 851.76473 / 688.38978 s | PASS (3 x 1729 IDs/outcomes, 20600 default selected, unchanged 372 assertion/raises/approx/warns ASTs); detached RED 4 failures, GREEN 4/4 probes | **keep** |
| 2 | Compact already-rejected edge/edge and edge/plane pairs in `HeightField.kinks`; frozen dense reference, same test node; `6ecce16f` | 688.38978 -> 595.92051 s (**13.43269%** gain, **39.01575%** cumulative); runs 530.65492 / 608.78033 / 595.92051 | PASS: 3 x 1729 IDs/outcomes; 20600 default IDs; RED 1 failure, GREEN 400 generated byte/purity cases + 221 layered-site calls, 5554 points | **keep** |
| 3 | Reuse remaining Git/large-box/lexical facts; trial `1e45e15a`, revert `99f5a59a` | 595.92051 -> 1025.17147 s (**-72.03158%** gain); runs 1025.17147 / 803.76483 / 1070.10845; wall 1543.90105 / 1060.34489 / 1522.62383 s | PASS: 3 x 1729 IDs/outcomes; 20600 default IDs; RED 3 failures, GREEN 3 probes incl. real checker and 300 lexical cases; 110 affected tests passed; all 884 original assertion/raises/approx/warns ASTs in 7 investigated files unchanged | **revert**, below 5% threshold |

Files per round (besides this log):
- R1: `tests/test_bind_ground_textures.py`, `tests/test_ucx_build.py`, `tests/test_evals_handoff.py`, `tests/max_tools/test_agr_tools_ui_qt.py`.
- R2: `src/dt_ai/geometry/ucx_build.py`, `tests/test_ucx_build.py`, `tests/ucx_kinks_reference.py`.
- R3 (fully reverted): `tests/test_ci_receipt.py`, `tests/qa/test_orientation_scaling.py`, `tests/test_model_maf_skill.py`.

The R3 slowdown affected unchanged files too: compared with R2's median run, UCX rose
102.94 -> 233.95 CPU s and opacity 98.56 -> 205.83 CPU s in R3 run 1. No observation was
discarded, no previous baseline rerun, and no threshold/metric retuned. This is further
evidence against calling process CPU deterministic under machine contention. The kept
median reduction is an observed protocol result, not a controlled causal percentage.
The remaining timebox is reserved for the mandatory frozen-head full-suite/capacity
measurements and publication verification; no further candidate can safely fit that budget.

The frozen metric is **not an instruction count**. Even the unmodified baseline varied from
842.18663 to 1292.23367 CPU s. Keep/stop decisions follow the prescribed three-run medians,
without dropping outliers or retuning the metric; the observed percentage is not a promise of
an identical causal speed-up on another load/frequency state. Fixture reuse is also independently
proven by encoding/build reuse and private-copy probes.

Round 2 changes no geometric predicate or tolerance: row-major `nonzero` compacts pairs only
after their existing necessary mask has passed. The surviving pairs use the original arithmetic,
strict inequalities and order, including duplicate points. The reference executable AST equals
the pre-change `HeightField.kinks` body (excluding its docstring); its source module hash is
`f18984031daec74e84f44af2a8d41f6194244fda9e7ff91d830b8bcfe0291a3e`.

## Parallelism evidence (no policy change)

The earlier report [601 s versus 2000–4000 s](full-suite-wall-time-601s-vs-4000s.md) found `-n 8`
ran the same default selection faster, but violated rule 43's xdist-in-slot ban. The present card explicitly
requests bounded n=2/4 experiments with two busy slots, three runs each; this is an experimental exception,
not authorization to change `suite_slot.py`, rule 43, or merge_batch.

The sampled load is **one xdist slot plus one serial slot**, not two xdist slots. The companion
first runs the canonical local CI producer (including the real full default pytest suite), then
repeats the real frozen target suite if needed to keep that slot busy. Exactly two live owned
holders are required before each xdist launch and sampled every two seconds. A successful
run whose samples all contain >=2 holders counts as conservative capacity evidence, per the
orchestrator's 2026-11-11 19:50 clarification on this card; a third foreign holder is disclosed,
not silently discarded. This does not certify simultaneous xdist in both owned slots.
A heap/worker failure under third-holder load receives at most two retries; if still contaminated,
report that cell `not measured: shared-board load`. Ordinary failures remain visible negative evidence.
Neither this clarification nor the experimental driver changes the shared scheduling policy.

## Interrupted final-validation attempt (external scheduling)

Measured head: `c43b0642af8b949b5f23242910dda1e96ae9b683`. After the low-priority queue wait,
our slots were granted at 18:38:58 and 18:53:56. Both preflights waited for the third foreign
holder to drain before starting. The final recorder collected 20600 IDs.

| Observation | Actual result | Validity |
| --- | --- | --- |
| n=2, run 1 | 996.203173 s command wall; pytest `20439 passed, 114 skipped, 49 xfailed, 109 warnings in 993.94s (0:16:33)`; exit 0; no desktop-heap or worker-failure markers | **Not a controlled two-slot observation**: holder counts [2, 3]; 182/495 samples had a third holder |
| n=2, run 2 | Started, then intentionally interrupted | No completed result; not counted as a passing run |
| Final serial CI | Interrupted; 15829 JSONL lines, no final session record or CI receipt | Incomplete; no whole-suite after-CPU or passing full-suite claim |
| n=4 | Not run | No capacity claim |

A new foreign slot-2 holder (`t_ed5212d6`) joined at 19:13:58 and restarted at 19:22:04.
Per-call `--slots 2` does not constrain other callers using the shared configuration of 3.
Continuing would knowingly overlap three suite jobs, so only our two owned process trees
were stopped; all recorded descendants were verified gone, and no owned live holder remained.
No foreign process, runner, configuration or coordination rule was changed.

All eight validation files were preserved under
`C:/x/autoresearch-suite/validation-attempt-001-interrupted/`; `manifest.json` binds their
original names, sizes and SHA-256 hashes. Baseline/plugin/guard/target inputs are untouched.
The incomplete `final.jsonl` must never be used as final evidence. The original two-slot-only
interpretation above is historical: the orchestrator subsequently accepted the successful n=2/r1
as conservative evidence under harder load (182/495 samples with three holders). It remains
visible with its original measured SHA. A fresh matrix and serial CI are measured on the retry
head; no baseline or retained target experiment is repeated. Launch preflights still wait for
at most two live holders; another caller's later third-holder admission is recorded, not hidden.

## Reproduction and exact-head publication

- Platform observed: Windows 11 build 26200, 32 logical CPUs; project Python 3.14.7,
  pytest 9.1.1, xdist 3.8.0, NumPy 2.5.3, Shapely 2.1.2, Pillow 12.3.0.
- Exact research harness snapshots are in [autoresearch-suite-cpu-harness](autoresearch-suite-cpu-harness/).
  They are `.txt` audit snapshots, not shared production tools. Scoped `.gitattributes` preserves
  original bytes/line endings; a RED probe caught Git normalizing the recorder, then 6/6 raw/index
  byte-parity checks passed. Raw plugin/guard/baseline hashes above remain unchanged.
- Target repetitions: `python C:/x/autoresearch-suite/bench.py --repo <worktree> --targets C:/x/autoresearch-suite/targets.txt --out <new-evidence-directory>`.
- Final serial command is the archived `final_companion.py`, through
  `python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --slots 2 --card t_4c32b36e -- python C:/x/autoresearch-suite/final_companion.py`.
  It invokes `uv run python tools/ci_receipt.py --issue 1227 --basetemp C:/x/t_4c32b36e-final --pytest-log tmp/full-suite.log --out tmp/ci-receipt.md`.
  The ready-gate preflight passed. Process-local `PYTEST_ADDOPTS` adds only `-p no:cacheprovider -p ar_cpu_plugin -p ar_env_boundary`;
  the recorder is installed in this worktree's venv, and the boundary clears recorder/addopts
  inheritance after recorder initialization, avoiding recursive nested-test evidence writes.
- In parallel, use the same slot wrapper with `--slots 2 --card t_4c32b36e -- python C:/x/autoresearch-suite/xdist_matrix.py`.
  Neither driver changes the shared slot configuration. Existing raw outputs are refused.
- Final CPU/node data are `final.jsonl`; actual pytest output is `final_pytest.log`; producer
  stdout is `final_stdout.txt`. The final guard, per-file CSV and top-node table are generated
  from those actual records. Exact-head CI/evals receipts and Agent trace are copied into the PR body.
  No tracked file is edited after the final suite starts.
