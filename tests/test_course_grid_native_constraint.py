"""new-case: constrained triangulation must consider native UV representability."""
import pytest
from tools.materials.course_grid_native import triangulate_conforming_polygon


def test_native_constraint_selects_another_complete_diagonal_not_partial_output():
    points = [[0,0],[2,0],[2,1],[0,1]]
    triangles = triangulate_conforming_polygon(points, triangle_allowed=lambda t: t != [0,1,2])
    assert {tuple(t) for t in triangles} == {(0,1,3),(1,2,3)}
    assert {i for t in triangles for i in t} == {0,1,2,3}


def test_native_constraint_refuses_when_no_complete_diagonal_is_encodable():
    with pytest.raises(ValueError, match='unrepresentable'):
        triangulate_conforming_polygon([[0,0],[2,0],[2,1],[0,1]], triangle_allowed=lambda t: False)


@pytest.mark.parametrize('value', [None, 0, 1, 'yes', float('nan')])
def test_native_constraint_requires_literal_bool_result(value):
    with pytest.raises(ValueError, match='triangle_allowed'):
        triangulate_conforming_polygon([[0,0],[2,0],[0,1]], triangle_allowed=lambda t: value)
