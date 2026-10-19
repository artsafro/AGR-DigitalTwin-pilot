"""Shared UCX collision builder for the Main and Ground targets (reg p.36-37 §13; docs/domain/areas/ucx.md).

Pattern: none - generalises the job-local KPP1 / PSU275 `vpm_ucx.py` hand-placed boxes into one tool
(REVIEW_CHECKLIST Q1: new-case: UCX construction from an accepted mesh, Main + Ground).

numpy only (no bpy), so the same code runs inside Blender (`tools/blender/ucx_build.py`) and under pytest.
Input is a triangle mesh in world metres (`verts` (N, 3), `tris` (M, 3)); output is a list of convex,
closed, triangulated pieces with 8 vertices / 12 triangles each (the primitive of 350 of 354 delivered
pieces, docs/research/ucx-etalon-analysis.md), no UV and no material slots by construction.

Main (OKS): the mesh is rotated into its dominant facade frame (pieces follow the facade, analysis rule 2),
its surface is voxelised conservatively (`cell` metres), the exterior is flood-filled from the padded grid
border so courtyards and passages wider than a cell stay open, and the solid cells are merged greedily
into boxes. Every box is shrunk by gap/2 per side, so two pieces are always at least `gap` apart in the
facade frame: no intersection and no touch (R09) by construction, gap inside the [D098] band (R10).
Every surface point lies in a solid cell, so the Main -> UCX deviation is at most the gap/2 shrink plus
the sampling spacing; an exposed UCX face belongs to a cell crossed by the surface, so UCX -> Main is at
most one cell diagonal. When the boxes exceed the [D012] triangle budget the cell grows and the build
repeats; a build that still exceeds it raises (fail closed).

Ground: quadtree over the surface plan; a cell becomes one hexahedron whose top is the upper envelope of
its four corner heights and whose bottom is `depth` below the lowest sample. A cell splits until the
vertical deviation between surface samples and the top is <= `tol` (R11: 10 cm) or `min_cell` is reached;
the achieved maximum is returned, never hidden. Pieces are shrunk by gap/2 in plan.

Thin-element exclusion (R04), target inventory (R01-R03) and stair shape (R14) are the caller's choice of
input objects; this module does not classify them.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

TARGETS = ("Main", "Ground")
GAP_M = 0.004  # analysis rule 4: 3-6 mm keeps float32 read-back inside the [D098] band 2 mm - 1 cm
GAP_BAND_M = (0.002, 0.01)
GAP_BUILD_M = (0.003, 0.006)  # builder accepts only the analysis target band: a 2 mm or 1 cm gap may read back outside [D098]
GROUND_TOL_M = 0.10  # R11, reg p.36 §13.5
PEDESTRIAN_TOL_M = 0.30  # R12
OKS_TOL_M = 1.0  # R13
MAX_PIECES = 999  # reg p.34 §4.2: index 001..999
_ADDRESS = re.compile(r"^[A-Za-z0-9_]+$")

# hexahedron: corners 0-3 bottom (x0y0, x1y0, x1y1, x0y1), 4-7 the same on top
_BOX_TRIS = np.array([
    (0, 2, 1), (0, 3, 2),  # bottom, normal -z
    (4, 5, 6), (4, 6, 7),  # top, normal +z
    (0, 1, 5), (0, 5, 4),  # y0
    (1, 2, 6), (1, 6, 5),  # x1
    (2, 3, 7), (2, 7, 6),  # y1
    (3, 0, 4), (3, 4, 7),  # x0
], dtype=np.int64)


class UcxBuildError(ValueError):
    """The input cannot give a valid UCX (empty, non-finite, over budget, too many pieces)."""


@dataclass
class Piece:
    verts: np.ndarray  # (8, 3) world metres
    tris: np.ndarray  # (12, 3)
    label: str = ""


@dataclass
class UcxResult:
    target: str
    pieces: list[Piece]
    cell_m: float
    gap_m: float
    angle_deg: float = 0.0
    budget: int | None = None  # triangles available to this build = file limit - reserved_triangles
    reserved_triangles: int = 0  # kept UCX of the same file counted against [D012]
    attempts: list[dict] = field(default_factory=list)
    max_vertical_dev_m: float | None = None  # Ground only: exact max |surface z - piece top|
    tol_m: float | None = None  # Ground only: requested vertical tolerance
    boxes_frame: np.ndarray | None = None  # Main only: (K, 2, 3) lo/hi in the facade frame
    footprint_overhang_bound_m: float | None = None  # Ground only: plan bound of a piece top over no surface
    uncovered_strip_m: float | None = None  # Ground only: widest covered strip left without a piece

    @property
    def within_tol(self) -> bool:
        """Ground: the exact vertical deviation, the footprint overhang bound and the uncovered strip are all
        within `tol_m` (a missing value fails); Main: always True (bounded by construction)."""
        if self.target != "Ground":
            return True
        vals = (self.max_vertical_dev_m, self.footprint_overhang_bound_m, self.uncovered_strip_m)
        return self.tol_m is not None and all(v is not None and v <= self.tol_m for v in vals)

    @property
    def triangles(self) -> int:
        return sum(len(p.tris) for p in self.pieces)


def ucx_triangle_limit(model_triangles: int) -> int:
    """[D012] budget, n excludes UCX: n < 50 000 -> 15 000, else min(ceil(5 % n), 100 000)."""
    if model_triangles < 50000:
        return 15000
    return min(math.ceil(model_triangles * 0.05), 100000)


def _reserved(value) -> int:
    """Triangles of UCX already in the file and kept (other targets/addresses): a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
        raise UcxBuildError(f"reserved_triangles must be a non-negative integer, got {value!r}")
    return int(value)


