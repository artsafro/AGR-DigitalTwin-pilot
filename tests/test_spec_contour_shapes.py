"""Level contour shapes and not-full-height deviations (issue #6). Synthetic data; not a real object."""
import json
import math
import random
import re

import numpy as np
import pytest
import shapely
from shapely.geometry import Point, Polygon

from dt_ai.cli.main import main
from dt_ai.spec import SpecError, SpecStops, extract_spec
from test_spec_extract import OBJECT, Mesh, close

LEVELS = (("L0", 0.0), ("L1", 3.3), ("roof", 6.6))


def flat(mesh, poly, z, up=True):
    """Triangulate a (possibly concave or holed) polygon at height z, facing up or down."""
    for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
        a, b, c = list(tri.exterior.coords)[:3]
        (ux, uy), (vx, vy) = np.subtract(b, a), np.subtract(c, a)
        if (ux * vy - uy * vx > 0) != up:
            b, c = c, b
        mesh.vertices += [[*a, z], [*b, z], [*c, z]]
        n = len(mesh.vertices)
        mesh.triangles.append([n - 3, n - 2, n - 1])


def walls(mesh, contour, z0, z1, boxes=(), extra_u=None, extra_z=()):
    """Vertical walls of a CCW contour from z0 to z1, split so box corners are shared vertices.
    boxes: (wall, u0, u1, bz0, bz1, depth) projections outward from that wall."""
    pts = np.asarray(contour, dtype=float)
    for w in range(len(pts)):
        a, b = pts[w], pts[(w + 1) % len(pts)]
        length = float(np.linalg.norm(b - a))
        us = {0.0, length, *[u for bx in boxes if bx[0] == w for u in bx[1:3]], *(extra_u or {}).get(w, [])}
        zs = {z0, z1, *[z for bx in boxes if bx[0] == w for z in bx[3:5] if z0 < z < z1], *extra_z}
        us, zs = sorted(us), sorted(zs)
        t = (b - a) / length
        cuts = [bx for bx in boxes if bx[0] == w and bx[5] <= 0]  # recesses and holes (depth 0): no wall there
        for u0, u1 in zip(us, us[1:]):
            for za, zb in zip(zs, zs[1:]):
                if any(c[1] <= u0 and u1 <= c[2] and c[3] <= za and zb <= c[4] for c in cuts):
                    continue
                p, q = a + u0 * t, a + u1 * t
                mesh.quad((*p, za), (*q, za), (*q, zb), (*p, zb))
    for w, u0, u1, bz0, bz1, depth in boxes:
        if depth == 0:
            continue
        a, b = pts[w], pts[(w + 1) % len(pts)]
        t = (b - a) / np.linalg.norm(b - a)
        n = np.array([t[1], -t[0]])                      # outward for a CCW contour
        p0, p1 = a + u0 * t, a + u1 * t
        o0, o1 = p0 + depth * n, p1 + depth * n
        mesh.quad((*o0, bz0), (*o1, bz0), (*o1, bz1), (*o0, bz1))   # front
        mesh.quad((*p0, bz1), (*o0, bz1), (*o1, bz1), (*p1, bz1))   # top
        mesh.quad((*p0, bz0), (*p1, bz0), (*o1, bz0), (*o0, bz0))   # bottom
        mesh.quad((*p0, bz0), (*o0, bz0), (*o0, bz1), (*p0, bz1))   # side at u0
        mesh.quad((*o1, bz0), (*p1, bz0), (*p1, bz1), (*o1, bz1))   # side at u1


def prism(contour, boxes=(), height=6.6):
    """One block from 0 to `height` with a flat roof and no parapet."""
    b = Mesh("Body")
    walls(b, contour, 0.0, height, boxes)
    flat(b, Polygon(contour), height, up=True)
    flat(b, Polygon(contour), 0.0, up=False)
    return dump_of(b)


def dump_of(mesh):
    return {"source": "synthetic-shapes", "meshes": [mesh.dump()],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in LEVELS]}


SQUARE10 = [[0, 0], [10, 0], [10, 10], [0, 10]]


def test_b02_like_non_90_corner_niche_and_two_roof_levels():
    lower = [[0, 0], [4, 0], [4, 0.5], [6, 0.5], [6, 0], [12, 0], [12, 6], [9, 9], [0, 9]]
    upper = [[6, 0], [12, 0], [12, 6], [9, 9], [6, 9]]
    b = Mesh("Body")
    walls(b, lower, 0.0, 3.3, extra_u={8: [3.0]})          # vertex at (6, 9) shared with the upper block
    walls(b, upper, 3.3, 6.6)
    flat(b, Polygon(lower).difference(Polygon(upper)), 3.3, up=True)   # lower roof (terrace)
    flat(b, Polygon(upper), 6.6, up=True)
    flat(b, Polygon(lower), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert close(spec.expanded_floors()[0].contour, lower)
    assert close(spec.expanded_floors()[1].contour, upper)
    assert (report["roof"]["plane_m"], spec.roof.parapet_h_m) == (6.6, 0.0)
    assert report["questions"] == []


def test_rounded_corner_is_one_point_with_radius():
    r, n = 1.5, 12
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    contour = [[0, 0], [10, 0], *arc, [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.expanded_floors()[0].contour
    assert len(pts) == 4
    corner = [p for p in pts if len(p) == 3]
    assert len(corner) == 1 and math.dist(corner[0][:2], [10, 10]) <= 0.02
    assert corner[0][2]["r"] == pytest.approx(1.5, abs=0.02)


@pytest.mark.parametrize("deg, kept", [(3.0, False), (7.0, True)])
def test_kinks_over_5_degrees_are_kept(deg, kept):
    y = 10 * math.tan(math.radians(deg))
    contour = [[0, 0], [10, 0], [20, y], [20, 10], [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.expanded_floors()[0].contour
    assert (any(math.dist(p[:2], [10, 0]) < 0.01 for p in pts)) == kept
    assert len(pts) == (5 if kept else 4)


def at(**heights):
    """object.json with contour_at_m: the user names a height of the wall shape per level."""
    return {**OBJECT, "contour_at_m": heights}


def only_question(dump, obj=OBJECT):
    spec, report = extract_spec(dump, obj)
    assert close(spec.expanded_floors()[0].contour, SQUARE10) and close(spec.expanded_floors()[1].contour, SQUARE10)
    assert len(report["questions"]) == 1, report["questions"]
    return report["questions"][0]


def test_plinth_never_changes_the_contour_and_is_a_high_priority_question():
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1)])
    # the storey ends differ (plinth at the bottom): the extractor asks, it does not pick
    with pytest.raises(SpecError, match=r"level L0: no section shape .* shape 1: 101.00 m2 at 0.000-0.600 m"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=2.0))
    assert (q["kind"], q["levels"], q["wall"], q["priority"]) == ("projection", ["L0"], 0, "high")
    assert q["depth_m"] == pytest.approx(0.1, abs=0.01) and q["length_m"] == pytest.approx(10, abs=0.01)


@pytest.mark.parametrize("u1, priority", [(2.9, "normal"), (3.1, "high")])
def test_facade_share_threshold_sets_priority_not_route(u1, priority):
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, u1, 1.0, 1.5, 0.2)]))
    assert q["facade_share"] == pytest.approx((u1 - 2.0) / 10, abs=0.002)
    assert (q["priority"], q["levels"]) == (priority, ["L0"])
    assert q["depth_m"] == pytest.approx(0.2, abs=0.01)


@pytest.mark.parametrize("z1, levels, priority", [(3.2, ["L0"], "normal"), (3.8, ["L0", "L1"], "high")])
def test_two_levels_threshold_sets_priority_not_route(z1, levels, priority):
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 2.8, z1, 0.2)]), at(L0=1.0, L1=5.0))
    assert (q["levels"], q["priority"]) == (levels, priority)


def test_full_height_pilaster_is_in_the_contour_without_a_question():
    spec, report = extract_spec(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 0.0, 3.3, 0.2)]), OBJECT)
    assert close(spec.expanded_floors()[0].contour, [[0, 0], [2, 0], [2, -0.2], [2.5, -0.2], [2.5, 0], [10, 0], [10, 10], [0, 10]],
                 tol=0.01) or close(spec.expanded_floors()[0].contour,
                                    [[2, -0.2], [2.5, -0.2], [2.5, 0], [10, 0], [10, 10], [0, 10], [0, 0], [2, 0]])
    assert close(spec.expanded_floors()[1].contour, SQUARE10)
    assert report["questions"] == []


# --- regressions from Codex review 1 of PR #19 -------------------------------------------------

@pytest.mark.parametrize("bz0, bz1", [(0.2, 3.1), (0.1, 3.2)])
def test_partial_projection_over_most_of_the_storey_never_changes_the_contour(bz0, bz1):
    # F1: absent only near the storey ends; frequency must not put it into the contour. The shape at
    # both ends is not the tallest, so the extractor asks; with the wall height named it answers
    dump = prism(SQUARE10, boxes=[(0, 2.0, 3.0, bz0, bz1, 0.2)])
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends and the tallest"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=bz0 / 2))
    assert (q["kind"], q["levels"], q["priority"]) == ("projection", ["L0"], "normal")
    assert (q["depth_m"], q["length_m"], q["facade_share"], q["heights_m"]) == (0.2, 1.0, 0.1, [bz0, bz1])


def test_partial_recess_over_most_of_the_storey_never_changes_the_contour():
    dump = prism(SQUARE10, boxes=[(0, 2.0, 3.0, 0.2, 3.1, -0.2)])
    with pytest.raises(SpecError, match="no section shape"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=0.1))
    assert (q["kind"], q["wall"], q["depth_m"], q["length_m"], q["heights_m"]) == ("recess", 0, 0.2, 1.0, [0.2, 3.1])


