"""DCC batch locks must take the live kanban card, not a finished card id."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
# Flora atlas Max coverage is parked; that file keeps its old card on purpose.
ALLOWLIST = frozenset({"tests/dcc/test_flora_atlas_max.py"})
CARD_ID = re.compile(r"t_[0-9a-f]{8}\Z")


def hardcoded_card_literals(source: str) -> list[tuple[int, str]]:
    """Return (line, id) where a ``--card`` argument is a finished-card literal.

    AST adjacency covers ``--card`` and the id on separate lines.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [(exc.lineno or 1, "unparseable")]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            elements = node.elts
        elif isinstance(node, ast.Call):
            elements = list(node.args)
        else:
            continue
        for left, right in zip(elements, elements[1:]):
            if (
                isinstance(left, ast.Constant)
                and left.value == "--card"
                and isinstance(right, ast.Constant)
                and isinstance(right.value, str)
                and CARD_ID.fullmatch(right.value)
            ):
                found.append((right.lineno, right.value))
    return found


def scan_paths(paths, *, root: Path = ROOT) -> list[str]:
    rows = []
    for path in paths:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for line, value in hardcoded_card_literals(text):
            rows.append(f"{rel}:{line} {value}")
    return rows


def scan_tests_tree() -> list[str]:
    return scan_paths(sorted(TESTS.rglob("*.py")))


def test_scanner_reports_card_literal_across_lines(tmp_path):
    sample = tmp_path / "bad.py"
    sample.write_text('args = [\n    "--card",\n    "t_deadbeef",\n]\n', encoding="utf-8")
    assert scan_paths([sample], root=tmp_path) == ["bad.py:3 t_deadbeef"]


def test_scanner_ignores_card_id_call(tmp_path):
    sample = tmp_path / "ok.py"
    sample.write_text('args = ["--card", card_id()]\n', encoding="utf-8")
    assert scan_paths([sample], root=tmp_path) == []


def test_tests_tree_has_no_hardcoded_finished_card_id():
    assert scan_tests_tree() == []
