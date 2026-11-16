# #1365 implementation checkpoint — not ready for review

Branch: `improve/issue-1365-review-handoff-check-textures-visible-in`; base: `main`.
Dependency #1390 is merged in base (`8a36a5ad`).

## Verified

- Tests-first commit `9f37d6d9`: 21 failures (module absent), 1 native deselected.
- Native Blender 5.1.2 regression: saves/reopens synthetic empty, linked, packed,
  missing-path, disconnected and wrong-output `.blend` files. Empty fails; linked and
  packed pass; all negative routes fail; source hashes unchanged; repeat result equal.
- Real historical 4BK pair: both declared brick IDs fail in original, pass in preview.
  Committed JSON receipts and exact scope are beside this checkpoint.
- Exact affected command:
  `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_3b38fc56-final2 tests/test_review_textures.py tests/test_skills_sync.py tests/test_validate_delivery_gates.py tests/test_dcc_skill_pitfalls.py tests/test_max_pid_guard.py tests/test_blender_exit_code_guard.py tests/test_max_marker_contract.py tests/test_guard_permissions.py::test_dcc_risks_and_skills_reference_single_register tests/test_build_counters.py::test_rule_is_written_in_workflow_skills_and_checker`
  Result: **201 passed, 1 deselected**, 85.26 s.
- Native command:
  `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -m blender -p no:cacheprovider --basetemp=C:/x/t_3b38fc56-blender2 tests/test_review_textures.py`
  Result: **1 passed, 23 deselected**, 1.45 s.
- Global-setting rule and review-gate references added to canonical skills; mirrors synced.
- Native read-only Max 2026 interface discovery: active viewport texture limit is 1024.
  No global settings changed. Native `GetTextureSizeLimit()` does not exist; changed the
  adapter to published `GetActiveViewportSetting().TextureSizeLimit`, RED then GREEN regression.

Full suite: deferred to merge batch (rule 68).

## Unfinished / blocker

The mandatory synthetic **Max scene** regression is NOT executed. Native Max adapter
correctness beyond the viewport getter is NOT established. Do not interpret Python or
Blender green tests as a Max pass. Read-only discovery found Max PID 969748 holds the
user's dirty `C:/Users/artsafro/Downloads/bukvi.max` (386 objects, meters). A fresh empty
Max 2026 is needed; the fixture explicitly refuses a nonempty session. Do not reset,
load over, close, or hold/fetch the user's scene to get an empty test scene. Do not start
another Max while the one-process restriction applies.

Ready fixture: `tests/max_tools/run_review_textures_1365.py:run(repo, NEW_evidence_dir)`.
Its binaries must go to a new external evidence version + SHA256SUMS, never git/LFS.
Follow `docs/procedure/REVIEW_TEXTURES.md`; verify batch results by reading the native JSON.

No PR is opened because acceptance is incomplete. On resume: obtain a free authorized
Max slot, execute fixture, repair in-scope native failures test-first (remaining attempt
budget per distinct failure), add Max material/ID fail-closed probes, perform hostile
self-review/fresh-process CLI and input-race probes, rerun affected tests, obtain evals
receipt, finish the PR acceptance table/Agent trace and request dt-reviewer review.

## Preserved failed runs

`tmp/red.log`: initial RED. Documentation contract separately failed before the links
were added. An overly broad affected selection (including all permission/eval tests)
timed out after 180 s; not a green receipt. Focused rerun exposed skill length 125>120,
case-sensitive wording, and marker-contract test's incompatibility with `-o addopts=`.
Kept Max skill within 120 lines and resynced mirrors; native test is now selected with
`-m blender` separately without clearing ini addopts. These failures are not hidden by
the final counts above. No surviving card-specific affected pytest process was found
after the timeout before the focused rerun.
