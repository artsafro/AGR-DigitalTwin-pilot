import importlib.util
import math
from pathlib import Path

_ownspec = importlib.util.spec_from_file_location(
    "udimtile_core_dt_ai", Path(__file__).resolve().parents[3] / "adapters/max/agr_tools/udimtile_core.py")
_udimtile = importlib.util.module_from_spec(_ownspec)  # the one UDIM function (#1337, #1376)
_ownspec.loader.exec_module(_udimtile)


def _regulated_tile_origin(tile: int):
    """UDIM tile -> (u_tile, v_tile) via udimtile_core.tile_origin, limited to the regulation grid 1001..1100."""
    if type(tile) is not int or not 1001 <= tile <= 1100:
        raise ValueError("UDIM must be 1001..1100")
    return _udimtile.tile_origin(tile)


tile_origin = _regulated_tile_origin


def tile_quad(tile: int, size: int, padding: int):
    u, v = tile_origin(tile)
    p = padding / size
    return [[u + p, v + p], [u + 1 - p, v + p],
            [u + 1 - p, v + 1 - p], [u + p, v + 1 - p]]


def signed_area(uv):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(uv, uv[1:] + uv[:1])) / 2


def validate_uv(uv, tile, size, padding):
    u, v = tile_origin(tile)
    p = padding / size
    return (len(uv) >= 3 and all(len(x) == 2 and all(math.isfinite(c) for c in x) for x in uv)
            and signed_area(uv) > 1e-10
            and all(u + p - 1e-6 <= x <= u + 1 - p + 1e-6
                    and v + p - 1e-6 <= y <= v + 1 - p + 1e-6 for x, y in uv))


def edge_densities(vertices, uv, size):
    result = []
    for i in range(len(vertices)):
        j = (i + 1) % len(vertices)
        world = math.dist(vertices[i], vertices[j])
        if world <= 1e-9:
            raise ValueError("Degenerate surface edge")
        result.append(size * math.dist(uv[i], uv[j]) / world)
    return result
