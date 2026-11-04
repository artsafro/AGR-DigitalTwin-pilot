# Why worker worktrees run the full suite without .claude/settings.json (13 false failures)

Card t_b67ee728. Report only; no code, hook or permission change. Everything below was verified by me
(commands run, code read) unless marked "claim".

## Summary

- `.claude/settings.json` is tracked on origin/main (blob d5bd2455) and is **present** in a fresh worktree
  (checked `t_b67ee728`, `t_b7013e47`, `t_26515539`: file there, no skip-worktree `S` flags, `git ls-files -d`
  empty, `core.sparseCheckout` unset, `git check-ignore` empty). Worktree creation is not the cause.
- Cause: the Cursor wrapper **moves the file away on purpose** for the whole Cursor run and restores it in
  `finally`: `C:/Users/artsafro/hermes_kanban/scripts/cursor-run.ps1:36-40` (hide), `:121-122` (restore).
  Reason in its header (`:16-24`): Cursor imports Claude hooks from that file and then denies every write.
- The wrapper's own run includes the full suite the Cursor CLI executes (task says "run the full suite"),
  so during that window `settings.json` does not exist. Exactly 13 tests read it and fail.
- Reproduced: hiding the file by hand in one worktree and running the 8 files gives **13 failed, 373 passed,
  7 skipped**; with the file present **386 passed, 7 skipped**.
- A killed wrapper skips `finally`: `t_e15b15fa` still has `.claude/settings.json.cursor-hidden` and no
  `settings.json` (worktree dated 00:07, left behind). Such a worktree fails the same 13 for any later run too.
- Share of the non-zero `suite_slot` exits explained: **not measurable** from the log (see below). The 13
  failures are a small constant, not the bulk of the exits.

## Findings

### 1. Worktree state (verified)

| worktree | `.claude/settings.json` | skip-worktree / deleted / sparse |
|---|---|---|
| t_b67ee728 | present | none |
| t_b7013e47 | present | none |
| t_26515539 | present | none |
| t_e15b15fa | **only `settings.json.cursor-hidden`** | `git ls-files -d` lists `.claude/settings.json` |

`git ls-tree origin/main .claude/settings.json` -> `100644 blob d5bd2455...`. So the file is deleted in the
working tree by a process, not missing from the checkout.

### 2. Hermes worktree creation path (verified)

`grep` for `settings.json` in `C:/Users/artsafro/hermes_kanban/scripts/*.ps1|*.py` finds only `cursor-run.ps1`.
`C:/Users/artsafro/.hermes/claude-code` has no match for `settings.json` or `cursor-hidden`. No sparse or
skip-worktree handling exists on the creation path. Only `cursor-run.ps1` touches the file.

### 3. The 13 failing node ids (verified, run once, file hidden by hand, restored after)

```
tests/test_pipeline_gate.py::test_settings_register_the_gate_for_runs_and_writes
tests/test_usage_hooks.py::test_hooks_are_wired
tests/test_subagents.py::test_subagent_hooks_are_wired
tests/test_context_watch.py::test_hook_is_wired
tests/test_session_context.py::test_hooks_are_wired
tests/test_harness_inventory.py::test_every_settings_hook_has_a_row
tests/test_harness_inventory.py::test_a_hook_without_a_row_fails
tests/test_harness_inventory.py::test_documentation_correction_keeps_all_guard_inventory_rows_and_hook
tests/test_pi_guard_adapter.py::test_names_fields_cwd_and_project_root_match_claude[bash-Bash-tin0-expected0]
tests/test_pi_guard_adapter.py::test_names_fields_cwd_and_project_root_match_claude[powershell-PowerShell-tin1-expected1]
tests/test_pi_guard_adapter.py::test_names_fields_cwd_and_project_root_match_claude[write-Write-tin2-expected2]
tests/test_pi_guard_adapter.py::test_names_fields_cwd_and_project_root_match_claude[edit-Edit-tin3-expected3]
tests/test_pi_guard_adapter.py::test_names_fields_cwd_and_project_root_match_claude[edit-Edit-tin4-expected4]
```

`tests/test_guard.py` also mentions the file but stayed green. `test_ground_site_settings.py` is unrelated
(site settings).

### 4. Share of the non-zero suite_slot exits (verified counts, attribution not possible)

`C:/Users/artsafro/hermes_kanban/kpi/suite_slot_runs.jsonl`: 320 runs, 167 exit 0, 153 non-zero
(144 exit 1, 3 exit 4, 3 exit 2, 1 each 127, 0xC0000142, 1073807364). The row keeps only card, timing and
exit code: no failure count or test ids. The task text quotes 134/300; the file has grown since. So how many
exits the 13 explain cannot be computed from the log. Bound: the 13 only matter for runs made while the
wrapper hid the file (Cursor-driven cards) or in a worktree left with `.cursor-hidden`. An exit 1 with more
than 13 failures has another cause. To measure it the log needs the pytest summary (see proposal 3).

## How it applies to this repository

Files that read `.claude/settings.json`: `tests/test_pipeline_gate.py`, `test_usage_hooks.py`,
`test_subagents.py`, `test_context_watch.py`, `test_session_context.py`, `test_harness_inventory.py`,
`test_pi_guard_adapter.py`. Workers currently note "13 failures from the wrapper" by hand in each PR; the
reviewer cannot tell them from real regressions.

## Proposed fixes

1. **Hermes config (owner: kanban/wrapper owner; touches hooks/permissions -> USER DECISION).** Make the
   wrapper hide `settings.json` only while Cursor edits, and have the driver run the full suite after the
   wrapper exits (file restored), i.e. tell Cursor to run only affected tests and let `suite_slot.py` run
   the full suite from the driver. Effort S, removes the 13 and the leftover-file risk when the run is
   killed. Also add a restore step to the Hermes task start (`mv *.cursor-hidden`) for abandoned worktrees.
2. **Pilot test skip (owner: pilot tests).** Mark the 13 tests `skipif` when `.claude/settings.json` is
   missing. Effort S but weakens the guard: a deleted settings file would pass silently. This conflicts with
   the fail-closed rule and edits guard-related tests -> **USER DECISION**; not recommended.
3. **KPI (owner: kanban scripts, no guard impact).** `suite_slot.py` `log_run` (`:141`, call `:210`) records
   the pytest summary line and failed count, so "N of M exits are the 13" becomes measurable. Effort S.

Recommendation: 1 + 3.

## Proposed next tasks

- **Run the full suite after the wrapper restores the file** (proposal 1). Scope: change the Cursor card
  recipe and `cursor-run.ps1` finally-path so the driver, not Cursor, runs the full suite; recover
  `.cursor-hidden` leftovers. Value high, effort S. Archive: no roadmap link (tooling).
- **Record pytest summary in `suite_slot_runs.jsonl`** (proposal 3). Value medium, effort S.
  Archive: no roadmap link.

## Open questions for the user

1. Approve proposal 1 (changes how the Cursor wrapper and its permissions interact with the Claude hooks)?
2. Is the leftover `t_e15b15fa/.claude/settings.json.cursor-hidden` safe to restore (I did not touch it)?
3. Do you accept that proposal 2 (skip) is rejected as it weakens the guard?

## Not measured

Share of the 153 non-zero exits explained; whether other cards' worktrees besides `t_e15b15fa` hold
`.cursor-hidden` leftovers (I inspected 4 worktrees only). Sources: local code and logs only, no web sources.
