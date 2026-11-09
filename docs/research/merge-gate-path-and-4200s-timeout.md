# Merge-gate suite: which path runs it (merge<date> vs automerge) and does the 4200 s timeout kill it

## Summary

The full suite that gates merges runs through **two separate paths**, not one. The `merge<date><letter>`
rows in `kpi/suite_slot_runs.jsonl` are written by the **manual merge-batch** script
(`~/.hermes/skills/agr-kanban-orchestration/scripts/merge_batch.py`, line 69 `--card merge<tag>`), which the
orchestrator runs on the user's explicit merge command and which has **no timeout**. The `--card automerge`
path is a *different* script — `agr_automerge.py` (the cron "agr-pilot automerge" job, every 30 min) — and it
has **never** written a single row: `grep -c automerge kpi/suite_slot_runs.jsonl` = 0, no `automerge_*.json`
receipt has ever been produced, and the two documented runs were killed by the **cron's own 3600 s script
timeout** (`"Script timed out after 3600s"`, 2026-11-05 05:58 and 2026-11-06 03:58). The script's own
`timeout=4200` (line 79) is effectively **dead code**: it caps only the pytest subprocess, but the cron's
3600 s cap on the whole script fires first (slot wait + `uv sync` + pytest already exceed 3600 s). Either way
the suite verdict is lost — no green, no red, no `STOP_AUTOMERGE` pause file. The 4200 s figure is also
**below the observed suite wall-time**: 9 gate rows exceed 4200 s (max 5743 s), and 7 have a pytest-reported
time above 4200 s.

## Findings

### F1 — `merge<date>` rows come from `merge_batch.py`, not from any `hermes_kanban/scripts/` file

The `merge20261020b … merge20261106d` cards in `kpi/suite_slot_runs.jsonl` (60 gate rows) are written by the
manual merge-batch procedure. The script lives **outside** `hermes_kanban/scripts/` — in the Hermes skill:

