"""Kernel invariant quad_dominance: the editable master has triangles only where they are needed [D129, D108, D131].

The editable master (NPM-OKS, VPM-OKS, NPM / VPM Ground; not the triangulated export [D021], DER-03) is 100 % quads
except needed triangles (`docs/domain/geometry.md`, "Editable master"). `invariants.Mesh` holds triangles only, so this
module reads its own polygon mesh `PolyMesh`; topology comes from the face indices (no weld).

Every face of a part gets one label. Faces with more than 4 sides are `ngon` offenders; a face with zero area
(<= `AREA_EPS_M2`) is a `degenerate` offender; a quad is fine. A triangle is classified in this order:
1. `mergeable` (offender): across one of its manifold edges lies another triangle and the two form a convex planar
   quad: dihedral <= `planar_deg` (default `PLANAR_DEG`, orientation of the windings ignored), every corner turns the
   same way and no interior angle >= `STRAIGHT_DEG`. The spokes of a qualifying fan (rule 3) are not merge
   candidates - otherwise a 5-gon or 6-gon fan cap could never pass (acceptance (d) of #345).
2. `needed:odd_boundary`: the triangle has an edge on the outline of its coplanar patch (faces joined across
   manifold edges with dihedral <= `planar_deg`; open borders count as outline) and that outline has an odd number
   of edges in total - then no quad-only fill exists (4Q + 3T = 2E_inner + B, so T = B mod 2). Parity is taken
   over all loops of the patch (an annulus with two odd loops can be filled with quads) and only the minimal one
   triangle per odd patch is needed: the first candidate by face id; further triangles fall through to rules 3-5.
3. `needed:pole_fan`: the triangle belongs to a closed fan (every face around one vertex is a triangle, the spokes
   are manifold and the rim is one cycle) that either closes a coplanar n-gon cap with n >= 5 rim corners (a rim
   vertex counts as a corner when its interior angle is < `STRAIGHT_DEG`) or, when not coplanar, sits around a pole
   of valence 3 or >= 5 (cone tips). Fans on an open border are not recognised.
4. `needed:parts_list`: the part is in the allowance set (`allow_triangles_from_parts`: parts with
   `operation == "library_replace"` - Flora, MAF library objects - and the [D109] opacity classes `railing`,
   `rod_ladder`, `grille`, `ac_screen`, `fence`).
5. otherwise `unneeded` (offender).

Thresholds (no number exists in the decisions; orchestrator default, user may change): `unneeded + mergeable +
ngon + degenerate` = 0 for every profile; per part the needed-triangle share (needed triangles / faces) <= 10 % for
NPM and <= 5 % for VPM, exactly at the limit passes. Parts in the allowance set are exempt from the share cap
(their triangles are allowed). `count` of the result = offending faces plus one per part over the share cap or
without faces. Fail-closed: no part to check, a part without faces or an unknown profile never pass; malformed
input (NaN / inf, an index out of range, a repeated index in a face, < 3 sides) raises `ValueError`.

Pure numpy, no Blender; checks the parts an operation changed, after the operation.
Pattern: none | new-case: quad-dominance kernel invariant on polygon meshes (D129).
"""
from dataclasses import dataclass, field
from typing import Iterable, Mapping

import numpy as np

from dt_ai.ops.invariants import InvariantReport, InvariantResult

PLANAR_DEG = 1.0          # orchestrator default, user may change - max dihedral of "coplanar" / mergeable faces
STRAIGHT_DEG = 179.0      # orchestrator default, user may change - an interior angle this wide is a straight corner
NPM_SHARE_MAX = 0.10      # orchestrator default, user may change - needed triangles / faces per part, NPM
VPM_SHARE_MAX = 0.05      # orchestrator default, user may change - needed triangles / faces per part, VPM
POLE_CAP_MIN_CORNERS = 5  # orchestrator default, user may change - a coplanar fan closes an n-gon cap, n >= 5
AREA_EPS_M2 = 1e-12       # orchestrator default, user may change - a face with no more area is degenerate
NAME = "quad_dominance"

SHARE_MAX = {"NPM": NPM_SHARE_MAX, "VPM": VPM_SHARE_MAX}
_PROFILE_SUFFIXES = ("", "-OKS", "-GROUND")
ALLOW_CLASSES = frozenset({"railing", "rod_ladder", "grille", "ac_screen", "fence"})   # [D109] opacity classes
OFFENDING = ("mergeable", "unneeded", "ngon", "degenerate")


