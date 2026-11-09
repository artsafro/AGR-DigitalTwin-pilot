# Research: MAX Ultra MCP vs 3dsmax-mcp and the agr-mcp plan (multi-instance, selection)

Card: t_4b9cb55c (research, no GitHub issue). Date: 2026-11-04. Report only. `docs/plans/agr-mcp.md` is not edited here, because open PR #825 touches it.

Sources used:
- **MU** = MAX Ultra MCP, `https://github.com/maxpkg-dev/max-ultra-mcp`. I made a shallow clone of commit `2fcc3167fd63cc63639d2a216d5c7634389bdd6d` (2026-10-28) into the scratch directory, outside the repo. All `MU file:line` references point to that commit. Permalink base: `https://github.com/maxpkg-dev/max-ultra-mcp/blob/2fcc3167fd63cc63639d2a216d5c7634389bdd6d/<file>#L<n>`.
- **3MM** = our route `3dsmax-mcp`. Local copy `C:\Users\artsafro\tools\3dsmax-mcp`, version 1.7.5 (per the plan, §7). It is registered in `.agents/mcp_config.json:3-12`.
- **Plan** = `docs/plans/agr-mcp.md` (PR #814, merged).

I read every claim below from code or files myself, unless it is marked *(source claims)*.

## Summary

1. **Multi-instance: both 3MM and MU already handle it, but they behave differently when a call is ambiguous.** MU stops and refuses. When more than one Max is connected and the client has not chosen one, the call fails with the instance list (`core/server.js:429-446`). 3MM picks a target silently: the last claimed instance or the newest live one (`maxmcp/max_client.py:287-296`). Our `max_exec.py` pins the newest Max that is not running in batch mode (`max_exec.py:66-99`). The plan mentions none of this.
2. **Selection: MU has no general guard.** Its object-creation tools select the new node: always for primitives (`core/tool-runtime.js:247`), and by default for boxes (`:366-371`). What MU does do is state the selection behaviour in each tool's description, and its layer selection tool checks the selection after it runs (`core/layers.ms:438-443`). This confirms #816: our plan must define the selection behaviour itself.
3. **The selection problem in our plan has two sides.** The output side is the #816 finding: `_report(select=True)` changes the selection. The input side is not in #816: an empty `handles` means `runtime._targets(None)`, which reads the user's current selection (`adapters/max/agr_tools/runtime.py:205-207`).
4. **Ideas worth taking from MU:**
   - per-session instance choice, with refusal when the target is ambiguous;
   - node references guarded by a scene revision (`STALE_NODE_REF`, `core/tool-runtime.js:130`);
   - a preview → apply token bound to the instance and scene revision (`core/plan-token.js:28-43`);
   - MCP `readOnlyHint` / `destructiveHint` annotations on every tool (`core/tool-catalog.js:73-76`);
   - tool profiles (`core` / `archviz` / `full`);
   - skills served over MCP (`max_skills_list` / `max_skill_read`).
5. **MU's licence is not an open-source licence.** The repo has no LICENSE file. GitHub reports the licence as `null`, `core/package.json:22` says `"UNLICENSED"`, and the catalog says `"license":"Free"` (price 0). Take ideas only and copy no code.
6. **Do not adopt or install MU.** It would be a third Max bridge, with its own TCP daemon on port 47635 (`core/server.js:33-34`). It also includes unrestricted `max_execute` in its `core` profile (`core/tool-catalog.js:152`).

## Findings

### F1. Licence and identity (MU)

| Claim | Evidence |
|---|---|
| No SPDX licence | `gh api repos/maxpkg-dev/max-ultra-mcp` → `"license": null` (run 2026-11-04); the repo root has no `LICENSE` file (`ls` of the clone) |
| npm licence field | `core/package.json:22` `"license": "UNLICENSED"` |
| "Free" licence | `docs/MAXPKG.md:19` ("project license is permanently set to `Free`"); catalog page `https://maxpkg.dev/catalog/max-ultra-mcp` JSON-LD `"license":"Free"`, `"price":0`, `"softwareVersion":"1.5.3"` (fetched with curl, HTTP 200) |
| Author | `core/tool-catalog.js:3` "Copyright (c) 2026 Lukianenko Vasyl", website 3dground.net |
| Version | `version.ini` `Version=1.5.4`; `CHANGELOG.md:5` "1.5.4 - 2026-10-28". The catalog still lists 1.5.3 |
| Bundled third-party code | `THIRD_PARTY_NOTICES.md` (Lucide ISC, SVGL MIT, Node.js runtime) |

How to read this: "Free" is a statement about price and distribution, not a licence to reuse the code. This report describes MU's design and copies no code.

### F2. Transport and Max versions

| | MU | 3MM | Plan |
|---|---|---|---|
| MCP transport to the client | stdio. `core/stdio-host.js` runs over a `BridgeControlClient` (`:14`, `:174`). README:13 "another STDIO MCP client" | stdio, `uv run --directory … 3dsmax-mcp` (`.agents/mcp_config.json:4-10`) | stdio, one process per client (Plan §3) |
| Server ↔ Max link | A Node daemon on TCP `127.0.0.1:47635` (`core/server.js:33-34`, `:154-168`). Each Max connects to it as a client and sends `HELLO` with its instance id, pid and Max version (`python/max_ultra/client.py:73`, `:84`; `core/server.js:349-375`) | A named pipe per Max process: `\\.\pipe\3dsmax-mcp-pid-<pid>` (`native/src/bridge_gup.cpp:189-190`). Its default `\\.\pipe\3dsmax-mcp` is at `maxmcp/max_client.py:16` | Reuse the 3MM pipe in phase 0, own listener later (Plan §3, §6 Q1) |
| Max versions | README:11 "3ds Max 2022 through 2027" *(source claims)*. Real-Max acceptance was recorded only on 2022 (`docs/BRIDGE_STABILITY.md`) | README:26 "3ds Max 2023–2027"; native bridge "only 2023-2027" (README:19) *(source claims)* | Not stated |
| Runtime | Node, portable runtime bundled (`THIRD_PARTY_NOTICES.md:21`), MZP installer (`_install.ms`) | Python + C++ GUP plugin (`native/`) | Python package `agr-mcp`, AGR Tools MZP (Plan §4) |

### F3. Multi-instance routing

**MU**
- The daemon keeps a `Map` of instances keyed by instance id (`core/server.js:140`). If the same instance reconnects, it replaces the old socket and rejects requests that were still pending (`:354-358`).
- The instance id has the form `max-<year>-pid-<pid>-<ticks>` (`python/max_ultra/client.py:73`).
- Each MCP client session stores its own `selectedInstanceId` (`core/server.js:189`, `:430-431`, `:493-496`), so two agents can target two different Max processes.
- How `selectInstance` resolves a call (`core/server.js:429-446`):
  1. it takes the explicit `instance_id`, otherwise the session's choice;
  2. if that instance is unknown, it errors with the instance list;
  3. if no instance was given and exactly one Max is connected, it uses that one;
  4. if no instance was given and more than one is connected, it errors: "Multiple 3ds Max instances are connected. Call max_select_instance or pass instance_id".
- The stdio host maps that error to the code `INSTANCE_REQUIRED`. Its hint tells the agent to list the instances and ask the user one short question if the choice is ambiguous (`core/stdio-host.js:38`, `:65`).
- Every tool schema accepts an optional `instance_id` (`core/tool-catalog.js:13-15`, `:78-82`).
- Scene revisions are counted per instance (`core/tool-runtime.js:108-123`). A `NodeRef` that carries an old `sceneRevision` is rejected with `STALE_NODE_REF` (`:130`).

**3MM (local 1.7.5)**
- Tools `list_max_instances`, `select_max_instance(pid)`, `get_selected_max_instance` and `release_max_instance` exist (`maxmcp/tools/routing.py:6`, `:12`, `:18`, `:24`).
- Each Max writes `instances\<id>.json`. "Claim" writes `active_instance.json` under the local-appdata config dir (`native/src/bridge_gup.cpp:45-58`, `:135`, `:146-150`).
- Without a pin, the client uses the active claim if its pipe answers, otherwise the newest live instance (`maxmcp/max_client.py:287-296`). There is **no error on ambiguity**.
- Environment pins: `MCP_MAX_PIPE` or `MCP_MAX_PID` (`maxmcp/max_client.py:203-207`).

**Our wrapper `max_exec.py`** (`C:\Users\artsafro\hermes_kanban\scripts\max_exec.py`, outside the repo)
- `_gui_max_pid()` picks the newest `3dsmax.exe` that has no `-batch` flag and sets `MCP_MAX_PID` (`:66-99`).
- The reason is recorded in its docstring: without a pin, the client bound to a batch Max (SAFE_MODE errors on card #189).
- With two interactive Max processes it still silently picks the newest one.

**Plan**
- §3 names the locks, but not the target. The audit fields in §3 have `host` (`max-live` | `max-batch` | …) but no `max_pid` or instance id.
- The phase-0 exit test (§5) has no multi-instance case.

**Answer to the card question:** MU solves instance routing in the way we want: the session chooses the instance, and an ambiguous call is refused. 3MM can route, but it guesses. The plan should state the rule; it does not need MU for that.

### F4. Selection handling (does a tool change the user's selection?)

**MU**
- `max_create_primitive` always runs `select n` (`core/tool-runtime.js:241-249`).
- `max_create_box` runs `if select do select n`, with `select` true by default (`core/tool-runtime.js:366-371`; schema `core/tool-catalog.js:114`). `polygonMesh.select` is also true by default (`:51`).
- `max_select_objects` is an explicit selection tool (replace / add / remove / clear), classed as `write` (`core/tool-catalog.js:122`; implementation `core/tool-runtime.js:430-431`).
- `max_frame_selection` reads the selection (`core/tool-runtime.js:524`). `max_export_file` takes `selectedOnly` (`core/tool-runtime.js:509`). Both use the user's selection as an input.
- Two tools state in their descriptions that they do not change the selection: `max_material_find_unassigned` (`core/tool-catalog.js:127`) and `max_layer_set_current` (`core/layers.js`, description "without changing object selection"). README:90 says the same for the material finder.
- `max_layer_select_nodes` changes the selection only when needed, then checks that the selection count matches what was intended, and fails with `LAYER_OPERATION_FAILED` if it does not (`core/layers.ms:430-443`).
- `max_capture_viewport` is annotated `readOnly`, yet it leaves the viewport maximized (`core/tool-catalog.js:135`). A `readOnlyHint` is therefore not a promise of no UI side effects.
- No general "save selection → run → restore selection" wrapper was found. I grepped `selection` / `select` in `core/*.js` and `core/*.ms`, and the hits are the tool-specific ones above.

**3MM**
- `maxmcp/tools/selection.py:9` `select_objects`: an explicit tool.
- `selection` / `select` occurs 103 times in `maxmcp/tools/*.py`, including `booleans.py`, `identify.py` and `mesh_ops.py`. I did not check which tools change the selection.
- CAPABILITIES classes every 3MM tool as destructive (Plan §1, row 7).

**Our code (`adapters/max/agr_tools/runtime.py`, version 0.4.0)**

The output side (#816 item 3):
- `_report(..., select=True)` runs `rt.select(nodes with findings)` (`:229-236`). `xview` and `matid` use the default `True` (Plan §2 items 1-2).
- `cleanup` (`:438`), `nudge` (`:697`), `atlas` (`:1057`, `:1190`) pass `select=False`.
- The apply paths select the copies they create: `rt.select(copies)` at `:473`, `:722`, `:1770`.

The input side (new, not in #816):
- `_targets(None)` returns `list(rt.selection) or list(rt.geometry)` (`:205-207`).
- In the plan, an empty `handles` means "current targets `runtime._targets`" (§2, common input). A read-only call therefore depends on whatever the user happened to have selected at that moment. It also gives different results on two Max instances.

### F5. Tool-set side by side

MU has 88 tools in total: 75 in `core/tool-catalog.js` (counted with `grep -c '^  tool("'`) and 13 layer tools in `core/layers.js`. Its default profile is `archviz`, set with the environment variable `MAX_ULTRA_MCP_TOOL_PROFILE` (`core/tool-catalog.js:175-186`, `core/stdio-host.js:171`). 3MM has 179 `@mcp.tool` decorators in 70 files under `maxmcp/tools/` (counted with grep; README states 160, see Plan §7). I did not map the 3MM tools one by one. Where this table names a 3MM tool, I verified it.

| Group | MU tools (`core/tool-catalog.js` line) | 3MM | agr-mcp plan (§2) | Selection effect in MU |
|---|---|---|---|---|
| Skills | `max_skills_list`, `max_skill_read` (89-90). They work without Max | Bundled `skills/3dsmax-mcp-dev` installed by the installer (README:405) *(source claims)* | None. Skills live in `.agents/skills` and `.claude/skills` | none |
| Instances | `max_list_instances`, `max_select_instance` (91-92) | `list_max_instances`, `select_max_instance`, `get_selected_max_instance`, `release_max_instance` (`routing.py`) | **missing** | none |
| Health / info | `max_capabilities`, `max_health`, `max_scene_summary`, `max_query_scene`, `max_get_info`, `max_get_logs` (93-98) | not mapped | none (the plan has no health tool) | none |
| Jobs | `max_job_list/status/wait/cancel/result` (100-104), owned by the session | not mapped | none (all synchronous) | none |
| Scene files | `max_scene_new/open/save/merge/reset`, `max_undo`, `max_redo` (106-112), with `dryRun` | not mapped | none. Saving is limited to `agr_export_commit` writing a new file | — |
| Create / edit | `max_create_box`, `max_create_primitive`, `max_validate_polygon_mesh`, `max_create_polygon_mesh`, `max_clone_object`, `max_delete_objects`, `max_rename_object`, `max_transform_object` (114-121) | not mapped | `agr_cleanup_apply`, `agr_ucx_apply` (copies only) | create selects the node (see F4) |
| Selection | `max_select_objects` (122), `max_layer_select_nodes` | `select_objects` (`selection.py:9`) | **implicit**: `_report(select=True)` and `_targets` | explicit |
| Layers | 13 `max_layer_*` (`core/layers.js`) | not mapped | none | `set_current` keeps the selection |
| Materials | `max_material_create/assign/find_unassigned`, normal and smooth modifiers (125-129) | not mapped | `agr_matid_check` | find_unassigned keeps the selection |
| Import / export | `max_import_file`, `max_export_file` (`selectedOnly`) (130-131), profile `full` | not mapped | `agr_export_preview`, `agr_export_commit` | export reads the selection |
| Viewport / render | 7 view tools and 8 render tools (135-150) | not mapped | none | capture leaves the viewport maximized |
| Arbitrary code | `max_execute`, `max_run_script`, `max_run_script_file`, `max_run_macro`, `max_run_action` (152-156), profile `core`, `activity` label required | `execute_maxscript` (`maxmcp/tools/execute.py:12`), `execute_python` (`:58`) (Plan §7) | `agr_exec_unsafe` only with `AGR_MCP_UNSAFE=1` (Plan §3) | arbitrary |
| UI automation | 11 `max_ui_*` (159-169) | not mapped | none | possibly |
| Domain QA | `max_validate_floor_plan`, `max_build_floor_plan` (171-172) | not mapped | `agr_xview_check`, `agr_matid_check`, `agr_*_preview`, `agr_texel_readout`, offline `agr_fbx_readback`, `agr_package_validate`, `agr_mesh_names`, `agr_geojson_check`, `agr_xview_parity` | — |

What MU has and the plan lacks, as a design pattern:
- **MCP annotations.** `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` on every tool (`core/tool-catalog.js:73-76`). Our CAPABILITIES risk classes could be expressed with them.
- **Validate → token → build.** `max_validate_polygon_mesh` returns a 64-char `validationToken`, and `max_create_polygon_mesh` / `max_build_floor_plan` require it (116-117, 171-172). The token is the SHA-256 of a canonical binding of `{operation, instanceId, sceneRevision, request, targets, capabilities, externalState}` (`core/plan-token.js:28-43`). The plan instead has the agent send the `preview` object back (§2).
- **`dryRun` on every write tool** (schemas in 106-172; result `core/tool-runtime.js:137-138`).
- **Activity journal.** MU keeps a per-instance SQLite journal (`python/max_ultra/client.py:76`) and requires an `activity` label on arbitrary code. The plan has one machine-wide JSONL (§3).

### F6. Skills packaging

- MU ships 9 skills (README:132-148): `skills/<id>/SKILL.md` plus `skill.json` metadata (`docs/SKILL_METADATA.md`).
- They are packaged three ways:
  - Codex plugin: `plugins/max-ultra-mcp/.codex-plugin/plugin.json`, marketplace `3dground-max-ultra-mcp` (README:41-42);
  - Claude skill: `.claude/skills/max-ultra-mcp/SKILL.md`;
  - over MCP itself: `max_skills_list` / `max_skill_read`, with revision-pinned reads (`core/tool-catalog.js:89-90`; `core/skill-store.js`).
- Users can import their own skill folders or ZIPs ("instruction-only", README:118-120).
- Registration in the clients is user-scoped (`claude mcp`, README:52; Antigravity settings backup, README:57).
- Our repo keeps duplicate texts in `.agents/skills` and `.claude/skills` (Plan §1). The plan's §4 does not ship skills.

## How it applies to this repository

- `docs/plans/agr-mcp.md`. This branch does not edit it (PR #825). The proposals below say which section each one changes:
  - §2: the common input `handles` and tools 1-2 (selection);
  - §3: lock, audit fields, transport (instance target);
  - §4: registration (skills);
  - §5: exit test.
- `adapters/max/agr_tools/runtime.py:205-207, 229-236`: the input and output selection behaviour in F4. The MCP layer can avoid both without touching this file: pass explicit nodes and `select=False`, as Plan §2 already does for cleanup and nudge.
- `C:\Users\artsafro\hermes_kanban\scripts\max_exec.py:66-99`: the only place where instance choice is made today. agr-mcp phase 0 reuses this pipe (Plan §3), so it inherits the "newest non-batch Max wins" rule unless the plan changes it.
- `.agents/skills/3dsmax-mcp-dev/SKILL.md:12-14` already says "Confirm the intended application/version, active document…". It does not say "confirm the instance (pid)" when several Max processes are open.
- `docs/agents/CAPABILITIES.md` risk classes: MU's annotations show how these classes could be published in `tools/list`.

## Proposed next tasks

All proposals are plan changes (docs) or the phase-0 test spec. None of them adopts or installs MU. No open issue labelled `roadmap` or `blocker` is about agr-mcp: `gh issue list --label roadmap` returns #149, #298, #349, #352, #371, #425, #426, #753, #790, #792, and `--label blocker` returns none. #807 is closed. The open follow-ups #815 and #816 are not roadmap issues. So the honest link for each proposal is `Archive: no roadmap link`, with the related follow-up issue named.

1. **Plan §3: "Target Max instance" rule (S).**
   - Add a subsection on routing.
   - Every live-Max call resolves exactly one interactive `3dsmax.exe` pid.
   - If more than one interactive Max is running and neither `instance` / `MCP_MAX_PID` nor a session choice is set, the call is refused with the pid list. This is MU's rule (`core/server.js:429-446`), not 3MM's "newest wins".
   - A batch Max is never a target.
   - The audit JSONL gains `max_pid` and `max_version`.
   - The common Max input in §2 gains an optional `instance`.
   - Value: high, effort: S. Archive: no roadmap link (follow-up to #816 and to PR #825's plan edit).
2. **Plan §2: selection contract (S).**
   - Closes #816 item 3 and the input side from F4.
   - The MCP layer never passes `nodes=None`. An empty `handles` either errors or means an explicit `"scope": "selection"` that is logged.
   - Tools 1-2 call `_report(select=False)`, with optional opt-in `select_findings: true`, classified selection-modifying.
   - After each phase-0 call, the layer checks that the selection is unchanged (handle set before = after), in the spirit of MU's `core/layers.ms:438-443`.
   - Value: high, effort: S. Archive: no roadmap link (resolves #816 item 3).
3. **Plan §5: multi-instance and selection cases in the phase-0 exit test (M).**
   - Add three cases on the synthetic scene and a mock second endpoint:
     - an ambiguous call with two instances is refused;
     - a pinned call hits the right pid;
     - an `agr_xview_check` leaves the selection set unchanged.
   - The two-instance case may need a mock pipe or a second Max. That is a user question (Q1).
   - Value: medium, effort: M. Archive: no roadmap link.
4. **Plan §2/§3: tool annotations and a bound preview token (M).**
   - Publish MCP `readOnlyHint` / `destructiveHint` that match the CAPABILITIES risk classes, and add a selection-modifying flag.
   - In phase 1, replace "the agent sends `preview` back" with a server-issued token: SHA-256 over `{tool, max_pid, scene path / revision, handles, args}`, in the spirit of `core/plan-token.js:28-43`. An apply call with a stale token is refused.
   - Value: medium, effort: M. Archive: no roadmap link.
5. **Plan §4: skills delivery decision (S, decision only).**
   - Write down the options: keep `.agents/skills` + `.claude/skills` as they are, or have `agr-mcp` serve skill texts as `agr_skills_list` / `agr_skill_read` with revision pinning (as MU does).
   - Recommendation: keep repo skills in v1. Revisit when `artsafro/agr-mcp` is split out (Plan §6 Q5).
   - Value: low, effort: S. Archive: no roadmap link.

## Open questions for the user

1. Do you ever run two interactive 3ds Max processes at once on this PC, for example a production scene and a test scene? If yes, should a live call be refused until an instance is chosen? Recommendation: refuse, as MU does. Today `max_exec.py` silently takes the newest one.
2. Should `agr_xview_check` / `agr_matid_check` select the objects with findings when you, not an agent, call them, so you can see them in the viewport? Recommendation: off by default, opt-in flag `select_findings`.
3. Should MAX Ultra MCP be installed even for a trial? Recommendation: no. There is no open-source licence (`UNLICENSED` / "Free"), it adds a third Max bridge, and it brings a TCP daemon on port 47635 with unrestricted MaxScript in its `core` profile.
4. No roadmap issue covers agr-mcp, so every proposal above is `Archive: no roadmap link`. Should #816 (or a new roadmap issue for agr-mcp phase 0) count as the `Advances` link, so that the planner can pick these up?
5. Which 3ds Max versions must agr-mcp support? 3MM's native bridge says 2023-2027 and MU says 2022-2027 (both *source claims*). The plan names no version.
