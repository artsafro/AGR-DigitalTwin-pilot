# dcc-skill-loaded (regression)

**What is checked.** Every DCC MCP call of the main session had its skill loaded earlier in the same session:
3ds Max -> `3dsmax-mcp-dev`, Blender -> `blender-mcp`, Revit -> `revit-mcp`. Expected: 0 calls before their
skill; measured: the count, with the file, record number, tool and skill of each.

**Why.** The skill carries the route, the units, the read-only start and the traps of that application
(`docs/agents/WORKFLOW.md`, "Triggers": the first DCC MCP call of a session makes the skill mandatory). A call
without it is the case the `tools/hooks/skill_gate.py` gate exists for; the eval shows the sessions where the
gate was off, missing or passed by a tool name it does not match.

**Evidence.** `transcript`: every transcript of the branch kept at `/handover`,
`<main checkout>/logs/transcripts/<branch slug>-pr<N|none>-<session UUID>.jsonl`. One file is one session, and
the skill must be loaded inside that session. None found = not measured, exit 2; a line that is not a transcript
record (a torn last line included) with no violation = not measured.

**Detection rule** (grader `twinqa.evals.graders.dcc_skill_loaded`). Read from the record structure only:

- a DCC call = a `tool_use` whose `name` matches one of `DCC_SKILLS` (`^mcp__[^_]*3dsmax`, `^mcp__[^_]*blender`,
  `^mcp__[^_]*revit`, case-insensitive - the table of `tools/hooks/skill_gate.py`, copied, a test keeps them equal);
- a load = an earlier `tool_use` named `Skill` whose `input.skill` is the skill or ends in `:<skill>` (a plugin
  skill) and that did not fail (its `tool_result.is_error` is not true and `toolUseResult.success` is not false),
  or a user record whose content is the command text `<command-name>/<skill></command-name>`
  (`command_of` in `tools/hooks/usage_log.py`: a tag quoted in a tool result or a file is not a command);
- `isSidechain: true` records are left out: subagents are read-only and preload their skills in `.claude/agents/`.

Every DCC call before the load counts, not one per session: the number says how long the session worked blind.

**References.** `fixtures/no-skill.real-excerpt.jsonl` -> fail (2): an EXCERPT of a real session
(02e3e831, branch `harness/engine-blender-writer`, 2026-10-10) with two `mcp__3dsmax-mcp__*` calls and no Skill
call. `fixtures/skill-loaded.corrected.synthetic.jsonl` -> pass: the same excerpt with a SYNTHETIC `Skill` call
for `3dsmax-mcp-dev` and its success result in front. `uv run dt evals --task dcc-skill-loaded --references`.
