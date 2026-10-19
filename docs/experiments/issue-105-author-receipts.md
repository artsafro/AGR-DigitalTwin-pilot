# Issue #105: Author Receipts & Adoption Verification Evidence

Follow-up to Issue #105. Merged PR #104 is not modified. This document records author evidence receipts and procedural evaluation status with no production changes (new test only).

## 1. Context and Scope

- **Scope**: Adds a reproducible synthetic proper-crossing regression test and documents missing/unavailable procedural evidence receipts. No production code changes were made ([`technical_library/mesh_audit/core.py`](../../technical_library/mesh_audit/core.py) is untouched).
- **Adoption Replay (RED)**: RED is an adoption replay against pre-adoption revision `3cf7c9358591a12813ec5bcbcb8e082ddf5fe342`, demonstrating what the generator test would have caught prior to #91 adoption (aggregate 640 mismatches verified), rather than a new geometry fix.
- **GREEN Starting Revision**: `2e61c73` with only [`test_mesh_audit_generated_crossings.py`](../../tests/test_mesh_audit_generated_crossings.py) added.
- **Environment**: CI not run (billing lock). No DCC invoked. No modifications to `docs/PROJECT_STATE.md` or shared standards.

## 2. Synthetic Generator & Invariant Verification

- **Generator Configuration**: `random.Random(105)`, integer grid `[-15, 15]^2`, vertex count $n \in [4, 9]$. Polygons with collinear triples are strictly rejected via independent exact integer determinant.
- **Population Counts**: 245 attempts, 45 rejections, 200 accepted (27 clean, 173 crossed, 117 multiple-crossing subset).
- **Invariant Space**: Every cyclic shift ($n$), both windings (forward, reversed), across 4 embeddings (XY, XZ, YZ, oblique $(x, y, x + 2y)$), generating 9,920 mesh variants.
- **Independent Oracle**: Exact integer 2D orientation determinant counts nonadjacent edge crossing pairs, expecting `self_intersecting_polygons = int(pairs > 0)` (1 flag per crossed polygon even when multiple pairs).
- **Report-Only Semantics**: Preserves `delivery_passed=False` and `intersection_test_performed=False`.
- **Bounded Claim**: Evaluates synthetic non-collinear planar integer polygons; makes no universal 3D geometry claim, float epsilon/tolerance certification, or delivery readiness claim. Current test pass evidence is not universal proof.

| Invariant / Property | Evaluated Probe | Result (Current Test Pass Evidence) | Result (Pre-Adoption `3cf7c935` Replay) |
|---|---|:---:|:---:|
| Cyclic vertex shifts ($n$) | All $n$ rotations | 9920 / 9920 match against exact oracle | Only aggregate 640 mismatches verified |
| Winding reversal | Forward & reversed | 9920 / 9920 match against exact oracle | Only aggregate 640 mismatches verified |
| Principal & oblique planes | XY, XZ, YZ, $(x, y, x+2y)$ | 9920 / 9920 match against exact oracle | Only aggregate 640 mismatches verified |
| Multiple crossing detection | Multiple polygon population 117 subset (1 flag per crossed polygon even when multiple pairs) | 9920 / 9920 match against exact oracle | Only aggregate 640 mismatches verified |
| Report-only contract flags | `delivery_passed`, `intersection_test_performed` | Both `False` | Both `False` |

*Note: All summary rows represent current test pass evidence under the evaluated synthetic suite, not universal proof. For pre-adoption replay, only the aggregate 640 mismatches across the 9,920 variants were verified by log; individual per-invariant failure breakdowns were not isolated in the log.*

## 3. Test Executions & Actual Log Counts

- **Direct standalone execution**:
  `uv run python tests/test_mesh_audit_generated_crossings.py`
- **Targeted suite command**:
  `uv run pytest tests/test_mesh_audit_generated_crossings.py tests/test_mesh_audit_planar_polygons.py tests/test_shared_library.py -q -s -p no:cacheprovider --basetemp=C:/x/t_77ae3695-targeted`
  - Result: `211 passed in 1.46s` ([targeted.log](../../tmp/issue-105/targeted.log)).
- **RED replay command**:
  `.venv/Scripts/python.exe -m pytest tmp/issue105-prev/tests/test_mesh_audit_generated_crossings.py -q -s -p no:cacheprovider --basetemp=C:/x/t_77ae3695-red` (test copied into detached worktree `tmp/issue105-prev` at SHA `3cf7c9358591a12813ec5bcbcb8e082ddf5fe342`)
  - Result: `1 failed in 1.08s` ([red.log](../../tmp/issue-105/red.log); aggregate 640 mismatches out of 9920 variants vs 0 on current code).
