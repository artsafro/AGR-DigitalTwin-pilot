"""Texel readiness kernel invariant: every face fits one texture tile at the profile density [D129, D021, D097].

`texel_ready` answers: can each part be unwrapped to its target texel density without further cuts? A face fits one
tile when its longest side is at most `max_side = (tile_px - 2 x padding_px) / density_px_per_m` [D021,
`docs/domain/conflicts.md` #26]. Per face we measure the longest edge (n-gons with more than 4 sides: the longest
edge or diagonal, "span"), the area (Newell vector area) and the aspect ratio:
quad = mean of the two longer opposite edges / mean of the two shorter; triangle = longest edge / its height
(2 x area / longest edge); n-gon = span / (area / span).

Profiles (limits are computed, never typed in):
- VPM (OKS and Ground): 4096 px tile, 32 px padding, 1024 px/m. Above the padded side 3.9375 m a face is `review`,
  above one tile 4096 / 1024 = 4.0 m it fails [D021: "about 4 x 4 m ... adapter default 3.9 m"]; area <= 4.0^2.
- NPM Ground: 2048 px tile, 8 px padding, 40 px/m (upper end of D097 "NPM 10-40 at 2K", so the face fits at every
  density of the range; orchestrator default, user may change) -> 50.8 m, area <= 50.8^2.
- NPM-OKS: no density gate (`docs/domain/uv-textures.md`); sizes are only reported, never fail.
- Aspect <= 8 : 1 in every profile: no decision number exists (orchestrator default, user may change).
Degenerate faces (zero edge, zero / collinear / self-cancelling area) fail in every profile: they cannot be unwrapped.

Pure numpy, no Blender [D108, D131]. Inputs: `PolyMesh` (polygon faces) or the triangle `Mesh` of `invariants.py`.
Does not measure UV density (V009) and does not cut quads (the adapter).
Pattern: none | new-case: kernel invariant texel_ready, per-face tile fit per profile (#346).
"""
from dataclasses import dataclass
from math import isfinite
from typing import Iterable

import numpy as np

from dt_ai.ops.invariants import InvariantReport, InvariantResult, Mesh

NAME = "texel_ready"

# VPM [D021]: "cut VPM quads to about 4 x 4 m (1024 px/m; adapter default 3.9 m)"; 4K tile [D097 "VPM ... at 4K"];
# padding 32 px @4096 (docs/domain/uv-textures.md, reg p.30 §5.1.5).
VPM_TILE_PX = 4096
VPM_PADDING_PX = 32
VPM_DENSITY_PX_PER_M = 1024
# NPM Ground [D097]: "NPM 10-40 at 2K"; 40 px/m = upper end of the range (orchestrator default, user may change);
# padding 8 px (docs/domain/uv-textures.md, reg p.9 §5.4).
NPM_GROUND_TILE_PX = 2048
NPM_GROUND_PADDING_PX = 8
NPM_GROUND_DENSITY_PX_PER_M = 40
# Aspect ratio: no decision number exists; 8 : 1 is the orchestrator default (#346), user may change.
ASPECT_MAX = 8.0
# A face is degenerate when its area is below this fraction of its longest side squared.
_DEGENERATE_REL = 1e-9


def max_side(tile_px: float, padding_px: float, density_px_per_m: float) -> float:
    """Longest face side that fits one tile with padding: (tile_px - 2 x padding_px) / density [D021, conflicts #26]."""
    for name, value in (("tile_px", tile_px), ("padding_px", padding_px), ("density_px_per_m", density_px_per_m)):
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)) or not isfinite(value):
            raise ValueError(f"{name} must be a finite number, got {value!r}")
    if density_px_per_m <= 0:
        raise ValueError(f"density_px_per_m must be > 0, got {density_px_per_m}")
    if padding_px < 0:
        raise ValueError(f"padding_px must be >= 0, got {padding_px}")
    usable = tile_px - 2 * padding_px
    if usable <= 0:
        raise ValueError(f"tile {tile_px} px minus 2 x padding {padding_px} px leaves no room")
    return usable / density_px_per_m