def test_faceted_corner_is_not_turned_into_an_arc():
    # F2: five real kinks (11-25 degrees) are facets, not a fillet
    contour = [[0, 0], [10, 0], [10, 8], [9.9, 8.5], [9.5, 9.2], [8.8, 9.7], [8, 10], [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    assert close(spec.expanded_floors()[0].contour, contour) and all(len(p) == 2 for p in spec.expanded_floors()[0].contour)


def test_seven_degree_kink_next_to_a_small_one_is_kept():
    # F3: directions 0, 4.5, -2.5 degrees: the -7 degree kink stays, the 4.5 degree one goes
    p1 = [10 + 10 * math.cos(math.radians(4.5)), 10 * math.sin(math.radians(4.5))]
    p2 = [p1[0] + 10 * math.cos(math.radians(-2.5)), p1[1] + 10 * math.sin(math.radians(-2.5))]
    contour = [[0, 0], [10, 0], p1, p2, [p2[0], 10], [0, 10]]
    spec, _ = extract_spec(prism(contour), OBJECT)
    pts = spec.expanded_floors()[0].contour
    assert any(math.dist(p[:2], p1) < 0.01 for p in pts)
    assert not any(math.dist(p[:2], [10, 0]) < 0.01 for p in pts)


@pytest.mark.parametrize("n", [12, 24])
def test_large_radius_does_not_depend_on_tessellation(n):
    # F4: r = 10 m quarter circle with 1.31 m or 0.65 m chords
    r = 10.0
    arc = [[30 - r + r * math.cos(a), 30 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    spec, _ = extract_spec(prism([[0, 0], [30, 0], *arc, [0, 30]]), OBJECT)
    pts = spec.expanded_floors()[0].contour
    assert len(pts) == 4
    corner = [p for p in pts if len(p) == 3][0]
    assert math.dist(corner[:2], [30, 30]) <= 0.05 and corner[2]["r"] == pytest.approx(10, abs=0.05)


def test_thin_element_between_old_sample_heights_is_seen():
    # F5: 5 cm high, 2 cm wide elements: exact height intervals, no area cut-off
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 3.0, 1.15, 1.20, 0.2)]))
    assert q["heights_m"] == [1.15, 1.2] and q["depth_m"] == 0.2
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 2.02, 1.0, 1.5, 0.2)]))
    assert q["length_m"] == pytest.approx(0.02, abs=0.001) and q["depth_m"] == 0.2


def test_element_crossing_a_level_line_is_on_both_levels():
    # F5: 2.8-3.4 m crosses the 3.3 m level, although no old sample height fell in L1 below 3.437
    q = only_question(prism(SQUARE10, boxes=[(0, 2.0, 2.5, 2.8, 3.4, 0.2)]), at(L0=1.0, L1=5.0))
    assert (q["levels"], q["priority"], q["heights_m"]) == (["L0", "L1"], "high", [2.8, 3.4])


def test_recess_near_a_corner_is_measured_on_its_own_wall():
    # F6: recess 0.1 m wide, 1.2 m deep, 2 cm from the west wall
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, boxes=[(0, 0.02, 0.12, 1.0, 1.5, -1.2)])
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    q = only_question(dump_of(b))
    assert (q["kind"], q["wall"], q["priority"]) == ("recess", 0, "normal")
    assert (q["length_m"], q["depth_m"], q["facade_share"]) == (0.1, 1.2, 0.01)


def test_pieces_overlapping_in_plan_but_not_in_height_are_separate_elements():
    # F7 (review 1) and R2-F1 (review 2): an element is connected in plan AND height. L0 pieces x 1-2
    # and 3-4 at 1.0-1.5, L1 piece x 1.5-3.5 at 4.0-4.5: three elements, no partial merge
    spec, report = extract_spec(prism(SQUARE10, boxes=[(0, 1.0, 2.0, 1.0, 1.5, 0.2), (0, 3.0, 4.0, 1.0, 1.5, 0.2),
                                                       (0, 1.5, 3.5, 4.0, 4.5, 0.2)]), OBJECT)
    got = sorted((q["levels"], q["length_m"], q["heights_m"]) for q in report["questions"])
    assert got == [(["L0"], 1.0, [1.0, 1.5]), (["L0"], 1.0, [1.0, 1.5]), (["L1"], 2.0, [4.0, 4.5])]


@pytest.mark.parametrize("u1, share, priority, shown", [(3.0, 0.1, "normal", "10.0%"), (3.01, 0.101, "high", "10.1%")])
def test_share_threshold_is_visible_in_the_questions_file(u1, share, priority, shown):
    # F8: the file shows which side of 10 % the element is on
    from dt_ai.spec.mesh import questions_markdown
    spec, report = extract_spec(prism(SQUARE10, boxes=[(0, 2.0, u1, 1.0, 1.5, 0.2)]), OBJECT)
    q = report["questions"][0]
    assert (q["facade_share"], q["priority"]) == (share, priority)
    assert f"| {shown} |" in questions_markdown(spec.id, report["questions"])


def test_cli_writes_the_questions_file(tmp_path):
    dump, obj, out = tmp_path / "dump.json", tmp_path / "object.json", tmp_path / "spec-v001.json"
    dump.write_text(json.dumps(prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1)])), encoding="utf-8")
    obj.write_text(json.dumps(at(L0=2.0)), encoding="utf-8")
    assert main(["spec", "extract", "--dump", str(dump), "--object", str(obj), "--output", str(out)]) == 0
    text = out.with_suffix(".questions.md").read_text(encoding="utf-8")
    assert "| 1 | high | projection | L0 | 0 | 0.1 | 10.0 | 100.0% | 0.0–0.6 |" in text


# --- regressions from Codex review 2 of PR #19 -------------------------------------------------

@pytest.mark.parametrize("cornice_depth", [0.1, 0.2])
def test_plinth_and_cornice_at_both_ends_are_not_the_wall(cornice_depth):
    # R2-F1: plinth 0-0.6 and cornice 3.0-3.3 on the whole south wall; the wall is visible in between only
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 0.6, 0.1), (0, 0.0, 10.0, 3.0, 3.3, cornice_depth)])
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends and the tallest"):
        extract_spec(dump, OBJECT)
    spec, report = extract_spec(dump, at(L0=1.5))
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    kinds = sorted((q["kind"], q["depth_m"], q["heights_m"][0]) for q in report["questions"])
    assert kinds == [("projection", 0.1, 0.0), ("projection", cornice_depth, 3.0)]


def test_majority_plinth_is_a_question_not_the_contour():
    # R2-F1: plinth 0-2.0 m (61 % of the storey) is the taller end shape, still not the wall
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, 0.0, 2.0, 0.1)])
    with pytest.raises(SpecError, match="no section shape"):
        extract_spec(dump, OBJECT)
    q = only_question(dump, at(L0=3.0))
    assert (q["kind"], q["depth_m"], q["heights_m"]) == ("projection", 0.1, [0.0, 2.0])


def test_holes_at_the_storey_ends_are_openings_and_the_contour_stays_strict():
    # R2-F1 / #7: wall missing at x 5-6 near both storey ends: two openings, the ends close by the
    # bridges; the projection between (70 % of the storey) still makes the extractor ask
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, boxes=[(0, 5.0, 6.0, 0.0, 0.5, 0.0), (0, 5.0, 6.0, 2.8, 3.3, 0.0),
                                        (0, 2.0, 3.0, 0.5, 2.8, 0.2)])
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends"):
        extract_spec(dump_of(b), OBJECT)
    spec, report = extract_spec(dump_of(b), at(L0=0.2))
    got = [(o.x_m, o.sill_m, o.w_m, o.h_m) for o in spec.expanded_floors()[0].openings]
    assert got == [(5.0, 0.0, 1.0, 0.5), (5.0, 2.8, 1.0, 0.5)]


def test_contour_at_a_height_off_the_closed_sections_is_an_error():
    with pytest.raises(SpecError, match="contour_at_m 5.0 m is not on a closed section"):
        extract_spec(prism(SQUARE10), at(L0=5.0))


def test_dense_wall_rows_keep_the_contour():
    # R2-F2: 8000 rows of vertices 0.825 mm apart must not delete every interval
    b = Mesh("Body")
    rows = np.linspace(0.0, 6.6, 8001)
    pts = np.asarray(SQUARE10, dtype=float)
    for w in range(4):
        a, c = pts[w], pts[(w + 1) % 4]
        for za, zb in zip(rows, rows[1:]):
            b.quad((*a, za), (*c, za), (*c, zb), (*a, zb))
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert close(spec.expanded_floors()[0].contour, SQUARE10) and close(spec.expanded_floors()[1].contour, SQUARE10)
    assert report["questions"] == []


def test_projection_on_a_rounded_corner_is_measured_on_its_facet():
    # R2-F3: 0.1 m long, 0.2 m deep projection on a tessellated r 1.5 arc
    r, n = 1.5, 12
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    contour = [[0, 0], [10, 0], *arc, [0, 10]]
    facet = 2 + 6                                  # wall index of the 7th chord in `contour`
    chord = math.dist(contour[facet], contour[facet + 1])
    u0 = (chord - 0.1) / 2
    q = only_question(prism(contour, boxes=[(facet, u0, u0 + 0.1, 1.0, 1.5, 0.2)]))
    assert q["depth_m"] == pytest.approx(0.2, abs=0.005) and q["length_m"] == pytest.approx(0.1, abs=0.005)


def test_projection_on_a_dropped_small_kink_is_measured_on_its_facet():
    # R2-F3: the 4.5 degree kink is not in the contour, the projection is still 0.2 m deep, 1 m long
    y = 10 * math.tan(math.radians(4.5))
    contour = [[0, 0], [10, 0], [20, y], [20, 10], [0, 10]]
    spec, report = extract_spec(prism(contour, boxes=[(0, 2.0, 3.0, 1.0, 1.5, 0.2)]), OBJECT)
    assert len(spec.expanded_floors()[0].contour) == 4                     # the 4.5 degree kink is not in the contour
    (q,) = report["questions"]
    assert (q["wall"], q["depth_m"], q["length_m"]) == (0, 0.2, 1.0)


@pytest.mark.parametrize("n", [5, 6, 7])
def test_coarse_true_arcs_are_rounded_corners(n):
    # R2-F4: a quarter circle in 5, 6 or 7 chords is still an r 1.5 corner
    r = 1.5
    arc = [[10 - r + r * math.cos(a), 10 - r + r * math.sin(a)] for a in np.linspace(0, math.pi / 2, n + 1)]
    spec, _ = extract_spec(prism([[0, 0], [10, 0], *arc, [0, 10]]), OBJECT)
    pts = spec.expanded_floors()[0].contour
    assert len(pts) == 4 and [p for p in pts if len(p) == 3][0][2]["r"] == pytest.approx(1.5, abs=0.02)


