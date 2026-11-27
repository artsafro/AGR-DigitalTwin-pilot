"""Generate `.agents/mcp_config.json` (Antigravity) from the one MCP server list in `.codex/config.toml` (#1962).

Why: the same six DCC routes were kept by hand in two files (backlog H8). `.codex/config.toml` is the owner; edit
it, then run this script. Antigravity also gets the two routes Codex does not read from the project: `3dsmax-mcp`
(Codex takes it from the user's config) and `agr-mcp` (frozen, [D394]); they live in `ANTIGRAVITY_ONLY` below.

Usage (repository root): `uv run python tools/mcp/sync_config.py` writes the JSON; `--check` exits 1 when it is
stale (tests/test_mcp_config_sync_1962.py runs the check).
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

OWNER = ".codex/config.toml"
TARGET = ".agents/mcp_config.json"

ANTIGRAVITY_ONLY = {
    "3dsmax-mcp": {
        "command": "uv",
        "args": ["run", "--directory", "C:\\Users\\artsafro\\tools\\3dsmax-mcp", "3dsmax-mcp"],
        "env": {},
    },
    "agr-mcp": {
        "command": "uv",
        "args": ["run", "--directory", "C:\\agr\\AGR-DigitalTwin-pilot", "agr-mcp"],
        "env": {},
    },
}


def render(root: Path) -> str:
    owner = tomllib.loads((root / OWNER).read_text(encoding="utf-8"))["mcp_servers"]
    servers = dict(ANTIGRAVITY_ONLY)
    for name, spec in owner.items():
        if name in servers:
            raise SystemExit(f"{name}: defined in {OWNER} and in ANTIGRAVITY_ONLY; keep one")
        servers[name] = {"command": spec["command"], "args": list(spec.get("args", [])), "env": dict(spec.get("env", {}))}
    return json.dumps({"mcpServers": servers}, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--check", action="store_true", help="exit 1 when the generated file is stale")
    a = ap.parse_args(argv)
    text, path = render(a.root), a.root / TARGET
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if a.check:
        if current != text:
            print(f"{TARGET} is stale: run `uv run python tools/mcp/sync_config.py`", file=sys.stderr)
            return 1
        return 0
    if current != text:
        path.write_text(text, encoding="utf-8", newline="\n")
    print(f"{TARGET}: {len(json.loads(text)['mcpServers'])} servers from {OWNER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
