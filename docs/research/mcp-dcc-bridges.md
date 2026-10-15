# Research Report: MCP DCC Bridges, Architecture, Concurrency, and Multi-Agent Safety

- **Date**: 2026-10-15
- **Verification Status**: Documentation and source code research based on driver-verified local evidence (labels L1–L5) and public architecture references ([1]–[15]). Public ledger sources were targeted for specific claims and setup details, not read in full. No live DCC applications were started, no smoke commands were executed, and no shared repository configuration files were modified.

---

## 1. Summary

- Configured DCC routes (`3dsmax-mcp`, `blender`, `revit-http-2025`, `revit-bridge`) decouple stdio MCP clients from DCC APIs across secondary IPC transports (named pipes, loopback TCP, loopback HTTP) (L1–L5).
- Each host DCC executes commands sequentially on its primary UI thread or queue; multiple clients do not execute simultaneous mutations on that thread at the same instant (L2–L5).
- None of the configured bridges provide cross-process session isolation, scene leasing, or multi-step transaction fences between independent agents (L2–L5).
- Without coordination, multiple agents interleave sequential operations across a workflow, risking torn inspection reads, overwritten scene modifications, and conflicting document states (L2–L5).
- Unobserved failure modes such as main-thread race conditions or socket stream desynchronization in configured Blender Lab were not verified; the actual hazard is multi-step logical interleaving without isolation (L3).
- Network aborts, client disconnections, and modal blocking dialogs leave the host DCC in an unconfirmed execution state without guaranteed automatic rollback (L2, L4, L5).
- Safe multi-agent automation requires a host-global cooperative lease coordinator with process identification (PID + start time) and strict disposable fixture lifecycles (PROPOSED).

---

## 2. Findings with Sources

### 2.1 Architectural Analysis of Configured Routes

#### 2.1.1 Autodesk 3ds Max — `3dsmax-mcp` (cl0nazepamm/3dsmax-mcp v1.7.5) [4], L1, L2
- **Two Transport Layers and Ports**:
  1. *Client to MCP Server*: Stdio JSON-RPC launched via Python process `uv run --directory C:/Users/artsafro/tools/3dsmax-mcp 3dsmax-mcp` (L1).
  2. *MCP Server to DCC Host Bridge*: Dual-transport client (`maxmcp/max_client.py`) with automatic mode (`transport=auto` in `%LOCALAPPDATA%/3dsmax-mcp/mcp_config.ini`). Prioritizes PID-pinned Named Pipes with format `\\.\pipe\3dsmax-mcp-pid-<PID>`, falling back to legacy default `\\.\pipe\3dsmax-mcp` (L2). Instance discovery reads JSON registry files from `%LOCALAPPDATA%/3dsmax-mcp/instances/*.json` and `active_instance.json` (claim), rather than scanning active OS processes (L2). When pinned or bound to an explicit target, it does not silently fall back to TCP if unavailable (raises `ConnectionError`). Only an unpinned automatic client falls back to legacy loopback TCP at `127.0.0.1:8765` (L2).
- **Exposed Commands and Surface**:
  - 179 decorated tool functions across module files in `maxmcp/tools/*.py` (L2).
  - *Functional Groups & Representative Modules*:
    - *Scene Management & Session*: `maxmcp/tools/scene_manage.py` defines only `manage_scene` and `undo_last` (L2). Other scene-level tools reside in dedicated modules: `query_scene.py` (`query_scene`), `session_context.py` (`get_session_context`), `scene_patch.py` (`scene_patch`), and `scene_qa.py` (`scene_qa`).
    - *Node Hierarchy & Objects*: `maxmcp/tools/objects.py` (`create_object`, `delete_objects`), `maxmcp/tools/hierarchy.py` (`set_parent`, `get_hierarchy`), `maxmcp/tools/transform.py` (`transform_object`), `maxmcp/tools/selection.py` (`select_objects`), `maxmcp/tools/clone.py` (`clone_objects`), `maxmcp/tools/identify.py` (`batch_rename_objects`, `isolate_and_capture_selected`).
    - *Mesh & Spline Geometry*: `maxmcp/tools/mesh_ops.py` (`inspect_mesh`, `create_mesh`, `mesh_edit`), `maxmcp/tools/booleans.py` (`boolean_operation`), `maxmcp/tools/poly_edit.py` (`edit_vertices`), `maxmcp/tools/splines.py` (`draw_spline`), `maxmcp/tools/curve_model.py` (`curve_model`), `maxmcp/tools/contact_check.py` (`contact_check`).
    - *Modifiers & Data Channels*: `maxmcp/tools/modifiers.py` (`add_modifier`, `remove_modifier`, `set_modifier_property`, `collapse_modifier_stack`), `maxmcp/tools/data_channel.py` (`add_data_channel`, `set_data_channel_operator`).
    - *Materials, Shaders & Textures*: `maxmcp/tools/materials.py` (`get_materials`), `maxmcp/tools/material_ops.py` (`assign_material`, `set_material_property`, `write_osl_shader`, `create_shell_material`), `maxmcp/tools/material_replace.py` (`replace_material`), `maxmcp/tools/material_roles.py` (`material_roles`).
    - *Lighting & Viewport*: `maxmcp/tools/lighting.py` (`create_lights`, `inspect_lights`), `maxmcp/tools/viewport.py` (`set_viewport`, `capture_viewport`).
    - *Procedural Graphs & Automations*: `maxmcp/tools/mcg.py` (`mcg_inspect_graph`, `mcg_create_graph`), `maxmcp/tools/tyflow.py` (`create_tyflow`, `modify_tyflow_operator`), `maxmcp/tools/railclone.py` (`get_railclone_style`), `maxmcp/tools/wire_params.py` (`wire_params`), `maxmcp/tools/controllers.py` (`assign_controller`).
  - *Execution Security*: Setting `safe_mode` in `mcp_config.ini` is not a formal OS-level sandbox, nor is there a project blanket ban against changing it; for the scope of this proposal, `safe_mode=true` is maintained, and disabling it requires separate explicit authorization. The `execute_python` tool delegates to `execute_maxscript` via `python_execution_script(...)`, which is gated by `safe_mode` inside the bridge, rather than performing an explicit check inside `execute_python` itself (L2).
