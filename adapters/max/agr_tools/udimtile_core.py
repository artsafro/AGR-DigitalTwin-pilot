"""new-case: one shared UDIM tile function (#1337), stdlib only; importable from 3ds Max, Blender and Python.

UDIM = 1001 + u_tile + 10 * v_tile (Blender manual «UDIM»; reg p.23, p.31 §2.1.3, VPM_STANDARD.yaml uv.udim_grid).

Domain, explicit:
- a point (u, v) must be finite real numbers (bool and str refused) with 0 <= u < 10 and v >= 0;
- tiles are half-open [k, k + 1): u = 1.0 lies in tile 1002, v = 1.0 in tile 1011, u = 10.0 is outside;
- rows v_tile >= 10 are DEFINED (1101, 1102, ...), as in Blender; the regulation range 1001..1100 (10 x 10) is
  the caller's check, not this function's;
- anything outside the domain raises UdimDomainError (a ValueError) naming the value. Never None.

A face is judged by its centroid (a face whose corners all lie on tile lines, e.g. [1, 2] x [0, 1], is tile 1002,
not a vote of its corners). With strict=True (default) a corner more than `tol` outside the closed centroid tile
raises UdimCrossTileError (a UdimDomainError); strict=False returns the centroid tile for a crossing face, for
callers that report crossing separately (twinqa face_issue, uv_features cross_tile).

Loaded by path (no package import), like the other agr_tools cores: twinqa/uv.py, uvlayout_core.py and
jobs/elv-tc-vpm/scripts/joint_continuity_v008.py (Blender) all use this file.
"""
import math
import numbers

FIRST_UDIM = 1001
U_TILES = 10
FACE_TOL = 1e-6


class UdimDomainError(ValueError):
    """A point, cell, face or tile outside the UDIM domain (u in [0, 10), v >= 0, finite)."""


class UdimCrossTileError(UdimDomainError):
    """A face whose corners leave the tile of its centroid."""


def _real(x, what):
    if isinstance(x, bool) or not isinstance(x, numbers.Real):
        raise UdimDomainError('UDIM {} must be a real number: {!r}'.format(what, x))
    x = float(x)
    if not math.isfinite(x):
        raise UdimDomainError('UDIM {} must be finite: {!r}'.format(what, x))
    return x


def udim_of_cell(cu, cv):
    """Integer UV cell (u_tile, v_tile) -> UDIM. 0 <= u_tile <= 9, v_tile >= 0; v_tile >= 10 gives 1101+."""
    for name, c in (('u_tile', cu), ('v_tile', cv)):
        if isinstance(c, bool) or not isinstance(c, numbers.Integral):
            raise UdimDomainError('UDIM {} must be an integer: {!r}'.format(name, c))
    if not 0 <= cu < U_TILES:
        raise UdimDomainError('UDIM u_tile outside 0..9: {!r}'.format(cu))
    if cv < 0:
        raise UdimDomainError('UDIM v_tile must be >= 0: {!r}'.format(cv))
    return FIRST_UDIM + int(cu) + U_TILES * int(cv)


def udim_tile(u, v):
    """UDIM tile of a UV point: 1001 + floor(u) + 10 * floor(v); u in [0, 10), v >= 0, else UdimDomainError."""
    u, v = _real(u, 'u'), _real(v, 'v')
    if not 0.0 <= u < U_TILES:
        raise UdimDomainError('UDIM u outside [0, 10): {!r}'.format(u))
    if v < 0.0:
        raise UdimDomainError('UDIM v must be >= 0: {!r}'.format(v))
    return udim_of_cell(math.floor(u), math.floor(v))


def tile_origin(tile):
    """UDIM tile (int >= 1001) -> its integer cell (u_tile, v_tile)."""
    if isinstance(tile, bool) or not isinstance(tile, numbers.Integral) or tile < FIRST_UDIM:
        raise UdimDomainError('UDIM tile must be an integer >= 1001: {!r}'.format(tile))
    k = int(tile) - FIRST_UDIM
    return k % U_TILES, k // U_TILES


def face_tile(uvs, strict=True, tol=FACE_TOL):
    """UDIM tile of a face [(u, v), ...] (>= 3 corners) by its centroid; see the module docstring for strict."""
    try:
        pts = [tuple(p) for p in uvs]
    except TypeError:
        raise UdimDomainError('UDIM face must be a sequence of (u, v) corners: {!r}'.format(uvs)) from None
    if len(pts) < 3 or any(len(p) != 2 for p in pts):
        raise UdimDomainError('UDIM face needs >= 3 (u, v) corners: {!r}'.format(uvs))
    pts = [(_real(p[0], 'u'), _real(p[1], 'v')) for p in pts]
    cu = sum(p[0] for p in pts) / len(pts)
    cv = sum(p[1] for p in pts) / len(pts)
    tile = udim_tile(cu, cv)
    if strict:
        u0, v0 = tile_origin(tile)
        out = [p for p in pts if not (u0 - tol <= p[0] <= u0 + 1 + tol and v0 - tol <= p[1] <= v0 + 1 + tol)]
        if out:
            raise UdimCrossTileError('UDIM face crosses tile {}: corners {!r} outside it'.format(tile, out))
    return tile
