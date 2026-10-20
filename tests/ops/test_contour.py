"""rebuild_by_contour and the numpy prism extrusion (#338, D108, D131, D082). All meshes are SYNTHETIC."""
import math

import numpy as np
import pytest
import shapely

from dt_ai.ops import rebuild_by_contour
from dt_ai.ops.contour import ExtrudeBackend, NumpyExtrude, extrude_polygon
from dt_ai.ops.invariants import Mesh, border_edges, winding_number
from dt_ai.ops.silhouette import SILHOUETTE_MAX_M, VIEWS, silhouette_deviations
from tests.ops.test_invariants import box, quad
from tests.ops.test_primitive import join

SQUARE = shapely.Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
L_SHAPE = shapely.Polygon([(0, 0), (4, 0), (4, 0.3), (0.3, 0.3), (0.3, 3), (0, 3)])
WITH_HOLE = shapely.Polygon([(0, 0), (5, 0), (5, 4), (0, 4)], [[(1, 1), (1, 3), (4, 3), (4, 1)]])
COLLINEAR = shapely.Polygon([(0, 0), (1, 0), (2, 0), (2, 1), (0, 1)])       # (1, 0) lies on the bottom edge
CASES = {"square": SQUARE, "l_shape": L_SHAPE, "hole": WITH_HOLE, "collinear": COLLINEAR}


def signed_volume(mesh: Mesh) -> float:
    a, b, c = (mesh.corners()[:, i] for i in range(3))
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)


def outward_points(mesh: Mesh, offset=1e-3) -> np.ndarray:
    tri = mesh.corners()
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return tri.mean(axis=1) + n / np.linalg.norm(n, axis=1)[:, None] * offset


def assert_closed_outward(mesh: Mesh, expected_volume: float):
    assert len(border_edges(mesh)) == 0
    vol = signed_volume(mesh)
    assert vol > 0
    assert vol == pytest.approx(expected_volume, rel=1e-6)
    assert np.abs(winding_number(outward_points(mesh), mesh)).max() < 0.5


def orient_convex(v, tris):
    """Hand-made convex solid: turn every triangle so its normal points away from the centre."""
    v = np.asarray(v, float)
    centre = v.mean(axis=0)
    out = []
    for a, b, c in tris:
        n = np.cross(v[b] - v[a], v[c] - v[a])
        out.append((a, b, c) if n @ (v[[a, b, c]].mean(axis=0) - centre) > 0 else (a, c, b))
    return Mesh(v, np.array(out))


def gable(width=6.0, depth=4.0, eaves=0.0, ridge=2.0):
    """A sloped roof: triangle profile in x-z, run along y."""
    v = [(0, 0, eaves), (width, 0, eaves), (width / 2, 0, ridge),
         (0, depth, eaves), (width, depth, eaves), (width / 2, depth, ridge)]
    tris = [(0, 1, 2), (3, 4, 5), (0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4), (2, 0, 3), (2, 3, 5)]
    return orient_convex(v, tris)


def l_wall_with_detail():
    """An L-shaped wall 3 m high as two touching boxes, plus a hidden inner detail box (extra faces)."""
    return join(box((0, 0, 0), (4, 0.3, 3)), box((0, 0.3, 0), (0.3, 3, 3)), box((0.1, 0.1, 1), (0.2, 0.2, 2)))


# ---- the extrusion backend ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("axis", [2, 1, 0])
def test_extrusion_is_closed_outward_with_area_times_height(name, axis):
    polygon = CASES[name]
    mesh = extrude_polygon(polygon, axis, base_m=-1.25, height_m=2.5)
    assert_closed_outward(mesh, polygon.area * 2.5)
    span = mesh.vertices[:, axis]
    assert span.min() == pytest.approx(-1.25) and span.max() == pytest.approx(1.25)


def test_default_backend_satisfies_the_adapter_protocol():
    assert isinstance(NumpyExtrude(), ExtrudeBackend)

    class Recorder:
        def __init__(self):
            self.calls = []

        def __call__(self, polygon, axis, base_m, height_m):
            self.calls.append((polygon.area, axis, base_m, height_m))
            return NumpyExtrude()(polygon, axis, base_m, height_m)

    rec = Recorder()
    assert isinstance(rec, ExtrudeBackend)
    r = rebuild_by_contour({"p": box((0, 0, 0), (2, 2, 3))}, "p", backend=rec)
    assert r.applied and rec.calls == [(pytest.approx(4.0), 2, 0.0, 3.0)]