- **Two-Client Behavior and Concurrency**:
  - Native C++ server (`native/src/pipe_server.cpp`) handles multiple inbound connections using worker threads. Read operations can query the bridge, but all scene-mutating calls are dispatched to 3ds Max's main UI thread via `native/src/main_thread_executor.cpp` (L2).
  - The server synchronizes threads per client pipe, but enforces **no cross-process scene locking**. Two independent agents communicating with the same 3ds Max instance will interleave multi-step scene edits sequentially across a workflow without isolation (L2).
- **Timeouts and Failure Semantics**:
  - `DEFAULT_TIMEOUT=120.0s` governs transport connection, TCP socket waits, and named pipe handle acquisition (`_ensure_pipe_handle`); it is NOT a guaranteed total call execution cutoff once dispatched to Max (L2).
  - Client-side acquisition of `_pipe_lock` (`with self._pipe_lock:`) is unbounded and blocks until released (L2).
  - Failure modes are distinct and must not be conflated:
    - `DialogBlocked`: Raised when a command is held by an active modal dialog on 3ds Max's main thread. The call continues executing inside Max and its outcome can be monitored or resolved via `max_dialogs` (L2).
    - `RequestOutcomeUnknown`: Raised when a request was dispatched but the pipe/socket connection closed or broke before the reply arrived. The command may have committed or failed inside Max; blind replays are strictly prohibited (L2).
- **Scene Reset and Recovery**:
  - `manage_scene(action='reset')` invokes destructive `resetMaxFile #noPrompt` (L2).
  - MaxScript `holdMaxFile` and `fetchMaxFile` maintain a single host-wide buffer, providing zero per-agent isolation. Recovery must rely on opening clean, versioned working copies.
- **Smoke Sequence (NOT EXECUTED)**:
  - Explicit PID selection via `select_max_instance(pid=<verified_pid>)` before smoke in explicit diagnostic/task scope -> `get_bridge_status()` -> on-demand `get_session_context()` bundle (not obligatory on every call) -> `manage_scene(action='info')`.

#### 2.1.2 Blender Lab — `blender` (blmcp v1.0.3) [1], [2], [3], L1, L3
- **Two Transport Layers and Ports**:
  1. *Client to MCP Server*: Stdio JSON-RPC launched via `C:/Users/artsafro/AppData/Local/CodexMCP/BlenderLab103/venv/Scripts/blender-mcp.exe --transport stdio` (L1).
  2. *MCP Server to DCC Host Bridge*: Fresh TCP socket per tool call (`tools_helpers/connection.py`) using wire type `execute`: `{"type":"execute","code":code,"strict_json":strict_json}\0` to loopback address `127.0.0.1:9877` (L1, L3). Package default port 9876 conflicts with local SketchUp per project skill, so `BLENDER_MCP_PORT=9877` is configured locally. Optional HTTP frontend on port 8000 is DEFAULT NOT running; `--host` and `--port` configure the HTTP frontend, not the addon bridge socket.
- **Exposed Commands and Surface**:
  - Exactly 26 static `@mcp.tool` definitions in `blmcp` v1.0.3 (L3).
  - Module `__init__.py` dynamically registers all tools in `blmcp.tools` whose module name does not end with `_toolcode` and does not start with `_template_` (L3).
  - The 20 non-CLI tools are: `execute_blender_code`, `get_blendfile_summary_datablocks`, `get_blendfile_summary_missing_files`, `get_blendfile_summary_of_linked_libraries`, `get_blendfile_summary_path_info`, `get_blendfile_summary_usage_guess`, `get_objects_summary`, `get_object_detail_summary`, `get_python_api_docs`, `get_screenshot_of_window_as_image`, `get_screenshot_of_window_as_json`, `get_screenshot_of_area_as_image`, `jump_to_tab_by_name`, `jump_to_tab_by_space_type`, `jump_to_view3d_object_by_name`, `jump_to_view3d_object_data_by_name`, `render_thumbnail_to_path`, `render_viewport_to_path`, `search_api_docs`, `search_manual_docs` (L3).
  - The 6 CLI-spawning tools are: `execute_blender_code_for_cli`, `get_blendfile_summary_datablocks_for_cli`, `get_blendfile_summary_missing_files_for_cli`, `get_blendfile_summary_of_linked_libraries_for_cli`, `get_blendfile_summary_path_info_for_cli`, `get_blendfile_summary_usage_guess_for_cli`. These spawn external background processes; they were not invoked during research and are not suitable for interactive scene smoke, but are not excluded from server registration.
  - The tool catalog does not exclusively target the running scene: `search_api_docs`, `search_manual_docs`, and `get_python_api_docs` operate locally on bundled documentation data without connecting to Blender, while the 6 `*_for_cli` tools execute via external CLI processes.
  - *Execution Security*: Official Blender documentation [2] explicitly notes that the server executes Python scripts directly inside the host Blender application without a sandbox, requiring trusted client environments.
  - *Registration Status*: Configured in `.claude.json` (L1), but `.cursor/mcp.json` contains no Blender registration (unregistered in Cursor).
