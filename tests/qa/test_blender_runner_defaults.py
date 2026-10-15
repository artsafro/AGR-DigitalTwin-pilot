"""Synthetic CLI probes: profile reviews share the pinned runner default."""
from pathlib import Path
import sys

import pytest

from dt_ai.core.blender import DEFAULT_BLENDER


@pytest.mark.parametrize('environment,override,expected', [
    (None, None, DEFAULT_BLENDER),
    ('environment-blender', None, 'environment-blender'),
    ('environment-blender', 'explicit-blender', 'explicit-blender'),
])
def test_profile_cli_uses_shared_executable_default(monkeypatch, environment, override, expected):
    import tools.run_profile_checks as profile

    monkeypatch.delenv('TWINQA_BLENDER', raising=False)
    if environment:
        monkeypatch.setenv('TWINQA_BLENDER', environment)
    argv = ['run_profile_checks.py', '--run', 'synthetic-run', '--review-id', 'synthetic-review']
    if override:
        argv.extend(['--blender', override])
    monkeypatch.setattr(sys, 'argv', argv)
    original = profile.argparse.ArgumentParser.parse_args
    parsed = []

    class Parsed(Exception):
        pass

    def parse(parser, *args, **kwargs):
        parsed.append(original(parser, *args, **kwargs))
        raise Parsed

    monkeypatch.setattr(profile.argparse.ArgumentParser, 'parse_args', parse)
    with pytest.raises(Parsed):
        profile.main()
    assert parsed[0].blender == Path(expected)
