# Shared capabilities

What agents can rely on, across all worktrees. A tool or workflow counts as
available to other agents only after it is listed here **on `main`**.

Status:
- **WORKING** — validated end to end on the real application/data (date, by whom).
- **CONFIGURED** — installed and the server/tool starts; not yet validated on a live app.
- **IN BRANCH** — exists only in an unmerged branch; other worktrees do not have it.
- **BROKEN** — known not to work; see the backlog item.

## Publish a capability

1. Validate it on the real application (not only "server connected").
2. Commit the working solution in your branch.
3. Add or update its entry here: status, owner, branch, how to use, limits, date.
4. Ask for review and merge (`ROLES.md`: Codex integrates `main`; DCC tools are confirmed by Claude on real data).
5. Other worktrees pick it up with `git merge main` at the start of their next task.

## Machine and repository

- Local: `C:\Users\artsafro\AGR-DigitalTwin` (branch `main`); GitHub `artsafro/AGR-DigitalTwin`
  (private, `origin`). Task worktrees: the agent's own worktree folder or
  `C:\Users\artsafro\HerdrWorktrees\AGR-DigitalTwin\<name>` (Herdr).
- Applications: Blender 4.4 and 5.1.2, Unreal Engine 5.5 and 5.7, 3ds Max 2024 and 2026, Revit 2025,
  AutoCAD 2025, SketchUp 2026, SpeedTree Modeler 10.0.1, RizomUV 2024.1, Python 3.13 (`py -3`), uv,
  Node/npx, Git LFS, GitHub CLI, poppler. DCC executables are not on PATH.
- Drive C is ~99 % full (about 20 GB free); heavy data has no backup outside this machine (backlog H9).
- `.gitattributes` routes production binaries to Git LFS, but the LFS budget is exhausted (push
  rejected 2026-10-06): commit no LFS files until H9 is decided. Files over 50 MB go as links (below).
- CI on GitHub does not start (account locked for billing, 2026-10-14): checks are the local suite only.

## Headless toolchain smoke check