@dataclass(frozen=True)
class PolyMesh:
    vertices: np.ndarray   # (n, 3) metres
    faces: tuple           # tuple of int index tuples, each >= 3 distinct indices

    def __post_init__(self):
        v = np.asarray(self.vertices, dtype=float)
        if v.ndim != 2 or v.shape[1] != 3:
            raise ValueError("vertices must be (n, 3)")
        if not np.isfinite(v).all():
            raise ValueError("vertices must be finite")
        faces = []
        for k, face in enumerate(self.faces):
            ids = []
            for i in face:
                if isinstance(i, (bool, np.bool_)) or not isinstance(i, (int, np.integer)):
                    raise ValueError(f"face {k}: index {i!r} is not an integer")
                ids.append(int(i))
            if len(ids) < 3:
                raise ValueError(f"face {k}: fewer than 3 sides")
            if min(ids) < 0 or max(ids) >= len(v):
                raise ValueError(f"face {k}: index outside the vertices")
            if len(set(ids)) != len(ids):
                raise ValueError(f"face {k}: repeated vertex index")
            faces.append(tuple(ids))
        object.__setattr__(self, "vertices", v)
        object.__setattr__(self, "faces", tuple(faces))


PolyScene = Mapping[str, PolyMesh]   # part id -> polygon mesh


@dataclass(frozen=True)
class PartQuadReport:
    part: str
    faces: int
    triangles: int
    quads: int
    ngons: int
    triangle_share: float                         # triangles / faces
    needed_share: float                           # needed triangles / faces
    share_max: float | None                       # None: part in the allowance set, no cap
    needed: dict = field(default_factory=dict)    # reason -> count ("odd_boundary", "pole_fan", "parts_list")
    offenders: tuple = ()                         # every offender, "part#face: reason"

    @property
    def passed(self) -> bool:
        return not self.offenders


def allow_triangles_from_parts(parts) -> frozenset:
    """Part ids allowed to keep triangles: library replacements and the [D109] opacity classes of a PartsList."""
    return frozenset(p.id for p in parts.parts if p.operation == "library_replace" or p.part_class in ALLOW_CLASSES)


def share_max(profile) -> float:
    """Needed-triangle share cap of a profile: NPM / VPM, optionally -OKS or -Ground; anything else is ValueError."""
    if not isinstance(profile, str):
        raise ValueError(f"unknown profile {profile!r}")
    p = profile.strip().upper()
    for base, cap in SHARE_MAX.items():
        if p in tuple(base + s for s in _PROFILE_SUFFIXES):
            return cap
    raise ValueError(f"unknown profile {profile!r}; expected NPM / VPM, optionally -OKS or -Ground")


# ---- geometry ---------------------------------------------------------------------------------------------------

def _unit(x):
    n = np.linalg.norm(x)
    return x / n if n > 0 else x


def _angle_deg(a, b) -> float:
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b))))


def _newell(points: np.ndarray) -> np.ndarray:
    """Twice the vector area of a polygon (Newell); its length / 2 is the area of a planar polygon."""
    nxt = np.roll(points, -1, axis=0)
    return np.cross(points, nxt).sum(axis=0)


def _mergeable(vx, tri_t, tri_u, edge, planar_deg) -> bool:
    """Do two triangles sharing `edge` form a convex planar quad?"""
    a, b = edge
    c = next(i for i in tri_t if i not in edge)
    d = next(i for i in tri_u if i not in edge)
    if c == d:
        return False
    pa, pb, pc, pd = vx[a], vx[b], vx[c], vx[d]
    n1 = np.cross(pb - pa, pc - pa)              # triangle (a, b, c)
    n2 = np.cross(pa - pb, pd - pb)              # triangle (b, a, d): same orientation as the quad a-d-b-c
    if np.linalg.norm(n1) / 2 <= AREA_EPS_M2 or np.linalg.norm(n2) / 2 <= AREA_EPS_M2:
        return False
    if _angle_deg(n1, n2) > planar_deg:
        return False
    loop = np.array([pa, pd, pb, pc])
    normal = _unit(_unit(n1) + _unit(n2))
    for i in range(4):
        prev, cur, nxt = loop[i - 1], loop[i], loop[(i + 1) % 4]
        if np.dot(np.cross(cur - prev, nxt - cur), normal) <= 0:
            return False
        if _angle_deg(prev - cur, nxt - cur) >= STRAIGHT_DEG:
            return False
    return True


