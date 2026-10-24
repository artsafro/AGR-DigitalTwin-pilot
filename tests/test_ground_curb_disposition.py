"""new-case: per-entity curb disposition reports retained/trimmed area after joint clipping (#449).

The role-union trim was previously copied to every entity of the shorter role and a fully
occluded entity stayed ``modeled`` with no geometry left. These probes pin the corrected
per-entity retained/stair/joint trim split, the ``trimmed`` status for fully covered entities
with a truthful reason (stair footprint vs taller-curb joint), the once-only role-union totals,
and the untouched/partially-trimmed same-role controls, while the crossing-junction mesh stays
unchanged (see tests/test_ground_curb_joints.py).
"""
import random

import numpy as np

import pytest
from shapely.geometry import box, mapping, LineString
from shapely.ops import unary_union

from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry import ground_details as gd

# Synthetic approval record for tests only; not a real project decision.
APPROVAL = dict(approved_by='synthetic-test-approver', approved_at='2026-10-21', decision_id='D-test')


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
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True, approval=APPROVAL)
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
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True, approval=APPROVAL)
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
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True, approval=APPROVAL)
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
    mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True, approval=APPROVAL)
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


def stair_sampler():
    return gc.ReliefSampler(gc.build_tin([(x, y, 100 + .2 * y) for x in (-10, 20) for y in (-10, 20)]))


def stairs(root='S', outline=((1, 1), (3, 1), (3, 4), (1, 4), (1, 1)),
           treads=(((1, 2), (3, 2)), ((1, 3), (3, 3)))):
    es = [dict(ref=root, handle=root, kind='INSERT', container=None, role='stairs',
               label=None, geometry=None, problem=None)]
    for i, coords in enumerate([list(outline), *[list(t) for t in treads]]):
        es.append(dict(ref=f'{root}>{i}', handle=f'{root}>{i}', kind='LWPOLYLINE', container=root,
                       role='stairs', geometry=mapping(LineString(coords)), problem=None))
    return es


def test_fully_stair_covered_garden_reported_trimmed_with_stair_reason():
    boundary = box(0, 0, 10, 10)
    elements = stairs() + [element('curb_garden', 'garden', [(1.5, 2.5), (2.5, 2.5)])]
    mesh, report, joints = gd.build_details(elements, boundary, stair_sampler(), separate_curbs=True, approval=APPROVAL)
    g = by_ref(report)['garden']
    assert g['status'] == 'trimmed'
    assert g['footprint_m2'] == pytest.approx(0.08, abs=1e-9)
    assert g['retained_m2'] == 0.0
    assert g['stair_trim_m2'] == pytest.approx(0.08, abs=1e-9)
    assert g['joint_trim_m2'] == 0.0
    assert 'stair' in g['reason'] and 'taller' not in g['reason']
    assert joints == []
    assert set(mesh.slot) == {'Stairs'}


def test_partially_stair_covered_garden_reports_stair_trim():
    boundary = box(0, 0, 10, 10)
    elements = stairs() + [element('curb_garden', 'garden', [(0, 2.5), (5, 2.5)])]
    mesh, report, joints = gd.build_details(elements, boundary, stair_sampler(), separate_curbs=True, approval=APPROVAL)
    g = by_ref(report)['garden']
    assert g['status'] == 'modeled'
    assert g['footprint_m2'] == pytest.approx(0.40, abs=1e-9)
    assert g['retained_m2'] == pytest.approx(0.24, abs=1e-6)
    assert g['stair_trim_m2'] == pytest.approx(0.16, abs=1e-6)
    assert g['joint_trim_m2'] == 0.0
    assert g['retained_m2'] + g['stair_trim_m2'] + g['joint_trim_m2'] == pytest.approx(g['footprint_m2'], abs=1e-9)
    assert joints == []


