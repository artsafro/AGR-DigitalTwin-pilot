"""#1619 63B v007 whole-model gate: an opening rim is classified by structure, not by size (review P1, PR #1661).

A rim = the open back of a reveal tube: a closed, planar boundary loop whose every face is a reveal face,
perpendicular to the loop plane. A hole left by a deleted wall quad is bounded by facade faces coplanar with the
loop, so it stays an open boundary whatever its size. Synthetic geometry (wall y=0, reveal depth 0.3 m).

Pattern: n/a | new-case: structural opening-rim classifier for the whole-model open-boundary gate (tests).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("gates63b", ROOT / "jobs" / "POLY63-B" / "hooks" / "gates63b.py")
gates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gates)

WALL_N = (0.0, -1.0, 0.0)


def _ring(pts):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def test_reveal_back_rim_is_a_rim():
    pts = [(0, 0.3, 0), (1, 0.3, 0), (1, 0.3, 1.95), (0, 0.3, 1.95)]
    normals = [(0, 0, 1), (-1, 0, 0), (0, 0, -1), (1, 0, 0)]  # sill, jamb, head, jamb faces of the tube
    assert gates.classify_boundary_loop(_ring(pts), normals) == "rim"


def test_small_window_rim_is_a_rim():
    pts = [(0, 0.3, 1.0), (0.6, 0.3, 1.0), (0.6, 0.3, 1.7), (0, 0.3, 1.7)]
    normals = [(0, 0, 1), (-1, 0, 0), (0, 0, -1), (1, 0, 0)]
    assert gates.classify_boundary_loop(_ring(pts), normals) == "rim"


def test_window_over_a_facade_kink_is_a_rim():
    # build 15: windows at (94.11, 32.01) wrap ring-A vertex 58 (8 deg kink), the reveal back is bent, not planar
    k = (0.989, 0.148, 0.0)  # second facade segment direction (8.5 deg)
    p2 = (0.8 + 0.2 * k[0] / k[0], 0.3 + 0.2 * k[1] / k[0], 0.0)
    pts = [(0, 0.3, 0), (0.8, 0.3, 0), p2, (p2[0], p2[1], 1.95), (0.8, 0.3, 1.95), (0, 0.3, 1.95)]
    jamb = (-k[0], -k[1], 0.0)  # right jamb faces back into the opening, perpendicular to segment 2
    normals = [(0, 0, 1), (0, 0, 1), jamb, (0, 0, -1), (0, 0, -1), (1, 0, 0)]
    assert gates.classify_boundary_loop(_ring(pts), normals) == "rim"


def test_deleted_wall_quad_is_open_whatever_its_height():
    for h in (1.95, 0.70, 3.15):
        pts = [(0, 0, 0), (1, 0, 0), (1, 0, h), (0, 0, h)]
        assert gates.classify_boundary_loop(_ring(pts), [WALL_N] * 4) == "open", h


def test_deleted_reveal_face_is_open():
    pts = [(0, 0, 0), (1, 0, 0), (1, 0.3, 0), (1, 0.3, 2), (0, 0.3, 2), (0, 0.3, 0)]
    normals = [WALL_N, (-1, 0, 0), (-1, 0, 0), (0, 0, -1), (1, 0, 0), (1, 0, 0)]
    assert gates.classify_boundary_loop(_ring(pts), normals) == "open"


def test_wall_quad_next_to_an_opening_is_open():
    # deleted wall quad sharing its right edge with a reveal jamb face
    pts = [(0, 0, 0), (1, 0, 0), (1, 0, 2), (0, 0, 2)]
    normals = [WALL_N, (1, 0, 0), WALL_N, WALL_N]
    assert gates.classify_boundary_loop(_ring(pts), normals) == "open"


def test_open_chain_is_open():
    pts = [(0, 0.3, 0), (1, 0.3, 0), (1, 0.3, 2), (0, 0.3, 2)]
    edges = _ring(pts)[:3]
    assert gates.classify_boundary_loop(edges, [(0, 0, 1), (-1, 0, 0), (0, 0, -1)]) == "open"
