# agr-mcp (tool_schema_version 2)

stdio MCP server over the AGR checkers and the AGR Tools plan rows. Plan and decisions: `docs/plans/agr-mcp.md`
(issue #841, Artem 2026-11-04: Max through the installed 3dsmax-mcp pipe, Blender headless only, no AutoCAD,
`agr_exec_unsafe` only with `AGR_MCP_UNSAFE=1`; v2 catalogue #1024 branch 0, owner answers 06.11.2026: apply of a
1.0 row only by a button in the panel/dock).

SDK: `mcp==1.30.0` (pinned in `pyproject.toml`, extra `agr-mcp` and dev group). That SDK speaks protocol
revision `2025-11-25`; the plan's target revision 2026-07-28 is not implemented by it. `tool_schema_version`
is in every result and in the audit.

## Tools v2 (generated from `docs/plans/agr-tools-suite.json`, `catalog.py`)

| tool | what | over MCP |
|---|---|---|
| 15 stage tools `agr_<prefix>_<name>` (`agr_project_passport`, `agr_source_intake`, `agr_body_prepare`, `agr_win_place`, `agr_win_generate`, `agr_body_capsules`, `agr_body_roof`, `agr_mat_table`, `agr_mat_tiles`, `agr_vpm_build`, `agr_npm_build`, `agr_npm_to_vpm`, `agr_pack_deliver`, `agr_agent_request`, `agr_agent_accept`) | new 1.0 stage buttons, `runtime.edits_100(row, "preview", actor="mcp")` | preview only; answer holds `preview_id`; apply = panel/dock button |
| `agr_check_run(check_ids[], scene, handles\|scope\|refs)` | 38 read/select rows (released 0.1-0.9 + 1.0 read rows), one Max call | read-only, selection restored |
| `agr_op_preview(op, scene, handles\|scope\|refs, options)` | 32 editing rows (0.8, 0.9, 1.0 small rows) | preview; server holds it, answers `preview_id` |
| `agr_op_apply(preview_id, idempotency_key?)` | apply of a held preview | only the 11 rows of 0.8; others `needs_human` |
| 3 handoff tools (1.1.0): `agr_handoff_export` (class `file`, operator+), `agr_handoff_import` (class `markup`, operator+), `agr_handoff_verify` (read, observer+) | rows `handoff.*` of plan version 1.1 (`catalog.py`, `max_side/max_bridge.py`, `max_side/agr_profiles.py`) | export/import: no `preview_id` = preview, with `preview_id` = apply of the held preview (new bundle folder, layer `AGENT_<req>`); import and verify take no selection; `handoff.restore_materials` only via `agr_op_preview`, apply by button (`needs_human`) |
| `ops_d108.register(catalog)` | branch U's D108 operations (empty stub now) | appended without editing `tools.py` |

Previews (`preview_store.py`): `preview_id = sha256(canonical(report))`; bound to host, Max pid
(`AGR_MCP_MAX_PID`), document, runtime version, `plan.state_hash`, row and targets; TTL `AGR_MCP_PREVIEW_TTL`
(1800 s). Unknown, expired, applied or re-bound -> `stale_preview`; the bridge re-checks doc and runtime version in
Max and the runtime glue re-checks the plan hash and the scene state. In memory; `AGR_MCP_PREVIEW_STORE=file` also
keeps `<data>/previews/<id>.json` across a server restart.

`refs`: ObjRef `{host: "max", doc, handle, name}` (`contract_core.obj_ref`); every finding of `findings_top`
carries `ref`. Exactly one of `handles` / `refs` / `scope`.

## Tools v1 (deprecated, kept: 52 = `tools.PHASE0`)

| tool | wraps | host / lock |
|---|---|---|
| `agr_xview_check` | installed AGR Tools `runtime.xview` | max-live, `agr-3dsmax-live.lock` |
| `agr_matid_check` | `runtime.matid` | max-live |
| `agr_texel_readout` | `runtime.texel_preview` | max-live |
| 12 `CHECKS_070`, 13 `EDITS_080`, 19 `EDITS_090` | `runtime.checks_070` / `edits_080` / `edits_090` | max-live |
| `agr_fbx_readback` | `twinqa.scene.readback` | blender-batch, `agr-blender-batch.lock` |
| `agr_package_validate` | `tools/qa/validate_package.validate` | offline; blender-batch with `scene=true` |
| `agr_mesh_names` | `twinqa.naming.mesh_name_findings` | offline |
| `agr_geojson_check` | `twinqa.geojson.geojson_findings` (VPM profile) | offline |
| `agr_xview_parity` | `tools/qa/xview_parity.compare` | offline |

The selection of the pinned Max is restored after every Max call (`selection_changed` if it cannot be).

## Phase 2 previews (#1021, [D231])

Runtime 0.9.0 copy families, preview only (read-only, max-live, schema 1, not deprecated):

| tool | wraps | apply pair (always `needs_human`, host offline, Max never called) |
|---|---|---|
| `agr_cleanup_preview` | `runtime.cleanup_preview(nodes, options)` | `agr_cleanup_apply` |
| `agr_uv_nudge_preview` | `runtime.nudge_preview` | `agr_uv_nudge_apply` |
| `agr_atlas_preview` | `runtime.atlas_preview` (PNG bytes -> `{bytes, sha256}`) | `agr_atlas_apply` |
| `agr_ucx_preview` | `runtime.ucx_preview` | `agr_ucx_apply` |
| `agr_export_preview` | `runtime.export_preview(nodes, target)` | `agr_export_commit` |

