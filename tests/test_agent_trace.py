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


def _field(text, name):
    prefix = f"- {name}: "
    return next(line[len(prefix):] for line in text.splitlines() if line.startswith(prefix))


def _jsonl(tmp_path, name, lines):
    """Dump dicts as JSON lines; a string item is written raw (a torn or malformed line)."""
    path = tmp_path / name
    rendered = [line if isinstance(line, str) else json.dumps(line) for line in lines]
    path.write_text("\n".join(rendered) + "\n", encoding="utf-8")
    return path


def _user(content, session):
    return {"sessionId": session, "isSidechain": False, "type": "user",
            "message": {"role": "user", "content": content}}


def _assistant(content, session):
    return {"sessionId": session, "isSidechain": False, "type": "assistant",
            "message": {"role": "assistant", "content": content}}


def _tool(name, tool_id, payload, session):
    return _assistant([{"type": "tool_use", "id": tool_id, "name": name, "input": payload}], session)


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
    crlf = "## Where we are\r\n\r\nDone.\r\n\r\n## Agent trace\r\n\r\n- old\r\n\r\n## Next step\r\n\r\nGo.\r\n"
    updated = agent_trace.replace_section(crlf, block)
    assert updated.startswith("## Where we are\r\n\r\nDone.\r\n\r\n")
    assert updated.endswith("## Next step\r\n\r\nGo.\r\n")
    assert "- Sessions: `a`" in updated and "old" not in updated.split("## Next step", 1)[0]


def test_replace_section_keeps_refs_after_the_last_section():
    block = "## Agent trace\n\n- Sessions: `a`\n"
    original = "## Agent trace\n\n-\n\nRefs artsafro/AGR-DigitalTwin#124\n"
    updated = agent_trace.replace_section(original, block)
    assert updated.endswith("\n\nRefs artsafro/AGR-DigitalTwin#124\n")
    assert block in updated
    assert updated == block + "\nRefs artsafro/AGR-DigitalTwin#124\n"


def test_replace_section_replaces_the_template_placeholder():
    block = "## Agent trace\n\n- Sessions: `a`\n"
    original = ("# Handoff\n\n## Agent trace\n\n"
                "<generated by tools/hooks/agent_trace.py --into docs/HANDOFF.md>\n")
    updated = agent_trace.replace_section(original, block)
    assert "<generated by" not in updated
    assert updated == "# Handoff\n\n" + block


def test_replace_section_is_idempotent():
    block = "## Agent trace\n\n- Sessions: `a`\n"
    originals = (
        "## Agent trace\n\n-\n\nRefs artsafro/AGR-DigitalTwin#124\n",
        "# Handoff\n\n## Agent trace\n\n<generated by tools/hooks/agent_trace.py>\n\n## Next step\n\nGo.\n",
        "## Where we are\r\n\r\nDone.\r\n\r\n## Agent trace\r\n\r\n-\r\n\r\nRefs artsafro/AGR-DigitalTwin#124\r\n",
    )
    for original in originals:
        once = agent_trace.replace_section(original, block)
        assert agent_trace.replace_section(once, block) == once


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


def _trace(paths, rows, monkeypatch):
    _clear_context_env(monkeypatch)
    return agent_trace.trace(paths, rows, ("aaa1111", "bbb2222", 1), "-")


def test_bad_middle_line(tmp_path, monkeypatch):
    path = _jsonl(tmp_path, "bad.jsonl", [
        _user("hello", "s-bad"),
        "{not json",
        _tool("Bash", "bash-9", {"command": "pytest -q"}, "s-bad"),
    ])
    text = _trace([path], [], monkeypatch)
    for name in ("Hook denials", "Retries"):
        assert _field(text, name).startswith("incomplete, none seen (")
        assert "not a transcript record" in _field(text, name)
    assert "- Hook denials: none\n" not in text


