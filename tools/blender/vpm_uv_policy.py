"""new-case: shared VPM quad-size policy for the slicer and master QA (#1380).

[D021], [D320]: (tile_px - 2 * padding_px) / density; default density 1024 px/m,
padding 16 px per 2048 tile. 4096 -> 3.9375 m, 2048 -> 1.96875 m.
This geometric ceiling does not waive finish-specific phase/padding constraints.
Tileable islands may overlap/stack; no UV overlap check is imposed [D320].
"""
import math
import numbers


def max_quad_side(tile_px=4096, *, padding_px=None, density_px_per_m=1024):
    """Inclusive maximum side in metres; malformed/unmeasurable policy raises ValueError."""
    if isinstance(tile_px, bool) or not isinstance(tile_px, numbers.Integral) or tile_px <= 0:
        raise ValueError(f'tile_px must be a positive integer: {tile_px!r}')
    padding_px = tile_px / 128 if padding_px is None else padding_px
    for name, value in (('padding_px', padding_px), ('density_px_per_m', density_px_per_m)):
        if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
            raise ValueError(f'{name} must be finite: {value!r}')
    if padding_px < 0 or 2 * padding_px >= tile_px or density_px_per_m <= 0:
        raise ValueError('tile padding must leave a positive span; density must be positive')
    side = (tile_px - 2 * padding_px) / density_px_per_m
    if not math.isfinite(side) or side <= 0:
        raise ValueError('tile side is unmeasurable')
    return side
