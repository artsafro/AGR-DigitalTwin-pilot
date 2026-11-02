"""Source class from connected parts, largest-part area share, and a closed shell (#533).

Synthetic meshes only. A panelised curtain is many open parts whose largest share is about 11 %
of the area. A monolithic source is a closed shell and routes to `dt spec extract`.
"""
import math
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    from dt_ai.spec.source_class import (
        PANEL_HINT_SHARE, PANELISED, MONOLITHIC, ROUTE_EXTRACT, ROUTE_MEASUREMENT,
        SourceClassError, classify_source, source_facts, source_route,
    )
    return (PANEL_HINT_SHARE, PANELISED, MONOLITHIC, ROUTE_EXTRACT, ROUTE_MEASUREMENT,
            SourceClassError, classify_source, source_facts, source_route)


def _quad(origin, width, height=1.0):
    """One open rectangle (two triangles) of area width * height, lying on z = origin[2]."""
    x, y, z = origin
    return [
        (x, y, z), (x + width, y, z), (x + width, y + height, z), (x, y + height, z)
    ]


def _add_quad(verts, tris, origin, width, height=1.0):
    n = len(verts)
    verts.extend(_quad(origin, width, height))
    tris.extend(((n, n + 1, n + 2), (n, n + 2, n + 3)))


def _curtain(largest_area, other_areas, gap=3.0):
    """Disconnected open panels. Part i sits `gap` metres from the next, so they do not weld."""
    verts, tris = [], []
    _add_quad(verts, tris, (0.0, 0.0, 0.0), largest_area)
    for i, area in enumerate(other_areas, start=1):
        _add_quad(verts, tris, (i * gap, 0.0, 0.0), area)
    return np.asarray(verts, dtype=float), np.asarray(tris, dtype=np.int64)


def _box(scale=1.0, origin=(0.0, 0.0, 0.0), reverse=()):
    """Closed box with duplicated corners (a shell only after welding). Synthetic.

    `reverse` is a set of face indices whose two triangles are wound the other way.
    Reversing faces does not change the undirected edges.
    """
    x, y, z = origin
    s = float(scale)
    lo = (x, y, z)
    hi = (x + s, y + s, z + s)
    faces = (
        ((lo[0], lo[1], lo[2]), (lo[0], hi[1], lo[2]), (hi[0], hi[1], lo[2]), (hi[0], lo[1], lo[2])),
        ((lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])),
        ((lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], lo[1], hi[2]), (lo[0], lo[1], hi[2])),
        ((hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (hi[0], hi[1], hi[2]), (hi[0], lo[1], hi[2])),
        ((hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]), (lo[0], hi[1], hi[2]), (hi[0], hi[1], hi[2])),
        ((lo[0], hi[1], lo[2]), (lo[0], lo[1], lo[2]), (lo[0], lo[1], hi[2]), (lo[0], hi[1], hi[2])),
    )
    flipped = set(reverse)
    verts, tris = [], []
    for index, face in enumerate(faces):
        n = len(verts)
        verts.extend(face)
        pair = ((n, n + 1, n + 2), (n, n + 2, n + 3))
        if index in flipped:
            pair = tuple(tuple(reversed(tri)) for tri in pair)
        tris.extend(pair)
    return np.asarray(verts, dtype=float), np.asarray(tris, dtype=np.int64)


def _shell_witness(center=(0.0, 0.0, 0.0), reverse=()):
    """Unit cube plus ten disconnected open panels of area 4. Synthetic.

    The cube is the largest part (area 6 of 46, share 0.1304). A missed shell
    classifies the mesh as panelised.
    """
    origin = (center[0] - 0.5, center[1] - 0.5, center[2] - 0.5)
    cube_v, cube_t = _box(origin=origin, reverse=reverse)
    panels_v, panels_t = _curtain(4.0, [4.0] * 9, gap=3.0)
    panels_v = panels_v.copy()
    panels_v[:, 0] += 30.0
    verts = np.vstack([cube_v, panels_v])
    tris = np.vstack([cube_t, panels_t + len(cube_v)])
    return verts, tris


