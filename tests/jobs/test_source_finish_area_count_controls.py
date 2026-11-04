"""new-case: count-mode versus area-mode controls for source_finish_report.

Acceptance table. A and B are the finish strings "A" and "B". Streams are
literal synthetic lists. Areas below are hand totals (0.5+0.25+0.25 = 1,
0.5+0.25 = 0.75, 0.75+0.5 = 1.25, 0.25+0.25 = 0.5, 0.75+0.75 = 1.5,
0.5+0.5 = 1, four times 0.5 = 2). Oracles are these numbers, not
match_source_faces, poly_areas or tri_areas. Tolerance is 1e-6 + 1e-5*area
(about 1.1e-5 on area 1); every failing residual is 0.25 or 0.5.

1. src_faces [[0, 1, 2, 3]], expected ["A"], owners [(0,)] * 3,
   delivered ["A"] * 3, no areas (count mode: a quad needs len(face)-2 = 2
   triangles, three were delivered)
   -> ok false, tris 3, source_polygons_not_covered 1, uncovered_examples [0],
   wrong_finish = unmatched = ambiguous = 0, examples [].

2. Same streams, t_areas [0.5, 0.25, 0.25], p_areas [1.0]
   -> ok true, tris 3, uncovered 0, all counters 0.

3. owners [(0,)] * 2, delivered ["A"] * 2, t_areas [0.5, 0.25] on that quad.
   Count mode (areas omitted) -> ok true, tris 2, uncovered 0.
   Area mode p_areas [1.0] -> ok false, polygon 0 uncovered (count 1,
   examples [0]).

4. t_areas [0.75, 0.5] against p_areas [1.0] (two triangles on the quad)
   -> area mode ok false (over-coverage), uncovered [0].

5. Two quads src_faces [[0, 1, 2, 3], [4, 5, 6, 7]], expected ["A", "B"],
   owners [(0,), (0,), (1,), (1,)], delivered ["A", "A", "B", "B"],
   p_areas [1, 1].
   t_areas [0.25, 0.25, 0.75, 0.75] -> sums are both 2, but per polygon the
   areas are 0.5 and 1.5, so ok false, uncovered count 2, examples [0, 1].
   t_areas [0.5, 0.5, 0.5, 0.5] -> ok true.

6. delivered ["A", "A", "B"] on the three-triangle quad with t_areas
   [0.5, 0.25, 0.25] and p_areas [1.0]
   -> wrong_finish 1, uncovered 0, ok false, examples contain tri 2 /
   source_polygon 0 / expected "A" / delivered "B".

7. One permutation applied to owners, delivered and t_areas together leaves
   source_polygons_not_covered, uncovered_examples, unmatched, ambiguous,
   wrong_finish, tris and ok unchanged. examples is order-sensitive and is
   not compared.

8. After every call, expected, src_faces, owners, delivered, t_areas and
   p_areas still equal their deep copies.
"""
import copy
import itertools
import math
import random
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "jobs" / "TEC26-OKS" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import qa_packages  # noqa: E402

A = "A"
B = "B"
QUAD = [[0, 1, 2, 3]]
TWO_QUADS = [[0, 1, 2, 3], [4, 5, 6, 7]]

_STABLE = (
    "ok",
    "tris",
    "source_polygons_not_covered",
    "uncovered_examples",
    "unmatched",
    "ambiguous",
    "wrong_finish",
)


def _call(expected, src_faces, owners, delivered, t_areas=None, p_areas=None):
    """Call the real report and require every input to be unchanged."""
    assert len(owners) == len(delivered)
    if t_areas is not None or p_areas is not None:
        assert t_areas is not None and p_areas is not None
        assert len(t_areas) == len(owners)
        assert len(p_areas) == len(src_faces)
        assert all(math.isfinite(x) and x > 0 for x in t_areas)
        assert all(math.isfinite(x) and x > 0 for x in p_areas)
    snap = {
        "expected": copy.deepcopy(expected),
        "src_faces": copy.deepcopy(src_faces),
        "owners": copy.deepcopy(owners),
        "delivered": copy.deepcopy(delivered),
        "t_areas": copy.deepcopy(t_areas),
        "p_areas": copy.deepcopy(p_areas),
    }
    result = qa_packages.source_finish_report(
        expected, src_faces, owners, delivered, t_areas=t_areas, p_areas=p_areas,
    )
    assert expected == snap["expected"]
    assert src_faces == snap["src_faces"]
    assert owners == snap["owners"]
    assert delivered == snap["delivered"]
    assert t_areas == snap["t_areas"]
    assert p_areas == snap["p_areas"]
    return result