def _fans(mesh: PolyMesh, edges, coplanar, planar_deg) -> dict:
    """centre vertex -> list of triangle ids of a qualifying closed fan (rule 3)."""
    vx, faces = mesh.vertices, mesh.faces
    around: dict[int, list[int]] = {}
    for f, face in enumerate(faces):
        for i in face:
            around.setdefault(i, []).append(f)
    out = {}
    for c, inc in around.items():
        k = len(inc)
        if k < 3 or any(len(faces[f]) != 3 for f in inc):
            continue
        rim: dict[int, list[int]] = {}
        ok = True
        for f in inc:
            x, y = (i for i in faces[f] if i != c)
            rim.setdefault(x, []).append(y)
            rim.setdefault(y, []).append(x)
        spokes = [tuple(sorted((c, x))) for x in rim]
        if len(rim) != k or any(len(n) != 2 for n in rim.values()) \
                or any(len(edges.get(s, ())) != 2 for s in spokes):
            continue
        order = [next(iter(rim))]                 # walk the rim: one cycle through all k rim vertices
        prev = None
        while True:
            nxt = [n for n in rim[order[-1]] if n != prev]
            prev = order[-1]
            if not nxt:                           # both rim neighbours are one vertex: duplicate triangles
                ok = False
                break
            if nxt[0] == order[0]:
                break
            order.append(nxt[0])
            if len(order) > k:
                ok = False
                break
        if not ok or len(order) != k:
            continue
        flat = all(coplanar(f, g) for f in inc for g in inc if f < g)
        if flat:
            pts = vx[order]
            corners = sum(_angle_deg(pts[i - 1] - pts[i], pts[(i + 1) % k] - pts[i]) < STRAIGHT_DEG
                          for i in range(k))
            if corners >= POLE_CAP_MIN_CORNERS:
                out[c] = inc
        elif k == 3 or k >= 5:
            out[c] = inc
    return out


def classify_faces(mesh: PolyMesh, allowed: bool = False, planar_deg: float = PLANAR_DEG) -> list:
    """One label per face: quad, ngon, degenerate, mergeable, needed:<reason> or unneeded (module docstring)."""
    if not (np.isfinite(planar_deg) and 0 <= planar_deg < 90):
        raise ValueError("planar_deg must be in [0, 90)")
    vx, faces = mesh.vertices, mesh.faces
    m = len(faces)
    vec = [_newell(vx[list(f)]) for f in faces]
    area = np.array([np.linalg.norm(n) / 2 for n in vec])
    unit = [_unit(n) for n in vec]
    good = area > AREA_EPS_M2

    edges: dict[tuple, list[int]] = {}
    for f, face in enumerate(faces):
        for i in range(len(face)):
            edges.setdefault(tuple(sorted((face[i], face[(i + 1) % len(face)]))), []).append(f)

    def coplanar(f, g):
        if not (good[f] and good[g]):
            return False
        return _angle_deg(unit[f], unit[g]) <= planar_deg or _angle_deg(unit[f], -unit[g]) <= planar_deg

    # coplanar patches (union-find over manifold edges) and the parity of each patch outline
    root = list(range(m))

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    inner = set()
    for e, fs in edges.items():
        if len(fs) == 2 and coplanar(*fs):
            inner.add(e)
            root[find(fs[0])] = find(fs[1])
    outline: dict[int, int] = {}
    for f, face in enumerate(faces):
        r = find(f)
        outline[r] = outline.get(r, 0) + sum(tuple(sorted((face[i], face[(i + 1) % len(face)]))) not in inner
                                             for i in range(len(face)))

    fans = _fans(mesh, edges, coplanar, planar_deg)
    in_fan = {f for inc in fans.values() for f in inc}
    spokes = {tuple(sorted((c, x))) for c, inc in fans.items() for f in inc for x in faces[f] if x != c}

    labels = []
    budget = {r: n % 2 for r, n in outline.items()}
    for f, face in enumerate(faces):
        if not good[f]:
            labels.append("degenerate")
            continue
        if len(face) > 4:
            labels.append("ngon")
            continue
        if len(face) == 4:
            labels.append("quad")
            continue
        fedges = [tuple(sorted((face[i], face[(i + 1) % 3]))) for i in range(3)]
        partner = None
        for e in fedges:
            fs = edges[e]
            if len(fs) != 2 or e in spokes:
                continue
            g = fs[0] if fs[1] == f else fs[1]
            if len(faces[g]) == 3 and good[g] and _mergeable(vx, face, faces[g], e, planar_deg):
                partner = g
                break
        if partner is not None:
            labels.append("mergeable")
            continue
        r = find(f)
        if budget[r] and any(e not in inner for e in fedges):
            budget[r] = 0
            labels.append("needed:odd_boundary")
        elif f in in_fan:
            labels.append("needed:pole_fan")
        elif allowed:
            labels.append("needed:parts_list")
        else:
            labels.append("unneeded")
    return labels