- **Two-Client Behavior and Concurrency**:
  - Addon script `mcp_to_blender_server.py` (`AppData/Roaming/Blender Foundation/Blender/5.1/extensions/user_default/mcp/`) maintains a client list with backlog 5 (L3).
  - A modal timer callback polls connections and executes code sequentially on Blender's main thread. Because execution is sequential on the main thread, multiple agents do not mutate datablocks simultaneously at the same instant; rather, sequential scripts from different clients can interleave across a multi-step workflow without session isolation (L3).
- **Timeouts and Failure Semantics**:
  - Client socket I/O timeout is 300s (`connection.py`), serving as a socket transport timeout rather than a hard process kill (L3).
  - The in-addon server enforces a 10s timeout on incomplete incoming JSON requests and a 30s send timeout.
  - While an NVIDIA driver crash (`nvoglv64.dll`) was previously observed following MCP screenshot calls in the project environment, the exact crash causality remains unknown; live viewport screenshot calls should be avoided.
- **Scene Reset and Recovery**:
  - No dedicated MCP reset tool exists in the catalog. Reset requires authorized execution of `bpy.ops.wm.read_factory_settings(use_empty=True)` or reopening an explicit WORKING COPY via `bpy.ops.wm.open_mainfile(filepath=...)`.
  - After `open_mainfile`, `bpy.context.window` can evaluate to `None` inside timer callbacks. Operators must use `bpy.context.temp_override(...)` after reidentifying windows from `bpy.context.window_manager.windows`.
- **Smoke Sequence (NOT EXECUTED)**:
  - `get_blendfile_summary_path_info()` -> `get_blendfile_summary_datablocks()` -> read-only `execute_blender_code` querying version and scene unit settings.

#### 2.1.3 Autodesk Revit HTTP — `revit-http-2025` / `revit-2025` (KenLP/RevitMCPServer v0.8.40) [5], [10], [11], [12], L1, L4
- **Two Transport Layers and Ports**:
  1. *Client to MCP Server*: Stdio JSON-RPC launched via Node process `node C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer/dist/index.js` (L1).
  2. *MCP Server to DCC Host Bridge*: Loopback HTTP `POST /mcp` and `POST /mcp/batch` targeting `http://127.0.0.1:7891` (L1, L4). Default port for Revit 2025 is 7890, overridden locally to 7891 via `REVIT_MCP_PORT=7891`. Authenticated via a 32-byte Bearer token generated at startup (`%APPDATA%/Autodesk/Revit/Addins/<version>/revit-mcp-token.txt`). Loopback address is strictly enforced.
- **Exposed Commands and Surface**:
  - 94 literal `server.tool` registrations in `dist/index.js` v0.8.40 (L4).
  - *PROFILES Groups*: Inspection, architecture, documentation, editing, views, core/batch/recipes/coordination.
  - *Key Tools*: `revit_ping`, `revit_get_version`, `revit_get_document_info`, `revit_list_elements`, `revit_get_element_info`, `revit_list_levels`, `revit_list_wall_types`, `revit_create_wall`, `revit_create_level`, `revit_batch`, `revit_export_view_pdf`.
- **Two-Client Behavior and Concurrency**:
  - In upstream source (`McpHttpServer.cs` [10], [12]), requests are accepted on threadpool threads with a hard cap of 32 concurrent in-flight requests (shedding load with HTTP 503 `overloaded` + `Retry-After: 1`), enqueued into `ConcurrentQueue<PendingRequest>`, and drained sequentially on the Revit UI thread via `RevitMCPExternalEventHandler.cs` [11]. This 32-request limit is an upstream source observation, NOT a verified inspection of the compiled DLL installed on this machine.
  - Separate Node clients share the same addin and active document. FIFO queue execution provides single-call sequential execution, but **no multi-step session lease or agent isolation**.
  - `revit-http-2025` and `revit-bridge` MAY target the same running Revit 2025 process (this research did not query the live runtime to verify active process bindings). If both attach to the same process, they must resolve identity and share the same host lock.
- **Timeouts and Failure Semantics**:
  - Client `dist/revitClient.js` enforces a 30s abort timeout on commands and 5s on health checks (L4).
  - Client-side HTTP abort does not cancel or roll back an operation that Revit has already dequeued and started executing on its UI thread.
  - The local Node package version (`v0.8.40`, L4) does not prove the version of the C# addin DLL actually installed in Revit. A `GET /health` query could verify this, but live HTTP calls are prohibited in this research.
- **Scene Reset and Recovery**:
  - No document creation, opening, closing, saving, or resetting tools exist in this 94-tool catalog.
  - `dryRun=true` rolls back Revit transactions at commit time for preview, but does not reset modified document flags or UI states. Reset requires closing disposable working copies via authorized native UI without saving.
- **Smoke Sequence (NOT EXECUTED)**:
  - `revit_ping()` -> `revit_get_version()` -> `revit_get_document_info()` -> `revit_list_levels()`.
- **Stale `revit-twin` Registration**:
  - Claude stdio configuration (`.claude.json` top-level `mcpServers.revit-twin`, L1) launches `node C:/Users/artsafro/HerdrWorktrees/DigitalTwinProject/worktree-revit-workflow/Scripts/revit-twin/mcp/server.mjs`; that file is absent on disk (checked with `ls` on 2026-10-15).
  - Its bridge port, commands, timeouts, and reset mechanisms are uninspected and unknown; agents must not start it or assume `twin_*` commands correspond to this stale registration.

