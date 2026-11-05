"""tools/retro/condense_transcript.py: the conversation of a transcript without tool output (Session retro)."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("condense_transcript", ROOT / "tools/retro/condense_transcript.py")
ct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct)


def _entry(kind, content, ts="2026-11-05T07:06:00Z", **extra):
    return {"type": kind, "timestamp": ts, "cwd": "C:/w", "gitBranch": "job/x",
            "message": {"role": kind, "content": content}, **extra}


def _write(tmp_path, entries):
    path = tmp_path / "s.jsonl"
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\nnot json\n", encoding="utf-8")
    return path


def test_keeps_conversation_drops_noise(tmp_path):
    path = _write(tmp_path, [
        _entry("user", "сделай ворота<system-reminder>hook noise</system-reminder>"),
        _entry("user", "<command-name>/yolo</command-name>"),
        _entry("user", "meta", isMeta=True),
        _entry("assistant", [{"type": "text", "text": "x" * 50}, {"type": "tool_use", "name": "Bash", "input": {}}]),
        _entry("user", [{"type": "tool_result", "content": "big output", "is_error": False},
                        {"type": "tool_result", "content": [{"type": "text", "text": "exit 49"}], "is_error": True}]),
        _entry("user", [{"type": "text", "text": "[Request interrupted by user]"}]),
        _entry("assistant", [{"type": "text", "text": "sub"}], isSidechain=True),
    ])
    text = ct.condense(path, width=20)
    lines = text.splitlines()
    assert lines[0] == f"## {path}" and "branch: job/x" in lines[1]
    body = [line.split("] ", 1)[1] for line in lines[2:]]
    assert body == ["USER   сделай ворота", "AI   " + "x" * 19 + "…", "ERR  exit 49", "INTERRUPT"]
    assert "TOOL Bash" in ct.condense(path, tools=True)
    assert "hook noise" not in text and "big output" not in text and "sub" not in text


def test_queued_message_is_a_user_line(tmp_path):
    path = _write(tmp_path, [{"type": "attachment", "timestamp": "2026-11-05T22:26:29Z", "isSidechain": False,
                              "attachment": {"type": "queued_command", "prompt": "я же говорил про evals"}},
                             {"type": "attachment", "timestamp": "2026-11-05T22:27:00Z",
                              "attachment": {"type": "queued_command", "prompt": "<task-notification>x"}}])
    text = ct.condense(path)
    assert "USER ! я же говорил про evals" in text and "task-notification" not in text


def test_since_scans_project_folders(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "projects" / "C--Users-a--AGR-DigitalTwin-pilot--w"
    folder.mkdir(parents=True)
    _write(folder, [_entry("user", "принято", ts="2026-11-05T10:00:00Z")])
    (folder / "subagents").mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert ct.main(["--since", "2000-01-01", "--list"]) == 0
    out = capsys.readouterr().out
    assert "s.jsonl" in out and "user messages: 1" in out


def test_signals():
    assert ct.signal("ты перемудрил, сделай врезкой") == "!"
    assert ct.signal("я же говорил про стекло") == "!"
    assert ct.signal("Видны, принято") == "+"
    assert ct.signal("все норм спс") == "+"
    assert ct.signal("это не принято") == " "
    assert ct.signal("сделай развёртку") == " "


def test_range_filter_and_empty(tmp_path):
    path = _write(tmp_path, [_entry("user", "старое", ts="2026-11-01T10:00:00Z"),
                             _entry("user", "новое", ts="2026-11-05T10:00:00Z")])
    since = datetime(2026, 11, 4, tzinfo=timezone.utc)
    text = ct.condense(path, since=since)
    assert "новое" in text and "старое" not in text
    assert ct.condense(path, until=datetime(2026, 10, 1, tzinfo=timezone.utc)) == ""


def test_main_paths_and_missing(tmp_path, capsys):
    path = _write(tmp_path, [_entry("user", "принято")])
    out = tmp_path / "o" / "c.md"
    assert ct.main([str(path), "--out", str(out)]) == 0
    assert "USER + принято" in out.read_text(encoding="utf-8")
    assert ct.main(["--current"]) in (0, 2)          # depends on the environment; never raises
    capsys.readouterr()


def test_current_finds_session_file(tmp_path, monkeypatch):
    folder = tmp_path / "projects" / "C--x"
    folder.mkdir(parents=True)
    (folder / "abc.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    assert ct.current() == [folder / "abc.jsonl"]
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    assert ct.current() == []