def file_budget_available(model_triangles: int, kept_triangles: int) -> int:
    """[D012] is a whole-file limit: triangles left for new UCX after the kept UCX. Fails when no
    single box (12 tris) fits."""
    limit = ucx_triangle_limit(int(model_triangles))
    free = limit - _reserved(kept_triangles)
    if free < 12:
        raise UcxBuildError(f"kept UCX {kept_triangles} tris leave {free} of the file budget {limit}; "
                            "no box fits")
    return free


def check_file_budget(model_triangles: int, ucx_triangles: int) -> None:
    """All UCX of the file (kept + new) must stay within the [D012] limit; checked before export."""
    limit = ucx_triangle_limit(int(model_triangles))
    if _reserved(ucx_triangles) > limit:
        raise UcxBuildError(f"file UCX {ucx_triangles} tris exceed the budget {limit}")


def ucx_names(address: str, target: str, count: int) -> list[str]:
    """UCX_SM_{Address}_{Main|Ground}_{001..999} (reg p.34 §4.2, R08), contiguous from 001."""
    if target not in TARGETS:
        raise UcxBuildError(f"target must be one of {TARGETS}, got {target!r}")
    if not address or not _ADDRESS.match(address):
        raise UcxBuildError(f"address must be A-Z a-z 0-9 _ only, got {address!r}")
    if not 1 <= count <= MAX_PIECES:
        raise UcxBuildError(f"piece count {count} outside 1..{MAX_PIECES}")
    return [f"UCX_SM_{address}_{target}_{k:03d}" for k in range(1, count + 1)]


def select_inputs(names, target: str, object: str | None = None, with_=None) -> tuple[str, list[str], str]:
    """Resolve the build inputs among the scene's non-UCX mesh names, independent of their order.

    Returns (target object, extra objects in the requested order, address). The target object is `object`
    or the single `SM_<Address>_<Target>`; every requested extra must exist exactly once, differ from the
    target object and not be a UCX; anything else raises before a build or a write."""
    if target not in TARGETS:
        raise UcxBuildError(f"target must be one of {TARGETS}, got {target!r}")
    names = list(names)
    if object is not None:
        cand = [n for n in names if n == object]
    else:
        cand = [n for n in names if n.startswith("SM_") and n.endswith("_" + target)]
    if len(cand) != 1:
        raise UcxBuildError(f"need exactly one {target} object{f' named {object!r}' if object else ''}, found {cand}")
    main = cand[0]
    extra = list(with_ or [])
    bad = [n for n in extra if not n or n.upper().startswith("UCX") or n == main]
    missing = [n for n in extra if n not in names]
    if bad or missing or len(set(extra)) != len(extra):
        raise UcxBuildError(f"bad extra objects {extra}: invalid {bad}, missing {missing}")
    sfx = "_" + target
    address = main[3:-len(sfx)] if main.startswith("SM_") and main.endswith(sfx) else main
    return main, extra, address


_UCX_OWNED = re.compile(r"^UCX_(.+)_(\d{3})(\.\d+)?$", re.IGNORECASE)


def ucx_replace_plan(ucx_names, input_names, model_names) -> tuple[list[str], list[str]]:
    """Split the scene's UCX into (replaced, kept): a UCX named `UCX_<object>_NNN` is replaced when <object>
    is one of the build inputs and kept when it is another model object (e.g. the Ground collision during a
    Main rebuild). A UCX that names no model object cannot be attributed to a target and is refused."""
    inputs, model = set(input_names), set(model_names)
    replace, keep, orphan = [], [], []
    for n in ucx_names:
        m = _UCX_OWNED.match(n)
        owner = m.group(1) if m and n[:4] == "UCX_" else None
        (replace if owner in inputs else keep if owner in model else orphan).append(n)
    if orphan:
        raise UcxBuildError(f"UCX not attributable to a model object (UCX_<object>_NNN): {orphan}")
    return replace, keep


def _check_mesh(verts, tris) -> tuple[np.ndarray, np.ndarray]:
    v = np.asarray(verts, dtype=float).reshape(-1, 3)
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    if len(v) == 0 or len(t) == 0:
        raise UcxBuildError("empty mesh")
    if not np.isfinite(v).all():
        raise UcxBuildError("mesh has NaN/inf coordinates")
    if t.min() < 0 or t.max() >= len(v):
        raise UcxBuildError("triangle index out of range")
    area = 0.5 * np.linalg.norm(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]), axis=1)
    if area.sum() <= 1e-9:
        raise UcxBuildError("mesh has zero surface area")
    return v, t


