"""Live 3ds Max / Blender safety pitfalls are in the repo skills, each dated (#1032).

new-case: doc-content regression test for DCC skill pitfalls.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_SKILL = ROOT / ".agents/skills/3dsmax-mcp-dev/SKILL.md"
BLENDER_SKILL = ROOT / ".agents/skills/blender-mcp/SKILL.md"
MAX_LINES = 120  # a skill stays a short procedure, not a manual

# token that must appear in one pitfall bullet -> source session cited in that bullet
MAX_PITFALLS = {
    "resetMaxFile": "кондиционеров 4К",
    "loadMaxFile": "кондиционеров 4К",
    "max undo": "кондиционеров 4К",
    "freeSceneBitmaps()": "кондиционеров 4К",
    "4.3 M faces": "кондиционеров 4К",
    "unsaved live scene": "Kasatkino",
    "useNewFile:false": "Ворота Object 001",
    "meshop.attach": "Ворота Object 001",
    "polyop.detachFaces": "кондиционеров 4К",
    "Start-Process": "Ворота Object 001",
    # mirrored from user memory max-mesh-edit-pitfalls.md
    "formattedPrint": "Ворота Object 001",
    "o.modifiers.count": "Ворота Object 001",
    "setEdgeVis": "Ворота Object 001",
    "by handle": "Ворота Object 001",
    "fileIn": "2026-11-07",
    "polyop.attach": "2026-11-07",
}
DATE = re.compile(r"20\d\d-\d\d-\d\d")


def bullets(text):
    """Top-level bullets with their continuation lines joined."""
    out = []
    for line in text.splitlines():
        if line.startswith("- "):
            out.append(line)
        elif line.startswith("  ") and out and out[-1]:
            out[-1] += " " + line.strip()
        else:
            out.append("")
    return [b for b in out if b]


def bullet_with(text, token):
    hits = [b for b in bullets(text) if token in b]
    assert hits, f"no pitfall bullet mentions {token!r}"
    return hits[0]


def test_every_max_pitfall_is_dated_and_sourced():
    text = MAX_SKILL.read_text(encoding="utf-8")
    for token, source in MAX_PITFALLS.items():
        bullet = bullet_with(text, token)
        assert DATE.search(bullet), f"{token!r} bullet has no date"
        assert source in bullet, f"{token!r} bullet lacks source {source!r}"


def test_blender_heavy_pass_pitfall():
    bullet = bullet_with(BLENDER_SKILL.read_text(encoding="utf-8"), "UDIM")
    for need in ("main thread", "background", "2026-11-05", "Garibaldi"):
        assert need in bullet, need


def test_unverified_crash_cause_not_stated_as_fact():
    # memory line 14: Max closed during a base-mesh edit, but the user said he closed it himself
    bullet = bullet_with(MAX_SKILL.read_text(encoding="utf-8"), "baseobject")
    assert "unverified" in bullet
    assert not re.search(r"\bcrash(es|ed)?\b", bullet.replace("crash cause unverified", ""))


def test_skills_stay_short():
    for skill in (MAX_SKILL, BLENDER_SKILL):
        assert len(skill.read_text(encoding="utf-8").splitlines()) <= MAX_LINES, skill
