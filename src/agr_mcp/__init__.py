"""new-case: agr-mcp phase 0, read-only stdio MCP server over the AGR checkers (docs/plans/agr-mcp.md).

Kept import-light on purpose: `max_bridge` is imported inside 3ds Max's Python, which has no `mcp` package.
"""

SERVER_NAME = "agr-mcp"
SERVER_VERSION = "0.0.1"
# Bump on any breaking change of a tool input or output field (plan section 4).
TOOL_SCHEMA_VERSION = 1