def _welded_cube_edge_uses(vertices, triangles):
    """Undirected edge counts of the cube (its 12 triangles) after welding."""
    from dt_ai.spec.source_class import _welded
    _v, tris = _welded(vertices, triangles)
    counts = {}
    for a, b, c in tris[:12]:
        for i, j in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            edge = (i, j) if i < j else (j, i)
            counts[edge] = counts.get(edge, 0) + 1
    return counts


def _panelised_tow02():
    """90 open parts, largest area 11, the other 89 area 1 each: largest share 11 %."""
    return _curtain(11.0, [1.0] * 89)


def test_panelised_fixture_is_panelised_and_skips_extract():
    _, panelised, _, route_extract, route_measure, _, classify_source, source_facts, source_route = _load()
    facts = source_facts(*_panelised_tow02())
    assert facts.connected_parts == 90
    assert facts.largest_share == pytest.approx(0.11, abs=1e-9)
    assert facts.shell is False
    assert facts.source_class == panelised
    assert classify_source(*_panelised_tow02()) == panelised
    assert source_route(panelised) == route_measure
    assert route_extract not in source_route(panelised)


def test_closed_shell_is_not_panelised():
    _, panelised, monolithic, route_extract, _, _, classify_source, source_facts, source_route = _load()
    facts = source_facts(*_box())
    assert facts.connected_parts == 1
    assert facts.shell is True
    assert facts.largest_share == pytest.approx(1.0)
    assert facts.source_class == monolithic
    assert classify_source(*_box()) != panelised
    assert source_route(monolithic) == route_extract


def test_shell_present_overrides_a_small_largest_share():
    """A closed box plus many larger open panels is still monolithic: a shell is present."""
    _, panelised, monolithic, _, _, _, classify_source, source_facts, _ = _load()
    box_v, box_t = _box(scale=1.0, origin=(0.0, 0.0, 0.0))
    panels_v, panels_t = _curtain(4.0, [4.0] * 9, gap=3.0)
    panels_v = panels_v.copy()
    panels_v[:, 0] += 20.0
    verts = np.vstack([box_v, panels_v])
    tris = np.vstack([box_t, panels_t + len(box_v)])
    facts = source_facts(verts, tris)
    assert facts.shell is True
    assert facts.largest_share < 0.5
    assert facts.source_class == monolithic
    assert classify_source(verts, tris) != panelised


def test_single_part_share_100_is_monolithic():
    _, panelised, monolithic, route_extract, _, _, classify_source, source_facts, source_route = _load()
    verts, tris = _curtain(1.0, [])
    facts = source_facts(verts, tris)
    assert facts.connected_parts == 1
    assert facts.largest_share == pytest.approx(1.0)
    assert facts.shell is False
    assert facts.source_class == monolithic
    assert classify_source(verts, tris) != panelised
    assert source_route(facts.source_class) == route_extract


def test_two_part_equal_split_is_an_error():
    _, _, _, _, _, err, _, source_facts, _ = _load()
    with pytest.raises(err, match="PANEL_HINT_SHARE"):
        source_facts(*_curtain(1.0, [1.0]))


def test_exact_threshold_with_a_smaller_remainder_is_an_error():
    """Largest share == 0.5 (areas 1, 0.5, 0.5) is the threshold, not a silent monolithic."""
    share, _, _, _, _, err, _, source_facts, _ = _load()
    assert share == 0.5
    with pytest.raises(err, match="PANEL_HINT_SHARE"):
        source_facts(*_curtain(1.0, [0.5, 0.5]))


@pytest.mark.parametrize("vertices,triangles,match", [
    (np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), "empty"),
    (np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]),
     np.array([[0, 1, 2]]), "area"),
    (np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, np.nan]]),
     np.array([[0, 1, 2]]), "non-finite"),
    (np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, np.inf]]),
     np.array([[0, 1, 2]]), "non-finite"),
    (np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
     np.array([[0, 1, 5]]), "index"),
    (np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]]),
     np.array([[0, 1, 2, 3]]), "unsupported"),
    (np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
     np.array([[0.0, 1.5, 2.0]]), "fractional"),
])
def test_fail_closed_inputs(vertices, triangles, match):
    _, _, _, _, _, err, classify_source, source_facts, _ = _load()
    with pytest.raises(err, match=match):
        source_facts(vertices, triangles)
    with pytest.raises(err, match=match):
        classify_source(vertices, triangles)


