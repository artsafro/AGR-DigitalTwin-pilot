"""new-case: issue 1297 DCC policy entry-point contract."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('name', ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'docs/agents/CAPABILITIES.md', 'docs/domain/geometry.md'])
def test_entry_defaults(name):
    text = (ROOT / name).read_text(encoding='utf-8')
    assert '[D270]' in text
    assert 'per step' in text
    assert 'reason' in text
    assert 'once per task' in text
    assert 'по завершении этапов открывать тебе сцену для приёмки?' in text
    assert 'yes' in text and 'no' in text
    assert 'each stage' in text and 'absolute path' in text
    assert '3ds Max 2026' in text and 'QUAD' in text
    assert 'delivery' in text and 'triangulat' in text


def test_decision_is_recorded():
    text = (ROOT / 'docs/decisions.md').read_text(encoding='utf-8')
    row = re.search(r'^\| D270 \|.*$', text, re.M)
    assert row is not None
    for word in ('per step', 'reason', 'headless', 'Corona', 'AGR Tools', '2026-11-11'):
        assert word in row[0]
