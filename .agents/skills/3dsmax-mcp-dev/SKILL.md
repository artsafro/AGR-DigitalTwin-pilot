---
name: 3dsmax-mcp-dev
description: 'Inspect the configured 3ds Max MCP route and safely authorize versioned scene operations. Use when: «что открыто в 3ds Max?», «проверь MCP 3ds Max», «сохрани сцену новой версией».'
---

# 3ds Max MCP for project agents

## Identify before calling

1. Read `docs/agents/CAPABILITIES.md`, 3ds Max entry. The route is `3dsmax-mcp`
   v1.7.5 with safe_mode enabled; one scoped live cycle on a synthetic scene is
   validated, production scenes are not.
2. Confirm the intended application/version, active document, units, saved/dirty
   state and scene/port/export ownership. Start read-only. Inspect the actual
   advertised tool schemas; do not invent tool names or substitute another route.
   Pin the exact Max process (PID) before any scene call: a newly started Max
   registers itself and becomes the default target, so never rely on the default.
   Pinning (`select_max_instance`) rebinds the session and is in the destructive
   class: name the PID and get it authorized like any other mutation.
3. If the route cannot inspect without mutation, stop with the exact missing
   capability. Do not test a connection by changing the user's production scene.

## Risk gate before mutation

Before any write, name the exact tool/operation and its risk class from
[`CAPABILITIES.md#dcc-tool-risk-classes`](../../../docs/agents/CAPABILITIES.md#dcc-tool-risk-classes).
Only the read-only subset listed there is registered, and it is restricted by
arguments (e.g. `query_scene` only with `overview`/`selection`); every other tool or
operation defaults to `destructive`; inspect the schema and script before use. Arbitrary MaxScript/Python
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

## Known pitfalls (live cycle 2026-11-03)

- `create_object` with `pos` fails («Invalid position parameter») and creates
  nothing: create without `pos`, then `transform`, then read the position back.
- `manage_scene(save)` saves only to the current path: Save As to a new versioned
  path through MAXScript, then reopen that file and compare object count and geometry.
- Undo counts only after a readback shows the previous state, never on a `true` reply.
- The agent viewport does not redraw while the Max window is hidden: show the
  pinned process window before capturing.
- Max 2026 starts with a `polyunwrapper_autoload.mse` .NET error dialog: acknowledge
  it once, do not edit the plugin or startup scripts.

## Live-instance pitfalls (user's open Max)

Sources: retro `docs/retros/2026-11-05-sessions-retro-04-05.md` (problem 3); sessions
«VPM текстура кондиционеров 4К», «Ворота Object 001 переделка размеров», «Kasatkino
ground mesh preparation». Never put the user's scene at risk to finish faster.

- No `resetMaxFile` / `loadMaxFile` over MCP on the user's instance: it crashed Max;
  `max undo` over MCP did not revert a scripted edit. Ask the user to reopen the file
  (2026-11-05, «VPM текстура кондиционеров 4К», K3 «макс упал»).
- No `freeSceneBitmaps()`: it unloads every scene bitmap (25), the whole building went
  black. Reload only the agent's own maps, by their nodes/paths (2026-11-05, «VPM
  текстура кондиционеров 4К», K5).
- No long per-vertex/per-face loops on large meshes (4.3 M faces) on the main thread:
  a `polyop.getFacesUsingVert` loop hung Max until it died. Use bulk APIs
  (`polyop.getVerts`, one element query), estimate cost first, or run a separate
  batch process (2026-11-05, «VPM текстура кондиционеров 4К», K1).
- Never put work only into the user's unsaved live scene: versions imported as layers
  were lost when Max closed. Write each result to a new versioned file (2026-11-05,
  «Kasatkino ground mesh preparation», incident 11).
- `saveMaxFile <copy> useNewFile:false` clears the dirty flag (`getSaveRequired`) of the
  open scene: the user's scene on disk may be older than it looks. Record the dirty
  state before the save and tell the user (2026-11-05, «Ворота Object 001 переделка
  размеров», 3.12).
- `meshop.attach` reset material IDs of the attached and the receiving mesh (whole
  Ground set to ID 1). Read IDs back after every attach and restore them (2026-11-05,
  «Ворота Object 001 переделка размеров», 3.11).
- `polyop.attach` merges the two multi-subs and condenses IDs: set IDs after attach;
  attached faces are the tail of the face list (2026-11-07, K5 NPM).
- `polyop.detachFaces ... delete:true` renumbers faces: never reuse a face bitarray
  computed before it; re-query (e.g. by mat ID) (2026-11-05, «VPM текстура
  кондиционеров 4К», K3).
- Max launched by the agent with `Start-Process` closed within a minute. Give the
  user the full absolute path to open instead (2026-11-05, «Ворота Object 001
  переделка размеров», 3.7).

Mesh edits through MAXScript (Max 2024; mirrored from the user memory
`max-mesh-edit-pitfalls.md` so every agent sees them):

- `format "%" p.x` prints ~6 significant digits (~5 cm lost at 16 km): export with
  `formattedPrint v format:".7f"` and work in object space (2026-11-05, «Ворота Object
  001 переделка размеров»).
- With modifiers on the stack `o.mesh` is a temp copy of the evaluated result and edits
  do nothing: check `o.modifiers.count` before every edit (2026-11-05, «Ворота Object
  001 переделка размеров»).
- Topology edits of `o.baseobject.mesh` under a modifier stack: Max closed during such
  an edit, crash cause unverified (the user said he closed it himself). Edit a
  modifier-free copy or ask before collapsing (2026-11-05, «Ворота Object 001 переделка
  размеров»).
- New faces need explicit `setEdgeVis` (quad diagonals hidden, outer edges visible),
  or Convert to Editable Poly drops the part (2026-11-05, «Ворота Object 001 переделка
  размеров»).
- `mesh vertices:... faces:...` creates `Object00N`; delete temp nodes by handle,
  never `delete $Mesh*` (2026-11-05, «Ворота Object 001 переделка размеров»).
- `on`/`off` are reserved (`off = ...` fails); put multi-statement scripts in a `.ms`
  file run by `fileIn` with a dry-run flag first (2026-11-07, K5 railing posts).
