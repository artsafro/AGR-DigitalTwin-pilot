---
name: 3dsmax-mcp-dev
description: 'Inspect the configured 3ds Max MCP route and safely authorize versioned scene operations. Use when: «что открыто в 3ds Max?», «проверь MCP 3ds Max», «сохрани сцену новой версией».'
---

# 3ds Max MCP for project agents

## Identify before calling

1. Read `docs/agents/CAPABILITIES.md`, 3ds Max entry. The configured route is
   `3dsmax-mcp` v1.7.5 with safe_mode enabled; this is not live-scene validation.
2. Confirm the intended application/version, active document, units, saved/dirty
   state and scene/port/export ownership. Start read-only. Inspect the actual
   advertised tool schemas; do not invent tool names or substitute another route.
3. If the route cannot inspect without mutation, stop with the exact missing
   capability. Do not test a connection by changing the user's production scene.

## Risk gate before mutation

Before any write, name the exact tool/operation and its risk class from
[`CAPABILITIES.md#dcc-tool-risk-classes`](../../../docs/agents/CAPABILITIES.md#dcc-tool-risk-classes).
No live inspection subset is validated for this route, so its tools default to
`destructive`; inspect the schema and script before use. Arbitrary MaxScript/Python
is destructive even if the script plans to save a new output. Require explicit
user authorization for the exact mutation; safe_mode is not an authorization ledger.
For a registered `versioned-write`, require task authorization and a new versioned
destination, including sidecars. Apply the
[Permission matrix and DCC gate](../../../docs/agents/WORKFLOW.md#gate-dcc-authorization).
Never overwrite/delete sources or accepted versions. Use a managed export copy for
export preparation, not the working source (`docs/domain/export-import.md`).

## Verify and recover

Save/export only to a new versioned path. Read the actual output back and check
geometry/topology, UVs, materials, units and transforms; exit 0 alone is not success.
After timeout the outcome is unknown: inspect the active document and existing
outputs before retrying, preserve partial evidence, and stop after two failures
with the same cause. Do not discard user work or close an unrelated scene as cleanup.
Report exact calls, results, evidence paths and unverified gates separately.
