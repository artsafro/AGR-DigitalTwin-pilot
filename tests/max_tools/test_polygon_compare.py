"""new-case: polygon comparison is fail-closed (#885).

invariant: a code mismatch, a missing expected object, NaN/Inf and an empty report are mismatches;
a matching fail (including at_threshold) is not a pass; an unknown button is an error that names it.
"""
import math
from pathlib import Path

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


def test_census_missing_map_known_bug_is_closed():
    """#979 E3: scene.census reads the shared bitmap enumerator, so the contract row carries no known bug."""
    from test_polygon_support import load_expected
    for button in ('scene.census', 'qa.preflight'):
        row = next(obj for obj in load_expected(button)['objects']
                   if obj['name'] == 'SM_Polygon_007_Main' and obj['scene'] == 'polygon_all')
        assert 'missing_map' in row['codes'] and 'known_bug' not in row, button
    text = (Path(__file__).resolve().parents[2] / 'test-polygon' / 'KNOWN_BUGS.md').read_text(encoding='utf-8')
    assert '## census-usedmaps-drops-missing-file' not in text


def test_unmapped_button_is_an_error_naming_it():
    from test_polygon_support import load_expected
    with pytest.raises(KeyError, match='no-such-button'):
        load_expected('no-such-button')


def test_known_bug_live_pass_is_not_ok_and_counts_apart():
    """P1-1: expected fail [missing_map] + known_bug pass [] , live pass [] is not OK.

    The row is a known bug, not a mismatch. Exit code stays the mismatch count.
    """
    import copy
    import sys
    from test_polygon_support import group_runs, render_table
    core = sys.modules['agr_polygon_core']
    real = core.load_expected

    def with_known_bug(button):  # a synthetic known bug on the census row (the real one is closed, #979)
        doc = copy.deepcopy(real(button))
        if button == 'scene.census':
            row = next(o for o in doc['objects'] if o['name'] == 'SM_Polygon_007_Main')
            row['known_bug'] = {'id': 'example-known-bug', 'issue': 886, 'got_expect': 'pass', 'got_codes': []}
        return doc
    core.load_expected = with_known_bug
    try:
        _known_bug_rows(group_runs, render_table)
    finally:
        core.load_expected = real


def _known_bug_rows(group_runs, render_table):
    grouped = group_runs([('qa.matid', 'polygon_all')], [])
    text = render_table(grouped, [])
    assert 'получилось' in text.splitlines()[0]
    live = {('scene.census', 'polygon_all', 'SM_Polygon_007_Main'): []}
    grouped = group_runs([('scene.census', 'polygon_all')], [], live)
    rows = [row for base in grouped for spec in base['stations'] for row in spec['rows']
            if row['name'] == 'SM_Polygon_007_Main']
    assert len(rows) == 1
    assert rows[0]['result'] != 'OK'
    assert rows[0]['result'] == 'НЕ OK (известная ошибка #886)'
    assert rows[0]['got'] == 'pass []'
    assert rows[0]['known_bug'] is True
    known = [row for base in grouped for spec in base['stations'] for row in spec['rows']
             if row.get('known_bug')]
    assert len(known) == 1


def test_claimed_fail_when_status_fail_has_no_codes():
    """P1-2: status fail with no derived codes is claimed_fail, the mirror of claimed_pass."""
    from test_polygon_support import compare_report
    got = compare_report(
        [{'name': 'A', 'expect': 'pass', 'codes': []}],
        {'status': 'fail', 'objects': [{'name': 'A', 'findings': []}]})
    assert any(m['kind'] == 'claimed_fail' for m in got)
    matched = compare_report(
        [{'name': 'A', 'expect': 'fail', 'codes': ['cleanup']}],
        {'status': 'fail', 'objects': [
            {'name': 'A', 'findings': [{'code': 'cleanup', 'ids': [], 'detail': ''}]}]})
    assert matched == []


@pytest.mark.parametrize('status', ['not_run', 'skipped', None, '', 'PASS', 'report', 7, '<missing>'])
def test_bad_status_when_top_level_status_is_not_pass_or_fail(status):
    """Round-2 P1: a top-level status outside pass/fail/error is a bad_status mismatch naming it."""
    from test_polygon_support import compare_report
    report = {'objects': [{'name': 'A', 'findings': []}]}
    if status != '<missing>':
        report['status'] = status
    got = compare_report([{'name': 'A', 'expect': 'pass', 'codes': []}], report)
    bad = [m for m in got if m['kind'] == 'bad_status']
    assert len(bad) == 1
    assert repr(report.get('status')) in bad[0]['detail']


def test_bad_status_combined_with_earlier_fixes():
    """bad_status does not mask claimed_pass/claimed_fail on valid statuses, and pass/fail still match."""
    from test_polygon_support import compare_report
    exp = [{'name': 'A', 'expect': 'pass', 'codes': []}]
    assert compare_report(exp, {'status': 'pass', 'objects': [{'name': 'A', 'findings': []}]}) == []
    got = compare_report(exp, {'status': 'fail', 'objects': [{'name': 'A', 'findings': []}]})
    assert [m['kind'] for m in got] == ['claimed_fail']
