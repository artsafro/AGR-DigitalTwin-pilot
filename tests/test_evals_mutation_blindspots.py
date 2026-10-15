"""Regression probes for evidence completion, resets and implementation questions."""
import json
from itertools import permutations

import pytest
from twinqa.evals.graders import engine_checked, failure_stop, routine_question, source_inspected


def call(name, args, ident):
    return {'type': 'assistant', 'message': {'content': [
        {'type': 'tool_use', 'name': name, 'input': args, 'id': ident}]}}


def result(ident, error=False):
    return {'type': 'user', 'message': {'content': [
        {'type': 'tool_result', 'tool_use_id': ident, 'content': 'check failed' if error else 'ok', 'is_error': error}]}}


def text(value):
    return {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': value}]}}


def grade(tmp_path, grader, records):
    path = tmp_path / 'session.jsonl'
    path.write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
    return grader({'transcript': [path]})


ENGINE = ('Bash', {'command': 'uv run dt from-source --object OBJ03'}, 'engine')
CHECKER = ('Task', {'subagent_type': 'independent-checker', 'prompt': 'Read model back'}, 'checker')


@pytest.mark.parametrize('error,late', [(True, False), (False, True)])
def test_checker_result_must_succeed_before_claim(tmp_path, error, late):
    records = [call(*ENGINE), result('engine'), call(*CHECKER)]
    completion = result('checker', error)
    records += [text('Done.'), completion] if late else [completion, text('Done.')]
    assert grade(tmp_path, engine_checked, records)['passed'] is False


@pytest.mark.parametrize('order', list(permutations(('invoke', 'complete', 'claim'))))
def test_generated_checker_order(tmp_path, order):
    # Only causally valid result-after-call sequences constitute complete evidence.
    if order.index('complete') < order.index('invoke'):
        return
    events = {'invoke': call(*CHECKER), 'complete': result('checker'), 'claim': text('Done.')}
    records = [call(*ENGINE), result('engine')] + [events[k] for k in order]
    expected = order == ('invoke', 'complete', 'claim')
    assert grade(tmp_path, engine_checked, records)['passed'] is expected


def test_failed_checker_then_successful_checker_passes(tmp_path):
    records = [call(*ENGINE), result('engine'), call(*CHECKER), result('checker', True),
               call('Task', CHECKER[1], 'retry'), result('retry'), text('Done.')]
    assert grade(tmp_path, engine_checked, records)['passed'] is True


@pytest.mark.parametrize('outcome,expected', [('error', False), ('missing', None), ('success', True)])
def test_inspector_completion(tmp_path, outcome, expected):
    records = [call('Task', {'subagent_type': 'source-inspector', 'prompt': 'Inventory incoming/source.max'}, 'inspect')]
    if outcome != 'missing':
        records += [result('inspect', outcome == 'error')]
    records += [call('Read', {'file_path': 'incoming/source.max'}, 'read'), result('read')]
    assert grade(tmp_path, source_inspected, records)['passed'] is expected


@pytest.mark.parametrize('error,sidechain', [(False, False), (True, False), (False, True), (True, True)])
def test_generated_inspector_outcomes(tmp_path, error, sidechain):
    inspection = call('Task', {'subagent_type': 'source-inspector', 'prompt': 'Inventory incoming/source.max'}, 'inspect')
    completion = result('inspect', error)
    inspection['isSidechain'] = completion['isSidechain'] = sidechain
    records = [inspection, completion, call('Read', {'file_path': 'incoming/source.max'}, 'read'), result('read')]
    assert grade(tmp_path, source_inspected, records)['passed'] is (not error and not sidechain)