#### 2.1.4 Autodesk Revit Named Pipe — `revit-bridge` (RevitBridge 2025) L1, L5
- **Two Transport Layers and Ports**:
  1. *Client to MCP Server*: Stdio JSON-RPC launched via Node (`tools/revit-bridge-mcp/src/index.js` or `Desktop/zavod/projects/revit-bridge/src/RevitBridge.McpServer/src/index.js`) (L1, L5).
  2. *MCP Server to DCC Host Bridge*: Token-authenticated, length-prefixed JSON Named Pipe (no TCP port) with exact path `\\.\pipe\RevitBridge.Cursor.2025.<PID>` (`Protocol.cs` defines `PipeNamePrefix = "RevitBridge.Cursor"`, `BridgeHost.cs` sets `PipeName = $"{BridgeConstants.PipeNamePrefix}.2025.{Environment.ProcessId}"`) (L5).
- **Exposed Commands and Surface**:
  - Exactly 25 registered tools in `index.js` (L5): `revit_status`, `get_revit_version`, `get_active_document_info`, `list_open_documents`, `list_views`, `list_3d_views`, `list_categories`, `list_revit_links`, `get_link_status`, `get_link_transform`, `load_revit_link`, `unload_revit_link`, `reload_revit_link`, `repath_revit_link`, `load_links_from_folder`, `open_document`, `export_fbx`, `export_fbx_files`, `export_buildings_fbx`, `get_selected_elements`, `get_element_info`, `get_model_statistics`, `agr_census`, `agr_export_fbx`, `create_test_3d_view`.
  - The `open_document` operation requires `confirm: true`.
- **Two-Client Behavior and Concurrency**:
  - Host source `BridgeHost.cs` creates a single named-pipe instance (`CreateServerPipe()`) inside a sequential connection loop (`await server.WaitForConnectionAsync(ct)`) (L5).
  - A second concurrent client cannot connect simultaneously while a client is attached. Work is dispatched via Revit's `ExternalEvent` queue.
  - `revit-http-2025` and `revit-bridge` MAY target the same running Revit 2025 process. If both attach to the same process, they will collide on the Revit UI thread unless coordinated under a shared lock.
- **Timeouts and Failure Semantics**:
  - Client timeout defaults to 30s (`DEFAULT_TIMEOUT_MS = 30_000`) for standard operations (L5).
  - Extended client timeouts in `index.js`: `open_document`, `load_links_from_folder`, `export_fbx`, `export_fbx_files`, `export_buildings_fbx`, and `agr_export_fbx` are set to 900s; `agr_census` is set to 300s (L5).
  - *Mismatch Notes Documented Without Changing Code*:
    - *Mismatch A (Host Long, Client Short)*: In `index.js`, `load_revit_link`, `reload_revit_link`, and `repath_revit_link` use default forwarding without a timeout override, inheriting the Node client default of 30s, whereas host `BridgeHost.cs` (`ToolTimeoutMs`) allows up to 900s for link loading operations (L5).
    - *Mismatch B (Host Short, Client Long)*: In `index.js`, `agr_census` (300s) and `agr_export_fbx` (900s) specify extended timeouts on the Node client, but in `BridgeHost.cs`'s `ToolTimeoutMs` switch statement, `agr_census` and `agr_export_fbx` are not listed and fall through to `BridgeConstants.DefaultTimeoutMs` (30s) on the host side (L5).
  - *Cancellation Semantics*: A cancellation while waiting in Revit's `ExternalEvent` queue aborts cleanly before dispatch; however, if client timeout triggers while Revit is actively executing a command on the UI thread, the execution outcome inside Revit is unknown and cannot be rolled back from the client.
- **Scene Reset and Recovery**:
  - Contains `open_document(path)` to switch active documents, but no close, save, or revert tools.
  - Complete reset requires closing disposable working copies via authorized native UI without saving and reopening.
- **Smoke Sequence (NOT EXECUTED)**:
  - `revit_status()` alone is insufficient because it bypasses the Revit API UI thread (handled directly in `BridgeHost.cs`). A valid smoke sequence requires: `revit_status()` -> `get_revit_version()` -> `get_active_document_info()`.

---

### 2.2 Comparison with Public Alternatives

This comparison strictly distinguishes verified local implementation code (CODE), vendor README claims (README CLAIM), and design proposals (PROPOSED).

| Capability / Attribute | Configured Routes (CODE) | dcc-mcp/dcc-mcp-3dsmax [7], [14] | ahujasid/mcp-for-blender [6], [13] | mcp-servers-for-revit (Monorepo) [15] |
|---|---|---|---|---|
| **Target Application** | 3ds Max 2026, Blender 5.1.2, Revit 2025 (PROJECT RECORD; configured project versions, not runtime CODE verified this session) | 3ds Max 2017+ claimed in README [7] (README CLAIM; not independently tested) | Blender (versions unstated); community project renamed to `mcp-for-blender` [6] (README CLAIM) | Revit 2020–2026 claimed in README [15] (README CLAIM; older standalone repos [8], [9] claimed 2019–2024 and are deprecated in favor of monorepo [15]; not installed KenLP) |
| **Primary Transport** | Named pipes (`\\.\pipe\...`), loopback TCP (9877), loopback HTTP (7891) (CODE) | Shared HTTP Gateway (`127.0.0.1:9765/mcp`) + dynamic instance ports [14] (README CLAIM) | Single persistent TCP socket (180s timeout, thread lock) [13] (CODE) | WebSocket connection between Node server and C# plugin per README [15] (README CLAIM; code not inspected) |
| **Multi-Client Handling** | Multi-thread worker pools or sequential listeners; **no cross-process scene lock**; sequential UI dispatch without isolation (CODE) | Gateway instance discovery panel; process sidecar architecture [14] (README CLAIM). Client isolation unknown / not inspected in code. | Single socket with per-connection thread lock [13] (CODE). README explicitly warns to run ONE server (Cursor OR Claude, not both) [6] (README CLAIM). | WebSocket between Node server and C# plugin per README [15] (README CLAIM; code not inspected); concurrency behavior not inspected. |
| **Tool Surface / Focus** | Deep inspection, BIM parameters, spec extraction, mesh auditing (179 Max, 26 Blender, 94 Revit HTTP, 25 Revit Pipe) (CODE) | Standard modeling operations, script execution, undo claims described in README [7], [14] (README CLAIM). Exact surface not inspected in code. | Generative 3D (Tripo/Hunyuan), asset downloading (Poly Haven/SketchFab), telemetry [13] (CODE/README CLAIM). | Geometry creation, parameter coloring, raw C# code execution (`send_code_to_revit`) described in README [15] (README CLAIM). Exact tool count and catalog not inspected in code. |
| **Undo / Rollback** | Revit HTTP has per-batch `dryRun` preview rollback; 3ds Max wraps `execute_python` in undo contexts and rolls back on error, but per-tool transactional guarantees across the catalog are unknown or command-dependent; Blender has no automatic transaction rollback mechanism across arbitrary script execution (CODE). | README claims host undo wrapping [7] (README CLAIM; not independently tested). | Trajectory feedback records accept/reject; no native transaction rollback [13] (CODE). | Rollback and transaction handling unknown / not inspected in code. |
| **Testing Harness** | Standalone driver tests, offline readback tools, no live DCC execution in research (CODE). | Unknown / not inspected in code. No parity guarantees. | Evals and trajectory recording framework [13] (CODE). | Integration tests via Nice3point.TUnit.Revit against live instance described in README [15] (README CLAIM). Not tested. |