def test_close_vertex_rows_do_not_hide_an_element():
    # R3-F1 (review 3 of PR #19): a wall row 0.1 mm below a 0.5 m projection must not hide it
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 6.6, boxes=[(0, 2.0, 3.0, 1.0002, 1.5, 0.2)], extra_z=[1.0001])
    flat(b, Polygon(SQUARE10), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    q = only_question(dump_of(b))
    assert (q["wall"], q["depth_m"], q["length_m"], q["facade_share"]) == (0, 0.2, 1.0, 0.1)


def test_lower_walls_reaching_above_the_level_are_no_terrace():
    # pattern terrace (PR B): the lower floor's walls go on 0.6 m above LEVEL_L1 but there is no walkable
    # part at the level (the ledge top is at 3.9): a height difference, not a parapet -> still unclear
    upper = [[4, 0], [10, 0], [10, 10], [4, 10]]
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 3.9, extra_z=(3.3,))
    walls(b, upper, 3.9, 6.6)
    flat(b, Polygon(SQUARE10).difference(Polygon(upper)), 3.9, up=True)
    flat(b, Polygon(upper), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends and the tallest"):
        extract_spec(dump_of(b), OBJECT)


WEST = [[4, 0], [10, 0], [10, 10], [4, 10]]
LEDGE = Polygon(SQUARE10).difference(Polygon(WEST))


def stepped_shell(walk=None, cap=None):
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 3.9, extra_z=(3.3,), extra_u={0: [0.05, 4], 2: [6, 9.95]})
    walls(b, WEST, 3.9, 6.6)
    if walk is not None:
        flat(b, walk, 3.3)
    if cap is not None:
        flat(b, cap, 3.9)
    flat(b, Polygon(WEST), 6.6)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    return dump_of(b)


@pytest.mark.parametrize("walk, cap", [
    (shapely.box(0, 0, 2, 10), shapely.box(0, 0, 2, 10)),    # areas add up to the ledge, but one half is covered twice
    (shapely.box(0, 0, 0.05, 10), LEDGE),                       # a sliver at the level under a full ceiling, no inner face
])
def test_area_sums_alone_never_make_a_terrace(walk, cap):
    # Codex review 1 of PR #61: coverage in plan, no overlap and the parapet's inner face, not area sums
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends and the tallest"):
        extract_spec(stepped_shell(walk, cap), OBJECT)


def test_a_parapet_on_part_of_a_ledge_is_a_question():
    # Codex review 1 of PR #61: structure on a ledge that is no terrace never disappears silently
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 3.3, extra_u={0: [0.3, 4], 2: [6, 9.7]})
    walls(b, WEST, 3.3, 6.6)
    b.box((0, 0, 3.3), (0.3, 10, 3.9))
    flat(b, LEDGE.difference(shapely.box(0, 0, 0.3, 10)), 3.3)
    flat(b, Polygon(WEST), 6.6)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert spec.terraces == []
    assert [(q["kind"], q["levels"]) for q in report["questions"]] == [("ledge-structure", ["L1"])]


def test_a_relief_over_a_real_ledge_is_no_ledge_structure():
    # Codex review 1 of PR #66: a 0.075 x 0.09 m full-height relief profile on the upper floor's facade over a
    # real ledge is relief, not something standing on the ledge
    upper = [[4, 0], [10, 0], [10, 10], [4, 10], [4, 5.075], [3.91, 5.075], [3.91, 5], [4, 5]]
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 3.3)
    walls(b, upper, 3.3, 6.6)
    flat(b, Polygon(SQUARE10).difference(Polygon(upper)), 3.3)
    flat(b, Polygon(upper), 6.6)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert report["questions"] == [] and report["floors"]["L1"]["relief_parts"] == 1


# --- rule 3 (user 2026-10-12): mid-storey section; a change only in the 0.3 m under the next level is the
# slab edge, not the contour; contour_at_m only when the section changes in the wall band itself

@pytest.mark.parametrize("z0", [3.0, 3.05])
def test_slab_edge_under_the_next_level_is_not_the_contour(z0):
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, z0, 3.3, 0.15)])
    spec, report = extract_spec(dump, OBJECT)
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert report["floors"]["L0"]["contour_rule"] == f"mid storey, slab edge from {z0:.3f} m"


def test_section_change_in_the_wall_band_still_asks():
    # 0.4 m under the next level reaches into the wall band (> 0.3 m): the user names the height
    with pytest.raises(SpecError, match="no section shape is both at the two storey ends"):
        extract_spec(prism(SQUARE10, boxes=[(0, 0.0, 10.0, 2.9, 3.3, 0.15)]), OBJECT)


