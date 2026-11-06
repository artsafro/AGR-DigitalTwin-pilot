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

- Local: `C:\Users\artsafro\.AGR-DigitalTwin_pilot` (branch `main`); GitHub `artsafro/AGR-DigitalTwin-pilot`
  (private, `origin`). The upstream `artsafro/AGR-DigitalTwin` (`C:\Users\artsafro\AGR-DigitalTwin`) is a separate repo. Task worktrees: the agent's own worktree folder or
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
- Status: WORKING for one scoped live cycle (Codex, 2026-11-03, Max 2026.3.0.30732, dedicated
  empty process pinned by PID, synthetic Box + Sphere): create → read → transform → `undo_last`
  (position restored, confirmed by readback) → `geometry_qa` → agent viewport → Save As (MAXScript)
  → reopen with an unsaved sentinel gone. Not validated: production scenes, export/import,
  materials/UV, render, Max 2024. Server health check 2026-10-06.
- Evidence (outside this repo, git-ignored): `C:\Users\artsafro\.codex\worktrees\ece9\.AGR_Project\tmp\mcp-research-20261103\`
  `LIVE_TEST.md`, `LIVE_QA.json` (sha256 `94b30523…b1b0`), `mcp_cycle_2026_v001.max` (`91f10f5a…bab5`);
  comparison with Max Ultra 1.5.4 and MaxForge in `..\mcp-compare-20261103\COMPARISON.md`: keep this
  route (both candidates failed Undo in that test; Max Ultra is `UNLICENSED`, MaxForge forbids
  derivative works).
- Known issues (same run): `create_object` with `pos` fails («Invalid position parameter», nothing
  created) — create without `pos`, then `transform`; `manage_scene(save)` saves only to the current
  path — Save As to a new versioned path via MAXScript; a newly started Max registers itself and
  becomes the default target — pin the exact PID; the agent viewport does not redraw while Max is
  hidden; the Max 2026 startup shows the `polyunwrapper_autoload.mse` .NET error dialog (see
  Toolchain smoke above). Source review (PR #793): `query_scene(action="class", scope="refs")`
  passes `class_name`/`superclass` to MAXScript `execute`, and the TCP fallback of `property`
  inserts `property_name` as code — safe_mode does not block that; hence the narrow read-only row.
- Owner: Claude (main) · scope: user (all projects)
- Server: cl0nazepamm/3dsmax-mcp v1.7.5 (commit `bcd4e4c6`, licence MIT), `C:\Users\artsafro\tools\3dsmax-mcp`; plugin in
  `C:\ProgramData\Autodesk\ApplicationPlugins\3dsmax-mcp`; `safe_mode = true`
- Use: 3ds Max 2026 (2024 is forced to run as administrator and may not connect from a
  non-elevated client). Skill: `3dsmax-mcp-dev`.

### AGR checkers and AGR Tools rows — `agr-mcp`
- What: our own stdio MCP server (`src/agr_mcp`, `uv run --directory <pilot> agr-mcp`) over the AGR
  checkers and the AGR Tools plan rows; it reaches the pinned open 3ds Max through the `3dsmax-mcp`
  pipe above and calls only the installed AGR Tools `runtime.*`. Plan: `docs/plans/agr-mcp.md`;
  usage: `src/agr_mcp/README.md`. Registered in `.agents/mcp_config.json` (directory
  `C:\agr\AGR-DigitalTwin-pilot`); set `AGR_MCP_MAX_PID` to the pid of the open Max per session —
  without it every Max tool answers `host_unavailable`, it never picks a Max by itself.
- Status: CONFIGURED, tool_schema_version 2 (#1024 branch 0, 2026-11-06). Unit-tested on a fake pymxs;
  the v2 tools have not been run against a live Max yet (L12 checks latency, one Undo record,
  selection restore, slot isolation).
- Catalogue (generated from `docs/plans/agr-tools-suite.json`): 15 stage tools of 1.0
  (`agr_project_passport` … `agr_agent_accept`), `agr_check_run` (38 read rows), `agr_op_preview`
  (32 editing rows), `agr_op_apply`; plus the 52 v1 tools, deprecated. Profiles
  (`observer` / `operator` / `modeller` / `dev`) do not exist yet — branch U; today every tool is listed.
- Preview-only rule: editing rows answer a preview held by the server (`preview_id`, bound to host,
  Max pid, document, runtime version and scene state hash; TTL 30 min). `agr_op_apply` applies only
  the 0.8 rows (export copies, new files, UCX rename in one undo record); every 0.9 / 1.0 row answers
  `needs_human` — apply is the user's button in the AGR Tools panel/dock (owner answers 06.11.2026).
- Journal: one journal for panel and MCP (`journal_core.py`, `%LOCALAPPDATA%\AGRTools\journal`),
  one line per call with actor `mcp`; plus the transport audit `%LOCALAPPDATA%\agr-mcp\audit.jsonl`.
- Errors carry `structuredContent.error_code`: `busy`, `stale_preview`, `scene_mismatch`,
  `version_mismatch`, `needs_human`, `host_unavailable`, `handles_required`, `target_conflict`,
  `unknown_handle`, `selection_changed`, `runtime_missing`, `invalid_input`, … (`instance_ambiguous`,
  `invariant_broken` reserved for branch U / D108).
- `agr_exec_unsafe` exists only with `AGR_MCP_UNSAFE=1` (destructive, audited).
- Owner: Claude (main) · scope: repo (`.agents/mcp_config.json`)

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
  uses `revit-http-2025` instead (`docs/pipeline-tools.md`, "Spec extractor").

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
- bpy wheel pin rule: a bpy wheel lane, if used, must equal the baseline Blender version 5.1.2 (`BLENDER_VERSION` in `src/dt_ai/core/blender_runner.py`) and is re-verified on each Blender upgrade.

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

Offline DCC preparation and the native-run handoff runbook (not a verified adapter):
`docs/agents/dcc-offline-workflows.md`. Adapters and evidence log: `tools/mcp/README.md`, `tools/mcp/verification.txt`. All routes are
registered for Codex and Antigravity; Claude uses only its own user-scope registrations.
Project sessions load only the DCC servers [D130]: `.claude/settings.json` sets `disableClaudeAiConnectors`
(claude.ai connectors such as Gmail, Zoom, Drive stay out of terminal, VS Code and JetBrains sessions;
GitHub works through `gh`); desktop-app and cloud sessions ignore that key, there the connectors are
switched off at claude.ai/customize/connectors.

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
| 3dsmax-mcp | `get_selected_max_instance`; `query_scene` with `action` `overview` or `selection` only; `get_object_properties` by `name`/`handle`; `geometry_qa` (scene untouched; the server writes and deletes its own temp snapshot file) — source-inspected at `bcd4e4c6`, used in the 2026-11-03 live cycle | read-only |
| 3dsmax-mcp | All other tools and operations, including `query_scene` `class`/`property`/`filter`/`delta` (caller strings reach MAXScript `execute` or unquoted code on the TCP path; `delta` resets a baseline), `select_max_instance` (rebinds the session), `manage_scene`, viewport tools and script execution; inspect schema before use | destructive |
| agr-mcp | `agr_check_run`, `agr_op_preview`, the 15 stage tools (preview only), v1 checks and every v1 `mode=preview` / read tool; the selection is restored after each call | read-only |
| agr-mcp | v1 `mode=apply` of the 0.8 copy/file rows (export copies and new files, never overwrites) | versioned-write |
| agr-mcp | `agr_op_apply` (its 0.8 rows include `ucx.rename`, an in-place rename in one undo record), v1 `agr_ucx_rename` apply, `agr_exec_unsafe` (only with `AGR_MCP_UNSAFE=1`) and anything not listed | destructive |
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

Hooks, permission lists, guard rule sets, commands, subagents and git hooks — inventory, evidence, status of the
guard, context-rotation hooks, subagents and pipeline gate, re-examination rules and the rule-layer size:
`docs/agents/harness-inventory.md`. The guard is CONFIGURED for Claude Code, Antigravity and Codex; Codex payload
and "ask" support are not validated (backlog H1).

### Kanban board — GitHub Projects `artsafro/projects/1`
- Status: WORKING (2026-10-14): Status and Agent fields; `gh` needs the `project` token scope. Rules:
  `docs/agents/KANBAN.md`. Vibe Kanban: REJECTED (2026-10-14 trial, 0.1.44), reasons in the same file.

### Evals runner — `dt evals` (#122)
- Status: WORKING (2026-10-15, PR #142): `uv run dt evals --suite regression|capability` or `--task <id>`;
  graders in `src/twinqa/evals/graders.py` (pure Python, no LLM); exit 0 / 1 grader fails / 2 evidence missing.
  Tasks, evidence rules and reports: `evals/README.md`. Receipt and handoff checks (`--check-receipt`,
  `--check-handoff`, `src/twinqa/evals/handoff.py`): `docs/agents/WORKFLOW.md#before-requesting-review-author`.
  Tests: `tests/test_evals.py`, `tests/test_evals_handoff.py`.

