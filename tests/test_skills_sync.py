"""`.claude/skills/` must be the generated copy of the canonical `.agents/skills/`."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = sorted(ROOT.glob(".agents/skills/*/SKILL.md")) + sorted(
    ROOT.glob(".claude/skills/*/SKILL.md")
)


def load():
    spec = importlib.util.spec_from_file_location("sync_skills", ROOT / "tools/sync_skills.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_claude_skills_match_agents_skills():
    assert load().differences() == [], "run: py -3 tools/sync_skills.py"


def test_every_skill_has_frontmatter():
    for skill in (ROOT / ".agents/skills").glob("*/SKILL.md"):
        head = skill.read_text(encoding="utf-8").splitlines()[:4]
        assert head[0] == "---" and any(line.startswith("name:") for line in head), skill


@pytest.mark.parametrize("skill", SKILL_FILES, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_skill_description_loads_with_trigger_and_action(skill):
    opening, frontmatter, body = skill.read_text(encoding="utf-8").split("---\n", 2)
    assert not opening and body.strip()
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == skill.parent.name
    description = metadata["description"]
    assert isinstance(description, str)
    trigger, separator, action = description.partition(". ")
    assert trigger.startswith("Use when ") and trigger.removeprefix("Use when ").strip()
    assert separator and action.endswith(".") and action[:-1].strip()
