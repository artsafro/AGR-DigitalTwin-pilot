"""Densify one named part so the file's UCX fits the [D012] budget, under the D108 invariants (#1537).

Why: the [D012] limit grows with the model (n >= 50 000 -> ceil(5 % n), capped at 100 000), so a file whose UCX
does not fit needs more model triangles. Session 0a21d4de (elv-tc-vpm, 2026-11-15) bisected edges of Main and
connected midpoints: SINTEZ then found 296 zero-area 3D faces and mirrored UV faces rose 375 -> 441, and a rerun with
one `connect_verts` call per pair took ~20 min. Artem: «Не увеличивай полигоны, чтобы там ничего не сбить»; his
practice is to detach an element (letters, a flat plate) and subdivide it.

`densify_for_ucx_budget(object, part, target_tris)`:
- `object` = every non-UCX part of the file (part name -> `UVPart`); `target_tris` = the UCX triangles the file must
  carry. It computes the needed model triangle count from [D012] (`needed_model_triangles`), then subdivides ONLY
  `part`: every triangle -> 4 at once (shared edge midpoints, per-corner UV and material id carried), repeated the
  fewest levels that reach the count. Bulk numpy, no per-edge or per-pair loop; the bmesh twin of one level is
  `bmesh.ops.subdivide_edges(bm, edges=<all edges of the part>, cuts=1, use_grid_fill=True)` [D110, D131].
- No part given -> it stops with the question which part to densify (candidates listed, Main never proposed).
  A part named Main (a case-insensitive `_`-separated token, ignoring a trailing `.NNN` DCC suffix) is refused
  unless the caller passes `allow_main=True`. MainGlass remains a detached-part candidate.
- `check_densify(before, after, part)` = the D108 invariants of this operation, relative to the source [D201]:
  no NEW degenerate 3D face, zero-area UV face, mirrored UV face or open (border) edge, part bbox and UV bounds
  unchanged, material ids kept, every other part untouched. A violator is pre-existing when it lies within `WELD_M`
  of a source violator (all corners of a face inside one source violating face; both ends of a border edge on one
  source border edge), so the children of a face that was already degenerate or mirrored are baseline, not new.
  A broken invariant rolls the operation back (the object comes back unchanged) with a question.
Out of scope: UCX generation, densifying in 3ds Max.
Pattern: new-case: kernel densify operation for the [D012] UCX budget (#1537).
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np

from dt_ai.geometry.ucx_build import ucx_triangle_limit
from dt_ai.ops.invariants import WELD_M, InvariantReport, InvariantResult, Mesh, border_edges

DEGENERATE_AREA_M2 = 1e-10   # 3D face area at or below this is degenerate («нулевая площадь 3D»)
UV_AREA_EPS = 1e-12          # |signed UV area| at or below this is a zero-area UV face; below -eps is mirrored
BOUNDS_TOL = 1e-9            # bbox / UV bounds must stay equal within this
MAX_LEVELS = 3               # 1 -> 64 triangles at most; more needs another part, asked of the user
UCX_CAP = 100_000            # [D012] cap
_PAIR_BLOCK = 2_000_000      # candidate pairs checked per numpy block
_GRID_CELLS_MAX = 20_000_000


@dataclass(frozen=True)
class UVPart:
    """A part: triangle mesh in metres + per-corner UV (m, 3, 2) + optional per-face material ids (m,)."""
    mesh: Mesh
    uv: np.ndarray
    material_ids: np.ndarray | None = None

    def __post_init__(self):
        uv = np.asarray(self.uv, dtype=float)
        m = len(self.mesh.triangles)
        if uv.shape != (m, 3, 2):
            raise ValueError(f"uv must be (faces, 3, 2) = ({m}, 3, 2), got {uv.shape}")
        if not np.isfinite(uv).all():
            raise ValueError("uv must be finite")
        object.__setattr__(self, "uv", uv)
        if self.material_ids is not None:
            ids = np.asarray(self.material_ids)
            if ids.shape != (m,) or not np.issubdtype(ids.dtype, np.integer):
                raise ValueError(f"material_ids must be ({m},) integers")
            object.__setattr__(self, "material_ids", ids)


ObjectParts = dict  # part name -> UVPart (non-UCX parts of one file)


@dataclass(frozen=True)
class DensifyResult:
    applied: bool
    part: str | None
    object: dict                      # the densified object when applied, else the one that came in (same object)
    report: InvariantReport | None    # None when it stopped before any geometry changed
    question: str | None = None       # why it stopped or rolled back, for the user
    notes: dict | None = None


# ---- [D012] -------------------------------------------------------------------------------------------------------

def needed_model_triangles(model_triangles: int, ucx_triangles: int) -> int:
    """Smallest n >= model_triangles with ucx_triangles <= limit(n) [D012]; model_triangles when it already fits.

    Raises ValueError when no n fits (UCX above the 100 000 cap)."""
    n, u = _count(model_triangles, "model_triangles", 0), _count(ucx_triangles, "ucx_triangles", 1)
    if u <= ucx_triangle_limit(n):
        return n
    if u > UCX_CAP:
        raise ValueError(f"UCX {u} triangles exceed the [D012] cap {UCX_CAP}: no model density fits")
    need = max(n, 50_000, 20 * (u - 1) + 1)
    while ucx_triangle_limit(need) < u:   # float guard of ceil(5 %); runs at most a step or two
        need += 1
    return need


def _count(value, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {value!r}")
    return int(value)


# ---- measures -----------------------------------------------------------------------------------------------------

def face_areas(mesh: Mesh) -> np.ndarray:
    c = mesh.corners()
    return 0.5 * np.linalg.norm(np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]), axis=1)


def uv_signed_areas(uv: np.ndarray) -> np.ndarray:
    d1, d2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    return 0.5 * (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])


def _violators(p: UVPart) -> dict:
    a, s = face_areas(p.mesh), uv_signed_areas(p.uv)
    return {"degenerate_3d_faces": a <= DEGENERATE_AREA_M2,
            "uv_zero_area_faces": np.abs(s) <= UV_AREA_EPS,
            "uv_mirrored_faces": s < -UV_AREA_EPS}


# ---- "lies on a source violator": AABB grid, exact distance on candidates ----------------------------------------

def _point_triangle_distance(p: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """Pairwise (K) distance of p[k] to triangle tri[k]; a degenerate triangle (a segment) uses its edges only."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    d = np.full(len(p), np.inf)
    for s, e in ((a, b), (b, c), (c, a)):
        se = e - s
        t = np.clip(((p - s) * se).sum(1) / np.maximum((se * se).sum(1), 1e-30), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(p - (s + t[:, None] * se), axis=1))
    n = np.cross(b - a, c - a)
    nn = (n * n).sum(1)
    ok = nn > 1e-30
    if ok.any():
        n_, a_, b_, c_, p_ = n[ok], a[ok], b[ok], c[ok], p[ok]
        dist = ((p_ - a_) * n_).sum(1) / np.sqrt(nn[ok])
        q = p_ - dist[:, None] * n_ / np.sqrt(nn[ok])[:, None]
        inside = ((np.cross(b_ - a_, q - a_) * n_).sum(1) >= 0) & ((np.cross(c_ - b_, q - b_) * n_).sum(1) >= 0) \
            & ((np.cross(a_ - c_, q - c_) * n_).sum(1) >= 0)
        sub = d[ok]
        sub[inside] = np.minimum(sub[inside], np.abs(dist[inside]))
        d[ok] = sub
    return d


