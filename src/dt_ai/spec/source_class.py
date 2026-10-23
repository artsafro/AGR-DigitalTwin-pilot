"""Source class from connected parts, largest-part area share, and a closed shell.

Rule 1 [D066]: `PANEL_HINT_SHARE` in `dt_ai.spec.mesh` is the hint threshold, not a guessed
default. `panelised` requires at least two connected parts, a largest-part share strictly
below that threshold, and no closed shell. That class routes to measurement and a direct
build. A closed shell, a single part, or a largest share strictly above the threshold is
`monolithic` and keeps `dt spec extract`. A largest share within 1e-9 of the threshold,
with no shell and more than one part, raises `SourceClassError`.

Empty input, a non-finite coordinate, a zero total area, a bad triangle index, or a face
that is not a triangle also raises. Nothing here changes the extractor.
"""
import math
from dataclasses import dataclass

import numpy as np

from dt_ai.spec.mesh import PANEL_HINT_SHARE, PANELISED, _areas, _parts, _weld

MONOLITHIC = "monolithic"
ROUTE_MEASUREMENT = "measurement+direct-build"
ROUTE_EXTRACT = "dt spec extract"
_SHARE_AT = 1e-9  # shares this close to PANEL_HINT_SHARE are the threshold, not a class


class SourceClassError(ValueError):
    """The three metrics do not decide a class. Fail closed: no default class."""


@dataclass(frozen=True)
class SourceFacts:
    connected_parts: int
    largest_share: float
    shell: bool
    source_class: str


def source_route(source_class: str) -> str:
    """`panelised` → measurement + direct build; `monolithic` → `dt spec extract`."""
    if source_class == PANELISED:
        return ROUTE_MEASUREMENT
    if source_class == MONOLITHIC:
        return ROUTE_EXTRACT
    raise SourceClassError(f"unknown source class {source_class!r}")


def classify_source(vertices, triangles) -> str:
    """Return `panelised` or `monolithic`. Raises `SourceClassError` when it cannot."""
    return source_facts(vertices, triangles).source_class


def source_facts(vertices, triangles) -> SourceFacts:
    """Connected-part count, largest area share, shell present, and the class."""
    v, tris = _welded(vertices, triangles)
    areas = _areas(v, tris)
    if not np.isfinite(areas).all():
        raise SourceClassError("non-finite triangle area")
    total = float(areas.sum())
    if not math.isfinite(total) or total <= 0.0:
        raise SourceClassError("total area is not a positive finite number")
    parts = _parts(v, tris)
    if not parts:
        raise SourceClassError("empty part list")
    shares = [float(areas[part].sum()) / total for part in parts]
    if any(not math.isfinite(share) for share in shares):
        raise SourceClassError("non-finite area share")
    largest = shares[0]
    shell = any(_closed_shell(v, tris[part]) for part in parts)
    return SourceFacts(len(parts), largest, shell, _decide(len(parts), largest, shell))


def _decide(n_parts: int, largest: float, shell: bool) -> str:
    if shell or n_parts == 1:
        return MONOLITHIC
    if math.isclose(largest, PANEL_HINT_SHARE, rel_tol=0.0, abs_tol=_SHARE_AT):
        raise SourceClassError(
            f"largest part share {largest} equals PANEL_HINT_SHARE {PANEL_HINT_SHARE}; not classified")
    if largest < PANEL_HINT_SHARE:
        return PANELISED
    return MONOLITHIC


def _welded(vertices, triangles):
    try:
        v = np.asarray(vertices, dtype=float)
    except (TypeError, ValueError) as exc:
        raise SourceClassError(f"unsupported vertices: {exc}") from exc
    raw = np.asarray(triangles)
    if v.ndim != 2 or v.shape[1] != 3 or raw.ndim != 2 or raw.shape[1] != 3:
        raise SourceClassError("unsupported mesh: vertices (N, 3) and triangles (M, 3) are required")
    if v.shape[0] == 0 or raw.shape[0] == 0:
        raise SourceClassError("empty part list")
    if not np.isfinite(v).all():
        raise SourceClassError("non-finite vertex coordinate")
    if raw.dtype.kind == "f":
        if not np.isfinite(raw).all() or np.any(raw != np.trunc(raw)):
            raise SourceClassError("fractional or non-finite triangle index")
        tris = raw.astype(np.int64)
    elif raw.dtype.kind in "iu":
        tris = raw.astype(np.int64)
    else:
        raise SourceClassError("unsupported triangle index type")
    if np.any(tris < 0) or np.any(tris >= v.shape[0]):
        raise SourceClassError("triangle index out of range")
    rep = _weld(v)
    used, inverse = np.unique(rep, return_inverse=True)
    return v[used], inverse.ravel()[tris]


def _closed_shell(v, comp_tris) -> bool:
    """A part is a shell when every edge has two triangles and the volume is non-zero."""
    if len(comp_tris) < 4:
        return False
    counts: dict[tuple[int, int], int] = {}
    for a, b, c in comp_tris:
        a, b, c = int(a), int(b), int(c)
        if len({a, b, c}) < 3:
            return False
        for i, j in ((a, b), (b, c), (c, a)):
            edge = (i, j) if i < j else (j, i)
            counts[edge] = counts.get(edge, 0) + 1
    if not counts or any(n != 2 for n in counts.values()):
        return False
    p = v[comp_tris]
    volume = float(np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum()) / 6.0
    if not math.isfinite(volume):
        raise SourceClassError("non-finite shell volume")
    return abs(volume) > 1e-9