### Skills sync — `tools/sync_skills.py`
- Status: WORKING (2026-10-06): `.agents/skills/` is canonical; the script regenerates
  `.claude/skills/` (vendored skills from `skills-lock.json` are skipped — Claude has user-level
  copies). `tests/test_skills_sync.py` fails when the copies drift.

### Herdr workspace tooling
- Status: CONFIGURED (moved from DigitalTwinProject; paths re-pointed, not re-run — backlog H6).
  `tools/herdr/`; details, keys and rules in `docs/HERDR.md`. Herdr runs from the main folder, so `main` must
  stay checked out there.

### Large files as links
- Status: WORKING (2026-10-06, Claude main; tested with a 60 MB file)
- `tools/git-hooks/link_large_files.py` via `.git/hooks/pre-commit`: new files over
  50 MB are committed as entries in `docs/sources/linked-files.json` (created on first use). Toggle: Ctrl+B Shift+K.

### Lab CI — `lab-ci.toml` (lab laptop DESKTOP-IHMQLNS, `artsafro/agr-lab`)
- Status: CONFIGURED (`lab-ci.toml` on `main` since 2026-11-05); a run of this repo on the laptop is not recorded here.
- The laptop runs this repo's tests on every new commit of `main`, `harness/*`, `fix/*`, `feature/*` and nightly:
  checkout → `uv sync --frozen --python 3.13` → build `AGR-Tools.mzp` → slots `blender` (`pytest -m "blender or dcc"`,
  `DT_BLENDER` = Blender 5.1.2), `unit` (default suite `-n 8`; nightly/first/manual only), `agr-tools-max2024`,
  `agr-tools-checks-max2024` (`tests/max_tools/run_agr_tools_native.py`, `run_agr_tools_checks_native.py`, batch
  3ds Max 2024, synthetic scenes). JUnit results are compared with the branch's previous run; verdict GREEN /
  CHANGED / RED to Telegram, report `C:\agr\lab-data\ci\reports\ci-pilot-<sha8>-*.md`.