def _covered(items: np.ndarray, base: np.ndarray, tol: float = WELD_M) -> np.ndarray:
    """Mask of items (P, k, 3) whose k points ALL lie within tol of ONE base triangle (S, 3, 3).

    Candidates come from a grid: each base triangle is registered in every cell its tol-expanded AABB touches; an
    item's first point within tol of a triangle lies inside that box, so its cell holds the triangle. Exact distances
    decide. Linear in P + S for parts whose faces are of similar size."""
    P = len(items)
    if not P or not len(base):
        return np.zeros(P, dtype=bool)
    lo, hi = base.min(axis=1) - tol, base.max(axis=1) + tol
    h = max(float(np.percentile((hi - lo).max(axis=1), 90)), 64 * tol)
    while True:
        clo, chi = np.floor(lo / h).astype(np.int64), np.floor(hi / h).astype(np.int64)
        span = chi - clo + 1
        cells = span.prod(axis=1)
        if cells.sum() <= _GRID_CELLS_MAX:
            break
        h *= 2
    tri = np.repeat(np.arange(len(base)), cells)
    k = np.arange(len(tri)) - np.repeat(np.cumsum(cells) - cells, cells)
    sx, sy = span[tri, 0], span[tri, 1]
    cell = clo[tri] + np.stack([k % sx, (k // sx) % sy, k // (sx * sy)], axis=1)
    q = np.floor(items[:, 0] / h).astype(np.int64)
    origin = np.minimum(cell.min(axis=0), q.min(axis=0))
    dims = np.maximum(cell.max(axis=0), q.max(axis=0)) - origin + 1
    if float(dims[0]) * float(dims[1]) * float(dims[2]) >= 2.0 ** 62:
        raise ValueError("geometry too far apart for the invariant grid")

    def pack(c):
        c = c - origin
        return (c[:, 0] * dims[1] + c[:, 1]) * dims[2] + c[:, 2]

    keys = pack(cell)
    order = np.argsort(keys, kind="stable")
    keys, tri = keys[order], tri[order]
    qk = pack(q)
    start, end = np.searchsorted(keys, qk, "left"), np.searchsorted(keys, qk, "right")
    counts = end - start
    out = np.zeros(P, dtype=bool)
    item = np.repeat(np.arange(P), counts)
    pos = np.arange(len(item)) - np.repeat(np.cumsum(counts) - counts, counts) + np.repeat(start, counts)
    cand = tri[pos]
    for s in range(0, len(item), _PAIR_BLOCK):
        i, j = item[s:s + _PAIR_BLOCK], cand[s:s + _PAIR_BLOCK]
        ok = np.ones(len(i), dtype=bool)
        for corner in range(items.shape[1]):
            ok &= _point_triangle_distance(items[i, corner], base[j]) <= tol
        out[i[ok]] = True
    return out


# ---- the invariants of this operation [D108, D201] ----------------------------------------------------------------

def _named(prefix, items, mask):
    return [f"{prefix} {np.round(x.mean(axis=0), 4).tolist()}" for x in items[mask][:5]]


def check_densify(before: dict, after: dict, part: str) -> InvariantReport:
    """D108 invariants of a densify step on `part`, relative to the source [D201]; see the module docstring."""
    if part not in before or part not in after:
        raise ValueError(f"unknown part {part!r}")
    src, out = before[part], after[part]
    results = []
    touched = sorted(k for k in set(before) | set(after) if k != part and
                     (k not in before or k not in after or not _same(before[k], after[k])))
    results.append(InvariantResult("other_parts_unchanged", not touched, len(touched), tuple(touched[:5])))
    vb, va = _violators(src), _violators(out)
    cs, ca = src.mesh.corners(), out.mesh.corners()
    for name in ("degenerate_3d_faces", "uv_zero_area_faces", "uv_mirrored_faces"):
        new = va[name].copy()
        new[new] = ~_covered(ca[new], cs[vb[name]])
        off = _named("face at", ca, new)
        results.append(InvariantResult(name, not new.any(), int(new.sum()), tuple(off),
                                       baseline=int(vb[name].sum()), after=int(va[name].sum())))
    eb, ea = border_edges(src.mesh), border_edges(out.mesh)
    base = np.concatenate([eb, eb[:, 1:]], axis=1) if len(eb) else np.zeros((0, 3, 3))
    new_e = ~_covered(ea, base)
    results.append(InvariantResult("open_edges", not new_e.any(), int(new_e.sum()), tuple(_named("edge at", ea, new_e)),
                                   baseline=len(eb), after=len(ea)))
    for name, x, y in (("bbox_unchanged", cs.reshape(-1, 3), ca.reshape(-1, 3)),
                       ("uv_bounds_unchanged", src.uv.reshape(-1, 2), out.uv.reshape(-1, 2))):
        if not len(x) or not len(y):
            moved = [f"{name}: empty part"]
        else:
            dl, dh = np.abs(x.min(0) - y.min(0)).max(), np.abs(x.max(0) - y.max(0)).max()
            moved = [] if max(dl, dh) <= BOUNDS_TOL else [f"min moved {dl:.3g}, max moved {dh:.3g}"]
        results.append(InvariantResult(name, not moved, len(moved), tuple(moved)))
    ids_b = None if src.material_ids is None else set(np.unique(src.material_ids).tolist())
    ids_a = None if out.material_ids is None else set(np.unique(out.material_ids).tolist())
    lost = [] if ids_b == ids_a else [f"material ids {sorted(ids_b or [])} -> {sorted(ids_a or [])}"]
    results.append(InvariantResult("material_ids_kept", not lost, len(lost), tuple(lost)))
    return InvariantReport(tuple(results))


def _same(a: UVPart, b: UVPart) -> bool:
    if a is b:
        return True
    return (np.array_equal(a.mesh.vertices, b.mesh.vertices) and np.array_equal(a.mesh.triangles, b.mesh.triangles)
            and np.array_equal(a.uv, b.uv) and (a.material_ids is None) == (b.material_ids is None)
            and (a.material_ids is None or np.array_equal(a.material_ids, b.material_ids)))


# ---- the operation ------------------------------------------------------------------------------------------------

def subdivide(p: UVPart, levels: int = 1) -> UVPart:
    """Every triangle -> 4 through its edge midpoints, `levels` times; bulk numpy (one pass per level).

    Midpoints are shared by vertex-index pair, so neighbouring faces stay connected; UV and material ids are carried
    per corner / per face; the winding of each child is its parent's."""
    for _ in range(levels):
        v, t = p.mesh.vertices, p.mesh.triangles
        if not len(t):
            return p
        e = np.stack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]], axis=1).reshape(-1, 2)
        lo, hi = e.min(axis=1).astype(np.int64), e.max(axis=1).astype(np.int64)
        uniq, inv = np.unique(lo * len(v) + hi, return_inverse=True)
        mid = 0.5 * (v[uniq // len(v)] + v[uniq % len(v)])
        m = (len(v) + inv.reshape(-1, 3))
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        ab, bc, ca = m[:, 0], m[:, 1], m[:, 2]
        tris = np.stack([np.stack([a, ab, ca], 1), np.stack([ab, b, bc], 1),
                         np.stack([ca, bc, c], 1), np.stack([ab, bc, ca], 1)], axis=1).reshape(-1, 3)
        u0, u1, u2 = p.uv[:, 0], p.uv[:, 1], p.uv[:, 2]
        u01, u12, u20 = 0.5 * (u0 + u1), 0.5 * (u1 + u2), 0.5 * (u2 + u0)
        uv = np.stack([np.stack([u0, u01, u20], 1), np.stack([u01, u1, u12], 1),
                       np.stack([u20, u12, u2], 1), np.stack([u01, u12, u20], 1)], axis=1).reshape(-1, 3, 2)
        ids = None if p.material_ids is None else np.repeat(p.material_ids, 4)
        p = UVPart(Mesh(np.concatenate([v, mid]), tris), uv, ids)
    return p


def is_main(part: str) -> bool:
    """Recognise Main tokens regardless of case or a trailing DCC duplicate suffix (.NNN)."""
    name, dot, suffix = str(part).rpartition(".")
    if not (dot and len(suffix) == 3 and suffix.isascii() and suffix.isdecimal()):
        name = str(part)
    return "main" in name.casefold().split("_")


def _triangles(obj: dict) -> int:
    return sum(len(p.mesh.triangles) for p in obj.values())


def densify_for_ucx_budget(object: dict, part: str | None, target_tris: int, *, allow_main: bool = False,
                           max_levels: int = MAX_LEVELS) -> DensifyResult:
    """Subdivide only `part` until the file's UCX of `target_tris` triangles fits [D012]; see the module docstring."""
    if not isinstance(object, dict) or not object:
        raise ValueError("object must be a non-empty dict part name -> UVPart")
    for name, p in object.items():
        if str(name).upper().startswith("UCX_"):
            raise ValueError(f"part {name!r} is a UCX mesh: n of [D012] excludes UCX, pass model parts only")
        if not isinstance(p, UVPart):
            raise ValueError(f"part {name!r} is not a UVPart")
    target = _count(target_tris, "target_tris", 1)
    max_levels = _count(max_levels, "max_levels", 1)
    n = _triangles(object)
    limit = ucx_triangle_limit(n)
    notes = {"model_triangles": n, "ucx_triangles": target, "ucx_limit_before": limit}
    if target > UCX_CAP:
        return DensifyResult(False, part, object, None, f"UCX of {target} triangles exceed the [D012] cap {UCX_CAP}: "
                             "no densification fits; which UCX should be simplified?", notes)
    need = needed_model_triangles(n, target)
    notes.update(needed_model_triangles=need, add_triangles=need - n)
    if need == n:
        return DensifyResult(False, part, object, None, None, {**notes, "reason": "UCX already within the budget"})
    if part is None:
        cands = sorted(((k, len(p.mesh.triangles)) for k, p in object.items() if not is_main(k)),
                       key=lambda kv: -kv[1])
        listed = ", ".join(f"{k} ({m} tris)" for k, m in cands) or "none (only Main; detach a part first)"
        return DensifyResult(False, None, object, None,
                             f"which part should be densified? The model needs {need - n} more triangles "
                             f"({n} -> {need}) for {target} UCX triangles [D012]; detached parts: {listed}. "
                             "Main is never densified automatically.", notes)
    if part not in object:
        raise ValueError(f"unknown part {part!r}")
    if is_main(part) and not allow_main:
        return DensifyResult(False, part, object, None,
                             f"{part} is Main: Main is never densified automatically; detach a part (letters, a flat "
                             "plate) and densify it, or confirm Main explicitly (allow_main=True)?", notes)
    m = len(object[part].mesh.triangles)
    if not m:
        return DensifyResult(False, part, object, None, f"{part} has no faces; which part should be densified?", notes)
    levels = next((lv for lv in range(1, max_levels + 1) if m * (4 ** lv - 1) >= need - n), None)
    if levels is None:
        return DensifyResult(False, part, object, None,
                             f"{part} has {m} triangles: {max_levels} subdivision levels add {m * (4 ** max_levels - 1)}"
                             f" of the {need - n} needed; which other part should be densified as well?", notes)
    t0 = time.perf_counter()
    dense = subdivide(object[part], levels)
    after = {**object, part: dense}
    report = check_densify(object, after, part)
    n_after = _triangles(after)
    notes.update(levels=levels, faces_before=m, faces_after=len(dense.mesh.triangles), model_triangles_after=n_after,
                 ucx_limit_after=ucx_triangle_limit(n_after), seconds=round(time.perf_counter() - t0, 3))
    if not report.passed:
        broken = "; ".join(f"{r.name} ({r.count}): {r.offenders[0] if r.offenders else ''}" for r in report.broken)
        return DensifyResult(False, part, object, report,
                             f"densify on {part} broke the invariants and was rolled back: {broken}; "
                             "which other part should be densified?", notes)
    if ucx_triangle_limit(n_after) < target:   # cannot happen when need is right; fail closed anyway
        return DensifyResult(False, part, object, report, f"after densifying {part} the budget "
                             f"{ucx_triangle_limit(n_after)} is still below {target}; which part next?", notes)
    return DensifyResult(True, part, after, report, None, notes)
