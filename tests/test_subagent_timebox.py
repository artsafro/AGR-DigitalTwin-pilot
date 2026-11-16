"""new-case: background subagent elapsed-time transcript contract (#1539)."""
import json
from pathlib import Path

from twinqa.evals.graders import GRADERS


def test_registration_and_unchecked_background_fails(tmp_path):
    assert 'subagent_timebox' in GRADERS
    p = tmp_path / 'unchecked.synthetic.jsonl'
    rows = [
        {'type': 'assistant', 'timestamp': '2026-11-15T22:35:16Z', 'message': {'content': [
            {'type': 'tool_use', 'id': 'launch', 'name': 'Agent',
             'input': {'run_in_background': True, 'prompt': 'Fix UCX. Time box: 30 min.'}}]}},
        {'type': 'user', 'timestamp': '2026-11-16T00:05:54Z',
         'message': {'content': 'What is taking so long?'}}]
    p.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
    assert GRADERS['subagent_timebox'][0]({'transcript': [p]})['passed'] is False
