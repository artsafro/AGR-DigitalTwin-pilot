"""Opt-in operation-count regression, not a default-suite timing assertion.

RED under A and GREEN under B. Collinear input exits before edge tests, isolating
normal selection without accepting a mesh or claiming a production defect.
"""
import pytest
from technical_library.mesh_audit import core


class Coordinate(float):
    subtractions = 0

    def __sub__(self, other):
        type(self).subtractions += 1
        return float(self) - float(other)


@pytest.mark.parametrize('n', [4, 8, 16, 32])
def test_linear_normal_selection_work(n):
    poly = [tuple(Coordinate(c) for c in (i, 2*i, 3*i)) for i in range(n)]
    Coordinate.subtractions = 0
    assert core._has_proper_crossing(poly) is False
    assert Coordinate.subtractions <= 6*n + 3