def test_concave_parapet_of_one_thickness_is_measured():
    """Review 1 of #81: an L-shaped parapet 0.2 m thick; at the concave corner the mitre is a 0.283 m diagonal,
    still one thickness."""
    outline = [[0, 0], [10, 0], [10, 5], [5, 5], [5, 10], [0, 10]]
    inner = Polygon(outline).buffer(-0.2, join_style="mitre")
    b = Mesh("Body")
    walls(b, outline, 0.0, 7.2)
    walls(b, [list(p) for p in list(inner.exterior.coords)[:-1]][::-1], 6.6, 7.2)    # inner face, inward
    flat(b, Polygon(outline).difference(inner), 7.2, up=True)                        # cap
    flat(b, inner, 6.6, up=True)                                                     # roof
    flat(b, Polygon(outline), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert spec.roof.parapet_thickness_m == 0.2
    assert report["roof"]["parapet_thickness"]["by"] == "measured"


@pytest.mark.parametrize("h", [0.3, 0.6])
def test_short_storey_with_a_slab_edge_on_top_keeps_the_mid_storey_rule(h):
    """Review 1 of #81: a storey up to 0.6 m high - the slab edge band ends at mid storey."""
    levels = (("L0", 0.0), ("L1", h), ("roof", h + 3.3))
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, h + 3.3, boxes=[(0, 0.0, 10.0, h - 0.1, h, 0.15)])
    flat(b, Polygon(SQUARE10), h + 3.3, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    dump = {**dump_of(b), "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in levels]}
    spec, report = extract_spec(dump, OBJECT)
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    assert report["floors"]["L0"]["contour_rule"].startswith("mid storey, slab edge")


def test_open_slab_edge_keeps_the_contour_and_is_asked():
    """Review 2 of #81: the south face missing only at 3.0-3.3 m (an open slab edge band) - the mid-storey
    contour stands, the open band is in the report and a question, never filled silently."""
    dump = prism(SQUARE10, boxes=[(0, 0.0, 10.0, 3.0, 3.3, 0.0)])
    spec, report = extract_spec(dump, OBJECT)
    assert close(spec.expanded_floors()[0].contour, SQUARE10)
    edge = report["floors"]["L0"]["slab_edge"]
    assert edge["open_m"] == [[3.0, 3.3]] and edge["closed_shapes"] == 0
    q = [q for q in report["questions"] if q["kind"] == "slab-edge-open"]
    assert [(x["levels"], x["heights_m"]) for x in q] == [(["L0"], [3.0, 3.3])]


# --- rules 1-2 (user 2026-10-13): a panel facade without a shell - contours by the panels' outer faces

def _panel(name, a, b, z0, z1, out=0.1):
    """A panel `out` thick standing outward of the CCW wall a -> b; it covers the outer corner at its start and
    leaves a 0.02 m joint at both ends."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = (b - a) / np.linalg.norm(b - a)
    n = np.array([t[1], -t[0]])
    a0, b0 = a - 0.1 * t + 0.02 * t, b - 0.02 * t
    m = Mesh(name)
    walls(m, [list(a0), list(b0), list(b0 + out * n), list(a0 + out * n)], z0, z1)
    return m


def panelised(outlines=(SQUARE10, SQUARE10), slab=SQUARE10, levels=LEVELS, extra=(), slabs_at=None, mass_m=2.0):
    """An inner mass 2 x 2 m; per storey a panel shell 0.1 m outside its outline (one part per wall); slab plates
    at every level above the ground (mesh 'Slabs', the given outline)."""
    mass = Mesh("Mass")
    lo, hi = 5 - mass_m / 2, 5 + mass_m / 2
    inner = [[lo, lo], [hi, lo], [hi, hi], [lo, hi]]
    walls(mass, inner, 0.0, levels[-1][1])
    flat(mass, Polygon(inner), levels[-1][1], up=True)
    flat(mass, Polygon(inner), 0.0, up=False)
    meshes = [mass]
    for k, ((_, z0), (_, z1)) in enumerate(zip(levels, levels[1:])):
        pts = outlines[k]
        meshes += [_panel(f"Panel_{k}_{w}", pts[w], pts[(w + 1) % len(pts)], z0 + 0.01, z1 - 0.01)
                   for w in range(len(pts))]
    slabs = Mesh("Slabs")
    for k, (_, z) in enumerate(levels[1:]):
        outline = (slabs_at or {}).get(k + 1, slab)
        flat(slabs, Polygon(outline), z, up=True)
        flat(slabs, Polygon(outline), z - 0.2, up=False)
    meshes += [slabs, *extra]
    return {"source": "synthetic-shapes", "meshes": [m.dump() for m in meshes],
            "helpers": [{"name": f"LEVEL_{n}", "location": [0.0, 0.0, z]} for n, z in levels]}


PANEL_OBJECT = {**OBJECT, "source_class": "panelised", "slabs": ["Slabs"]}
OUTER10 = [[-0.1, -0.1], [10.1, -0.1], [10.1, 10.1], [-0.1, 10.1]]


def test_panel_facade_without_a_shell_is_hinted_with_slab_candidates():
    with pytest.raises(SpecError, match=r"panel facade without a shell.*source_class.*Slabs \(2 levels\)"):
        extract_spec(panelised(), OBJECT)


def test_contour_is_the_panels_outer_face_and_the_slab_is_data():
    spec, report = extract_spec(panelised(), PANEL_OBJECT)
    assert all(close(f.contour, OUTER10, tol=0.03) for f in spec.expanded_floors())
    rep = report["floors"]["L0"]
    assert rep["measured_by"] == "panels" and rep["contour_rule"] == "panels at 1.650 m (rule 2)"
    assert rep["slab_area_m2"] == 100.0 and rep["facade_offset_m"] == pytest.approx(0.1, abs=0.011)
    assert not [q for q in report["questions"] if "slab" in q["kind"]]          # data, not a question


def test_a_slab_overhanging_the_panels_is_data_and_the_contour_stays_the_panels():
    wide = [[0, 0], [10, 0], [10, 10], [-0.5, 10], [-0.5, 0]]
    spec, report = extract_spec(panelised(slab=wide), PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)
    assert report["floors"]["L0"]["facade_offset_range_m"][0] == pytest.approx(-0.4, abs=0.011)


def test_a_balcony_beyond_0_8_m_is_left_out_of_the_contour():
    balcony = _panel("Balcony", [4, -0.1], [6, -0.1], 1.0, 2.0, out=1.5)
    spec, report = extract_spec(panelised(extra=[balcony]), PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)
    assert report["floors"]["L0"]["attachment_pieces_left_out"] >= 1


def test_a_storey_without_its_ceiling_slab_is_read_by_its_panels():
    dump = panelised()
    slabs = next(m for m in dump["meshes"] if m["name"] == "Slabs")
    slabs["triangles"] = [tr for tr in slabs["triangles"] if min(slabs["vertices"][i][2] for i in tr) > 5.0]
    spec, report = extract_spec(dump, PANEL_OBJECT)                # no slab at 3.3 m: L0 has no ceiling slab
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)
    assert report["floors"]["L0"]["slab"] == "no ceiling slab at 3.3 m"


def test_an_open_facade_stops_and_is_not_filled():
    from dt_ai.spec import SpecStops
    dump = panelised()
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]          # the south wall missing
    with pytest.raises(SpecStops) as caught:
        extract_spec(dump, PANEL_OBJECT, collect_stops=True)
    assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0")]
    assert "do not close round the building" in caught.value.stops[0]["message"]


def test_a_setback_with_a_parapet_on_the_ledge_is_a_terrace():
    upper = [[0, 0], [6, 0], [6, 10], [0, 10]]
    parapet = [_panel(f"Parapet_{w}", a, b, 3.3, 4.4) for w, (a, b) in
               enumerate([([6, 0], [10, 0]), ([10, 0], [10, 10]), ([10, 10], [6, 10])])]
    spec, report = extract_spec(panelised(outlines=(SQUARE10, upper), extra=parapet, slabs_at={2: upper}),
                                PANEL_OBJECT)
    assert [t.model_dump() for t in spec.terraces] == [{"level": "L1", "parapet_h_m": pytest.approx(1.09, abs=0.02)}]
    t = report["floors"]["L1"]["terrace"]
    assert t["walkable_m2"] > 30 and t["rule"] == "panels on the ledge edge (rule 2)"


def test_contours_by_panels_need_the_slabs_named():
    with pytest.raises(SpecError, match=r"needs object.json slabs.*not in the source: \['Nope'\]"):
        extract_spec(panelised(), {**PANEL_OBJECT, "slabs": ["Nope"]})


def test_a_small_roof_hole_is_no_opening_and_is_listed():
    """User 2026-10-13 (pattern roof-inset-plane): a slab opening with both sizes under 0.7 m that is no shaft
    is no body opening - left out and listed (OBJ03: 0.04 m2 at 96.55 m); a larger one still asks."""
    def roofed(hole):
        b = Mesh("Body")
        walls(b, SQUARE10, 0.0, 6.6)
        flat(b, Polygon(SQUARE10, [hole]), 6.6, up=True)
        flat(b, Polygon(SQUARE10), 0.0, up=False)
        return dump_of(b)
    spec, report = extract_spec(roofed([[5, 5], [5.2, 5], [5.2, 5.2], [5, 5.2]]), OBJECT)
    assert report["roof"]["holes_ignored"] == [{"area_m2": 0.04, "at": [5.1, 5.1], "sizes_m": [0.2, 0.2]}]
    with pytest.raises(SpecError, match="that is not a shaft"):
        extract_spec(roofed([[5, 5], [5.2, 5], [5.2, 5.8], [5, 5.8]]), OBJECT)    # 0.2 x 0.8 m: an opening


def test_the_id_ranges_cache_follows_the_file(tmp_path, monkeypatch):
    """User 2026-10-13: the cache of standards/material_id_ranges.yaml follows the file - another path, or the
    same path rewritten, is read again (review 2 of #83: the test must fail on a per-group cache)."""
    import os
    from dt_ai.spec import mesh as M
    (tmp_path / "standards").mkdir()
    ranges = tmp_path / "standards/material_id_ranges.yaml"
    ranges.write_text("groups:\n  opening: {first: 41, last: 42}\n", encoding="utf-8")
    monkeypatch.setattr("dt_ai.core.io.repo_root", lambda: tmp_path)
    assert M._opening_ids() == frozenset({41, 42})
    ranges.write_text("groups:\n  opening: {first: 43, last: 43}\n", encoding="utf-8")
    os.utime(ranges, ns=(ranges.stat().st_atime_ns, ranges.stat().st_mtime_ns + 10**9))
    assert M._opening_ids() == frozenset({43})


def test_an_inner_mass_does_not_decide_whether_the_facade_closes():
    """Review 2 of #83: a 3 x 3 m inner mass (more material than the panel ring) inside a closed facade."""
    spec, report = extract_spec(panelised(mass_m=3.0), PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)


def test_an_inner_ring_is_no_facade_when_the_outer_one_is_open():
    """Review 2 of #83: the south facade missing, an inner panel ring round [1, 1]-[9, 9]: a stop, not the ring."""
    from dt_ai.spec import SpecStops
    inner = [_panel(f"Inner_{w}", a, b, 0.01, 3.29) for w, (a, b) in
             enumerate([([1, 1], [9, 1]), ([9, 1], [9, 9]), ([9, 9], [1, 9]), ([1, 9], [1, 1])])]
    dump = panelised(extra=inner)
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    with pytest.raises(SpecStops) as caught:
        extract_spec(dump, PANEL_OBJECT, collect_stops=True)
    assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0")]


def _open_facade_joined_to_inner_ring():
    """South panel gone, an inner ring round [1, 1]-[9, 9], one connector to the east facade (#85)."""
    inner = [_panel(f"Inner_{w}", a, b, 0.01, 3.29) for w, (a, b) in
             enumerate([([1, 1], [9, 1]), ([9, 1], [9, 9]), ([9, 9], [1, 9]), ([1, 9], [1, 1])])]
    dump = panelised(extra=[*inner, _panel("Join", [9, 5], [10, 5], 0.01, 3.29)])
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    return dump


def test_an_open_facade_joined_to_an_inner_ring_is_asked_not_read_as_a_recess():
    """#85: the connector closes the open south facade onto the inner ring. That contour runs about 0.92 m
    inside the slabs; the extractor asks, it does not read a niche."""
    dump = _open_facade_joined_to_inner_ring()
    with pytest.raises(SpecStops) as caught:
        extract_spec(dump, PANEL_OBJECT, collect_stops=True)
    assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0")]
    msg = caught.value.stops[0]["message"]
    assert "niche" in msg and "missing facade wall" in msg and "panel_niches" in msg and "L0" in msg
    depth = float(re.search(r"up to ([0-9.]+) m", msg).group(1))
    assert depth == pytest.approx(0.92, abs=0.05)
    boxes = re.findall(r"bbox \[([-\d.]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)\]", msg)
    assert len(boxes) == 1
    x0, y0, x1, _y1 = (float(v) for v in boxes[0])
    assert y0 < 0.1 and x0 < 1.0 and x1 > 9.0


def test_a_recess_answered_as_a_niche_keeps_the_panel_contour():
    """#85: a point inside the south strip (the centre the stop prints) accepts the contour unchanged."""
    dump = _open_facade_joined_to_inner_ring()
    spec, report = extract_spec(dump, {**PANEL_OBJECT, "panel_niches": {"L0": [[5.0, 0.5]]}})
    assert report["floors"]["L0"]["area_m2"] == pytest.approx(70.484, abs=0.01)
    regions = report["floors"]["L0"]["panel_niches"]
    assert len(regions) == 1 and regions[0]["depth_m"] == pytest.approx(0.92, abs=0.05)
    assert len(spec.expanded_floors()[0].contour) == 17


def test_a_niche_answer_elsewhere_does_not_confirm_the_recess():
    """#85: a point outside the gap (inside the inner ring, inside the contour) leaves the contour stop."""
    dump = _open_facade_joined_to_inner_ring()
    with pytest.raises(SpecStops) as caught:
        extract_spec(dump, {**PANEL_OBJECT, "panel_niches": {"L0": [[3.0, 7.0]]}}, collect_stops=True)
    assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0")]
    assert re.search(r"region 1 centre \(", caught.value.stops[0]["message"])


LOGGIA = [[0, 0], [3, 0], [3, 2.9], [6, 2.9], [6, 0], [10, 0], [10, 10], [0, 10]]


def test_a_loggia_deeper_than_the_attachment_reach_is_asked_and_kept_when_answered():
    """#85: a 2.9 m loggia is deeper than 0.8 m. Unanswered, both storeys stop; answered, the panel contour
    stays the loggia (outer faces 0.1 m outside the wall line), not the slab square."""
    dump = panelised(outlines=(LOGGIA, LOGGIA))
    with pytest.raises(SpecStops) as caught:
        extract_spec(dump, PANEL_OBJECT, collect_stops=True)
    assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0"), ("contour", "L1")]
    # wall-line notch is 3 * 2.9; the panel outer face is 0.1 m outside, so the contour area is the outer
    # square minus a notch 2.8 m wide and 2.9 m deep (~95.6), not 100 - 3*2.8
    spec, report = extract_spec(dump, {**PANEL_OBJECT, "panel_niches": {"L0": [[4.5, 1.0]], "L1": [[4.5, 1.0]]}})
    pts = spec.expanded_floors()[0].contour
    assert len(pts) > 4
    assert report["floors"]["L0"]["area_m2"] == pytest.approx(95.627, abs=0.05)
    assert not Polygon([p[:2] for p in pts]).covers(Point(4.5, 1.5))


def test_a_recess_within_the_attachment_reach_is_data_not_a_question():
    """#85: a 0.5 m notch (outer face 0.4 m inside the slab) is within 0.8 m, so it stays data."""
    outline = [[0, 0], [3, 0], [3, 0.5], [6, 0.5], [6, 0], [10, 0], [10, 10], [0, 10]]
    spec, _ = extract_spec(panelised(outlines=(outline, outline)), PANEL_OBJECT)
    pts = spec.expanded_floors()[0].contour
    assert any(abs(p[1] - 0.4) < 0.05 and 3 < p[0] < 6 for p in pts)
    assert not Polygon([p[:2] for p in pts]).covers(Point(4.5, 0.2))


def test_probe_recesses_are_asked_exactly_when_deeper_than_the_attachment_reach():
    """#85 probe (seed 85, 12 cases): a south notch of depth d stops on L0 and L1 iff d > 1.0. The panel
    outer face sits 0.1 m outside the wall line, so the measured depth is d - 0.1, past 0.8 m exactly then.
    Answering the notch centre clears a stop."""
    rng = random.Random(85)
    for _ in range(12):
        a, w = rng.uniform(1.0, 4.0), rng.uniform(1.5, 4.0)
        d = rng.uniform(*((0.3, 0.6) if rng.randrange(2) == 0 else (1.1, 3.0)))
        outline = [[0, 0], [a, 0], [a, d], [a + w, d], [a + w, 0], [10, 0], [10, 10], [0, 10]]
        dump = panelised(outlines=(outline, outline))
        if not d > 1.0:
            extract_spec(dump, PANEL_OBJECT)
            continue
        with pytest.raises(SpecStops) as caught:
            extract_spec(dump, PANEL_OBJECT, collect_stops=True)
        assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0"), ("contour", "L1")], (a, w, d)
        mark = [a + w / 2, d / 2]
        extract_spec(dump, {**PANEL_OBJECT, "panel_niches": {"L0": [mark], "L1": [mark]}})


_DEEP_VERTEX = [[0, 0], [3.075396912266968, 0], [3.7335075576212855, 1.0286117553710938],
                [4.391618202975602, 0], [10, 0], [10, 10], [0, 10]]


def _printed_niches(stops):
    niches = {}
    for stop in stops:
        centres = re.findall(r"region \d+ centre \(([-\d.]+), ([-\d.]+)\)", stop["message"])
        niches[stop["level"]] = [[float(x), float(y)] for x, y in centres]
    return niches


def test_a_deep_vertex_between_offset_samples_stops_and_is_kept_when_answered(monkeypatch):
    """Synthetic: a vertex between the 0.02 m samples, deeper than 0.8 m, stops and stays when answered (review 1 of #85)."""
    dump = panelised(outlines=(_DEEP_VERTEX, _DEEP_VERTEX))
    with pytest.raises(SpecStops) as caught:
        extract_spec(dump, PANEL_OBJECT, collect_stops=True)
    assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0"), ("contour", "L1")]
    niches = _printed_niches(caught.value.stops)
    assert all(niches[lv] for lv in ("L0", "L1"))
    _, report = extract_spec(dump, {**PANEL_OBJECT, "panel_niches": niches})
    monkeypatch.setattr("dt_ai.spec.mesh._apply_panel_niches", lambda *args, **kwargs: None)
    _, bypass = extract_spec(dump, PANEL_OBJECT)
    assert report["floors"]["L0"]["area_m2"] == bypass["floors"]["L0"]["area_m2"]


def test_a_deep_vertex_combined_with_the_open_facade_case_and_a_shallow_notch():
    """Synthetic: the open south facade still asks once, a 0.5 m notch does not, and an answered deep vertex passes (review 1 of #85)."""
    with pytest.raises(SpecStops) as caught:
        extract_spec(_open_facade_joined_to_inner_ring(), PANEL_OBJECT, collect_stops=True)
    assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0")]
    boxes = re.findall(r"bbox \[([-\d.]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)\]", caught.value.stops[0]["message"])
    assert len(boxes) == 1
    x0, y0, x1, _y1 = (float(v) for v in boxes[0])
    assert y0 < 0.1 and x0 < 1.0 and x1 > 9.0
    shallow = [[0, 0], [3, 0], [3.6, 0.6], [4.2, 0], [10, 0], [10, 10], [0, 10]]
    extract_spec(panelised(outlines=(shallow, shallow)), PANEL_OBJECT)
    dump = panelised(outlines=(_DEEP_VERTEX, _DEEP_VERTEX))
    with pytest.raises(SpecStops) as caught:
        extract_spec(dump, PANEL_OBJECT, collect_stops=True)
    extract_spec(dump, {**PANEL_OBJECT, "panel_niches": _printed_niches(caught.value.stops)})


def test_probe_slanted_and_narrow_recesses_stop_exactly_when_deeper_than_the_attachment_reach(monkeypatch):
    """Synthetic: slanted narrow notches stop exactly when the contour is deeper than 0.8 m (review 1 of #85)."""
    from dt_ai.spec import mesh as mesh_mod

    def depth_inside(env, reference):
        ring = env.exterior
        distances = np.arange(0.0, ring.length, 0.001)
        xy = [np.asarray(ring.coords)[:, :2]]
        if len(distances):
            xy.append(shapely.get_coordinates(shapely.line_interpolate_point(ring, distances)))
        cloud = shapely.points(np.vstack(xy))
        covered = np.asarray(shapely.covered_by(cloud, reference), dtype=bool)
        if not covered.any():
            return 0.0
        return float(np.max(shapely.distance(cloud[covered], reference.exterior)))

    real = mesh_mod._apply_panel_niches
    rng = random.Random(8586)
    checked = saw_stop = saw_clear = 0
    for i in range(38):
        a = rng.uniform(1.0, 4.0)
        w1, w2 = rng.uniform(0.2, 2.5), rng.uniform(0.2, 2.5)
        if i >= 30:
            h = rng.uniform(0.3, 0.85)
        elif rng.randrange(2) == 0:
            h = rng.uniform(0.85, 0.95)
        else:
            h = rng.uniform(0.95, 1.2)
        outline = [[0, 0], [a, 0], [a + w1, h], [a + w1 + w2, 0], [10, 0], [10, 10], [0, 10]]
        dump = panelised(outlines=(outline, outline))
        depths = []

        def bypass(env, reference, *args, sink=depths, **kwargs):
            sink.append(depth_inside(env, reference))

        monkeypatch.setattr(mesh_mod, "_apply_panel_niches", bypass)
        extract_spec(dump, PANEL_OBJECT, collect_stops=True)
        monkeypatch.setattr(mesh_mod, "_apply_panel_niches", real)
        if not depths or any(abs(d - 0.8) <= 1e-3 for d in depths):
            continue
        if any(d > 0.8 for d in depths) and any(d <= 0.8 for d in depths):
            continue
        truth = max(depths)
        checked += 1
        if truth > 0.8:
            with pytest.raises(SpecStops) as caught:
                extract_spec(dump, PANEL_OBJECT, collect_stops=True)
            assert [(s["stage"], s["level"]) for s in caught.value.stops] == [("contour", "L0"), ("contour", "L1")]
            saw_stop += 1
        else:
            extract_spec(dump, PANEL_OBJECT, collect_stops=True)
            saw_clear += 1
    assert checked >= 20 and saw_stop and saw_clear


def test_a_parapet_on_the_slab_edge_inside_the_facade_line_is_found():
    """Review 2 of #83: the parapet stands on the walkable slab's edge (x 9.8-10), 0.1 m inside the lower facade's
    outer line."""
    upper = [[0, 0], [6, 0], [6, 10], [0, 10]]
    parapet = Mesh("Parapet")
    walls(parapet, [[9.8, 0], [10, 0], [10, 10], [9.8, 10]], 3.3, 4.4)
    spec, report = extract_spec(panelised(outlines=(SQUARE10, upper), extra=[parapet], slabs_at={2: upper}),
                                PANEL_OBJECT)
    assert [(t.level, round(t.parapet_h_m, 2)) for t in spec.terraces] == [("L1", 1.1)]


def test_a_fin_welded_to_a_facade_panel_is_cut_off_and_the_panel_stays():
    """#87 (user 2026-10-13): a part is classified segment by segment - a fin 0.85 m out welded to the south
    panel is an attachment candidate, the panel stays facade (OBJ03 L16-L28 dropped whole facade parts)."""
    dump = panelised()
    south = next(m for m in dump["meshes"] if m["name"] == "Panel_0_0")
    dump["meshes"].remove(south)
    joined = Mesh("Panel_0_0")
    walls(joined, [[-0.08, 0], [9.98, 0], [9.98, -0.1], [-0.08, -0.1]], 0.01, 3.29, extra_u={2: [5.88, 5.98]})
    walls(joined, [[4.0, -0.1], [4.1, -0.1], [4.1, -0.95], [4.0, -0.95]][::-1], 0.01, 3.29)
    dump["meshes"].append(joined.dump())
    spec, report = extract_spec(dump, PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)
    assert report["floors"]["L0"]["attachment_pieces_left_out"] == 1


def test_a_storey_under_a_terrace_deck_keeps_its_floor_slab_as_reference():
    """#88 (user 2026-10-13): at a terrace level the slab is the deck (the walkable top); the storey under it
    takes its own floor slab too, so a narrow deck does not leave its facade out."""
    levels = (("L0", 0.0), ("L1", 3.3), ("L2", 6.6), ("roof", 9.9))
    upper = [[0, 0], [8, 0], [8, 10], [0, 10]]
    deck = [[8, 0], [10, 0], [10, 10], [8, 10]]
    dump = panelised(outlines=(SQUARE10, SQUARE10, upper), levels=levels, slabs_at={2: deck, 3: upper})
    spec, report = extract_spec(dump, PANEL_OBJECT)
    assert close(spec.expanded_floors()[1].contour, OUTER10, tol=0.03)
    assert report["floors"]["L1"]["attachment_pieces_left_out"] == 0


def _fin(mesh, x0, x1, y_out, cross=None, z0=0.01, z1=3.29):
    """A fin from the panels' outer face (y = -0.1) out to y_out, as quads sharing their corners; `cross`: the y
    of a crossbar between its sides."""
    ys = [-0.1] + ([cross] if cross is not None else []) + [y_out]
    for x in (x0, x1):
        for ya, yb in zip(ys, ys[1:]):
            mesh.quad((x, ya, z0), (x, yb, z0), (x, yb, z1), (x, ya, z1))
    mesh.quad((x0, y_out, z0), (x1, y_out, z0), (x1, y_out, z1), (x0, y_out, z1))
    if cross is not None:
        mesh.quad((x0, cross, z0), (x1, cross, z0), (x1, cross, z1), (x0, cross, z1))


def test_a_glass_line_ending_at_a_fin_stays_facade():
    """Review 1 of #89: the south facade is one glass line; a fin welded at its end is cut off, the glass stays."""
    dump = panelised()
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    glass = Mesh("Glass")
    glass.quad((-0.1, 0.02, 0.01), (-0.1, -0.1, 0.01), (-0.1, -0.1, 3.29), (-0.1, 0.02, 3.29))   # west corner
    glass.quad((-0.1, -0.1, 0.01), (10.1, -0.1, 0.01), (10.1, -0.1, 3.29), (-0.1, -0.1, 3.29))
    _fin(glass, 10.1, 10.1, -0.95)
    dump["meshes"].append(glass.dump())
    spec, report = extract_spec(dump, PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)


def test_a_fin_with_a_crossbar_leaves_no_stub():
    """Review 1 of #89: a fin 1.1 m out with a crossbar 0.4 m out, welded to the south panel, goes."""
    dump = panelised()
    south = next(m for m in dump["meshes"] if m["name"] == "Panel_0_0")
    dump["meshes"].remove(south)
    joined = Mesh("Panel_0_0")
    walls(joined, [[-0.08, 0], [9.98, 0], [9.98, -0.1], [-0.08, -0.1]], 0.01, 3.29, extra_u={2: [5.58, 5.98]})
    _fin(joined, 4.0, 4.4, -1.2, cross=-0.5)
    dump["meshes"].append(joined.dump())
    spec, report = extract_spec(dump, PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)  # the fin, its crossbar and its root are gone (#90)
    assert report["floors"]["L0"]["attachment_pieces_left_out"] == 1


def _fin_dump(cross, x0=4.0, x1=4.4, y_out=-1.2):
    dump = panelised()
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    joined = Mesh("Panel_0_0")
    walls(joined, [[-0.08, 0], [9.98, 0], [9.98, -0.1], [-0.08, -0.1]], 0.01, 3.29, extra_u={2: [5.58, 5.98]})
    _fin(joined, x0, x1, y_out, cross=cross)
    dump["meshes"].append(joined.dump())
    return dump


@pytest.mark.parametrize("cross", [-0.35, -0.4, -0.45, -0.5])
@pytest.mark.parametrize("width", [0.1, 0.4, 1.0])
def test_a_fin_root_inside_the_facade_band_leaves_no_stub(cross, width):
    """#90: a fin 1.2 m out with a crossbar 0.25-0.4 m off the panels - its root (across the facade, from the cut
    back to the panels' outer face) goes too, so the contour is the panels' line without a stub."""
    spec, report = extract_spec(_fin_dump(cross, x1=4.0 + width), PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)
    assert report["floors"]["L0"]["attachment_pieces_left_out"] == 1


def test_a_fin_at_a_facade_step_leaves_the_step():
    """#90: the south facade steps 0.3 m outward. The ceiling slab's south edge sits 0.1 m behind that outer
    face, so the face is inside the facade band, and the step (across the outline, inside the band) shares its
    outer corner with the fin's root. The walk stops at that facade node: the step stays and the fin goes.
    Walking on through the facade node removes the step and the south facade no longer closes. The re-entrant
    corner (5, -0.1) is rounded by the 0.05 m joint closing, so the vertex that remains is about 0.045 m off it;
    the convex corner (5, -0.4) comes back within 0.03 m."""
    slab = [[0, -0.3], [10, -0.3], [10, 10], [0, 10]]
    dump = panelised(slab=slab)
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    south = Mesh("Panel_0_0")
    z0, z1 = 0.01, 3.29
    south.quad((-0.1, 0.02, z0), (-0.1, -0.1, z0), (-0.1, -0.1, z1), (-0.1, 0.02, z1))       # west corner
    south.quad((-0.1, -0.1, z0), (5, -0.1, z0), (5, -0.1, z1), (-0.1, -0.1, z1))
    south.quad((5, -0.1, z0), (5, -0.4, z0), (5, -0.4, z1), (5, -0.1, z1))                     # the step
    south.quad((5, -0.4, z0), (10.1, -0.4, z0), (10.1, -0.4, z1), (5, -0.4, z1))
    south.quad((10.1, -0.4, z0), (10.1, -0.08, z0), (10.1, -0.08, z1), (10.1, -0.4, z1))       # to the east panel
    for x in (5.0, 5.4):                                                                        # fin at the step corner
        for ya, yb in ((-0.4, -0.7), (-0.7, -1.6)):
            south.quad((x, ya, z0), (x, yb, z0), (x, yb, z1), (x, ya, z1))
    south.quad((5.0, -1.6, z0), (5.4, -1.6, z0), (5.4, -1.6, z1), (5.0, -1.6, z1))
    south.quad((5.0, -0.7, z0), (5.4, -0.7, z0), (5.4, -0.7, z1), (5.0, -0.7, z1))
    dump["meshes"].append(south.dump())
    spec, _report = extract_spec(dump, PANEL_OBJECT)
    contour = spec.expanded_floors()[0].contour
    # (5, -0.4) is the convex corner and comes back within 0.03. (5, -0.1) is re-entrant: the 0.05 m joint
    # closing rounds it, and simplify keeps the fillet's landing, about 0.045 m west of the corner.
    assert any(math.dist(p[:2], (5, -0.4)) <= 0.03 for p in contour)
    assert any(math.dist(p[:2], (5, -0.1)) <= 0.05 for p in contour)
    assert min(p[1] for p in contour) >= -0.45


@pytest.mark.parametrize("tail_shear", [0.05, 0.1, -0.05, -0.1])
def test_a_bent_fin_root_leaves_no_stub(tail_shear):
    """Synthetic review-2 P1: the root is upright, but the cut tail bends at the crossbar.
    The entire fin must go, not leave a successful contour with a 0.30 m stub at y=-0.4.
    """
    dump = _fin_dump(-0.4)
    for p in dump["meshes"][-1]["vertices"]:
        if p[1] < -0.1 - 1e-9:
            p[0] += tail_shear * max(0.0, -p[1] - 0.1 - 0.3)
    spec, report = extract_spec(dump, PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)
    assert report["floors"]["L0"]["attachment_pieces_left_out"] == 1


def _shear(dump, k, below=-0.1):
    """Lean a fin: every vertex of the last mesh with y < `below` moves x += k * (below - y); the facade stays."""
    for p in dump["meshes"][-1]["vertices"]:
        if p[1] < below - 1e-9:
            p[0] += k * (below - p[1])
    return dump


@pytest.mark.parametrize("shear", [0.5, 0.9, 1.0, 1.1, 1.5, 2.0, 4.0, 6.0, -1.0, -1.5, -4.0, -6.0])
@pytest.mark.parametrize("cross", [-0.35, -0.4, -0.5])
def test_an_oblique_fin_root_leaves_no_stub(shear, cross):
    """Review 1 of #279 (#90): a fin leaning about 9-63 degrees off the facade (either way, 45 included, and the
    shallow shears 4 and 6 that sit within 15 degrees of the facade line) with a crossbar 0.25-0.4 m off the panels.
    Its root goes with it, so the contour is the panels' line. Witness: shear 1.5, crossbar -0.4 left a 0.15 m stub
    at y = -0.25 when a 45-degree test read the root as facade; shear 4 left the same stub when a 15-degree
    along-outline test did."""
    spec, report = extract_spec(_shear(_fin_dump(cross), shear), PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)
    assert report["floors"]["L0"]["attachment_pieces_left_out"] == 1


@pytest.mark.parametrize("tail_shear", [0.0, 0.05, -0.1, 0.8])
def test_an_oblique_fin_root_in_two_pieces_leaves_no_stub(tail_shear):
    """#90: the leaning root is split at y = -0.25 (no crossbar there); a bent tail must not leave either piece."""
    dump = panelised()
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    joined = Mesh("Panel_0_0")
    walls(joined, [[-0.08, 0], [9.98, 0], [9.98, -0.1], [-0.08, -0.1]], 0.01, 3.29, extra_u={2: [5.58, 5.98]})
    z0, z1 = 0.01, 3.29
    for x in (4.0, 4.4):
        for ya, yb in ((-0.1, -0.25), (-0.25, -0.4), (-0.4, -1.2)):
            joined.quad((x, ya, z0), (x, yb, z0), (x, yb, z1), (x, ya, z1))
    joined.quad((4.0, -1.2, z0), (4.4, -1.2, z0), (4.4, -1.2, z1), (4.0, -1.2, z1))
    joined.quad((4.0, -0.4, z0), (4.4, -0.4, z0), (4.4, -0.4, z1), (4.0, -0.4, z1))
    dump["meshes"].append(joined.dump())
    spec, _report = extract_spec(_piecewise_fin(dump, 1.5, tail_shear, 0.3), PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)


def _step_dump(fin_from, shear=0.0, cross=-0.7):
    """The #90 step facade (0.3 m out at x = 5) with a fin 0.4 m wide at x = `fin_from` on the step's outer line
    (y = -0.4), out to y = -1.6, leaning by `shear`; `cross`: its crossbar's y (None: no crossbar, the fin is cut
    off whole at the facade)."""
    slab = [[0, -0.3], [10, -0.3], [10, 10], [0, 10]]
    dump = panelised(slab=slab)
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    south = Mesh("Panel_0_0")
    z0, z1 = 0.01, 3.29
    q = lambda a, b: south.quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1))  # noqa: E731
    q((-0.1, 0.02), (-0.1, -0.1))
    q((-0.1, -0.1), (5, -0.1))
    q((5, -0.1), (5, -0.4))                                                                  # the step
    q((5, -0.4), (10.1, -0.4))
    q((10.1, -0.4), (10.1, -0.08))
    ys = [-0.4] + ([cross] if cross is not None else []) + [-1.6]
    for x in (fin_from, fin_from + 0.4):
        for ya, yb in zip(ys, ys[1:]):
            q((x, ya), (x, yb))
    q((fin_from, -1.6), (fin_from + 0.4, -1.6))
    if cross is not None:
        q((fin_from, cross), (fin_from + 0.4, cross))
    dump["meshes"].append(south.dump())
    return _shear(dump, shear, below=-0.4)


@pytest.mark.parametrize("cross", [-0.7, None])
@pytest.mark.parametrize("shear", [0.0, 1.0, 1.5, 4.0, -1.5, -4.0])
def test_a_fin_at_a_step_corner_leaves_the_step(shear, cross):
    """#90 combined with the facade-node stop: a fin (upright or leaning, with a crossbar or cut whole) stands on
    the step's outer corner (5, -0.4), in line with the step. The fin goes; the step, which continues the fin's
    line back to the panels, is facade and stays (the re-entrant corner (5, -0.1) is rounded by the joint)."""
    spec, _report = extract_spec(_step_dump(5.0, shear, cross), PANEL_OBJECT)
    contour = spec.expanded_floors()[0].contour
    assert any(math.dist(p[:2], (5, -0.4)) <= 0.03 for p in contour)
    assert any(math.dist(p[:2], (5, -0.1)) <= 0.05 for p in contour)
    assert min(p[1] for p in contour) >= -0.43


@pytest.mark.parametrize("shear", [0.0, 1.5, 4.0, -1.5, -4.0])
def test_an_oblique_fin_at_a_glass_line_end_leaves_the_glass(shear):
    """#90 combined with review 1 of #89: a leaning fin welded at the south glass line's east end goes, the glass
    stays."""
    dump = panelised()
    dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
    glass = Mesh("Glass")
    glass.quad((-0.1, 0.02, 0.01), (-0.1, -0.1, 0.01), (-0.1, -0.1, 3.29), (-0.1, 0.02, 3.29))   # west corner
    glass.quad((-0.1, -0.1, 0.01), (10.1, -0.1, 0.01), (10.1, -0.1, 3.29), (-0.1, -0.1, 3.29))
    _fin(glass, 9.7, 10.1, -0.95, cross=-0.4)
    dump["meshes"].append(glass.dump())
    spec, _report = extract_spec(_shear(dump, shear), PANEL_OBJECT)
    assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03)


