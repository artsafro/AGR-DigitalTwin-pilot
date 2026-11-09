# Ported from AGR src/dt_ai/geometry/uv.py (sha256 259a15fe300c) on 2026-10-06;
# changes: tile range and density limits come from VPM_STANDARD.yaml, added
# udim_of()/face_issue() so a failure says why (mirrored / cross-tile / margin),
# added sequential_tiles(). tile_origin/tile_quad/signed_area/edge_densities unchanged.
"""UDIM tiles, mirrored islands, tile margins and texel density (VPM, reg p.31-32, 39)."""
import math

from twinqa.report import Finding, signed_margin

# VPM diffuse band (standards/VPM_STANDARD.yaml uv.diffuse_density_px_per_m). Not a new limit.
DENSITY_MIN_PX_PER_M = 512
DENSITY_MAX_PX_PER_M = 1706

# UDIM = 1001 + U + 10 * V on a 10 x 10 grid (reg p.23, p.31 §2.1.3, p.39;
# VPM_STANDARD.yaml uv.udim_grid; figure typo on p.39 is conflict #9, text wins).
FIRST_TILE, LAST_TILE = 1001, 1100
EPS = 1e-6


def tile_origin(tile: int):
    if type(tile) is not int or not FIRST_TILE <= tile <= LAST_TILE:
        raise ValueError("UDIM must be 1001..1100")
    return (tile - 1001) % 10, (tile - 1001) // 10


def tile_quad(tile: int, size: int, padding: int):
    u, v = tile_origin(tile)
    p = padding / size
    return [[u + p, v + p], [u + 1 - p, v + p],
            [u + 1 - p, v + 1 - p], [u + p, v + 1 - p]]


def signed_area(uv):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(uv, uv[1:] + uv[:1])) / 2


def udim_of(uv) -> int | None:
    """Tile of the face centroid, or None when it lies outside the 10 x 10 grid."""
    cu = sum(p[0] for p in uv) / len(uv)
    cv = sum(p[1] for p in uv) / len(uv)
    u, v = math.floor(cu), math.floor(cv)
    return 1001 + u + 10 * v if 0 <= u <= 9 and 0 <= v <= 9 else None


def face_issue(uv, tile, size, padding):
    """None if the face is valid in `tile`; otherwise 'invalid', 'mirrored', 'cross_tile' or 'margin'.

    mirrored: UV winding opposite to the polygon winding (reg p.31 §2.1.4 forbids mirrored islands).
    cross_tile: a vertex leaves the tile (geometry must be split, reg p.31 §2.1.2).
    margin: inside the tile but closer to its border than `padding` px; the regulation asks for
    a margin (reg p.31 §2.1.5) without a size, so the caller reports this as review.
    """
    if len(uv) < 3 or not all(len(x) == 2 and all(math.isfinite(c) for c in x) for x in uv):
        return "invalid"
    area = signed_area(uv)
    if abs(area) <= 1e-12:
        return "invalid"
    if area < 0:
        return "mirrored"
    u, v = tile_origin(tile)
    if not all(u - EPS <= x <= u + 1 + EPS and v - EPS <= y <= v + 1 + EPS for x, y in uv):
        return "cross_tile"
    p = padding / size
    if not all(u + p - EPS <= x <= u + 1 - p + EPS and v + p - EPS <= y <= v + 1 - p + EPS for x, y in uv):
        return "margin"
    return None


def validate_uv(uv, tile, size, padding):
    return face_issue(uv, tile, size, padding) is None


def sequential_tiles(tiles) -> bool:
    """Tiles filled from 1001 without gaps (reg p.31 §2.1.3)."""
    ordered = sorted(set(tiles))
    return ordered == list(range(FIRST_TILE, FIRST_TILE + len(ordered))) and (not ordered or ordered[-1] <= LAST_TILE)


def _density_finding(name, measured, threshold, bound, observed, evidence="uv edge density") -> Finding:
    """One density bound. No measured value, or a zero threshold, is a fail with margin None."""
    margin = None if measured is None else signed_margin(measured, threshold, bound)
    if margin is None:
        status = "fail"
    elif bound == "min":
        status = "pass" if measured >= threshold else "fail"
    else:
        status = "pass" if measured <= threshold else "fail"
    relation = ">=" if bound == "min" else "<="
    return Finding(
        name, status, observed, f"{relation} {threshold:g} px/m", [31, 32], evidence,
        measured=measured, threshold=threshold, margin=margin,
    )


def density_findings(vertices, uv, size, *, min_px_per_m=DENSITY_MIN_PX_PER_M,
                     max_px_per_m=DENSITY_MAX_PX_PER_M) -> list[Finding]:
    """Min and max texel-density findings for one polygon.

    The minimum uses the smallest edge density against 512 px/m. The maximum uses the
    largest edge density against 1706 px/m. An empty polygon fails both; a degenerate
    edge still raises from ``edge_densities``.
    """
    if len(vertices) < 2 or len(uv) < 2:
        return [
            _density_finding("texel density", None, min_px_per_m, "min", "no edges"),
            _density_finding("texel density upper", None, max_px_per_m, "max", "no edges"),
        ]
    values = edge_densities(vertices, uv, size)
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"non-finite edge density {value!r}")
    if not values:
        return [
            _density_finding("texel density", None, min_px_per_m, "min", "no edges"),
            _density_finding("texel density upper", None, max_px_per_m, "max", "no edges"),
        ]
    low, high = min(values), max(values)
    return [
        _density_finding("texel density", low, min_px_per_m, "min", f"min {low:.6g} px/m"),
        _density_finding("texel density upper", high, max_px_per_m, "max", f"max {high:.6g} px/m"),
    ]


def _finite_components(point, label):
    """Reject a non-finite coordinate before it becomes a density.

    Accept any finite-length iterable of finite numbers, including a numpy
    ndarray, the same inputs ``math.dist`` accepts. ``str`` and ``bytes`` stay
    rejected: iterating them would yield characters, not coordinates.
    """
    if isinstance(point, (str, bytes)):
        raise ValueError(f"partial {label}")
    try:
        components = list(point)
    except TypeError:
        raise ValueError(f"partial {label}") from None
    if len(components) < 2:
        raise ValueError(f"partial {label}")
    for coord in components:
        if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord):
            raise ValueError(f"non-finite {label} {coord!r}")


def edge_densities(vertices, uv, size):
    """px/m per polygon edge: texture_side_px * |duv| / |dxyz| (reg p.32 §6.2, division per conflict #10).

    A non-finite UV coordinate, world coordinate, texture size or resulting density raises
    before any min/max can treat it as a pass.
    """
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size):
        raise ValueError(f"non-finite texture size {size!r}")
    if len(vertices) != len(uv):
        raise ValueError(f"partial UV geometry: {len(uv)} uv for {len(vertices)} vertices")
    result = []
    for i in range(len(vertices)):
        j = (i + 1) % len(vertices)
        _finite_components(vertices[i], "world coordinate")
        _finite_components(vertices[j], "world coordinate")
        _finite_components(uv[i], "UV coordinate")
        _finite_components(uv[j], "UV coordinate")
        world = math.dist(vertices[i], vertices[j])
        if not math.isfinite(world):
            raise ValueError(f"non-finite world edge {world!r}")
        if world <= 1e-9:
            raise ValueError("Degenerate surface edge")
        density = size * math.dist(uv[i], uv[j]) / world
        if not math.isfinite(density):
            raise ValueError(f"non-finite edge density {density!r}")
        result.append(density)
    return result
