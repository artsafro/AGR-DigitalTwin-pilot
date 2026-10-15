# branch-name (regression)

**What is checked.** The task worked and committed on a branch named by `docs/agents/NAMING.md`:
`<type>/<area>-<what>` with a type out of `feature`, `fix`, `experiment`, `research`, `harness`, or
`job/<object-id>-<stage>`; `main` passes, because a state update after a merge happens there. Expected: 0 bad
names; measured: the count, with the file, record number, branch and reason of each.

**Why.** An auto-generated worktree branch (`claude/npm-models-school-kpp-ec9ced`) says nothing about the task
and is renamed before its first commit - the agent proposes one name, the user confirms
(user 2026-10-14 [D078], `docs/agents/NAMING.md`, "Branches"). The pre-commit gate blocks such a commit; this grader shows the
sessions that got past it or ran without it.

**Evidence.** `transcript`: every transcript of the branch kept at `/handover`,
`<main checkout>/logs/transcripts/<branch slug>-pr<N|none>-<session UUID>.jsonl`. None found = not measured,
exit 2; a line that is not a transcript record (a torn last line included) with no violation = not measured.

**Detection rule** (grader `twinqa.evals.graders.branch_name`). Read from the record structure only:

- the graded names = the `gitBranch` of every record that holds a main-session `tool_use` named `Bash` whose
  `input.command` matches `COMMIT` (`git ... commit`, `git ... push`, `gh pr create`), plus the `gitBranch` of the
  last record of the file that carries one - the branch the session ended on. A rename (`git branch -m`) is no
  commit, so the old name is not graded by itself;
- a name passes when it is `main`, or matches `NAMED` and not `AUTO_BRANCH`
  (`^(?:claude/|codex/)?[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{6}$`, copied from `tools/git-hooks/branch_names.py`
  together with its type list; a test keeps the copies equal);
- the reason is `auto-generated worktree branch` or `not <type>/<area>-<what> (docs/agents/NAMING.md)`;
- one violation per (branch, file): the same bad name in two sessions is two rows, the same name twice in one
  session is one;
- a file with neither a commit record nor any `gitBranch` is a problem, so the check is not measured, never a
  pass (`isSidechain: true` records hold no commit of the main agent).

**References.** `fixtures/auto-branch-commit.real-excerpt.jsonl` -> fail (1): an EXCERPT of a real session
(34b245fd, 2026-10-07) that committed on `claude/npm-models-school-kpp-ec9ced`.
`fixtures/renamed.corrected.synthetic.jsonl` -> pass: the SYNTHETIC correction - `git branch -m` on the auto
branch with no commit on it, then the same commit on `job/school-kpp1-npm`.
`uv run dt evals --task branch-name --references`.
