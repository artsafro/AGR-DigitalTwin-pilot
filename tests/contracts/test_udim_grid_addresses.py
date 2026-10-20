"""new-case: independent 10x10 UDIM address and pixel-margin geometry controls.

Characterize public engine/checker math, not UV delivery acceptance. Expected
coordinates come from literal row starts, never from either implementation.
"""

import pytest

from dt_ai.geometry import uv as engine
from twinqa import uv as checker


ROW_STARTS = [1001, 1011, 1021, 1031, 1041, 1051, 1061, 1071, 1081, 1091]
GRID = [
    (start + column, column, row)
    for row, start in enumerate(ROW_STARTS)
    for column in range(10)
]
IMPLEMENTATIONS = [pytest.param(engine, id="engine"), pytest.param(checker, id="checker")]


@pytest.mark.parametrize("reader", IMPLEMENTATIONS)
@pytest.mark.parametrize("tile,column,row", GRID)
def test_every_address_has_its_literal_grid_origin(reader, tile, column, row):
    assert reader.tile_origin(tile) == (column, row)


@pytest.mark.parametrize("reader", IMPLEMENTATIONS)
def test_grid_is_bijective_with_literal_endpoints_and_every_row_transition(reader):
    origins = [reader.tile_origin(tile) for tile, _, _ in GRID]
    assert len(origins) == len(set(origins)) == 100
    assert set(origins) == {(column, row) for column in range(10) for row in range(10)}
    assert reader.tile_origin(1001) == (0, 0)
    assert reader.tile_origin(1100) == (9, 9)
    for row, start in enumerate(ROW_STARTS[1:], start=1):
        assert reader.tile_origin(start - 1) == (9, row - 1)
        assert reader.tile_origin(start) == (0, row)


@pytest.mark.parametrize("reader", IMPLEMENTATIONS)
@pytest.mark.parametrize("tile,column,row", GRID)
def test_padded_quad_has_exact_corners_traversal_area_and_pixel_margins(reader, tile, column, row):
    expected = [
        [column + 1 / 64, row + 1 / 64],
        [column + 63 / 64, row + 1 / 64],
        [column + 63 / 64, row + 63 / 64],
        [column + 1 / 64, row + 63 / 64],
    ]
    quad = reader.tile_quad(tile, size=1024, padding=16)
    assert quad == expected  # bottom-left, bottom-right, top-right, top-left
    assert reader.tile_quad(tile, size=2048, padding=32) == expected

    # Scalar shoelace oracle: no production area/UV validator participates.
    twice_area = sum(
        quad[i][0] * quad[(i + 1) % 4][1]
        - quad[(i + 1) % 4][0] * quad[i][1]
        for i in range(4)
    )
    assert twice_area / 2 == (31 / 32) ** 2 > 0
    assert [(quad[i][0] - column) * 1024 for i in (0, 3)] == [16, 16]
    assert [(column + 1 - quad[i][0]) * 1024 for i in (1, 2)] == [16, 16]
    assert [(quad[i][1] - row) * 1024 for i in (0, 1)] == [16, 16]
    assert [(row + 1 - quad[i][1]) * 1024 for i in (2, 3)] == [16, 16]


@pytest.mark.parametrize("reader", IMPLEMENTATIONS)
@pytest.mark.parametrize("tile,column,row", GRID)
def test_zero_padding_returns_exact_unit_tile_corners(reader, tile, column, row):
    assert reader.tile_quad(tile, size=1024, padding=0) == [
        [column, row], [column + 1, row],
        [column + 1, row + 1], [column, row + 1],
    ]


@pytest.mark.parametrize("reader", IMPLEMENTATIONS)
@pytest.mark.parametrize("tile,column,row", GRID)
def test_quad_calls_own_fresh_outer_and_corner_lists(reader, tile, column, row):
    expected = [
        [column + 1 / 64, row + 1 / 64],
        [column + 63 / 64, row + 1 / 64],
        [column + 63 / 64, row + 63 / 64],
        [column + 1 / 64, row + 63 / 64],
    ]
    first = reader.tile_quad(tile, 1024, 16)
    second = reader.tile_quad(tile, 1024, 16)
    assert isinstance(first, list) and isinstance(second, list)
    assert first is not second
    assert len({id(corner) for corner in first + second}) == 8
    assert all(isinstance(corner, list) for corner in first + second)
    for corner in first:
        corner[0] = -123
    first.append([999, 999])
    assert second == expected
    assert reader.tile_quad(tile, 1024, 16) == expected


@pytest.mark.parametrize("reader", IMPLEMENTATIONS)
@pytest.mark.parametrize("method", ["tile_origin", "tile_quad"])
@pytest.mark.parametrize("tile", [1000, 1101, True, 1001.0, "1001", None])
def test_invalid_tile_raises_the_existing_value_error(reader, method, tile):
    args = () if method == "tile_origin" else (1024, 16)
    with pytest.raises(ValueError, match=r"UDIM must be 1001\.\.1100"):
        getattr(reader, method)(tile, *args)
