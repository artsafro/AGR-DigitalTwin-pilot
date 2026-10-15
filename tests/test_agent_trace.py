# Fixtures under tests/fixtures/agent_trace/ are synthetic: hand-written for this test, not a real session.
"""tools/hooks/agent_trace.py: the ## Agent trace block from a usage log and a transcript."""
import json
import os
import subprocess
import sys
from pathlib import Path

from twinqa.evals.graders import read_jsonl

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tools/hooks/agent_trace.py"
FIXTURE = ROOT / "tests/fixtures/agent_trace"
TRANSCRIPT = FIXTURE / "transcript.jsonl"
USAGE = FIXTURE / "usage.jsonl"
sys.path.insert(0, str(HOOK.parent))
import agent_trace  # noqa: E402

FIELDS = ["Sessions", "Written by", "Subagents", "Skills", "Commands", "Hook denials", "Retries",
          "Context at handover", "Duration", "Commits"]
EXPECTED = """\
## Agent trace

- Sessions: `sess-trace-124`
- Written by: Cursor (grok-4.7-medium)
- Subagents: Explore 2
- Skills: tdd 1
- Commands: handover 1
- Hook denials: 1: Bash - push needs approval
- Retries: 2: `pytest -q` x2
- Context at handover: 40 % (80k of 200k tokens)
- Duration: 1 h 12 min (2026-10-15T08:00:00Z - 2026-10-15T09:12:00Z, UTC)
- Commits: `aaa1111..bbb2222` (4 commits)
"""


def usage_rows():
    return [json.loads(line) for line in USAGE.read_text(encoding="utf-8").splitlines() if line.strip()]


def field_names(text):
    return [line[2:].split(":", 1)[0] for line in text.splitlines() if line.startswith("- ")]


def _clear_context_env(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_MAX_CONTEXT_TOKENS", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_DISABLE_1M_CONTEXT", raising=False)


def test_fields_are_present_once_in_order_and_counts_match(monkeypatch):
    _clear_context_env(monkeypatch)
    text = agent_trace.trace([TRANSCRIPT], usage_rows(), ("aaa1111", "bbb2222", 4), "Cursor (grok-4.7-medium)")
    assert text == EXPECTED
    assert field_names(text) == FIELDS
    assert text.count("## Agent trace") == 1
    records, _problems = read_jsonl(TRANSCRIPT)
    assert agent_trace.retries(records) == ["pytest -q", "pytest -q"]


def test_fallback_counts_tool_uses_when_the_session_is_absent_from_the_log(monkeypatch):
    _clear_context_env(monkeypatch)
    rows = [row for row in usage_rows() if row["session_id"] != "sess-trace-124"]
    text = agent_trace.trace([TRANSCRIPT], rows, ("aaa1111", "bbb2222", 1), "-")
    assert "- Subagents: pattern-librarian 1 (from the transcript)\n" in text
    assert "- Skills: experience-transfer 1 (from the transcript)\n" in text
    assert "- Commands: none (from the transcript)\n" in text
    assert "Explore" not in text and "codex-rescue" not in text
    assert field_names(text) == FIELDS


def test_missing_transcript_is_not_measured(tmp_path):
    missing = tmp_path / "absent.jsonl"
    text = agent_trace.trace([missing], usage_rows(), ("aaa1111", "bbb2222", 2), "-")
    assert "- Sessions: not measured (" in text and "does not exist" in text
    assert "- Subagents: not measured (" in text
    assert "- Hook denials: not measured (" in text
    assert "- Retries: not measured (" in text
    assert "- Context at handover: not measured (" in text
    assert "- Duration: not measured (" in text
    assert "- Commits: `aaa1111..bbb2222` (2 commits)\n" in text
    assert "- Written by: -\n" in text
    assert field_names(text) == FIELDS


def test_replace_section_keeps_the_surrounding_sections_and_appends_when_absent():
    block = "## Agent trace\n\n- Sessions: `a`\n"
    original = "## Where we are\n\nDone.\n\n## Agent trace\n\n- Sessions: `old`\n\n## Next step\n\nGo.\n"
    assert agent_trace.replace_section(original, block) == (
        "## Where we are\n\nDone.\n\n## Agent trace\n\n- Sessions: `a`\n\n## Next step\n\nGo.\n")
    absent = "## Where we are\n\nDone.\n"
    assert agent_trace.replace_section(absent, block) == absent + block
    crlf = "## Where we are\r\n\r\nDone.\r\n\r\n## Agent trace\r\n\r\nold\r\n\r\n## Next step\r\n\r\nGo.\r\n"
    updated = agent_trace.replace_section(crlf, block)
    assert updated.startswith("## Where we are\r\n\r\nDone.\r\n\r\n")
    assert updated.endswith("## Next step\r\n\r\nGo.\r\n")
    assert "- Sessions: `a`" in updated and "old" not in updated.split("## Next step", 1)[0]


def test_cli_writes_the_section_into_a_file(tmp_path):
    dest = tmp_path / "handoff.md"
    original = "# Handoff\n\n## Next step\n\nGo.\n"
    dest.write_text(original, encoding="utf-8", newline="")
    env = {key: value for key, value in os.environ.items()
           if key not in ("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "CLAUDE_CODE_DISABLE_1M_CONTEXT", "AGR_USAGE_LOG")}
    result = subprocess.run(
        [sys.executable, str(HOOK), "--transcript", str(TRANSCRIPT), "--usage-log", str(USAGE),
         "--writer", "Cursor (grok-4.7-medium)", "--into", str(dest)],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    text = dest.read_text(encoding="utf-8", newline="")
    assert text.startswith(original)
    assert "- Subagents: Explore 2\n" in text
    assert "- Skills: tdd 1\n" in text
    assert "- Commands: handover 1\n" in text
    assert "- Hook denials: 1: Bash - push needs approval\n" in text
    assert "- Retries: 2: `pytest -q` x2\n" in text
    assert "- Duration: 1 h 12 min (" in text
    assert field_names(text) == FIELDS
