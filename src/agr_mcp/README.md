# agr-mcp (phase 0)

Read-only stdio MCP server over the AGR checkers. Plan and decisions: `docs/plans/agr-mcp.md` (issue #841,
Artem 2026-11-04: Max through the installed 3dsmax-mcp pipe, Blender headless only, no AutoCAD,
`agr_exec_unsafe` only with `AGR_MCP_UNSAFE=1`, own repo after the phase-0 exit test).

SDK: `mcp==1.30.0` (pinned in `pyproject.toml`, extra `agr-mcp` and dev group). That SDK speaks protocol
revision `2025-11-25`; the plan's target revision 2026-07-28 is not implemented by it. `tool_schema_version`
is in every result and in the audit.

## Tools

| tool | wraps | host / lock |
|---|---|---|
| `agr_xview_check` | installed AGR Tools `runtime.xview` | max-live, `agr-3dsmax-live.lock` |
| `agr_matid_check` | `runtime.matid` | max-live |
| `agr_texel_readout` | `runtime.texel_preview` | max-live |
| `agr_fbx_readback` | `twinqa.scene.readback` | blender-batch, `agr-blender-batch.lock` |
| `agr_package_validate` | `tools/qa/validate_package.validate` | offline; blender-batch with `scene=true` |
| `agr_mesh_names` | `twinqa.naming.mesh_name_findings` | offline |
| `agr_geojson_check` | `twinqa.geojson.geojson_findings` (VPM profile) | offline |
| `agr_xview_parity` | `tools/qa/xview_parity.compare` | offline |

Phase 2 (#1021, plan section 5 "Фаза 1"): edits on copies, runtime 0.9.0, host max-live:

| tool | wraps | writes |
|---|---|---|
| `agr_cleanup_preview` / `agr_cleanup_apply` | `runtime.cleanup_preview` / `cleanup_apply` | new nodes `*_AGR_export_` |
| `agr_uv_nudge_preview` / `agr_uv_nudge_apply` | `nudge_preview` / `nudge_apply` | new nodes `*_AGR_nudge_` |
| `agr_atlas_preview` / `agr_atlas_apply` | `atlas_preview` / `atlas_apply` | new nodes `*_AGR_atlas_`, new atlas PNGs |
| `agr_ucx_preview` / `agr_ucx_apply` | `ucx_preview` / `ucx_apply` | new export copy + new `UCX_*` nodes |
| `agr_export_preview` / `agr_export_commit` | `export_preview` / `export_commit` | one new FBX + `.report.json` |

Targets are explicit: non-empty `handles` or `scope: "selection"` (never both, never neither). The selection is
restored after every phase-2 call (`selection_changed` otherwise). `preview` is the unaltered object returned by
the matching `*_preview` call; the bridge keeps the native one and accepts it once. `target` is a new absolute
`.fbx` whose report and `.partial` do not exist and are not the scene file. Audit lines add `scope`, `handles`,
`written`.

`agr_xview_check` and `agr_matid_check` keep the runtime default `select=True`: with findings they change
the selection of the pinned Max (plan section 2). No tool writes geometry or files.

Result: `{"tool_schema_version": 1, "server_version": "0.0.1", "result": <the wrapped function's output>}`.
A held lock, bad input, unknown handle, scene mismatch, wrong AGR Tools version or a MAXScript error is an
MCP error result (`isError`), never a pass.

## Environment

| variable | meaning |
|---|---|
| `AGR_MCP_MAX_PID` | pid of the open 3ds Max to use (required for Max tools; never guessed) |
| `AGR_TOOLS_ROOT` | folder of the installed `runtime.py` (default `userScripts/AGRTools-0.5.0`) |
| `AGR_MAX_MCP_DIR` | 3dsmax-mcp clone (default `C:\Users\artsafro\tools\3dsmax-mcp`) |
| `AGR_BLENDER` | Blender executable for readback (default: `TWINQA_BLENDER` / pinned 5.1) |
| `AGR_MCP_AUDIT` | audit JSONL (default `%LOCALAPPDATA%\agr-mcp\audit.jsonl`) |
| `AGR_MCP_LOCK_DIR` | lock folder (default `%LOCALAPPDATA%\Temp`) |
| `AGR_MCP_CARD` | card id written into locks and audit (falls back to `HERMES_KANBAN_TASK`) |
| `AGR_MCP_UNSAFE` | exactly `1` registers `agr_exec_unsafe` (destructive, audited with `code_sha256`) |

## Registration

`<pilot>` = a checkout of this repository after `uv sync`. Tested: `tests/agr_mcp/list_tools_stdio.py --uv`
runs exactly the `uv run --directory <pilot> agr-mcp` command below through the MCP SDK stdio client and
lists the tools. The client-specific files below were not edited on this machine.

Claude Code (user scope):

```
claude mcp add --scope user agr-mcp -e AGR_MCP_MAX_PID=<pid> -- uv run --directory <pilot> agr-mcp
```

Codex, `~/.codex/config.toml`:

```toml
[mcp_servers.agr-mcp]
command = "uv"
args = ["run", "--directory", "<pilot>", "agr-mcp"]

[mcp_servers.agr-mcp.env]
AGR_MCP_MAX_PID = "<pid>"
```

Cursor, `%USERPROFILE%\.cursor\mcp.json`:

```json
{"mcpServers": {"agr-mcp": {"command": "uv", "args": ["run", "--directory", "<pilot>", "agr-mcp"],
                            "env": {"AGR_MCP_MAX_PID": "<pid>"}}}}
```

Hermes, `~/.hermes/profiles/<name>/config.yaml`:

```yaml
mcp_servers:
  agr-mcp:
    command: "uv"
    args: ["run", "--directory", "<pilot>", "agr-mcp"]
    env:
      AGR_MCP_MAX_PID: "<pid>"
```

## Tests

- `uv run pytest tests/agr_mcp` - exit test (MCP result == direct call) for the offline tools and, on a fake
  pymxs, for the Max plumbing; locks, audit, unsafe gate, fresh stdio process.
- `uv run pytest tests/agr_mcp -m blender` - `agr_fbx_readback` against real headless Blender.
- `tests/agr_mcp/run_agr_mcp_native.py` - the three Max tools in an EMPTY interactive Max through the pipe,
  MCP result vs direct `runtime.*` call over the same pipe (see its docstring).