# ---- the invariant ----------------------------------------------------------------------------------------------

def _offender_text(part, f, label, mesh):
    if label == "ngon":
        return f"{part}#{f}: ngon ({len(mesh.faces[f])} sides)"
    if label == "degenerate":
        return f"{part}#{f}: degenerate (zero area)"
    return f"{part}#{f}: {label}"


def part_report(part: str, mesh: PolyMesh, profile: str, allowed: bool = False,
                planar_deg: float = PLANAR_DEG) -> PartQuadReport:
    """Faces, triangles, quads, n-gons, shares, needed-by-reason counts and every offender of one part."""
    cap = share_max(profile)
    labels = classify_faces(mesh, allowed, planar_deg)
    n = len(labels)
    tris = sum(len(f) == 3 for f in mesh.faces)
    needed: dict[str, int] = {}
    for lab in labels:
        if lab.startswith("needed:"):
            key = lab.split(":", 1)[1]
            needed[key] = needed.get(key, 0) + 1
    offenders = [_offender_text(part, f, lab, mesh) for f, lab in enumerate(labels) if lab in OFFENDING]
    needed_share = sum(needed.values()) / n if n else 0.0
    if not n:
        offenders.append(f"{part}: no faces")
    elif not allowed and needed_share > cap + 1e-12:
        offenders.append(f"{part}: needed-triangle share {needed_share:.1%} > {cap:.1%} ({profile})")
    return PartQuadReport(part, n, tris, sum(len(f) == 4 for f in mesh.faces), sum(len(f) > 4 for f in mesh.faces),
                          tris / n if n else 0.0, needed_share, None if allowed else cap, needed, tuple(offenders))


def quad_report(scene: PolyScene, profile: str, parts: Iterable[str] | None = None,
                allow_triangles: Iterable[str] = frozenset(), planar_deg: float = PLANAR_DEG) -> dict:
    """part id -> PartQuadReport for `parts` (None = every part of the scene)."""
    share_max(profile)
    names = list(scene if parts is None else parts)
    missing = [p for p in names if p not in scene]
    if missing:
        raise ValueError(f"parts not in the scene: {missing}")
    allow = frozenset(allow_triangles)
    return {p: part_report(p, scene[p], profile, p in allow, planar_deg) for p in names}


def quad_dominance(scene: PolyScene, profile: str, parts: Iterable[str] | None = None,
                   allow_triangles: Iterable[str] = frozenset(), planar_deg: float = PLANAR_DEG) -> InvariantResult:
    """The invariant over `parts` (None = all); no part to check is a failure, never a vacuous pass."""
    reports = quad_report(scene, profile, parts, allow_triangles, planar_deg)
    if not reports:
        return InvariantResult(NAME, False, 1, ("no parts to check",))
    offenders = [o for r in reports.values() for o in r.offenders]
    return InvariantResult(NAME, not offenders, len(offenders), tuple(offenders[:5]))


def check_operation_quads(report: InvariantReport, after_polys: PolyScene, changed: Iterable[str], profile: str,
                          allow_triangles: Iterable[str] = frozenset(),
                          planar_deg: float = PLANAR_DEG) -> InvariantReport:
    """`check_operation`'s report followed by quad_dominance over the changed parts; earlier results unchanged."""
    if any(r.name == NAME for r in report.results):
        raise ValueError("the report already has a quad_dominance result")
    changed = list(changed)
    missing = [p for p in changed if p not in after_polys]
    if missing:
        raise ValueError(f"changed parts without a polygon mesh: {missing}")
    result = quad_dominance(after_polys, profile, changed, allow_triangles, planar_deg)
    return InvariantReport(tuple(report.results) + (result,))
