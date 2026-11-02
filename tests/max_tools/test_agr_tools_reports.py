"""new-case: strict native AGR Tools report seam."""
import importlib.util
import json
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools/runtime.py'


def runtime():
    spec = importlib.util.spec_from_file_location('agr_runtime', PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_native_report_parser_preserves_exact_findings():
    mod = runtime()
    assert hasattr(mod, 'parse_report'), 'native report parser missing'
    value = {'schema': 1, 'tool': 'matid', 'status': 'fail', 'objects': [
        {'handle': 7, 'name': 'planted', 'findings': [{'code': 'udim_id', 'ids': [2], 'detail': '1001'}]}]}
    assert mod.parse_report(json.dumps(value)) == value


@pytest.mark.parametrize('text', [
    '', '{}', '{"schema":1,"schema":1}', 'NaN',
    '{"schema":1,"tool":"unknown","status":"pass","objects":[]}',
    '{"schema":1,"tool":"matid","status":"pass","objects":[]}',
    '{"schema":1,"tool":"matid","status":"not_run","objects":[]}',
])
def test_native_parser_rejects_incomplete_unsupported(text):
    mod = runtime()
    assert hasattr(mod, 'parse_report'), 'native report parser missing'
    with pytest.raises(ValueError):
        mod.parse_report(text)


@pytest.mark.parametrize('field,value', [('tool', []), ('tool', None), ('schema', True)])
def test_parser_malformed_field_is_named_error(field, value):
    mod = runtime()
    report = {'schema': 1, 'tool': 'matid', 'status': 'pass',
              'objects': [{'handle': 1, 'name': 'clean', 'findings': []}]}
    report[field] = value
    with pytest.raises(ValueError):
        mod.parse_report(json.dumps(report))


@pytest.mark.parametrize('status', ['pass', 'fail', 'review', 'not_run', 'unknown'])
@pytest.mark.parametrize('defect', [False, True])
def test_declared_status_never_overrides_actual_findings(status, defect):
    mod = runtime()
    report = {'schema': 1, 'tool': 'matid', 'status': status,
              'objects': [{'handle': 1, 'name': 'synthetic', 'findings':
                           [{'code': 'empty_id', 'ids': [1], 'detail': '0'}] if defect else []}]}
    if status == ('fail' if defect else 'pass'):
        assert mod.parse_report(json.dumps(report)) == report
    else:
        with pytest.raises(ValueError, match='status'):
            mod.parse_report(json.dumps(report))


@pytest.mark.parametrize('change', ['duplicate_handle', 'unknown_code', 'fractional_id',
                                   'duplicate_id', 'partial_object', 'infinity'])
def test_hostile_report_payloads(change):
    mod = runtime()
    obj = {'handle': 1, 'name': 'synthetic', 'findings': [
        {'code': 'udim_id', 'ids': [1], 'detail': '1001'}]}
    report = {'schema': 1, 'tool': 'matid', 'status': 'fail', 'objects': [obj]}
    if change == 'duplicate_handle':
        report['objects'].append(obj)
    elif change == 'unknown_code':
        obj['findings'][0]['code'] = 'not_measured'
    elif change == 'fractional_id':
        obj['findings'][0]['ids'] = [1.5]
    elif change == 'duplicate_id':
        obj['findings'][0]['ids'] = [1, 1]
    elif change == 'partial_object':
        del obj['name']
    elif change == 'infinity':
        obj['handle'] = float('inf')
    with pytest.raises(ValueError):
        mod.parse_report(json.dumps(report))
