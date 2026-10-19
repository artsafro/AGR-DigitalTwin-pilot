"""Visibility invariants of the operation kernel: what must hold before and after every operation [D108, D115].

The invariant is visibility, not closure (grilling log Q18): an open border is normal at a joint as long as nobody
sees it. After an operation on a part (1) every open border edge lies inside a neighbouring part, embedded at least
`embed_min_m` (10 mm), or below the Ground, or the part is an opacity / glass plane; (2) no face was deleted that was
not covered: a projection of the scene from many directions loses no pixel; (3) no viewer sees a back face (gnawed
geometry, flipped normals) except on parts that are two-sided on purpose; (4) no co-directional faces closer than
`overlap_min_m` (5 mm, reg p.8 §3.9; z-fighting). The checks return counts and the first offenders so a broken
invariant can roll the operation back and stop with a question.

Pure numpy on triangle meshes in metres (the 2-4 checks reuse `twinqa.clearance`); no Blender. Meant for parts and
synthetic scenes: the ray probe tests every ray against every triangle, so a whole building needs a BVH (the
bpy kernel, later cards). The probe sees nothing smaller than one pixel (`2 * radius / resolution`).
Not here yet: quad dominance and texel readiness [D129] (they need polygons, not triangles).
Pattern: none - kernel foundation (grilling log card C3).
"""
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from twinqa.clearance import near_parallel_overlaps
from twinqa.geometry.mesh import weld

EMBED_MIN_M = 0.010
OVERLAP_MIN_M = 0.005
WELD_M = 1e-4
_EPS = 1e-9
_BUDGET = 4_000_000     # ray x triangle pairs per numpy block


@dataclass(frozen=True)
class Mesh:
    vertices: np.ndarray   # (n, 3) metres
    triangles: np.ndarray  # (m, 3) int, counter-clockwise seen from the outside

    def __post_init__(self):
        v = np.asarray(self.vertices, dtype=float)
        t = np.asarray(self.triangles, dtype=int)
        if v.ndim != 2 or v.shape[1] != 3 or t.ndim != 2 or t.shape[1] != 3:
            raise ValueError("vertices must be (n, 3) and triangles (m, 3)")
        if len(t) and (t.min() < 0 or t.max() >= len(v)):
            raise ValueError("triangle index outside the vertices")
        if not np.isfinite(v).all():
            raise ValueError("vertices must be finite")
        object.__setattr__(self, "vertices", v)
        object.__setattr__(self, "triangles", t)

    def corners(self) -> np.ndarray:
        return self.vertices[self.triangles]


Scene = dict[str, Mesh]   # part id -> mesh


@dataclass(frozen=True)
class Context:
    ground_z: float | None = None                      # border edges at or below it are hidden
    opacity_parts: frozenset = frozenset()             # opacity / glass planes: open borders and back faces allowed
    embed_min_m: float = EMBED_MIN_M
    overlap_min_m: float = OVERLAP_MIN_M
    resolution: int = 48                               # rays per side of the probe
    lost_pixels_max: int = 0


@dataclass(frozen=True)
class InvariantResult:
    name: str
    passed: bool
    count: int
    offenders: tuple = ()      # up to 5 short descriptions


@dataclass(frozen=True)
class InvariantReport:
    results: tuple = ()
    passed: bool = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "passed", all(r.passed for r in self.results))

    @property
    def broken(self) -> tuple:
        return tuple(r for r in self.results if not r.passed)

    def to_dict(self) -> dict:
        return {"passed": self.passed,
                "results": [{"name": r.name, "passed": r.passed, "count": r.count, "offenders": list(r.offenders)}
                            for r in self.results]}


def _result(name, offenders):
    return InvariantResult(name, not offenders, len(offenders), tuple(str(o) for o in offenders[:5]))


# ---- geometry helpers -------------------------------------------------------------------------------------------

