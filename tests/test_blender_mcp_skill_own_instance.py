"""blender-mcp skill: port check first, agent-owned Blender on a copy, close only own PID (#1033).

new-case: doc-content regression test for the blender-mcp skill connection procedure.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/blender-mcp/SKILL.md"
DECISIONS = ROOT / "docs/decisions.md"
MAX_LINES = 120  # same cap as tests/test_dcc_skill_pitfalls.py


def section(text, title):
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"section '## {title}' missing"
    return m.group(1)


def decision_id():
    rows = [l for l in DECISIONS.read_text(encoding="utf-8").splitlines()
            if l.startswith("| D") and "own Blender" in l]
    assert len(rows) == 1, f"expected one own-Blender decision row, got {len(rows)}"
    return rows[0].split("|")[1].strip()


def test_port_check_comes_before_any_question_to_the_user():
    text = SKILL.read_text(encoding="utf-8")
    connect = section(text, "Connect and identify")
    first = connect.strip().splitlines()[0]
    assert first.startswith("0.") and "port" in first.lower()
    step0 = connect.split("\n1.")[0]
    for token in ("9877", "9876", "SketchUp", "netstat -ano", "tasklist"):
        assert token in step0, token
    # the check is step 0, before step 4 (the only step that may ask the user)
    assert "before asking the user" in step0
    assert connect.index("netstat -ano") < connect.index("\n4.")
    assert "authorization" not in step0


def test_own_instance_on_hashed_versioned_copy_documented():
    own = section(SKILL.read_text(encoding="utf-8"), "Agent-owned Blender on a copy")
    for token in ("5.1.2", "--online-mode", "9877", "sha256sum", "_v", "copy"):
        assert token in own, token
    assert "never" in own.lower() and "toggle" in own.lower()


def test_online_access_conflict_resolved_by_recorded_decision():
    did = decision_id()
    assert re.fullmatch(r"D\d+", did)
    text = SKILL.read_text(encoding="utf-8")
    assert f"[{did}]" in text
    connect = section(text, "Connect and identify")
    # step 4 now limits the authorization rule to the user's own instance
    step4 = connect.split("\n4.")[1]
    assert "user's own" in step4 and f"[{did}]" in step4


def test_stray_instances_close_only_own_pid():
    own = section(SKILL.read_text(encoding="utf-8"), "Agent-owned Blender on a copy")
    assert "PID" in own and "taskkill /PID" in own
    assert re.search(r"only (its|the agent's) own", own)
    assert "/IM" not in own  # never kill by image name


def test_skill_stays_short():
    assert len(SKILL.read_text(encoding="utf-8").splitlines()) <= MAX_LINES
