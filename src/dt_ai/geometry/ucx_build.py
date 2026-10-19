"""Shared UCX collision builder for the Main and Ground targets (reg p.36-37 §13; docs/domain/areas/ucx.md).

Pattern: none - generalises the job-local KPP1 / PSU275 `vpm_ucx.py` hand-placed boxes into one tool
(REVIEW_CHECKLIST Q1: new-case: UCX construction from an accepted mesh, Main + Ground).

numpy only (no bpy), so the same code runs inside Blender (`tools/blender/ucx_build.py`) and under pytest.
Input is a triangle mesh in world metres (`verts` (N, 3), `tris` (M, 3)); output is a list of convex,
closed, triangulated pieces (Main: boxes with 8 vertices / 12 triangles, the
primitive of 350 of 354 delivered pieces, docs/research/ucx-etalon-analysis.md; Ground: prisms over convex
polygons), no UV and no material slots by construction.

Main (OKS): the mesh is rotated into its dominant facade frame (pieces follow the facade, analysis rule 2),
its surface is voxelised conservatively (`cell` metres), the exterior is flood-filled from the padded grid
border so courtyards and passages wider than a cell stay open, and the solid cells are merged greedily
into boxes. Every box is shrunk by gap/2 per side, so two pieces are always at least `gap` apart in the
facade frame: no intersection and no touch (R09) by construction, gap inside the [D098] band (R10).
Every surface point lies in a solid cell, so the Main -> UCX deviation is at most the gap/2 shrink plus
the sampling spacing; an exposed UCX face belongs to a cell crossed by the surface, so UCX -> Main is at
most one cell diagonal. When the boxes exceed the [D012] triangle budget the cell grows and the build
repeats; a build that still exceeds it raises (fail closed).

Ground (#326): binary space partition of the covered plan into convex prisms (2k vertices, 4k - 4
triangles over a convex k-gon) with planar tops. The covered-region outline (overlapping layer edges of a
method-C layered surface are not outline), steep-face traces and layer edges serve as cut lines; a leaf is
cut until its top is within `tol` of the surface envelope (R11: 10 cm) or `min_cell` is reached; the
achieved maximum is exact over the leaf and returned, never hidden. Pieces stay inside the covered plan
(voids stay open) and are shrunk by gap/2 per edge.
R11-R13 use one-sided model -> UCX deviation [D134]; exposed UCX -> model distance and Ground
footprint overhang are diagnostics only, not tolerance gates. Coverage and functional voids still apply.

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
    verts: np.ndarray  # (V, 3) world metres; Main: 8 (box), Ground: 2k (prism over a convex k-gon)
    tris: np.ndarray  # (2V - 4, 3)
    label: str = ""
    plan: np.ndarray | None = None  # Ground: convex CCW plan polygon (k, 2)
    plane: tuple | None = None  # Ground: planar top z = a x + b y + c


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
        """Ground: model -> UCX vertical deviation and uncovered strip within `tol_m`.
        Reverse footprint overhang is diagnostic only [D134]; Main is bounded by construction.
        """
        if self.target != "Ground":
            return True
        vals = (self.max_vertical_dev_m, self.uncovered_strip_m)
        return (self.tol_m is not None and math.isfinite(self.tol_m) and self.tol_m > 0
                and all(v is not None and math.isfinite(v) and 0 <= v <= self.tol_m for v in vals))

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

    def _cands(self, grid, rect):
        x0, y0, x1, y1 = rect
        i0 = np.floor((np.array([x0, y0]) - self.lo) / self.bucket).astype(int)
        i1 = np.floor((np.array([x1, y1]) - self.lo) / self.bucket).astype(int)
        cand = set()
        for gx in range(i0[0], i1[0] + 1):
            for gy in range(i0[1], i1[1] + 1):
                cand.update(grid.get((gx, gy), ()))
        return np.fromiter(sorted(cand), int, len(cand))

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

    def kinks(self, lo, hi) -> np.ndarray:
        """Plan points inside the box [lo, hi] where the upper envelope of a layered (overlapping, unwelded)
        surface can bend between mesh vertices: crossings of two triangle edges in plan and points where
        an edge pierces another triangle's plane inside that triangle. With the vertices and the boundary
        crossings they are the vertices of the envelope's arrangement, so the max of |envelope - plane| over
        a leaf is attained among them. Pairs sharing a vertex (one welded layer) bend nowhere new."""
        k = self._cands(self._grid, (lo[0], lo[1], hi[0], hi[1]))
        if len(k) < 2:
            return np.zeros((0, 2))
        tt = self.t[k]
        e = np.unique(np.sort(np.concatenate([tt[:, [0, 1]], tt[:, [1, 2]], tt[:, [2, 0]]]), axis=1), axis=0)
        p0, p1 = self.v[e[:, 0]], self.v[e[:, 1]]
        out = []
        r = p1[:, :2] - p0[:, :2]
        for s0 in range(0, len(e), 256):  # edge x edge crossings
            a, ra, ea = p0[s0:s0 + 256, None, :2], r[s0:s0 + 256, None], e[s0:s0 + 256, None]
            den = ra[..., 0] * r[None, :, 1] - ra[..., 1] * r[None, :, 0]
            d = p0[None, :, :2] - a
            ok = (np.abs(den) > 1e-12) & (ea[..., 0] != e[None, :, 0]) & (ea[..., 0] != e[None, :, 1]) \
                & (ea[..., 1] != e[None, :, 0]) & (ea[..., 1] != e[None, :, 1])
            dd = np.where(ok, den, 1.0)
            tq = (d[..., 0] * r[None, :, 1] - d[..., 1] * r[None, :, 0]) / dd
            uq = (d[..., 0] * ra[..., 1] - d[..., 1] * ra[..., 0]) / dd
            m = ok & (tq > 0) & (tq < 1) & (uq > 0) & (uq < 1)
            i, _ = np.nonzero(m)
            out.append((a[i, 0] + ra[i, 0] * tq[m][:, None]))
        a0, e1, e2, det, okt = self._a[k], self._e1[k], self._e2[k], self._det[k], self._ok[k]
        nrm = np.cross(e1, e2)
        for s0 in range(0, len(e), 256):  # edge x foreign triangle plane
            q0, q1, ee = p0[s0:s0 + 256, None], p1[s0:s0 + 256, None], e[s0:s0 + 256, None]
            f0 = ((q0 - a0[None]) * nrm[None]).sum(-1)
            f1 = ((q1 - a0[None]) * nrm[None]).sum(-1)
            den = f0 - f1
            ok = okt[None] & (np.abs(nrm[None, :, 2]) > 1e-12) & (np.abs(den) > 1e-15)
            s = np.where(ok, f0 / np.where(ok, den, 1.0), -1.0)
            pt = q0[..., :2] + s[..., None] * (q1[..., :2] - q0[..., :2])
            d = pt - a0[None, :, :2]
            u = (d[..., 0] * e2[None, :, 1] - d[..., 1] * e2[None, :, 0]) / det[None]
            w = (e1[None, :, 0] * d[..., 1] - e1[None, :, 1] * d[..., 0]) / det[None]
            shared = (tt[None, :, :] == ee[..., 0:1]).any(-1) | (tt[None, :, :] == ee[..., 1:2]).any(-1)
            m = ok & ~shared & (s > 0) & (s < 1) & (u > 0) & (w > 0) & (u + w < 1)
            out.append(pt[m])
        pts = np.concatenate(out) if out else np.zeros((0, 2))
        return pts[((pts >= np.asarray(lo)) & (pts <= np.asarray(hi))).all(axis=1)]

    def layer_crossings(self, segments) -> np.ndarray:
        """Plan points on the given segments where two triangles covering the point have equal height: the
        envelope of crossing layers bends there, also between mesh edges (completes `kinks` on a leaf
        boundary)."""
        out = []
        for a, b in np.asarray(segments, float).reshape(-1, 2, 2):
            k = self._cands(self._grid, (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
            k = k[self._ok[k]]
            if len(k) < 2:
                continue
            d0, d1 = a - self._a[k, :2], b - self._a[k, :2]
            e1, e2, det = self._e1[k], self._e2[k], self._det[k]

            def bary(d):
                return ((d[:, 0] * e2[:, 1] - d[:, 1] * e2[:, 0]) / det, (e1[:, 0] * d[:, 1] - e1[:, 1] * d[:, 0]) / det)

            (u0, w0), (u1, w1) = bary(d0), bary(d1)
            z0 = self._a[k, 2] + u0 * e1[:, 2] + w0 * e2[:, 2]
            z1 = self._a[k, 2] + u1 * e1[:, 2] + w1 * e2[:, 2]
            dz = z1 - z0
            den = dz[None, :] - dz[:, None]
            ok = np.abs(den) > 1e-12
            s = np.where(ok, (z0[:, None] - z0[None, :]) / np.where(ok, den, 1.0), -1.0)
            i, j = np.nonzero(ok & (s > 0) & (s < 1))
            if not len(i):
                continue
            ss = s[i, j]
            ui, wi = u0[i] + ss * (u1[i] - u0[i]), w0[i] + ss * (w1[i] - w0[i])
            uj, wj = u0[j] + ss * (u1[j] - u0[j]), w0[j] + ss * (w1[j] - w0[j])
            e = -1e-9
            m = (ui >= e) & (wi >= e) & (ui + wi <= 1 - e) & (uj >= e) & (wj >= e) & (uj + wj <= 1 - e)
            out.append(a[None] + ss[m, None] * (b - a)[None])
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


def _outline(hf: HeightField, probe: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """Plan outline of the covered region: the mesh boundary segments (HeightField.bseg) with coverage on
    exactly one side. A layered (method C) Ground has overlapping, unwelded surfacing layers whose own
    edges lie inside the covered region; they bound no void (#326) and are returned separately as
    (outline, internal layer edges): the upper surface may step there. Probed at 1/4, 1/2 and 3/4 of
    each segment, `probe` metres to either side."""
    s = hf.bseg
    if not len(s):
        return s, s
    d = s[:, 1] - s[:, 0]
    ln = np.linalg.norm(d, axis=1)
    nrm = np.stack([-d[:, 1], d[:, 0]], axis=1) / np.maximum(ln, 1e-12)[:, None]
    keep = np.zeros(len(s), bool)
    for f in (0.25, 0.5, 0.75):
        m = s[:, 0] + f * d
        keep |= np.isfinite(hf.z(m + probe * nrm)) != np.isfinite(hf.z(m - probe * nrm))
    return s[keep & (ln > 1e-9)], s[~keep & (ln > 1e-9)]


def _breaklines(hf: HeightField, rise: float, max_nz: float = 0.9) -> np.ndarray:
    """Plan traces of steep faces (kerbs, steps, embankments steeper than ~26 deg): every plan edge of a
    triangle with |n_z| < `max_nz` that rises more than `rise`. A Ground leaf whose planar top misses the
    surface is split along them, so creases and steps fall on piece borders instead of forcing tiny cells."""
    v, t = hf.v, hf.t
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    a = np.linalg.norm(n, axis=1)
    zs = v[t][:, :, 2]
    steep = (a > 1e-12) & (np.abs(n[:, 2]) < max_nz * np.maximum(a, 1e-12)) & (zs.max(1) - zs.min(1) > rise)
    tt = t[steep]
    e = np.unique(np.sort(np.concatenate([tt[:, [0, 1]], tt[:, [1, 2]], tt[:, [2, 0]]]), axis=1), axis=0)
    seg = np.stack([v[e[:, 0], :2], v[e[:, 1], :2]], axis=1) if len(e) else np.zeros((0, 2, 2))
    return seg[np.linalg.norm(seg[:, 1] - seg[:, 0], axis=1) > 1e-6]


class _SegIndex:
    """Bucket index of plan segments (K, 2, 2) for bbox queries."""

    def __init__(self, seg, lo, bucket):
        self.seg, self.lo, self.b = seg, lo, bucket
        self.grid: dict[tuple[int, int], list[int]] = {}
        if len(seg):
            i0 = np.floor((seg.min(axis=1) - lo) / bucket).astype(int)
            i1 = np.floor((seg.max(axis=1) - lo) / bucket).astype(int)
            for k in range(len(seg)):
                for gx in range(i0[k, 0], i1[k, 0] + 1):
                    for gy in range(i0[k, 1], i1[k, 1] + 1):
                        self.grid.setdefault((gx, gy), []).append(k)

    def query(self, lo, hi) -> np.ndarray:
        return self.seg[self.ids(lo, hi)]

    def ids(self, lo, hi) -> np.ndarray:
        i0 = np.floor((lo - self.lo) / self.b).astype(int)
        i1 = np.floor((hi - self.lo) / self.b).astype(int)
        cand = set()
        for gx in range(i0[0], i1[0] + 1):
            for gy in range(i0[1], i1[1] + 1):
                cand.update(self.grid.get((gx, gy), ()))
        return np.fromiter(sorted(cand), int, len(cand))


def _poly_area(p) -> float:
    if len(p) < 3:
        return 0.0
    return 0.5 * float(np.dot(p[:, 0], np.roll(p[:, 1], -1)) - np.dot(p[:, 1], np.roll(p[:, 0], -1)))


def _clip(p, n, c) -> np.ndarray:
    """Convex polygon `p` (CCW) cut to the half-plane n . x >= c."""
    out = []
    k = len(p)
    s = p @ n - c
    for i in range(k):
        j = (i + 1) % k
        if s[i] >= 0:
            out.append(p[i])
        if (s[i] >= 0) != (s[j] >= 0):
            f = s[i] / (s[i] - s[j])
            out.append(p[i] + f * (p[j] - p[i]))
    q = np.array(out, float).reshape(-1, 2)
    if len(q):  # drop repeated points (a cut through a vertex)
        keep = np.linalg.norm(q - np.roll(q, -1, axis=0), axis=1) > 1e-10
        q = q[keep]
    return q


def _half_planes(p):
    """Inward unit normals and offsets of a CCW convex polygon: inside <=> n . x >= c for every edge."""
    e = np.roll(p, -1, axis=0) - p
    ln = np.maximum(np.linalg.norm(e, axis=1), 1e-15)
    n = np.stack([-e[:, 1], e[:, 0]], axis=1) / ln[:, None]
    return n, np.einsum("ij,ij->i", n, p)


def _inset(p, d) -> np.ndarray:
    """Convex polygon shrunk by `d` on every edge (empty when nothing is left)."""
    n, c = _half_planes(p)
    q = p
    for k in range(len(p)):
        q = _clip(q, n[k], c[k] + d)
        if len(q) < 3:
            return np.zeros((0, 2))
    return q if _poly_area(q) > 1e-12 else np.zeros((0, 2))


def _min_width(p) -> float:
    """Minimum width of a convex polygon (smallest extent over its edge normals)."""
    n, _ = _half_planes(p)
    proj = p @ n.T
    return float((proj.max(axis=0) - proj.min(axis=0)).min())


def _segs_inside(seg, p, eps=1e-6) -> np.ndarray:
    """Parts of plan segments strictly inside convex polygon `p` (Cyrus-Beck, `eps` inset): a segment
    lying on the polygon boundary is not inside."""
    if not len(seg):
        return seg
    n, c = _half_planes(p)
    p0, d = seg[:, 0], seg[:, 1] - seg[:, 0]
    num = p0 @ n.T - (c + eps)[None]  # (S, E)
    den = d @ n.T
    t0, t1 = np.zeros(len(seg)), np.ones(len(seg))
    out = ((np.abs(den) < 1e-15) & (num < 0)).any(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = -num / den
    t0 = np.maximum(t0, np.where(den > 1e-15, r, -np.inf).max(axis=1))
    t1 = np.minimum(t1, np.where(den < -1e-15, r, np.inf).min(axis=1))
    ok = ~out & (t1 - t0 > 1e-9)
    return np.stack([p0[ok] + t0[ok, None] * d[ok], p0[ok] + t1[ok, None] * d[ok]], axis=1)


def _inside(p, xy, eps=0.0) -> np.ndarray:
    n, c = _half_planes(p)
    return (xy @ n.T >= c[None] - eps).all(axis=1)


def _simplify(q, h: float = 0.002) -> np.ndarray:
    """Drop vertices of convex CCW `q` that stand less than `h` above the chord of their neighbours (or
    close a shorter edge): the polygon only shrinks (stays inside the leaf), and its float32 read-back
    stays convex (#326: near-collinear BSP vertices read back as non-convex hulls)."""
    q = np.asarray(q, float)
    while len(q) > 3:
        a, b, c = np.roll(q, 1, axis=0), q, np.roll(q, -1, axis=0)
        ch = c - a
        ln = np.maximum(np.linalg.norm(ch, axis=1), 1e-15)
        ht = np.abs(ch[:, 0] * (b - a)[:, 1] - ch[:, 1] * (b - a)[:, 0]) / ln
        k = int(np.argmin(ht))
        if ht[k] >= h:
            break
        q = np.delete(q, k, axis=0)
    return q


_NUDGE = 1e-5 * np.stack([np.cos(np.arange(6) * np.pi / 3), np.sin(np.arange(6) * np.pi / 3)], axis=1)


def _prism(q, plane, base) -> Piece:
    """Closed convex prism over the convex CCW plan `q` (k vertices): planar top a x + b y + c, flat bottom."""
    k = len(q)
    # fan apex with the largest smallest triangle: a tiny top triangle turns float32 noise into a
    # non-convex face plane on read-back (#326)
    def min_area(a):
        r = np.roll(q, -a, axis=0)
        e1, e2 = r[1:-1] - r[0], r[2:] - r[0]
        return float(np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).min()) if k > 3 else 1.0
    a0 = max(range(k), key=min_area)
    order = [(a0 + i) % k for i in range(k)]
    top = q @ plane[:2] + plane[2]
    verts = np.concatenate([np.column_stack([q, np.full(k, base)]), np.column_stack([q, top])])
    tr = [(order[0], order[i + 1], order[i]) for i in range(1, k - 1)] + \
         [(k + order[0], k + order[i], k + order[i + 1]) for i in range(1, k - 1)]
    for j in range(k):
        j1 = (j + 1) % k
        tr += [(j, j1, k + j1), (j, k + j1, k + j)]
    pc = Piece(verts, np.array(tr, np.int64))
    pc.plan, pc.plane = q.copy(), (float(plane[0]), float(plane[1]), float(plane[2]))
    return pc


def build_ground(verts, tris, *, cell: float = 16.0, min_cell: float = 0.5, tol: float = 0.08,
                 depth: float = 0.5, gap: float = GAP_M, samples: int = 6,
                 model_triangles: int | None = None, reserved_triangles: int = 0) -> UcxResult:
    """UCX for the Ground target: convex prisms over a binary space partition of the covered plan.

    Start cells of `cell` metres are cut (a) along a single chord when the covered-region outline inside
    the cell lies within tol/4 of one line (the chord is moved to the void side of every outline point,
    so no piece reaches into a void), (b) along the line of the longest outline segment, (c) along the
    longest kerb/step trace (`_breaklines`) or internal layer edge when the planar top misses the surface by more than `tol`,
    else (d) in half across the longer side down to `min_cell`. Each leaf is shrunk by gap/2 per edge and
    gets a minimax-shifted least-squares planar top; its deviation is exact over the leaf (surface vertices,
    mesh-edge crossings of the leaf boundary and leaf corners, see HeightField.crossings). Covered strips
    left without a piece (chord band, slivers thinner than the gap) are reported in `uncovered_strip_m`."""
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
    out_seg, layer_seg = _outline(hf)
    outline = _SegIndex(out_seg, lo, hf.bucket)
    breaks = _SegIndex(np.concatenate([_breaklines(hf, tol / 2), layer_seg]), lo, hf.bucket)
    vidx = _SegIndex(np.stack([hf.v[:, :2], hf.v[:, :2]], axis=1), lo, hf.bucket)
    g = gap / 2
    chord_tol = tol / 4  # band + corner retreat stay within tol (uncovered_strip_m)
    stack = [(np.array([(x, y), (x + sx, y), (x + sx, y + sy), (x, y + sy)]), 0)
             for x in lo[0] + sx * np.arange(n[0]) for y in lo[1] + sy * np.arange(n[1])]
    pieces, devs, strips, loose = [], [0.0], [0.0], []
    lin = (np.arange(samples) + 0.5) / samples

    def covered(p) -> bool:
        q = _inset(p, min(g, 0.25 * _min_width(p)))
        c = (q if len(q) else p).mean(axis=0)
        return bool(np.isfinite(hf.z(c[None])[0]))

    def cut(p, a, b):
        d = b - a
        nn = np.array([-d[1], d[0]]) / max(float(np.hypot(*d)), 1e-15)
        c = float(nn @ a)
        p1, p2 = _clip(p, nn, c), _clip(p, -nn, -c)
        area = _poly_area(p)
        if len(p1) >= 3 and len(p2) >= 3 and min(_poly_area(p1), _poly_area(p2)) > 1e-9 * max(area, 1.0) \
                and max(_poly_area(p1), _poly_area(p2)) < area - 1e-12:
            return [p1, p2]
        return None

    def bisect(p):
        bmin, bmax = p.min(axis=0), p.max(axis=0)
        ax = int(np.argmax(bmax - bmin))
        if (bmax - bmin)[ax] < 2 * min_cell:
            return None
        m = (bmin[ax] + bmax[ax]) / 2
        nn = np.zeros(2)
        nn[ax] = 1.0
        return [_clip(p, nn, m), _clip(p, -nn, -m)]

    def fit(q):
        """Planar top for the shrunk leaf `q`: exact max |surface - top| over it."""
        bmin, bmax = q.min(axis=0), q.max(axis=0)
        gx, gy = np.meshgrid(bmin[0] + lin * (bmax[0] - bmin[0]), bmin[1] + lin * (bmax[1] - bmin[1]))
        grid = np.stack([gx.ravel(), gy.ravel()], axis=1)
        vin = vidx.query(bmin, bmax)[:, 0]
        edges = np.stack([q, np.roll(q, -1, axis=0)], axis=1)
        pts = np.concatenate([q, grid[_inside(q, grid)], vin[_inside(q, vin)], hf.crossings(edges),
                              hf.kinks(bmin, bmax), hf.layer_crossings(edges)])
        # the envelope of unwelded layers jumps across layer edges: its one-sided limits at a vertex of the
        # arrangement are read just beside it (6 directions, 10 um: slope x 1e-5 m below any tolerance)
        pts = np.concatenate([pts, (pts[:, None, :] + _NUDGE[None]).reshape(-1, 2)])
        pts = pts[_inside(q, pts, 1e-9)]
        zs = hf.z(pts)
        hit = np.isfinite(zs)
        if not hit.any():
            return None
        a = np.column_stack([pts[hit], np.ones(int(hit.sum()))])
        plane = np.linalg.lstsq(a, zs[hit], rcond=None)[0]
        r = zs[hit] - a @ plane
        plane[2] += (r.max() + r.min()) / 2  # minimax shift: max |r| becomes (max - min) / 2
        dev = float((r.max() - r.min()) / 2)
        return plane, dev, float(zs[hit].min())

    def low(p, reach) -> float:
        """Lowest model vertex within `reach` of leaf `p` (inf when none)."""
        k = vidx.ids(p.min(axis=0) - reach, p.max(axis=0) + reach)
        if not len(k):
            return math.inf
        k = k[_poly_dist(hf.v[k, :2], p)[0] <= reach]
        return float(hf.v[k, 2].min()) if len(k) else math.inf

    def leaf(p, strip=0.0):
        q = _inset(p, g)
        q = _simplify(q) if len(q) else q
        if not len(q) or _min_width(q) < 1e-4:
            loose.append((p, None, strip))  # covered sliver thinner than the gap: no piece, measured below
            return True
        got = fit(q)
        if got is None:
            return True
        plane, dev, zmin = got
        return plane, dev, zmin, q

    while stack:
        p, lvl = stack.pop()
        if len(p) < 3 or _poly_area(p) <= 1e-12:
            continue
        pmin, pmax = p.min(axis=0), p.max(axis=0)
        seg = _segs_inside(outline.query(pmin, pmax), p)
        deep = lvl >= 80
        parts, strip = [p], 0.0
        if len(seg):
            pts = seg.reshape(-1, 2)
            ctr = pts.mean(axis=0)
            _, _, vt = np.linalg.svd(pts - ctr)
            nn = np.array([-vt[0, 1], vt[0, 0]])
            proj = pts @ nn
            cmin, cmax = float(proj.min()), float(proj.max())
            if cmax - cmin <= chord_tol or deep:
                parts, strip = [], cmax - cmin  # outline in a band: keep the outline-free sides only
                for side in (_clip(p, nn, cmax), _clip(p, -nn, -cmin)):
                    if len(side) >= 3 and _poly_area(side) > 1e-12 and covered(side):
                        parts.append(side)
                strips.append(strip + g)
            else:
                ln = np.linalg.norm(seg[:, 1] - seg[:, 0], axis=1)
                kids = cut(p, *seg[int(np.argmax(ln))]) or bisect(p)
                if kids:
                    stack.extend((k, lvl + 1) for k in kids)
                    continue
                parts, strip = [], cmax - cmin  # cannot cut: same band rule, reported
                for side in (_clip(p, nn, cmax), _clip(p, -nn, -cmin)):
                    if len(side) >= 3 and _poly_area(side) > 1e-12 and covered(side):
                        parts.append(side)
                strips.append(strip + g)
        elif not covered(p):
            continue
        for part in parts:
            got = leaf(part, strip)
            if got is True:
                continue
            plane, dev, zmin, q = got
            if dev > tol and not deep:
                br = _segs_inside(breaks.query(pmin, pmax), part)
                kids = None
                if len(br):
                    ln = np.linalg.norm(br[:, 1] - br[:, 0], axis=1)
                    kids = cut(part, *br[int(np.argmax(ln))])
                kids = kids or bisect(part)
                if kids:
                    stack.extend((k, lvl + 1) for k in kids)
                    continue
            top = q @ plane[:2] + plane[2]
            # bottom below every model vertex of the leaf and its outline band: perimeter skirts and
            # undersides of a layered (method C) slab are model surface too [D134]
            reach = strip + g + 1e-6
            pieces.append(_prism(q, plane, min(float(top.min()) - depth, zmin - depth, low(part, reach))))
            devs.append(dev)
            retreat = float(_poly_dist(part, q)[0].max())  # farthest leaf point from its own piece
            if retreat > gap:  # acute corner or needle: measured against all pieces below
                loose.append((part, q, strip))
            else:
                strips.append(retreat + strip)
    if not pieces:
        raise UcxBuildError("ground surface has no plan area")
    strips += [_loose_distance(p, q, pieces, gap) + strip for p, q, strip in loose]
    tri_count = sum(len(pc.tris) for pc in pieces)
    if len(pieces) > MAX_PIECES or tri_count > budget:
        raise UcxBuildError(f"{len(pieces)} ground pieces / {tri_count} tris exceed {MAX_PIECES} pieces "
                            f"or budget {budget}")
    pieces.sort(key=lambda pc: tuple(np.round(pc.plan.mean(axis=0)[::-1], 3)))
    return UcxResult("Ground", pieces, float(cell), gap, 0.0, budget, reserved,
                     [{"min_cell_m": min_cell, "tol_m": tol, "grid_m": [round(sx, 6), round(sy, 6)],
                       "outline_segments": len(outline.seg), "internal_layer_edges":
                           len(layer_seg), "breaklines": len(breaks.seg)}],
                     max_vertical_dev_m=max(devs), tol_m=tol,
                     footprint_overhang_bound_m=0.0, uncovered_strip_m=max(strips))


def _region_distance(p, pieces, step: float = 0.01) -> float:
    """Upper bound of the plan distance from any point of convex region `p` to the nearest piece: the
    maximum over boundary samples `step` apart, plus step / 2, plus half the minimum width of `p` (every
    point of a convex polygon lies within its inradius of the boundary; distance is 1-Lipschitz)."""
    pts = [p]
    for a, d in zip(p, np.roll(p, -1, axis=0) - p):
        k = max(1, int(math.ceil(float(np.hypot(*d)) / step)))
        pts.append(a + np.outer(np.arange(1, k) / k, d))
    pts = np.concatenate(pts)
    lo, hi = p.min(axis=0) - 1.0, p.max(axis=0) + 1.0
    best = np.full(len(pts), np.inf)
    for pc in pieces:
        if (pc.plan.min(axis=0) > hi).any() or (pc.plan.max(axis=0) < lo).any():
            continue
        best = np.minimum(best, _poly_dist(pts, pc.plan)[0])
    return float(best.max()) + step / 2 + _min_width(p) / 2


def _loose_distance(p, q, pieces, gap: float) -> float:
    """Farthest point of the covered leaf `p` from all pieces, where its own piece `q` (p shrunk by gap/2,
    or None for a dropped sliver) leaves more than `gap`: the distance to the convex `q` is convex, so it
    peaks at a vertex of `p`; a vertex that retreats R > gap (acute corner, needle tip) is re-measured
    against every piece over p clipped to the square of half-size R around it."""
    if q is None:
        return _region_distance(p, pieces)
    r = _poly_dist(p, q)[0]
    out = [float(r[r <= gap].max()) if (r <= gap).any() else 0.0]
    for k in np.flatnonzero(r > gap):
        reg = p
        for nn, c in ((np.array([1.0, 0.0]), p[k, 0] - r[k]), (np.array([-1.0, 0.0]), -p[k, 0] - r[k]),
                      (np.array([0.0, 1.0]), p[k, 1] - r[k]), (np.array([0.0, -1.0]), -p[k, 1] - r[k])):
            reg = _clip(reg, nn, c)
        if len(reg) >= 3:
            out.append(min(float(r[k]), _region_distance(reg, pieces)))
    return max(out)


def piece_plan_contains(piece: Piece, xy, eps: float = 0.0) -> np.ndarray:
    """Which plan points (N, 2) lie on or inside the plan of a Ground piece (its convex bottom)."""
    return _inside(piece.plan, np.asarray(xy, float).reshape(-1, 2), eps)


def _poly_dist(xy, q):
    """Plan distance of points (N, 2) to convex polygon `q` (0 inside) and the nearest polygon points."""
    ins = _inside(q, xy, 1e-12)
    e0, ev = q, np.roll(q, -1, axis=0) - q
    tt = np.clip(((xy[:, None, :] - e0[None]) * ev[None]).sum(-1) / np.maximum((ev ** 2).sum(-1), 1e-15)[None], 0, 1)
    near = e0[None] + tt[..., None] * ev[None]
    dh = np.linalg.norm(xy[:, None, :] - near, axis=2)
    k = np.argmin(dh, axis=1)
    r = np.arange(len(xy))
    return np.where(ins, 0.0, dh[r, k]), np.where(ins[:, None], xy, near[r, k])


def ground_deviation(points, result: UcxResult, margin: float | None = None) -> np.ndarray:
    """One-sided model -> UCX distance [D134] of each surface point (an upper bound of the true distance):
    over a piece plan, the vertical distance to its top; within `margin` (default: gap + the reported
    uncovered strip) outside every plan, the distance to the nearest point of the nearest top edge;
    inf where no piece is that close."""
    p = np.asarray(points, float).reshape(-1, 3)
    out = np.full(len(p), np.inf)
    if margin is None:
        margin = result.gap_m + (result.uncovered_strip_m or 0.0) + 1e-9
    for pc in result.pieces:
        q, (a, b, c) = pc.plan, pc.plane
        lo, hi = q.min(axis=0) - margin, q.max(axis=0) + margin
        sel = np.flatnonzero((p[:, 0] >= lo[0]) & (p[:, 0] <= hi[0]) & (p[:, 1] >= lo[1]) & (p[:, 1] <= hi[1]))
        if not len(sel):
            continue
        dh, nq = _poly_dist(p[sel, :2], q)
        dz = p[sel, 2] - (a * nq[:, 0] + b * nq[:, 1] + c)
        d = np.where(dh <= margin, np.hypot(dh, dz), np.inf)
        out[sel] = np.minimum(out[sel], d)
    return out


def build(target: str, verts, tris, **kw) -> UcxResult:
    """One entry point for job scripts: target 'Main' or 'Ground'."""
    if target == "Main":
        return build_main(verts, tris, **kw)
    if target == "Ground":
        return build_ground(verts, tris, **kw)
    raise UcxBuildError(f"target must be one of {TARGETS}, got {target!r}")
