# Draft: reconcile unknown DCC outcomes, never blindly retry writes (#1292)

Status: **research draft**, not an adopted permission or global policy change.
Sources: [measurement/prototype](dcc-code-mode-1292.md), #1273 W2 and verification-gap
retros; existing `.agents/skills/3dsmax-mcp-dev/SKILL.md` Verify/recover section;
`docs/domain/validation.md` mandatory readback/manual-gate distinction. No code from
Revit-Bridge is incorporated.

## State machine (all DCCs)

```text
authorize exact operation + identify application/document/units/version + acquire ownership
  -> capture baseline ids/counts/state + reserve request id
  -> execute guarded operation once
      explicit pre-dispatch refusal -> no commit assumed only with evidence of no dispatch
      successful commit receipt -> committed_unverified -> independent readback
      timeout/disconnect/cancellation/malformed receipt/post-dispatch error -> unknown
          -> stop writes and dependent steps
          -> reconcile against actual scene/model and any published files
              no effect proved -> reauthorize a new operation; do not replay automatically
              complete effect proved -> verify independently; don't duplicate the write
              partial/ambiguous effect -> preserve evidence; ask for recovery decision
```

A client timeout does not roll back a host transaction. An exception can be raised
after a successful commit. A new request ID, reconnect, process restart, positive
transport status, DONE marker, Undo reply or existing output path is not proof of
absence/success. Never repeat a write merely to obtain a cleaner receipt.

## Reconciliation evidence by DCC

| DCC | Identity and baseline | Read-only reconciliation | Independent post-commit verification |
|---|---|---|---|
| 3ds Max | pinned PID, runtime version, exact scene path/dirty state, units, node handles+names, selection, relevant geometry/material/UV counts | resolve the original handles; inventory added/deleted nodes and expected transforms/IDs; inspect output bytes/partial receipts and audit under the same scene identity | separate read/query; for a versioned save/export reopen the actual output on an authorized copy and check geometry, UV, materials, units, transforms |
| Blender | owned PID/session lock, version, blend path/units, explicit object/datablock names plus task-bound identity/custom ID where available; topology/material/UV baseline | inspect target datablocks and counts, transforms/map assignments, saved output bytes; names alone can be reused, so compare state as well | separate invocation/readback from the final saved blend/FBX; don't reuse the write script's asserted success |
| Revit | version, exact document identity/path, units, ElementId **and UniqueId** for targets, transaction/request identity and relevant counts/parameters | inspect the same document, resolve UniqueIds and current ElementIds, compare created/deleted elements/parameters; distinguish dry-run rollback from committed state | independent read-only query; when persistence is claimed, reopen an authorized upgraded copy and verify it, never save over the source |

Reconciliation reads need their own receipts: request ID, operation/argument hash,
application/document identity, before/after IDs and counts, observed state, missing
or partial outputs and unresolved checks. No generic retry loop or output-exists
shortcut. A stale receipt for another document/state is an error, not a cache hit.

Do not hold a live document hostage while retrying communication. Respect existing
Max/Blender locks and Revit dry-run-only restrictions; inability to read the host is
an external blocker, not permission to reset/close/reopen the user's scene.

## Boundaries

- Batch frontend calls are not necessarily one host transaction. Preserve a receipt
  for every executed or skipped operation; never silently drop the remainder.
- Apply only through existing guarded handlers. Catalog discovery and read-only
  defaults cannot authorize edits, destructive scripts or arbitrary execution.
- After any commit, verification must be a separate observation of actual state,
  not the writer's own counters. Technical QA, manual acceptance and publication
  remain separate; any missing mandatory check means no delivery-pass.
- Durable request journals and restart reconciliation are production requirements,
  not implemented by the process-local offline prototype. Do not deploy that
  prototype as an exactly-once system.
