"""Decision trees per scenario (#2039): every skeleton stage has a node, every cited rule exists and is quoted."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import decision_trees as dt  # noqa: E402


def _live():
    return dt.load_trees(ROOT), dt.load_skeletons(ROOT), dt.decision_sources(ROOT)


def _first_agent_branch(trees):
    for node in trees["stages"].values():
        for branch in node["branches"]:
            if branch["decider"] == "AGENT" and any(r.startswith("D") for r in branch["rule"]):
                return branch
    raise AssertionError("no AGENT branch with a D-id")


def test_live_trees_are_clean():
    trees, skeletons, rows = _live()
    assert dt.problems(trees, skeletons, rows, ROOT) == []


def test_cited_missing_decision_id_fails():
    trees, skeletons, rows = _live()
    bad = copy.deepcopy(trees)
    _first_agent_branch(bad)["rule"] = ["D999"]
    found = dt.problems(bad, skeletons, rows, ROOT)
    assert any("cites missing D999" in p for p in found), found


def test_quote_not_in_cited_rule_fails():
    trees, skeletons, rows = _live()
    bad = copy.deepcopy(trees)
    _first_agent_branch(bad)["quote"] = "a rule nobody ever wrote"
    found = dt.problems(bad, skeletons, rows, ROOT)
    assert any("quote not found" in p for p in found), found


def test_skeleton_stage_without_node_fails():
    trees, skeletons, rows = _live()
    sk = copy.deepcopy(skeletons)
    sk["stages"]["no-such-stage"] = {"ru": "x", "calls": None, "gap": "manual"}
    sk["cells"]["oks-npm"]["stages"].append("no-such-stage")
    found = dt.problems(trees, sk, rows, ROOT)
    assert "oks-npm: stage no-such-stage has no decision node" in found, found


def test_skeleton_cell_without_tree_fails():
    trees, skeletons, rows = _live()
    bad = copy.deepcopy(trees)
    del bad["cells"]["sintez-fix"]
    found = dt.problems(bad, skeletons, rows, ROOT)
    assert "sintez-fix: skeleton cell has no tree" in found, found


def test_gap_flag_must_match_skeleton():
    trees, skeletons, rows = _live()
    bad = copy.deepcopy(trees)
    bad["stages"]["zero"]["gap"] = False
    found = dt.problems(bad, skeletons, rows, ROOT)
    assert any("zero: gap flag" in p for p in found), found


def test_agent_branch_without_rule_fails_and_artem_needs_sheet():
    trees, skeletons, rows = _live()
    bad = copy.deepcopy(trees)
    branch = _first_agent_branch(bad)
    branch["rule"] = []
    found = dt.problems(bad, skeletons, rows, ROOT)
    assert any("AGENT branch without a rule" in p for p in found), found
    bad = copy.deepcopy(trees)
    for node in bad["stages"].values():
        artem = [b for b in node["branches"] if b["decider"] == "ARTEM"]
        if artem:
            artem[0]["sheet"] = ""
            break
    found = dt.problems(bad, skeletons, rows, ROOT)
    assert any("ARTEM branch without a picture sheet" in p for p in found), found


def test_every_gap_stage_is_marked_and_counted():
    trees, skeletons, _ = _live()
    gaps = sorted(s for s, spec in skeletons["stages"].items() if spec.get("gap"))
    assert len(gaps) == 11
    assert all(trees["stages"][s]["gap"] is True for s in gaps)


def test_rendered_markdown_in_sync():
    trees, skeletons, _ = _live()
    for cell in skeletons["cells"]:
        path = ROOT / dt.MD_DIR / f"{cell}.md"
        assert path.read_text(encoding="utf-8") == dt.render_md(trees, skeletons, cell), cell


def test_show_prints_stage_node():
    out = subprocess.run([sys.executable, str(ROOT / "tools/architecture/decision_trees.py"), "--show", "oks-npm",
                          "--stage", "body"], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert "[D336]" in out.stdout and "AGENT" in out.stdout


def test_trees_linked_from_skeletons():
    data = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))
    assert data["decision_trees"] == dt.TREES
    assert "decision-trees.json" in (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("nxt", ["back:no-such-stage", "elsewhere"])
def test_bad_next_fails(nxt):
    trees, skeletons, rows = _live()
    bad = copy.deepcopy(trees)
    _first_agent_branch(bad)["next"] = nxt
    found = dt.problems(bad, skeletons, rows, ROOT)
    assert any("next" in p for p in found), found
