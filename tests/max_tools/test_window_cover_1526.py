"""new-case: #1526 frame-bounded glass/grille cover at the public build_type seam."""
import copy
import itertools
from pathlib import Path
from typing import Any

import pytest

from test_window_seating_1449 import STD, bounds, opening, wg

LIBRARY = wg.load_library(str(Path(__file__).resolve().parents[2] / 'library/windows'))


def panels(mesh):
    return [[lo[0], lo[2], hi[0], hi[2]]
            for part in ('glass', 'grille') for fi in mesh['parts'][part]
            for lo, hi in [bounds(mesh, fi)]]


def assert_bounded(mesh):
    w, _, h = mesh['size_m']
    rects = panels(mesh)
    for x0, z0, x1, z1 in rects:
        assert 0 <= x0 < x1 <= w
        assert 0 <= z0 < z1 <= h
    for a, b in itertools.combinations(rects, 2):
        assert min(a[2], b[2]) - max(a[0], b[0]) <= 1e-9 or min(a[3], b[3]) - max(a[1], b[1]) <= 1e-9


@pytest.mark.parametrize('case', ['WT-24', 'thin-face', 'thin-impost'])
@pytest.mark.parametrize('kind', ['glass', 'grille'])
def test_review_reproductions_have_bounded_cover(case, kind):
    if case == 'WT-24':
        entry = copy.deepcopy(next(t for t in LIBRARY['types'] if t['id'] == case))
    else:
        face, impost = (0.01, 0.05) if case == 'thin-face' else (0.05, 0.03)
        entry = opening(frame_profile_m={'face_m': face, 'depth_m': 0.07, 'impost_m': impost})
        if case == 'thin-impost':
            entry['panes_m'] = [[0.05, 0.05, 0.585, 1.45], [0.615, 0.05, 1.15, 1.45]]
    if kind == 'grille':
        entry['grilles_m'] = entry.pop('panes_m')
    before = copy.deepcopy((entry, STD))
    mesh = wg.build_type(entry, STD)
    assert_bounded(mesh)
    assert (entry, STD) == before
    # Each reduction must be exposed, including the field, edge and actual cover.
    reports = mesh['clamped_infill_edges']
    assert reports
    assert all(r['kind'] == kind and r['requested_m'] == 0.02 and 0 <= r['cover_m'] < 0.02
               and r['edge'] in ('left', 'bottom', 'right', 'top') for r in reports)
    if case == 'thin-face':
        assert panels(mesh)[0] == pytest.approx([0, 0, 1.2, 1.5])
        assert {r['cover_m'] for r in reports} == {0.01}
    elif case == 'thin-impost':
        assert panels(mesh)[0][2] == pytest.approx(0.6)
        assert panels(mesh)[1][0] == pytest.approx(0.6)
        assert [r['cover_m'] for r in reports] == pytest.approx([0.015, 0.015])


@pytest.mark.parametrize('entry', LIBRARY['types'], ids=lambda t: t['id'])
def test_every_library_type_has_no_panel_overlap_or_protrusion(entry):
    assert_bounded(wg.build_type(entry, STD))


@pytest.mark.parametrize('gap', [0.004, 0.025, 0.03, 0.04, 0.05])
@pytest.mark.parametrize('transpose', [False, True])
@pytest.mark.parametrize('kinds', [('glass', 'glass'), ('glass', 'grille'), ('glass', 'opaque')])
def test_synthetic_staggered_matrix_is_bounded_and_order_independent(gap, transpose, kinds):
    # Synthetic diagonal corners: the perpendicular projections are separated by
    # only 4 mm, so inspecting clear-light intersections alone misses collisions.
    rects = [[0.05, 0.05, 0.55, 0.65], [0.55 + gap, 0.654, 1.15, 1.45]]
    if transpose:
        rects = [[r[1], r[0], r[3], r[2]] for r in rects]
    entry: dict[str, Any] = opening(width_m=1.5 if transpose else 1.2, height_m=1.2 if transpose else 1.5,
                    panes_m=[], opaque_m=[])
    for kind, key in (('glass', 'panes_m'), ('grille', 'grilles_m'), ('opaque', 'opaque_m')):
        entry[key] = [r for k, r in zip(kinds, rects) if k == kind]
    before = copy.deepcopy(entry)
    mesh = wg.build_type(entry, STD)
    assert entry == before
    assert_bounded(mesh)
    reversed_entry = dict(entry)
    for key in ('panes_m', 'grilles_m', 'opaque_m'):
        reversed_entry[key] = list(reversed(before[key]))
    reordered = wg.build_type(reversed_entry, STD)
    assert sorted(panels(mesh)) == sorted(panels(reordered))
    assert_bounded(reordered)
    # All reported values match the emitted panel edges, not a nominal cover.
    for report in mesh['clamped_infill_edges']:
        kind, light = mesh['fields'][report['index']]
        fi = mesh['parts'][kind][sum(k == kind for k, _ in mesh['fields'][:report['index']])]
        lo, hi = bounds(mesh, fi)
        actual = dict(left=light[0]-lo[0], bottom=light[1]-lo[2],
                      right=hi[0]-light[2], top=hi[2]-light[3])
        assert actual[report['edge']] == pytest.approx(report['cover_m'], abs=1e-7)
    assert entry == before


def test_unconstrained_and_npm_controls_have_no_clamp_reports():
    assert wg.build_type(opening(), STD)['clamped_infill_edges'] == []
    assert wg.build_type(opening(), STD, {'variant': 'npm'})['clamped_infill_edges'] == []

