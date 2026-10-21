# Research: Why do Cursor runs repeatedly lose `.claude/settings.json` during full suites?

## Summary

The repeated 13-failure "missing `.claude/settings.json`" pattern in full suites is a **direct, by-design
consequence of the current Cursor wrapper's hide window**, not a test path bug and not an unproven environment
effect. `C:/Users/artsafro/hermes_kanban/scripts/cursor-run.ps1` renames `.claude/settings.json` (and
`.claude/settings.local.json`) to `*.cursor-hidden` **before** launching `cursor-agent` (lines 35–42) and only
restores them in a `finally` block **after** the process exits or is killed (lines 117–125). The full suite is a
child process of `cursor-agent`, so it runs entirely inside that hide window and sees the file missing. Seven
test modules hardcode `ROOT = Path(__file__).resolve().parents[1]` and read `ROOT / ".claude/settings.json"`
via `.read_text()`, which raises `FileNotFoundError` when the file is hidden — exactly the 13 failures (9 test
functions, one parametrized ×5). The file is restored on every *normal, error, stall (75) and wall (76)* path;
it is left hidden only when the wrapper **process itself** is killed externally (`finally` skipped) — a separate
defect, distinct from the 13 full-suite failures. No reproduction was run (card forbids Cursor launch and
pytest); the mechanism is proven by read-only source inspection.

## Findings

### F1. The wrapper hides `.claude/settings.json` for the entire run, by design

`cursor-run.ps1` (SHA256 `3cd358c42a2306f11b7187841b9b2baa30a04740e29f7035469b16115324ab9b`, 126 lines,
6778 bytes; verified by reading the file, `sha256sum`):

- **Hide (lines 35–42):** for each of `settings.json` and `settings.local.json`, if
  `<Workspace>\.claude\<name>` exists, `Move-Item -LiteralPath $f -Destination "$f.cursor-hidden" -Force`
  and record `$f` in `$hidden`.
- **Launch (line 60):** `Start-Process ... cursor-agent.cmd ... --workspace "$Workspace"` runs *after* the hide.
- **Restore (lines 117–125):** the `finally` block loops over `$hidden` and
  `Move-Item -LiteralPath "$f.cursor-hidden" -Destination $f -Force` for each that still exists.

The hide is intentional. The script's own header comment (lines 14–23) attributes the reason: Cursor imports the
project's Claude Code hooks from `.claude/settings.json` and, on Windows, wraps them in a PowerShell preamble that
fails (Git Bash `MSYSTEM` markers; bash syntax like `"$CLAUDE_PROJECT_DIR/..."`), with "no opt-out"
(forum.cursor.com/t/166558, forum.cursor.com/t/168129). That attribution is the *wrapper author's claim*, not
re-verified here — no Cursor launch was permitted.

**Proven mechanism (source-read, not reproduced):** any process running as a child of `cursor-agent` — including
the `pytest` full suite the CLI runs — executes while `.claude/settings.json` is renamed to
`.claude/settings.json.cursor-hidden`. A test that reads the original name therefore finds no file.

### F2. The seven failing test modules read the file at the worktree root

Every failing module derives the root the same way (all read-only verified):

| File | `ROOT` definition (line) | Read site |
|---|---|---|
| `tests/test_context_watch.py` | `Path(__file__).resolve().parents[1]` (10) | line 42 |
| `tests/test_harness_inventory.py` | `parents[1]` (13) | `settings_hooks()` line 50 |
| `tests/test_pi_guard_adapter.py` | `parents[1]` (12) | line 170 |
| `tests/test_pipeline_gate.py` | `parents[1]` (12) | line 957 |
| `tests/test_session_context.py` | `parents[1]` (13) | line 56 |
| `tests/test_subagents.py` | `parents[1]` (11) | line 48 |
| `tests/test_usage_hooks.py` | `parents[1]` (14) | line 55 |

`parents[1]` of a file under `tests/` is the repository (worktree) root — the same directory the wrapper passes
as `-Workspace` (line 57). So the expected path is always `<worktree root>/.claude/settings.json`, and the
wrapper's hide is applied to exactly that path. There is no second, differently-resolved copy of the file; the
tests' path assumption is *not* the cause — it is simply where the hide happens to land.

### F3. Per-failing-function table (13 failures = 9 functions, one ×5)

| Test function | Expected path | Source of root | Missing-file behavior | Wrapper source explains it? |
|---|---|---|---|---|
| `test_context_watch.py::test_hook_is_wired` | `<root>/.claude/settings.json` | `parents[1]` | `.read_text()` → `FileNotFoundError` → FAILED | Yes (lines 35–42) |
| `test_harness_inventory.py::test_every_settings_hook_has_a_row` | same | `parents[1]` | `settings_hooks()` → `FileNotFoundError` | Yes |
| `test_harness_inventory.py::test_a_hook_without_a_row_fails` | same | `parents[1]` | `settings_hooks()` → `FileNotFoundError` | Yes |
| `test_harness_inventory.py::test_documentation_correction_keeps_all_guard_inventory_rows_and_hook` | same | `parents[1]` | `settings_hooks()` → `FileNotFoundError` | Yes |
| `test_pi_guard_adapter.py::test_names_fields_cwd_and_project_root_match_claude` (×5 params) | same | `parents[1]` | line 170 `.read_text()` → `FileNotFoundError` | Yes |
| `test_pipeline_gate.py::test_settings_register_the_gate_for_runs_and_writes` | same | `parents[1]` | line 957 → `FileNotFoundError` | Yes |
| `test_session_context.py::test_hooks_are_wired` | same | `parents[1]` | line 56 → `FileNotFoundError` | Yes |
| `test_subagents.py::test_subagent_hooks_are_wired` | same | `parents[1]` | line 48 → `FileNotFoundError` | Yes |
| `test_usage_hooks.py::test_hooks_are_wired` | same | `parents[1]` | line 55 → `FileNotFoundError` | Yes |

