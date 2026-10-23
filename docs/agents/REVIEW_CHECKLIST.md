# Review checklist

Reviewer: any agent that is not the author (now Codex). The reviewer checks evidence, not
confidence. Source: `docs/HARNESS_PLAN.md` §8. Post the answer as a PR comment: verdict
(clean / changes needed), the three answers with numbers, findings by severity (P1/P2/P3).

1. **Pattern / scope.** Does each NEW module refer to a pattern in `docs/domain/patterns/INDEX.md`,
   or is it honestly marked `new-case` in the module docstring and PR body (author receipt verified per
   [WORKFLOW.md#before-requesting-review-author](WORKFLOW.md#before-requesting-review-author))?
   Does the change stay inside its issue and list what is not done?
2. **Invention.** Is there anything in the code or its output that the spec and the inputs do
   not support — guessed levels, made-up geometry, a silent fallback that hides a failure?
3. **Evidence.** Did the checker or the tests pass **with numbers**, run by the reviewer?
   Every regression test must fail on the commit before the fix and pass after it.
   Did the author provide a valid regression eval receipt per
   [WORKFLOW.md#before-requesting-review-author](WORKFLOW.md#before-requesting-review-author)
   (report path, passed / failed / not measured counts, and reasons)? The pass criterion is
   100 % for measured checks: a failed check blocks the merge, and a check that is not
   measured is named with its reason (no transcript, a torn line, an unclassified question),
   never counted as a pass. The tasks and what fails each: `evals/README.md`, "Regression tasks".
   Does the author's handoff evidence check (`--check-handoff` on the PR body and head) exit 0
   ([WORKFLOW.md#handoff-evidence-check-584](WORKFLOW.md#handoff-evidence-check-584))? A missing full suite,
   RED/GREEN or sample output is a finding, not a pass. The reviewer does not run the full suite for the author.

## Counterexamples

Did the author provide the required counterexample probe receipt (`invariant -> probe -> N/N` or
`n/a: <reason>`) per [WORKFLOW.md#before-requesting-review-author](WORKFLOW.md#before-requesting-review-author)?
The reviewer independently attacks the guarantee; the author's probe is input, not a clean verdict.

## Procedure (user 2026-10-13 [D073])

1. **Rounds by risk.**
   - `src/`, hooks, `pipeline_gate`, checkers: 2 rounds; a round 3 only if round 2 found a P1.
   - Patterns, plans, READMEs, briefs (ТЗ), benchmark specs and hashes, `object.json`: 1 round, no test run,
     a check against the rules for contradictions.
   - Jobs: no Codex; `independent-checker` and the user's acceptance.
   - The ceiling stays 3 rounds. The merge waits for the user's command.
2. **P1 in the PR, P2 to an issue.** P1 = a wrong result, a silent skip, data loss, or a hook bypass; it is
   fixed in the PR. Route P2 to issues without asking the user by
   [Escalation (b)](WORKFLOW.md#escalation-131): search duplicates, file/link the issue and record its
   number and review-round URL. The merge does not wait for P2, but still needs the user's command.
   If filing is forbidden or unavailable, use that procedure's explicit pending-issue record instead of
   claiming an issue exists. The reviewer's prompt carries this definition.
3. **The review's input** is the diff, this checklist and the affected tests and benchmarks - not the whole
   repository and not the full suite. The author runs the full suite and every benchmark once, before the
   merge.
4. **Timing.** Round 1 starts right after the first code commit; docs and tests are written meanwhile. The
   last round reviews the final version.

## Verification boundary

Every review comment includes a machine-greppable line:
`Verification boundary: reviewer ran <command, revision, environment, counts>; author-only <checks not re-run>; not measured <checks and reasons>; CI <status/reason>.`
List the exact revision and any uncommitted changes for each run; if they changed after testing, name
that limitation and rerun affected checks. Keep author full-suite counts separate from reviewer runs.
Missing telemetry is `not measured`, never zero or pass. State the known CI limitation once; a billing
lock is not a test failure or a successful CI run. This line supplements the existing risk-based review
rounds and required reruns; it does not waive them.

PR authors use `.github/pull_request_template.md` for the same evidence boundary. Keep verification
commands, RED/GREEN results and environment outside the generated `## Agent trace` block: its fixed
fields still come from `tools/hooks/agent_trace.py`. Preserve `not measured` output when the provider's
transcript is unsupported or absent; do not fabricate a Claude transcript for another provider.
The exact-head/redacted receipt engine proposed in `docs/research/agent-harness-practices.md` is not
implemented by this template.

## Running a Codex review that can execute tests

Lessons of PR #15 (2026-10-08). The Codex sandbox runs as a separate Windows user
(`CodexSandboxOnline`) with no access to the author's profile and no GitHub token.

- Folder of throwaway worktrees outside the repo: `git worktree add --detach <dir>/head <head>`
  and `<dir>/prev <commit before the fix>`. Remove them after the review.
- Self-contained Python inside that folder: `uv python install 3.13 --install-dir <dir>/py`;
  in each worktree `UV_LINK_MODE=copy uv sync --reinstall --python <dir>/py/<cpython>/python.exe`.
  The default venv points at the author's Python and the uv cache: "access denied" in the sandbox.
- Give the issue text in the prompt (`gh issue view <n>` returns 401 inside the sandbox).
- Run: `codex exec -s workspace-write -C <dir> --skip-git-repo-check --output-last-message <file> -`
  with the prompt on stdin; tests as `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
  --basetemp=../tN`; git as `git -c safe.directory=* ...`.
- Keep `--basetemp` short (`../tN`, `C:/x/t-<name>`), for authors too: a long one passes MAX_PATH (git
  "Filename too long", the Win32 working-directory limit of 258) - PR #79. On the user's machine the default
  `%TEMP%\pytest-of-artsafro` is inaccessible (left as is, user 2026-10-12 [D063]): plain `uv run pytest` errors there.
- Known sandbox-only failure: `tests/test_run_record.py::test_timeout_preserves_partial_stdout_and_stderr`
  (`taskkill` access denied). It is not a finding.
- `codex review --base` does not take custom instructions; use `codex exec` for this checklist.
