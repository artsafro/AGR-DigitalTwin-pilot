"""Synthetic belt-joint witness with the measured crossing geometry simplified to XY."""
from collections import Counter
from pathlib import Path
import runpy
import math

import numpy as np
import pytest


hook = runpy.run_path(str(Path(__file__).parents[2] / 'jobs/POLY63-B/hooks/body_grid.py'))
build = hook['build']


def test_near_crossing_belt_is_sewn():
    design = {'modules': {
        'A': {'ring': [(0, 0), (4, 0), (4, 4), (0, 4)], 'zone': [0]*4},
        'B': {'ring': [(0, -.004), (4, .001), (4, 3), (0, 3)], 'zone': [2]*4},
    }, 'floors': [{'type': key, 'bottom': i, 'top': i+1, 'openings': []}
                  for i, key in enumerate('AB')]}
    mesh = build(design)
    edges = Counter(tuple(sorted((a, b))) for f in mesh['faces']
                    for a, b in zip(f, f[1:] + f[:1]))
    assert not [(a, b, n) for (a, b), n in edges.items()
                if mesh['vertices'][a][2] == mesh['vertices'][b][2] == 1 and n != 2]


def boundary_points(mesh):
    counts = Counter(tuple(sorted((a, b))) for f in mesh['faces']
                     for a, b in zip(f, f[1:] + f[:1]))
    return {frozenset(tuple(mesh['vertices'][i]) for i in edge)
            for edge, count in counts.items() if count == 1}


def test_curtain_reveal_is_continuous_across_floor_join():
    ring = [(0, 0), (8, 0), (8, 8), (0, 8)]
    modules = {key: {'ring': ring, 'zone': [0]*4} for key in 'AB'}
    floors = [dict(type='A', bottom=i, top=i+3, openings=[
        dict(s0=2, s1=3, z0=i, z1=i+3, depth=depth, curtain=True)])
        for i, depth in [(0, .24), (3, .25)]]
    # At +3 m both jambs must share the same radial edges, not end in cracks.
    assert not [edge for edge in boundary_points(build(dict(modules=modules, floors=floors)))
                if all(p[2] == 3 for p in edge)]


def test_shoulder_is_notched_and_welded_to_curtain_jambs():
    a = [(0, 0), (8, 0), (8, 8), (0, 8)]
    b = [(1, 1), (7, 1), (7, 7), (1, 7)]
    modules = {key: {'ring': ring, 'zone': [0]*4} for key, ring in [('A', a), ('B', b)]}
    floors = [dict(type='A', bottom=0, top=3, openings=[
        dict(s0=2, s1=3, z0=0, z1=3, depth=.25, curtain=True)]),
        dict(type='B', bottom=3, top=6, openings=[])]
    at_joint = {edge for edge in boundary_points(build(dict(modules=modules, floors=floors)))
                if all(p[2] == 3 for p in edge)}
    assert at_joint == {frozenset({(2, .25, 3), (3, .25, 3)})}


def test_reveal_ends_share_depth_where_window_overlaps_curtain():
    ring = [(0, 0), (8, 0), (8, 8), (0, 8)]
    modules = {key: {'ring': ring, 'zone': [0]*4} for key in 'AB'}
    floors = [dict(type='A', bottom=0, top=3, openings=[
        dict(s0=2, s1=3, z0=0, z1=3, depth=.25, curtain=True),
        dict(s0=2.8, s1=4, z0=1, z1=2, depth=.7)])]
    mesh = build(dict(modules=modules, floors=floors))
    assert boundary_points(mesh) == {
        frozenset(tuple(mesh['vertices'][i]) for i in (a,b))
        for a,b,_ in mesh['planned_boundary']}
    assert [4, .7, 1] in [list(p) for p in mesh['vertices']]


@pytest.mark.parametrize('change', ['none', 'missing-face', 'split', 'touch-only', 'sealed-mouth'])
def test_native_join_audit_rejects_unplanned_boundaries_and_counts_edge_shells(change):
    checker = runpy.run_path(str(Path(__file__).parents[2] / 'jobs/POLY63-B/hooks/check_readback.py'))
    v = np.array([(0,0,0), (1,0,0), (2,0,0), (0,0,1), (1,0,1), (2,0,1), (1,0,0), (1,0,1)])
    faces = [[0,1,4,3], [1,2,5,4]]
    allowed = {(0,1): 'stage_extent', (1,2): 'stage_extent', (2,5): 'reveal_lip',
               (4,5): 'stage_extent', (3,4): 'stage_extent', (0,3): 'reveal_lip'}
    labels = list(range(len(v))); labels[6:] = [1,4]
    if change == 'missing-face': faces.pop()
    if change == 'split': faces[1] = [6,2,5,7]
    if change == 'touch-only': faces[1] = [1,2,5]
    if change == 'sealed-mouth': allowed[1,4] = 'reveal_lip'
    result = checker['shell_audit'](v, faces, labels, allowed)
    assert result['shell_count'] == (2 if change in ('split','touch-only') else 1)
    assert bool(result['bad_vertex_fans']) == (change == 'touch-only')
    assert bool(result['unexpected_boundary_edges']) == (change in ('missing-face','split','touch-only'))
    assert bool(result['missing_boundary_edges']) == (change in ('missing-face','touch-only','sealed-mouth'))