def _shear_for(degrees):
    """Shear whose fin leaves the facade at `degrees` (positive leans +x). tan(angle) = 1 / shear."""
    return 1.0 / math.tan(math.radians(degrees))


def test_probe_oblique_roots_at_every_angle_leave_no_stub():
    """#90: a straight fin every 5 degrees from 5 to 85 off the south facade, both ways, crossbar 0.4 m out.
    45 degrees and the shallow angles (within 45 of the facade line) are in the set. The root continues the
    fin's own line, so the contour stays the panels' line within 0.03 m; the angle to the facade decides nothing."""
    for degrees in range(5, 90, 5):
        for sign in (1.0, -1.0):
            spec, report = extract_spec(_shear(_fin_dump(-0.4), sign * _shear_for(degrees)), PANEL_OBJECT)
            assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03), degrees
            assert report["floors"]["L0"]["attachment_pieces_left_out"] == 1


def test_probe_a_step_and_a_glass_end_stay_at_every_oblique_angle():
    """#90 with the facade-node stop: the same angles, mirrored, on the 0.3 m step and on the glass line's end.
    The fin's root goes; the step corners and the glass line stay. Deviation from the step's outer corner is
    at most 0.03 m, from the re-entrant corner at most 0.05 m, and the contour never passes 0.43 m out."""
    for degrees in (5, 15, 45, 60, 80):
        for sign in (1.0, -1.0):
            shear = sign * _shear_for(degrees)
            spec, _report = extract_spec(_step_dump(5.0, shear, -0.7), PANEL_OBJECT)
            contour = spec.expanded_floors()[0].contour
            assert any(math.dist(p[:2], (5, -0.4)) <= 0.03 for p in contour), degrees
            assert any(math.dist(p[:2], (5, -0.1)) <= 0.05 for p in contour), degrees
            assert min(p[1] for p in contour) >= -0.43, (degrees, sign)
            dump = panelised()
            dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
            glass = Mesh("Glass")
            glass.quad((-0.1, 0.02, 0.01), (-0.1, -0.1, 0.01), (-0.1, -0.1, 3.29), (-0.1, 0.02, 3.29))
            glass.quad((-0.1, -0.1, 0.01), (10.1, -0.1, 0.01), (10.1, -0.1, 3.29), (-0.1, -0.1, 3.29))
            _fin(glass, 9.7, 10.1, -0.95, cross=-0.4)
            dump["meshes"].append(glass.dump())
            spec, _report = extract_spec(_shear(dump, shear), PANEL_OBJECT)
            assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03), (degrees, sign)


