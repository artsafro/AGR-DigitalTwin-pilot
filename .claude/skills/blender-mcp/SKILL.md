---
name: blender-mcp
description: 'Inspect the open Blender 5.1.2 or later scene through the project''s official Blender Lab MCP route and diagnose connection gaps. Use when: «что открыто в Блендере?», «посмотри объект в сцене Blender», «Blender MCP не отвечает».'
---

# Blender MCP for project agents

## Risk gate before mutation

Before any write, name the exact tool/operation and its risk class from
[`CAPABILITIES.md#dcc-tool-risk-classes`](../../../docs/agents/CAPABILITIES.md#dcc-tool-risk-classes).
For batches use the highest risk of any operation. `versioned-write` requires task
authorization and a new versioned path (including sidecars); `destructive` requires
explicit authorization for the exact mutation, even when the final save is versioned.
Unknown operations and arbitrary code default to destructive. Confirm application,
document, units and version; preserve sources and accepted outputs. Apply the
[Permission matrix and DCC gate](../../../docs/agents/WORKFLOW.md#gate-dcc-authorization)
before execution; authorization never permits a prohibited overwrite. Read outputs
back before reporting success. Inspection and live-mutation coverage are separate.

## Connect and identify

0. Port check first, before asking the user anything. Session «Garibaldi
   NPM→VPM», 2026-11-05: ~30 min were lost on bridge toggling. Run
   `netstat -ano | grep LISTENING | grep -E ':(9876|9877) '`, then
   `tasklist /FI "PID eq <pid>"` for each owner. 9877 owned by `blender.exe` =
   a Blender bridge is up; 9876 = SketchUp, never Blender data; nothing on 9877
   = no bridge. Tell 9877 from a stray listener with a no-code probe: send
   `{"type":"ping"}` + NUL to 127.0.0.1:9877; the Blender bridge answers
   `Unknown request type: 'ping'`. If 9877 is free or the task needs no live
   user scene, go to "Agent-owned Blender on a copy" instead of asking the
   user to open, start or restart anything.
1. Use `blender`, the installed Blender Lab MCP 1.0.3 route. Project client
   configs set `BLENDER_MCP_HOST=127.0.0.1`, `BLENDER_MCP_PORT=9877`.
   Port 9876 belongs to SketchUp. CLI `--host`/`--port` bind the HTTP transport;
   they do not configure the Blender extension bridge.
2. Confirm Blender 5.1.2 or later and the intended open scene through the
   native app. Call `get_blendfile_summary_path_info`, then
   `get_blendfile_summary_datablocks` and `get_objects_summary`.
   These take no arguments. Confirm source path, saved/dirty state and objects
   before relying on the connection. A blank path means an unsaved scene.
3. Require outer MCP success and inner JSON `status="ok"`. Connection failure
   or a protocol response from SketchUp is not usable Blender data.
4. If the user's own instance is disconnected, inspect Preferences > Add-ons >
   MCP: enabled, Host localhost, Port 9877, Auto Start checked. Online Access
   must be enabled in System preferences; changing preferences in the user's
   own instance requires his authorization [D233]; an agent-owned instance
   needs none (next section).
   Click Start MCP Bridge Server and confirm Server is running. Explicitly
   Save Preferences after setup. Changing client config requires Codex reload
   and a fresh actual Codex tool call, even if a separate stdio probe passes.

## Agent-owned Blender on a copy

The agent may start its own Blender 5.1.2+ with Online Access and the bridge
on 9877 without asking each time [D233]. Never ask the user to toggle the
bridge in his instance; never touch his instance or its preferences.

1. Port 9877 must be free (step 0). If a Blender the agent did not start holds
   it, that is the user's: inspect it read-only or use `blender -b` on a copy.
2. Copy the scene to a new versioned path (`<name>_agent_v001.blend`) with
   `test ! -e <copy> && cp <source> <copy>`: an existing target or a copy path
   equal to the source stops with exit 1 (`cp -n` would skip silently with exit
   0). Then hash the source alone beside the copy:
   `sha256sum <source> > <copy dir>/SHA256SUMS.txt` (the copy is edited later).
3. Launch: `"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
   --online-mode <copy>` (terminal `background=true`). `--online-mode` enables
   Online Access for this session only; the add-on's Auto Start opens the bridge
   on the saved port 9877 (the add-on default 9876 would collide with SketchUp).
4. Record the agent's own PID and file: re-run step 0 after launch; the new
   9877 owner PID's `powershell -NoProfile -Command "(Get-CimInstance
   Win32_Process -Filter 'ProcessId=<pid>').CommandLine"` must name the copy.
   Then identify the scene through MCP (step 2 above).
5. Close only its own instance: `taskkill /PID <own pid>`, never by image name
   and never a PID it did not start; after closing, port 9877 is free and
   `sha256sum -c <copy dir>/SHA256SUMS.txt` (source line only) still passes.

## Inspection tools

Seven scene inspection tools were verified on the default unsaved scene:
`get_blendfile_summary_path_info`, `get_blendfile_summary_datablocks`,
`get_blendfile_summary_missing_files`,
`get_blendfile_summary_of_linked_libraries`,
`get_blendfile_summary_usage_guess`, `get_objects_summary`, and
`get_object_detail_summary` with `name` from the live inventory.
Empty missing-file/library lists on that scene do not prove populated-source
coverage. Inspect fresh tool schemas before using other tools.

## Safety and recovery

- The extension executes Python with the app's rights; it has no effective
  sandbox. Prefer typed inspection tools. Review any Python before execution;
  require task authorization for edits, saves, exports, filesystem or network
  operations and save only to a versioned output. Setup permission does not
  authorize production-scene changes.
- `_for_cli` tools can launch another Blender process and are not substitutes
  for identifying the open scene. Inspect their behavior before use.
- The two MCP image tools returned images on 2026-10-06, followed by a native
  NVIDIA `nvoglv64.dll` access violation. Causality remains unknown. Use native
  Computer Use captures meanwhile; do not repeat that capture path on a source
  scene to establish coverage. Preserve crash evidence before recovery.
- Production fixture QA exercised Python creation, transforms, material, UVs,
  bevel modifier, native save/reopen, FBX export/import and saved roundtrip.
  Native Computer Use confirmed the imported blue beveled object. Evidence:
  `tmp/mcp/blender-production-20261006T174642Z/recovery_report.json`.
  Rendering and CLI variants remain untested; the catalog is not full coverage.
- After `open_mainfile`, a timer callback may have `bpy.context.window=None`.
  Select a real `bpy.context.window_manager.windows` entry and use
  `bpy.context.temp_override(window=window, scene=scene, view_layer=...)`
  for operators. Reidentify the loaded file before continuing after a failure.
- Heavy passes (UDIM bake) block the Blender main thread and MCP calls time out;
  sleeping/polling does not help. Run them in a separate background Blender
  (`blender -b`) on a versioned copy and read the result back (2026-11-05,
  «Garibaldi NPM to VPM conversion», G5; retro problem 3).

Connection evidence and pending Codex reload are recorded in
`tools/mcp/README.md` and `tools/mcp/verification.txt`.