def test_generated_star_polygons_with_holes_extrude_closed():
    """Probe: 60 random star-shaped polygons (some with a hole) in all three views stay closed with exact volume."""
    rng = np.random.default_rng(338)
    done = 0
    for k in range(60):
        n = int(rng.integers(3, 14))
        ang = np.sort(rng.uniform(0, 2 * np.pi, n))
        rad = rng.uniform(1.0, 3.0, n)
        outer = shapely.Polygon(np.c_[rad * np.cos(ang), rad * np.sin(ang)])
        if not outer.is_valid or outer.area < 1e-3:
            continue
        holes = []
        if k % 2:
            hole = shapely.Point(0, 0).buffer(0.4, 3)
            if outer.contains(hole.buffer(0.01)):
                holes = [list(hole.exterior.coords)]
        polygon = shapely.Polygon(outer.exterior.coords, holes)
        axis = k % 3
        assert_closed_outward(extrude_polygon(polygon, axis, 0.0, 1.7), polygon.area * 1.7)
        done += 1
    assert done >= 40


def test_generated_box_unions_are_rebuilt_within_the_silhouette_limit():
    """Probe: 25 random unions of 2-3 overlapping boxes (one footprint, common height): applied, closed, within 0.07 m."""
    rng = np.random.default_rng(1338)
    applied = 0
    for _ in range(25):
        h = float(rng.uniform(0.5, 4.0))
        boxes, prints = [], []
        x, y = 0.0, 0.0
        for _ in range(int(rng.integers(2, 4))):
            sx, sy = rng.uniform(0.3, 3.0, 2)
            boxes.append(box((x, y, 0), (x + sx, y + sy, h)))
            prints.append(shapely.box(x, y, x + sx, y + sy))
            x, y = x + sx * rng.uniform(0.2, 0.8), y + sy * rng.uniform(0.2, 0.8)       # overlap the next box
        source = join(*boxes)
        r = rebuild_by_contour({"p": source}, "p")
        assert r.applied, r.question
        area = shapely.union_all(prints).area
        assert_closed_outward(r.scene["p"], area * h)
        assert max(r.notes["deviations_m"].values()) <= SILHOUETTE_MAX_M
        applied += 1
    assert applied == 25


def test_extrusion_rejects_bad_input():
    with pytest.raises(ValueError):
        extrude_polygon(shapely.Polygon([(0, 0), (1, 1), (1, 0), (0, 1)]), 2, 0, 1)        # bow-tie
    with pytest.raises(ValueError):
        extrude_polygon(SQUARE, 3, 0, 1)
    with pytest.raises(ValueError):
        extrude_polygon(SQUARE, 2, 0, 0)


# ---- the operation -----------------------------------------------------------------------------------------------

def test_l_wall_is_rebuilt_by_its_plan_contour_with_fewer_triangles():
    source = l_wall_with_detail()
    scene = {"wall": source}
    r = rebuild_by_contour(scene, "wall")
    assert r.applied and r.report.passed and r.operation == "contour_rebuild"
    new = r.scene["wall"]
    assert_closed_outward(new, L_SHAPE.area * 3)
    dev = silhouette_deviations(source, new)
    print(f"l_wall: tris {len(source.triangles)} -> {len(new.triangles)}, deviations {dev}")
    assert max(dev.values()) <= SILHOUETTE_MAX_M
    assert len(new.triangles) < len(source.triangles)
    n = r.notes
    assert (n["faces_before"], n["faces_after"]) == (len(source.triangles), len(new.triangles))
    assert n["view"] == "top" and n["base_m"] == 0.0 and n["height_m"] == 3.0
    assert n["contour_area_m2"] == pytest.approx(L_SHAPE.area) and n["pieces"] == 1
    assert set(n["deviations_m"]) == set(VIEWS) and max(n["deviations_m"].values()) <= SILHOUETTE_MAX_M
    assert scene["wall"] is source                                                    # the input is untouched


def test_courtyard_keeps_its_hole():
    ring = join(box((0, 0, 0), (5, 1, 2)), box((0, 3, 0), (5, 4, 2)), box((0, 1, 0), (1, 3, 2)), box((4, 1, 0), (5, 3, 2)))
    r = rebuild_by_contour({"c": ring}, "c")
    assert r.applied, r.question
    assert_closed_outward(r.scene["c"], WITH_HOLE.area * 2)
    assert r.notes["contour_area_m2"] == pytest.approx(14.0)


def test_gable_rebuilt_in_the_front_view():
    roof = gable()
    r = rebuild_by_contour({"roof": roof}, "roof", view="front")
    assert r.applied, r.question
    assert_closed_outward(r.scene["roof"], 6 * 2 / 2 * 4)
    assert max(r.notes["deviations_m"].values()) <= SILHOUETTE_MAX_M
    assert r.notes["base_m"] == 0.0 and r.notes["height_m"] == 4.0


def test_explicit_base_and_height_are_used_and_reported():
    r = rebuild_by_contour({"p": box((0, 0, 0), (2, 2, 3))}, "p", height_m=3.04, base_m=-0.02)
    assert r.applied, r.question
    z = r.scene["p"].vertices[:, 2]
    assert (z.min(), z.max()) == (pytest.approx(-0.02), pytest.approx(3.02))
    assert r.notes["base_m"] == -0.02 and r.notes["height_m"] == 3.04