def border_edges(mesh: Mesh) -> np.ndarray:
    """(k, 2, 3) world points of the edges used by exactly one triangle, after a 0.1 mm weld."""
    if not len(mesh.triangles):
        return np.zeros((0, 2, 3))
    ids = weld(mesh.vertices, WELD_M)
    t = ids[mesh.triangles]
    e = np.sort(np.stack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]], axis=1).reshape(-1, 2), axis=1)
    edges, counts = np.unique(e, axis=0, return_counts=True)
    use = edges[counts == 1]
    first = np.zeros(int(ids.max()) + 1, dtype=int)
    first[ids[::-1]] = np.arange(len(ids))[::-1]    # a vertex of each welded id
    return mesh.vertices[first[use]]


def winding_number(points: np.ndarray, mesh: Mesh) -> np.ndarray:
    """(P,) generalised winding number of a closed mesh: about +1 inside, 0 outside (Van Oosterom-Strackee)."""
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    tri = mesh.corners()
    if not len(tri) or not len(points):
        return np.zeros(len(points))
    total = np.zeros(len(points))
    step = max(1, _BUDGET // (9 * len(tri)))
    for s in range(0, len(points), step):
        r = tri[None, :, :, :] - points[s:s + step, None, None, :]          # (P, T, 3, 3)
        ra, rb, rc = r[:, :, 0], r[:, :, 1], r[:, :, 2]
        la, lb, lc = (np.linalg.norm(x, axis=-1) for x in (ra, rb, rc))
        num = np.einsum("ptk,ptk->pt", ra, np.cross(rb, rc))
        den = la * lb * lc + np.einsum("ptk,ptk->pt", ra, rb) * lc + np.einsum("ptk,ptk->pt", ra, rc) * lb \
            + np.einsum("ptk,ptk->pt", rb, rc) * la
        total[s:s + step] = (2 * np.arctan2(num, den)).sum(axis=1) / (4 * np.pi)
    return total


def distance_to_surface(points: np.ndarray, mesh: Mesh) -> np.ndarray:
    """(P,) distance from every point to the nearest triangle of the mesh."""
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    tri = mesh.corners()
    if not len(tri) or not len(points):
        return np.full(len(points), np.inf)
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    e1, e2 = b - a, c - a
    n = np.cross(e1, e2)
    nn = np.linalg.norm(n, axis=1)
    d11, d12, d22 = (e1 * e1).sum(1), (e1 * e2).sum(1), (e2 * e2).sum(1)
    det = d11 * d22 - d12 * d12
    out = np.empty(len(points))
    step = max(1, _BUDGET // (9 * len(tri)))
    for s in range(0, len(points), step):
        p = points[s:s + step, None, :]
        sv = p - a[None]
        d1, d2 = (sv * e1[None]).sum(2), (sv * e2[None]).sum(2)
        with np.errstate(divide="ignore", invalid="ignore"):
            l1 = (d22 * d1 - d12 * d2) / det
            l2 = (d11 * d2 - d12 * d1) / det
            plane = np.abs((sv * n[None]).sum(2)) / nn
        inside = (det > 1e-18) & (nn > 1e-12) & (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        best = np.where(inside, plane, np.inf)
        for p0, p1 in ((a, b), (b, c), (c, a)):
            seg = (p1 - p0)[None]
            ll = np.maximum((seg * seg).sum(2), 1e-30)
            t = np.clip(((p - p0[None]) * seg).sum(2) / ll, 0.0, 1.0)
            best = np.minimum(best, np.linalg.norm(p - (p0[None] + t[..., None] * seg), axis=2))
        out[s:s + step] = best.min(axis=1)
    return out


def _directions() -> np.ndarray:
    """The 26 directions of a cube's faces, edges and corners, unit length."""
    d = np.array([(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)],
                 dtype=float)
    return d / np.linalg.norm(d, axis=1)[:, None]


def _first_hits(origins, d, corners, budget=_BUDGET):
    """Nearest triangle along d for every origin: (index or -1, back_face flag). Moller-Trumbore with matmuls."""
    r = len(origins)
    if not len(corners):
        return np.full(r, -1), np.zeros(r, dtype=bool)
    v0 = corners[:, 0]
    e1, e2 = corners[:, 1] - v0, corners[:, 2] - v0
    h = np.cross(d, e2)
    a = (e1 * h).sum(1)
    ok = np.abs(a) > 1e-14
    f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
    n = np.cross(e1, e2)
    w = np.cross(e1, d)
    c_u, c_v, c_t = (v0 * h).sum(1), (v0 * w).sum(1), (v0 * n).sum(1)
    hit = np.full(r, -1)
    step = max(1, budget // len(corners))
    for s in range(0, r, step):
        o = origins[s:s + step]
        u = (o @ h.T - c_u) * f
        v = (o @ w.T - c_v) * f
        t = (o @ n.T - c_t) * f
        valid = ok & (u >= -_EPS) & (v >= -_EPS) & (u + v <= 1 + _EPS) & (t > _EPS)
        t = np.where(valid, t, np.inf)
        idx = t.argmin(axis=1)
        found = np.isfinite(t[np.arange(len(o)), idx])
        hit[s:s + step] = np.where(found, idx, -1)
    back = np.zeros(r, dtype=bool)
    got = hit >= 0
    back[got] = (n[hit[got]] @ d) > 0       # the ray travels along the normal: it enters from behind
    return hit, back


def _grid(center, radius, d, res):
    helper = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d, helper)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    cell = 2 * radius / res
    s = (np.arange(res) + 0.37) * cell - radius           # off-centre so rays avoid shared edges and axis planes
    gx, gy = np.meshgrid(s, s + 0.11 * cell)
    return center - d * (1.5 * radius) + gx.reshape(-1, 1) * u + gy.reshape(-1, 1) * v


def _stack(scene: Scene):
    parts = list(scene)
    corners = [scene[p].corners() for p in parts]
    owner = np.concatenate([np.full(len(c), i) for i, c in enumerate(corners)]) if corners else np.zeros(0, int)
    return parts, (np.concatenate(corners) if corners else np.zeros((0, 3, 3))), owner


def _frame(*scenes: Scene):
    pts = np.concatenate([m.vertices for s in scenes for m in s.values() if len(m.vertices)] or [np.zeros((1, 3))])
    lo, hi = pts.min(0), pts.max(0)
    return (lo + hi) / 2, max(float(np.linalg.norm(hi - lo)) / 2 * 1.02, 1e-3)


# ---- the four invariants ----------------------------------------------------------------------------------------

def open_borders_hidden(scene: Scene, part: str, ctx: Context = Context()) -> InvariantResult:
    """(1) Every open border edge of `part` lies inside a neighbour (>= embed_min_m deep) or at / below the Ground."""
    name = "open_borders_hidden"
    if part in ctx.opacity_parts:
        return _result(name, [])
    edges = border_edges(scene[part])
    if not len(edges):
        return _result(name, [])
    samples = np.concatenate([edges[:, 0], edges[:, 1], edges.mean(axis=1)])        # ends and middle of every edge
    hidden = np.zeros(len(samples), dtype=bool)
    if ctx.ground_z is not None:
        hidden |= samples[:, 2] <= ctx.ground_z + 1e-6
    for other, mesh in scene.items():
        if other == part or hidden.all() or not len(mesh.triangles):
            continue
        todo = np.flatnonzero(~hidden)
        inside = np.abs(winding_number(samples[todo], mesh)) > 0.5
        deep = distance_to_surface(samples[todo[inside]], mesh) >= ctx.embed_min_m - 1e-9
        hidden[todo[inside][deep]] = True
    k = len(edges)
    bad = np.flatnonzero(~(hidden[:k] & hidden[k:2 * k] & hidden[2 * k:]))
    return _result(name, [f"{part}: edge {np.round(edges[i, 0], 4).tolist()} -> {np.round(edges[i, 1], 4).tolist()}"
                          for i in bad])


def no_see_through_hole(before: Scene, after: Scene, ctx: Context = Context()) -> InvariantResult:
    """(2) No ray that hit the scene before the operation misses it after: nothing was deleted that was not covered."""
    name = "no_see_through_hole"
    parts, c0, owner = _stack(before)
    _, c1, _ = _stack(after)
    # Registration alone does not waive holes in existing opacity parts, or removal of a part.
    replaced = np.array([
        p in ctx.opacity_parts and p in after and len(before[p].triangles) > 2
        and len(after[p].triangles) == 2 and len(after[p].vertices) == 4
        and np.linalg.matrix_rank(after[p].vertices - after[p].vertices.mean(axis=0), tol=1e-10) == 2
        for p in parts], dtype=bool)
    center, radius = _frame(before, after)
    lost = []
    total = 0
    for d in _directions():
        origins = _grid(center, radius, d, ctx.resolution)
        first = _first_hits(origins, d, c0)[0]
        was = first >= 0
        # Exempt only rays whose BEFORE first hit belongs to the replaced candidate.
        # Never index -1 (misses), nor exempt a different first-hit part behind/in front of it.
        was[was] &= ~replaced[owner[first[was]]]
        now = _first_hits(origins, d, c1)[0] >= 0
        n = int((was & ~now).sum())
        total += n
        if n:
            lost.append(f"direction {np.round(d, 2).tolist()}: {n} pixels lost")
    if total <= ctx.lost_pixels_max:
        return InvariantResult(name, True, total)
    return InvariantResult(name, False, total, tuple(lost[:5]))


def no_visible_back_faces(scene: Scene, ctx: Context = Context()) -> InvariantResult:
    """(3) The first surface a viewer meets is never a back face, except on opacity / glass parts. count = pixels."""
    name = "no_visible_back_faces"
    parts, corners, owner = _stack(scene)
    exempt = np.array([p in ctx.opacity_parts for p in parts], dtype=bool)
    center, radius = _frame(scene)
    count, notes = 0, []
    for d in _directions():
        origins = _grid(center, radius, d, ctx.resolution)
        hit, back = _first_hits(origins, d, corners)
        seen = back & (hit >= 0)
        seen[seen] = ~exempt[owner[hit[seen]]]
        n = int(seen.sum())
        count += n
        if n:
            names = sorted({parts[i] for i in owner[hit[seen]]})
            notes.append(f"direction {np.round(d, 2).tolist()}: {n} pixels of {names}")
    return InvariantResult(name, count == 0, count, tuple(notes[:5]))


def no_close_overlap(scene: Scene, parts: Iterable[str] | None = None, ctx: Context = Context()) -> InvariantResult:
    """(4) No co-directional overlapping faces closer than overlap_min_m (z-fighting); a pair must touch `parts`."""
    name = "no_close_overlap"
    faces = [{"object": p, "index": i, "points": tri.tolist()}
             for p, mesh in scene.items() for i, tri in enumerate(mesh.corners())]
    watch = set(scene if parts is None else parts)
    pairs = [q for q in near_parallel_overlaps(faces, ctx.overlap_min_m)
             if q["same_direction"] and (q["a"][0] in watch or q["b"][0] in watch)]
    return _result(name, [f"{q['a'][0]}#{q['a'][1]} / {q['b'][0]}#{q['b'][1]}: {q['distance_m'] * 1000:.1f} mm"
                          for q in pairs])


def check_operation(before: Scene | None, after: Scene, changed: Iterable[str], ctx: Context = Context()) -> InvariantReport:
    """All four invariants for an operation that changed the parts `changed`; `before` None skips the hole check."""
    changed = list(changed)
    missing = [p for p in changed if p not in after]
    if missing:
        raise ValueError(f"changed parts not in the scene: {missing}")
    results = [_merge("open_borders_hidden", [open_borders_hidden(after, p, ctx) for p in changed])]
    if before is not None:
        results.append(no_see_through_hole(before, after, ctx))
    results += [no_visible_back_faces(after, ctx), no_close_overlap(after, changed, ctx)]
    return InvariantReport(tuple(results))


def _merge(name, results):
    offenders = [o for r in results for o in r.offenders]
    return InvariantResult(name, all(r.passed for r in results), sum(r.count for r in results), tuple(offenders[:5]))
