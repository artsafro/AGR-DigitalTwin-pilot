"""new-case: per-entity curb disposition reports retained/trimmed area after joint clipping (#449).

The role-union trim was previously copied to every entity of the shorter role and a fully
occluded entity stayed ``modeled`` with no geometry left. These probes pin the corrected
per-entity retained/trimmed split, the ``trimmed`` status for fully covered entities, the
once-only role-union totals, and the untouched/partially-trimmed same-role controls, while the
crossing-junction mesh stays unchanged (see tests/test_ground_curb_joints.py).
"""
import random

import pytest
from shapely.geometry import box, mapping, LineString
from shapely.ops import unary_union

from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry import ground_details as gd


def sampler():
    return gc.ReliefSampler(gc.build_tin([(-1, -1, 0), (11, -1, 0), (-1, 11, 0), (11, 11, 0)]))


def element(role, ref, coords):
    return dict(ref=ref, handle=ref, kind='LWPOLYLINE', container=None, role=role,
                geometry=mapping(LineString(coords)), problem=None)


def by_ref(report):
    return {r['ref']: r for r in report}


def test_fully_occluded_garden_is_reported_trimmed_not_modeled():
    boundary = box(0, 0, 10, 10)
    elements = [element('curb_drive', 'drive', [(1, 5), (9, 5)]),
                element('curb_garden', 'garden', [(2, 5), (8, 5)])]
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True)
    rows = by_ref(report)
    # taller drive section continues through the joint unchanged
    assert rows['drive']['status'] == 'modeled'
    assert rows['drive']['retained_m2'] == pytest.approx(1.2, abs=1e-9)
    assert rows['drive']['joint_trim_m2'] == 0.0
    # garden is fully covered by the taller section: dropped with the joint-policy reason
    assert rows['garden']['status'] == 'trimmed'
    assert rows['garden']['retained_m2'] == 0.0
    assert rows['garden']['joint_trim_m2'] == pytest.approx(0.48, abs=1e-9)
    assert 'taller' in rows['garden']['reason']
    # geometry holds only the drive slot
    assert set(mesh.slot) == {'CurbDrive'}
    # union-level total is reported once at its own scope, not copied to every entity
    assert len(joints) == 1
    j = joints[0]
    assert j['role'] == 'curb_garden' and j['scope'] == 'role union'
    assert j['union_trim_m2'] == pytest.approx(0.48, abs=1e-9)
    assert j['gap_m'] == .006 and j['rule'] == 'taller section continuous'


def test_multiple_garden_entities_each_report_own_trim_and_union_total_once():
    boundary = box(0, 0, 10, 10)
    elements = [element('curb_drive', 'drive', [(1, 5), (9, 5)]),
                element('curb_garden', 'g1', [(2, 5), (8, 5)]),
                element('curb_garden', 'g2', [(3, 5), (7, 5)])]
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True)
    rows = by_ref(report)
    # each garden entity carries its OWN area, not the whole role-union trim
    assert rows['g1']['status'] == 'trimmed'
    assert rows['g1']['joint_trim_m2'] == pytest.approx(0.48, abs=1e-9)
    assert rows['g2']['status'] == 'trimmed'
    assert rows['g2']['joint_trim_m2'] == pytest.approx(0.32, abs=1e-9)
    # union total appears exactly once, not on every entity row
    assert len(joints) == 1
    assert joints[0]['union_trim_m2'] == pytest.approx(0.48, abs=1e-9)


def test_partially_trimmed_garden_reports_retained_and_trimmed():
    boundary = box(0, 0, 8, 8)
    elements = [element('curb_drive', 'drive', [(1, 4), (7, 4)]),
                element('curb_garden', 'garden', [(4, 1), (4, 7)])]
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True)
    rows = by_ref(report)
    g = rows['garden']
    assert g['status'] == 'modeled'
    assert g['retained_m2'] > 0
    assert g['joint_trim_m2'] > 0
    assert g['retained_m2'] + g['joint_trim_m2'] == pytest.approx(g['footprint_m2'], abs=1e-9)
    assert g['joint_gap_m'] == .006
    assert len(joints) == 1 and joints[0]['union_trim_m2'] > 0


