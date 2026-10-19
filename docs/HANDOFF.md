# Handoff — 2026-10-19 06:50

Branch: `feature/kernel-op-primitive` · Commit: `79d428b` · Worktree: `/home/user/AGR-DigitalTwin-pilot (cloud container)` · Job: `-`
Transcript: `logs/transcripts/feature-kernel-op-primitive-prnone-e29841e3-114f-5603-814f-96cdb3ac3d4a.jsonl (cloud container only, git-ignored)`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Cloud kernel cards of the grilling plan (`docs/grill/modeling-architecture-2026-10-16.md`, D110), no DCC, board
paused. Five open draft PRs, none reviewed or merged:
- #287 C1 `bpy` 5.1.2 wheel headless on Linux works (note `docs/research/bpy-linux-headless-probe.md`), base `main`.
- #288 C2 `PartsList` contract + `schemas/PartsList.schema.json` (`src/dt_ai/parts/`), base `main`.
- #289 C3 visibility invariants `src/dt_ai/ops/invariants.py` (open borders hidden, no see-through hole, no
  visible back face, no co-directional overlap < 5 mm), base `main`.
- #290 C4a `run_operation` + `keep` + `embed_into_neighbour` (`src/dt_ai/ops/operations.py`), base = #289 branch.
- #291 C4b `primitive_box` + silhouette test 0.07 m (`src/dt_ai/ops/silhouette.py`), base = #290 branch.
Verified on the cloud checkout: `tests/ops` 62 passed, `tests/contracts/test_parts_list.py` 24 passed, mutation
probes catch every deliberate break, full suite `uv run pytest -q -n 8 --deselect tests/test_pipeline_gate.py` ->
4355 passed, 5 failed. The same 5 fail on a clean `origin/main` (`test_batch_export_plan.py` x3,
`test_clearance.py::test_vectorized_setup_matches_per_face_setup`, `test_butovskaya_twin_snapshot.py::test_twin_export_refuses_existing_folder`):
environment. `test_pipeline_gate.py` is deselected (`.git/hooks/pre-commit` not executable in the container).

## In progress

- Nothing uncommitted on this branch. The `bpy` venv and fixtures of C1 lived in the session scratchpad
  (cloud only, gone with the container); the commands are in the C1 note.
- Stack order: #289 -> #290 -> #291 (each base is the previous branch). CI does not start on #290 / #291 (base is
  not `main`); #287-#289 show a red `build`, the billing lock (D122), commented once each.
- The old remote branch `claude/exciting-maxwell-7k6oko` is still on `origin` (not deleted).

## User decisions not in the code

- Branch name `research/bpy-linux-headless-probe` confirmed (user 2026-10-18) - D078 rename done before the first commit.
- User asked to go on with C2, C3, C4 in turn ("давай далее", "продолжай", 2026-10-18); C4 is split into one PR
  per operation.
- D104-D130 are still recorded but not implemented (build by reduction, menu operations, headless kernel, weld vs
  embed by mesh cost, benchmark triples, two human gates, thin drivers, context diet, local CI receipt, PR triage).

## Waiting for the user

- Review of #287-#291 and the merge command naming the PRs and the order (`WORKFLOW.md`, Gate merge authorization).
- Operations as numpy functions on the invariants' meshes, not `bmesh` code (PR #290 "Decision to confirm"); `bmesh`
  only through an adapter for booleans and extrusion. Not answered.
- The numeric rule "few extra edges -> weld, more -> embed" [D124]: not encoded, the threshold is not decided.
- From the earlier handoff, still open: `claude mcp list` and `/plugin` output from the local PC (Unreal MCP and
  plugin names for `deniedMcpServers` / `enabledPlugins`); the files of the first benchmark triple (16-storey
  building: source FBX, delivered FBX, album PDF) in a private place the cloud can reach (D114, D128); explicit board
  resume; connectors to switch off at claude.ai/customize/connectors.

## Next step

After the merge command: C4c `to_opacity_plane` (D109): replace a see-through repeating part by one plane with
opacity; needs a rule for the lost-pixel tolerance of the hole check and for `Context.opacity_parts`.

## Rules broken

- None broken. Notes: `gh` is not available in the cloud container, GitHub work went through the MCP tools; the bases of
  #290 and #291 are not `main`, so no CI runs on them.

## Open PRs and issues for this task

- #287 C1, #288 C2, #289 C3: open, draft, waiting for review and the merge command.
- #290 C4a, #291 C4b: open, draft, stacked on #289 / #290.
- The 13 older open PRs (#226-#280) are untouched; their triage is D123 (local line L1).

## Agent trace

- Sessions: `e29841e3-114f-5603-814f-96cdb3ac3d4a`
- Written by: -
- Subagents: none
- Skills: none
- Commands: takeover 1
- Hook denials: none
- Retries: none
- Context at handover: 35 % (347k of 1000k tokens)
- Duration: 17 h 22 min (2026-10-18T13:25:22Z - 2026-10-19T06:48:20Z, UTC)
- Commits: `013d30b..79d428b` (3 commits)