def test_unknown_class_has_no_route():
    _, _, _, _, _, err, _, _, source_route = _load()
    with pytest.raises(err, match="unknown"):
        source_route("")
    with pytest.raises(err, match="unknown"):
        source_route("panel")


def test_brute_share_below_threshold_is_panelised():
    share, panelised, _, route_extract, route_measure, _, classify_source, source_facts, source_route = _load()
    rng = np.random.default_rng(533)
    drawn = rng.uniform(0.05, share - 0.02, size=24)
    assert len(drawn) == 24
    for largest in drawn:
        others_n = int(math.floor((1.0 - largest) / largest)) + 1
        other = (1.0 - largest) / others_n
        assert other < largest < share
        verts, tris = _curtain(largest, [other] * others_n)
        facts = source_facts(verts, tris)
        assert facts.shell is False
        assert facts.connected_parts == others_n + 1
        assert facts.largest_share < share
        assert facts.source_class == panelised
        assert classify_source(verts, tris) == panelised
        assert source_route(panelised) == route_measure
        assert route_extract not in source_route(panelised)


def test_brute_share_above_threshold_is_monolithic():
    share, panelised, monolithic, route_extract, _, _, classify_source, source_facts, source_route = _load()
    rng = np.random.default_rng(534)
    drawn = rng.uniform(share + 0.02, 0.95, size=24)
    assert len(drawn) == 24
    for largest in drawn:
        other = 1.0 - largest
        assert other < largest
        verts, tris = _curtain(largest, [other])
        facts = source_facts(verts, tris)
        assert facts.shell is False
        assert facts.largest_share > share
        assert facts.source_class == monolithic
        assert classify_source(verts, tris) != panelised
        assert source_route(monolithic) == route_extract


def test_oriented_origin_cube_with_panels_is_a_shell():
    """Control: consistent winding, cube centred at the origin, ten open panels."""
    _, panelised, monolithic, _, _, _, _, source_facts, _ = _load()
    verts, tris = _shell_witness(center=(0.0, 0.0, 0.0), reverse=())
    uses = _welded_cube_edge_uses(verts, tris)
    assert uses and set(uses.values()) == {2}
    facts = source_facts(verts, tris)
    assert facts.connected_parts == 11
    assert facts.largest_share == pytest.approx(0.1304, abs=5e-5)
    assert facts.shell is True
    assert facts.source_class == monolithic
    assert facts.source_class != panelised


def test_three_reversed_faces_on_origin_cube_stay_a_shell():
    """Witness: reverse three faces. Edges stay paired; the mesh must not become panelised."""
    _, panelised, monolithic, _, _, err, _, source_facts, _ = _load()
    verts, tris = _shell_witness(center=(0.0, 0.0, 0.0), reverse=(0, 1, 2))
    uses = _welded_cube_edge_uses(verts, tris)
    # 12 cube edges plus one diagonal on each of the 6 faces.
    assert len(uses) == 18 and set(uses.values()) == {2}
    try:
        facts = source_facts(verts, tris)
    except err:
        return
    assert facts.connected_parts == 11
    assert facts.largest_share == pytest.approx(0.1304, abs=5e-5)
    assert facts.shell is True
    assert facts.source_class == monolithic
    assert facts.source_class != panelised


def test_translated_cube_oriented_and_three_faces_reversed():
    """Same cube centred away from the origin, consistent winding and three faces reversed."""
    _, panelised, monolithic, _, _, err, _, source_facts, _ = _load()
    center = (12.0, -4.0, 7.0)
    for reverse in ((), (0, 1, 2)):
        verts, tris = _shell_witness(center=center, reverse=reverse)
        uses = _welded_cube_edge_uses(verts, tris)
        assert set(uses.values()) == {2}
        try:
            facts = source_facts(verts, tris)
        except err:
            continue
        assert facts.shell is True
        assert facts.connected_parts == 11
        assert facts.source_class == monolithic
        assert facts.source_class != panelised