Checked 2026-10-15 (#139): one short headless run per tool on this workstation, no GUI, no user scenes,
scratch copies only, nothing installed. 18 runs, 149.381 s of probe time in total. Exact commands, exit
codes and output tails: [toolchain-smoke-2026-10-15.md](../research/toolchain-smoke-2026-10-15.md). Helper scripts lived in the git-ignored
scratch dir `tmp/issue139/`. A smoke run is not delivery validation (`passed=true`).

| Tool | Version | Command used | Result (works / fails + error line) | Date checked |
|---|---|---|---|---|
| PyMuPDF | 1.28.2 | `uv run --offline --extra pdf-review python tmp/issue139/pdf.py` ([run 2](../research/toolchain-smoke-2026-10-15.md#run-2-pdf_extra_fallback)) | works: page 1 of the regulation PDF rendered to PNG 1232x1755 and read back. The issue's `--group pdf-review` fails: `error: Group 'pdf-review' is not defined in the project's 'dependency-groups' table` (it is an optional extra) | 2026-10-15 |
| ezdxf | 1.4.3 | `uv run --offline --extra cad python tmp/issue139/cad.py` ([run 4](../research/toolchain-smoke-2026-10-15.md#run-4-cad_extra_fallback)) | works: 1 LINE written to DXF and read back. The issue's `--group cad` fails: `error: Group 'cad' is not defined in the project's 'dependency-groups' table` (it is an optional extra) | 2026-10-15 |
| CheckToolBox | v1.5 add-on (no version in bl_info) on Blender 4.4.0 | `blender 4.4 --background --factory-startup --python-exit-code 1 --python jobs/KPP1/scripts/qa_checktoolbox.py -- <out.json> <synthetic_cube.fbx>` ([run 14](../research/toolchain-smoke-2026-10-15.md#run-14-blender_44_qa_checktoolbox_run)) | works on Blender 4.4 (the KPP1 host): faces 6, doubles 0, intersect_faces 0. Fails on Blender 5.1.2: `ModuleNotFoundError: No module named 'CheckToolBox_v1_5'` (add-on not installed there; Blender exits 0 unless `--python-exit-code` is set) | 2026-10-15 |
| speedtree-mcp | mcp 1.30.0; SpeedTree Modeler v10.0.1 install | `python tmp/issue139/speedtree.py` (stdio client in the BlenderLab103 venv) ([run 5](../research/toolchain-smoke-2026-10-15.md#run-5-speedtree_mcp_client)) | works: server starts, 6 tools listed, `installation_info` installed=True. No `.spm` sample is tracked, so no inspect or export | 2026-10-15 |
| AutoCAD core console | AutoCAD 2025, ACADVER 25.0 | `python hermes_kanban/scripts/dcc_batch.py acad --ping` ([run 10](../research/toolchain-smoke-2026-10-15.md#run-10-acad_dcc_batch_ping)) | works: `AGR_PING acad=25.0`, exit code 0, 4.0 s | 2026-10-15 |
| 3ds Max batch | 3ds Max 2026.3 (28.3.0.30732) | `python hermes_kanban/scripts/dcc_batch.py max --ping` ([run 11](../research/toolchain-smoke-2026-10-15.md#run-11-max_dcc_batch_ping)) | works with an error: `AGR_PING max=28000` printed, wrapper status ok, but native exit 4294967166 and `MAXScript Auto-load Script Error Exception ... polyunwrapper_autoload.mse` (a startup script in the user profile; the whole batch run took 119.9 s) | 2026-10-15 |
| Blender | 5.1.2 (hash ec6e62d40fa9) | `blender 5.1 --background --factory-startup --version` ([run 6](../research/toolchain-smoke-2026-10-15.md#run-6-blender_version)) | works: version printed, exit 0; the synthetic test FBX was also exported headless ([run 7](../research/toolchain-smoke-2026-10-15.md#run-7-blender_synthetic_cube_fbx)) | 2026-10-15 |
| autocad-mcp | multiCAD (`tools/mcp/multicad_stdio.py`) | none | not checked: needs AutoCAD open (user); the MCP server drives a live AutoCAD session, which a headless smoke check does not start | 2026-10-15 |

#### Not used, by decision

User decisions of roadmap round 4 (COORDINATION_RULES 27, issue #139):
- trimesh: not used.
- CADCraft: not used.
- ODA File Converter: not installed for now; DWG is read through the AutoCAD 2025 core console (DXFOUT) + ezdxf.
- MTree/Sapling: not used until a Flora benchmark on the user's trees.
- IfcOpenShell: transient `uv --with` only, no project dependency, until the Revit adapter.

## DCC / MCP

Rules for every DCC: confirm the MCP tools are present **and** the intended application and
document are live before work; start read-only; preserve source files and scenes. Saves,
exports, overwrites and other mutations need explicit task authorization and a versioned
output path. If the MCP or live session is missing, stop that application's work and report
the exact gap. An application not listed here has no MCP — do not claim live control or
substitute ad-hoc scripting.

### 3ds Max — `3dsmax-mcp`
- Status: CONFIGURED (server health check passed 2026-10-06; no live-scene operation validated)
- Owner: Claude (main) · scope: user (all projects)
- Server: cl0nazepamm/3dsmax-mcp v1.7.5, `C:\Users\artsafro\tools\3dsmax-mcp`; plugin in
  `C:\ProgramData\Autodesk\ApplicationPlugins\3dsmax-mcp`; `safe_mode = true`
- Use: 3ds Max 2026 (2024 is forced to run as administrator and may not connect from a
  non-elevated client). Skill: `3dsmax-mcp-dev`.

### Revit — `revit-bridge` (the live route)
- Status: CONFIGURED (Codex, 2026-10-06: `revit_status` answered from the running Revit 2025;
  a Revit API version query over the pipe timed out — needs a fresh read-only check)
- Server: `C:\Users\artsafro\tools\revit-bridge-mcp\src\index.js`, env `REVIT_BRIDGE_VERSION=2025`
  (copied 2026-10-06 from `Desktop\zavod\projects\revit-bridge`, which Cursor still uses;
  handshake lists 25 tools). Talks to the RevitBridge ("Cursor Bridge") add-in in
  `%AppData%\Autodesk\Revit\Addins\2025` over a named pipe — no TCP port.
- Registered for Codex and Antigravity (`.codex/config.toml`, `.agents/mcp_config.json`) from the
  `tools` path. Codex exported FBX from a QA fixture over the pipe (2026-10-06).
- Mutating tools (`open_document`, `export_fbx*`, `agr_export_fbx`, `load/unload/reload/repath`
  links) need explicit task authorization and versioned outputs.
- Sources are Revit 2022 files — open upgraded **copies**, never save over `data/sources/revit/*.rvt`.

### Revit — `revit-http-2025` (HTTP add-in route)
- Status: WORKING for inspection (Codex, 2026-10-06 18:38+): KenLP/RevitMCPServer v0.8.31 live on
  `127.0.0.1:7891`, 94 tools advertised; 20 calls across 19 tools passed on a separate fixture
  project, including a dry-run `create_level`. RVT persistence of edits not verified.
- Registered for Codex and Antigravity as `revit-http-2025` (port 7891). The Claude user
  registration `revit-2025` still sets 7891 — matches. Skill: `revit-mcp`.

### Revit twin — `revit-twin`
- Status: BROKEN (2026-10-06: connection closed). Its source was only on the former DT branch
  `feature/revit-workflow` (archive bundle); the Claude user registration points at that
  worktree. Not part of this repo — backlog H3.
- 2026-10-08 (Claude): still fails to connect (CONNECTION_CLOSED). The Revit spec extractor
  uses `revit-http-2025` instead (`docs/HARNESS_PLAN.md` §4).

### AutoCAD — `multiCAD`
- Status: WORKING (Codex, 2026-10-06, AutoCAD 2025): inspection on `flora.dwg`; on a fixture, seven
  entity types, edits, DWG/DXF save to a new path and reopen. Built-in screenshot is broken — use
  Computer Use for visuals.
- Server: upstream multiCAD in `%LOCALAPPDATA%\CodexMCP\MultiCAD\venv`, wrapped by
  `tools/mcp/multicad_stdio.py` (all COM calls on one thread). Install with
  `tools/mcp/constraints-multicad.txt`. Not a Revit connector. Skill: `autocad-mcp`.

### Blender — `blender`
- Status: WORKING on a fixture (Codex, 2026-10-06): official Blender Lab MCP 1.0.3, Blender 5.1.2,
  port 9877. Create/edit/material/UV, save/reopen, FBX export/import passed. MCP screenshots
  preceded an NVIDIA driver crash — use Computer Use for visuals. Runs arbitrary Python in the
  open scene: never on an unrelated production scene. Skill: `blender-mcp`.

### SpeedTree Modeler — `speedtree`
- Status: WORKING for file inspection and CLI FBX batch export (Codex, 2026-10-06, Modeler v10.0.1).
  Does not drive the GUI. Native geometry/scale/texture readback of exports still pending.
- Server: `tools/mcp/speedtree_server.py` (6 tools). Exports only to a new empty directory.
  Skill: `speedtree-mcp`. The 8-tool Antigravity variant (`harness/antigravity-support`) was
  not adopted.

### RizomUV — `rizomuv`
- Status: WORKING on a fixture (Codex, 2026-10-06, RizomUV 2024.1): load, unfold, optimize, pack,
  versioned OBJ/FBX save and readback. Cold `open_session` sometimes times out at the Link API
  limit. Server: `tools/mcp/rizomuv_server.py`. Skill: `rizomuv-mcp`.

### SketchUp
- Status: CONFIGURED (scripts only): Codex's Production extension worked on SketchUp 2026 from
  the former AGR folder's venv. Scripts are now in `adapters/sketchup/`; the venv was not moved
  — create one and re-verify before use (backlog H2).

Adapters and evidence log: `tools/mcp/README.md`, `tools/mcp/verification.txt`. All routes are
registered for Codex and Antigravity; Claude uses only its own user-scope registrations.

### DCC tool risk classes

This register is the single risk source for DCC skills and the guard's manual
[DCC authorization gate](WORKFLOW.md#gate-dcc-authorization). Risk describes the
**operation**, not connection status: `read-only` inspects without changing scene/file
state; `versioned-write` creates only a new versioned output; `destructive` changes
existing scene/session/data or can execute arbitrary code. Even creation in a live
scene is destructive: unsaved user work may be affected. A new output path does not
make arbitrary Python safe. Task authorization is required for versioned writes;
destructive operations need explicit authorization for the exact mutation. The
[Permission matrix](WORKFLOW.md#permission-matrix) still prohibits source overwrites.

Match the actual tool schema and every operation in a batch before calling it; the
highest risk wins. The rows below cover each registered route, including scripts.
External catalogs are not pinned in this repo: only the enumerated inspection
operations are read-only; **every unlisted/new/unknown tool defaults to destructive**
until inspected and registered here. This fallback is a classification, not a claim
that those tools have been tested. No generic MCP sandbox is implemented by guard.py.

| Route | Tool / operation (all unmatched operations use the route's fallback) | Risk |
|---|---|---|
| 3dsmax-mcp | All tools, including script execution; inspect schema before use (no live inspection subset validated) | destructive |
| revit-bridge | `revit_status` | read-only |
| revit-bridge | `export_fbx*`, `agr_export_fbx` to new versioned destinations | versioned-write |
| revit-bridge | All other tools, including `open_document`, link load/unload/reload/repath | destructive |
| revit-http-2025 | `revit_ping`, `revit_get_document_info`, `revit_get_views`, `revit_list_categories`, `revit_list_elements`, `revit_get_element_info`, `revit_get_parameter`, `revit_list_levels`, `revit_list_families`, `revit_list_sheets`, `revit_list_rooms`, `revit_list_materials`, `revit_get_worksets`, `revit_get_linked_files`, `revit_get_model_health` | read-only |
| revit-http-2025 | Inspected export-only tools to new versioned paths (including PDF) | versioned-write |
| revit-http-2025 | All other tools, including create/edit/delete, arbitrary code and dry-run mutations until inspected | destructive |
| revit-twin | All tools (broken route, no validated operation subset) | destructive |
| multiCAD | `manage_files` list/info; `manage_layers` list/info; `manage_blocks` list/info/get_attrs; `manage_session` status/check_running; `export_data` JSON returned without saving | read-only |
| multiCAD | `manage_files` save with explicit new versioned DWG/DXF destination via project wrapper | versioned-write |
| multiCAD | All other tools/operations, including session connect/open/close, entity/layer/block edits and script execution | destructive |
| blender | `get_blendfile_summary_path_info`, `get_blendfile_summary_datablocks`, `get_blendfile_summary_missing_files`, `get_blendfile_summary_of_linked_libraries`, `get_blendfile_summary_usage_guess`, `get_objects_summary`, `get_object_detail_summary` | read-only |
| blender | Inspected typed save/export-only tools to new versioned paths | versioned-write |
| blender | All other tools, including Python, `_for_cli`, scene mutation and crash-prone MCP image tools | destructive |
| speedtree | `installation_info`, `list_templates`, `list_presets`, `inspect_preset`, `inspect_spm` | read-only |
| speedtree | `export_tree` to a new path in an empty versioned directory | versioned-write |
| speedtree | All other/new tools | destructive |
| rizomuv | `get_session_status`, `get_version` | read-only |
| rizomuv | `save_mesh` to a new path in a fresh versioned directory | versioned-write |
| rizomuv | `open_session`, `load_obj`, `load_mesh`, `unfold_visible`, `optimize_visible`, `pack_visible`, `close_managed_session`, all other/new tools | destructive |
| SketchUp | All scripts/extension operations until inspected (route not re-verified) | destructive |

## Harness

### Harness inventory
One row per component (#129): every hook command in `.claude/settings.json` and in the subagents' frontmatter, every
permission list, guard rule set, command, subagent and git hook. **Evidence** is a case, PR or issue where the failure
really happened; `none` = a precaution only (the decision that made it is named). **Last verified** = the last date it
was seen working: `live` (a real session, named) or `pytest` (its suite green on that date). **Eval** = tasks under
`evals/` that would catch the stated failure, or `none`; for protection rows, a task must test the component's
rejection behavior to count. Indirect procedural signals are listed separately below, not as covering evals.
Rules for re-examining it: `docs/agents/WORKFLOW.md`,
"Harness inventory". `tests/test_harness_inventory.py` fails when a hook, command, subagent or git hook has no row
or an eval id is no task.

| Component | Kind | Failure it prevents | Evidence it happened | Last verified | Eval |
|---|---|---|---|---|---|
| `.claude/hooks/guard.py` | PreToolUse hook (Bash, PowerShell, Write, Edit, NotebookEdit), "ask" | a destructive, outward or asset-corrupting action without the user's word | PR #142: the app isolation hook refused a Write into another worktree (real handover transcript); not component-specific evidence for project guard | never (project-guard verification unknown; component-specific run required) | none |
| `.pi/extensions/agr-guard.ts` + `tools/hooks/pi_guard_adapter.py` | Pi `tool_call` bridge (bash, powershell, write, edit), fail closed | Pi skips Claude hooks; headless ask/deny and hook failures must block | #58: Windows third-party hook adapter passed an unexpanded project path | 2026-10-15 live via `pi-run.sh` + nested smoke driver (`tests/fixtures/pi_guard_smoke.ts`): status allowed, reset blocked; pytest `tests/test_pi_guard_adapter.py` + `tests/test_pi_guard_contract.py` (installed-Pi parity); exact `edits[]` preview; special Pi paths and fuzzy-only edits block (use native/relative paths and exact text); opt in with `PI_EXTENSIONS=.pi/extensions/agr-guard.ts`, wrapper wiring deferred | none |
| guard rule set `SHELL_RULES` | guard rule set | push, `reset --hard`, `clean`, forced branch delete, discarded changes, history rewrite, LFS migrate, deletes of sources or production assets, recursive delete, installs, system changes | none (precaution, carried over from DigitalTwinProject) | never (no test) | none |
| guard rule set `PRODUCTION_EXT` | guard rule set (Write, Edit) | a text write over a production asset (`.fbx`, `.max`, `.blend`, `.png`, ...) | none (precaution) | never (no test) | none |
| guard rule set `ALLOWED_WRITE_ROOTS` | guard rule set (Write, Edit) | a write outside the project and the allowed folders, e.g. into another worktree | PR #142: the app isolation hook refused the foreign-worktree Write; not component-specific evidence for this rule set | never (rule-set verification unknown; component-specific run required) | none |
| `permissions.allow` | `.claude/settings.json` list | a routine read-only git, test or `dt` call stops the session for a confirmation | none (convenience) | never (no test) | none |
| `permissions.ask` | `.claude/settings.json` list | push, `reset --hard`, `clean`, `branch -D` without the user's word (duplicates `SHELL_RULES`) | none (precaution) | never (no test) | none |
| `permissions.deny` | `.claude/settings.json` list | secrets in `.env` read into the context | none (precaution) | never (no test) | none |
| `.claude/hooks/pipeline_gate.py` | PreToolUse hook (Write, Edit), deny | a job status above draft without spec, extractor report and checker report; a job script without an engine gap | case alina-bld (`docs/cases.md`): no spec, no checker report, build script left only as `.pyc` | 2026-10-15 pytest (`tests/test_pipeline_gate.py`) | none |
| `tools/hooks/skill_gate.py` | PreToolUse hook (DCC MCP), deny | a 3ds Max / Blender / Revit MCP call before its skill is loaded | none (precaution, [D074], PR #107) | 2026-10-15 pytest (`tests/test_usage_hooks.py`) | none |
| `tools/hooks/session_context.py start` | SessionStart hook | a session after `/clear` or compaction starts without branch, state and handoff, or on a stale / foreign handoff | none (precaution, [D076], PR #107) | 2026-10-15 pytest (`tests/test_session_context.py`); live 2026-10-14 in `claude -p` | none |
| `tools/hooks/session_context.py precompact` | PreCompact hook | a manual `/compact` over a stale handoff loses the session state | none (precaution, [D076]) | 2026-10-15 pytest (`tests/test_session_context.py`) | none |
| `tools/hooks/context_watch.py` | UserPromptSubmit hook | the session runs into auto-compaction without a handover (45 % / 65 % notes) | none (precaution, [D076]) | 2026-10-15 pytest (`tests/test_context_watch.py`) | none |
| `tools/hooks/usage_log.py prompt` | UserPromptSubmit hook | an unused `/command` stays invisible (no 7-day counts at `/takeover`) | none (precaution, [D074]) | 2026-10-15 pytest (`tests/test_usage_hooks.py`) | none |
| `tools/hooks/usage_log.py post` | PostToolUse hook (Agent, Task, Skill) | an unused subagent or skill stays invisible; the usage-log evidence for evals | none (precaution, [D074]) | 2026-10-15 pytest (`tests/test_usage_hooks.py`) | none |
| `.claude/hooks/subagents.py start` | SubagentStart hook | a subagent forgets it is read-only; no `git status` snapshot for the stop check | none (precaution, [D071]) | 2026-10-15 pytest (`tests/test_subagents.py`) | none |
| `.claude/hooks/subagents.py stop` | SubagentStop hook | tracked files changed by a subagent go unnamed; `independent-checker` ends without a verdict table | none (precaution, [D071]) | 2026-10-15 pytest (`tests/test_subagents.py`) | none |
| `.claude/hooks/subagents.py guard` | PreToolUse hook in all five subagents, deny | a plain Bash write from a read-only subagent | none (precaution, [D071]) | 2026-10-15 pytest (`tests/test_subagents.py`) | none |
| `.claude/hooks/subagents.py deny-geometry` | PreToolUse hook in `independent-checker`, deny | the checker reads how the model was built and confirms it instead of checking | #117: the engine's own "11/11 checks passed" on a wrong model | 2026-10-15 pytest (`tests/test_subagents.py`); live 2026-10-13 (PR #86) | none |
| `tools/hooks/save_transcript.py` | script of `/handover` | the session transcript is lost at `/clear`, so evals have no evidence | #121 (no transcripts kept before it) | 2026-10-15 live (PR #140, by nonce); pytest (`tests/test_save_transcript.py`) | none |
| `.claude/commands/handover.md` | command `/handover` | session state lost at a context rotation | none (precaution, [D076]) | 2026-10-14 live in `claude -p` (PR #107) | none |
| `.claude/commands/takeover.md` | command `/takeover` | a new session starts from a handoff that disagrees with git and GitHub | none (precaution, [D076]) | 2026-10-14 live in `claude -p` (PR #107) | none |
| `.claude/commands/reuse-scan.md` | command `/reuse-scan` | repeated procedures never become code, a skill or a pattern | none (precaution, [D075]) | 2026-10-15 pytest of `tools/reuse_candidates.py` (`tests/test_usage_hooks.py`) | none |
| `.claude/agents/source-inspector.md` | subagent, read only | work on an uninspected source (scale, levels, dropped parts); a scene dump in the main context | none recorded | 2026-10-13 live (PR #86, B01 `etalon.max`) | `source-inspected` |
| `.claude/agents/pattern-librarian.md` | subagent, read only | a rule question asked again or a new rule invented where one exists | none recorded | 2026-10-13 live (PR #86) | `routine-question` |
| `.claude/agents/bench-runner.md` | subagent, read only | raw benchmark and test logs in the main context | none (precaution, [D071]) | 2026-10-13 live (PR #86, B01 9/9) | none |
| `.claude/agents/independent-checker.md` | subagent, read only | "done" reported from the engine's own output | #117 | 2026-10-13 live (PR #86, B01 model) | `engine-checked` |
| `.claude/agents/mesh-reader.md` | subagent, read only | a mesh dump read into the main context | none (precaution, [D071]) | never (not test-called) | none |
| `tools/git-hooks/pre-commit` | git pre-commit (every agent) | a commit that skips linking or the pipeline gate; fail-open when the root or the gate is missing | case alina-bld (the gate it runs); fail-open versions were found in review of PR #79, not in use | 2026-10-13 live (manual blocked commit) | none |
| `tools/git-hooks/link_large_files.py` | git pre-commit step | a new file over 50 MB committed into history | none recorded | 2026-10-06 live (60 MB file) | none |
| `tools/git-hooks/pipeline_gate.py` | git pre-commit step, delivery gate | as `.claude/hooks/pipeline_gate.py`, for every agent; a commit on an auto-named branch; a `.pyc` without its `.py` at delivery | case alina-bld | 2026-10-15 pytest (`tests/test_pipeline_gate.py`) | `branch-name` |
| `tools/git-hooks/branch_names.py` | rule module of the gate and the SessionStart hook | a commit on an auto-generated worktree branch | `claude/npm-models-school-kpp-ec9ced` (`evals/branch-name/task.md`), [D078] | 2026-10-15 pytest (`tests/test_branch_names.py`) | `branch-name` |

**Indirect procedural signals** (not component behavior coverage):
- `no-hook-denial`: `.claude/hooks/guard.py`, `SHELL_RULES`, `PRODUCTION_EXT`, `ALLOWED_WRITE_ROOTS`,
  `permissions.ask`, `tools/hooks/skill_gate.py`, `.claude/hooks/subagents.py guard`,
  `.claude/hooks/subagents.py deny-geometry`. It detects agent attempts refused by hooks, not whether
  unauthorized actions are rejected. Its [task definition](../../evals/no-hook-denial/task.md) excludes
  accepted calls and non-blocking hook failures: a fail-open guard can pass.
- `dcc-skill-loaded`: `tools/hooks/skill_gate.py`; checks skill ordering in the transcript, not the gate's
  rejection behavior. See its [task definition](../../evals/dcc-skill-loaded/task.md).

These mappings must not be used alone as proof that a protection is tested in removal decisions.
`Eval = none` records missing behavior-specific eval coverage, not absence of the dated pytest runs above.
No guard deletion is authorized; hooks, permissions and rule sets remain unchanged. The candidates below
are not expanded by this coverage correction; re-examination requires component-specific evidence and user approval.

Removal candidates by the rule (no evidence, no eval): `permissions.allow`, `permissions.deny`, the hooks
`session_context.py`, `context_watch.py`, `usage_log.py`, `subagents.py start` / `stop`, the three commands,
`bench-runner`, `mesh-reader`, `link_large_files.py`. They are proposed to the user, not removed.

### Rule-layer size
- Measured 2026-10-15 at commit 32813c6: **141k tokens** (564 970 characters / 4; an estimate, not a tokenizer
  count). Scope as in the spec: Markdown, YAML and JSON at the root (top level only), `docs/agents`, `docs/domain`,
  `docs/adr`, `.agents/skills`, `standards/` and the plan / state files (`PROJECT_STATE`, `HARNESS_PLAN`, `backlog`,
  `cases`, `pipeline`, `HANDOFF`, `decisions`). Out of it: `docs/agr`, `jobs`, `technical_library`.
- Command (Git Bash, from the repository root; divide by four):
  `{ find . -maxdepth 1 -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' \); find docs/agents docs/domain docs/adr .agents/skills standards -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' \); ls docs/PROJECT_STATE.md docs/HARNESS_PLAN.md docs/backlog.md docs/cases.md docs/pipeline.md docs/HANDOFF.md docs/decisions.md; } | tr '\n' '\0' | xargs -0 cat | wc -c`
- Threshold: **200k tokens**. Below it the agent loads the relevant file whole; no semantic index, no vector store,
  no BM25. Retrieval tooling is reconsidered only when a measurement passes 200k.

### Guard hook — `.claude/hooks/guard.py`
- Claude Code: CONFIGURED (PreToolUse in `.claude/settings.json`); project-guard live verification
  unknown. PR #142's foreign-worktree Write was refused by the app isolation hook, not proven to be
  refused by this project hook. A component-specific run is required; the hook and rules remain enabled.
- Antigravity: CONFIGURED (`.agents/hooks.json` → `guard.cmd`; Antigravity-side run not validated).
- Codex: CONFIGURED (`.codex/hooks.json`; payload and "ask" support not validated — backlog H1).

### Kanban board — GitHub Projects `artsafro/projects/1`
- Status: WORKING (2026-10-14): Status and Agent fields, 30 open issues on the board; `gh` needs the
  `project` token scope. Rules: `docs/agents/KANBAN.md`.
- Vibe Kanban: REJECTED (2026-10-14 trial, 0.1.44), reasons in the same file.

### Context rotation, triggers, reuse (Claude Code, PR #107; `docs/agents/WORKFLOW.md`)
- Status: WORKING (2026-10-14, live in `claude -p`; desktop and interactive CLI not checked).
- `tools/hooks/session_context.py`: SessionStart (`startup|clear|compact`) passes branch, status, last commits,
  open PRs and `docs/HANDOFF.md` (warnings when stale / foreign / old format); PreCompact blocks a manual
  `/compact` with a stale handoff (`/compact force` passes), logs auto ones to `<git dir>/agr-compactions.log`.
- `tools/hooks/context_watch.py`: UserPromptSubmit, context share from the transcript's last `usage`; tells the
  agent once per session at 45 % and 65 %. Context % on screen: the user-level status line (`ctx N%`).
- `tools/hooks/skill_gate.py`: PreToolUse on DCC MCP tools (3ds Max, Blender, Revit) denies the call in the
  main session until `3dsmax-mcp-dev` / `blender-mcp` / `revit-mcp` is loaded.
- `tools/hooks/usage_log.py`: PostToolUse on Agent / Skill and UserPromptSubmit `/commands` ->
  `logs/agent-usage.jsonl` in the main checkout (git-ignored); `stats --days N`; `backfill --days N` (#109) adds
  past usage from the transcripts of this repository and its registered worktrees (idempotent; skips calls the hooks logged).
- `tools/hooks/save_transcript.py` (#121): `/handover` copies the session transcript to `logs/transcripts/
  <branch>-pr<N>-<session>.jsonl` in the main checkout (git-ignored), never over an existing copy; the handoff's
  `Transcript:` line names it and `session_context.py` prints it. The session is proven by a nonce: the agent's Bash call
  is in its own transcript before it runs, so the one transcript holding the nonce is the caller's; never file times.
  Status: WORKING (2026-10-15, PR #140): found the live desktop session by its nonce; not yet run inside a real
  /handover.
- Commands: `/handover`, `/takeover` (ends with 7-day usage), `/reuse-scan` (+ `tools/reuse_candidates.py`).
- Tests: `tests/test_session_context.py`, `tests/test_context_watch.py`, `tests/test_usage_hooks.py`,
  `tests/test_save_transcript.py`.

### Evals runner — `dt evals` (Claude Code, #122; `evals/README.md`)
- Status: WORKING (2026-10-15, PR #142): `uv run dt evals --suite regression|capability` or
  `--task <id>` runs `evals/<task>/task.json`; graders in `src/twinqa/evals/graders.py` (pure Python, no LLM);
  report `<main checkout>/logs/evals/runs/<time>-<selector>/report.json` (git-ignored), exit 0 / 1 grader fails /
  2 evidence missing or task stopped, as the benchmark runner. Evidence by rule (main checkout or task folder,
  `{branch_slug}`), `--evidence name=path` for one task, `--references` checks graders against known verdicts.
- Tasks: `no-hook-denial` (regression): every transcript of the branch, a hook denial = `permissionDecision`
  `{source: hook, decision: reject}` (or a `PreToolUse:<tool> hook error:` tool_result); synthetic references.
  Run on this branch's real handover transcript: 1 denial found (a Write into another worktree).
- Tests: `tests/test_evals.py`.

### Skills sync — `tools/sync_skills.py`
- Status: WORKING (2026-10-06): `.agents/skills/` is canonical; the script regenerates
  `.claude/skills/` (vendored skills from `skills-lock.json` are skipped — Claude has user-level
  copies). `tests/test_skills_sync.py` fails when the copies drift.

### Herdr workspace tooling
- Status: CONFIGURED (moved from DigitalTwinProject; paths re-pointed, not re-run — backlog H6)
- `tools/herdr/` (layout repair, HUD, TOOLS/LOGS feeds for Claude and Codex, full refresh,
  pane swap, screenshot paste, cheat sheet); details in `docs/HERDR.md`.
- Herdr runs these from the main folder, so `main` must stay checked out there.
- Keys: Ctrl+B Shift+L layout · Shift+U refresh · I screenshot · Shift+H cheat sheet.

### Large files as links
- Status: WORKING (2026-10-06, Claude main; tested with a 60 MB file)
- `tools/git-hooks/link_large_files.py` via `.git/hooks/pre-commit`: new files over
  50 MB are committed as entries in `docs/sources/linked-files.json`. Toggle: Ctrl+B Shift+K.

### Subagents — `.claude/agents/` (Claude Code, read only; `docs/agents/WORKFLOW.md`)
Hooks: `.claude/hooks/subagents.py` (SubagentStart reminder and a `git status` snapshot for all five;
SubagentStop blocks until changed tracked files are named, and for `independent-checker` without a verdict table;
PreToolUse `guard` denies plain Bash writes in all five, `deny-geometry` denies `src/dt_ai/geometry/` to the
checker). Note: the desktop app did not load project subagents from this worktree; `claude -p` in it did. Tests: `tests/test_subagents.py`.
- `source-inspector` — VERIFIED (2026-10-13, PR #86): B01 `etalon.max` inventory, 4 objects (B01_ETALON + 3 LEVEL_), read from the file header without opening it over another scene.
- `pattern-librarian` — VERIFIED (2026-10-13, PR #86): "plane flush with the facade" -> C24 / `opening-plane` (and OD1); tools Read, Grep, Glob only.
- `bench-runner` — VERIFIED (2026-10-13, PR #86): B01 9/9 etalon self and model, a per-check table, the spec diff.
- `independent-checker` — VERIFIED (2026-10-13, PR #86): B01 model, a check / expected / measured / pass-fail table; reading `src/dt_ai/geometry/` denied by its hook.
- `mesh-reader` — CONFIGURED (PR #86); not yet test-called.

### Pipeline gate
- Status: WORKING (2026-10-13): installed in `.git/hooks/pre-commit` on this machine (#79 version); a commit
  of `Pipeline status: built` without `pipeline/` is blocked (manual test).
- `tools/git-hooks/pipeline_gate.py --staged` (pre-commit, every agent) and `--job jobs/<JOB>` (delivery):
  `Pipeline status` above draft needs `pipeline/spec.json` + `spec.report.json` + `check.json`; new job
  scripts name an engine gap `EG<n>`; delivery needs a committed `.py` for every `.pyc`;
  attempts limit (pipeline/state.json, #128) (`docs/HARNESS_PLAN.md` §16). Claude Code also blocks such writes at PreToolUse
  (`.claude/hooks/pipeline_gate.py`, permission "deny"), and runs of a locked job (Bash/PowerShell runner
  commands; `dt` itself refuses with exit 2). Run interception is partial (known bypasses: #144); the
  guaranteed part is the write/status/commit gate.
- Limit (user 2026-10-12 [D064], #79): a compromised environment is not covered, for example a fake `py` on PATH.

## Pipeline core (src/dt_ai, technical_library, tools)

Environment: `uv sync`; tests `uv run pytest -q` — 284 passed, 1 skipped on 2026-10-06
(AGR + DT suites merged, incl. real Blender roundtrips).

### `dt` CLI — `src/dt_ai/`
- Status: WORKING on the synthetic job (`jobs/SYNTH-001`): `dt profiles check`, `dt schemas --check`,
  `dt build`, `dt validate`, `dt index-pdf`, `dt registry merge`. Real-object use goes through the
  accepted-case tools below. `passed` is always false in this version.
- Geometry adapters (Exterior, Shell, Connect) with `AdapterReport` and Blender readback:
  proven on Obr22 (`docs/cases.md`). RunRecord inspection: `tools/harness_status.py`
  (skill `run-evidence`).

### Spec extractor — `tools/source/measure_spec_blender.py` + `dt spec extract` / `dt spec merge-questions`
- Status: WORKING on synthetic data (Claude, 2026-10-08; issues #5, #16, #6, #7): Blender 5.1 dumps
  triangles and `LEVEL_<name>` helpers; `dt spec extract --dump --object --output` writes spec v0.1
  (`schemas/Spec.schema.json`), a report and `<spec>.questions.md`. Levels are input; roof confirmed at
  the top input level; strict full-height level contour (`contour_at_m` in object.json when it asks);
  kinks, rounded corners; typical floors written once (`typical_of` / `repeat_to`, `Spec.expanded_floors()`); openings from holes in the body or glass panes (`source`); door recesses from the floor are openings (`kind` door, or window when glass fills the height), relief <= 10 cm is no kink, panes of one frame are one opening with `panes`, an opening across a level is one record with `level_from` / `level_to` (spec v0.2, #31). Spec v0.3 (#36): opening = hole with frame (mesh: the reveal; Revit: frame or curtain wall, else the family box), glass as `glass_w` / `glass_h`, `depth_m` only as an exception. Vent grilles are openings of kind `grille` (Revit: window elements without a transparent material). `dt spec extract --tolerances` reads the `spec_extract` thresholds.
  `dt spec merge-questions --report --version --into jobs/<object>/questions.md` keeps one questions
  list per object with stable ids and kept answers.
- Limits: `window_type` is always null (no material ids in the dump; window library #4); no
  attachments; roofs: drainage slopes up to 10° are one roof
  (area-weighted height, ±10 cm), separate roof parts and caps are read (#9); steeper roofs are a question.
  First real run: KPP1 v005 spec v001 (`jobs/KPP1/STATE.md`). `object.json` may give `frames` per source. Pattern: `docs/domain/patterns/wall-from-contour.md`.
- Revit path, wall lines (Claude, 2026-10-08, #29; the bounding-box route of #10 was removed after it):
  `node tools/source/measure_spec_revit_twin.mjs <new-folder>` calls the TwinPack commands of the
  revit-http add-in (`twin_floor_manifest`, `twin_export_floor` with every wall function; not in the MCP
  tool list, called through `revitClient.callRevit`), writes `floor.json` + `reference.obj` per band and
  `twin-data.json` (with the document's Levels and Roofs since MH2: `list_levels`, `list_elements` OST_Roofs,
  `get_element_info`; object.json `revit_levels` turns them into LEVEL_ helpers, `src/dt_ai/spec/markup.py`); `dt spec extract --dump <twin-data.json>` reads it (`dt_ai.spec.revit_twin`): walls as
  prisms on their location lines (any angle; curved walls from their real geometry), glass by material
  transparency, doors from records, attachments by the main-walls hull rule (user decision 2026-10-08 [D027]). The
  document is not modified (flag checked before and after); files go only to the new folder.
  KPP1: contours equal to the mesh path (0.0 mm), `jobs/KPP1/spec-compare-v002.md`.
- Intake check (Claude, 2026-10-11, IN1, HARNESS_PLAN §15): `dt intake check --dir jobs/<JOB>/intake` validates
  `sources.json` / `spec-draft.json` (schemas `IntakeSources`, `IntakeSpecDraft`), `picture.md` (Facts and
  Contradictions tables) and `questions.md`: sources and confidence of every fact, null = unknown, images at
  most estimated, the primary source by priority, the scale anchor; reports `buildable`. Procedure: skill
  `analyze-architectural-source`, intake mode. Adapters per format: IN2-IN7.
- Spec comparison (Claude, 2026-10-08, #11): `dt spec compare --a <spec> --b <spec> --tolerances
  benchmark/<id>/tolerances.json --output <cmp.json>` (+ `.md`): rows per criterion of HARNESS_PLAN §4
  with both values, threshold and reference side, contour difference regions; thresholds, reference
  sides and whether a verdict is given come from tolerances.json. KPP1: `jobs/KPP1/spec-compare-v001.md`.

### Window type list — `library/windows/window_types.json` (#4)
- Status: WORKING (Claude, 2026-10-09): 46 entries; 37 confirmed and named by the user (W01–W07, D01–D03, KPP1-W01–W03,
  WT-01–WT-24; `library/windows/confirmations.json`), the rest `unconfirmed`; 24 from `Win_Typical.max` (WT-01–WT-24, read from 3ds Max
  without changes into `library/windows/sources/win-typical-max-v001.json`; duplicates by subdivision + size ±2 cm get
  `same_as`) — SOSH1150
  typology v003 (11 types, 6 size variants; CW_021, CW_022, D04 kept as not typed) and 3 KPP1 candidates from the
  Revit spec. Rebuilt by `tools/library/build_window_types.py` from the user's library files (read only); handing
  null, sashes not in the sources. The spec's `window_type` index waits for confirmed entries.

### Operation library — `technical_library/`
- Status: WORKING per package README (Russian): `glb_atlas`, `uv_continuous` (UV v006),
  `window_atlas`, `texture_tiles`, `mesh_audit`. Scope of each = its accepted case.

## Delivery QA (tools/qa, src/twinqa, standards/)

### Standards layer — `standards/`
- Status: WORKING (2026-10-06; loader tests). One loader for both packages: `twinqa.profiles`.
- NPM/VPM profiles, validator spec V001-V017, 232-rule traceability, SHA-256 lock, regulation PDF
  (plain Git blob). Fields touched by `docs/domain/conflicts.md` carry `conflicts:` entries; checks
  report them as review. Machine-readable twin of `docs/domain/`.

### Package validator — `tools/qa/validate_package.py`
- Status: WORKING for archive composition, names, FBX header, VPM maps, UDIM sequence, GeoJSON
  (V001, V002 header, V007, V008 sequence, V011, V012); `--scene` adds V003/V004/V006/V008/V013 via
  Blender. Everything else is `not_run`; V015-V017 are manual.
- `py -3 tools/qa/validate_package.py <zip|fbx|geojson> [--profile npm|vpm] [--json] [--scene]`;
  exit 0 passed / 1 fail / 2 review or not_run left.
- Not yet: NPM embedded-atlas pixel rules (PNG bytes inside FBX), units, UCX (V010), texel density
  (V009), coordinates vs MSK-77 (V013/V014).

### FBX readback — `tools/blender/fbx_readback.py`
- Status: WORKING (2026-10-06; Blender 4.4 and 5.1 background, cube roundtrip tests)
- Triangles, polygon degrees, UV channels, UDIM tiles, mirrored UV, transforms, embedded images.

### Face overlap check — `tools/qa/check_clearance.py`
- Status: WORKING (2026-10-06; AGR boundary cases + FBX planes 3 mm apart)
- Near-parallel faces closer than 5 mm (profile), on faces JSON or FBX via
  `tools/blender/export_faces.py`. Hits need classifying (embed vs defect).

### Engine — `src/dt_ai/geometry/from_spec.py`
- Status: WORKING on synthetic specs only (2026-10-09, `tests/qa/test_from_spec.py`): the B01 fixture
  spec builds a model that passes all benchmark checks against the synthetic box; no real etalon yet.
- `build(spec, BuildInputs)` -> mesh dump (format of `measure_spec_blender.py`): walls by contour,
  holes with reveals and planes, roof, parapet; quads, welded, no T-junctions, no Shell (C23);
  plane seat by profile (C24 final, user 2026-10-10 [D037]: `npm_min` full opening depth, `mid` half).
  Build inputs not in the spec (parapet thickness, material IDs) are required arguments.
- Floor steps (pattern floor-step, 2026-10-10): a contour per floor, ledge (roof ID) / soffit (facade ID).
- Oblique walls (pattern non-90-corner, 2026-10-10): trapezoid strips for horizontal faces; B02 green end to end.
- Terraces (pattern terrace, spec v0.4 `terraces`, 2026-10-10): a parapet on a floor-step ledge (outer / inner
  face, cap, walkable part); the extractor does not read them yet.
- Not yet: rounded corners, an x-extreme sharp corner (triangle), terraces as walkable roofs, attachments, corner, touching or
  roof-level openings, cross-level openings in a typical template, writing a Blender
  scene / FBX (errors, never guesses).

### Benchmark run — `tools/qa/run_benchmark.py`
- Status: WORKING on a synthetic etalon FBX (2026-10-10, `tests/qa/test_from_spec.py`, Blender 5.1):
  etalon FBX -> spec -> engine model -> `tools/export/export_mesh_blender.py` (.blend + FBX, slot
  index + 1 = material id, LEVEL_ empties) -> FBX readback -> etalon self-check and model report.
- `uv run python tools/qa/run_benchmark.py --etalon <fbx> --object <object.json> --tolerances <t.json> --output <new folder>`;
  exit 0 both pass / 1 a check fails / 2 a step stops or a check is not measured.

### Build by source modules — `src/dt_ai/geometry/from_source.py`, `tools/qa/run_from_source.py`
- Status: EXPERIMENTAL (user, 2026-10-14 [D079]): on OBJ03 it did not give an acceptable model - open polygons,
  flipped normals, excess mesh, while the own checks passed (blind spots: normals, decor topology; issue #117).
  Tests pass on synthetic sources (`tests/qa/test_from_source.py`). What it does: the model rebuilt
  module by module from the source (`jobs/<OBJ>/modules/modules.json`, `build_as` per group) - walls per storey
  (quads), slab and deck boxes (quad fill clipped by the outline, CDT fallback counted), decor one box per
  element, planes for the roof enclosure, glass railings per ledge side - and its spec measured by the same
  modules; the same checkers as the spec path. Beside `from_spec`, not instead of it.
- `uv run dt from-source --dump <source dump> --modules <modules.json> --object <object.json> --output <new folder>`
  (model dump, spec, report); `uv run python tools/qa/run_from_source.py ... --tolerances <t.json> --output <new folder>`
  adds the FBX export, readback and checks (etalon = the source without `skip` modules).
- Pattern primitive-first (2026-10-14): two deliveries in the output folder - `modules/` (`modules-scene.json`,
  `modules.blend`: collections per group, instances share a type mesh) and `npm/` (`model.blend`, `model.fbx`); the
  blocking `complexity` check (`src/twinqa/geometry/complexity.py`) when the tolerances have a `complexity` block.

### Benchmark geometry checks — `tools/qa/check_geometry.py`
- Status: WORKING on synthetic boxes only (2026-10-09, `tests/qa/test_geometry_checks.py`); no
  real etalon yet (B01, issue #12). Logic in `src/twinqa/geometry/`.
- Model vs etalon mesh dumps (`tools/source/measure_spec_blender.py`, now with `polygon_sizes`):
  bbox, levels, storey areas, silhouettes, mesh (manifold, open edges, n-gons, overlaps), triangle
  budget, opening planes, material ID ranges; thresholds from `benchmark/<id>/tolerances.json`.
- `uv run python tools/qa/check_geometry.py <model-dump> <etalon-dump> --spec <spec.json> --tolerances <t.json> --output <report.json>`;
  exit 0 pass / 1 fail / 2 not measured or bad input.

### 3ds Max production scripts (external)
- Status: CONFIGURED (inventory only, not run) — see `docs/tools/max-scripts.md` for which
  script serves Flora, Ground, MAF, UCX, lights, and their rule mismatches.

## Project workflows

### `analyze-architectural-source`, `validate-delivery` (project skills)
- Status: CONFIGURED (written against `docs/domain/`; not yet run on a real source)
