"""Offset inset elements off the body so one joined NPM `*_Main` passes xView (#1966, Refs #1784) [D419].

Pattern: n/a | new-case: pure numpy over the shared xView kernel (`dt_ai.ops.inv_xview`, no Blender). A joined
delivery mesh = body volumes (anchors, never moved) + inset elements (windows, curtain glass, decor, frames, decks).
Insets touching the body make xView pairs in the joined mesh that the per-object review copy never had:
coincident vertices (< `vertex_m`) and parallel faces closer than `face_m` (NPM: 2 mm / 5 mm). Each inset
loose component is moved rigidly, never deformed:

- face pair: along the normal of the face it touches, to the side the inset lies on, until the two planes are
  `target_m` apart (`target_m - separation`);
- vertex pair (no parallel face): along the inset's own normal at that vertex by `target_m`;
- inset against inset: the component with fewer faces moves; body against body is never moved (reported, the
  caller may weld exactly coincident body vertices with `weld_targets`, which moves nothing).

Rounds repeat on the moved mesh (a move can make a new contact). A component pushed both ways is a conflict:
not moved, listed. The orchestrator-approved 1-2 mm (2026-11-25) cannot clear a parallel pair: NPM face_m is
5 mm, hence the default 6 mm (KPP1 precedent: insets >= 6 mm in front of the body).

    uv run python tools/derive/inset_offset.py DUMP.json NEW_PLAN.json [--target-mm 6] [--anchor-finish 01_,02_,03_]

DUMP.json: {"v": [[x, y, z]], "f": [[i, ...]], "finish": [name per face]} (the `dump` mode of the job's Blender
hook). Anchor = every loose component holding a face whose finish starts with an `--anchor-finish` prefix.
NEW_PLAN.json: moves per component, the vertices of each component, conflicts, rounds and the residual pairs.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import numpy as np

try:
    from dt_ai.ops import inv_xview as X
    from dt_ai.ops.inv_quads import PolyMesh
except ImportError:  # pragma: no cover - run from a checkout without the package installed
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    from dt_ai.ops import inv_xview as X
    from dt_ai.ops.inv_quads import PolyMesh

PAR = 0.99   # two move directions closer than ~8 deg are one direction
SIDE_M = 5e-4   # an inset face nearer than 0.5 mm to the body plane: its side is read from the normals, not the gap


def components(faces, n_vertices: int) -> list:
    """Loose component id per face (faces sharing a vertex are one component), numbered in face order."""
    parent = list(range(n_vertices))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for f in faces:
        r = find(f[0])
        for v in f[1:]:
            s = find(v)
            if s != r:
                parent[s] = r
    ids, out = {}, []
    for f in faces:
        out.append(ids.setdefault(find(f[0]), len(ids)))
    return out


def _normal(P):
    n = np.cross(P, np.roll(P, -1, axis=0)).sum(0)          # Newell
    ln = np.linalg.norm(n)
    return n / ln if ln > 0 else n


def vertex_comp(faces, comp, n_vertices: int) -> np.ndarray:
    vc = np.full(n_vertices, -1)
    for f, c in zip(faces, comp):
        vc[list(f)] = c
    return vc


def apply_moves(V, faces, comp, moves, vertex_moves=None) -> np.ndarray:
    """Vertices with every moved component translated (components are vertex-disjoint by construction) and the
    single vertices of `vertex_moves` (components that a rigid move cannot free) shifted."""
    V = np.array(V, float)
    vc = vertex_comp(faces, comp, len(V))
    for c, t in moves.items():
        V[vc == int(c)] += np.asarray(t, float)
    for v, t in (vertex_moves or {}).items():
        V[int(v)] += np.asarray(t, float)
    return V


def _combine(lst, target_m=None, thin_m=None):
    """Sum of one move per direction group (max amount); None when two requests point opposite ways.

    Exception: a face sandwiched between two opposite body planes closer than `thin_m` (a seam overlap of
    two body volumes, the face is hidden between them) passes through the nearer plane - moved so that both
    planes end up >= `target_m` away (amounts are `target_m - gap`)."""
    groups = []
    for d, amt in lst:
        for g in groups:
            dot = float(g[0] @ d)
            if dot > PAR:
                g[1] = max(g[1], amt)
                break
            if dot < -PAR:
                if target_m is None or 2 * target_m - g[1] - amt > thin_m:
                    return None
                a = max(g[1], 2 * target_m - amt)          # keep g's direction, cross the other plane
                b = max(amt, 2 * target_m - g[1])          # take d's direction, cross g's plane
                if b < a:
                    g[0], g[1] = d, b
                else:
                    g[1] = a
                break
        else:
            groups.append([d, amt])
    return sum((g[0] * g[1] for g in groups), np.zeros(3))


def _pairs(V, faces, tol):
    m = PolyMesh(V, tuple(tuple(f) for f in faces))
    used = np.array(sorted({v for f in faces for v in f}), int)      # a welded-away vertex is no vertex
    a, b, _ = X.vertex_pairs(V[used], tol.vertex_m)
    return X.face_pairs(m, tol), list(zip(used[a].tolist(), used[b].tolist()))


def _classify(ca, cb, anchor):
    if ca == cb:
        return "same_component"
    k = (ca in anchor) + (cb in anchor)
    return ("inset-inset", "anchor-inset", "anchor-anchor")[k]


def plan_offsets(V, faces, comp, anchor, target_m: float = 0.006, profile: str = "NPM", rounds: int = 6,
                 cap_m: float = 0.03, trace=()) -> dict:
    """Moves per inset component until no xView pair involves an inset (or `rounds` run out).

    Rigid first; a component pushed both ways (an F05-like glazing closed against two opposite jambs) is moved
    locally instead: only the vertices of its touching faces shift, each along its own request (the element
    gets `target_m` shorter at each end). A vertex still pushed both ways stays and is listed."""
    tol = X.tolerance_for(profile).validate()
    V0 = np.array(V, float)
    faces = [tuple(f) for f in faces]
    anchor = set(anchor)
    nfaces = collections.Counter(comp)
    vfaces = collections.defaultdict(list)
    for k, f in enumerate(faces):
        for v in f:
            vfaces[v].append(k)
    vc = vertex_comp(faces, comp, len(V0))
    size = {}                 # inset against inset: the smaller element (bounding-box diagonal) moves
    for c in set(comp):
        P = V0[vc == c]
        size[c] = float(np.linalg.norm(P.max(0) - P.min(0)))
    moves: dict = {}
    vmoves: dict = {}
    local: dict = {}          # component -> why it is moved per vertex
    stuck: set = set()
    why: dict = {}            # stuck vertex -> its opposite requests [dx, dy, dz, amount, source component]
    traced: dict = {}
    hist: dict = {}           # component -> directions of its applied rigid moves
    pinned: set = set()       # inset held between other insets: they move, it does not
    capped = 0
    log = []

    def pick(ca, cb):                        # (mover, anchor side) or None when neither may move
        fa, fb = ca in anchor or ca in pinned, cb in anchor or cb in pinned
        if fa and fb:
            return None
        if fa:
            return cb, ca
        if fb:
            return ca, cb
        return (ca, cb) if (size[ca], -ca) < (size[cb], -cb) else (cb, ca)

    for r in range(rounds):
        Vc = apply_moves(V0, faces, comp, moves, vmoves)
        fp, vp = _pairs(Vc, faces, tol)
        cen = {}
        req = collections.defaultdict(list)          # comp -> [(direction, amount, vertices, source comp)]
        for i, j, _kind, _sep in fp:
            if comp[i] == comp[j]:
                continue
            p = pick(comp[i], comp[j])
            if p is None:
                continue
            mov = p[0]
            fm, fa = (i, j) if comp[i] == mov else (j, i)
            Pa, Pm = Vc[list(faces[fa])], Vc[list(faces[fm])]
            n = _normal(Pa)
            s = float((Pm.mean(0) - Pa.mean(0)) @ n)
            if abs(s) <= SIDE_M:                             # (nearly) coplanar: the side is not measurable
                if float(_normal(Pm) @ n) < -0.5:            # back to back: the inset faces into the body face
                    s = 1.0
                else:
                    if mov not in cen:
                        cen[mov] = Vc[vc == mov].mean(0)
                    s = float((cen[mov] - Pa.mean(0)) @ n) or 1.0
            d = np.sign(s) * n
            dmin = float(((Pm - Pa.mean(0)) @ d).min())     # nearest point of the inset face to the body plane
            amt = target_m - dmin
            if amt > cap_m:
                amt, capped = cap_m, capped + 1
            if amt > 0:
                req[mov].append((d, amt, faces[fm], comp[fa]))
        for a, b in vp:
            p = pick(int(vc[a]), int(vc[b]))
            if p is None:
                continue
            v = a if vc[a] == p[0] else b
            w = b if v == a else a
            if p[0] in req:      # follow the element's own face move, but at least target_m (frees the vertex)
                own = [q for q in req[p[0]] if v in q[2]] or req[p[0]]
                req[p[0]].append((own[0][0], target_m, (v,), int(vc[w])))
                continue
            n = sum((_normal(Vc[list(faces[k])]) for k in vfaces[v]), np.zeros(3))
            if np.linalg.norm(n) == 0:
                continue
            na = sum((_normal(Vc[list(faces[k])]) for k in vfaces[w]), np.zeros(3))
            if float(n @ na) < 0:                            # never into the surface it touches
                n = -n
            req[p[0]].append((n / np.linalg.norm(n), target_m, (v,), int(vc[w])))
        log.append({"round": r + 1, "face_pairs": len(fp), "vertex_pairs": len(vp), "movers": len(req)})
        if not req:
            break
        for c, lst in sorted(req.items()):
            if c in trace:
                traced.setdefault(int(c), []).append([r + 1] + [[round(float(x), 4) for x in d] + [round(amt, 4), int(src)]
                                                                for d, amt, _, src in lst])
            t = None if c in local else _combine([(d, amt) for d, amt, _, _ in lst])
            back = t is not None and any(float(h @ d) < -PAR for h in hist.get(c, ()) for d, _, _, _ in lst)
            if back:              # pushed back against an earlier move: held from both sides over the rounds
                t = None
                local.setdefault(c, "pushed back over rounds: moved per vertex")
            if t is None and c not in local and not any(src in anchor for *_, src in lst):
                pinned.add(c)                                # held between insets: the insets around it move
                continue
            if t is None:
                local.setdefault(c, "pushed both ways: moved per vertex")
                per = collections.defaultdict(list)
                for d, amt, vs, src in lst:
                    for v in vs:
                        per[int(v)].append((d, amt, src))
                for v, vl in per.items():
                    tv = _combine([(d, amt) for d, amt, _ in vl], target_m, tol.face_m)
                    if tv is None:
                        stuck.add(v)
                        why.setdefault(v, [[round(float(x), 3) for x in d] + [round(amt, 4), int(sc)] for d, amt, sc in vl])
                    else:
                        vmoves[v] = vmoves.get(v, np.zeros(3)) + tv
            elif np.linalg.norm(t) > 0:
                moves[c] = np.asarray(moves.get(c, np.zeros(3))) + t
                hist.setdefault(c, []).extend(d for d, _, _, _ in lst)
    Vc = apply_moves(V0, faces, comp, moves, vmoves)
    fp, vp = _pairs(Vc, faces, tol)
    by = collections.Counter()
    for i, j, kind, _ in fp:
        by["face:%s:%s" % (_classify(comp[i], comp[j], anchor), kind)] += 1
    for a, b in vp:
        by["vertex:%s" % _classify(int(vc[a]), int(vc[b]), anchor)] += 1
    every = list(moves.values()) + list(vmoves.values())
    return {"profile": profile, "target_m": target_m, "thresholds": {"vertex_m": tol.vertex_m, "face_m": tol.face_m},
            "moves": {int(c): [round(float(x), 6) for x in t] for c, t in moves.items()},
            "vertex_moves": {int(v): [round(float(x), 6) for x in t] for v, t in vmoves.items()},
            "local": {int(c): w for c, w in local.items()}, "pinned": sorted(int(c) for c in pinned), "stuck_vertices": sorted(stuck), "stuck_requests": {int(v): why[v] for v in sorted(why)}, "capped": capped,
            "rounds": log, "trace": traced, "max_move_m": round(max((float(np.linalg.norm(t)) for t in every), default=0.0), 6),
            "residual": {"face_pairs": len(fp), "vertex_pairs": len(vp), "by_class": dict(sorted(by.items()))}}


def weld_targets(V, faces, comp, anchor, eps: float = 1e-5) -> dict:
    """{drop vertex: keep vertex} for exactly coincident (<= eps) vertices of two different anchor components.

    Welding moves no vertex (keep and drop are within eps); it removes the unwelded seam contacts between body
    volumes joined into one mesh (bmesh.ops.weld_verts keeps the UV loops). A pair is welded only when it closes
    a shared edge with another pair (both ends coincident): a lone corner weld would make a bow-tie vertex."""
    V = np.asarray(V, float)
    vc = vertex_comp(faces, comp, len(V))
    a, b, _ = X.vertex_pairs(V, eps)
    nb = collections.defaultdict(set)
    for f in faces:
        for i, v in enumerate(f):
            nb[v].add(f[i - 1])
            nb[f[i - 1]].add(v)
    pairs = [(x, y) for x, y in zip(a.tolist(), b.tolist())
             if vc[x] != vc[y] and vc[x] in anchor and vc[y] in anchor]
    mate = collections.defaultdict(set)
    for x, y in pairs:
        mate[x].add(y)
        mate[y].add(x)
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for x, y in pairs:
        if not any(mate[x2] & nb[y] for x2 in nb[x]):          # no neighbour pair: the volumes meet at a point
            continue
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)
    return {int(k): int(find(k)) for k in parent}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offset inset components off the body for a joined NPM *_Main (#1966)")
    ap.add_argument("dump")
    ap.add_argument("out")
    ap.add_argument("--target-mm", type=float, default=6.0)
    ap.add_argument("--anchor-finish", default="01_,02_,03_")
    ap.add_argument("--profile", default="NPM")
    ap.add_argument("--weld-anchor", action="store_true", help="also list coincident body vertices to weld")
    a = ap.parse_args(argv)
    if os.path.exists(a.out):
        print("refused: output exists", file=sys.stderr)
        return 2
    with open(a.dump, encoding="utf-8") as fh:
        d = json.load(fh)
    V, F, fin = np.array(d["v"], float), [tuple(f) for f in d["f"]], d["finish"]
    comp = components(F, len(V))
    pref = tuple(p for p in a.anchor_finish.split(",") if p)
    anchor = {c for c, f in zip(comp, fin) if f.startswith(pref)}
    weld = weld_targets(V, F, comp, anchor) if a.weld_anchor else {}
    if weld:   # measure the plan on the welded mesh (the weld moves nothing; it only merges indices)
        F = [tuple(dict.fromkeys(weld.get(v, v) for v in f)) for f in F]
    plan = plan_offsets(V, F, comp, anchor, a.target_mm / 1000.0, a.profile)
    vc = vertex_comp(F, comp, len(V))
    plan["components"] = len(set(comp))
    plan["anchors"] = sorted(anchor)
    plan["weld"] = weld
    plan["move_vertices"] = {str(c): np.flatnonzero(vc == c).tolist() for c in plan["moves"]}
    plan["moves"] = {str(c): t for c, t in plan["moves"].items()}
    plan["vertex_moves"] = {str(v): t for v, t in plan["vertex_moves"].items()}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1)
    print("OFFSET target %.1f mm: %d components moved rigidly, %d per vertex (max %.4f m), %d stuck, residual %s" % (
        a.target_mm, len(plan["moves"]), len(plan["local"]), plan["max_move_m"], len(plan["stuck_vertices"]),
        plan["residual"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