@dataclass(frozen=True)
class TexelParams:
    """Limits of one profile. All three size fields None = report-only (no density gate)."""
    tile_px: float | None
    padding_px: float | None
    density_px_per_m: float | None
    aspect_max: float = ASPECT_MAX
    padding_is_review: bool = False   # True: fail above one tile (tile / density), review above the padded side

    def __post_init__(self):
        sizes = (self.tile_px, self.padding_px, self.density_px_per_m)
        if any(s is None for s in sizes) and not all(s is None for s in sizes):
            raise ValueError("tile_px, padding_px and density_px_per_m are all set or all None")
        if self.size_gated:
            max_side(*sizes)   # validates
        a = self.aspect_max
        if isinstance(a, bool) or not isinstance(a, (int, float)) or not isfinite(a) or a < 1:
            raise ValueError(f"aspect_max must be a finite number >= 1, got {a!r}")
        if not isinstance(self.padding_is_review, bool):
            raise ValueError("padding_is_review must be a bool")

    @property
    def size_gated(self) -> bool:
        return self.tile_px is not None

    @property
    def review_side_m(self) -> float | None:
        return max_side(self.tile_px, self.padding_px, self.density_px_per_m) if self.size_gated else None

    @property
    def hard_side_m(self) -> float | None:
        if not self.size_gated:
            return None
        return self.tile_px / self.density_px_per_m if self.padding_is_review else self.review_side_m

    @property
    def max_area_m2(self) -> float | None:
        return self.hard_side_m ** 2 if self.size_gated else None


VPM = TexelParams(VPM_TILE_PX, VPM_PADDING_PX, VPM_DENSITY_PX_PER_M, padding_is_review=True)
NPM_GROUND = TexelParams(NPM_GROUND_TILE_PX, NPM_GROUND_PADDING_PX, NPM_GROUND_DENSITY_PX_PER_M)
NPM_OKS = TexelParams(None, None, None)   # no density gate (uv-textures.md): sizes reported only
PROFILES = {"VPM-OKS": VPM, "VPM-Ground": VPM, "NPM-Ground": NPM_GROUND, "NPM-OKS": NPM_OKS}


@dataclass(frozen=True)
class PolyMesh:
    vertices: np.ndarray   # (n, 3) metres
    faces: tuple           # tuples of vertex indices, >= 3 per face

    def __post_init__(self):
        v = np.asarray(self.vertices, dtype=float)
        if v.ndim != 2 or v.shape[1] != 3:
            raise ValueError("vertices must be (n, 3)")
        if not np.isfinite(v).all():
            raise ValueError("vertices must be finite")
        faces = []
        for f in self.faces:
            f = tuple(int(i) for i in f)
            if len(f) < 3:
                raise ValueError(f"face {f} has fewer than 3 vertices")
            if min(f) < 0 or max(f) >= len(v):
                raise ValueError(f"face {f} indexes outside the vertices")
            faces.append(f)
        object.__setattr__(self, "vertices", v)
        object.__setattr__(self, "faces", tuple(faces))


@dataclass(frozen=True)
class FaceMetrics:
    sides: int
    max_edge_m: float      # n > 4: span (longest edge or diagonal)
    area_m2: float
    aspect: float          # inf when degenerate
    degenerate: bool
    nonfinite: bool = False  # a derived metric overflowed to inf / NaN; the face fails in every profile


@dataclass(frozen=True)
class TexelPartReport:
    part: str
    faces: int
    max_edge_m: float
    max_area_m2: float
    max_aspect: float
    offenders: tuple = ()  # every failing face
    review: tuple = ()     # VPM faces between the padded side and one tile: pass, flagged for a look
    reported: tuple = ()   # report-only profile: faces that would exceed a size limit if one existed

    @property
    def passed(self) -> bool:
        return not self.offenders


def face_metrics(corners: np.ndarray) -> FaceMetrics:
    p = np.asarray(corners, dtype=float)
    n = len(p)
    # Local frame: subtract the first corner so the Newell cross products do not cancel catastrophically for
    # faces far from the origin (a 1 cm sliver at 1e6 m would otherwise lose its area; PR #356 review r1).
    with np.errstate(over="ignore", invalid="ignore"):
        q = p - p[0]
        edges = np.linalg.norm(np.roll(q, -1, axis=0) - q, axis=1)
        newell = np.cross(q, np.roll(q, -1, axis=0)).sum(axis=0)
        area = float(np.linalg.norm(newell) / 2)
        if n > 4:
            size = float(np.linalg.norm(q[:, None] - q[None], axis=2).max())
        else:
            size = float(edges.max())
    if not (np.isfinite(edges).all() and isfinite(area) and isfinite(size)):
        # Overflow (e.g. 1e200 m coordinates) -> inf / NaN metrics: fail closed in every profile.
        return FaceMetrics(n, size, area, float("nan"), True, nonfinite=True)
    degenerate = bool(edges.min() <= 0 or area <= _DEGENERATE_REL * size * size)
    if degenerate:
        return FaceMetrics(n, size, area, float("inf"), True)
    if n == 3:
        aspect = size / (2 * area / size)
    elif n == 4:
        pairs = sorted(((edges[0] + edges[2]) / 2, (edges[1] + edges[3]) / 2))
        aspect = pairs[1] / pairs[0]
    else:
        aspect = size * size / area
    return FaceMetrics(n, size, area, float(aspect), False)