def _positive(name, value):
    if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
        raise UcxBuildError(f"{name} must be a finite positive number, got {value!r}")


def facade_angle(verts, tris) -> float:
    """Dominant facade direction (degrees, -45..45): area-weighted 4-fold circular mean of the plan
    normals of near-vertical faces. 0 when the mesh has no vertical faces."""
    v, t = np.asarray(verts, float), np.asarray(tris, np.int64)
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    a = np.linalg.norm(n, axis=1)
    ok = a > 1e-12
    n, a = n[ok] / a[ok, None], a[ok]
    vert = np.abs(n[:, 2]) < 0.2
    if not vert.any():
        return 0.0
    phi = np.arctan2(n[vert, 1], n[vert, 0])
    w = a[vert] * np.hypot(n[vert, 0], n[vert, 1])
    s, c = (w * np.sin(4 * phi)).sum(), (w * np.cos(4 * phi)).sum()
    if math.hypot(s, c) < 1e-9 * w.sum():
        return 0.0
    return math.degrees(math.atan2(s, c) / 4)


def _rot(angle_deg: float) -> np.ndarray:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def sample_surface(verts, tris, spacing: float) -> np.ndarray:
    """Deterministic points on every triangle, no two neighbours further apart than `spacing`."""
    v, t = np.asarray(verts, float), np.asarray(tris, np.int64)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    longest = np.max(np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1),
                               np.linalg.norm(a - c, axis=1)]), axis=0)
    steps = np.maximum(1, np.ceil(longest / spacing)).astype(np.int64)
    out = []
    for k in np.unique(steps):
        sel = steps == k
        ii, jj = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing="ij")
        keep = ii + jj <= k
        u, w = ii[keep] / k, jj[keep] / k  # barycentric grid
        pa, pb, pc = a[sel], b[sel], c[sel]
        pts = pa[:, None, :] + (pb - pa)[:, None, :] * u[None, :, None] + (pc - pa)[:, None, :] * w[None, :, None]
        out.append(pts.reshape(-1, 3))
    return np.concatenate(out)


def _flood_exterior(surface: np.ndarray) -> np.ndarray:
    """6-connected flood fill of empty cells from the grid border (the grid is padded by one empty cell)."""
    free = ~surface
    ext = np.zeros_like(surface)
    ext[0, :, :] = ext[-1, :, :] = True
    ext[:, 0, :] = ext[:, -1, :] = True
    ext[:, :, 0] = ext[:, :, -1] = True
    ext &= free
    while True:
        grow = ext.copy()
        grow[1:, :, :] |= ext[:-1, :, :]
        grow[:-1, :, :] |= ext[1:, :, :]
        grow[:, 1:, :] |= ext[:, :-1, :]
        grow[:, :-1, :] |= ext[:, 1:, :]
        grow[:, :, 1:] |= ext[:, :, :-1]
        grow[:, :, :-1] |= ext[:, :, 1:]
        grow &= free
        if np.array_equal(grow, ext):
            return ext
        ext = grow


def greedy_boxes(solid: np.ndarray, order=(2, 0, 1)) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """Cover the True cells exactly with disjoint boxes [lo, hi) in grid indices. `order` = axes extended
    first, second, third."""
    perm = (order[2], order[1], order[0])  # transposed axes: last one is extended first
    rem = np.transpose(solid, perm).copy()
    n0, n1, n2 = rem.shape
    boxes = []
    for a, b, c in np.argwhere(rem):
        if not rem[a, b, c]:
            continue
        c1 = c + 1
        while c1 < n2 and rem[a, b, c1]:
            c1 += 1
        b1 = b + 1
        while b1 < n1 and rem[a, b1, c:c1].all():
            b1 += 1
        a1 = a + 1
        while a1 < n0 and rem[a1, b:b1, c:c1].all():
            a1 += 1
        rem[a:a1, b:b1, c:c1] = False
        lo_t, hi_t = (a, b, c), (a1, b1, c1)
        lo, hi = [0, 0, 0], [0, 0, 0]
        for k, ax in enumerate(perm):
            lo[ax], hi[ax] = int(lo_t[k]), int(hi_t[k])
        boxes.append((tuple(lo), tuple(hi)))
    return boxes


