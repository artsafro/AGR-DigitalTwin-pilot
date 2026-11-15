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
    import copy
    mesh = wg.build_type(opening(), STD)
    # B v005-like construction: panel 3 mm short of the clear light, behind frame middle.
    # Behaviour fixture only; the real v007 source coordinates are tested below.
    legacy = copy.deepcopy(mesh)
    (_, r), = legacy['fields']
    legacy['verts'] = list(legacy['verts'])
    face = legacy['faces'][legacy['parts']['glass'][0]]
    for i,p in zip(face, ((r[0]+.003, .1, r[1]+.003), (r[2]-.003, .1, r[1]+.003),
                          (r[2]-.003, .1, r[3]-.003), (r[0]+.003, .1, r[3]-.003))):
        legacy['verts'][i] = list(p)
    assert overlaps(legacy) == pytest.approx([-.003]*4)
    assert not all(x >= .015 for x in overlaps(legacy))
    assert min(overlaps(mesh)) >= 0.015
    assert overlaps(mesh) == pytest.approx([0.020]*4)
    assert mesh['glass_y_m'] == pytest.approx(mesh['depth_m']/2)
    assert {mesh['verts'][i][1] for i in mesh['faces'][mesh['parts']['glass'][0]]} == {mesh['depth_m']/2}


def test_revit_profile_drives_real_frame_and_mid_depth():
    mesh = wg.build_type(opening(frame_profile_m={'face_m': 0.05, 'depth_m': 0.022, 'impost_m': 0.05}), STD)
    assert mesh['depth_m'] == pytest.approx(0.022)
    assert mesh['glass_y_m'] == pytest.approx(0.011)
    assert mesh['fields'][0][1] == pytest.approx([0.05, 0.05, 1.15, 1.45])


def test_capsule_is_separate_setback_box_not_thin_frame_strips():
    plain = wg.build_type(opening(), STD)
    mesh = wg.build_type(opening(), STD, {'interior': {'setback_m': 0.15, 'depth_m': 2.0}})
    assert wg.part_mesh(mesh, 'frame') == wg.part_mesh(plain, 'frame')
    cap = wg.part_mesh(mesh, 'capsule')
    assert len(cap['faces']) == 5  # front open, inward walls/back
    assert set(cap['mat_ids']).isdisjoint({wg.MAT_FACE, wg.MAT_BACK, wg.MAT_GLASS})
    assert [min(v[k] for v in cap['verts']) for k in range(3)] == pytest.approx([-0.044, 0.15, -0.130])
    assert [max(v[k] for v in cap['verts']) for k in range(3)] == pytest.approx([1.244, 2.15, 1.630])
    for f in cap['faces']:
        pts = [cap['verts'][i] for i in f]
        assert min(sum((a-b)**2 for a,b in zip(pts[i], pts[(i+1)%4]))**0.5 for i in range(4)) >= 0.020


def test_grille_gets_overlap_mid_depth_but_never_a_capsule():
    entry = opening(panes_m=[], grilles_m=[[0.057, 0.057, 1.143, 1.443]])
    mesh = wg.build_type(entry, STD)
    assert mesh['fields'][0][0] == 'grille'
    lo, hi = bounds(mesh, mesh['parts']['grille'][0])
    assert lo == pytest.approx([0.037, 0.05, 0.037])
    assert hi == pytest.approx([1.163, 0.05, 1.463])
    assert not mesh['parts']['glass'] and not mesh['parts'].get('capsule')
    with pytest.raises(ValueError, match='grille'):
        wg.build_type(entry, STD, {'interior': {'setback_m': 0.15, 'depth_m': 2.0}})
    body = wg.part_mesh(mesh, 'body')
    assert len(body['faces']) + len(wg.part_mesh(mesh, 'glass')['faces']) == len(mesh['faces'])
    assert wg.MAT_GRILLE in body['mat_ids']


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), True])
def test_nonfinite_or_boolean_fields_refused(bad):
    with pytest.raises(ValueError):
        wg.build_type(opening(panes_m=[[bad, 0.057, 1.143, 1.443]]), STD)


@pytest.mark.parametrize('profile', [{}, {'face_m': 0.05}, {'face_m': 0.05, 'depth_m': 0.1, 'impost_m': 0.05, 'unknown': 1}])
def test_partial_or_unmapped_profiles_refused(profile):
    with pytest.raises(ValueError, match='frame_profile_m'):
        wg.build_type(opening(frame_profile_m=profile), STD)


@pytest.mark.parametrize('change', [dict(panes_m=[]), dict(role='unmapped'),
    dict(panes_m=[[0.057, 0.057, 0.057, 1.443]]),
    dict(panes_m=[], grilles_m=[[0.057, 0.057, 0.057, 1.443]]),
    dict(panes_m=[[0.057, 0.057, 1.143, 1.443]]*2)])
