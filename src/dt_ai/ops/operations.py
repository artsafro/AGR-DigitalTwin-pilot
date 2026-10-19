"""Operations of the menu, each applied under the invariants of `dt_ai.ops.invariants` [D108, D115].

The agent never edits a delivery mesh freehand: it applies one operation to one part of a scene. `run_operation`
checks the scene before and after (`check_operation`); a broken invariant, or an operation that refuses, returns the
scene unchanged with a question for the user, never a half-built result. Each operation is a pure function
`(scene, part, ...) -> scene` on the numpy meshes of the invariants module, so it runs and is tested without Blender;
operations that need bmesh (booleans, extrusion) will call it through an adapter, the data stay the same.

Here: `keep` (copy + checks) and `embed_into_neighbour` (sink by 10-20 mm, delete the faces it hides) [Q8, Q18a].
Pattern: `facade-decor-inset` (docs/domain/patterns/facade-decor-inset.md): embed 0.02 m, inner face deleted.
"""
from dataclasses import dataclass
from typing import Callable

import numpy as np

from dt_ai.ops.invariants import Context, InvariantReport, Mesh, Scene, check_operation, winding_number

EMBED_DEPTH_RANGE_M = (0.010, 0.020)    # Q18a: embed depth 10-20 mm


class OperationRefused(Exception):
    """The operation cannot be applied to this input; the message is the question for the user."""


@dataclass(frozen=True)
class OperationResult:
    operation: str
    part: str
    params: dict
    applied: bool
    scene: Scene                      # the new scene when applied, else the one that came in (same object)
    report: InvariantReport | None    # None when the operation refused before any geometry changed
    question: str | None = None       # why it was rolled back, for the user
    notes: dict | None = None


def run_operation(scene: Scene, operation: str, part: str, apply: Callable[[Scene], Scene], ctx: Context = Context(),
                  params: dict | None = None) -> OperationResult:
    """Apply `apply(scene)` to `part`, check the invariants before and after, roll back on any break."""
    params = params or {}
    if part not in scene:
        raise ValueError(f"unknown part {part!r}")
    try:
        after = apply(scene)
    except OperationRefused as why:
        return OperationResult(operation, part, params, False, scene, None, f"{operation} on {part}: {why}")
    report = check_operation(scene, after, [part], ctx)
    if report.passed:
        return OperationResult(operation, part, params, True, after, report,
                               notes={"faces_before": len(scene[part].triangles), "faces_after": len(after[part].triangles)})
    broken = "; ".join(f"{r.name} ({r.count}): {r.offenders[0] if r.offenders else ''}" for r in report.broken)
    return OperationResult(operation, part, params, False, scene, report,
                           f"{operation} on {part} broke the invariants and was rolled back: {broken}")


def keep(scene: Scene, part: str) -> Scene:
    """Keep the part as it is: the copy is the same mesh; the invariants decide whether it may stay."""
    return dict(scene)


def embed_into_neighbour(scene: Scene, part: str, neighbour: str, direction, depth_m: float) -> Scene:
    """Sink `part` by `depth_m` along `direction` into `neighbour` and delete every face of it that is now hidden.

    A face is hidden when all its corners lie inside the neighbour (a closed mesh). Refuses when the depth is outside
    10-20 mm, the neighbour is missing, or nothing is hidden afterwards (the parts do not touch, or the direction points
    out of the neighbour): embedding that deletes nothing is not an embed.
    """
    lo, hi = EMBED_DEPTH_RANGE_M
    if not lo - 1e-9 <= depth_m <= hi + 1e-9:
        raise OperationRefused(f"embed depth {depth_m * 1000:.1f} mm is outside {lo * 1000:.0f}-{hi * 1000:.0f} mm")
    if neighbour not in scene or neighbour == part:
        raise OperationRefused(f"neighbour {neighbour!r} is not another part of the scene")
    d = np.asarray(direction, dtype=float)
    if d.shape != (3,) or np.linalg.norm(d) < 1e-12:
        raise OperationRefused("embed direction must be a non-zero 3-vector")
    mesh = scene[part]
    moved = mesh.vertices + d / np.linalg.norm(d) * depth_m
    inside = np.abs(winding_number(moved, scene[neighbour])) > 0.5
    hidden = inside[mesh.triangles].all(axis=1)
    if not hidden.any():
        raise OperationRefused(f"after sinking {depth_m * 1000:.0f} mm no face of {part} lies inside {neighbour}: "
                               "they do not touch, or the direction points out of the neighbour")
    kept = mesh.triangles[~hidden]
    used, inverse = np.unique(kept, return_inverse=True)
    return {**scene, part: Mesh(moved[used], inverse.reshape(-1, 3))}