def _main_boxes(v_frame: np.ndarray, t: np.ndarray, cell: float):
    pts = sample_surface(v_frame, t, cell / 2)
    origin = pts.min(axis=0) - cell
    dims = np.ceil((pts.max(axis=0) - origin) / cell).astype(np.int64) + 2
    if int(np.prod(dims)) > 60_000_000:
        raise UcxBuildError(f"voxel grid {dims.tolist()} too large for cell {cell} m")
    idx = np.clip(np.floor((pts - origin) / cell).astype(np.int64), 0, dims - 1)
    surface = np.zeros(tuple(dims), dtype=bool)
    surface[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    solid = ~_flood_exterior(surface)
    best = None
    for order in ((2, 0, 1), (0, 1, 2), (1, 0, 2)):
        b = greedy_boxes(solid, order)
        if best is None or len(b) < len(best):
            best = b
    return origin, best, pts


MIN_THICK_M = 0.05  # R04: a retracted piece never gets thinner than the thin-element limit


def _retract(lohi: np.ndarray, pts: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Pull every face that touches no other box back to the outermost surface sample inside the box.
    Only removes volume without surface samples, so Main -> UCX coverage is unchanged; faces in contact
    stay, so neighbour gaps are unchanged; boxes only shrink, so no new overlap can appear."""
    out = lohi.copy()
    lo, hi = lohi[:, 0, :], lohi[:, 1, :]
    k = len(lohi)
    contact = np.zeros((k, 3, 2), dtype=bool)
    for a in range(3):
        o1, o2 = [x for x in range(3) if x != a]
        ov = ((np.minimum(hi[:, None, o1], hi[None, :, o1]) - np.maximum(lo[:, None, o1], lo[None, :, o1]) > eps)
              & (np.minimum(hi[:, None, o2], hi[None, :, o2]) - np.maximum(lo[:, None, o2], lo[None, :, o2]) > eps))
        contact[:, a, 0] = (ov & (np.abs(lo[:, None, a] - hi[None, :, a]) <= eps)).any(axis=1)
        contact[:, a, 1] = (ov & (np.abs(hi[:, None, a] - lo[None, :, a]) <= eps)).any(axis=1)
    for i in range(k):
        if contact[i].all():
            continue
        m = ((pts >= lo[i] - eps) & (pts <= hi[i] + eps)).all(axis=1)
        if not m.any():
            continue
        pmin, pmax = pts[m].min(axis=0), pts[m].max(axis=0)
        for a in range(3):
            if not contact[i, a, 0]:
                out[i, 0, a] = min(max(lo[i, a], pmin[a]), out[i, 1, a] - MIN_THICK_M)
            if not contact[i, a, 1]:
                out[i, 1, a] = max(min(hi[i, a], pmax[a]), out[i, 0, a] + MIN_THICK_M)
            out[i, 0, a] = max(out[i, 0, a], lo[i, a])
            out[i, 1, a] = min(out[i, 1, a], hi[i, a])
    return out


def build_main(verts, tris, *, cell: float = 0.25, gap: float = GAP_M, model_triangles: int | None = None,
               angle_deg: float | None = None, grow: float = 1.25, max_attempts: int = 12,
               retract: bool = True, reserved_triangles: int = 0) -> UcxResult:
    """UCX for the Main (OKS) target. `model_triangles` = n of [D012] (all non-UCX triangles of the FBX;
    default: this mesh); `reserved_triangles` = kept UCX of the file, subtracted from the budget."""
    v, t = _check_mesh(verts, tris)
    _positive("cell", cell)
    _positive("gap", gap)
    if not GAP_BUILD_M[0] <= gap <= GAP_BUILD_M[1]:
        raise UcxBuildError(f"gap {gap} m outside the build band 3-6 mm (inside [D098] 2 mm - 1 cm)")
    if gap >= cell / 2:
        raise UcxBuildError("gap must be smaller than half a cell")
    reserved = _reserved(reserved_triangles)
    budget = file_budget_available(len(t) if model_triangles is None else int(model_triangles), reserved)
    angle = facade_angle(v, t) if angle_deg is None else float(angle_deg)
    r = _rot(-angle)  # world -> facade frame
    vf = v @ r.T
    attempts = []

    def run(c):
        origin, boxes, pts = _main_boxes(vf, t, c)
        attempts.append({"cell_m": round(c, 4), "pieces": len(boxes), "triangles": 12 * len(boxes)})
        return (origin, boxes, pts) if 12 * len(boxes) <= budget and len(boxes) <= MAX_PIECES else None

    c, bad = float(cell), None
    for _ in range(max_attempts):
        got = run(c)
        if got:
            break
        bad, c = c, c * grow
    else:
        raise UcxBuildError(f"no cell within {max_attempts} attempts meets budget {budget} / "
                            f"{MAX_PIECES} pieces: {attempts}")
    if bad is not None:  # bisect between the last failing and the first fitting cell (finer = closer)
        good = c
        for _ in range(3):
            mid = (bad + good) / 2
            trial = run(mid)
            if trial:
                good, got = mid, trial
            else:
                bad = mid
        c = good
    origin, boxes, pts = got
    raw = np.array([[origin + np.array(lo) * c, origin + np.array(hi) * c] for lo, hi in boxes])
    lohi = _retract(raw, pts) if retract else raw
    lohi = lohi + np.array([gap / 2, -gap / 2])[None, :, None]
    back = _rot(angle)
    pieces = []
    for lo, hi in lohi:
        corners = np.array([(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
                            (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])])
        pieces.append(Piece(corners @ back.T, _BOX_TRIS.copy()))
    return UcxResult("Main", pieces, c, gap, angle, budget, reserved, attempts, boxes_frame=lohi)


def main_deviation(points, result: UcxResult) -> np.ndarray:
    """Exact distance from each world point to the union of the Main boxes (0 inside)."""
    if result.target != "Main" or result.boxes_frame is None:
        raise UcxBuildError("main_deviation needs a Main result")
    p = np.asarray(points, float) @ _rot(-result.angle_deg).T
    lo, hi = result.boxes_frame[:, 0, :], result.boxes_frame[:, 1, :]
    out = np.full(len(p), np.inf)
    for s in range(0, len(p), 2000):
        q = p[s:s + 2000, None, :]
        d = np.maximum(np.maximum(lo[None] - q, 0.0), q - hi[None])
        out[s:s + 2000] = np.sqrt((d ** 2).sum(axis=2)).min(axis=1)
    return out


class HeightField:
    """Highest surface z above plan points (NaN where no triangle covers the point)."""

    def __init__(self, verts, tris, bucket: float | None = None):
        v, t = _check_mesh(verts, tris)
        self.v, self.t = v, t
        a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        self._a, self._e1, self._e2 = a, b - a, c - a
        det = self._e1[:, 0] * self._e2[:, 1] - self._e1[:, 1] * self._e2[:, 0]
        self._ok = np.abs(det) > 1e-12  # vertical triangles have no plan area
        self._det = np.where(self._ok, det, 1.0)
        lo = np.minimum(np.minimum(a, b), c)[:, :2]
        hi = np.maximum(np.maximum(a, b), c)[:, :2]
        self.lo, self.hi = v[:, :2].min(axis=0), v[:, :2].max(axis=0)
        span = max(float((self.hi - self.lo).max()), 1e-6)
        self.bucket = bucket or max(span / max(1.0, math.sqrt(len(t) / 4)), 1e-3)
        self._grid: dict[tuple[int, int], list[int]] = {}
        i0 = np.floor((lo - self.lo) / self.bucket).astype(int)
        i1 = np.floor((hi - self.lo) / self.bucket).astype(int)
        for k in np.flatnonzero(self._ok):
            for gx in range(i0[k, 0], i1[k, 0] + 1):
                for gy in range(i0[k, 1], i1[k, 1] + 1):
                    self._grid.setdefault((gx, gy), []).append(k)
        self._boundary()

    def _boundary(self):
        """Plan boundary of the covered region: an edge (vertices welded in plan, so a vertical cliff joins
        its top and bottom) is interior only when non-vertical triangles lie on both of its sides; every
        other edge is boundary. The covered region's boundary lies on these segments, so a rectangle that no
        boundary segment enters is either fully covered or fully uncovered (it is connected)."""
        v, t = self.v, self.t[self._ok]
        _, first, pid = np.unique(np.round(v[:, :2] / 1e-6).astype(np.int64), axis=0, return_index=True,
                                  return_inverse=True)
        pid = pid.reshape(-1)
        rows = []
        for i, j, k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
            a, b, c = v[t[:, i], :2], v[t[:, j], :2], v[t[:, k], :2]
            side = np.sign((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))
            pa, pb = pid[t[:, i]], pid[t[:, j]]
            side = np.where(pa < pb, side, -side).astype(np.int64)
            rows.append(np.stack([np.minimum(pa, pb), np.maximum(pa, pb), side], axis=1))
        e = np.concatenate(rows) if rows else np.zeros((0, 3), np.int64)
        e = e[e[:, 0] != e[:, 1]]
        seg = np.zeros((0, 2, 2))
        if len(e):
            key, inv = np.unique(e[:, :2], axis=0, return_inverse=True)
            inv = inv.reshape(-1)
            pos = np.bincount(inv, weights=(e[:, 2] > 0), minlength=len(key)) > 0
            neg = np.bincount(inv, weights=(e[:, 2] < 0), minlength=len(key)) > 0
            bk = key[~(pos & neg)]
            pxy = v[first, :2]
            seg = np.stack([pxy[bk[:, 0]], pxy[bk[:, 1]]], axis=1)
        self.bseg = seg
        self._bgrid: dict[tuple[int, int], list[int]] = {}
        if len(seg):
            i0 = np.floor((seg.min(axis=1) - self.lo) / self.bucket).astype(int)
            i1 = np.floor((seg.max(axis=1) - self.lo) / self.bucket).astype(int)
            for k in range(len(seg)):
                for gx in range(i0[k, 0], i1[k, 0] + 1):
                    for gy in range(i0[k, 1], i1[k, 1] + 1):
                        self._bgrid.setdefault((gx, gy), []).append(k)

    def _cands(self, grid, rect):
        x0, y0, x1, y1 = rect
        i0 = np.floor((np.array([x0, y0]) - self.lo) / self.bucket).astype(int)
        i1 = np.floor((np.array([x1, y1]) - self.lo) / self.bucket).astype(int)
        cand = set()
        for gx in range(i0[0], i1[0] + 1):
            for gy in range(i0[1], i1[1] + 1):
                cand.update(grid.get((gx, gy), ()))
        return np.fromiter(sorted(cand), int, len(cand))

    def boundary_in(self, rect, eps: float = 1e-9) -> np.ndarray:
        """Boundary segments that enter the open rectangle (x0, y0, x1, y1) (Liang-Barsky clip)."""
        k = self._cands(self._bgrid, rect)
        if not len(k):
            return np.zeros((0, 2, 2))
        seg = self.bseg[k]
        p0, d = seg[:, 0], seg[:, 1] - seg[:, 0]
        t0, t1 = np.zeros(len(seg)), np.ones(len(seg))
        out = np.zeros(len(seg), bool)
        x0, y0, x1, y1 = rect
        for ax, lo, hi in ((0, x0 + eps, x1 - eps), (1, y0 + eps, y1 - eps)):
            for pp, qq in ((-d[:, ax], p0[:, ax] - lo), (d[:, ax], hi - p0[:, ax])):
                par = np.abs(pp) < 1e-15
                out |= par & (qq <= 0)
                r = np.where(par, 0.0, qq / np.where(par, 1.0, pp))
                t0 = np.where(~par & (pp < 0), np.maximum(t0, r), t0)
                t1 = np.where(~par & (pp > 0), np.minimum(t1, r), t1)
        return seg[~out & (t0 < t1)]

    def covered_bbox(self, rect):
        """Exact bounding box of the covered plan region inside `rect` (triangles clipped to the rectangle,
        Sutherland-Hodgman); None when nothing of positive area is covered."""
        k = self._cands(self._grid, rect)
        x0, y0, x1, y1 = rect
        pts = []
        for tri in self.t[k]:
            poly = [tuple(self.v[i, :2]) for i in tri]
            for ax, lim, keep_lo in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
                nxt = []
                for m in range(len(poly)):
                    p, q = poly[m], poly[(m + 1) % len(poly)]
                    pin = p[ax] >= lim if keep_lo else p[ax] <= lim
                    qin = q[ax] >= lim if keep_lo else q[ax] <= lim
                    if pin:
                        nxt.append(p)
                    if pin != qin:
                        f = (lim - p[ax]) / (q[ax] - p[ax])
                        nxt.append((p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1])))
                poly = nxt
                if not poly:
                    break
            if len(poly) >= 3:
                a = np.array(poly)
                area = 0.5 * abs(np.dot(a[:, 0], np.roll(a[:, 1], -1)) - np.dot(a[:, 1], np.roll(a[:, 0], -1)))
                if area > 1e-12:
                    pts.append(a)
        if not pts:
            return None
        a = np.concatenate(pts)
        lo, hi = a.min(axis=0), a.max(axis=0)
        return (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))

    def crossings(self, segments) -> np.ndarray:
        """Plan points where mesh edges cross the given segments ((K, 2, 2) xy); with the surface vertices
        and the segment ends they are every vertex of the common refinement of the surface and a cell top,
        so the maximum of |surface - top| over a cell is attained among them (both are piecewise linear)."""
        seg = np.asarray(segments, float).reshape(-1, 2, 2)
        lo, hi = seg.reshape(-1, 2).min(axis=0), seg.reshape(-1, 2).max(axis=0)
        i0 = np.floor((lo - self.lo) / self.bucket).astype(int)
        i1 = np.floor((hi - self.lo) / self.bucket).astype(int)
        cand = set()
        for gx in range(i0[0], i1[0] + 1):
            for gy in range(i0[1], i1[1] + 1):
                cand.update(self._grid.get((gx, gy), ()))
        if not cand:
            return np.zeros((0, 2))
        tt = self.t[np.fromiter(cand, int)]
        e = np.concatenate([tt[:, [0, 1]], tt[:, [1, 2]], tt[:, [2, 0]]])
        e = np.unique(np.sort(e, axis=1), axis=0)
        p, r = self.v[e[:, 0], :2], self.v[e[:, 1], :2] - self.v[e[:, 0], :2]
        out = []
        for a, b in seg:
            s_ = b - a
            den = r[:, 0] * s_[1] - r[:, 1] * s_[0]
            ok = np.abs(den) > 1e-12
            d = a - p
            tq = np.where(ok, (d[:, 0] * s_[1] - d[:, 1] * s_[0]) / np.where(ok, den, 1), -1)
            uq = np.where(ok, (d[:, 0] * r[:, 1] - d[:, 1] * r[:, 0]) / np.where(ok, den, 1), -1)
            m = ok & (tq >= 0) & (tq <= 1) & (uq >= 0) & (uq <= 1)
            out.append(p[m] + r[m] * tq[m, None])
        return np.concatenate(out) if out else np.zeros((0, 2))

    def z(self, xy) -> np.ndarray:
        q = np.asarray(xy, float).reshape(-1, 2)
        out = np.full(len(q), np.nan)
        cell = np.floor((q - self.lo) / self.bucket).astype(int)
        keys = {}
        for i, key in enumerate(map(tuple, cell)):
            keys.setdefault(key, []).append(i)
        eps = 1e-9
        for key, rows in keys.items():
            cand = self._grid.get(key)
            if not cand:
                continue
            cand = np.asarray(cand)
            rows = np.asarray(rows)
            d = q[rows, None, :] - self._a[None, cand, :2]
            e1, e2, det = self._e1[cand], self._e2[cand], self._det[cand]
            u = (d[..., 0] * e2[None, :, 1] - d[..., 1] * e2[None, :, 0]) / det[None]
            w = (e1[None, :, 0] * d[..., 1] - e1[None, :, 1] * d[..., 0]) / det[None]
            inside = (u >= -eps) & (w >= -eps) & (u + w <= 1 + eps)
            zz = self._a[None, cand, 2] + u * e1[None, :, 2] + w * e2[None, :, 2]
            zz = np.where(inside, zz, -np.inf)
            best = zz.max(axis=1)
            out[rows] = np.where(np.isfinite(best), best, np.nan)
        return out


def _ground_top(corners_xy, h, xy):
    """Upper envelope of the 4 corner heights (convex top) evaluated at plan points `xy`."""
    (x0, y0), (x1, y1) = corners_xy[0], corners_xy[2]
    s = (xy[:, 0] - x0) / (x1 - x0)
    r = (xy[:, 1] - y0) / (y1 - y0)
    h0, h1, h2, h3 = h
    # diagonal 0-2: triangles (0,1,2) where s >= r, (0,2,3) where s < r
    d02 = np.where(s >= r, h0 + s * (h1 - h0) + r * (h2 - h1), h0 + r * (h3 - h0) + s * (h2 - h3))
    # diagonal 1-3: triangles (0,1,3) where s + r <= 1, (1,2,3) otherwise
    d13 = np.where(s + r <= 1, h0 + s * (h1 - h0) + r * (h3 - h0),
                   h2 + (1 - s) * (h3 - h2) + (1 - r) * (h1 - h2))
    return np.maximum(d02, d13), bool((h0 + h2) >= (h1 + h3))


def build_ground(verts, tris, *, cell: float = 16.0, min_cell: float = 0.5, tol: float = 0.08,
                 depth: float = 0.5, gap: float = GAP_M, samples: int = 6,
                 model_triangles: int | None = None, reserved_triangles: int = 0) -> UcxResult:
    """UCX for the Ground target: quadtree hexahedra over the surface heightfield."""
    for name, val in (("cell", cell), ("min_cell", min_cell), ("tol", tol), ("depth", depth), ("gap", gap)):
        _positive(name, val)
    if not GAP_BUILD_M[0] <= gap <= GAP_BUILD_M[1]:
        raise UcxBuildError(f"gap {gap} m outside the build band 3-6 mm (inside [D098] 2 mm - 1 cm)")
    if min_cell > cell or gap >= min_cell / 2:
        raise UcxBuildError("need gap < min_cell / 2 and min_cell <= cell")
    reserved = _reserved(reserved_triangles)
    hf = HeightField(verts, tris)
    budget = file_budget_available(len(hf.t) if model_triangles is None else int(model_triangles), reserved)
    lo, span = hf.lo, hf.hi - hf.lo
    if not (span > 2 * gap).all():
        raise UcxBuildError("ground surface has no plan area")
    n = np.maximum(1, np.ceil(span / cell)).astype(int)
    sx, sy = float(span[0] / n[0]), float(span[1] / n[1])  # grid fitted to the plan bbox: no cell sticks out
    stack = [(lo[0] + i * sx, lo[1] + j * sy, sx, sy, False) for i in range(n[0]) for j in range(n[1])]
    g = gap / 2
    pieces, devs, overs, strips = [], [], [], [0.0]
    lin = (np.arange(samples) + 0.5) / samples

    def split4(x, y, wx, wy):
        hx, hy = wx / 2, wy / 2
        stack.extend([(x, y, hx, hy, False), (x + hx, y, hx, hy, False), (x, y + hy, hx, hy, False),
                      (x + hx, y + hy, hx, hy, False)])

    while stack:
        x, y, wx, wy, final = stack.pop()
        can_split = not final and min(wx, wy) / 2 >= min_cell
        rect = (x + g, y + g, x + wx - g, y + wy - g)
        if rect[2] - rect[0] < gap or rect[3] - rect[1] < gap:  # a split strip too thin for a piece
            if hf.covered_bbox((x, y, x + wx, y + wy)) is not None:
                strips.append(min(wx, wy))
            continue
        bnd = hf.boundary_in(rect)
        overhang = 0.0
        if not len(bnd):  # fully covered or fully empty (exact, see HeightField._boundary)
            if not np.isfinite(hf.z(np.array([[(rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2]]))[0]):
                continue
        else:
            if can_split:
                split4(x, y, wx, wy)
                continue
            if not final:  # split at the boundary vertices: rectilinear coverage becomes exact
                e = 1e-7
                cx = sorted({round(float(q), 9) for q in bnd[:, :, 0].ravel() if x + e < q < x + wx - e})
                cy = sorted({round(float(q), 9) for q in bnd[:, :, 1].ravel() if y + e < q < y + wy - e})
                if cx or cy:
                    bx, by = [x, *cx, x + wx], [y, *cy, y + wy]
                    stack.extend((bx[a], by[b], bx[a + 1] - bx[a], by[b + 1] - by[b], True)
                                 for a in range(len(bx) - 1) for b in range(len(by) - 1))
                    continue
            bb = hf.covered_bbox(rect)
            if bb is None:
                continue
            if bb[2] - bb[0] < gap or bb[3] - bb[1] < gap:
                strips.append(min(wx, wy))
                continue
            rect = bb
            if len(hf.boundary_in(rect)):  # still partly uncovered: any top point is within the diagonal
                overhang = math.hypot(rect[2] - rect[0], rect[3] - rect[1])
        x0, y0, x1, y1 = rect
        corners = np.array([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
        h = hf.z(corners)
        gx, gy = np.meshgrid(x0 + lin * (x1 - x0), y0 + lin * (y1 - y0))
        grid = np.stack([gx.ravel(), gy.ravel()], axis=1)
        vx = hf.v
        inner = vx[(vx[:, 0] > x0) & (vx[:, 0] < x1) & (vx[:, 1] > y0) & (vx[:, 1] < y1)]
        edges = np.array([[corners[k], corners[(k + 1) % 4]] for k in range(4)] + [[corners[0], corners[2]],
                                                                                   [corners[1], corners[3]]])
        pts = np.concatenate([grid, corners, inner[:, :2], hf.crossings(edges)])
        zs = hf.z(pts)
        hit = np.isfinite(zs)
        if not hit.any():
            continue
        if np.isnan(h).any():  # only a partly covered (reported) piece has an uncovered corner
            h = np.where(np.isfinite(h), h, float(np.mean(zs[hit])))
        top, diag02 = _ground_top(corners, h, pts[hit])
        dev = float(np.max(np.abs(zs[hit] - top)))
        if dev > tol and can_split:
            split4(x, y, wx, wy)
            continue
        base = min(float(h.min()), float(np.min(zs[hit]))) - depth
        vv = np.array([(*corners[k], base) for k in range(4)] + [(*corners[k], h[k]) for k in range(4)])
        tr = _BOX_TRIS.copy()
        tr[2:4] = [(4, 5, 6), (4, 6, 7)] if diag02 else [(4, 5, 7), (5, 6, 7)]
        pieces.append(Piece(vv, tr))
        devs.append(dev)
        overs.append(overhang)
    if not pieces:
        raise UcxBuildError("ground surface has no plan area")
    if len(pieces) > MAX_PIECES or 12 * len(pieces) > budget:
        raise UcxBuildError(f"{len(pieces)} ground pieces exceed {MAX_PIECES} pieces or budget {budget}")
    pieces.sort(key=lambda p: (round(float(p.verts[0, 1]), 3), round(float(p.verts[0, 0]), 3)))
    return UcxResult("Ground", pieces, float(cell), gap, 0.0, budget, reserved,
                     [{"min_cell_m": min_cell, "tol_m": tol, "grid_m": [round(sx, 6), round(sy, 6)]}],
                     max_vertical_dev_m=max(devs), tol_m=tol,
                     footprint_overhang_bound_m=max(overs), uncovered_strip_m=max(strips))


def ground_deviation(points, result: UcxResult, margin: float | None = None) -> np.ndarray:
    """Vertical distance (an upper bound of the true distance) from each surface point to the top of the
    Ground piece below it; inf where no piece covers the point in plan. A point in the gap strip between
    pieces (within `margin`, default the gap) is compared with the nearest piece edge."""
    p = np.asarray(points, float)
    out = np.full(len(p), np.inf)
    for pc in result.pieces:
        lo, hi = pc.verts[:, :2].min(axis=0), pc.verts[:, :2].max(axis=0)
        e = result.gap_m if margin is None else margin
        sel = (p[:, 0] >= lo[0] - e) & (p[:, 0] <= hi[0] + e) & (p[:, 1] >= lo[1] - e) & (p[:, 1] <= hi[1] + e)
        if not sel.any():
            continue
        xy = np.clip(p[sel, :2], lo, hi)
        top, _ = _ground_top(pc.verts[:4, :2], pc.verts[4:, 2], xy)
        out[sel] = np.minimum(out[sel], np.abs(p[sel, 2] - top))
    return out


def build(target: str, verts, tris, **kw) -> UcxResult:
    """One entry point for job scripts: target 'Main' or 'Ground'."""
    if target == "Main":
        return build_main(verts, tris, **kw)
    if target == "Ground":
        return build_ground(verts, tris, **kw)
    raise UcxBuildError(f"target must be one of {TARGETS}, got {target!r}")