Provenance of the public column: for `mcp-for-blender` only the MCP server module `src/blender_mcp/server.py` at a pinned commit was read [13] (persistent socket, 180 s timeout, thread lock); its in-Blender addon and any reset path were not read. For `dcc-mcp-3dsmax` [7], [14] and `mcp-servers-for-revit` [15] only README/docs were read. No public bridge was run, so none of their reset, timeout or multi-client claims are verified here.

Note: `transform_object` (3ds Max) mutates the scene and is excluded from the read-only measurement table in section 3.2; any transform check must use a reviewed read-only script.

---

### 2.3 Proposed Safe Sharing Protocol (PROPOSED, Not Implemented)

Because git worktrees isolate repository files but provide **zero isolation for DCC application state, TCP ports, named pipes, or scene undo stacks**, multi-agent DCC automation requires a host-global synchronization layer.

```
+-----------------------------------------------------------------------------------------+
|                                HOST-GLOBAL LEASE COORDINATOR                            |
|               (Atomic Lockfile / Broker at %LOCALAPPDATA%/AGR-DCC-Leases/)              |
+-----------------------------------------------------------------------------------------+
       |                                                                          |
       v                                                                          v
+-----------------------------+                                            +-----------------------------+
|    Agent A (Worktree 1)     |                                            |    Agent B (Worktree 2)     |
| Task: KPP1 Spec Extraction  |                                            | Task: PSU275 Massing Audit  |
| - Requests DCC lease        |                                            | - Requests DCC lease        |
| - ACQUIRES LEASE            |                                            | - BLOCKED (Wait / Backoff)  |
|   Token: {task, pid, doc,   |                                            |                             |
|           fencing_token: 101}                                            |                             |
| - Verifies file/dirty/units |                                            |                             |
| - Runs bounded read/write   |                                            |                             |
| - Clean readback QA         |                                            |                             |
| - RELEASES LEASE            |                                            |                             |
+-----------------------------+                                            +-----------------------------+
                                                                                          |
                                                                                          v
                                                                           +-----------------------------+
                                                                           | - ACQUIRES LEASE            |
                                                                           |   Token: {fencing_tok: 102} |
                                                                           | - Operates on fresh copy    |
                                                                           +-----------------------------+
```

#### Core Components of the Safe Sharing Specification:
1. **Explicit Fencing Limitation & Broker Requirement**:
   - An advisory/cooperative lockfile token alone **cannot fence raw DCC clients**. Any external process or script connecting directly to open loopback ports (7891, 9877) or named pipes completely bypasses the lockfile.
   - True fencing requires that every client—including direct HTTP automation scripts (such as `measure_spec_revit_twin.mjs`) and MCP servers—routes exclusively through an enforcing broker or middleware layer. Until such an enforcing broker exists, a file-based lock is strictly a cooperative, best-effort convention.
2. **Process Identity and Coarse Granularity**:
   - Leases must identify the target application by **OS Process ID (PID) + Process Start Time** (creation timestamp) to prevent Windows PID recycling/reuse hazards.
   - Initial locking granularity must be the coarsest **one-at-a-time per PROGRAM** (one lease for 3ds Max, one for Blender, one for Revit). Finer per-process leasing may only be introduced after verifying separate application instances, separate export destination directories, and complete application-level state isolation. Until an enforcing broker is implemented, all cooperative locks remain best-effort.
   - Crucially, `revit-http-2025` and `revit-bridge` must share the exact same Revit program/process lease whenever they target the same application instance.
   - *Ownership Schema*: Compact explicit lease token fields: `task_id`, `agent_name`, `client_pid`, `application_pid`, `process_start_time`, `active_document_path`, `app_version`, `units`, `source_hash`, `output_directory`, `heartbeat`, `fencing_token`.
