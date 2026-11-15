"""new-case: #1449 general window seating; synthetic one-opening regression."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('window_seating_core', ROOT / 'adapters/max/agr_tools/windowgen_core.py')
wg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wg)
STD = wg.load_library(str(ROOT / 'library/windows'))['standard']


def opening(**changes):
    return dict(dict(id='synthetic-one', role='window', width_m=1.2, height_m=1.5,
                     panes_m=[[0.057, 0.057, 1.143, 1.443]], opaque_m=[],
                     source={'occurrences': 1}), **changes)


def bounds(mesh, face):
    pts = [mesh['verts'][i] for i in mesh['faces'][face]]
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def overlaps(mesh):
    (_, light), = mesh['fields']
    lo, hi = bounds(mesh, mesh['parts']['glass'][0])
    return [light[0]-lo[0], light[1]-lo[2], hi[0]-light[2], hi[2]-light[3]]


def test_one_opening_glass_is_under_every_frame_edge():
    # B v005 behaviour: a panel exactly matching its light has zero overlap.
    legacy = [0.0]*4
    assert not all(x >= 0.015 for x in legacy)
    mesh = wg.build_type(opening(), STD)
    assert min(overlaps(mesh)) >= 0.015
    assert overlaps(mesh) == pytest.approx([0.020]*4)
    assert mesh['glass_y_m'] == pytest.approx(mesh['depth_m']/2)
    assert {mesh['verts'][i][1] for i in mesh['faces'][mesh['parts']['glass'][0]]} == {mesh['depth_m']/2}
