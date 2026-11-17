"""PR #1660 review r2 (#1619): this PR's decision rows must not reuse an id already taken by another branch.

#1315 (branch improve/issue-1315-cold-reproduction-on-a-new-site-ground-u) reserved and pushed D340 first, so by
COORDINATION rule 42 the #1619 row was renumbered D340 -> D344; D342 is reserved by card 8753.

Pattern: n/a | new-case: test of the #1619 decision-id renumbering.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs" / "decisions.md"
BRANCH_1315 = "origin/improve/issue-1315-cold-reproduction-on-a-new-site-ground-u"
# The #1315 row as pushed in 5cb972b3 (id + leading words); used when the branch is not fetched.
ROW_1315 = {"D340": "Silikatny #1315"}
RESERVED_ELSEWHERE = {"D340", "D342"}  # D340: #1315 (rule 42), D342: codex card 8753
ROW = re.compile(r"^\| (D\d+) \|(.*)$")


def _rows(text):
    out = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


def _ours(rows):
    return {i for i, bodies in rows.items() if any("#1619" in b and "t_9421c40f" in b for b in bodies)}


def _branch_rows(ref):
    try:
        text = subprocess.run(["git", "show", f"{ref}:docs/decisions.md"], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", check=True).stdout
    except (subprocess.CalledProcessError, OSError):
        return None
    return _rows(text)


def test_our_ids_are_renumbered():
    rows = _rows(DECISIONS.read_text(encoding="utf-8"))
    assert _ours(rows) == {"D341", "D344"}


def test_no_duplicate_ids_in_file():
    rows = _rows(DECISIONS.read_text(encoding="utf-8"))
    dup = {i: len(b) for i, b in rows.items() if len(b) > 1}
    assert dup == {}


def test_no_id_reserved_elsewhere():
    rows = _rows(DECISIONS.read_text(encoding="utf-8"))
    assert _ours(rows) & RESERVED_ELSEWHERE == set()


def test_no_stale_d340_citation():
    hits = []
    for rel in [".agents/skills/scenario/SKILL.md", ".claude/skills/scenario/SKILL.md", "docs/domain/areas/body.md",
                "docs/research/body-modelling-summary-ru.md", "docs/research/body-modelling.md",
                "docs/research/body-training-1619/README.md",
                "jobs/garibaldi22/body-training-1619/hooks/zones_from_etalon.py"]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        hits += [rel for _ in re.finditer(r"D340\b", text)]
    assert hits == []


def test_no_reuse_against_1315_branch():
    other = _branch_rows(BRANCH_1315)
    if other is None:  # branch not fetched: compare with the pinned #1315 row
        other = {k: [v] for k, v in ROW_1315.items()}
    ours = _ours(_rows(DECISIONS.read_text(encoding="utf-8")))
    other_1315 = {i for i, bodies in other.items() if any("#1315" in b for b in bodies)}
    assert "D340" in other_1315
    assert ours & other_1315 == set()


def test_detector_catches_reuse():
    """Witness: the old state (our row at D340) must be flagged against the #1315 row."""
    old = _rows("| D340 | 2026-11-17 | OKS body grid (#1619) Kanban t_9421c40f |\n")
    assert _ours(old) & set(ROW_1315) == {"D340"}


@pytest.mark.parametrize("text", ["", "no table\n", "| D340 | broken"])
def test_parser_fail_closed(text):
    assert _ours(_rows(text)) == set()
