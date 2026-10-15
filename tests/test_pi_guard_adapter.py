"""Exercise the Pi adapter's public JSON stdin/stdout boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools/hooks/pi_guard_adapter.py"


def invoke(tool="bash", tin=None, cwd=ROOT, adapter=ADAPTER):
    result = subprocess.run(
        [sys.executable, str(adapter)],
        input=json.dumps({"tool": tool, "input": tin or {"command": "git status"}, "cwd": str(cwd)}),
        capture_output=True, text=True, encoding="utf-8", cwd=cwd,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_destructive_command_is_blocked():
    result = invoke(tin={"command": "git reset --hard HEAD"})
    assert result["decision"] == "block"
    assert "git reset --hard discards work" in result["reason"]