def _expect(result, *, ok, tris, uncovered, wrong=0, unmatched=0, ambiguous=0, examples=None):
    assert result["tris"] == tris
    assert result["ok"] is ok
    assert result["source_polygons_not_covered"] == len(uncovered)
    assert result["uncovered_examples"] == uncovered
    assert result["wrong_finish"] == wrong
    assert result["unmatched"] == unmatched
    assert result["ambiguous"] == ambiguous
    if examples is not None:
        assert result["examples"] == examples


def _stable(result):
    return {key: result[key] for key in _STABLE}


def _permute(owners, delivered, t_areas, order):
    return (
        [owners[i] for i in order],
        [delivered[i] for i in order],
        [t_areas[i] for i in order],
    )


def test_count_mode_three_triangles_leave_quad_uncovered():
    result = _call([A], QUAD, [(0,)] * 3, [A] * 3)
    _expect(
        result, ok=False, tris=3, uncovered=[0],
        examples=[],
    )


def test_area_mode_three_triangles_cover_quad():
    result = _call(
        [A], QUAD, [(0,)] * 3, [A] * 3,
        t_areas=[0.5, 0.25, 0.25], p_areas=[1.0],
    )
    _expect(result, ok=True, tris=3, uncovered=[], examples=[])


def test_two_triangles_pass_count_mode_and_fail_area_mode():
    owners = [(0,)] * 2
    delivered = [A] * 2
    t_areas = [0.5, 0.25]
    count = _call([A], QUAD, owners, delivered)
    _expect(count, ok=True, tris=2, uncovered=[], examples=[])
    area = _call([A], QUAD, owners, delivered, t_areas=t_areas, p_areas=[1.0])
    _expect(area, ok=False, tris=2, uncovered=[0], examples=[])


def test_area_over_coverage_marks_polygon_uncovered():
    result = _call(
        [A], QUAD, [(0,)] * 2, [A] * 2,
        t_areas=[0.75, 0.5], p_areas=[1.0],
    )
    _expect(result, ok=False, tris=2, uncovered=[0], examples=[])


def test_global_sum_can_match_while_each_polygon_is_uncovered():
    owners = [(0,), (0,), (1,), (1,)]
    delivered = [A, A, B, B]
    split = _call(
        [A, B], TWO_QUADS, owners, delivered,
        t_areas=[0.25, 0.25, 0.75, 0.75], p_areas=[1.0, 1.0],
    )
    _expect(split, ok=False, tris=4, uncovered=[0, 1], examples=[])
    even = _call(
        [A, B], TWO_QUADS, owners, delivered,
        t_areas=[0.5, 0.5, 0.5, 0.5], p_areas=[1.0, 1.0],
    )
    _expect(even, ok=True, tris=4, uncovered=[], examples=[])


def test_wrong_finish_on_area_complete_triangle():
    result = _call(
        [A], QUAD, [(0,)] * 3, [A, A, B],
        t_areas=[0.5, 0.25, 0.25], p_areas=[1.0],
    )
    _expect(
        result, ok=False, tris=3, uncovered=[], wrong=1,
        examples=[{"tri": 2, "source_polygon": 0, "expected": A, "delivered": B}],
    )


def test_paired_permutation_preserves_coverage_and_defect_counters():
    """Same order applied to owners, delivered and t_areas. 6+24+16 probes."""
    seen = 0
    owners = [(0,), (0,), (0,)]
    delivered = [A, A, B]
    t_areas = [0.5, 0.25, 0.25]
    base = _stable(_call([A], QUAD, owners, delivered, t_areas=t_areas, p_areas=[1.0]))
    for order in itertools.permutations(range(3)):
        o, d, t = _permute(owners, delivered, t_areas, order)
        assert _stable(_call([A], QUAD, o, d, t_areas=t, p_areas=[1.0])) == base
        seen += 1

    owners = [(0,), (0,), (1,), (1,)]
    delivered = [A, A, B, B]
    t_areas = [0.25, 0.25, 0.75, 0.75]
    base = _stable(_call(
        [A, B], TWO_QUADS, owners, delivered, t_areas=t_areas, p_areas=[1.0, 1.0],
    ))
    for order in itertools.permutations(range(4)):
        o, d, t = _permute(owners, delivered, t_areas, order)
        assert _stable(_call(
            [A, B], TWO_QUADS, o, d, t_areas=t, p_areas=[1.0, 1.0],
        )) == base
        seen += 1

    rng = random.Random(0x656F8016)
    for _ in range(16):
        order = list(range(4))
        rng.shuffle(order)
        o, d, t = _permute(owners, delivered, t_areas, order)
        assert _stable(_call(
            [A, B], TWO_QUADS, o, d, t_areas=t, p_areas=[1.0, 1.0],
        )) == base
        seen += 1
    assert seen == 46
