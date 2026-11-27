"""#1962: one Antigravity guard shim. `.agents/hooks.json` runs `guard.cmd` next to it; the copy one level deeper
(`.agents/hooks/guard.cmd`, path depth was its only difference) is gone.
new-case: single guard.cmd regression (#1962)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hooks_json_command_is_the_single_guard_shim():
    hooks = json.loads((ROOT / ".agents/hooks.json").read_text(encoding="utf-8"))
    commands = {h["command"] for e in hooks["safety-guard"]["PreToolUse"] for h in e["hooks"]}
    assert commands == {"guard.cmd"}
    shims = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / ".agents").rglob("guard.cmd"))
    assert shims == [".agents/guard.cmd"]
    text = (ROOT / ".agents/guard.cmd").read_text(encoding="utf-8")
    assert "%~dp0..\\.claude\\hooks\\guard.py" in text and "py -3 .claude\\hooks\\guard.py" in text