def _piecewise_fin(dump, root_shear, tail_shear, hinge, below=-0.1):
    """Synthetic fin with independently directed root/tail; leave the facade vertices fixed."""
    for p in dump["meshes"][-1]["vertices"]:
        depth = below - p[1]
        if depth > 1e-9:
            p[0] += root_shear * depth + tail_shear * max(0.0, depth - hinge)
    return dump


def test_probe_piecewise_roots_preserve_the_facade():
    """Seed 90279, 36 synthetic bent fins: mirror, oblique root, crossbar depth and width together.
    Bends are at crossbars outside the facade band, as in the review P1; the root crosses into the band.
    """
    rng = random.Random(90279)
    for i in range(36):
        cross = rng.choice([-0.35, -0.4, -0.5])
        width = rng.choice([0.1, 0.4, 1.0])
        root = rng.choice([-1.5, -1.0, 0.0, 1.0, 1.5])
        tail = rng.choice([-0.8, -0.1, -0.05, 0.05, 0.1, 0.8])
        dump = _piecewise_fin(_fin_dump(cross, x1=4.0 + width), root, tail, -cross - 0.1)
        # Section noding/order must not change the answer.
        if i % 2:
            dump["meshes"][-1]["triangles"].reverse()
        spec, report = extract_spec(dump, PANEL_OBJECT)
        assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03), (i, cross, width, root, tail)
        assert report["floors"]["L0"]["attachment_pieces_left_out"] == 1


