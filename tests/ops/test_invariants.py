"""Visibility invariants of the operation kernel (cloud card C3, D115). All meshes are SYNTHETIC."""
import numpy as np
import pytest

from dt_ai.ops.invariants import (
    Context, Mesh, border_edges, check_operation, distance_to_surface, no_close_overlap, no_see_through_hole,
    no_visible_back_faces, open_borders_hidden, winding_number,
)

# box faces as vertex quads of the corner numbering below; orientation is fixed by the outward normal
_CORNERS = [(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)]
_QUADS = {"bottom": (0, 1, 3, 2), "top": (4, 5, 7, 6), "front": (0, 1, 5, 4), "back": (2, 3, 7, 6),
          "left": (0, 2, 6, 4), "right": (1, 3, 7, 5)}


def box(lo, hi, drop=(), flip=False):
    """Closed box lo..hi, outward normals; `drop` removes faces by name, `flip` turns all normals inwards."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    v = lo + np.array(_CORNERS, float) * (hi - lo)
    centre = (lo + hi) / 2
    tris = []
    for name, q in _QUADS.items():
        if name in drop:
            continue
        a, b, c, d = q
        for tri in ((a, b, c), (a, c, d)):
            p = v[list(tri)]
            out = np.cross(p[1] - p[0], p[2] - p[0]) @ (p.mean(0) - centre) > 0
            tris.append(tri if out != flip else (tri[0], tri[2], tri[1]))
    return Mesh(v, np.array(tris))


def quad(z, size=1.0, normal_up=True, origin=(0.0, 0.0)):
    """Horizontal quad at height z; normal up or down."""
    x, y = origin
    v = np.array([(x, y, z), (x + size, y, z), (x + size, y + size, z), (x, y + size, z)], float)
    t = [(0, 1, 2), (0, 2, 3)] if normal_up else [(0, 2, 1), (0, 3, 2)]
    return Mesh(v, np.array(t))


def wall_plane(y, hole=False):
    """Vertical single-sided wall at y facing -y, 4 x 4 m; `hole` drops the two triangles of its middle."""
    xs, zs = np.linspace(0, 4, 5), np.linspace(0, 4, 5)
    v = np.array([(x, y, z) for z in zs for x in xs], float)
    tris, quad_ids = [], []
    for j in range(4):
        for i in range(4):
            a, b, c, d = j * 5 + i, j * 5 + i + 1, (j + 1) * 5 + i + 1, (j + 1) * 5 + i
            quad_ids.append((i, j))
            tris += [(a, b, c), (a, c, d)]       # normal -y
    keep = [k for k, (i, j) in enumerate(quad_ids) if not (hole and (i, j) in {(1, 1), (2, 1), (1, 2), (2, 2)})]
    return Mesh(v, np.array([t for k in keep for t in tris[2 * k:2 * k + 2]]))


# ---- helpers ---------------------------------------------------------------------------------------------------

def test_winding_and_distance_on_a_cube():
    cube = box((0, 0, 0), (1, 1, 1))
    pts = np.array([[0.5, 0.5, 0.5], [2, 2, 2], [0.5, 0.5, 0.995]])
    w = winding_number(pts, cube)
    assert w[0] == pytest.approx(1, abs=1e-6) and w[1] == pytest.approx(0, abs=1e-6)
    assert distance_to_surface(pts, cube) == pytest.approx([0.5, np.sqrt(3), 0.005], abs=1e-9)


def test_border_edges_of_closed_and_open_boxes():
    assert len(border_edges(box((0, 0, 0), (1, 1, 1)))) == 0
    assert len(border_edges(box((0, 0, 0), (1, 1, 1), drop=("bottom",)))) == 4
    assert len(border_edges(quad(0))) == 4


def test_mesh_rejects_bad_input():
    with pytest.raises(ValueError):
        Mesh(np.zeros((3, 2)), np.zeros((1, 3), int))
    with pytest.raises(ValueError):
        Mesh(np.zeros((3, 3)), np.array([[0, 1, 5]]))


# ---- (1) open borders hidden ----------------------------------------------------------------------------------

def test_decor_embedded_into_wall_with_inner_face_deleted_is_hidden():
    wall = box((0, 0, 0), (4, 0.3, 3))
    decor = box((1, -0.1, 1), (2, 0.015 + 0.0, 2), drop=("back",))   # sunk 15 mm into the wall, inner face gone
    scene = {"wall": wall, "decor": decor}
    assert open_borders_hidden(scene, "decor", Context(embed_min_m=0.010)).passed


@pytest.mark.parametrize("depth,passed", [(0.015, True), (0.0101, True), (0.005, False), (0.0, False), (-0.02, False)])
def test_embed_depth_threshold(depth, passed):
    wall = box((0, 0, 0), (4, 0.3, 3))
    # the decor's open "back" face lies `depth` below the wall's front surface (y = 0)
    decor = box((1, -0.2, 1), (2, depth, 2), drop=("back",))
    r = open_borders_hidden({"wall": wall, "decor": decor}, "decor", Context(embed_min_m=0.010))
    assert r.passed is passed


def test_border_outside_every_neighbour_fails_and_names_the_edge():
    scene = {"wall": box((0, 0, 0), (4, 0.3, 3)), "decor": box((1, 2, 1), (2, 3, 2), drop=("back",))}
    r = open_borders_hidden(scene, "decor")
    assert not r.passed and r.count == 4 and "decor: edge" in r.offenders[0]


def test_border_below_ground_and_opacity_part_are_hidden():
    sunk = box((0, 0, -1), (1, 1, 2), drop=("bottom",))      # open bottom edges at z = -1
    assert open_borders_hidden({"b": sunk}, "b", Context(ground_z=0.0)).passed
    assert open_borders_hidden({"b": sunk}, "b", Context(ground_z=-1.0)).passed       # exactly at the Ground
    assert not open_borders_hidden({"b": sunk}, "b", Context(ground_z=-2.0)).passed   # above the Ground
    assert not open_borders_hidden({"b": sunk}, "b").passed                           # no Ground given
    rail = {"rail": quad(0.0)}
    assert not open_borders_hidden(rail, "rail").passed
    assert open_borders_hidden(rail, "rail", Context(opacity_parts=frozenset({"rail"}))).passed


# ---- (2) see-through holes -------------------------------------------------------------------------------------

def test_deleting_a_face_covered_by_a_neighbour_is_not_a_hole():
    wall = wall_plane(0.0)
    behind = wall_plane(0.5)                                  # a second wall behind the first covers the hole
    before = {"wall": wall, "behind": behind}
    after = {"wall": wall_plane(0.0, hole=True), "behind": behind}
    assert no_see_through_hole(before, after).passed


def test_deleting_an_uncovered_face_is_a_hole():
    before = {"wall": wall_plane(0.0)}
    after = {"wall": wall_plane(0.0, hole=True)}
    r = no_see_through_hole(before, after)
    assert not r.passed and r.count > 0 and "pixels lost" in r.offenders[0]


def test_hole_check_tolerates_a_stated_number_of_pixels():
    before, after = {"w": wall_plane(0.0)}, {"w": wall_plane(0.0, hole=True)}
    lost = no_see_through_hole(before, after).count
    assert no_see_through_hole(before, after, Context(lost_pixels_max=lost)).passed


# ---- (3) back faces ---------------------------------------------------------------------------------------------

def test_closed_cube_shows_no_back_face():
    r = no_visible_back_faces({"c": box((0, 0, 0), (1, 1, 1))})
    assert r.passed and r.count == 0


def test_flipped_normals_are_seen():
    r = no_visible_back_faces({"c": box((0, 0, 0), (1, 1, 1), flip=True)})
    assert not r.passed and r.count > 0 and "['c']" in r.offenders[0]


def test_gnawed_cube_shows_the_inside():
    """A face deleted from a closed shell: no pixel is lost (the far wall is behind it) but the inside is visible."""
    whole, gnawed = {"c": box((0, 0, 0), (1, 1, 1))}, {"c": box((0, 0, 0), (1, 1, 1), drop=("top",))}
    assert no_see_through_hole(whole, gnawed).passed
    assert not no_visible_back_faces(gnawed).passed


def test_opacity_part_may_show_its_back():
    scene = {"plane": quad(0.0, normal_up=False)}
    assert not no_visible_back_faces(scene).passed     # seen from above, a down-facing plane is a back face
    assert no_visible_back_faces(scene, Context(opacity_parts=frozenset({"plane"}))).passed


# ---- (4) close overlap ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("gap_m,passed", [(0.0, False), (0.002, False), (0.0049, False), (0.006, True), (0.010, True)])
def test_co_directional_faces_closer_than_5mm_fail(gap_m, passed):
    scene = {"a": quad(0.0), "b": quad(gap_m)}
    assert no_close_overlap(scene).passed is passed


def test_opposite_and_side_by_side_faces_are_not_z_fighting():
    assert no_close_overlap({"a": quad(0.0), "b": quad(0.002, normal_up=False)}).passed
    assert no_close_overlap({"a": quad(0.0), "b": quad(0.002, origin=(1.0, 0.0))}).passed


def test_overlap_pair_must_touch_a_watched_part():
    scene = {"a": quad(0.0), "b": quad(0.002), "c": quad(5.0)}
    assert not no_close_overlap(scene, parts=["a"]).passed
    assert no_close_overlap(scene, parts=["c"]).passed


# ---- the operation gate -----------------------------------------------------------------------------------------

def test_good_embed_operation_passes_every_invariant():
    wall = box((0, 0, 0), (4, 0.3, 3))
    before = {"wall": wall, "decor": box((1, -0.1, 1), (2, 0.015, 2))}
    after = {"wall": wall, "decor": box((1, -0.1, 1), (2, 0.015, 2), drop=("back",))}
    report = check_operation(before, after, ["decor"], Context(embed_min_m=0.010))
    assert report.passed and [r.name for r in report.results] == [
        "open_borders_hidden", "no_see_through_hole", "no_visible_back_faces", "no_close_overlap"]
    assert report.to_dict()["passed"] is True


def test_gnawed_operation_is_caught_and_listed():
    whole = box((0, 0, 0), (1, 1, 1))
    gnawed = box((0, 0, 0), (1, 1, 1), drop=("top",))
    report = check_operation({"p": whole}, {"p": gnawed}, ["p"])
    assert not report.passed
    assert {r.name for r in report.broken} == {"open_borders_hidden", "no_visible_back_faces"}


def test_operation_without_before_skips_the_hole_check_and_unknown_part_is_an_error():
    scene = {"p": box((0, 0, 0), (1, 1, 1))}
    assert "no_see_through_hole" not in [r.name for r in check_operation(None, scene, ["p"]).results]
    with pytest.raises(ValueError):
        check_operation(None, scene, ["missing"])
