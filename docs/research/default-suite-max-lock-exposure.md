# Default suites: why does an installed-Max selftest make unrelated cards red?

## Summary

The default pytest suite (`-m 'not blender and not dcc and not acad and not perf'`) contains two
**unmarked** tests that silently become real 3ds Max smoke tests whenever 3ds Max is installed on the
host, because their guard is "skip only when Max is absent" instead of "skip unless an explicit native
lane is requested". When a real `3dsmaxbatch.exe` exists, `max_adapter.default_adapter()` returns
`BatchAdapter()`, whose `selftest()`/`build()` run `dcc_batch.py` against the **shared, cross-profile,
cross-card** lock `%LOCALAPPDATA%\Temp\agr-3dsmax-session.lock`, waiting only `--wait 60` seconds. If any
production review publisher (or another card) already holds that lock, the test's `dcc_batch.py` call
returns exit 3 (`busy`, `held_by=review-publisher`) after 60 s, the adapter raises `RuntimeError`, and an
otherwise pure-Python card fails on Max lock contention — exactly the receipts in PR #465 and PR #452. This
is a **test-classification gap** (native smoke leaked into the default lane) combined with a **lock-identity
collision** (the fallback card name `review-publisher` is shared by both the test and the production
publisher when `HERMES_KANBAN_TASK` is unset). It is not a genuine adapter defect and not a scheduling
slot problem; it is a mis-classified test that acquires a shared resource in the default lane.

## Findings

### F1 — Two default-selected tests launch real Max when it is installed

`pyproject.toml` selects the default suite by marker exclusion only
(`addopts = "-m 'not blender and not dcc and not acad and not perf'"`, lines 32-41); there is no
directory-based exclusion and no `native` marker. Two tests are **not** marked `dcc`, so they always run:

- `tests/test_review_publish.py::test_max_dependent_merge_skips_when_max_absent` (lines 526-536):
  ```python
  adapter_mod = _load("max_adapter")
  if adapter_mod.max_batch_path() is None:
      pytest.skip("3ds Max is not installed")
  ...
  result = adapter_mod.default_adapter().selftest(...)
  assert result["cameras"] >= 1 ...
  ```
  The guard is inverted relative to the suite: it skips only when Max is *absent*, so on an installed-Max
  host it performs a **real** headless selftest (FBX export + import + camera + render readback) through
  `default_adapter()`.

- `tests/test_review_round2.py::test_real_max_keeps_fbx_mesh_named_review_camera` (lines 83-117): same
  inverted guard, then `_run_max(...)` (lines 74-80) which runs `dcc_batch.py ... --wait 120 --timeout 600`
  three times (export, build, readback).

Source SHAs (HEAD `fc0a1fea4589ca48a59db6534a100f2fad87f517`): `tests/test_review_publish.py` blob
`0b3f183f28c0420c7d22aede8eb4eda246899a54`; `tests/test_review_round2.py` (read 2026-10-21). Both files'
last-touching commits are `307c15609e4f49e3f46567569b79f76441e3c358` (wip) and
`6262fc155a69f1160d81600f6b2258ab843fea84` (fix) respectively.

### F2 — Adapter selection always picks the headless batch lane; the live lane is dead

`tools/review/max_adapter.py:73-78`:
```python
def default_adapter():
    if max_batch_path() is not None:
        return BatchAdapter()   # live = False
    raise RuntimeError("3ds Max is not available")
```
`max_batch_path()` (lines 15-20) probes `C:/Program Files/Autodesk/3ds Max {2026,2024}/3dsmaxbatch.exe`.
`default_adapter()` **never** returns `LiveAdapter` (lines 69-70); `LiveAdapter` is unused, and
`tools/review/README.md:63-69` confirms "The live adapter is not selected: the report writer is forbidden
by live SAFE_MODE". So the only adapter reachable from the default suite is the headless batch lane that
acquires the shared session lock. Blob `f6268842cd98a2fcb1aedfff7796020375961e4e`.

### F3 — Shared lock key and the `review-publisher` identity collision

`tools/review/max_adapter.py:50` reads the card name from the environment with a fixed fallback:
```python
card = os.environ.get("HERMES_KANBAN_TASK", "review-publisher")
```
and passes it as `--card` to `dcc_batch.py` (lines 52-59). `dcc_batch.py` (external, read-only,
`C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py`) derives the lock key at lines 34-35 and 149:
`%LOCALAPPDATA%\Temp\agr-3dsmax-session.lock` — **one lock per program, shared by every profile and every
card**. The production publisher `tools/review/publish.py:21` calls the same `default_adapter()`, so it
uses the **same** lock and the **same** `review-publisher` fallback when its process has no
`HERMES_KANBAN_TASK`.