- `C:\Users\artsafro\.hermes\skills\agr-kanban-orchestration\scripts\merge_batch.py:69`
  `slot = [sys.executable, … "suite_slot.py", "--card", f"merge{tag}", "--"]` — the `--card merge<tag>`
  label (tag = `--tag 20261021n` etc. from the orchestrator's user-approved merge command).
- `merge_batch.py:70-72` — `subprocess.run(..., capture_output=True, …)` with **no `timeout=`**. The docstring
  line 12 states why: *"with NO timeout (a fixed timeout dies while waiting for a slot)"*.
- `merge_batch.py:98` — writes the receipt `kpi/manual_merge_<tag>.json` (the status push reads these).
- `C:\Users\artsafro\hermes_kanban\scripts\suite_slot.py:243-246` — `log_run({… "card": a.card …})` appends the
  row to `kpi/suite_slot_runs.jsonl` (path at line 130). This is the single writer of every row in that file.

Verified by reading all three files and by `grep` over `hermes_kanban/scripts/`, `skills/` and
`docs/pipeline.md` (no `merge_batch.py` there; it is referenced only in `docs/HANDOFF.md:57` and in the
orchestration skill).

### F2 — the cron automerge path is a different script, and it has never completed a suite

- `C:\Users\artsafro\hermes_kanban\scripts\agr_automerge.py:76` — `"--card", "automerge"`;
  `:79` — `timeout=4200`; `:62-89` — `suite_on_main()` runs the suite only from `check_pause()` (line 106,
  red-main re-run) or after merges (line 256, `if merged and not a.dry_run`).
- `kpi/suite_slot_runs.jsonl` has **438 rows, 0 with `card == "automerge"`** (verified with `grep -c`).
- **No `kpi/automerge_*.json` receipt ever existed.** `scripts/agr_status_push.py:158` globs for
  `manual_merge_*.json` *and* `automerge_*.json`, but only `automerge_state.json` exists — and that file
  contains only `{"waiting_digest": "…"}` (the cron's waiting-list fingerprint, written at
  `agr_automerge.py:252-254`), not a suite receipt. `agr_automerge.py` has **no** code that writes a
  `manual_merge`-style receipt; its suite result is only `print`ed to stdout.
- The cron job `f1094b137cee` "agr-pilot automerge" (`no_agent`, `script: "agr_automerge.py"`, interval 30 min,
  488 completions) shows a `last_failure`:
  `"detail": "Script timed out after 3600s: C:\\Users\\artsafro\\.hermes\\scripts\\agr_automerge.py"`.
- Two output files record it: `cron/output/f1094b137cee/2026-11-05_05-58-13.md` and
  `2026-11-06_03-58-13.md`, both `**Status:** script failed` / `Script timed out after 3600s`.

**Hard evidence the suite actually started and was killed mid-run:** the pytest basetemp
`C:/x/automerge` (the `--basetemp=C:/x/automerge` at line 77) is left behind, directory mtime
**2026-11-06 03:56**, full of half-written test dirs (`test_a_…`, `flora-synthetic0`, etc.). pytest was
still running at 03:56; the cron killed the script at 03:58. Because the kill is a hard `TerminateProcess`,
`suite_slot.py`'s `log_run` (its `finally` block, `suite_slot.py:238-246`) never ran — which is exactly why
no `automerge` row exists. `automerge_state.json` mtime 2026-11-06 03:00:27 marks the last time automerge
reached the ≥30-PR threshold and wrote state.

### F3 — what happens on `TimeoutExpired` (and why it is currently pre-empted)

`subprocess.run(..., timeout=4200)` (`agr_automerge.py:77-79`) raises `subprocess.TimeoutExpired` on expiry:

1. The `finally` block (`:87-89`) removes the throw-away worktree and prunes — so the worktree is cleaned even
   on timeout.
2. The exception propagates out of `suite_on_main()` to its callers — `check_pause()` line 106 and `main()`
   line 256 — neither of which has a `try/except` around the call.
3. It reaches the top-level handler `if __name__ == "__main__": try: main() except Exception as e:
   print("agr_automerge error: …"); sys.exit(1)` (`:266-271`).
4. Net effect: **crash with exit code 1, and the red/green verdict is lost** — the `if not green:` branch that
   writes the `STOP_AUTOMERGE` red-main pause file (`:107`, `:260`) is never reached. If the suite was the
   post-merge run, the merges already happened, so a possibly-red `main` is left **un-paused and un-flagged**.

But in practice the 4200 s `timeout=` never fires first: the cron runner caps the **whole script** at
**3600 s** (the failure detail above), and the subprocess the 4200 s guards already includes the slot wait +
`uv sync` + pytest. With pytest alone now 4200–5700 s and a slot wait on top, the 3600 s cap always triggers
first, hard-killing the script (and orphaning the pytest grandchild — `subprocess.run(timeout=)` kills only its
direct child, `suite_slot.py`). So **the binding constraint is the cron's 3600 s, and the 4200 s timeout is
dead code**.

### F4 — two copies of `agr_automerge.py`, and the cron runs the stale one

The card references `scripts/agr_automerge.py`, but the cron resolves `script: "agr_automerge.py"` to a
different file (confirmed by the failure-detail path):

- Cron copy: `C:\Users\artsafro\.hermes\scripts\agr_automerge.py` (14 512 B, dated 2026-10-20).
- Card copy: `C:\Users\artsafro\hermes_kanban\scripts\agr_automerge.py` (14 603 B).
- `diff` shows **only line 78 differs** — the `-m` marker:
  - `.hermes` (cron) copy: `"-m", "not blender and not dcc"`
  - `hermes_kanban` copy: `"-m", "not blender and not dcc and not acad and not perf and not job and not max and not panel_texture and not native_max"`
- Both have `--card automerge` (line 76) and `timeout=4200` (line 79), so the timeout finding holds for either
  copy. The manual `merge_batch.py` gate uses `-m "not blender and not dcc"` too (line 71) — i.e. the cron's
  stale copy still matches the manual gate, but has drifted from the newer `hermes_kanban` copy (the `-m` drift
  that PR #1122 already flagged).

## Gate runs vs 4200 s

`kpi/suite_slot_runs.jsonl`, gate rows (`card` matches `^merge`). `ran_s` is the slot-holder's wall time
(slot acquired → command finished, includes `uv run pytest` startup); `pytest "in X s"` is the pytest-reported
duration from the summary line. Rows above 4200 s are in **bold**.

| card | ran_s (slot) | pytest "in X s" | exit | failed |
|---|---|---|---|---|
| **merge20261106b** | **5743** | **5726.79** | 1 | 4 |
| **merge20261105g** | **5601** | **5586.27** | 1 | 3 |
| **merge20261022d** | **5435** | (no summary) | 0 | — |
| **merge20261106c** | **5114** | **5102.45** | 1 | 4 |
| **merge20261105e** | **4938** | **4921.90** | 1 | 3 |
| **merge20261102g** | **4439** | (no summary) | 1 | — |
| **merge20261105f** | **4358** | **4344.56** | 1 | 4 |
| **merge20261106a** | **4288** | **4276.00** | 1 | 5 |
| **merge20261105a** | **4281** | **4237.87** | 1 | 2 |
| merge20261106d | 3976 | 3946.86 | 1 | 3 |
| merge20261102e | 3784 | (no summary) | 0 | — |
| merge20261102f | 3734 | (no summary) | 0 | — |
| … (48 more rows ≤ 3689 s) | | | | |

**9 of 60 gate rows exceed 4200 s of wall time; 7 have a pytest-reported time above 4200 s.** The card's
three figures — 4344.56 / 5586.27 / 4276.00 s — are exactly the pytest "in X s" values for
`merge20261105f`, `merge20261105g`, `merge20261106a`.

Conclusion: `timeout=4200` is below the *current* suite wall-time. Even in the best case (slot free
immediately), the suite would now be killed at 4200 s; with any slot wait it is killed earlier. It is a latent
bug that would kill the automerge gate every time — except that the cron's 3600 s cap currently fires first.

## How it applies to this repository

None of the implicated scripts live in the pilot repository; they are read-only inputs for this research:

- `C:\Users\artsafro\hermes_kanban\scripts\agr_automerge.py`, `…/suite_slot.py`, `…/kpi/suite_slot_runs.jsonl`,
  `…/kpi/manual_merge_*.json`, `…/scripts/agr_status_push.py`.
- `C:\Users\artsafro\.hermes\skills\agr-kanban-orchestration\scripts\merge_batch.py` (the manual merge gate).
- `C:\Users\artsafro\.hermes\scripts\agr_automerge.py` (the copy the cron actually runs) and
  `C:\Users\artsafro\.hermes\cron\jobs.json` + `output\f1094b137cee\` (the cron job and its failures).

The only artifact in this repository is this report (`docs/research/merge-gate-path-and-4200s-timeout.md`).
The pilot repo itself contributes no code to the merge-gate timing; the fix belongs to `hermes_kanban` /
`.hermes` (out of scope here, and the timeout/path choice is a user decision).

## Proposed next tasks

1. **Fix the automerge suite timeout and align it with the manual merge gate** — S.
   Remove the `timeout=4200` from `suite_on_main()` (or set it well above the worst observed slot-wait +
   suite time), and raise the cron "agr-pilot automerge" job's 3600 s script timeout so the suite can finish;
   optionally make `agr_automerge.py` write a `manual_merge`-style receipt (`-rf`, a `kpi/automerge_<tag>.json`)
   and reuse the no-timeout pattern already proven in `merge_batch.py`. Without this, the automerge path can
   never produce a green/red verdict. Value: closes the two "script failed" failure modes and makes the
   automerge gate actually gate. Effort: S (one line + one cron setting + a short receipt block).
   `Advances #1028` (merge-gate harness).

2. **Reconcile the two `agr_automerge.py` copies so the cron stops running a stale `-m` list** — S.
   The cron resolves `script: "agr_automerge.py"` to `~/.hermes/scripts/`, whose copy still carries the old
   `-m "not blender and not dcc"` marker while `hermes_kanban/scripts/` carries the extended list. Either point
   the cron at the canonical copy or sync the copies, so the automerge gate deselects the same tests as the
   manual gate. Value: removes the `-m` drift (PR #1122 open question) from the automerge path. Effort: S.
   `Advances #1028` (merge-gate harness).

## Open questions for the user

1. Is the intended outcome that the cron automerge **also** runs the full gate suite after a batch (as
   `agr_automerge.py` tries to), or should automerge stop running the suite entirely and leave gating to the
   manual `merge_batch.py` path the user already drives? (The timeout/path choice is a user decision — this
   report changes no scripts.)
2. The cron's 3600 s script timeout is the binding killer, not the 4200 s. Should the automerge job's timeout
   be raised (and to what — 90 min? no limit like `merge_batch.py`?), given the suite alone now takes
   4200–5700 s plus slot wait?
3. Two copies of `agr_automerge.py` are drifting (`.hermes/scripts` vs `hermes_kanban/scripts`). Which is
   canonical, and should the cron be repointed or the copies re-synced?

---

## Agent trace

- Sessions: 1 (kanban worker t_9e41f123, dt-worker-deepseek)
- Written by: deepseek-v4-pro (Hermes kanban worker)
- Subagents: none
- Skills: none loaded (research-only card)
- Commands: `git`, `grep`/`wc`/`stat`/`find` over `hermes_kanban/` and `~/.hermes/`, `gh issue list` /
  `gh pr view`, `python -c` (jsonl analysis of `kpi/suite_slot_runs.jsonl`), `diff`
- Hook denials: none (execute_code blocked in this session; re-done with `terminal` + `python -c`)
- Retries: none
- Context at handover: branch `docs/research-merge-gate-path-and-4200s-timeout` (worktree `t_9e41f123`)
- Duration: ~30 min
- Commits: 1