- **Full test suite command**:
  `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_77ae3695` (command-local `TMPDIR/TEMP/TMP` at `tmp/card-temp`)
  - Result: `2709 passed, 9 skipped, 13 deselected, 48 warnings in 317.36s (0:05:17)` ([full.log](../../tmp/issue-105/full.log)).
- **Standards validation**:
  - `uv run dt profiles check`: `profiles 3` OK.
  - `uv run dt schemas --check`: `schemas 11` OK.

## 4. Evaluation Suite & Procedural Evidence Gaps

- **Initial Evaluation Commands & Historical Baseline**:
  - `uv run dt evals --suite regression --output tmp/issue-105/regression-evals`
  - `uv run dt evals --suite regression --branch improve/hyp-91 --output tmp/issue-105/adoption-regression-evals`
  - Output: `0 passed, 0 failed, 10 not measured, exit code 2` for both initial runs ([`regression-report.json`](./issue-105-evidence/regression-report.json), [`adoption-regression-report.json`](./issue-105-evidence/adoption-regression-report.json)). Initial reports retain these historical 0/0/10 counts because the current PR did not yet exist at the time of those runs.
- **Available-Evidence Evaluation Command**:
  ```bash
  gh pr view 104 --repo artsafro/AGR-DigitalTwin-pilot --json body,comments > logs/pr/improve-hyp-91/view.json
  gh pr diff 104 --repo artsafro/AGR-DigitalTwin-pilot > logs/pr/improve-hyp-91/diff.patch
  uv run dt evals --suite regression --branch improve/hyp-91 --main C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_77ae3695 --output tmp/issue-105/adoption-available-evals-native
  ```
- **Final Available Evidence Output**:
  - Result: `3 passed, 0 failed, 7 not measured, exit code 2` ([`adoption-available-report.json`](./issue-105-evidence/adoption-available-report.json), [`adoption-available-evals-native/report.json`](../../tmp/issue-105/adoption-available-evals-native/report.json)).
  - **Passed Tasks (3)**: PR trace (`pr-agent-trace`: present, 10 fields), numeric literals (`pr-numeric-literals`: 0 new unreferenced literals), and review rounds (`pr-review-rounds`: 1 round $\le$ 3).
  - **Unmeasured Tasks (7)**: `branch-name`, `dcc-skill-loaded`, `engine-checked`, `failure-stop`, `no-hook-denial`, `routine-question`, `source-inspected` — unmeasured absent supported saved Claude JSONL transcripts (Hermes/agy transcript formats are unsupported; synthetic transcripts are prohibited).
- **Evidence Discovery & Procedural Assessment**:
  - The `--main` flag redirects evidence discovery to the authorized worktree for captured PR snapshots; the original main checkout was searched and also had no matching transcripts.
  - No outside-workspace writes were performed.
  - No grader changes were made; `--references` is not required.
  - This available result supersedes initial missing PR snapshot evidence, but does not constitute a procedural 100% pass (exit code 2; 7 unmeasured tasks).
  - A missing transcript is not zero failures or zero hook denials; transcripts are never fabricated.

## 5. Evidence Artifact Index

Stable evidence files are preserved in `./issue-105-evidence/` (copied from `tmp/issue-105/`):

| Artifact Description | Temporary Path | Stable Repository Path |
|---|---|---|
| Generator summary JSON | [`tmp/issue-105/generated.json`](../../tmp/issue-105/generated.json) | [`generated.json`](./issue-105-evidence/generated.json) |
| Targeted pytest log | [`tmp/issue-105/targeted.log`](../../tmp/issue-105/targeted.log) | — |
| RED baseline pytest log | [`tmp/issue-105/red.log`](../../tmp/issue-105/red.log) | — |
| Full pytest suite log | [`tmp/issue-105/full.log`](../../tmp/issue-105/full.log) | — |
| Initial regression eval report (0/0/10) | [`tmp/issue-105/regression-evals/report.json`](../../tmp/issue-105/regression-evals/report.json) | [`regression-report.json`](./issue-105-evidence/regression-report.json) |
| Initial adoption eval report (0/0/10) | [`tmp/issue-105/adoption-regression-evals/report.json`](../../tmp/issue-105/adoption-regression-evals/report.json) | [`adoption-regression-report.json`](./issue-105-evidence/adoption-regression-report.json) |
| Final available adoption eval report (3/0/7) | [`tmp/issue-105/adoption-available-evals-native/report.json`](../../tmp/issue-105/adoption-available-evals-native/report.json) | [`adoption-available-report.json`](./issue-105-evidence/adoption-available-report.json) |
