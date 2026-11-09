# Research: which `tests/agr_mcp` test fails 1 in 13 runs with `PytestUnhandledThreadExceptionWarning`

## Summary

The flaky failure flagged as P3-3 on PR #1126 did **not** reproduce here: **0 / 20** full
`tests/agr_mcp` runs (plus 25 targeted `test_agr_mcp_locks_release.py` and 25 thread-test loops, i.e.
**0 / 70** total) all passed under
`-W error::pytest.PytestUnhandledThreadExceptionWarning`. The failure is a rare, load/scheduling-dependent
race, not a deterministic bug. The mechanism is fully identified: pytest 9.1.1 globally replaces
`threading.excepthook`, so an unhandled exception in any worker thread becomes a
`PytestUnhandledThreadExceptionWarning` that — with `-W error` — fails the test at the next
`pytest_runtest_*` phase boundary. The candidates are the `tests/agr_mcp` race tests whose thread targets
guard only `locks.LockBusy` and call timed `threading.Barrier.wait` / `Event.wait` (or, in the new
`test_agr_mcp_locks_release.py`, whose `_o_excl` catches only `FileExistsError`): a rare
`threading.BrokenBarrierError` or a transient Windows `OSError` escapes the thread and surfaces as the
flaky warning. One S-size fix is proposed (broaden the thread-target guards so exceptions are reported
deterministically in the owning test) with a RED test.

## Findings

### 1. The warning is produced by pytest, not by agr_mcp

Verified by reading the installed pytest 9.1.1 source
(`.venv/Lib/site-packages/_pytest/threadexception.py`, project venv):

- `pytest_configure` (line 132) installs `threading.excepthook = functools.partial(thread_exception_hook, ...)`
  (line 137). This fires for an unhandled exception in **any** thread — daemon or not.
- `thread_exception_hook` (line 92) formats the traceback and appends a `ThreadExceptionMeta` to a per-session
  deque (`config.stash[thread_exceptions]`).
- `collect_thread_exception` (line 38) is called from `pytest_runtest_setup` / `pytest_runtest_call` /
  `pytest_runtest_teardown` (lines 141/146/151, `trylast`). It pops the deque, calls
  `warnings.warn(PytestUnhandledThreadExceptionWarning(msg))` (line 58), and — because the warning is an
  error under `-W error` — re-raises it (`raise errors[0]`, line 70). The raise happens inside a runtest
  hook, so **the current test fails**.

Consequence: the failure is attributed to whichever test is at the next setup/call/teardown boundary after
the thread raises. The thread owners in `tests/agr_mcp` all `join()` their threads with a timeout before the
test returns, so the raise normally lands on the owning test itself — the "unknown" nodeid in P3-3 is just
the reviewer's truncated log, not a pytest mis-attribution. The flakiness is the *rare triggering condition*,
not a random nodeid.

### 2. The trigger is a rare race exception escaping a narrow `except`

The `tests/agr_mcp` thread targets that can raise an unhandled exception are the ones whose `try` guards only
`locks.LockBusy` (or nothing), while calling timed `threading.Barrier.wait` / `Event.wait`:

| Site (file:line) | Thread | daemon | Guard | Escape path |
|---|---|---|---|---|
| `tests/agr_mcp/test_agr_mcp_locks_release.py:66` | `racer` (`locks._release` + `_o_excl`) | no | `_o_excl` catches `FileExistsError` only (line 43) | transient Windows `PermissionError`/`OSError` from `os.open`/`os.write` |
| `tests/agr_mcp/test_agr_mcp.py:502` (`test_two_concurrent_reclaimers_of_one_stale_lock_exactly_one_wins`) | `worker` | no | `except locks.LockBusy` (line 497) | `both_tried.wait()` = `Barrier(2, timeout=10)` → `threading.BrokenBarrierError`; any non-`LockBusy` from `locks.hold` |
| `tests/agr_mcp/test_agr_mcp.py:670` (`test_odd_lock_input_is_busy_or_error_and_never_two_holders`) | `both` | no | `except locks.LockBusy` (line 667) | `barrier.wait(5)` is **outside** the `try` (line 663) → `BrokenBarrierError` |

Lower risk (daemon threads that already catch `Exception` broadly and record into a shared `errors` list):
`test_agr_mcp.py:614-616` (`test_restore_rename_race_cannot_give_two_holders`, `thread_b`/`thread_a`),
`:752` / `:820` (`*_seed_896`), `:923` (`test_stale_mutex_unlink_by_name_cannot_admit_two`, `run`),
`:1103` (`test_probe_mutex_exclusivity_seed_972`, `run_hold`).

`src/agr_mcp` itself starts threads only in the Max-side daemon
(`max_side/agr_dock.py:194`, `max_side/agr_listener.py:78/111/124`), all `daemon=True` and not exercised by
the `tests/agr_mcp` unit run; they are not the subject here.

### 3. The reviewer's observation (source)

`gh pr view 1126 --comments` (repo `artsafro/AGR-DigitalTwin-pilot`), review round 1 verdict line:

> P3-3: 1 of 13 `tests/agr_mcp` runs gave `1 failed` with a `PytestUnhandledThreadExceptionWarning`. That
> run's output was cut, so the test name is unknown. 12 later runs, including 5 with `-rf`, were all green,
> so I can't attribute it to this diff. Noted only.

The reviewer could not attribute it to PR #1126 either. PR #1126 is already merged (`dfc82866`), so this
report runs at the post-merge `main` head.

### 4. Reproduction attempts (all green)

Command (as specified by the card), run in the worktree on branch
`docs/research-agr-mcp-flaky-unhandled-thread-exception` at `main` head `dfc82866`:

```
uv run --frozen pytest tests/agr_mcp -q -p no:cacheprovider -rfE \
  -W error::pytest.PytestUnhandledThreadExceptionWarning --basetemp=C:/x/t_db1b8447
```

- **20 full `tests/agr_mcp` runs**: `170 passed, 1 skipped, 1 deselected` each, 0 failures
  (logs `C:/x/ev_t_db1b8447/run_1.txt` … `run_20.txt`).
- **25 × `test_agr_mcp_locks_release.py`** (the new PR #1126 module, `23 passed` each): 0 failures.
- **25 × the 7 thread-spawning tests of `test_agr_mcp.py`** via `-k` (barrier/event races): 0 failures.

Total **0 / 70**. The `1 in 13` rate was not reached on this machine (fast, otherwise idle), consistent with
a scheduling/load-dependent race that is far rarer here than on the review box.

### 5. `-p no:randomly` and `--count` are not available

Verified in the project venv (`pkgutil.iter_modules`): only `pytest` (9.1.1) and `pytestqt` are installed.
`pytest-randomly` (`-p no:randomly`) and `pytest-repeat` (`--count`) are **not** installed, so those two card
steps were replaced by the manual 25× loops above.

## How it applies to this repository

- `tests/agr_mcp/test_agr_mcp.py` — lock-race/interleaving tests with worker threads; the escape paths are
  `Barrier`/`Event` timeouts and non-`LockBusy` exceptions, guarded by a narrow `except locks.LockBusy`.
- `tests/agr_mcp/test_agr_mcp_locks_release.py` — the new PR #1126 module; the `racer` thread (line 66) calls
  `_o_excl` whose `try` catches only `FileExistsError` (line 43), leaving a transient Windows `OSError` free
  to escape into `threading.excepthook`.
- `src/agr_mcp/locks.py` — the code under test; its release/reclaim paths are designed to "never raise"
  (verified: `_release` returns after a bounded sentinel wait and reports to stderr), so the flaky exception
  comes from the *test harness* (timeouts/OS errors in the racy interleaving), not from `locks.py` itself.
- `pyproject.toml` `[tool.pytest.ini_options]` (line 43) has only `addopts`; no `filterwarnings` — the
  `-W error::pytest.PytestUnhandledThreadExceptionWarning` that turns the warning into a failure comes from
  the review/card command line, not from repo config.

## Proposed next tasks

### 1. Harden the `tests/agr_mcp` thread targets so a race exception is reported deterministically (S)

Scope: in `tests/agr_mcp/test_agr_mcp_locks_release.py`, broaden `_o_excl`'s guard from
`except FileExistsError` to `except OSError as exc` that records into a shared `errors` list the interleaving
test asserts empty (or wrap the `racer` lambda in `try/except BaseException` doing the same). Optionally do
the same for the `Barrier.wait`/`Event.wait` calls in `test_agr_mcp.py:491-499` and `:662-668` so
`BrokenBarrierError`/timeout is surfaced as a named assertion in the owning test instead of leaking to
`threading.excepthook`. This is a test-only change; no `src/` edit.

Value/effort: S (one file, a few lines). It removes a 1-in-13 flaky red that the reviewer flagged, and makes
any future race fail with the owner's name instead of `PytestUnhandledThreadExceptionWarning`.

RED test idea (before the fix): monkeypatch `os.open` inside `_o_excl` (or `os.write`) to raise
`PermissionError` once; assert that `test_reviewer_interleaving_lstat_gap_gives_one_holder` fails with the
`OSError` surfaced in `holders`/`errors` (deterministic, owner-named) rather than emitting a
`PytestUnhandledThreadExceptionWarning` under `-W error`. After the fix the OSError is recorded and the
existing one-holder assertion fails; before the fix it escapes the racer thread as the warning.

**Archive: no roadmap link** — none of the open `roadmap`-labelled issues (textures, Flora, MAF,
roof-equipment, showcase scenes, Vatutino site, capability roadmap) is about test flakiness or CI hygiene, so
this proposal does not honestly advance one.

## Open questions for the user

1. Was the P3-3 run made on a loaded machine / a different box than this one? The 1-in-13 rate suggests
   scheduling pressure; a `threading.Barrier`/`Event` timeout is the most plausible trigger and only fires
   when a rendezvous is missed under load.
2. Do you want the S fix (broaden the thread guards) applied, given 0/70 reproduced here? It is defensive —
   it converts an unreproducible warning into a deterministic named failure — but it edits test code that is
   currently green.
3. Should the `-W error::pytest.PytestUnhandledThreadExceptionWarning` flag be added to `addopts` /
   `filterwarnings` so every run (not just review/card runs) treats a leaked thread exception as an error?
   Today only the review command uses it, so a leak can silently pass as a warning in the normal suite.

---

## Agent trace

- Sessions: 1 (kanban worker t_db1b8447, dt-worker-deepseek)
- Written by: deepseek-v4-pro (Hermes kanban worker)
- Subagents: none
- Skills: none loaded (research-only card)
- Commands: `git`, `grep`/`cat`/`read` over `tests/agr_mcp/`, `src/agr_mcp/`,
  `.venv/Lib/site-packages/_pytest/threadexception.py`; `uv run --frozen pytest tests/agr_mcp ...`
  (20 full runs + 25 locks_release + 25 thread-test loops, all green); `gh pr view 1126 --comments`,
  `gh issue list`
- Hook denials: none
- Retries: none (board was paused/resumed; continued the 20-run loop from run_4)
- Context at handover: branch `docs/research-agr-mcp-flaky-unhandled-thread-exception`
  (worktree `t_db1b8447`) at main head `dfc82866`
- Duration: ~45 min (incl. 70 pytest runs)
- Commits: 1
