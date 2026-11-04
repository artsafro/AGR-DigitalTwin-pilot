"""new-case: polygon comparison is fail-closed (#885).

invariant: a code mismatch, a missing expected object, NaN/Inf and an empty report are mismatches;
a matching fail (including at_threshold) is not a pass; an unknown button is an error that names it.
"""
import math

import pytest


def test_mismatch_count_missing_entry_and_unmapped_object():
    from test_polygon_support import compare_report
    expected = [
        {'name': 'A', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []},
        {'name': 'B', 'scene': 'polygon_all', 'expect': 'fail', 'codes': ['drop_short']},
        {'name': 'D', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []},
    ]
    report = {'status': 'fail', 'objects': [
        {'name': 'A', 'findings': [{'code': 'drop_short', 'ids': [], 'detail': ''}]},
        {'name': 'B', 'findings': [{'code': 'drop_short', 'ids': [], 'detail': ''}]},
        {'name': 'C', 'findings': []},
    ]}
    got = compare_report(expected, report)
    kinds = sorted(m['kind'] for m in got)
    assert kinds == ['code', 'missing', 'unmapped']
    assert any(m['name'] == 'C' and 'C' in m['detail'] for m in got)
    assert len(got) == 3


def test_nan_and_inf_are_mismatches_and_never_a_pass():
    from test_polygon_support import compare_report
    expected = [{'name': 'A', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []}]
    for bad in (float('nan'), float('inf'), float('-inf')):
        report = {'status': 'pass', 'objects': [{'name': 'A', 'findings': [], 'extra': bad}]}
        got = compare_report(expected, report)
        assert got and got[0]['kind'] == 'non_finite'
        assert all(m['kind'] != 'pass' for m in got)
        assert not math.isfinite(bad)


def test_empty_report_is_a_mismatch():
    from test_polygon_support import compare_report
    expected = [{'name': 'A', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []}]
    for report in ({}, None, {'status': 'pass', 'objects': []}):
        got = compare_report(expected, report)
        assert any(m['kind'] == 'empty' for m in got), report


def test_at_threshold_never_counts_as_pass():
    from test_polygon_support import compare_report
    expected = [{'name': 'A', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []}]
    report = {'status': 'pass', 'objects': [
        {'name': 'A', 'findings': [{'code': 'at_threshold', 'ids': [], 'detail': 'exactly'}]}]}
    got = compare_report(expected, report)
    assert got
    assert all(m['kind'] != 'pass' for m in got)
    ok = compare_report(
        [{'name': 'A', 'scene': 'polygon_all', 'expect': 'fail', 'codes': ['at_threshold']}],
        {'status': 'fail', 'objects': [
            {'name': 'A', 'findings': [{'code': 'at_threshold', 'ids': [1], 'detail': 'exactly'}]}]},
    )
    assert ok == []


def test_not_run_and_claimed_pass_are_mismatches():
    from test_polygon_support import compare_report
    scene = {'status': 'pass', 'objects': [], 'plan': {'path': 'x', 'findings': [
        {'name': 'system_unit', 'status': 'not_run', 'observed': '', 'expected': 'meters'}]}}
    got = compare_report(
        [{'name': '__scene__', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []}], scene)
    assert any(m['kind'] == 'not_run' for m in got)


def test_known_bug_keeps_the_contract_and_matches_only_the_recorded_got():
    from test_polygon_support import compare_report, load_expected
    expected = [{
        'name': 'SM_Polygon_007_Main', 'scene': 'polygon_all', 'expect': 'fail',
        'codes': ['missing_map'],
        'known_bug': {'id': 'census-usedmaps-drops-missing-file', 'got_expect': 'pass', 'got_codes': []},
    }]
    recorded = {'status': 'pass', 'objects': [{'name': 'SM_Polygon_007_Main', 'findings': []}]}
    assert compare_report(expected, recorded) == []
    fixed = {'status': 'fail', 'objects': [
        {'name': 'SM_Polygon_007_Main', 'findings': [{'code': 'missing_map', 'ids': [], 'detail': ''}]}]}
    assert compare_report(expected, fixed) == []
    other = {'status': 'fail', 'objects': [
        {'name': 'SM_Polygon_007_Main', 'findings': [{'code': 'tex_missing', 'ids': [], 'detail': ''}]}]}
    got = compare_report(expected, other)
    assert len(got) == 1 and got[0]['kind'] == 'code'
    census = load_expected('scene.census')
    row = next(obj for obj in census['objects']
               if obj['name'] == 'SM_Polygon_007_Main' and obj['scene'] == 'polygon_all')
    assert row['expect'] == 'fail' and row['codes'] == ['missing_map']
    assert row['known_bug']['id'] == 'census-usedmaps-drops-missing-file'
    assert row['known_bug']['got_expect'] == 'pass'


def test_unmapped_button_is_an_error_naming_it():
    from test_polygon_support import load_expected
    with pytest.raises(KeyError, match='no-such-button'):
        load_expected('no-such-button')