I verified (shell env) that `HERMES_KANBAN_TASK` is **unset** in the agent's terminal environment, so
every subprocess — `suite_slot.py` (defaults `--card` to `?`), the full-suite pytest child, and the
production `publish.py` — falls back to `review-publisher` unless the caller passes `--card` explicitly.
`suite_slot.py` (external, read-only) passes `--card` only to its own slot/ticket naming
(lines 152-155); the pytest command it runs (`subprocess.call(cmd)`, line 203) inherits the unset env, so
the selftest inside pytest still uses `--card review-publisher`. The leftover work dir
`%LOCALAPPDATA%\Temp\agr-3dsmax-review-publisher` (mtime окт 20 11:04) is direct evidence that a
production run with card `review-publisher` acquired that shared session.

### F4 — Timeout boundaries: `--wait 60` loses to a healthy long holder

`max_adapter.py:57-59` invokes `dcc_batch.py ... --timeout 600 --wait 60 --version <v>` for the batch lane.
In `dcc_batch.py:56-85`, `acquire()` waits up to `wait`=60 s for the lock; it reaps a stale lock **only**
if the recorded holder PID is dead, or if the lock file age exceeds `holder_timeout + 300` (the *holder's*
timeout 600 → 900 s, per the #223 fix comment at lines 65-66). A healthy production job (a real
`review-publisher` run, which legitimately takes minutes) is therefore **not** reaped, and the 60 s waiter
gives up: `dcc_batch.py` prints `{"status": "busy", "held_by": "review-publisher"}` and returns exit 3
(lines 150-157). `max_adapter._call` (lines 23-25) treats any nonzero return as failure, and
`BatchAdapter._run` raises `RuntimeError("Max adapter failed: ...")` (lines 61-65), which
`common.publish`/the test surface as a red test. This is precisely the `held_by=review-publisher` signature
in the two receipts.

The live bridge (`max_exec.py`, external, read-only) uses a **different** lock
`agr-3dsmax-live.lock` (line 27), so live/batch contention is not the issue here — the default lane never
reaches the live adapter.

### F5 — Documented historical busy results vs unmeasured present state

Both original receipts are recorded in the merged PR review comments (I read them via `gh`, did not
synthesize any baseline):

- **PR #465** (`improve/issue-461-eval-geometric-mutation-set-planted-defe`, merged 2026-10-21T10:02:40Z,
  merge `e5f9f377337375240aac7be3beeb4b3155b91740`): author-only full suite at `4491e52` reported
  **12045 passed / 1 failed / 21 skipped / 170 deselected**, 1449.43 s; the single failure is
  `tests/test_review_publish.py::test_max_dependent_merge_skips_when_max_absent`, shared Max session busy
  (`held_by=review-publisher`). Reviewer explicitly recorded "No main reproduction ... established; this is
  **not** a green full suite".
- **PR #452** (`improve/issue-432-parity-harness-src-twinqa-flags-what-sin`, merged 2026-10-21T08:13:13Z,
  merge `93e0440a1e13e1ceb7e56f1d51ef08cc69de8a72`): author full suite **11637 passed / 3 failed / 21
  skipped / 101 deselected**; the third failure is "existing Max session lock held by `review-publisher`;
  author detached-base retry passed". The other two are already filed (#453 AGR-index duplicate, #454
  publisher pending-lock race).

Present state (this card): 3ds Max **2026 and 2024 are both installed** (static `-f` check on the exe
paths, no launch), so `default_adapter()` returns `BatchAdapter()` and the two tests would launch real Max.
There is **currently no** `agr-3dsmax-session.lock` file (read-only `ls`), so the lock is free right now;
I did **not** run the selftest, invoke Max, or acquire/remove any lock, so the present selftest result is
**unmeasured** — only the historical receipts and static code are evidence.

### F6 — Inventory of default-selected tests that call (or could call) real Max

| Test | Location | Default suite? | Native launch? |
|---|---|---|---|
| `test_max_dependent_merge_skips_when_max_absent` | `tests/test_review_publish.py:526` | yes (unmarked) | **yes** — `selftest()` → `dcc_batch.py` `--wait 60` |
| `test_real_max_keeps_fbx_mesh_named_review_camera` | `tests/test_review_round2.py:83` | yes (unmarked) | **yes** — `_run_max` → `dcc_batch.py` `--wait 120`, 3 calls |
| `test_max_job_never_deletes_source_nodes_named_like_review_camera` | `tests/test_review_round2.py:62` | yes (unmarked) | no — static read of `max_job.py` source |
| every other `test_review_publish.py` test | `tests/test_review_publish.py` | yes | no — `FakeAdapter` (mocked) |
| `test_benchmark_one_pass_and_fbx`, `test_export_safety_probe` | `tests/dcc/test_batch_export_max.py` | no (`pytestmark = pytest.mark.dcc`, line 22) | yes (explicit dcc lane) |
| `test_synth_scene_one_flora_atlas` | `tests/dcc/test_flora_atlas_max.py:574` | no (`@pytest.mark.dcc` line 569) | yes (explicit dcc lane) |
| 12 `test_*preflight*` / `test_probe_*` / `test_job_guards*` | `tests/dcc/test_flora_atlas_max.py` | yes (unmarked) | no — guard/preflight logic, no `subprocess` Max launch |
| `tests/dcc/test_bpy_benchmark_parity.py` | whole module | no (`pytestmark = pytest.mark.dcc`, line 12) | Blender (not Max) |

