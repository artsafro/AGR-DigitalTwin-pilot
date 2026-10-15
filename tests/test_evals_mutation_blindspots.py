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


def failures(count=2):
    return [r for i in range(count) for r in
            (call('Bash', {'command': 'uv run pytest tests/check_x.py'}, str(i)), result(str(i), True))]


@pytest.mark.parametrize('phrase', [
    'The diagnostic contains the phrase "stop record"; I will rerun immediately.',
    'No stop record has been saved.', 'I will write a Stop record later.',
    '> Stop record: quoted from the documentation.', '```text\nStop record: example\n```',
])
def test_quoted_stop_does_not_reset(tmp_path, phrase):
    records = failures() + [text(phrase), call('Bash', {'command': 'uv run pytest tests/check_x.py'}, 'retry')]
    assert grade(tmp_path, failure_stop, records)['passed'] is False


@pytest.mark.parametrize('phrase', ['Stop record: tried twice; blocked; next: inspect input.',
                                    'Запись остановки: две ошибки; далее проверка входа.',
                                    '## Stop record: tried twice; next: inspect input.'])
def test_stop_reset(tmp_path, phrase):
    records = failures() + [text(phrase), call('Bash', {'command': 'uv run pytest tests/check_x.py'}, 'retry')]
    assert grade(tmp_path, failure_stop, records)['passed'] is True


@pytest.mark.parametrize('count', range(1, 6))
def test_failure_repeats(tmp_path, count):
    records = failures(count) + [call('Bash', {'command': 'uv run pytest tests/check_x.py'}, 'retry')]
    assert grade(tmp_path, failure_stop, records)['passed'] is (count < 2)


def test_success_resets_own_check(tmp_path):
    records = failures(1) + [call('Bash', {'command': 'uv run pytest tests/check_x.py'}, 'ok'), result('ok')]
    records += failures(1) + [call('Bash', {'command': 'uv run pytest tests/check_x.py'}, 'retry')]
    # Distinct ids: duplicated ids would join to a different result and corrupt this probe.
    records[4]['message']['content'][0]['id'] = 'fresh'
    records[5]['message']['content'][0]['tool_use_id'] = 'fresh'
    assert grade(tmp_path, failure_stop, records)['passed'] is True


@pytest.mark.parametrize('question', [
    'Which cache strategy should I use for model indexing?',
    'Which algorithm should I use for model indexing?',
    'Which report format should I use for object data?',
    'Which hint threshold should I use for model indexing?',
])
def test_implementation_question_with_model_context(tmp_path, question):
    transcript = tmp_path / 'question.jsonl'
    transcript.write_text(json.dumps(call('AskUserQuestion', {'questions': [{'question': question}]}, 'ask')) + '\n')
    empty = tmp_path / 'rules.md'
    empty.write_text('', encoding='utf-8')
    row = routine_question({'transcript': [transcript], 'decisions': [empty], 'patterns': [empty]})
    assert row['passed'] is False
    assert row['details'][0]['category'] == 'implementation'


@pytest.mark.parametrize('question', [
    'Should I delete the model cache?', 'May I push the algorithm fix?',
    'Do you approve the model depth?', 'What model depth is correct?',
    'Which source file dimensions are correct?',
])
def test_implementation_context_keeps_required_permissions(tmp_path, question):
    transcript = tmp_path / 'question.jsonl'
    transcript.write_text(json.dumps(call('AskUserQuestion', {'questions': [{'question': question}]}, 'ask')) + '\n')
    empty = tmp_path / 'rules.md'
    empty.write_text('', encoding='utf-8')
    assert routine_question({'transcript': [transcript], 'decisions': [empty], 'patterns': [empty]})['passed'] is True