def test_brute_winding_subsets_never_panelised():
    """Every subset of reversed cube faces, at three translations, stays a shell or errors."""
    _, panelised, monolithic, _, _, err, _, source_facts, _ = _load()
    translations = ((0.0, 0.0, 0.0), (12.0, -4.0, 7.0), (-20.0, 3.0, 15.0))
    seen = 0
    for mask in range(2 ** 6):
        reverse = tuple(i for i in range(6) if mask & (1 << i))
        for center in translations:
            seen += 1
            verts, tris = _shell_witness(center=center, reverse=reverse)
            try:
                facts = source_facts(verts, tris)
            except err:
                continue
            assert facts.shell is True
            assert facts.source_class == monolithic
            assert facts.source_class != panelised
    assert seen == 192


def test_brute_closed_shells_stay_monolithic():
    _, panelised, monolithic, route_extract, _, _, classify_source, source_facts, source_route = _load()
    rng = np.random.default_rng(535)
    scales = rng.uniform(0.2, 4.0, size=12)
    for i, scale in enumerate(scales):
        facts = source_facts(*_box(scale=float(scale), origin=(i * 20.0, 0.0, 0.0)))
        assert facts.shell is True and facts.connected_parts == 1
        assert facts.source_class == monolithic
        assert classify_source(*_box(scale=float(scale), origin=(i * 20.0, 0.0, 0.0))) != panelised
        assert source_route(monolithic) == route_extract


def test_skill_routes_panelised_away_from_extract():
    text = (ROOT / ".agents/skills/analyze-architectural-source/SKILL.md").read_text(encoding="utf-8")
    assert "Source class" in text
    assert "connected parts" in text
    assert "PANEL_HINT_SHARE" in text
    assert "panelised" in text
    assert "measurement+direct-build" in text
    assert "dt spec extract" in text
    assert "docs/sources/" in text
    assert "D066" in text
    mirror = (ROOT / ".claude/skills/analyze-architectural-source/SKILL.md").read_text(encoding="utf-8")
    assert mirror == text


def _flat(text):
    return " ".join(text.split())


def _checker_policy_texts():
    workflow = (ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8")
    checker = (ROOT / ".claude/agents/independent-checker.md").read_text(encoding="utf-8")
    subagents = workflow.split("## Subagents", 1)[1].split("## Triggers", 1)[0]
    triggers = workflow.split("## Triggers", 1)[1].split("## Rule of three", 1)[0]
    return _flat(subagents), _flat(triggers), _flat(checker)


def test_unshown_engine_run_still_requires_the_checker():
    subagents, triggers, checker = _checker_policy_texts()
    for text in (subagents, triggers, checker):
        assert "every engine run, shown or not" in text
        assert "independent-checker" in text
        assert "inv_xview" in text
        assert "dt qa xview" in text
        assert "527" in text


def test_shown_direct_or_lego_build_requires_the_checker():
    subagents, triggers, checker = _checker_policy_texts()
    for text in (subagents, triggers, checker):
        assert "direct / Lego" in text
        assert "shown or reported to the user" in text
        assert "independent-checker" in text


def test_checker_runs_before_the_build_is_shown():
    subagents, triggers, checker = _checker_policy_texts()
    for text in (subagents, triggers, checker):
        assert "before the build is shown or reported" in text


def test_each_new_build_version_needs_its_own_check():
    subagents, triggers, checker = _checker_policy_texts()
    for text in (subagents, triggers, checker):
        assert "Each new build version needs its own check" in text


def test_poll_timeout_and_progress_report():
    subagents, triggers, checker = _checker_policy_texts()
    assert "independent-checker" in subagents
    assert "independent-checker" in checker
    for text in (triggers, checker):
        assert "6 polls" in text
        assert "30 minutes" in text
        assert "progress line" in text
        assert "polls remain" in text


def test_tow02_source_record():
    page = (ROOT / "docs/sources/vyatskaya-tow02.md").read_text(encoding="utf-8")
    readme = (ROOT / "docs/sources/README.md").read_text(encoding="utf-8")
    assert "5561" in page
    assert "11%" in page
    assert "panelised" in page
    assert "measurement" in page
    assert "dt spec extract" in page
    assert "measure-v001" in page
    assert "absent" in page
    assert "copied from" in page and "jobs/vyatskaya-tow02/object.json" in page
    assert "historical" in page and "not recomputed" in page
    assert "git-ignored" in page
    assert "vyatskaya-tow02.md" in readme
    assert "panelised" in readme