3. **Fixture Immutability, Hash Policy, and Lifecycle Teardown**:
   - *Hash Policy*: Source models (`.rvt`, `.max`, `.blend`) are strictly immutable etalons and must never be opened directly for processing. The SHA-256 hash of the ORIGINAL immutable etalon must be computed and verified **both BEFORE and AFTER** task execution and required to remain UNCHANGED. Working-copy input and output hashes must be recorded separately (working-copy outputs may legitimately change when authorized mutations or exports occur; previous phrasing around fixture copy before/after was ambiguous).
   - *Lifecycle Teardown Under Held Lease*: Before releasing the lease token, the agent must perform explicit teardown: reset or reopen a clean disposable copy under the held lease; confirm document path, system units, and expected objects; verify that the DCC is idle with no unknown in-flight requests; preserve any dirty user scene (do not discard it without explicit user authorization); and verify that the original source hash remains unchanged.
4. **Quarantine Without Auto-Disposal**:
   - Stale leases cannot be automatically stolen or cleared while a command outcome is unconfirmed (`RequestOutcomeUnknown`).
   - If an operation times out or disconnects, the coordinator transitions the resource into a **quarantine state**. Quarantined artifacts and logs must **never be automatically deleted**; they are preserved for explicit human or diagnostic reconciliation.
5. **Per-Tool Read-Only Smoke Payload Examples (Untested)**:
   - *Autodesk 3ds Max (`3dsmax-mcp`)*:
     - Step 1: `select_max_instance(pid=<verified_pid>)` before smoke in explicit diagnostic/task scope.
     - Step 2: `get_bridge_status()` -> Verify bridge communication and transport mode.
     - Step 3: `get_session_context()` (on-demand diagnostic bundle, not obligatory on every call) -> Verify real units fields (`units.systemType`, `units.systemScale`, `units.displayType`, `units.distanceBase` from `_unit_context`; not `system_unit_type`/`system_unit_scale`). Max version and document path must be read from bridge/scene response only if present (do not invent keys).
     - Step 4: `manage_scene(action="info")` -> Read-only confirmation of active file path and polycount.
   - *Blender Lab (`blender`)*:
     - Step 1: `get_blendfile_summary_path_info()` -> Verify active `.blend` file path.
     - Step 2: `get_blendfile_summary_datablocks()` -> Confirm loaded datablock counts.
     - Step 3: `execute_blender_code` with parameter `code` returning read-only version and unit settings. Code MUST begin with `import bpy\n` before result assignment because addon namespace initializes `{'result':{}}` (omitting `import bpy` causes a `NameError: name 'bpy' is not defined`):
       ```json
       {
         "name": "execute_blender_code",
         "arguments": {
           "code": "import bpy\nresult = {'version': bpy.app.version_string, 'unit_system': bpy.context.scene.unit_settings.system, 'scale_length': bpy.context.scene.unit_settings.scale_length}"
         }
       }
       ```
   - *Autodesk Revit (`revit-bridge` / `revit-http-2025`)*:
     - Named Pipe: `revit_status()` (bridge check) -> `get_revit_version()` -> `get_active_document_info()`.
     - HTTP: `revit_ping()` (bridge check) -> `revit_get_version()` -> `revit_get_document_info()`.
     - *Units Note*: Document units must be verified only if returned by official API info fields; otherwise, verify via reviewed read wrapper or manual confirmation (never assume or guess uninspected response fields).

---

## 3. How It Applies to this Repository

### 3.1 Repository Architecture and Pipeline Mapping
The AGR-DigitalTwin pipeline extracts architectural specifications from heterogeneous source formats, synthesizes delivery meshes, and validates them against Moscow municipal standards (NPM/VPM, V001–V017):
- `tools/source/measure_spec_blender.py`: Runs headless Blender scripts to dump level contours, storey heights, and opening polygons for `dt spec extract`.
- `tools/source/measure_spec_revit_twin.mjs`: Node script interacting with `revit-http-2025` via direct HTTP (`revitClient.callRevit`), calling `twin_floor_manifest` and `twin_export_floor` to extract wall prism vectors and floor boundaries into `twin-data.json`.
- `tools/blender/fbx_readback.py`: Standalone validation utility executed in clean background Blender processes (`--background --factory-startup`) to verify FBX geometry, triangle counts, transforms, UV channels, and embedded textures.
- `tools/qa/{check_geometry,check_clearance,validate_package,run_benchmark}.py` & `src/twinqa/geometry/`: Independent offline QA suite evaluating manifoldness, coplanar face overlaps, boundary clearances, and standard conformance.
- `standards/DELIVERY_VALIDATOR.yaml`: Master technical standard defining validation rules V001 through V017.

### 3.2 Measurable Attributes Executable via Reviewed MCP Scripts
The following compact table identifies project validation checks that COULD be executed through reviewed MCP read-only inspection scripts versus their offline QA runners. For each row, existing typed tool coverage is partial, and unsupported attributes require proposed reviewed scripts:

| Measurement Domain | Source DCC & Bridge (Existing Typed vs. Proposed Reviewed Script) | Target Checks / Attributes | Downstream Consumer / Offline QA Runner |
|---|---|---|---|
| **Bounding Box & Scale** | Blender: `get_object_detail_summary` (partial) / `execute_blender_code` with proposed reviewed bpy script (no dedicated `inspect_mesh` tool exists). Max: typed `query_scene`, `inspect_mesh` (partial); proposed reviewed MAXScript for full world bounds. | Min/max bounds, height, footprint extents, scale transforms | `dt spec extract`, `tools/qa/check_geometry.py` |
| **System Units & Transforms** | Blender: `execute_blender_code` (proposed reviewed script). Max: `get_session_context` (units bundle); world transforms via proposed reviewed read-only MAXScript. Revit: HTTP `revit_get_document_info`; Pipe `get_active_document_info`. | Unit scale (m/mm), world transform matrix, rotation normalization | Offline coordinate & transform checkers |
| **Mesh Geometry & Topology** | Blender: `execute_blender_code` with proposed reviewed bpy/bmesh script (no `inspect_mesh` tool). Max: typed `inspect_mesh`, `geometry_qa` (partial; `mesh_ops` is a module, not a tool; proposed reviewed MAXScript for unsupported attributes, not `execute_python` with `safe_mode=true`). | Triangle/poly counts, non-manifold edges, open boundaries | `src/twinqa/geometry/`, `tools/qa/check_geometry.py` |
| **Face Normals & Orientation** | Blender: `execute_blender_code` with proposed reviewed bpy/bmesh script (no `inspect_mesh` tool). Max: `analyze_node_orientation` (partial node orientation; does not prove full face normal correctness; proposed read-only face-normal MAXScript required). | Inverted normals, planar alignment, winding order | `tools/qa/check_geometry.py` (independent normals gate coverage needs verification) |
| **Material Slots & IDs** | Blender: `get_object_detail_summary` (partial) / `execute_blender_code` with proposed script. Max: typed `get_materials`, `get_material_slots` (partial); proposed reviewed MAXScript for multi-sub IDs. | Material assignment count, multi-sub IDs, slot names | Material role mapper, atlas packaging |
| **UV Channels & Coverage** | Blender: `execute_blender_code` with proposed reviewed bpy/bmesh script (no `inspect_mesh` tool). Max: typed `inspect_mesh` (partial); proposed reviewed MAXScript for UV layout and UDIM tiles. | UV0 unwrapping, UDIM tile assignment, channel indices | Offline UV layout & tile checkers |
| **BIM Storey & Wall Geometry** | Revit HTTP: typed `revit_list_levels`, `revit_list_wall_types` (exact HTTP tool names). Revit Pipe: `list_revit_links` (link listing only, not levels/walls; proposed reviewed script or HTTP route required for storey/wall extraction). | Storey heights, wall thicknesses, link instance positions | `measure_spec_revit_twin.mjs`, `twin-data.json` |

