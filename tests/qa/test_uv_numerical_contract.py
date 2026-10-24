"""Independent synthetic UV math characterization, before any consolidation.

new-case: independent numerical characterization of UV edge densities and signed area.

Existing test_uv.py covers UDIM/margins and square profile density limits, not
these numerical contracts. Expectations below come from scalar lengths/areas,
never from the generator's UV helpers. This is not delivery approval. Malformed
arrays, nonfinite inputs, size policies and exact tolerance boundaries are out
of scope; the tiny finite witnesses are deliberately far from 1e-9.
"""
from copy import deepcopy
import math

import numpy as np
import pytest

from twinqa.uv import edge_densities, signed_area


RECT_XYZ = [[0, 0, 0], [3, 0, 0], [3, 0, 4], [0, 0, 4]]
RECT_UV = [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]
# World sides 3, 4; texture sides 600, 1200 pixels. Area = 0.5 * 1.
RECT_DENSITIES = [200, 300, 200, 300]

SLANTED_XYZ = [[0, 0, 0], [3, 0, 4], [3, 12, 4]]
SLANTED_UV = [[0, 0], [0.5, 0], [0.5, 1]]
# World sides 5 (3-4-5, NOT XY length 3), 12, 13 (5-12-13).
# UV sides 1/2, 1, sqrt(5)/2; closure has a unique density.
SLANTED_DENSITIES = [120, 100, 600 * math.sqrt(5) / 13]


@pytest.mark.parametrize("polygon", ["rectangle", "slanted"])
@pytest.mark.parametrize("reverse", [False, True])
def test_all_cyclic_starts_and_both_windings(polygon, reverse):
    if polygon == "rectangle":
        xyz, uv = deepcopy(RECT_XYZ), deepcopy(RECT_UV)
        expected = RECT_DENSITIES[:]
        area = 0.5
    else:
        xyz, uv = deepcopy(SLANTED_XYZ), deepcopy(SLANTED_UV)
        expected = SLANTED_DENSITIES[:]
        area = 0.25  # Half of a 0.5 by 1 rectangle.
    if reverse:
        xyz.reverse()
        uv.reverse()
        # Reversing vertices starts with the old penultimate edge; the old
        # closing edge remains last (not a simple reversal of edge values).
        expected = expected[-2::-1] + expected[-1:]
        area = -area
    for shift in range(len(xyz)):
        vertices = xyz[shift:] + xyz[:shift]
        coords = uv[shift:] + uv[:shift]
        before = deepcopy((vertices, coords))
        values = edge_densities(vertices, coords, 1200)
        assert len(values) == len(vertices)  # Includes LAST-to-FIRST.
        assert values == pytest.approx(expected[shift:] + expected[:shift])
        assert signed_area(coords) == pytest.approx(area)
        assert (vertices, coords) == before


@pytest.mark.parametrize(
    "world_offset,uv_offset,world_scale,size,expected",
    [
        ((8, -16, 32), (0, 0), 1, 1200, [200, 300, 200, 300]),
        ((0, 0, 0), (4, -8), 1, 1200, [200, 300, 200, 300]),
        ((8, -16, 32), (4, -8), 1, 1200, [200, 300, 200, 300]),
        ((0, 0, 0), (0, 0), 2, 1200, [100, 150, 100, 150]),
        ((0, 0, 0), (0, 0), 1, 2400, [400, 600, 400, 600]),
    ],
)
def test_exact_translations_and_scale_laws(
    world_offset, uv_offset, world_scale, size, expected
):
    xyz = [[world_scale * c + d for c, d in zip(p, world_offset)] for p in RECT_XYZ]
    uv = [[c + d for c, d in zip(p, uv_offset)] for p in RECT_UV]
    before = deepcopy((xyz, uv))
    assert edge_densities(xyz, uv, size) == pytest.approx(expected)
    assert signed_area(uv) == pytest.approx(0.5)
    assert (xyz, uv) == before


@pytest.mark.parametrize("as_array", [False, True])
def test_density_preserves_mutable_inputs(as_array):
    xyz, uv = deepcopy(SLANTED_XYZ), deepcopy(SLANTED_UV)
    if as_array:
        xyz, uv = np.array(xyz, dtype=float), np.array(uv, dtype=float)
    before_xyz, before_uv = deepcopy(xyz), deepcopy(uv)
    assert edge_densities(xyz, uv, 1200) == pytest.approx(SLANTED_DENSITIES)
    np.testing.assert_array_equal(xyz, before_xyz)
    np.testing.assert_array_equal(uv, before_uv)


@pytest.mark.parametrize("edge_length", [0.0, 2**-32])
@pytest.mark.parametrize("shift", range(3))
@pytest.mark.parametrize("as_array", [False, True])
def test_zero_and_clearly_subthreshold_edges_raise_without_mutation(
    edge_length, shift, as_array
):
    # 2**-32 ~= 2.33e-10 is finite and comfortably below 1e-9.
    xyz = [[0, 0, 0], [edge_length, 0, 0], [0, 3, 4]]
    uv = [[0, 0], [0.5, 0], [0, 1]]
    xyz, uv = xyz[shift:] + xyz[:shift], uv[shift:] + uv[:shift]
    if as_array:
        xyz, uv = np.array(xyz, dtype=float), np.array(uv, dtype=float)
    before_xyz, before_uv = deepcopy(xyz), deepcopy(uv)
    with pytest.raises(ValueError, match="Degenerate surface edge"):
        edge_densities(xyz, uv, 1200)
    np.testing.assert_array_equal(xyz, before_xyz)
    np.testing.assert_array_equal(uv, before_uv)


def test_clearly_superthreshold_finite_edge_has_analytic_density():
    # 2**-28 ~= 3.73e-9, safely above 1e-9, no cancellation at the origin.
    xyz = [[0, 0, 0], [2**-28, 0, 0], [0, 3, 4]]
    uv = [[0, 0], [0.5, 0], [0, 1]]
    before = deepcopy((xyz, uv))
    values = edge_densities(xyz, uv, 1200)
    expected = [600 * 2**28, 600 * math.sqrt(5) / math.sqrt(25 + 2**-56), 240]
    assert len(values) == 3
    assert all(math.isfinite(value) for value in values)
    assert values == pytest.approx(expected)
    assert (xyz, uv) == before