def test_caller_contour_replaces_the_measured_silhouette():
    r = rebuild_by_contour({"p": l_wall_with_detail()}, "p", contour=list(L_SHAPE.exterior.coords)[:-1])
    assert r.applied, r.question
    assert r.notes["contour_area_m2"] == pytest.approx(L_SHAPE.area)


def test_area_exactly_at_the_threshold_is_not_refused():
    """A 10 x 10 mm post: contour area 1e-4 m2 is the limit, not below it."""
    r = rebuild_by_contour({"post": box((0, 0, 0), (0.01, 0.01, 1))}, "post")
    assert r.applied, r.question
    assert r.notes["contour_area_m2"] == pytest.approx(1e-4)


def test_disjoint_footprint_needs_allow_multi():
    two = join(box((0, 0, 0), (1, 1, 2)), box((3, 0, 0), (4, 1, 2)))
    scene = {"p": two}
    refused = rebuild_by_contour(scene, "p")
    assert not refused.applied and refused.scene is scene and "allow_multi" in refused.question
    r = rebuild_by_contour(scene, "p", allow_multi=True)
    assert r.applied, r.question
    assert r.notes["pieces"] == 2
    assert_closed_outward(r.scene["p"], 2 * 2.0)


# ---- fail-closed refusals ----------------------------------------------------------------------------------------

def refused(scene, part="p", **kwargs):
    r = rebuild_by_contour(scene, part, **kwargs)
    assert not r.applied and r.scene is scene and r.question and r.operation == "contour_rebuild"
    print(f"refusal {kwargs}: {r.question}")
    return r


def test_unknown_view_is_refused():
    r = refused({"p": box((0, 0, 0), (1, 1, 1))}, view="bottom")
    assert "bottom" in r.question and r.report is None


def test_empty_part_is_refused():
    refused({"p": Mesh(np.zeros((0, 3)), np.zeros((0, 3), dtype=int))})


@pytest.mark.parametrize("mesh", [
    Mesh(np.array([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], float), np.array([(0, 1, 2), (0, 2, 3)])),   # edge-on
    box((0, 0, 0), (0.005, 0.005, 1)),                                                                         # 25 mm2
])
def test_degenerate_contour_area_is_refused(mesh):
    r = refused({"p": mesh})
    assert "area" in r.question


@pytest.mark.parametrize("height", [0.0, -1.0, math.nan, math.inf, -math.inf])
def test_bad_height_is_refused(height):
    refused({"p": box((0, 0, 0), (1, 1, 1))}, height_m=height)


@pytest.mark.parametrize("base", [math.nan, math.inf])
def test_bad_base_is_refused(base):
    refused({"p": box((0, 0, 0), (1, 1, 1))}, base_m=base)


def test_flat_part_without_height_is_refused():
    r = refused({"p": quad(0.5)})
    assert "height_m" in r.question


def test_self_intersecting_contour_is_refused_unless_allow_multi():
    bow = [(0, 0), (1, 1), (1, 0), (0, 1)]
    r = refused({"p": box((0, 0, 0), (1, 1, 1))}, contour=bow)
    assert "2 pieces" in r.question and "allow_multi" in r.question


def test_non_finite_contour_is_refused():
    refused({"p": box((0, 0, 0), (1, 1, 1))}, contour=[(0, 0), (1, 0), (math.nan, 1)])


def test_sloped_roof_extruded_in_plan_is_refused_with_the_worst_view():
    r = refused({"p": gable()})
    assert "front" in r.question and "mm" in r.question
    assert r.notes["deviations_m"]["front"] > SILHOUETTE_MAX_M


def test_deviation_at_the_limit_passes_and_above_it_is_refused():
    base = box((0, 0, 0), (2, 2, 3))
    assert rebuild_by_contour({"p": base}, "p", height_m=3 + SILHOUETTE_MAX_M).applied
    r = refused({"p": base}, height_m=3 + SILHOUETTE_MAX_M + 0.02)
    assert "front" in r.question or "side" in r.question


def test_prism_breaking_an_invariant_is_rolled_back():
    """The album height lifts the top 3 mm under a neighbour's co-directional face: z-fighting, rolled back."""
    scene = {"p": box((0, 0, 0), (2, 2, 3)), "slab": box((0.5, 0.5, 3.03), (1.5, 1.5, 3.053))}
    r = rebuild_by_contour(scene, "p", height_m=3.05)
    assert not r.applied and r.scene is scene and r.report is not None
    assert "no_close_overlap" in r.question and "rolled back" in r.question
    print(f"rollback: {r.question}")


def test_unknown_part_raises_like_run_operation():
    with pytest.raises(ValueError):
        rebuild_by_contour({"p": box((0, 0, 0), (1, 1, 1))}, "q")