- Limits: `pytest -m max` is not run (needs 3ds Max 2026 and `dcc_batch.py`); a branch without `lab-ci.toml` is
  skipped. Change the pipeline in `lab-ci.toml`, not in agr-lab.

## Shared tools

One line per shared tool, grouped. Commands, exit codes, limits and evidence: `docs/pipeline-tools.md` (section
named after the tool); production stages: `docs/pipeline.md`; environment and test commands:
`docs/agents/agents-reference.md`. Status words as above, plus TOOL ONLY (no real-object acceptance) and
EXPERIMENTAL.

Pipeline core:
- `dt` CLI, `src/dt_ai/` — WORKING on the synthetic job `jobs/SYNTH-001`; `passed` is always false; RunRecord
  inspection `tools/harness_status.py` (skill `run-evidence`).
- Spec extractor `tools/source/measure_spec_blender.py`, Revit path `tools/source/measure_spec_revit_twin.mjs`,
  `dt spec extract|merge-questions|compare`, `dt intake check` — WORKING on synthetic data; first real run KPP1.
- Engine `src/dt_ai/geometry/from_spec.py` — WORKING on synthetic specs only.
- Build by source modules `src/dt_ai/geometry/from_source.py`, `tools/qa/run_from_source.py` — EXPERIMENTAL [D079].
- Window type list `library/windows/window_types.json` (`tools/library/build_window_types.py`) — WORKING, 67 entries.
- Window library preview `tools/library/window_library_preview.py` (Blender, headless) — WORKING (2026-11-05): every
  type laid out flat by role (frame, `panes_m` glass, `opaque_m` leaves, label, red = unconfirmed) into a new `.blend`
  for a visual check; not a production asset.
