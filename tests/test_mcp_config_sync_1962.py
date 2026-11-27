"""#1962: one MCP server list. `.codex/config.toml` owns it; `.agents/mcp_config.json` is generated from it."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mcp/sync_config.py"


def _load():
    spec = importlib.util.spec_from_file_location("mcp_sync_config", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_antigravity_config_is_generated_from_the_codex_owner():
    mod = _load()
    assert mod.render(ROOT) == (ROOT / ".agents/mcp_config.json").read_text(encoding="utf-8")


def test_every_codex_server_reaches_antigravity_unchanged():
    owner = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))["mcp_servers"]
    servers = json.loads((ROOT / ".agents/mcp_config.json").read_text(encoding="utf-8"))["mcpServers"]
    for name, spec in owner.items():
        assert servers[name] == {"command": spec["command"], "args": spec.get("args", []), "env": spec.get("env", {})}
    # the two Antigravity-only routes stay as before #1962 (Codex gets 3dsmax-mcp from the user's config)
    assert set(servers) - set(owner) == {"3dsmax-mcp", "agr-mcp"}


def test_check_mode_fails_on_a_stale_copy(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".codex/config.toml").write_text((ROOT / ".codex/config.toml").read_text(encoding="utf-8"),
                                                encoding="utf-8")
    (tmp_path / ".agents/mcp_config.json").write_text("{}\n", encoding="utf-8")
    run = [sys.executable, str(SCRIPT), "--root", str(tmp_path)]
    assert subprocess.run([*run, "--check"], capture_output=True).returncode == 1
    assert subprocess.run(run, capture_output=True).returncode == 0
    assert subprocess.run([*run, "--check"], capture_output=True).returncode == 0
