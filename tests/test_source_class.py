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


def _box(scale=1.0, origin=(0.0, 0.0, 0.0)):
    """Closed box with duplicated corners (a shell only after welding). Synthetic."""
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
    verts, tris = [], []
    for face in faces:
        n = len(verts)
        verts.extend(face)
        tris.extend(((n, n + 1, n + 2), (n, n + 2, n + 3)))
    return np.asarray(verts, dtype=float), np.asarray(tris, dtype=np.int64)


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


def test_workflow_requires_checker_on_every_shown_build_and_a_poll_timeout():
    text = (ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8")
    triggers = text.split("## Triggers", 1)[1].split("## Rule of three", 1)[0]
    assert "shown to the user" in triggers
    assert "independent-checker" in triggers
    assert "inv_xview" in triggers
    assert "6 polls" in triggers
    assert "30 minutes" in triggers
    assert "progress line" in triggers
    assert "After every job build that is shown to the user" in text


def test_independent_checker_includes_inv_xview():
    text = (ROOT / ".claude/agents/independent-checker.md").read_text(encoding="utf-8")
    assert "shown to the user" in text
    assert "inv_xview" in text
    assert "dt qa xview" in text
    assert "527" in text
    assert text.split("---", 2)[1].lstrip().lower().find("use when") >= 0 or "Use when" in text.split("---", 2)[1]


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
    assert "vyatskaya-tow02.md" in readme
    assert "panelised" in readme
