"""Operation `from_face`: the exterior face of a thin part, its open border hidden in the neighbouring wall [D108, D082].

A thin panel (cassette, skin, soffit) on a closed wall needs only its exterior face. A single open face fails the
invariants on its own (`open_borders_hidden`, `no_visible_back_faces`), which is why the assembly used to close each
panel into a 12-triangle box. Here the face is built in the context of the wall: the exterior cap of the part's
contour in one object view (`top` / `front` / `side`, the normal axis of the panel) plus a skirt from the cap border
straight back into the wall, so deep that every open border sample lies inside the wall at least `embed_m` (10 mm,
the invariants' `embed_min_m`). There is no inner cap: the wall closes the back. A rectangle costs 2 + 8 triangles,
and a whole cluster of coplanar panels (one part, joints closed by `close_gaps_m`) costs the same plus 2 per extra
contour vertex. If the cap border is already embedded in receiving solids, retain only the cap (2 triangles for a
rectangle). Border eligibility uses ring vertices and edge midpoints, matching the current kernel invariant;
this finite sampling is not a continuous whole-edge certificate.

`band_between_walls` retains the sides of a source section between contacted receivers, embedding each hidden
end by at most 20 mm (and retaining one original exposed cap only by explicit request). It can recover an
open-ended prismatic source's actual projected section loop; it never invents a missing loop or bridges an air gap.
This is a candidate-producing capability, not a whole-building topology, D129 or delivery acceptance receipt.

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
          allow_multi: bool, silhouette_max_m: float, notes: dict, embed_min_m: float = EMBED_MIN_M,
          outward_sign: int | None = None, border_growth_m: float = 0.0) -> Scene:
    if view not in VIEWS:
        raise OperationRefused(f"unknown view {view!r}; which of {', '.join(VIEWS)} is the panel normal?")
    for name, value, lo in (("embed_m", embed_m, max(EMBED_MIN_M, embed_min_m)), ("max_reach_m", max_reach_m, 0.0),
                            ("close_gaps_m", close_gaps_m, 0.0)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < lo:
            raise OperationRefused(f"{name} {value!r} must be a finite number >= {lo}; which value?")
    if close_gaps_m > silhouette_max_m / 2:
        raise OperationRefused(f"close_gaps_m {close_gaps_m} closes joints wider than the silhouette limit allows "
                               f"({silhouette_max_m / 2} m); which joints should stay?")
    if outward_sign is not None and (type(outward_sign) is not int or outward_sign not in (-1, 1)):
        raise OperationRefused("outward_sign must be an explicit -1 or +1, or None")
    if (isinstance(border_growth_m, bool) or not isinstance(border_growth_m, (int, float))
            or not math.isfinite(border_growth_m) or not 0 <= border_growth_m <= .020):
        raise OperationRefused("border_growth_m must be finite and between 0 and 20 mm")
    if border_growth_m and outward_sign is None:
        raise OperationRefused("border growth requires an explicit source-bound outward_sign")
    if not walls:
        raise OperationRefused("no wall given; which closed neighbour should hide the open border?")
    if len(set(walls)) != len(walls):
        raise OperationRefused("receiving walls must be unique")
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
    if border_growth_m:
        original_topology = sorted(len(p.interiors) for p in pieces)
        grown = shapely.union_all(pieces).buffer(border_growth_m, join_style="mitre")
        grown_pieces = _contour(mesh, axis, grown)
        if sorted(len(p.interiors) for p in grown_pieces) != original_topology:
            raise OperationRefused("border growth changes source pieces or holes; which source contour is intended?")
        pieces = grown_pieces
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

    # A real opening frame need not contain the panel's centre. An explicit
    # source-bound orientation can choose the cap, but cannot waive the border,
    # silhouette or four scene invariants below. No opacity exception is added.
    if outward_sign is None:
        reach = [(sign, any(_inside_deep(at(probe, w0 + sign * t), wall_list, embed_m).all()
                            for t in np.arange(_STEP_M, max_reach_m + 1e-12, _STEP_M)))
                 for sign, w0 in ((-1.0, hi_w), (1.0, lo_w))]
        sides = [sign for sign, hit in reach if hit]
    else:
        sides = [-float(outward_sign)]
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
    # A seated face can already have its entire sampled border embedded in receiving frames.
    # Do not add a hidden skirt in that case; the same operation invariants still gate the cap.
    depth = 0.0 if _inside_deep(at(border, w_out), wall_list, embed_m).all() else None
    if depth is None:
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
            prism_depth = depth if depth else _STEP_M
            prism = extrude_polygon(p, axis, min(w_out, w_out + inward * prism_depth), prism_depth)
        except ValueError as why:
            raise OperationRefused(f"the {view} contour cannot be built ({why}); which contour?") from None
        n = len(prism.vertices) // 2
        caps = (len(prism.triangles) - 2 * n) // 2
        if depth == 0.0:
            # Use only the outward cap of a temporary prism, without unused back vertices.
            tris = prism.triangles[:caps] if inward > 0 else prism.triangles[caps:2 * caps]
            used, inverse = np.unique(tris, return_inverse=True)
            meshes.append(Mesh(prism.vertices[used], inverse.reshape(-1, 3)))
        else:
            drop = slice(caps, 2 * caps) if inward > 0 else slice(0, caps)  # the cap inside the wall
            tris = np.delete(prism.triangles, np.arange(len(prism.triangles))[drop], axis=0)
            meshes.append(Mesh(prism.vertices, tris))
    face = _join(meshes)
    # The skirt runs inside the wall, so the visible silhouette is the part's together with its wall.
    deviations = silhouette_deviations(_join([mesh, wall]), _join([face, wall]), silhouette_max_m / 4)
    notes.update(view=view, walls=list(walls), w_out=w_out, inward=inward, depth_m=depth, pieces=len(pieces),
                 thickness_m=hi_w - lo_w, deviations_m=deviations,
                 outward_sign=outward_sign, border_growth_m=border_growth_m)
    worst = max(deviations.items(), key=lambda kv: kv[1])
    if worst[1] > silhouette_max_m + 1e-9:
        raise OperationRefused(f"the face would change the silhouette by {worst[1] * 1000:.0f} mm in the {worst[0]} "
                               f"view (limit {silhouette_max_m * 1000:.0f} mm); which view or operation instead?")
    return {**scene, part: face}


def band_between_walls(scene: Scene, part: str, walls, view: str, ctx: Context = Context(),
                       max_embed_m: float = 0.020, allow_exposed_end: bool = False) -> OperationResult:
    """Retain a source contour's side faces, hiding contacted end rings in unchanged receivers.

    For example, a roof-support skin touching a slab at both ends costs eight triangles, not twelve.
    Extend or trim only a contacted end into its receiver, by at most 20 mm; never bridge an air gap.
    By explicit request one exposed end retains its original cap; at least one end must embed.
    The standard geometric operation invariants gate the entire local scene. D129 remains a separate check.
    """
    walls = (walls,) if isinstance(walls, str) else tuple(walls)
    notes: dict = {}

    def apply(s):
        if view not in VIEWS:
            raise OperationRefused(f"unknown view {view!r}")
        if (isinstance(ctx.embed_min_m, bool) or not isinstance(ctx.embed_min_m, (int, float)) or
                not math.isfinite(ctx.embed_min_m) or ctx.embed_min_m < EMBED_MIN_M):
            raise OperationRefused("context embed_min_m must be finite and at least 10 mm")
        if not isinstance(allow_exposed_end, bool):
            raise OperationRefused("allow_exposed_end must be a boolean")
        if (isinstance(max_embed_m, bool) or not isinstance(max_embed_m, (int, float)) or
                not math.isfinite(max_embed_m) or not ctx.embed_min_m + _MARGIN_M <= max_embed_m <= 0.020):
            raise OperationRefused("max_embed_m must be finite, at least embed_min_m + 1 mm and at most 20 mm")
        if not walls or len(set(walls)) != len(walls):
            raise OperationRefused("receiving walls must be nonempty and unique")
        for w in walls:
            if w not in s or w == part:
                raise OperationRefused(f"wall {w!r} is not another part of the scene")
            if not len(s[w].triangles) or not np.isfinite(s[w].vertices).all():
                raise OperationRefused(f"wall {w!r} has no finite faces")
            problem = topology_problem(s[w])
            if problem:
                raise OperationRefused(f"wall {w!r} is not closed and oriented ({problem})")
        mesh = s[part]
        if not len(mesh.triangles) or not np.isfinite(mesh.vertices).all():
            raise OperationRefused("the part has no finite faces")
        axis = VIEWS[view]
        pieces = _contour(mesh, axis, None)
        section_recovered = False
        if sum(p.area for p in pieces) < 1e-8:
            # Open-ended prismatic source skins have only zero-area side projections.
            # Recover actual closed section loops, using the same 0.1 mm coordinate grid as the kernel weld.
            uv_axes = [i for i in range(3) if i != axis]
            uv = np.round(mesh.vertices[:, uv_axes] / 1e-4) * 1e-4
            edges = np.vstack([mesh.triangles[:, [0, 1]], mesh.triangles[:, [1, 2]], mesh.triangles[:, [2, 0]]])
            lines = [shapely.LineString(uv[e]) for e in edges if np.linalg.norm(uv[e[1]] - uv[e[0]]) > 0]
            loops = shapely.polygonize(shapely.get_parts(shapely.union_all(lines)))
            pieces = _contour(mesh, axis, loops)
            section_recovered = True
        if len(pieces) != 1 or pieces[0].interiors:
            raise OperationRefused("the source band must have one unperforated contour")
        poly = pieces[0]
        ring = np.asarray(poly.exterior.coords)[:-1]
        samples = np.vstack([ring, (ring + np.roll(ring, -1, axis=0)) / 2])
        keep = [i for i in range(3) if i != axis]
        span = mesh.vertices[mesh.triangles.ravel(), axis]
        lo, hi = float(span.min()), float(span.max())
        if hi - lo <= _STEP_M:
            raise OperationRefused("the band has no axial extent")
        neighbours = [s[w] for w in walls]
        ends, exposed = [], []
        for end, sign in ((lo, -1), (hi, 1)):
            pts = np.zeros((len(samples), 3))
            pts[:, keep] = samples
            pts[:, axis] = end
            # A depth change is allowed only from actual surface contact or existing embed.
            contact = np.zeros(len(pts), bool)
            for wall in neighbours:
                contact |= ((distance_to_surface(pts, wall) <= 1e-6) |
                            (np.abs(winding_number(pts, wall)) > 0.5))
            if not contact.all():
                if allow_exposed_end:
                    ends.append(end)
                    exposed.append(True)
                    continue
                raise OperationRefused(f"the {end:g} end has no actual receiver contact; no artificial bridge")
            selected = None
            for step in np.arange(0.0, max_embed_m + 1e-12, _STEP_M):
                for direction in (sign, -sign):
                    pts[:, axis] = end + direction * step
                    if _inside_deep(pts, neighbours, ctx.embed_min_m + _MARGIN_M).all():
                        selected = end + direction * float(step)
                        break
                if selected is not None:
                    break
            if selected is None:
                raise OperationRefused(f"the {end:g} end cannot embed within {max_embed_m:g} m")
            ends.append(selected)
            exposed.append(False)
        if all(exposed) or ends[1] - ends[0] <= 0:
            raise OperationRefused("the band needs at least one embedded end and positive axial extent")
        prism = extrude_polygon(poly, axis, ends[0], ends[1] - ends[0])
        n = len(prism.vertices) // 2
        caps = (len(prism.triangles) - 2 * n) // 2
        kept = np.ones(len(prism.triangles), bool)
        if not exposed[0]:
            kept[:caps] = False
        if not exposed[1]:
            kept[caps:2 * caps] = False
        band = Mesh(prism.vertices, prism.triangles[kept])
        deviations = silhouette_deviations(_join([mesh, *neighbours]), _join([band, *neighbours]),
                                          SILHOUETTE_MAX_M / 4)
        if max(deviations.values()) > SILHOUETTE_MAX_M:
            raise OperationRefused("the band changes the silhouette beyond 0.07 m")
        notes.update(view=view, walls=list(walls), source_ends_m=[lo, hi], embedded_ends_m=ends,
                     exposed_ends=exposed, section_recovered=section_recovered, deviations_m=deviations)
        return {**s, part: band}

    result = run_operation(scene, OPERATION, part, apply, ctx,
                           {"view": view, "walls": list(walls), "max_embed_m": max_embed_m,
                            "allow_exposed_end": allow_exposed_end, "mode": "band"})
    return replace(result, notes={**(result.notes or {}), **notes})


def face_on_wall(scene: Scene, part: str, walls, view: str, embed_m: float = EMBED_MIN_M,
                  max_reach_m: float = MAX_REACH_M, close_gaps_m: float = 0.0, allow_multi: bool = False,
                  ctx: Context = Context(), silhouette_max_m: float = SILHOUETTE_MAX_M,
                  outward_sign: int | None = None, border_growth_m: float = 0.0) -> OperationResult:
    """Replace `part` by its exterior `view` face + a skirt into `walls`, through `run_operation("from_face")`.

    `walls`: one part name or several (closed meshes of the same scene). `embed_m` below `ctx.embed_min_m` (or 10 mm) is refused, never raised silently.
    The notes carry faces before / after, the outward side, skirt depth, pieces and per-view deviations.
    An explicit source-bound outward_sign also supports real opening frames with no solid behind
    the centre. Up to 20 mm border growth may seat a source panel in that frame. Neither option
    waives border embedding, silhouette, back-face or other invariants; opaque panels stay opaque.
    """
    walls = (walls,) if isinstance(walls, str) else tuple(walls)
    notes: dict = {}
    params = {"view": view, "walls": list(walls), "embed_m": embed_m, "max_reach_m": max_reach_m,
              "close_gaps_m": close_gaps_m, "allow_multi": allow_multi,
              "outward_sign": outward_sign, "border_growth_m": border_growth_m}
    if part not in scene:
        raise ValueError(f"unknown part {part!r}")
    result = run_operation(scene, OPERATION, part,
                           lambda s: _face(s, part, walls, view, embed_m, max_reach_m, close_gaps_m, allow_multi,
                                          silhouette_max_m, notes, ctx.embed_min_m,
                                          outward_sign, border_growth_m), ctx, params)
    return replace(result, notes={**(result.notes or {}), **notes})
