# Per-call PID guard (#1364)

PreToolUse `tools/hooks/skill_gate.py` requires this exact leading shape in
`execute_maxscript.code` (replace `563748` with the authorized positive integer PID):

```maxscript
local pc = dotNetClass "System.Diagnostics.Process";
if (pc.GetCurrentProcess()).Id != 563748 do throw "wrong Max";
-- Authorized mutation follows, not before or around the guard.
```

For `execute_python.code`, begin with this exact four-space-indented prefix:

```python
import os
if os.getpid() != 563748:
    raise RuntimeError("wrong Max")
# Authorized mutation follows.
```

Keep the guard unconditional, first and outside any `try/catch`, function or branch.
Comments/strings containing a guard, a guard after a write, malformed PID values,
missing code and unknown operations are denied. Use a guarded script equivalent
for `scene_patch`, `manage_scene`, creation, deletion, transform and other native
mutations; a `code` field on those tools is not an executable guard.
`select_max_instance` remains available for authorized routing, not scene mutation.
A fresh `get_selected_max_instance` is diagnostic only: another registration can
occur between the read and dispatch, so it cannot replace the in-process guard.
No persisted PID receipt is used: repeats, new sessions and resets cannot inherit
permission. Subagents and missing transcripts do not bypass the PID check.

Read-only script admission is intentionally limited to exact expressions:
`objects.count`, `selection.count`, `maxFileName`, `maxFilePath`, `getSaveRequired()`.
Other scripts, including complex read-only scripts, need the prefix. Typed inspection
and `query_scene` `overview`/`selection` remain available. `inspect_mesh` permits only
omitted/false `capture`; capture registers viewport callbacks and needs a guarded equivalent.
The legacy MAXScript `command` alias is denied: put the prefix and body in `code`.
This lexical accident guard
is not a sandbox, PID ownership verification or authorization; do not redefine native
process APIs, and continue following the skill's risk gate.

Evidence: `tests/test_max_pid_guard.py` simulates two registrations and executes the
Python guard against a mocked PID source. Live two-Max re-registration is NOT DONE
(2026-11-15: orchestrator forbids touching the user's open Max sessions). It does not
establish live pin survival. External Claude memory remains untouched by instruction;
its eventual replacement should be only a pointer to this section, not another rule copy.
