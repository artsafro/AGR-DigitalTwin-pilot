# Issue #1541 — Blender review isolation evidence

Check level: fast. No add-on, client configuration, user preferences, source file
or existing Blender scene was modified. This is the skill-step option explicitly
allowed by the issue, not an automatic MCP transport guard.

## Real two-process inventory

The PowerShell inventory in
[the canonical procedure](../../.agents/skills/blender-mcp/references/instance-pinning.md)
was extracted and executed verbatim before, during and after an agent-owned
factory-startup review window. Blender 5.1.2 was observed in both window titles.
The existing instance was inspected through OS process metadata only; **no MCP
scene request was sent to it**.

| Phase | PID | Displayed open file | Launch flags | Owns 9877 |
|---|---|---|---|---|
| Before | 1019084 | `MAF_16M_6M_review_v002.blend` (dirty title) | `--online-mode` | yes |
| During | 1019084 | same title/path as before | unchanged | yes |
| During | 1012240 | `(Unsaved)` | `--factory-startup --disable-autoexec` | no |
| After | 1019084 | same title/path as before | unchanged | yes |

Owner creation timestamp was `/Date(1794817384823)/` in all three inventories;
review creation timestamp was `/Date(1794819120822)/`. Listener was
`127.0.0.1:9877`, owner `1019084`, throughout. The agent-owned clean factory window
was closed with `taskkill /PID 1012240` (exit 0); its retained process handle
reported exit 0. It was absent from the final inventory. The dirty existing
window was not closed or saved. No model units/geometry were measured.

Raw outputs are `issue-1541/before.txt`, `issue-1541/two-blenders.txt` and
`issue-1541/after.txt` beside this report.
These show native titles (hints), not authoritative live `bpy.data.filepath`.
For an expected review file, the unsaved review cannot pass the procedure's
identity gate. The actual wrong-owner MCP read was deliberately not attempted
against somebody else's dirty document. Live typed-path refusal is **not
measured**; the skill contract requires it before scene reads.

## Verification

- Tests-first commit `26cc7881`: `tests/test_blender_mcp_skill_own_instance.py`
  gave **5 failed / 5 passed** because the new gate/reference was absent.
- Affected tests: the skill contract, DCC pitfalls, skill mirrors, Blender
  exit-code guard and skeleton fixture tests gave **189 passed / 0 failed**.
- First affected run: **52 passed / 1 failed**, exposing an existing synthetic
  skeleton launcher without `--python-exit-code`. The scanner reproduced both
  line-140/143 diagnostics on the exact `origin/main` source blob. The fixture
  now includes `--python-exit-code 1` without weakening duplicate-launch tests.
- Synthetic hostile documentation probe: remove each nonempty subset of the
  two launch flags (3 cases), remove each of 7 refusal/lifecycle tokens, and
  remove the entry's pre-read gate (1 case): **11/11 detected**, clean and reset
  controls **5/5 passed**. These are documentation mutation checks, not runtime
  PID/port mocks. Probe script/results are attached to the card for reuse.
- Regression evals: **0 passed / 0 failed / 10 not measured** (no Claude
  transcript / no branch PR snapshot); receipt checker exited 0.
- Full suite: deferred to merge batch (rule 68).

## Limits and hostile review

- Path aliases: the procedure requires filesystem `samefile` identity; names
  alone do not establish equality. No source/output/report path API was added.
- Duplicate process/file: require exactly one port owner and refuse a changed
  pinned PID/birth even when paths match; never select the newest process.
- State changing during a read: repeat identity after the read and discard on
  change. A switch-and-restore between checks remains outside this procedural
  guarantee; no atomic transport pin is claimed.
- Empty/partial/unsupported/unsaved/error identity: explicitly refuse. Numeric
  NaN/inf/threshold inputs and report/temp aliasing have no interface here.
- Fresh process: the documented inventory ran in new PowerShell processes;
  the factory GUI was a new native process, not a mocked process list.
- Stale receipts: before/after inventories describe this run only. No cached
  receipt authorizes subsequent MCP calls or makes unknown data a pass.