def test_probe_piecewise_roots_preserve_step_and_glass_junctions():
    """24 combinations per safeguard: bent tails plus upright/45-degree/oblique mirrored roots.
    The real facade junction is inside the band; it must stay even when collinear with the root.
    """
    for root in (-4.0, -1.5, -1.0, 0.0, 1.0, 1.5):
        for tail in (-0.8, -0.05, 0.05, 0.8):
            dump = _piecewise_fin(_step_dump(5.0, cross=-0.7), root, tail, 0.3, below=-0.4)
            spec, _ = extract_spec(dump, PANEL_OBJECT)
            contour = spec.expanded_floors()[0].contour
            assert any(math.dist(p[:2], (5, -0.4)) <= 0.03 for p in contour), (root, tail)
            assert any(math.dist(p[:2], (5, -0.1)) <= 0.05 for p in contour), (root, tail)
            assert min(p[1] for p in contour) >= -0.43, (root, tail)
            dump = panelised()
            dump["meshes"] = [m for m in dump["meshes"] if m["name"] != "Panel_0_0"]
            glass = Mesh("Glass")
            glass.quad((-0.1, 0.02, 0.01), (-0.1, -0.1, 0.01), (-0.1, -0.1, 3.29), (-0.1, 0.02, 3.29))
            glass.quad((-0.1, -0.1, 0.01), (10.1, -0.1, 0.01), (10.1, -0.1, 3.29), (-0.1, -0.1, 3.29))
            _fin(glass, 9.7, 10.1, -0.95, cross=-0.4)
            dump["meshes"].append(glass.dump())
            spec, _ = extract_spec(_piecewise_fin(dump, root, tail, 0.3), PANEL_OBJECT)
            assert close(spec.expanded_floors()[0].contour, OUTER10, tol=0.03), (root, tail)


def test_slab_data_follow_the_ceiling_not_the_reference():
    """Review 1 of #89: a 121 m2 floor slab and a 100 m2 ceiling - the share and the offset are the ceiling's."""
    big = [[-0.5, -0.5], [10.5, -0.5], [10.5, 10.5], [-0.5, 10.5]]
    spec, report = extract_spec(panelised(slabs_at={1: big, 2: SQUARE10}), PANEL_OBJECT)
    rep = report["floors"]["L1"]
    assert rep["slab_inside_facade_share"] == 1.0 and rep["facade_offset_m"] == pytest.approx(0.1, abs=0.011)


def test_contour_points_within_the_weld_are_one():
    """User 2026-10-13: contour points closer than weld_m (3 mm, inclusive) are one point."""
    from dt_ai.spec.mesh import _contour_points
    poly = Polygon([[0, 0], [5, 0], [5, 0.002], [10, 0.002], [10, 10], [0, 10]])   # a 2 mm step
    pts = _contour_points(poly, 0.003)
    assert len(pts) == len(_contour_points(poly, 0.0001)) - 1
    assert all(np.hypot(a[0] - b[0], a[1] - b[1]) > 0.003
               for i, a in enumerate(pts) for b in pts[i + 1:])


@pytest.mark.parametrize("weld,right_x", [(0.003, 1.003), (0.001, 1.001)])
def test_non_adjacent_contour_points_beyond_the_configured_weld_stay(weld, right_x):
    """A neck wider than weld_m stays intact; the configured tolerance is not always 3 mm."""
    from dt_ai.spec.mesh import _contour_points
    poly = Polygon([[0, 0], [2, 0], [2, 2], [right_x, 2], [2, 4], [0, 4], [0.999, 2], [0, 2]])
    pts = _contour_points(poly, weld)
    assert len(pts) == 8
    assert Polygon(pts).is_valid
    assert [right_x, 2] in pts and [0.999, 2] in pts


