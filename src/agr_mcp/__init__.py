"""new-case: agr-mcp, stdio MCP server over the AGR checkers and AGR Tools rows (docs/plans/agr-mcp.md).

Kept import-light on purpose: `max_bridge` is imported inside 3ds Max's Python, which has no `mcp` package.
"""

SERVER_NAME = "agr-mcp"
SERVER_VERSION = "0.1.0"
# Bump on any breaking change of a tool input or output field (plan section 4).
# 2 (#1024, branch 0): response envelope v2 (status, summary, counts, findings_top, truncated, report_uri,
# next_actions, error_code); `result` stays in the envelope of the v1 tools so v1 consumers keep working.
TOOL_SCHEMA_VERSION = 2

# Machine error codes of the envelope (mcp-review REPORT.md 3.7 + the bridge's own codes).
ERROR_CODES = ("busy", "stale_preview", "scene_mismatch", "version_mismatch", "instance_ambiguous",
               "invariant_broken", "needs_human", "host_unavailable", "handles_required", "target_conflict",
               "unknown_handle", "selection_changed", "not_implemented", "runtime_missing", "unsupported_tool",
               "idempotency_conflict", "invalid_input", "unknown_tool", "maxscript_error", "error")