Count check: 1 + 3 + 5 + 1 + 1 + 1 + 1 = **13**, matching the totals reported in PR #456 and PR #451 full-suite
sections verbatim (`test_context_watch.py`, `test_harness_inventory.py` ×3, `test_pi_guard_adapter.py` ×5,
`test_pipeline_gate.py`, `test_session_context.py`, `test_subagents.py`, `test_usage_hooks.py`).

### F4. Cleanup on every exit path — except an external kill of the wrapper process

The `finally` (lines 117–125) runs on: normal exit, a non-zero/`is_error` CLI exit, the idle stall (75), the
tool-call stall (75), and the wall timeout (76) — in all of these the wrapper breaks out of the `while` loop and
reaches `finally`, restoring `settings.json`. Therefore the 13 failures are **not** a permanent loss: the file
returns after the run ends.

The one path that skips `finally` is an **external kill of the PowerShell wrapper process itself** (the driver's
660 s tool-call timeout, the 95 min kill, a machine crash). In that case `.claude/settings.json` remains renamed
to `.claude/settings.json.cursor-hidden` and `.cursor-task.md` remains in the worktree. This is documented in the
worker's own memory ("a kill skips the wrapper's `finally`") and is a *separate* defect from the 13 full-suite
failures: it manifests as a dirty worktree *after* a killed run, not as failures *during* the suite. It is
consistent with the wrapper code, but no killed run was reproduced here (no Cursor launch permitted).

### F5. Attribution vs mechanism, and unmeasured links

- **Author attribution (not re-verified):** the header comment (lines 14–23) states the hide exists because
  Cursor has "no opt-out" for importing project Claude Code hooks and those hooks fail on Windows. The two forum
  links (t/166558, t/168129) are cited by the wrapper but not fetched/verified here.
- **Proven mechanism (read-only source):** F1–F4 above.
- **Unmeasured:** whether the historical 13-failure runs were ever followed by a failed restore (the historical
  `cursor-run-logs` under `%LOCALAPPDATA%\cursor-run-logs` were not inspected, and the wrapper/version used at the
  time of #451/#456/#459 is only assumed to be the current file at that SHA256); whether any of the three PRs
  lost `settings.json` *after* their run rather than only during it. These causal links are marked unresolved,
  not pass.

## How it applies to this repository

- `C:/Users/artsafro/hermes_kanban/scripts/cursor-run.ps1` — the hide (lines 35–42) and restore
  (lines 117–125) that produce the pattern. Not part of this repo; read-only reference.
- `tests/test_context_watch.py:42`, `tests/test_harness_inventory.py:50`, `tests/test_pi_guard_adapter.py:170`,
  `tests/test_pipeline_gate.py:957`, `tests/test_session_context.py:56`, `tests/test_subagents.py:48`,
  `tests/test_usage_hooks.py:55` — the 13 failing read sites, all via `ROOT = Path(__file__).resolve().parents[1]`.
- `.claude/settings.json` — git-tracked (confirmed via `git ls-files`), present in the worktree when the wrapper
  is not running (4130 bytes at time of writing). No `.gitignore` entry for `*.cursor-hidden` or
  `.cursor-task.md`, so an external-kill leftover would appear as untracked noise.

## Proposed next tasks (proposals only — no wrapper/test/hook change made)

1. **S — "Model the wrapper hide/restore ordering in a stdlib tmp dir and assert byte-identical restore."**
   One-paragraph scope: a self-contained Python model (under `tmp`/scratch, stdlib only) that mirrors the
   wrapper's `Move-Item` → run-a-reader → `Move-Item` back ordering on a dummy `settings.json`, and asserts that
   (a) a reader launched *inside* the hide window raises `FileNotFoundError`, and (b) after the ordinary
   restore the bytes are identical to the original. This turns F1/F2 from source-reading into a labeled model
   (never a reproduction of the historical run). Value: S effort, converts the explanation into a repeatable
   artifact. **Archive: no roadmap link** — no open roadmap/blocker issue is about the Cursor wrapper or test
   hygiene; the roadmap issues are all geometry/content (MAF/Flora/Ground).
2. **M — "Detect the abnormal-exit leftover state (`.cursor-hidden` + `.cursor-task.md`) after a Cursor run."**
   One-paragraph scope: define a check (e.g. a small post-run `git status --short` guard or a wrapper teardown
   assertion) that flags a worktree still containing `*.cursor-hidden` or `.cursor-task.md`, i.e. a run whose
   `finally` was skipped, and measures the remaining state explicitly instead of silently leaving the guard
   hidden. Input → expected output pairs: *ordinary exit → no `*.cursor-hidden`/`.cursor-task.md` and settings
   bytes restored*; *abnormal kill → leftover detected and reported (not pass, not silently ignored)*. Value: M
   effort, closes the F4 gap between "restored on all normal paths" and "left hidden on external kill."
   **Archive: no roadmap link** — same reason as above.

## Open questions for the user

1. Is the desired end state that these 13 failures become skips/not-run *inside* the wrapper (so a Cursor-run full
   suite reads green), or that they be kept as an expected, separately-reported "wrapper noise" bucket? The two
   proposed follow-ups do not change this policy; they only make the mechanism measurable.
2. Should the external-kill leftover (`.cursor-hidden` / `.cursor-task.md`) be treated as a hard defect with its
   own wrapper fix, or only as a detection/triage signal? The current wrapper restores on every path except an
   external kill of its own process.
