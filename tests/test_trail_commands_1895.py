"""Live-trail command smoke test (#1895, D386 review rule).

Pattern: n/a | new-case: selective `--help` smoke over the `agr` / `dt` commands named on the live entry trails.

Every `agr ...` / `dt ...` command written in backticks on the live trails (AGENTS.md, routes/*.md,
docs/scenarios/*.md, the SKELETONS index) must answer `--help` with exit 0 in a fresh process; a section titled
"Candidate ... (not implemented)" is a proposal list and is skipped by name. A command the docs call unavailable
while the CLI serves it (not one of the `agr` pointer stubs) is a failure too (the `agr ucx` / `agr brick-seams`
false gaps of #1895).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.cli import agr

ROOT = Path(__file__).resolve().parents[1]
TRAILS = ("AGENTS.md", "docs/agents/SKELETONS.md", "docs/agents/skeletons.json",
          *sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "routes").glob("*.md")),
          *sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/scenarios").glob("*.md")))
_CMD = re.compile(r"`(?:uv run )?((?:agr|dt) [a-z][a-z0-9-]*(?: [a-z][a-z0-9-]*)?)")
_UNAVAILABLE = re.compile(r"`(?:uv run )?agr ([a-z][a-z0-9-]*)`[^.\n|]{0,40}?(?:unavailable|недоступ)", re.I)
_SKIP_SECTION = re.compile(r"^#+ .*(not implemented|candidate)", re.I | re.M)
# dt commands whose second word is a positional argument, not a sub-command
_DT_LEAF = {"inspect", "index-pdf"}


def live_text(rel: str) -> str:
    """The file without its proposal sections ("Candidate commands (not implemented)")."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    out, skip = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            skip = bool(_SKIP_SECTION.match(line))
        if not skip:
            out.append(line)
    return "\n".join(out)


def commands(text: str) -> set[tuple[str, ...]]:
    found = set()
    for m in _CMD.finditer(text):
        words = tuple(m.group(1).split())
        if words[0] == "agr":
            # `agr ground site|zero|v015` and `agr library publish|accept|reject` take a step word
            words = words if words[1] in ("ground", "library", "build-manifest") and len(words) == 3 else words[:2]
        elif words[1] in _DT_LEAF:
            words = words[:2]
        found.add(words)
    return found


def _live_commands():
    out = {}
    for rel in TRAILS:
        for cmd in commands(live_text(rel)):
            out.setdefault(cmd, rel)
    return sorted(out.items())


def _help(words) -> subprocess.CompletedProcess:
    module = "dt_ai.cli.agr" if words[0] == "agr" else "dt_ai.cli.main"
    return subprocess.run([sys.executable, "-m", module, *words[1:], "--help"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_trails_name_enough_commands():
    cmds = dict(_live_commands())
    assert len(cmds) >= 25, sorted(cmds)
    for must in (("agr", "body"), ("agr", "ucx"), ("agr", "brick-seams"), ("agr", "ground", "site"),
                 ("agr", "npm-light")):
        assert must in cmds, must


@pytest.mark.parametrize("words,where", _live_commands(), ids=lambda v: " ".join(v) if isinstance(v, tuple) else v)
def test_live_trail_command_answers_help(words, where):
    if words[0] == "agr" and words[1] in agr.STUBS:
        pytest.fail(f"{where}: `{' '.join(words)}` is a pointer stub, not a command; name its owner instead")
    result = _help(words)
    assert result.returncode == 0, f"{where}: `{' '.join(words)} --help` exit {result.returncode}: {result.stderr[-300:]}"


def test_no_live_trail_calls_a_served_command_unavailable():
    served = set(agr.ALIASES) | set(agr.SCRIPTS) | {"body", "ucx", "brick-seams", "vpm-to-npm", "maf-npm-to-vpm"}
    wrong = [(rel, m.group(1)) for rel in TRAILS for m in _UNAVAILABLE.finditer(live_text(rel))
             if m.group(1) in served]
    assert wrong == []


# --- extraction probes (fail closed: never an empty or silently shortened set) ---------------------------------

def test_extraction_alternate_forms():
    text = ("`uv run agr body PLAN NEW_OUT` and `agr ground site SPEC` and `dt qa xview F --out N` and "
            "`dt inspect --manifest J` and `agr library publish B` plus `agr` alone and agr unquoted body")
    assert commands(text) == {("agr", "body"), ("agr", "ground", "site"), ("dt", "qa", "xview"),
                              ("dt", "inspect"), ("agr", "library", "publish")}


def test_candidate_section_is_skipped_but_next_section_is_live(tmp_path):
    text = "# T\n`agr inspect`\n## Candidate commands (not implemented)\n`agr revit-twin`\n## Next\n`agr zero`\n"
    rel = "routes/_probe_1895.md"
    path = ROOT / rel
    assert not path.exists()
    try:
        path.write_text(text, encoding="utf-8")
        assert commands(live_text(rel)) == {("agr", "inspect"), ("agr", "zero")}
    finally:
        path.unlink()


def test_unavailable_claim_detector_probe():
    good = "`agr unwrap-atlas` unavailable: pointer"
    bad = "- `ucx-ground` — `agr ucx` недоступен; prior art"
    assert [m.group(1) for m in _UNAVAILABLE.finditer(good)] == ["unwrap-atlas"]
    assert [m.group(1) for m in _UNAVAILABLE.finditer(bad)] == ["ucx"]


def test_unknown_command_fails_help():
    assert _help(("agr", "no-such-command-1895")).returncode != 0
    assert _help(("dt", "no-such-command-1895")).returncode != 0