def test_untouched_garden_beside_stairs_reports_no_trim():
    boundary = box(0, 0, 10, 10)
    elements = stairs() + [element('curb_garden', 'garden', [(4, 5), (8, 5)])]
    mesh, report, joints = gd.build_details(elements, boundary, stair_sampler(), separate_curbs=True, approval=APPROVAL)
    g = by_ref(report)['garden']
    assert g['status'] == 'modeled'
    assert g['footprint_m2'] == pytest.approx(0.32, abs=1e-9)
    assert g['retained_m2'] == pytest.approx(0.32, abs=1e-9)
    assert g['stair_trim_m2'] == 0.0
    assert g['joint_trim_m2'] == 0.0
    assert joints == []


def test_combined_stair_and_taller_curb_garden_accounts_both_trims():
    boundary = box(0, 0, 10, 10)
    elements = stairs(outline=((1, 4), (3, 4), (3, 6), (1, 6), (1, 4)),
                      treads=(((1, 4.5), (3, 4.5)), ((1, 5.5), (3, 5.5))))
    elements += [element('curb_drive', 'drive', [(6, 5), (10, 5)]),
                 element('curb_garden', 'garden', [(0, 5), (10, 5)])]
    mesh, report, joints = gd.build_details(elements, boundary, stair_sampler(), separate_curbs=True, approval=APPROVAL)
    rows = by_ref(report)
    g = rows['garden']
    assert g['status'] == 'modeled'
    assert g['footprint_m2'] == pytest.approx(0.80, abs=1e-9)
    assert g['retained_m2'] == pytest.approx(0.32, abs=5e-3)
    assert g['stair_trim_m2'] == pytest.approx(0.16, abs=5e-3)
    assert g['joint_trim_m2'] == pytest.approx(0.32, abs=5e-3)
    assert g['joint_gap_m'] == .006
    assert g['retained_m2'] + g['stair_trim_m2'] + g['joint_trim_m2'] == pytest.approx(g['footprint_m2'], abs=1e-9)
    # role-union joint total (stair area already excluded) appears once, at its own scope
    assert len(joints) == 1
    j = joints[0]
    assert j['role'] == 'curb_garden' and j['scope'] == 'role union'
    assert j['union_trim_m2'] == pytest.approx(0.32, abs=5e-3)
    # the taller drive section is untouched by the joint policy
    assert rows['drive']['status'] == 'modeled'
    assert rows['drive']['retained_m2'] == pytest.approx(0.60, abs=1e-6)
    assert rows['drive']['joint_trim_m2'] == 0.0


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
        mesh, report, joints = gd.build_details(elements, boundary, sampler(), separate_curbs=True, approval=APPROVAL)
        rows = [r for r in report if r['role'] in gd.SECTIONS and r['status'] in ('modeled', 'trimmed')]
        retained_slots = set()
        for r in rows:
            # per-entity reconciliation: retained + stair + joint trim == own footprint (no stairs here)
            assert r['retained_m2'] >= -1e-12 and r['stair_trim_m2'] >= -1e-12 and r['joint_trim_m2'] >= -1e-12
            assert r['retained_m2'] + r['stair_trim_m2'] + r['joint_trim_m2'] == pytest.approx(r['footprint_m2'], abs=1e-6)
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


# --- #512: separate_curbs requires an approval record ---------------------------------

def _mixed():
    return [element('curb_drive', 'drive', [(1, 5), (9, 5)]),
            element('curb_garden', 'garden', [(5, 1), (5, 9)]),
            element('curb_garden', 'garden2', [(2, 5), (4, 5)])]


@pytest.mark.parametrize('approval', [
    None,
    {},
    dict(APPROVAL, approved_by=''),
    dict(APPROVAL, approved_by='   '),
    dict(APPROVAL, approved_at=''),
    dict(APPROVAL, approved_at=' '),
    dict(APPROVAL, decision_id=''),
    {k: v for k, v in APPROVAL.items() if k != 'approved_by'},
    {k: v for k, v in APPROVAL.items() if k != 'approved_at'},
    {k: v for k, v in APPROVAL.items() if k != 'decision_id'},
    dict(APPROVAL, approved_by=None),
    dict(APPROVAL, approved_at=float('nan')),
    dict(APPROVAL, approved_at='yesterday'),
    dict(APPROVAL, approved_at='2026-13-40'),
    dict(APPROVAL, extra='x'),
    'approved',
    [('approved_by', 'x')],
], ids=['none', 'empty', 'by-empty', 'by-blank', 'at-empty', 'at-blank', 'decision-empty',
        'by-missing', 'at-missing', 'decision-missing', 'by-none', 'at-nan', 'at-garbage',
        'at-invalid-date', 'unknown-key', 'string', 'list'])