def test_empty_degenerate_duplicate_or_unmapped_input_never_passes(change):
    try:
        mesh = wg.build_type(opening(**change), STD)
    except ValueError:
        return
    assert mesh['status'] != 'ok'


@pytest.mark.parametrize('seat,depth', [(0.1, 2), (0.15, 0.020), (float('nan'), 2), (0.15, float('inf'))])
def test_invalid_and_exact_threshold_capsules_refused(seat, depth):
    with pytest.raises(ValueError):
        wg.build_type(opening(), STD, {'interior': {'setback_m': seat, 'depth_m': depth}})


@pytest.mark.parametrize('overlap', [0.015, 0.017, 0.020])
def test_source_overlap_within_approved_range(overlap):
    mesh = wg.build_type(opening(), STD, {'infill_overlap_m': overlap})
    assert overlaps(mesh) == pytest.approx([overlap]*4)


@pytest.mark.parametrize('overlap', [0.014999, 0.020001, float('nan'), float('inf')])
def test_out_of_range_overlap_refused(overlap):
    with pytest.raises(ValueError):
        wg.build_type(opening(), STD, {'infill_overlap_m': overlap})


def test_real_4bk_k3_b_v007_glass_grille_and_frame_within_2_mm():
    import json
    import math
    fixture = json.loads((ROOT / 'tests/fixtures/window_seating_1449.json').read_text())
    for case in fixture['cases']:
        mesh = wg.build_type(case['entry'], STD, case['options'])
        lo, hi = bounds(mesh, mesh['parts'][case['role']][0])
        measured = case['panel']
        expected_lo = [min(v[k] for v in measured) for k in range(3)]
        expected_hi = [max(v[k] for v in measured) for k in range(3)]
        assert max(abs(a-b) for a,b in zip(lo+hi, expected_lo+expected_hi)) < 0.002
        W, _, H = mesh['size_m']
        front_and_inner = []
        for fi in mesh['parts']['frame']:
            a,b = bounds(mesh, fi)
            if abs(a[1])+abs(b[1]) < 1e-9 or (
                b[1]-a[1] > 0.01 and not any(abs(a[k]-b[k])<1e-9 and
                    (abs(a[k])<1e-9 or abs(a[k]-edge)<1e-9) for k,edge in ((0,W),(2,H)))):
                front_and_inner.append([mesh['verts'][i] for i in mesh['faces'][fi]])
        source = [r['points'] for r in case['frame']]
        def residual(points, rectangles):
            boxes = [([min(v[k] for v in r) for k in range(3)],
                      [max(v[k] for v in r) for k in range(3)]) for r in rectangles]
            return max(min(math.sqrt(sum(max(a[k]-p[k],0,p[k]-b[k])**2 for k in range(3)))
                           for a,b in boxes) for r in points for p in r)
        # Two-way vertex-to-rectangle comparison of shared front/inner frame surfaces;
        # new closed outer/back faces are deliberately not claimed to reproduce the source's open shell.
        assert max(residual(source, front_and_inner), residual(front_and_inner, source)) < 0.002


def test_opaque_infill_outline_is_not_changed_by_glass_rule():
    mesh = wg.build_type(opening(panes_m=[], opaque_m=[[0.057, 0.057, 1.143, 1.443]]), STD)
    face, = [i for i,m in enumerate(mesh['mat_ids']) if m == wg.MAT_OPAQUE]
    lo,hi = bounds(mesh, face)
    assert [lo[0],lo[2],hi[0],hi[2]] == pytest.approx(mesh['fields'][0][1])


def test_generated_opening_matrix_preserves_parts_overlap_and_frame():
    # Synthetic exhaustive dimensions/profiles, not a real-building measurement.
    import copy
    for w in (0.5, 1.2, 3.0):
        for h in (0.6, 1.5, 3.5):
            for face in (0.05, 0.06, 0.07):
                for depth in (0.022, 0.058, 0.1):
                    entry = opening(width_m=w, height_m=h, panes_m=[[face,face,w-face,h-face]],
                                    frame_profile_m={'face_m': face, 'depth_m': depth, 'impost_m': face})
                    before = copy.deepcopy((entry, STD))
                    plain = wg.build_type(entry, STD)
                    cap = wg.build_type(entry, STD, {'interior': {'setback_m': 0.15, 'depth_m': 2}})
                    assert min(overlaps(cap)) >= 0.015
                    assert wg.part_mesh(cap, 'frame') == wg.part_mesh(plain, 'frame')
                    assert cap['glass_y_m'] == pytest.approx(depth/2)
                    owners = [fi for indices in cap['parts'].values() for fi in indices]
                    assert sorted(owners) == list(range(len(cap['faces'])))
                    assert (entry, STD) == before