Targets: non-empty `handles` or `scope: "selection"`. A preview that leaves or deletes a node is an error. The
export `target` is a new absolute `.fbx` whose `.report.json` and `.partial` do not exist and are not the scene file
(`invalid_target`, checked before Max). Apply is the button in the AGR Tools panel/dock (owner answers 06.11.2026);
`max_bridge` refuses the five apply names with `needs_human` as a second line.

## Answer: envelope v2 (`envelope.py`)

`structuredContent`: `tool_schema_version: 2`, `server_version`, `tool`, `status`
(`pass|fail|ok|not_implemented|...`), `summary` (<= 10 lines), `counts`, `findings_top` (<= 20, with `ref`),
`truncated`, `report_uri` (`agr://report/<sha256>`, file `<data>/reports/<sha256>.json`, data =
`AGR_MCP_DATA_DIR` or `%LOCALAPPDATA%gr-mcp`), `next_actions`, optional `preview_id`, `runtime_version`, `doc`,
and `result`. v1 tools: `result` always, text content = the JSON envelope (v1 consumers keep reading
`structuredContent.result`). v2 tools: text content = `summary`; `result` dropped above `AGR_MCP_INLINE_MAX`
bytes (64 KiB) - then `report_uri`.

Errors: `isError` with `structuredContent = {status: "error", error_code, error, summary, next_actions}`; the text
is the error message. Codes: `busy`, `stale_preview`, `scene_mismatch`, `version_mismatch`, `instance_ambiguous`
(reserved, branch U), `invariant_broken` (reserved, D108), `needs_human`, `host_unavailable`, `handles_required`,
`target_conflict`, `unknown_handle`, `selection_changed`, `not_implemented`, `runtime_missing`,
`unsupported_tool`, `idempotency_conflict`, `invalid_input`, `unknown_tool`, `maxscript_error`, `error`.

## Journal

One journal for the panel and MCP: `adapters/max/agr_tools/journal_core.py`
(`%LOCALAPPDATA%\AGRTools\journal\<sha1(doc)>.jsonl`, `AGR_JOURNAL_DIR` overrides). Every call gets one line,
actor `mcp`: written by the runtime inside Max for `edits_080/090/100` rows (the bridge passes `actor="mcp"`
when the runtime accepts it), by the server (`journal.py`) for everything else, errors included. The transport
audit (`AGR_MCP_AUDIT`) stays as the security log.

## Environment

| variable | meaning |
|---|---|
| `AGR_MCP_MAX_PID` | pid of the open 3ds Max to use (required for Max tools; never guessed) |
| `AGR_TOOLS_ROOT` | folder of the installed `runtime.py` (default: the newest `userScripts/AGRTools-<x.y.z>` at or above the tool's minimum) |
| `AGR_MAX_MCP_DIR` | 3dsmax-mcp clone (default `C:\Users\artsafro\tools\3dsmax-mcp`) |
| `AGR_BLENDER` | Blender executable for readback (default: `TWINQA_BLENDER` / pinned 5.1) |
| `AGR_MCP_AUDIT` | audit JSONL (default `%LOCALAPPDATA%\agr-mcp\audit.jsonl`) |
| `AGR_MCP_LOCK_DIR` | lock folder (default `%LOCALAPPDATA%\Temp`) |
| `AGR_MCP_CARD` | card id written into locks and audit (falls back to `HERMES_KANBAN_TASK`) |
| `AGR_MCP_UNSAFE` | exactly `1` registers `agr_exec_unsafe` (destructive, audited with `code_sha256`) |
| `AGR_MCP_DATA_DIR` | server data: `reports/`, `previews/` (default `%LOCALAPPDATA%gr-mcp`) |
| `AGR_MCP_INLINE_MAX` | bytes of `result` a v2 answer carries inline (default 65536) |
| `AGR_MCP_PREVIEW_TTL` | seconds a held preview may be applied (default 1800) |
| `AGR_MCP_PREVIEW_STORE` | `file`: also keep previews on disk across a restart |
| `AGR_JOURNAL_DIR` | journal folder (journal_core; default `%LOCALAPPDATA%\AGRTools\journal`) |

## Registration

`<pilot>` = a checkout of this repository after `uv sync`. Tested: `tests/agr_mcp/list_tools_stdio.py --uv`
runs exactly the `uv run --directory <pilot> agr-mcp` command below through the MCP SDK stdio client and
lists the tools (`tools.LISTED`, 70). Repo registration: `.agents/mcp_config.json` (`agr-mcp`). The
client-specific files below were not edited on this machine.

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
  pymxs, for the Max plumbing; locks, audit, unsafe gate, fresh stdio process; `test_agr_mcp_v2.py`: catalogue
  from the plan, envelope v2, held previews / stale_preview, needs_human, one journal line per call, error codes,
  ObjRef.
- `uv run pytest tests/agr_mcp -m blender` - `agr_fbx_readback` against real headless Blender.
- `tests/agr_mcp/run_agr_mcp_native.py` - the three Max tools in an EMPTY interactive Max through the pipe,
  MCP result vs direct `runtime.*` call over the same pipe (see its docstring).