def test_a_closing_weld_that_leaves_a_simple_triangle_succeeds():
    from dt_ai.spec.mesh import _contour_points
    assert _contour_points(Polygon([[0, 0], [10, 0], [10, 10], [0, 0.002]]), 0.003) == [
        [0, 0], [10, 0], [10, 10]]


def test_a_triangle_with_a_closing_edge_beyond_the_weld_stays():
    from dt_ai.spec.mesh import _contour_points
    assert _contour_points(Polygon([[0, 0], [10, 0], [0, 0.004]]), 0.003) == [
        [0, 0], [10, 0], [0, 0.004]]


@pytest.mark.parametrize("right_x", [1.001, 1.002])
def test_non_adjacent_contour_points_within_the_weld_stop(right_x):
    """#104: welding opposite sides of a narrow neck repeats a vertex, not a simple contour."""
    from dt_ai.spec.mesh import _contour_points
    poly = Polygon([[0, 0], [2, 0], [2, 2], [right_x, 2], [2, 4], [0, 4], [0.999, 2], [0, 2]])
    assert poly.is_valid
    with pytest.raises(SpecError, match="weld_m"):
        _contour_points(poly, 0.003)


@pytest.mark.parametrize("closing_edge", [0.002, 0.003])
def test_a_triangle_collapsed_by_the_closing_weld_stops(closing_edge):
    """#104: welding the closing edge must not leave a triangle with only two distinct points."""
    from dt_ai.spec.mesh import _contour_points
    poly = Polygon([[0, 0], [10, 0], [0, closing_edge]])
    with pytest.raises(SpecError, match="weld_m"):
        _contour_points(poly, 0.003)


def test_a_self_crossing_contour_stops_and_is_never_written():
    """#97 (OBJ03): a contour whose line crosses itself is a stop, not an invalid ring in the spec."""
    from dt_ai.spec.mesh import _contour_points
    with pytest.raises(SpecError, match="crosses itself"):
        _contour_points(Polygon([[0, 0], [10, 0], [10, 10], [4, 10], [4, -3], [3, -3], [3, 10], [0, 10]]))


# --- #84: the panel contour is simplified by Douglas-Peucker RELIEF_M; the roof coverage check is not

def _envelope(outline):
    """The panels' outer line of `panelised(outline)`: the outline 0.1 m out, mitred."""
    return [list(c) for c in Polygon(outline).buffer(0.1, join_style="mitre").exterior.coords[:-1]]


STEPS_84 = {
    "notch-in": [[0, 0], [6, 0], [6, 0.11], [7, 0.11], [7, 0], [10, 0], [10, 10], [0, 10]],
    "bump-out": [[0, 0], [6, 0], [6, -0.11], [7, -0.11], [7, 0], [10, 0], [10, 10], [0, 10]],
    "step-out": [[0, 0], [6, 0], [6, -0.11], [10, -0.11], [10, 10], [0, 10]],
    "step-in": [[0, 0], [6, 0], [6, 0.11], [10, 0.11], [10, 10], [0, 10]],
}


@pytest.mark.parametrize("name", sorted(STEPS_84))
def test_a_step_the_panel_contour_simplifies_away_is_no_roof_opening(name):
    """#84: complete slabs out to the panels' outer face with a 1 m x 0.11 m step on the south edge. The contour
    (Douglas-Peucker 0.10 m) moves off the slab there; that strip is no roof opening (it stopped as 'not a
    shaft'), the roof closes the whole envelope."""
    outline = STEPS_84[name]
    spec, report = extract_spec(panelised(outlines=(outline, outline), slab=_envelope(outline)), PANEL_OBJECT)
    assert report["roof"]["closed_share"] >= 0.999
    assert "holes_ignored" not in report["roof"]


def test_a_real_roof_hole_under_a_simplified_panel_contour_still_stops():
    """#84 control: the coverage check against the unsimplified envelope still sees a 0.2 x 0.8 m slab hole."""
    outline = STEPS_84["bump-out"]
    dump = panelised(outlines=(outline, outline), slab=_envelope(outline))
    roof = Mesh("RoofWithHole")
    flat(roof, Polygon(_envelope(outline), [[[2, 2], [2.2, 2], [2.2, 2.8], [2, 2.8]]]), 6.6, up=True)   # off the mass
    slabs = next(m for m in dump["meshes"] if m["name"] == "Slabs")
    slabs["triangles"] = [tr for tr in slabs["triangles"] if max(slabs["vertices"][i][2] for i in tr) < 6.5]
    dump["meshes"].append({**roof.dump(), "name": "Slabs2"})
    with pytest.raises(SpecError, match=r"opening of 0.16 m2 at \(2.10, 2.40\) that is not a shaft"):
        extract_spec(dump, {**PANEL_OBJECT, "slabs": ["Slabs", "Slabs2"]})


def test_probe_steps_within_the_simplification_never_read_as_roof_openings():
    """#84 probe (seed 84, 12 cases): a rectangular step 0.3-2.0 m wide and 0.02-0.15 m deep, in or out, on a
    random edge of the 10 m square; the roof slab is the panel envelope. The roof never stops and closes it."""
    rng = np.random.default_rng(84)
    for _ in range(12):
        w, d, x0 = rng.uniform(0.3, 2.0), rng.uniform(0.02, 0.15), rng.uniform(1.0, 7.0)
        d = d if rng.random() < 0.5 else -d                      # + inward (notch), - outward (bump)
        south = [[0, 0], [x0, 0], [x0, d], [x0 + w, d], [x0 + w, 0], [10, 0], [10, 10], [0, 10]]
        k = int(rng.integers(4))                                 # turn the square so the step is on any edge
        rot = [[[x, y], [10 - y, x], [10 - x, 10 - y], [y, 10 - x]][k] for x, y in south]
        outline = [[round(a, 4), round(b, 4)] for a, b in rot]
        _, report = extract_spec(panelised(outlines=(outline, outline), slab=_envelope(outline)), PANEL_OBJECT)
        assert report["roof"]["closed_share"] >= 0.999, (w, d, x0, k)


# --- #95: a real roof opening at the facade line is never left out as contour simplification

def _panel_roof_with_hole(outline, hole):
    """Panelised storey whose roof slab is the envelope with `hole` cut out (the #84 roof replacement)."""
    dump = panelised(outlines=(outline, outline), slab=_envelope(outline))
    roof = Mesh("RoofWithHole")
    flat(roof, Polygon(_envelope(outline), [hole]), 6.6, up=True)
    slabs = next(m for m in dump["meshes"] if m["name"] == "Slabs")
    slabs["triangles"] = [tr for tr in slabs["triangles"] if max(slabs["vertices"][i][2] for i in tr) < 6.5]
    dump["meshes"].append({**roof.dump(), "name": "Slabs2"})
    return dump, {**PANEL_OBJECT, "slabs": ["Slabs", "Slabs2"]}


def test_a_roof_hole_at_the_facade_line_stops_on_a_plain_storey():
    """#95: a 2 x 0.08 m roof opening on the south facade line, inside the storey, must ask.
    It is a real opening, never left out as contour simplification."""
    b = Mesh("Body")
    hole = [[3, 0.01], [5, 0.01], [5, 0.09], [3, 0.09]]
    walls(b, SQUARE10, 0.0, 6.6)
    flat(b, Polygon(SQUARE10, [hole]), 6.6, up=True)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    with pytest.raises(SpecError, match=r"opening of 0.16 m2 at \(4.00, 0.05\) that is not a shaft"):
        extract_spec(dump_of(b), OBJECT)


@pytest.mark.parametrize("name", sorted(STEPS_84))
def test_a_roof_hole_at_the_facade_line_stops_under_a_simplified_panel_contour(name):
    """#95 with #84: a real opening at the facade line, inside the storey, under a panel contour that
    Douglas-Peucker simplifies, must ask. It is never left out as contour simplification."""
    outline = STEPS_84[name]
    hole = [[2, 0.01], [4, 0.01], [4, 0.09], [2, 0.09]]
    dump, obj = _panel_roof_with_hole(outline, hole)
    with pytest.raises(SpecError, match="that is not a shaft"):
        extract_spec(dump, obj)


def test_probe_real_roof_holes_within_the_simplification_band_always_stop():
    """#95 probe (seed 95, 24 cases): a real roof opening inside the storey, wholly within 0.1001 m of the
    facade line, must ask on a plain storey and under a simplified panel step. Never listed as simplification."""
    rng = np.random.default_rng(95)
    names = sorted(STEPS_84)
    for i in range(24):
        w = float(rng.uniform(0.8, 3.0))
        x0 = float(rng.uniform(1.0, 9.0 - w))
        y0 = float(rng.uniform(0.005, 0.03))
        y1 = y0 + float(rng.uniform(0.04, 0.07))
        panel = i % 2 == 1
        if panel:
            k = int(rng.integers(1, 4))          # north, east or west: the step stays on the south edge
            name = names[int(rng.integers(len(names)))]
        else:
            k = int(rng.integers(4))
            name = "plain"
        south = ((x0, y0), (x0 + w, y0), (x0 + w, y1), (x0, y1))
        hole = [[[x, y], [10 - y, x], [10 - x, 10 - y], [y, 10 - x]][k] for x, y in south]
        if panel:
            dump, obj = _panel_roof_with_hole(STEPS_84[name], hole)
        else:
            b = Mesh("Body")
            walls(b, SQUARE10, 0.0, 6.6)
            flat(b, Polygon(SQUARE10, [hole]), 6.6, up=True)
            flat(b, Polygon(SQUARE10), 0.0, up=False)
            dump, obj = dump_of(b), OBJECT
        params = (w, x0, y0, y1, k, name)
        try:
            extract_spec(dump, obj)
        except SpecError as e:
            assert "that is not a shaft" in str(e), (str(e), params)
        else:
            pytest.fail(f"no stop for a real roof opening {params}")
