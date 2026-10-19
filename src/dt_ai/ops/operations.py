"""Operations of the menu, each applied under the invariants of `dt_ai.ops.invariants` [D108, D115].

The agent never edits a delivery mesh freehand: it applies one operation to one part of a scene. `run_operation`
checks the scene before and after (`check_operation`); a broken invariant, or an operation that refuses, returns the
scene unchanged with a question for the user, never a half-built result. Each operation is a pure function
`(scene, part, ...) -> scene` on the numpy meshes of the invariants module, so it runs and is tested without Blender;
operations that need bmesh (booleans, extrusion, solidify) will call it through an adapter [D131]; the data stay the same.

Here: `keep` (copy + checks), `embed_into_neighbour` (sink by 10-20 mm, delete the faces it hides),
`primitive_box` (bounding box, silhouette within 0.07 m) and `to_opacity_plane` (NPM PCA mid-plane quad).
`plan_opacity_swaps` reports the largest triangle savings first, stopping at the budget [D109].
Patterns: `facade-decor-inset` (embed 0.02 m, inner face deleted), `primitive-first` (silhouette test 0.07 m).
"""
from dataclasses import dataclass
from typing import Callable
import warnings

import numpy as np

from dt_ai.ops.invariants import Context, InvariantReport, Mesh, Scene, check_operation, winding_number
from dt_ai.ops.silhouette import SILHOUETTE_MAX_M, silhouette_deviations

EMBED_DEPTH_RANGE_M = (0.010, 0.020)    # Q18a: embed depth 10-20 mm
_BOX_MIN_EXTENT_M = 1e-4                # thinner than this is a plane, not a box


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


def _box_mesh(lo: np.ndarray, hi: np.ndarray) -> Mesh:
    """Closed axis-aligned box with outward normals."""
    v = lo + np.array([(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)], dtype=float) * (hi - lo)
    quads = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))   # all counter-clockwise from outside
    tris = [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]
    return Mesh(v, np.array(tris))


def primitive_box(scene: Scene, part: str, silhouette_max_m: float = SILHOUETTE_MAX_M) -> Scene:
    """Replace `part` by its axis-aligned bounding box (12 triangles) when the silhouette holds [D082].

    Refuses when the part is empty or flat along an axis (a plane, not a box), or when the box differs from the part by
    more than `silhouette_max_m` in the top, front or side view: such a part needs a richer operation (rebuild by
    contour). The box is axis-aligned in the object system; a part turned off the axes will fail the test.
    """
    mesh = scene[part]
    if not len(mesh.triangles):
        raise OperationRefused("the part has no faces")
    lo, hi = mesh.vertices.min(axis=0), mesh.vertices.max(axis=0)
    flat = [axis for axis, size in zip("xyz", hi - lo) if size < _BOX_MIN_EXTENT_M]
    if flat:
        raise OperationRefused(f"the part is flat along {','.join(flat)}: it is a plane, not a box")
    box = _box_mesh(lo, hi)
    worst = max(silhouette_deviations(mesh, box, silhouette_max_m / 4).items(), key=lambda kv: kv[1])
    if worst[1] > silhouette_max_m:
        raise OperationRefused(f"a box would change the silhouette by {worst[1] * 1000:.0f} mm in the {worst[0]} view "
                               f"(limit {silhouette_max_m * 1000:.0f} mm): rebuild it by contour instead")
    return {**scene, part: box}


def to_opacity_plane(scene: Scene, part: str) -> Scene:
    """Replace an NPM repeating see-through part by one PCA mid-plane quad [D109].

    The caller, not this operation, registers `part` in Context.opacity_parts. No texture or UV is generated.
    A refusal leaves the input unchanged; the existing silhouette test applies in all three object-system views.
    """
    mesh = scene[part]
    if not len(mesh.vertices) or not len(mesh.triangles):
        raise OperationRefused("the part is empty; which source geometry should become an opacity plane?")
    if len(mesh.triangles) <= 2:
        raise OperationRefused("the part already has 2 triangles or fewer; should it stay as geometry?")
    center = mesh.vertices.mean(axis=0)
    relative = mesh.vertices - center
    _, axes = np.linalg.eigh(relative.T @ relative)
    local = relative @ axes                      # thinnest principal axis first
    lo, hi = local.min(axis=0), local.max(axis=0)
    depth = hi[0] - lo[0]
    if depth > 2 * SILHOUETTE_MAX_M + 1e-12:
        raise OperationRefused(f"the part is {depth:.3f} m thick (limit {2 * SILHOUETTE_MAX_M:.2f} m); "
                               "which richer geometry should replace it?")
    mid = (lo[0] + hi[0]) / 2
    corners = np.array([(mid, u, v) for u, v in ((lo[1], lo[2]), (hi[1], lo[2]),
                                                (hi[1], hi[2]), (lo[1], hi[2]))])
    plane = Mesh(corners @ axes.T + center, np.array([(0, 1, 2), (0, 2, 3)]))
    # Narrow projected railing gaps need finer sampling than primitive_box; use the same capped checker.
    worst = max(silhouette_deviations(mesh, plane, SILHOUETTE_MAX_M / 32).items(), key=lambda kv: kv[1])
    if worst[1] > SILHOUETTE_MAX_M:
        raise OperationRefused(f"an opacity plane would change the silhouette by {worst[1]:.3f} m in the "
                               f"{worst[0]} view (limit {SILHOUETTE_MAX_M:.2f} m); rebuild it by contour instead?")
    return {**scene, part: plane}


def plan_opacity_swaps(scene: Scene, candidates, triangle_budget: int) -> list[tuple[str, int]]:
    """Plan NPM swaps largest saving first; stop immediately when the total fits [D109].

    Candidates are already classified by the caller; execution still checks feasibility and invariants.
    Each pair reports the part and its saving (current triangles minus two). The input is not changed.
    Ties preserve candidate order; duplicates and nonpositive savings are ignored. An unreachable budget emits
    a UserWarning with the remaining total while returning every useful swap (the return type stays a list).
    """
    if triangle_budget < 0:
        raise ValueError("triangle_budget must be non-negative")
    total = sum(len(mesh.triangles) for mesh in scene.values())
    if total <= triangle_budget:
        return []
    savings = [(part, len(scene[part].triangles) - 2) for part in dict.fromkeys(candidates)]
    swaps = []
    for part, saved in sorted(savings, key=lambda item: -item[1]):
        if saved <= 0:
            continue
        swaps.append((part, saved))
        total -= saved
        if total <= triangle_budget:
            break
    if total > triangle_budget:
        warnings.warn(f"opacity budget unreachable: {total} triangles remain after all swaps (budget {triangle_budget})",
                      UserWarning, stacklevel=2)
    return swaps
