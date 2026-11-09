"""Explicit repair op `repair.flip_close` on one polygon part (#1144, follow-up of [D201] #968).

new-case: source-baseline repair op - flip faces against their component's majority winding, cap planar convex
open border loops. Pure numpy on inv_quads.PolyMesh; no DCC or files.

[D201] judges every op relative to the source. This op is the one that CHANGES the source baseline: the caller
records the before/after violators and uses the repaired part as the new baseline. Every input polygon ends in the
output (flipped or as is, `face_sources[i]` = its input index); a cap is a new polygon (`face_sources` None) listed
in `caps`; a border loop that is not capped is listed in `skipped` with its reason. Nothing is defaulted: material
and UV of caps are the caller's (they are new geometry).
"""
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from dt_ai.ops.inv_quads import PolyMesh

PLANE_M = 0.002     # a cap loop must lie within 2 mm of its best-fit plane (the simplify line tolerance)


@dataclass(frozen=True)
class RepairResult:
    mesh: PolyMesh
    face_sources: tuple   # per output polygon: input polygon index, or None for a cap
    flipped: tuple        # input polygon indices whose winding was reversed
    caps: tuple           # per cap: (output polygon index, loop vertex ids)
    skipped: tuple        # per open loop not capped: (loop vertex ids, reason)


def _edges(f):
    return [(f[k], f[(k + 1) % len(f)]) for k in range(len(f))]


def _orient(faces):
    """Per face True = flip, so that every manifold edge is used once in each direction. Per connected component
    the smaller set is flipped (majority winding wins; a tie keeps the lowest face index as is)."""
    by_edge = defaultdict(list)
    for fi, f in enumerate(faces):
        for a, b in _edges(f):
            by_edge[frozenset((a, b))].append((fi, (a, b)))
    flip = [None] * len(faces)
    for seed in range(len(faces)):
        if flip[seed] is not None:
            continue
        flip[seed], comp, queue = False, [seed], [seed]
        while queue:
            fi = queue.pop()
            for a, b in _edges(faces[fi]):
                users = by_edge[frozenset((a, b))]
                if len(users) != 2:
                    continue
                (g, eg), = [u for u in users if u[0] != fi] or [(None, None)]
                if g is None:
                    continue
                same_dir = eg == (a, b)
                want = flip[fi] ^ same_dir     # same direction in both faces -> opposite flip state
                if flip[g] is None:
                    flip[g] = want
                    comp.append(g)
                    queue.append(g)
                elif flip[g] != want:
                    raise ValueError(f"face {g}: non-orientable component (edge {a}-{b})")
        if 2 * sum(flip[i] for i in comp) > len(comp):
            for i in comp:
                flip[i] = not flip[i]
    return flip


def _loops(faces):
    """Open border loops as cap vertex rings: each border half-edge a->b is capped as b->a."""
    count = defaultdict(int)
    for f in faces:
        for a, b in _edges(f):
            count[frozenset((a, b))] += 1
    nxt, bad = defaultdict(list), set()
    for f in faces:
        for a, b in _edges(f):
            if count[frozenset((a, b))] == 1:
                nxt[b].append(a)
    loops, seen = [], set()
    for start in sorted(nxt):
        if start in seen:
            continue
        ring, at = [], start
        while at not in seen and at in nxt:
            seen.add(at)
            ring.append(at)
            if len(nxt[at]) != 1:
                bad.add(len(loops))
            at = nxt[at][0]
        loops.append((tuple(ring), at == start and len(loops) not in bad))
    return loops


def _cap_reason(v, ring, plane_m):
    if len(ring) < 3:
        return "fewer than 3 points"
    p = v[list(ring)]
    c = p.mean(0)
    _, s, vt = np.linalg.svd(p - c)
    n = vt[2]
    if np.max(np.abs((p - c) @ n)) > plane_m:
        return f"nonplanar beyond {plane_m} m"
    u = vt[0]
    w = np.cross(n, u)
    q = np.stack([(p - c) @ u, (p - c) @ w], 1)
    e = np.roll(q, -1, 0) - q
    e2 = np.roll(e, -1, 0)
    cross = e[:, 0] * e2[:, 1] - e[:, 1] * e2[:, 0]
    # a point within plane_m of the chord of its neighbours is straight, not a turn (float32 sources)
    straight = np.abs(cross) <= plane_m * np.maximum(np.linalg.norm(e + e2, axis=1), 1e-12)
    turns = cross[~straight]
    if len(turns) < 3 or not (np.all(turns > 0) or np.all(turns < 0)):
        return "not a convex loop"
    return None


def flip_close(mesh: PolyMesh, *, close=None, plane_m: float = PLANE_M) -> RepairResult:
    """Flip faces against their component's majority winding, then cap open border loops.

    `close`: None = cap every open loop; else a set of frozenset({a, b}) border edges - a loop is capped only
    when ALL its edges are in it (the others are `skipped`, reason "not selected"). A loop that is not closed,
    branches, is nonplanar beyond `plane_m` or not convex is `skipped` with that reason, never forced."""
    if not isinstance(mesh, PolyMesh):
        raise ValueError(f"unsupported mesh {type(mesh).__name__}")
    if isinstance(plane_m, bool) or not np.isfinite(plane_m) or not 0 < plane_m <= PLANE_M:
        raise ValueError(f"plane_m must be finite and in (0, {PLANE_M}]")
    if not mesh.faces:
        raise ValueError("empty mesh")
    v = np.asarray(mesh.vertices, float)
    flip = _orient(mesh.faces)
    faces = [tuple(f[:1] + f[1:][::-1]) if fl else tuple(f) for f, fl in zip(mesh.faces, flip)]
    sources = list(range(len(faces)))
    caps, skipped = [], []
    for ring, closed in _loops(faces):
        edges = {frozenset((ring[k], ring[(k + 1) % len(ring)])) for k in range(len(ring))}
        if not closed:
            why = "open or branching border chain"
        elif close is not None and not edges <= set(close):
            why = "not selected"
        else:
            why = _cap_reason(v, ring, plane_m)
        if why:
            skipped.append((ring, why))
            continue
        caps.append((len(faces), ring))
        faces.append(ring)
        sources.append(None)
    return RepairResult(PolyMesh(v.copy(), tuple(faces)), tuple(sources),
                        tuple(i for i, fl in enumerate(flip) if fl), tuple(caps), tuple(skipped))