def test_torn_tail(tmp_path, monkeypatch):
    denial = next(line for line in TRANSCRIPT.read_text(encoding="utf-8").splitlines()
                  if "permissionDecision" in line)
    path = _jsonl(tmp_path, "torn.jsonl", [
        _user("hello", "s-torn"),
        _tool("Bash", "push-1", {"command": "git push origin HEAD"}, "s-torn"),
        denial[:40],
    ])
    text = _trace([path], [], monkeypatch)
    for name in ("Hook denials", "Retries"):
        assert _field(text, name).startswith("incomplete, none seen (")
        assert "not a transcript record" in _field(text, name)
    assert "- Hook denials: none\n" not in text


def test_no_conversation(tmp_path, monkeypatch):
    path = _jsonl(tmp_path, "sum.jsonl", [{"type": "summary", "summary": "synthetic"}])
    text = _trace([path], [], monkeypatch)
    for name in ("Hook denials", "Retries", "Duration"):
        value = _field(text, name)
        assert "no user or assistant record" in value or value.startswith("not measured")
    assert all(_field(text, name) != "none" for name in FIELDS)


def test_partial_fallback(tmp_path, monkeypatch):
    denial = next(line for line in TRANSCRIPT.read_text(encoding="utf-8").splitlines()
                  if "permissionDecision" in line)
    path = _jsonl(tmp_path, "part.jsonl", [
        _tool("Agent", "agent-9", {"subagent_type": "Explore"}, "s-part"),
        denial[:40],
    ])
    text = _trace([path], [], monkeypatch)
    assert _field(text, "Subagents").startswith("incomplete, at least ")
    assert "Explore" in _field(text, "Subagents")


def test_mixed_sessions(tmp_path, monkeypatch):
    path = _jsonl(tmp_path, "open.jsonl", [
        _tool("Agent", "agent-9", {"subagent_type": "independent-checker"}, "sess-unlogged"),
        _tool("Skill", "skill-9", {"skill": "grill-me"}, "sess-unlogged"),
        _user("<command-name>/takeover</command-name>", "sess-unlogged"),
    ])
    rows = [row for row in usage_rows() if row["session_id"] == "sess-trace-124"]
    text = _trace([TRANSCRIPT, path], rows, monkeypatch)
    sub, skills, commands = _field(text, "Subagents"), _field(text, "Skills"), _field(text, "Commands")
    assert "Explore 2" in sub and "independent-checker 1" in sub
    assert "from the transcript for `sess-unlogged`" in sub
    assert "tdd 1" in skills and "grill-me 1" in skills
    assert "handover 1" in commands and "takeover 1" in commands
    assert _field(text, "Sessions") == "`sess-trace-124`, `sess-unlogged`"


def test_quiet_session(tmp_path, monkeypatch):
    path = _jsonl(tmp_path, "quiet.jsonl", [
        _user("hello", "sess-quiet"),
        _assistant([{"type": "text", "text": "ok"}], "sess-quiet"),
    ])
    rows = [row for row in usage_rows() if row["session_id"] == "sess-trace-124"]
    text = _trace([TRANSCRIPT, path], rows, monkeypatch)
    assert "- Subagents: Explore 2 (from the transcript for `sess-quiet`)\n" in text


def test_same_session_twice(monkeypatch):
    text = _trace([TRANSCRIPT, TRANSCRIPT], usage_rows(), monkeypatch)
    assert _field(text, "Subagents") == "Explore 2"
    assert _field(text, "Sessions") == "`sess-trace-124`"
    assert _field(text, "Retries") == "2: `pytest -q` x2"
    assert _field(text, "Hook denials") == "1: Bash - push needs approval"


def test_quoted_command_tag(tmp_path, monkeypatch):
    path = _jsonl(tmp_path, "cmd.jsonl", [
        _user("<command-name>/handover</command-name>\n<command-args></command-args>", "s-cmd"),
        _user([{"type": "tool_result", "tool_use_id": "x",
                "content": "see <command-name>/release</command-name>"}], "s-cmd"),
    ])
    text = _trace([path], [], monkeypatch)
    assert "- Commands: handover 1 (from the transcript)\n" in text
    assert "release" not in next(line for line in text.splitlines() if line.startswith("- Commands:"))
