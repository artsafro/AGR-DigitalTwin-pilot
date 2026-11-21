# Verification attempt boundaries (#1445)

## Test-first and self-review

- Tests-first commit `c6f5412f`: `test_incident4_cli` failed (1 failed):
  the advertised CLI did not exist. The same test passed after implementation.
- The next incident-1 test failed (1 failed): `--brief` was unsupported and CLI
  demanded `--inputs`. Implementing structured brief preflight made it pass.
- Fail-closed probe round: 39 passed / 2 failed. Empty geometry with the empty-file
  SHA-256 incorrectly passed, and freeze documentation was not yet added. Added
  empty-file rejection and the documentation; then 41 passed.
- Hostile earlier-source mutation: 1 failed (`DID NOT RAISE ValueError`) when body A's
  accepted source changed during hashing body B, with an unchanged A copy supplied
  as input. Recheck all selected accepted sources at the end, not just candidates.
  The combined input/source/manifest mutation regressions then passed (42 passed).

These are local sequential RED/GREEN rounds; only `c6f5412f` is the published tests-first
commit. Do not label uncommitted intermediate implementations as immutable revisions.

## Broad reference-search run: NOT GREEN

A conservative run of all test files mentioning WORKFLOW.md, TASK_TO_MODEL.md or
CAPABILITIES.md selected unrelated runtime/permission engines as well as documentation
contracts. Foreground wrapper timed out at 300 seconds; verified surviving native PID
952076 and waited without modifying tracked files. It finished:

`687 failed, 923 passed, 2 skipped, 84 errors in 1173.15s`.

Native Python **and git** repeatedly failed to start with Windows status `3221225794`
(`0xC0000142`), e.g. `git init -q` in the pipeline fixture, fresh Python in route maps,
procedure CLI and permission hooks. The raw log is retained at
`tmp/issue-1445/affected.log` in this worktree. A separate diagnostic permission-only
run got `145 passed, 1 failed` with the same native startup status; an initial 20-case
permission check passed. No permission/checker algorithms were changed to hide it.
Confirmed no native processes matching this card's affected/diagnostic commands survived.
This environmental run is not a full suite and is not the final affected receipt.

After that load ended, focused affected seams (new tool + relevant existing document,
approval, intake and acceptance-policy contracts) ran successfully: an initial focused
run had `235 passed, 2 skipped in 39.60s`. Final head counts and exact command are in the
PR's `Affected tests:` receipt; do not transfer these preliminary counts onto a later head.
No production procedure/permission engine changed, so their entire runtime suites are
not part of the final focused selection. The full suite remains deferred to merge batch.