### 3.3 Distinguishing Measurement Tiers and Boundaries
To maintain delivery integrity, operations must be strictly categorized:
1. **Existing Scripts vs. Proposed Wrappers**: `measure_spec_revit_twin.mjs` directly dispatches HTTP calls via `revitClient.callRevit`; it checks `r.ok` and `r.error` (lines 27–30) and refuses existing output directories while recording modified flags, but operates without a shared DCC lease coordinator. Proposed reviewed wrappers must preserve those existing safeguards while integrating host-global lease fencing.
2. **Offline Checks vs. Live MCP**: Offline QA runners (`tools/qa/validate_package.py`, `fbx_readback.py`, `check_geometry.py`) consume structured dumps and exported files independently. Missing wrapper coverage or uninspected attributes does NOT constitute a pass.
3. **Independent Export Verification**: Embedded atlas inspection and reading exported files must remain an independent, clean process (e.g., executing `fbx_readback.py` in an isolated process); export success reported by a DCC scene alone does NOT prove deliverable validity.
4. **Manual Validation Gates**: Delivery rules V015 (visual facade/silhouette matching), V016 (passages/courtyard clearances), and V017 (insertion point / zero mark vs. approved DWG/SPOZU) are strict manual gates. They cannot be bypassed or marked green by automated MCP calls.
5. **Validation Policy**: Per `standards/DELIVERY_VALIDATOR.yaml` and `docs/domain/validation.md`, setting `passed=true` is forbidden while any mandatory check or manual gate remains open. Open delivery gates on active objects remain unchanged:
   - **KPP1**: Accepted ~90% by user; v007 waits for user review; open gates for GeoJSON, MSK-77, district code, and manual SINTEZ items.
   - **PSU275**: Delivery-v003 accepted; open gates for GeoJSON, MSK-77, address, УКЭП, Ground, racks, and manual items.
   - **OBJ03**: Source module build v011/v012 failed on 2026-10-14 (#117); must not be restarted without user authorization.
6. **Shared Docs Status**: In accordance with task constraints and `AGENTS.md`, `docs/agents/CAPABILITIES.md` is **not modified** by this research report.

---

## 4. Proposed Next Tasks

### Task 1: Host-Level Process Lease Coordinator for DCC Bridges
- **Scope**: Design and implement an OS-level file lock and lease registry coordinator (`tools/mcp/dcc_lease.py`) running outside git worktrees. Initial locking granularity must be one exclusive lock per PROGRAM (3ds Max, Blender, Revit), recording process identity metadata (`application_pid` + `process_start_time`), issuing fencing tokens, and tracking heartbeats; finer per-process leasing will only be enabled after verifying multi-instance isolation. Coordinates between multiple agents and prevents collisions between alias routes (`revit-http-2025` and `revit-bridge`). Until an enforcing broker is implemented, all cooperative file-based locks remain best-effort conventions. Includes CLI commands for acquire, heartbeat, status, and release.
- **Value / Effort**: Value: L | Effort: M

### Task 2: Disposable Working-Copy Fixture Lifecycle Manager
- **Scope**: Develop an automated fixture staging utility (`tools/mcp/fixture_manager.py`) that clones incoming source assets (`.rvt`, `.max`, `.blend`) into isolated, versioned working directories before any MCP tool execution. The manager computes SHA-256 fixture hashes before and after runs, verifies units and modified flags, ensures source files remain strictly untouched, and preserves quarantined artifacts without auto-disposal upon task failure.
- **Value / Effort**: Value: L | Effort: M

### Task 3: Reviewed DCC Wrapper Library for Spec Extraction and Export
- **Scope**: Refactor ad-hoc DCC automation scripts (such as `measure_spec_revit_twin.mjs` and direct `execute_blender_code` calls) into a typed, reviewed Python/TypeScript wrapper package. The library will provide structured parameter validation, explicit error envelopes, and integration with the host lease coordinator. Automatic retry on socket timeouts is **strictly unsafe for mutations**; retries must be restricted exclusively to verified pre-dispatch failures or explicitly idempotent read queries after state reconciliation.
- **Value / Effort**: Value: L | Effort: L

### Task 4: Timeout Quarantine and Recovery State Machine
- **Scope**: Implement a standardized recovery state machine for DCC bridges when requests trigger `RequestOutcomeUnknown`, `DialogBlocked`, or socket disconnects. Instead of replaying mutations or hanging agent turns, the system transitions into a diagnostic quarantine mode that captures application window state, reads scene logs, preserves all evidence without auto-disposal, and prompts for explicit operator reconciliation.
- **Value / Effort**: Value: M | Effort: M

---

## 5. Open Questions

1. **Approved Disposable Fixture Locations**: Which specific staging directories and naming conventions are authorized for disposable working copies (`.rvt`, `.max`, `.blend`) across agent worktrees?
2. **Authorization Policy for Cleaning Dirty Documents**: What explicit user authorization protocol is required to close and discard unsaved or dirty documents in host DCCs during recovery?
3. **Ownership and Architecture of Host-Global Coordinator**: Who owns and runs the host-global lease coordinator (e.g., local background service, CLI pre-flight guard, or an MCP proxy broker)?
4. **Single vs. Multiple Licensed Application Instances**: Given workstation and Autodesk licensing constraints, must all workflows strictly serialize through a single shared application instance per DCC, or are multiple concurrent instances authorized?
5. **Heartbeat Thresholds and Quarantine Safety**: A heartbeat timeout alone cannot prove that a timed-out DCC operation has safely terminated; because an agent heartbeat failure does not prove the DCC is idle, stale leases must enter quarantine rather than permitting automatic lock theft.

---

## 6. Local Evidence

- **L1**: Client MCP configuration files `.claude.json` and `.cursor/mcp.json` under `C:/Users/artsafro/`, defining stdio launch routes for `3dsmax-mcp`, `blender`, `revit-http-2025`, `revit-2025`, and `revit-bridge`. Confirmed `revit-twin` target file is absent.
- **L2**: Clean local checkout of `3dsmax-mcp` v1.7.5 at `C:/Users/artsafro/tools/3dsmax-mcp` (commit `bcd4e4c6e8e674b48bf9904f58aef708a93a9dca`). Inspected `server.py`, `maxmcp/max_client.py`, `maxmcp/tools/*.py`, `native/src/pipe_server.cpp`, `native/src/main_thread_executor.cpp`, and configuration `AppData/Local/3dsmax-mcp/mcp_config.ini`.
- **L3**: Installed Blender Lab package `blmcp` v1.0.3 at `C:/Users/artsafro/AppData/Local/CodexMCP/BlenderLab103/venv/Lib/site-packages/blmcp/` (inspected `__init__.py`, `tools_helpers/connection.py`, `tools/*.py`) and in-Blender addon `mcp_to_blender_server.py` at `C:/Users/artsafro/AppData/Roaming/Blender Foundation/Blender/5.1/extensions/user_default/mcp/`.
- **L4**: Local Revit HTTP MCP package distribution `dist/index.js` v0.8.40 and `dist/revitClient.js` at `C:/Users/artsafro/INTERACTIVE_TOUR/RevitMCPServer/`.
- **L5**: Revit Named Pipe Bridge source files at `C:/Users/artsafro/tools/revit-bridge-mcp/src/` (byte-identical to Cursor Desktop path at `C:/Users/artsafro/Desktop/zavod/projects/revit-bridge/src/RevitBridge.McpServer/src/`) and host plugin source at `C:/Users/artsafro/Desktop/zavod/projects/revit-bridge/src/RevitBridge.Revit2025/BridgeHost.cs` and `RevitBridge.Core/Protocol.cs`.

---

## Sources

[1] https://projects.blender.org/lab/blender_mcp
[2] https://www.blender.org/lab/mcp-server
[3] https://projects.blender.org/lab/blender_mcp/wiki/Setup
[4] https://github.com/cl0nazepamm/3dsmax-mcp/tree/bcd4e4c6e8e674b48bf9904f58aef708a93a9dca
[5] https://github.com/KenLP/RevitMCPServer/tree/4d273c6053be449e2066d0373d10b47c236de7ad
[6] https://github.com/ahujasid/mcp-for-blender/tree/7a0373ec9199183cb460068c4f96aed9c579fb4f
[7] https://github.com/dcc-mcp/dcc-mcp-3dsmax
[8] https://github.com/mcp-servers-for-revit/revit-mcp
[9] https://github.com/mcp-servers-for-revit/revit-mcp-plugin
[10] https://raw.githubusercontent.com/KenLP/RevitMCPServer/4d273c6053be449e2066d0373d10b47c236de7ad/docs/ARCHITECTURE.md
[11] https://raw.githubusercontent.com/KenLP/RevitMCPServer/4d273c6053be449e2066d0373d10b47c236de7ad/src/RevitMCP.Core/RevitMCPExternalEventHandler.cs
[12] https://raw.githubusercontent.com/KenLP/RevitMCPServer/4d273c6053be449e2066d0373d10b47c236de7ad/src/RevitAddin/Server/McpHttpServer.cs
[13] https://raw.githubusercontent.com/ahujasid/mcp-for-blender/7a0373ec9199183cb460068c4f96aed9c579fb4f/src/blender_mcp/server.py
[14] https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-3dsmax/main/docs/SIDECAR.md
[15] https://raw.githubusercontent.com/mcp-servers-for-revit/mcp-servers-for-revit/main/README.md
