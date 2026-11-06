"""new-case: import hook of branch U (#1024): D108 operations of agr-mcp. Stub of branch 0; owned by branch U.

`tools.catalog()` calls `register(catalog)` once per build and appends the returned specs, so branch U adds the D108
gate operations (dt_ai.ops.run_operation: undo, invariants before/after, hashes outside the layer, rollback,
question) without editing tools.py. Contract:

    register(catalog: dict[str, agr_mcp.spec.Spec]) -> list[agr_mcp.spec.Spec]

`catalog` is the catalogue built so far (read it, do not mutate it). A returned name that is already in the
catalogue is an error of the build. Return [] to add nothing. Branch 0 ships the empty stub.
"""
from __future__ import annotations


def register(catalog):  # noqa: ARG001 - branch U fills this
    return []
