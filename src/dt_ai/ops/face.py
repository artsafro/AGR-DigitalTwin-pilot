"""Operation `from_face`: the exterior face of a thin part, its open border hidden in the neighbouring wall [D108, D082].

A thin panel (cassette, skin, soffit) on a closed wall needs only its exterior face. A single open face fails the
invariants on its own (`open_borders_hidden`, `no_visible_back_faces`), which is why the assembly used to close each
panel into a 12-triangle box. Here the face is built in the context of the wall: the exterior cap of the part's
contour in one object view (`top` / `front` / `side`, the normal axis of the panel) plus a skirt from the cap border
straight back into the wall, so deep that every open border sample lies inside the wall at least `embed_m` (10 mm,
the invariants' `embed_min_m`). There is no inner cap: the wall closes the back. A rectangle costs 2 + 8 triangles,
and a whole cluster of coplanar panels (one part, joints closed by `close_gaps_m`) costs the same plus 2 per extra
contour vertex.

The operation refuses (a question, the scene unchanged) when the view is unknown, the part or the wall is empty or
not finite, the wall is not a closed oriented 2-manifold, the part is the wall, the wall is on both sides or on
neither side of the part along the normal, the border does not reach `embed_m` inside the wall within `max_reach_m`,
the contour splits (unless `allow_multi`) or the result changes the silhouette by more than 0.07 m. The result
replaces the part only through `run_operation`, so all invariants are checked after it and a break rolls back.
Pattern: facade-decor-inset | new-case: exterior face with a skirt embedded into the neighbouring wall (#353, user
decision 2026-10-22 variant B, from_face in context).
"""
from dataclasses import replace
import math

import numpy as np
import shapely

from dt_ai.ops.contour import _contour, extrude_polygon, topology_problem
from dt_ai.ops.invariants import EMBED_MIN_M, Context, Mesh, Scene, distance_to_surface, winding_number
from dt_ai.ops.operations import OperationRefused, OperationResult, run_operation
from dt_ai.ops.silhouette import SILHOUETTE_MAX_M, VIEWS, silhouette_deviations

OPERATION = "from_face"                  # the Operation literal of dt_ai.parts.model
MAX_REACH_M = 0.30                       # deepest skirt, outer face to bottom
_STEP_M = 0.001                          # depth search step
_MARGIN_M = 0.001                        # extra depth past the first deep sample


def _join(meshes) -> Mesh:
    offsets = np.cumsum([0] + [len(m.vertices) for m in meshes[:-1]])
    return Mesh(np.concatenate([m.vertices for m in meshes]),
                np.concatenate([m.triangles + o for m, o in zip(meshes, offsets)]))


def _inside_deep(points: np.ndarray, walls: list, embed_m: float) -> np.ndarray:
    """Each point at least `embed_m` deep inside ONE wall, the rule of the `open_borders_hidden` invariant."""
    ok = np.zeros(len(points), bool)
    for w in walls:
        todo = np.flatnonzero(~ok)
        if not len(todo):
            break
        inside = np.abs(winding_number(points[todo], w)) > 0.5
        deep = distance_to_surface(points[todo[inside]], w) >= embed_m - 1e-9
        ok[todo[inside][deep]] = True
    return ok


