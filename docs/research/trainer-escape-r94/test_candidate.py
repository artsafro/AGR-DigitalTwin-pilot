"""Frozen synthetic command boundaries; no commands are executed."""
from candidate import candidate_paths, HARNESS
import pytest


@pytest.mark.parametrize('quote', ['"', "'"])
def test_wrapper_stops_at_harness_executable(quote):
    data = 'C:/x/trainer-test/notes.txt'
    other = "'" if quote == '"' else '"'
    cmd = f'powershell.exe -Command {quote}{HARNESS} -c print(1) {other}{data}{other}{quote}'
    assert candidate_paths(cmd, 'C:/x/run/wt') == [HARNESS.lower(), data.lower()]


def test_non_executable_data_path_keeps_its_spaces():
    assert candidate_paths('Get-Content "C:/x/tool.exe notes/data.txt"', 'C:/x/run/wt') == [
        'c:/x/tool.exe notes/data.txt'
    ]