def test_occluded_tangent_is_projected_only_onto_supported_chord():
    checker = runpy.run_path(str(Path(__file__).parents[2] / 'jobs/POLY63-B/hooks/check_readback.py'))
    samples = [(np.array([[.08,1.00001],[.6,1.00001]]), [0.,1.])]
    assert checker['project_arc_station']([0,1], samples) == pytest.approx([0,1.00001])
    with pytest.raises(ValueError, match='off native chord'):
        checker['project_arc_station']([0,1.01], samples)


def test_corner_uses_tangent_anchored_full_steps_and_sagitta():
    points = np.array([(2*math.cos(a), 2*math.sin(a)) for a in np.linspace(0, math.pi/2, 23)])
    arc, xy = hook['resample_arc'](points, .6)
    assert np.allclose(xy[[0,-1]], points[[0,-1]])
    lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    stations = np.r_[0., lengths.cumsum()]
    for target in .6*np.arange(1,6):
        assert min(abs(stations-target)) < 1e-9
    assert 0 < stations[-1]-3 < .6
    assert max(2-np.linalg.norm((xy[1:]+xy[:-1])/2, axis=1)) <= .020


@pytest.mark.parametrize('stretched, jump', [(False, False), (True, False), (False, True), (True, True)])
def test_native_registration_rejects_stretched_repeat_and_same_id_jump(stretched, jump):
    checker = runpy.run_path(str(Path(__file__).parents[2] / 'jobs/POLY63-B/hooks/check_readback.py'))
    # Independent circular fixture. Each full repeat requires two .30 m chords.
    angle = 2*math.asin((.26 if stretched else .30)/4)
    angles = [0., angle, 2*angle, 2*angle+.09]
    xy = np.array([(2*math.cos(t), 2*math.sin(t)) for t in angles])
    residual = float(np.linalg.norm(xy[-1]-xy[-2]))
    u = [0., .5, 1., 2. if stretched else 1.+residual/.6]
    samples = [(xy[i:i+2], u[i:i+2]) for i in range(3)]
    arc = checker['measure_arc'](xy, [0, 2], [0.,0.], 2., samples, .6)
    assert (arc['max_step_error_m'] > .0002) == stretched
    assert (arc['max_uv_metric_error_m'] > .0002) == stretched
    assert arc['terminal_remainder_m'] == pytest.approx(residual)
    assert arc['max_sagitta_m'] <= .02
    edge = checker['phase_delta']([(1.,.5), (1.,1.5)], [(2.15 if jump else 2.,.5), (2.15 if jump else 2.,1.5)])
    assert checker['registration_failures']({'corner': arc}, edge, .6) == (
        (['corner'] if stretched else []) + (['same-ID facade edge phase'] if jump else []))


checker = runpy.run_path(str(Path(__file__).parents[2] / 'jobs/POLY63-B/hooks/check_readback.py'))


def verdict(mesh):
    """Artem's 2026-11-18 rejection counts (all must be 0) for a planned mesh."""
    return {k: len(v) for k, v in checker['stage1_checks'](mesh['vertices'], mesh['faces'], mesh['roles']).items()}


def rounded(x0, y0, x1, y1, r, n=6):
    """CCW rectangle with quarter-circle corners of radius r (n chords each)."""
    pts = []
    for cx, cy, a0 in ((x1-r, y0+r, -90), (x1-r, y1-r, 0), (x0+r, y1-r, 90), (x0+r, y0+r, 180)):
        pts += [(cx+r*math.cos(math.radians(a0+90*k/n)), cy+r*math.sin(math.radians(a0+90*k/n))) for k in range(n+1)]
    return pts


def test_belt_cap_round_corner_is_a_quad_ring_not_a_fan():
    # v005: constrained Delaunay fanned the rounded cap into triangles converging on one point.
    a, b = rounded(0, 0, 10, 8, 1.5), rounded(1.2, 1.2, 8.8, 6.8, .4)
    modules = {'A': {'ring': a, 'zone': [0]*len(a)}, 'B': {'ring': b, 'zone': [2]*len(b)}}
    floors = [dict(type=k, bottom=i*3., top=i*3.+3, openings=[]) for i, k in enumerate('ABA')]
    mesh = build(dict(modules=modules, floors=floors))
    caps = [f for f, r in zip(mesh['faces'], mesh['roles']) if r.startswith('shoulder')]
    assert caps and all(len(f) == 4 for f in caps)
    assert verdict(mesh) == dict.fromkeys(verdict(mesh), 0)
    # No cap vertex is shared by more than 4 cap faces (a fan would be).
    assert max(Counter(i for f in caps for i in f).values()) <= 4