def test_untouched_same_role_garden_reports_no_joint_trim():
    boundary = box(0, 0, 10, 10)
    elements = [element('curb_drive', 'drive', [(1, 1), (9, 1)]),
                element('curb_garden', 'far', [(1, 8), (9, 8)])]
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True)
    rows = by_ref(report)
    f = rows['far']
    assert f['status'] == 'modeled'
    assert f['retained_m2'] == pytest.approx(f['footprint_m2'], abs=1e-9)
    assert f['joint_trim_m2'] == 0.0
    assert 'joint_gap_m' not in f
    assert joints == []


def test_legacy_build_has_no_joint_fields_and_keeps_both_slots():
    boundary = box(0, 0, 10, 10)
    elements = [element('curb_drive', 'drive', [(1, 5), (9, 5)]),
                element('curb_garden', 'garden', [(2, 5), (8, 5)])]
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=False)
    rows = by_ref(report)
    for r in rows.values():
        assert 'joint_trim_m2' not in r and 'retained_m2' not in r
    assert joints == []
    assert {r['ref'] for r in report if r['status'] == 'modeled'} == {'drive', 'garden'}
    assert set(mesh.slot) == {'CurbDrive', 'CurbGarden'}


def _random_elements(rng):
    drive_y = rng.uniform(3.0, 7.0)
    elements = [element('curb_drive', 'drive', [(0.5, drive_y), (9.5, drive_y)])]
    # one garden per regime: contained (same y), crossing (near y), untouched (far y)
    contained_y = drive_y
    elements.append(element('curb_garden', 'g_contained',
                            [(1.0 + rng.random(), contained_y), (8.0 + rng.random(), contained_y)]))
    crossing_y = drive_y + rng.choice([-1.0, 1.0]) * rng.uniform(0.05, 0.30)
    elements.append(element('curb_garden', 'g_crossing',
                            [(2.0 + rng.random(), crossing_y - 2.0), (2.0 + rng.random(), crossing_y + 2.0)]))
    untouched_y = drive_y + rng.choice([-1.0, 1.0]) * rng.uniform(1.5, 3.5)
    if 0.5 < untouched_y < 9.5:
        elements.append(element('curb_garden', 'g_untouched',
                                [(1.0, untouched_y), (9.0, untouched_y)]))
    return elements


def test_random_per_entity_reconciliation_and_status_invariants():
    rng = random.Random(20261021)
    boundary = box(0, 0, 10, 10)
    for _ in range(60):
        elements = _random_elements(rng)
        mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True)
        rows = [r for r in report if r['role'] in gd.SECTIONS and r['status'] in ('modeled', 'trimmed')]
        retained_slots = set()
        for r in rows:
            # per-entity reconciliation: retained + joint trim == own footprint (no stairs here)
            assert r['retained_m2'] >= -1e-12 and r['joint_trim_m2'] >= -1e-12
            assert r['retained_m2'] + r['joint_trim_m2'] == pytest.approx(r['footprint_m2'], abs=1e-6)
            # fully covered <=> dropped
            assert (r['status'] == 'trimmed') == (r['retained_m2'] <= 1e-9)
            if r['retained_m2'] > 0:
                retained_slots.add(gd.SECTIONS[r['role']][2])
        # mesh slots are exactly the roles that retain geometry
        assert set(mesh.slot) == retained_slots
        # one joint entry per role that actually lost union area
        union_trims = [j for j in joints if j['union_trim_m2'] > 0]
        assert len(union_trims) == len(joints)
        for j in joints:
            assert j['scope'] == 'role union' and j['gap_m'] == .006
            assert j['rule'] == 'taller section continuous'
            assert j['union_trim_m2'] >= -1e-12