Net: exactly **two** default-selected tests perform real Max launches; the rest of the default suite is
mocked or static. The `tests/dcc/` modules that are marked `dcc` are correctly excluded; only the two
`tests/test_review_*.py` tests leak.

## How it applies to this repository

- `pyproject.toml` (lines 32-41): the default-suite selector and marker registry; adding a `native`/reusing
  `dcc` marker here is the single control point. Blob `47b9c4512da602ca4b9c75a7bad8fc4053fbc9a5`.
- `tools/review/max_adapter.py:50-59, 73-78`: adapter selection and the `--card` fallback; the lock-identity
  fix and the "absence path without native launch" contract both live here.
- `tools/review/common.py` (blob `f8d8536d9dfb8ec1a76ba6ec541bb9c276e80521`): `publish()` surfaces adapter
  `RuntimeError` as `ReviewError`; the "busy → named non-success" contract must be distinguishable there
  from a genuine adapter failure.
- `tests/test_review_publish.py:526-536` and `tests/test_review_round2.py:83-117`: the two tests to
  reclassify.
- External (read-only, not in this repo): `C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py` (shared
  lock, exit 3 `busy`), `max_exec.py` (separate live lock), `suite_slot.py` (slot/queue only; does not
  propagate `HERMES_KANBAN_TASK` into the pytest child).

## Proposed next tasks

At most two bounded fixes (proposals only; marker naming/selection, scheduling policy and
live/native-lane adoption belong to a subsequent decision — no skips/xfails or edits in this card).

### 1. Reclassify the real-Max smoke tests out of the default suite

**Scope.** Add a `native` marker (or reuse `dcc`) and tag the two tests
(`test_max_dependent_merge_skips_when_max_absent`, `test_real_max_keeps_fbx_mesh_named_review_camera`) so
the default suite never acquires the shared Max session. Keep the current inverted guard's intent by
rewording it to a positive "requires installed Max" skip; do **not** delete the native assertions.

**Input → expected output contract.**
- Input: default suite (`-m 'not blender and not dcc and not acad and not perf'`), Max installed →
  expected: both tests are **not collected**, zero `dcc_batch.py`/lock acquisition, no native launch.
- Input: explicit native lane (`-m native`, Max installed) → expected: original assertions retained —
  `selftest()` returns `cameras >= 1`, `materials >= 1`, a non-empty `.max` scene, a PNG preview starting
  `\x89PNG`; the camera-name collision readback asserts `geometry == ['Control_Box','Review_Camera',
  'Review_Target']` and `cameras == 1`.
- Input: native lane, Max absent → expected: skip (existing absence path), **no** native launch.

**Value/effort.** S (small: a marker + two decorators + one selector line). High value: removes the
recurring false-red from every full-suite receipt. **Advances #337** (Old PRs round 2 / merge-gate hygiene:
this exact failure is what keeps the full suite "NOT green" and blocks re-review on current head).

### 2. Distinct lock identity and named "busy" non-success for native smoke

**Scope.** Stop the native smoke from colliding with the production publisher: pass an explicit, distinct
`--card` (e.g. the real task id, never the `review-publisher` fallback) so a test's session never contends
with a production review job; and map a `dcc_batch.py` exit 3 (`busy`, `held_by=...`) to a **named
non-success** (skip/xfail-with-reason, never a `pass` and never an unrelated assertion failure) surfaced
through `common.publish` as a distinguishable `ReviewError`.

**Input → expected output contract.**
- Input: native smoke, lock held by a healthy long holder (`held_by=review-publisher`) →
  expected: named non-success carrying `held_by` and the lock path; **never** counted as a native pass and
  **never** reported as a generic `RuntimeError("Max adapter failed")` that reads like a code failure.
- Input: native smoke, lock free → expected: original assertions run and pass unchanged.
- Input: distinct card id passed → expected: no contention with a concurrent production `review-publisher`
  on the same host.

**Value/effort.** M (medium: touches `max_adapter._run`, `dcc_batch` return-code parsing, and one
`common.publish` error surface). High value: makes a true contention event legible instead of a false red.
**Advances #337** (same merge-gate hygiene; complements fix 1 so that even an explicitly-run native lane
cannot masquerade contention as a product failure).

## Open questions for the user

1. Marker policy: should the two tests move under the existing `dcc` marker (keeps a single native lane,
   consistent with `tests/dcc/`) or get a new `native` marker distinct from `dcc`/`blender`/`acad`? This
   decision (not made here) determines the exact `addopts` string.
2. Should the production `review-publisher` keep its `review-publisher` fallback card name, or must every
   native call require an explicit `HERMES_KANBAN_TASK`/`--card` (fail closed when unset)? The collision
   F3 disappears only if the fallback is removed or the test side always passes a distinct id.
3. On `busy`, is a `pytest.skip("busy held_by=...")` acceptable in the explicit native lane, or must it be
   a distinct outcome that the merge gate can flag separately from a genuine native failure?