def test_separate_curbs_without_valid_approval_raises_named_error(approval):
    with pytest.raises(gd.CurbJointApprovalError):
        gd.build_details(_mixed(), box(0, 0, 10, 10), sampler(), separate_curbs=True, approval=approval)


def test_separate_curbs_without_approval_argument_raises_named_error():
    with pytest.raises(gd.CurbJointApprovalError, match='approved_by'):
        gd.build_details(_mixed(), box(0, 0, 10, 10), sampler(), separate_curbs=True)


def test_approval_without_opt_in_is_rejected():
    with pytest.raises(gd.CurbJointApprovalError):
        gd.build_details(_mixed(), box(0, 0, 10, 10), sampler(), separate_curbs=False, approval=APPROVAL)


def test_joints_and_rows_carry_approval_beside_joint_trim():
    approval = dict(approved_by='synthetic-reviewer', approved_at='2026-10-21T20:00:00+02:00',
                    decision_id='D-synthetic-512')
    mesh, report, joints = gd.build_details(_mixed(), box(0, 0, 10, 10), sampler(),
                                            separate_curbs=True, approval=approval)
    assert joints, 'mixed junction must produce a joint entry'
    for j in joints:
        assert {k: j[k] for k in approval} == approval
    rows = [r for r in report if 'joint_trim_m2' in r]
    assert {r['ref'] for r in rows} == {'drive', 'garden', 'garden2'}
    for r in rows:
        assert {k: r[k] for k in approval} == approval
    # the caller's record is copied, not aliased
    approval['approved_by'] = 'mutated'
    assert all(j['approved_by'] == 'synthetic-reviewer' for j in joints)


LEGACY_DIGEST = '0f4465405faa45a09ab900575692a69f8d415a3a31fa9391af34d65bf3853d2d'


def _legacy_digest():
    import hashlib, json
    boundary = box(0, 0, 10, 10)
    h = hashlib.sha256()
    for els, sp in ((_mixed(), sampler()),
                    ([element('curb_drive', 'drive', [(1, 5), (9, 5)]),
                      element('curb_garden', 'garden', [(2, 5), (8, 5)])], sampler()),
                    ([*stairs(), element('curb_garden', 'g', [(0.5, 2.5), (3.5, 2.5)])], stair_sampler())):
        mesh, report, joints = gd.build_details(els, boundary, sp, separate_curbs=False)
        h.update(json.dumps([report, joints], sort_keys=True, default=str).encode())
        for a in (mesh.verts, mesh.faces, mesh.uv, mesh.level):
            h.update(np.ascontiguousarray(a).tobytes())
        h.update(json.dumps([list(mesh.slot), mesh.cell, mesh.report], sort_keys=True, default=str).encode())
    return h.hexdigest()


def test_legacy_output_byte_identical_to_pre_512():
    # Golden digest recorded on origin/main ed4d774 before #512.
    assert _legacy_digest() == LEGACY_DIGEST



def test_random_approval_records_fail_closed():
    rng = random.Random(512)
    blanks = ['', ' ', '\t', '\n  ', None, 0, 1.5, float('nan'), float('inf'), [], {}]
    for _ in range(200):
        rec = dict(APPROVAL)
        bad = rng.sample(gd.APPROVAL_KEYS, rng.randint(0, 3))
        for k in bad:
            if rng.random() < .3:
                rec.pop(k)
            else:
                rec[k] = rng.choice(blanks)
        if bad:
            with pytest.raises(gd.CurbJointApprovalError):
                gd.build_details(_mixed(), box(0, 0, 10, 10), sampler(), separate_curbs=True, approval=rec)
        else:
            _, _, joints = gd.build_details(_mixed(), box(0, 0, 10, 10), sampler(),
                                            separate_curbs=True, approval=rec)
            assert joints and all(j['decision_id'] == 'D-test' for j in joints)