def _face(scene: Scene, part: str, walls: tuple, view: str, embed_m: float, max_reach_m: float, close_gaps_m: float,
          allow_multi: bool, silhouette_max_m: float, notes: dict, embed_min_m: float = EMBED_MIN_M) -> Scene:
    if view not in VIEWS:
        raise OperationRefused(f"unknown view {view!r}; which of {', '.join(VIEWS)} is the panel normal?")
    for name, value, lo in (("embed_m", embed_m, max(EMBED_MIN_M, embed_min_m)), ("max_reach_m", max_reach_m, 0.0),
                            ("close_gaps_m", close_gaps_m, 0.0)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < lo:
            raise OperationRefused(f"{name} {value!r} must be a finite number >= {lo}; which value?")
    if close_gaps_m > silhouette_max_m / 2:
        raise OperationRefused(f"close_gaps_m {close_gaps_m} closes joints wider than the silhouette limit allows "
                               f"({silhouette_max_m / 2} m); which joints should stay?")
    if not walls:
        raise OperationRefused("no wall given; which closed neighbour should hide the open border?")
    for w in walls:
        if w not in scene or w == part:
            raise OperationRefused(f"wall {w!r} is not another part of the scene; which wall?")
    mesh = scene[part]
    if not len(mesh.triangles):
        raise OperationRefused("the part has no faces; which source geometry should become a face?")
    for w in walls:
        if not len(scene[w].triangles):
            raise OperationRefused(f"the wall {w!r} has no faces; which closed wall?")
    if not all(np.isfinite(scene[n].vertices).all() for n in (part, *walls)):
        raise OperationRefused("a vertex is not finite; which source geometry?")
    for w in walls:
        problem = topology_problem(scene[w])
        if problem:
            raise OperationRefused(f"the wall {w!r} is not a closed oriented 2-manifold ({problem}): it cannot hide a "
                                   "border; which closed wall?")
    wall_list = [scene[w] for w in walls]
    wall = _join(wall_list)
    axis = VIEWS[view]
    pieces = _contour(mesh, axis, None)
    if close_gaps_m > 0:
        merged = shapely.union_all(pieces).buffer(close_gaps_m, join_style="mitre").buffer(-close_gaps_m,
                                                                                          join_style="mitre")
        pieces = _contour(mesh, axis, merged)
    if not pieces:
        raise OperationRefused(f"the part has no area in the {view} view; which view is the panel normal?")
    if len(pieces) > 1 and not allow_multi:
        raise OperationRefused(f"the {view} contour splits into {len(pieces)} pieces; close the joints "
                               "(close_gaps_m) or pass allow_multi=True?")
    span = mesh.vertices[mesh.triangles.ravel(), axis]
    lo_w, hi_w = float(span.min()), float(span.max())
    # Which side is the wall on? Probe straight behind the contour's interior point on both sides.
    probe = np.array([p.representative_point().coords[0] for p in pieces])
    keep = [i for i in range(3) if i != axis]

    def at(uv, w):
        pts = np.zeros((len(uv), 3))
        pts[:, keep[0]], pts[:, keep[1]], pts[:, axis] = uv[:, 0], uv[:, 1], w
        return pts

    reach = [(sign, np.any([_inside_deep(at(probe, w0 + sign * t), wall_list, embed_m).all()
                            for t in np.arange(_STEP_M, max_reach_m + 1e-12, _STEP_M)]))
             for sign, w0 in ((-1.0, hi_w), (1.0, lo_w))]
    sides = [sign for sign, hit in reach if hit]
    if len(sides) != 1:
        where = "on neither side" if not sides else "on both sides"
        raise OperationRefused(f"the wall {walls} is {where} of the part within {max_reach_m} m along the {view} "
                               "normal; which wall is behind the panel?")
    inward = sides[0]
    w_out = hi_w if inward < 0 else lo_w
    # The skirt bottom: every border sample (ring vertices and edge midpoints) must lie deep inside the wall.
    border = []
    for p in pieces:
        for ring in (p.exterior, *p.interiors):
            c = np.asarray(ring.coords)
            border += [c[:-1], (c[:-1] + c[1:]) / 2]
    border = np.concatenate(border)
    depth = None
    for t in np.arange(_STEP_M, max_reach_m + 1e-12, _STEP_M):
        if _inside_deep(at(border, w_out + inward * t), wall_list, embed_m).all():
            depth = float(t) + _MARGIN_M
            break
    if depth is None or depth > max_reach_m + 1e-12 or \
            not _inside_deep(at(border, w_out + inward * depth), wall_list, embed_m).all():
        raise OperationRefused(f"the border does not reach {embed_m * 1000:.0f} mm inside the wall {walls} within "
                               f"{max_reach_m} m; which wall, or a closed operation instead?")
    meshes = []
    for p in pieces:
        try:
            prism = extrude_polygon(p, axis, min(w_out, w_out + inward * depth), depth)
        except ValueError as why:
            raise OperationRefused(f"the {view} contour cannot be built ({why}); which contour?") from None
        n = len(prism.vertices) // 2
        caps = (len(prism.triangles) - 2 * n) // 2
        drop = slice(caps, 2 * caps) if inward > 0 else slice(0, caps)      # the cap inside the wall
        tris = np.delete(prism.triangles, np.arange(len(prism.triangles))[drop], axis=0)
        meshes.append(Mesh(prism.vertices, tris))
    face = _join(meshes)
    # The skirt runs inside the wall, so the visible silhouette is the part's together with its wall.
    deviations = silhouette_deviations(_join([mesh, wall]), _join([face, wall]), silhouette_max_m / 4)
    notes.update(view=view, walls=list(walls), w_out=w_out, inward=inward, depth_m=depth, pieces=len(pieces),
                 thickness_m=hi_w - lo_w, deviations_m=deviations)
    worst = max(deviations.items(), key=lambda kv: kv[1])
    if worst[1] > silhouette_max_m + 1e-9:
        raise OperationRefused(f"the face would change the silhouette by {worst[1] * 1000:.0f} mm in the {worst[0]} "
                               f"view (limit {silhouette_max_m * 1000:.0f} mm); which view or operation instead?")
    return {**scene, part: face}


def face_on_wall(scene: Scene, part: str, walls, view: str, embed_m: float = EMBED_MIN_M,
                 max_reach_m: float = MAX_REACH_M, close_gaps_m: float = 0.0, allow_multi: bool = False,
                 ctx: Context = Context(), silhouette_max_m: float = SILHOUETTE_MAX_M) -> OperationResult:
    """Replace `part` by its exterior `view` face + a skirt into `walls`, through `run_operation("from_face")`.

    `walls`: one part name or several (closed meshes of the same scene). `embed_m` below `ctx.embed_min_m` (or 10 mm) is refused, never raised silently.
    The notes carry faces before / after, the outward side, skirt depth, pieces and per-view deviations.
    """
    walls = (walls,) if isinstance(walls, str) else tuple(walls)
    notes: dict = {}
    params = {"view": view, "walls": list(walls), "embed_m": embed_m, "max_reach_m": max_reach_m,
              "close_gaps_m": close_gaps_m, "allow_multi": allow_multi}
    if part not in scene:
        raise ValueError(f"unknown part {part!r}")
    result = run_operation(scene, OPERATION, part,
                           lambda s: _face(s, part, walls, view, embed_m, max_reach_m, close_gaps_m, allow_multi,
                                           silhouette_max_m, notes, ctx.embed_min_m), ctx, params)
    return replace(result, notes={**(result.notes or {}), **notes})
