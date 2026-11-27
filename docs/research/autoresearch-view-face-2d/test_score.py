import numpy as np

from score import decide, face_score, mesh_edges


def test_same_asymmetric_lines_fit_after_horizontal_and_top_translation():
    view = np.zeros((38, 35), bool)
    view[1:31, 4] = view[30, 4:28] = view[23:31, 27] = True
    model = np.zeros((48, 55), bool)
    model[5:43, 10:45] = view
    assert face_score(view, model, model, 0) == 1
    assert face_score(view[:, ::-1], model, model, 0) < 0.85


def test_empty_and_tied_candidates_abstain():
    empty = np.zeros((12, 15), bool)
    assert face_score(empty, ~empty, ~empty, 0) == -1
    assert face_score(~empty, empty, empty, 0) == -1
    assert decide({0: 0.9, 180: 0.9}) is None
    assert decide({0: 0.29, 180: 0.0}) is None
    assert decide({0: 0.9, 180: 0.7}) == 0


def test_uniform_mesh_has_no_artificial_edge_at_array_boundary():
    depth = np.ones((8, 15), dtype=float)
    normals = np.zeros((*depth.shape, 3))
    normals[..., 0] = 1
    assert not mesh_edges(depth, normals).any()
    depth[:, 6:9] += 0.20
    assert mesh_edges(depth, normals).sum() == 16


def test_shifting_a_line_beyond_tolerance_reduces_fit():
    view = np.zeros((12, 20), bool)
    view[2:12, 0] = view[2:12, 6] = True
    moved = view.copy()
    moved[:, 6] = False
    moved[2:12, 12] = True
    assert face_score(view, view, view, 0) == 1
    assert face_score(view, moved, moved, 0) < 0.75