def test_window_beside_curtain_steps_back_without_wedge_or_crack():
    # v005 tapered the reveal rear to the shallower depth: slanted wedge edges at the node.
    ring = [(0, 0), (8, 0), (8, 8), (0, 8)]
    modules = {key: {'ring': ring, 'zone': [0]*4} for key in 'AB'}
    floors = [dict(type='A', bottom=0, top=3, openings=[
        dict(s0=2, s1=3, z0=0, z1=3, depth=.25, curtain=True),
        dict(s0=3, s1=4, z0=1, z1=2, depth=.7)])]
    mesh = build(dict(modules=modules, floors=floors))
    assert verdict(mesh) == dict.fromkeys(verdict(mesh), 0)
    v = np.asarray(mesh['vertices'])
    # The window side facing the curtain is a straight step from .25 to .70 deep.
    assert {tuple(np.round(p, 3)) for p in v[np.isclose(v[:, 0], 3) & np.isclose(v[:, 2], 1)]} >= {
        (3., 0., 1.), (3., .25, 1.), (3., .7, 1.)}


def test_curtain_mouth_in_belt_cap_is_welded_without_t_junction():
    a = [(0, 0), (8, 0), (8, 8), (0, 8)]
    b = [(1, 1), (7, 1), (7, 7), (1, 7)]
    modules = {key: {'ring': ring, 'zone': [0]*4} for key, ring in [('A', a), ('B', b)]}
    floors = [dict(type='A', bottom=0, top=3, openings=[dict(s0=2, s1=3, z0=0, z1=3, depth=.25, curtain=True)]),
              dict(type='B', bottom=3, top=6, openings=[])]
    mesh = build(dict(modules=modules, floors=floors))
    assert verdict(mesh) == dict.fromkeys(verdict(mesh), 0)


def test_window_across_a_step_return_does_not_fold_its_sill():
    # Source A60..A65 (tower B, +5.33 m window from A62): the 0.35 m outward return beside a 0.70 m
    # deep window; mitring the reveal round both corners folded the sill over itself in v005.
    src = [(59.3, 20.078), (60.526, 20.677), (61.097, 19.509), (60.794, 19.332), (61.82, 17.2), (64.836, 11.063),
           (75, 8), (75, 25)]
    ring = [(x-59.3, y-11.) for x, y in src]
    modules = {key: {'ring': ring, 'zone': [0]*len(ring)} for key in 'AB'}
    floors = [dict(type='A', bottom=0, top=3, openings=[dict(s0=2.665, s1=4.825, z0=.68, z1=2.65, depth=.7)])]
    mesh = build(dict(modules=modules, floors=floors))
    assert verdict(mesh) == dict.fromkeys(verdict(mesh), 0)
    assert mesh['trimmed_step_returns'][0]['trimmed_m'] == pytest.approx(.351, abs=.002)


def test_tapered_reveal_rear_is_a_wedge():
    # v005 lip(): one reveal corner at the shallow curtain depth, the other at the window depth.
    from shapely import LinearRing
    ring = LinearRing([(0, 0), (8, 0), (8, 8), (0, 8)])
    v = [(2, 0, 1), (3, 0, 1), (3, .7, 1), (2, .25, 1), (4, 0, 1), (4, .7, 1)]
    taper = checker['stage1_checks'](v, [[0, 1, 2, 3]], ['sill'], ring_at=lambda z: ring)
    straight = checker['stage1_checks'](v, [[1, 4, 5, 2]], ['sill'], ring_at=lambda z: ring)
    assert taper['reveal_wedges'] == [0] and straight['reveal_wedges'] == []


@pytest.mark.parametrize('defect', ['t_junctions', 'overlapping_faces', 'reveal_wedges', 'cap_triangles'])
def test_stage1_checks_catch_each_rejected_defect(defect):
    v = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1), (2, 0, 0), (2, 0, 1), (.5, 0, 0), (.5, 0, -1), (0, 0, -1)]
    faces, roles = [[0, 1, 2, 3], [1, 4, 5, 2]], ['facade', 'facade']
    if defect == 't_junctions': faces.append([8, 7, 6, 0]); roles.append('facade')  # 6 sits inside edge 0-1
    if defect == 'overlapping_faces': faces.append([3, 2, 1, 0]); roles.append('facade')
    if defect == 'reveal_wedges': v[5] = (2, .3, 1.2); roles[1] = 'jamb'
    if defect == 'cap_triangles': faces.append([0, 1, 6]); roles.append('shoulder_up'); v[6] = (.5, -.5, 0)
    found = checker['stage1_checks'](v, faces, roles)
    assert found[defect], found
    assert not any(found[k] for k in found if k not in (defect, 'boundary_gaps')), found