def _num(x: float) -> str:
    s = f"{x:.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def _faces(mesh) -> tuple[np.ndarray, Iterable]:
    if isinstance(mesh, PolyMesh):
        return mesh.vertices, mesh.faces
    if isinstance(mesh, Mesh):
        return mesh.vertices, (tuple(t) for t in mesh.triangles)
    raise ValueError(f"part must be a PolyMesh or a Mesh, got {type(mesh).__name__}")


def _params(profile: str, params: TexelParams | None) -> TexelParams:
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; known: {sorted(PROFILES)}")
    if params is not None and not isinstance(params, TexelParams):
        raise ValueError("params must be a TexelParams")
    return params if params is not None else PROFILES[profile]


def _part_report(part: str, mesh, p: TexelParams) -> TexelPartReport:
    v, faces = _faces(mesh)
    offenders, review, reported = [], [], []
    count, max_edge, max_area, max_aspect = 0, 0.0, 0.0, 0.0
    hard, soft, area_max = p.hard_side_m, p.review_side_m, p.max_area_m2
    for i, f in enumerate(faces):
        count += 1
        m = face_metrics(v[list(f)])
        tag = f"{part}#{i}"
        if m.nonfinite:
            max_edge = max_area = max_aspect = float("nan")
            offenders.append(f"{tag}: non-finite metrics (edge {m.max_edge_m:.3g} m, area {m.area_m2:.3g} m^2)")
            continue
        if not np.isnan(max_edge):
            max_edge, max_area = max(max_edge, m.max_edge_m), max(max_area, m.area_m2)
            max_aspect = max(max_aspect, m.aspect)
        if m.degenerate:
            offenders.append(f"{tag}: degenerate face (edge {m.max_edge_m:.2f} m, area {m.area_m2:.3g} m^2)")
            continue
        label = "span" if m.sides > 4 else "edge"
        reasons, sizes = [], []
        if m.max_edge_m > (hard if hard is not None else np.inf):
            sizes.append(f"{label} {m.max_edge_m:.2f} m > {_num(hard)} m")
        if m.area_m2 > (area_max if area_max is not None else np.inf):
            sizes.append(f"area {m.area_m2:.2f} m^2 > {_num(area_max)} m^2")
        if m.aspect > p.aspect_max:
            reasons.append(f"aspect {m.aspect:.1f} > {p.aspect_max:g}")
        if p.size_gated:
            reasons = sizes + reasons
        if reasons:
            offenders.append(f"{tag}: " + ", ".join(reasons))
        elif p.size_gated and soft < m.max_edge_m <= hard:
            review.append(f"{tag}: {label} {m.max_edge_m:.2f} m in review ({_num(soft)}, {_num(hard)}] m")
        if not p.size_gated:
            reported.append(f"{tag}: {label} {m.max_edge_m:.2f} m, area {m.area_m2:.2f} m^2, aspect {m.aspect:.1f}")
    if count == 0:
        offenders.append(f"{part}: 0 faces")
    return TexelPartReport(part, count, max_edge, max_area, max_aspect, tuple(offenders), tuple(review),
                           tuple(reported))


def texel_report(scene: dict, profile: str, parts: Iterable[str] | None = None,
                 params: TexelParams | None = None) -> dict[str, TexelPartReport]:
    """Full per-part report: every offender, max edge / area / aspect, faces in review, report-only sizes."""
    p = _params(profile, params)
    parts = list(scene) if parts is None else list(parts)
    missing = [q for q in parts if q not in scene]
    if missing:
        raise ValueError(f"parts not in the scene: {missing}")
    return {q: _part_report(q, scene[q], p) for q in parts}


def texel_ready(scene: dict, profile: str, parts: Iterable[str] | None = None,
                params: TexelParams | None = None) -> InvariantResult:
    """`texel_ready`: count = offending faces (+1 per part without faces); fails closed on an empty scene."""
    reports = texel_report(scene, profile, parts, params)
    if not reports:
        return InvariantResult(NAME, False, 1, ("empty scene: no parts to measure",))
    offenders = [o for r in reports.values() for o in r.offenders]
    return InvariantResult(NAME, not offenders, len(offenders), tuple(offenders[:5]))


def check_operation_texel(report: InvariantReport, after: dict, changed: Iterable[str], profile: str,
                          params: TexelParams | None = None) -> InvariantReport:
    """`check_operation`'s report followed by `texel_ready` on the changed parts; earlier results are kept as is."""
    if not isinstance(report, InvariantReport):
        raise ValueError("report must be an InvariantReport")
    return InvariantReport(tuple(report.results) + (texel_ready(after, profile, list(changed), params),))
