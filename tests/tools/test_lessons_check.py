"""LESSONS evidence check [D415] (#1924): each new job lesson = situation / lesson / evidence.

Pattern: n/a | new-case: tests of the warn-only job LESSONS.md evidence check.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/qa"))
import lessons_check as L  # noqa: E402

GOOD = """# X — lessons (job-local)

## L1 Read SKELETONS first
- Situation: practice run opened 40 files before the first stage.
- Lesson: start from docs/agents/SKELETONS.md.
- Evidence: C:/x/ab/ab.json, wrong-turns 7 -> 2, verdict fixed.
"""


def _w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_lesson_with_all_fields_has_no_warning():
    assert L.warnings_for(GOOD) == []
    assert [x["id"] for x in L.parse_lessons(GOOD)] == ["L1"]


@pytest.mark.parametrize("evidence", ["", "TODO", "n/a", "<contrast report>", "-", "none", "tbd"])
def test_missing_or_placeholder_evidence_warns(evidence):
    text = GOOD.replace("C:/x/ab/ab.json, wrong-turns 7 -> 2, verdict fixed.", evidence)
    w = L.warnings_for(text)
    assert len(w) == 1 and "L1" in w[0] and "evidence" in w[0]


def test_absent_fields_warn_each():
    w = L.warnings_for("## L2 Thing\n- Lesson: do x.\n")
    assert len(w) == 1 and "situation" in w[0] and "evidence" in w[0]


def test_only_new_lessons_are_checked_against_base():
    old = GOOD + "\n## L2 Old without evidence\n- Situation: s\n- Lesson: l\n"
    new = old + "\n## L3 New without evidence\n- Situation: s\n- Lesson: l\n"
    w = L.warnings_for(new, base=old)
    assert len(w) == 1 and "L3" in w[0]


def test_added_legacy_line_warns_unchanged_legacy_does_not():
    base = "# K — lessons\n\n- **Old.** rule [#1]\n"
    assert L.warnings_for(base, base=base) == []
    w = L.warnings_for(base + "- **New.** another rule [#2]\n| 3 | table rule | src | job |\n", base=base)
    assert len(w) == 2 and all("situation / lesson / evidence" in x for x in w)


def test_fenced_examples_and_template_are_not_lessons():
    tpl = (ROOT / "jobs/_template/LESSONS.md").read_text(encoding="utf-8")
    assert L.parse_lessons(tpl) == [] and L.warnings_for(tpl) == []
    assert "Situation" in tpl and "Evidence" in tpl and "D415" in tpl


def test_duplicate_lesson_id_warns():
    w = L.warnings_for(GOOD + GOOD.split("\n", 2)[2])
    assert any("duplicate" in x for x in w)


def _cli(*args, cwd=ROOT):
    return subprocess.run([sys.executable, str(ROOT / "tools/qa/lessons_check.py"), *args], capture_output=True,
                          text=True, cwd=cwd)


def test_cli_warn_only_strict_and_unreadable(tmp_path):
    bad = _w(tmp_path / "jobs/X/LESSONS.md", "## L1 t\n- Situation: s\n- Lesson: l\n")
    p = _cli(str(bad))
    assert p.returncode == 0 and "WARN" in p.stdout and "L1" in p.stdout
    assert _cli("--strict", str(bad)).returncode == 1
    good = _w(tmp_path / "jobs/Y/LESSONS.md", GOOD)
    p = _cli("--strict", str(good))
    assert p.returncode == 0 and "WARN" not in p.stdout
    p = _cli(str(tmp_path / "missing.md"))
    assert p.returncode == 2 and "missing.md" in p.stderr


def test_cli_staged_checks_only_new_lessons(tmp_path):
    repo = tmp_path / "r"
    _w(repo / "jobs/X/LESSONS.md", "## L1 old\n- Situation: s\n- Lesson: l\n")
    _w(repo / "jobs/X/notes.md", "x")
    git = ["git", "-C", str(repo)]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c"], check=True)
    p = _cli("--staged", cwd=repo)
    assert p.returncode == 0 and "WARN" not in p.stdout            # nothing staged: no warning
    _w(repo / "jobs/X/LESSONS.md", "## L1 old\n- Situation: s\n- Lesson: l\n\n## L2 new\n- Situation: s\n"
       "- Lesson: l\n")
    subprocess.run([*git, "add", "-A"], check=True)
    p = _cli("--staged", cwd=repo)
    assert p.returncode == 0 and "L2" in p.stdout and "L1" not in p.stdout
    assert _cli("--staged", "--strict", cwd=repo).returncode == 1