- Operation library `technical_library/` — WORKING per package README.
- Album page reader `src/dt_ai/album/` (#317) — on `main`, synthetic PDFs only.
- Placement engine `src/dt_ai/placement/engine.py` (#316) — on `main`, synthetic tests only.
- Project state `tools/state/project_state.py` — WORKING; rule `docs/agents/WORKFLOW.md`, "Project state";
  `tools/state/project_state_freshness.py` is an advisory read-only freshness check.
- AGR Tools for 3ds Max 2024/2026, `adapters/max/agr_tools/` (build `tools/max/build_agr_tools.py`) — diagnostic
  and checked-export tool, not a delivery validator; version, install, native evidence: its `README.md`,
  `CHANGELOG.md`; native runners in `tests/max_tools/`.

Export:
- `tools/export/export_mesh_blender.py`, `tools/export/export_modules_blender.py` — Blender scene + FBX writers of
  the benchmark and from-source runs.
- `tools/export/batch_export_max.py` + `batch_export_plan.py` (#224) — resumable per-object MAX/FBX export from one
  headless Max session via `dcc_batch.py`; synthetic probes `export_safety_probe_max.py`,
  `benchmark_export_max.py`, `report_export_benchmark.py`; tests `tests/test_batch_export_plan.py`.

Delivery QA:
- Standards layer `standards/` + loader `twinqa.profiles` — WORKING.
- Package validator `tools/qa/validate_package.py` — WORKING for V001, V002 header, V007, V008, V011, V012
  (`--scene` adds V003/V004/V006/V008/V013); the rest `not_run` or manual.
- FBX readback `tools/blender/fbx_readback.py` — WORKING (Blender 4.4 and 5.1).
- FBX structure facts `tools/blender/fbx_structure.py` (#339) — parts-list facts in a factory Blender process
  [D110, D111]; tests `tests/parts/`.
- Zero-area check `tools/qa/fbx_zero_area.py` (#979) — zero-area faces, zero-length edges, slivers of an FBX without
  Max; exit 0 pass / 1 findings / 2 unreadable.
- UCX builder `src/dt_ai/geometry/ucx_build.py`, `tools/blender/ucx_build.py`; audit `tools/blender/ucx_audit.py` —
  TOOL ONLY (#166).
- Overlap gate `dt qa xview` (`src/dt_ai/ops/inv_xview.py`, `xview_gate.py`, #527) — WORKING; 3ds Max xView runner
  `tools/qa/xview_dump.ms` (#528), parity `tools/qa/xview_parity.py`, frozen benchmark `tools/qa/xview_bench.py`.
- Face overlap check `tools/qa/check_clearance.py` — WORKING.
- Benchmark run `tools/qa/run_benchmark.py`, geometry checks `tools/qa/check_geometry.py` — WORKING on synthetic
  etalons only.
- Methods catalog runner `tools/methods/run_variant.py`, `tools/methods/ucx/run_benchmarks.py` (#706) — WORKING.
- Preview QA `tools/qa/render_qa.py` (numerical, not acceptance; limits in `tools/qa/render_qa.md`) and the advisory
  VLM checklist `tools/qa/vlm_checklist.py` (#768, research) — advisory only.
- Capability session launcher `tools/qa/capability_b01.py` — harness eval support (`tests/test_capability_b01.py`).
- 3ds Max production scripts (external) — CONFIGURED, inventory only: `docs/tools/max-scripts.md`.

Project skills `analyze-architectural-source`, `validate-delivery` — CONFIGURED (written against `docs/domain/`;
not yet run on a real source).
