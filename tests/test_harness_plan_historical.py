"""Live docs cite docs/HARNESS_PLAN.md only as history; gate messages cite the current rule."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_ROOTS = (
    ROOT / "AGENTS.md",
    ROOT / "docs" / "agents",
    ROOT / ".agents",
    ROOT / ".claude",
)
CURRENT_RULE = "docs/agents/WORKFLOW.md"
GATE_IMPL = "tools/git-hooks/pipeline_gate.py"


def live_files():
    files = []
    for root in LIVE_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return files


def _const_strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    for child in ast.iter_child_nodes(node):
        yield from _const_strings(child)


def test_live_docs_mark_harness_plan_historical():
    """Every HARNESS_PLAN line in the live set says historical; an empty set fails closed."""
    files = live_files()
    assert files, "live-doc set is empty (fail closed)"
    unmarked = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(text.splitlines(), 1):
            if "HARNESS_PLAN" in line and "historical" not in line.lower():
                unmarked.append(f"{rel}:{number}: {line.strip()}")
    assert not unmarked, "unmarked HARNESS_PLAN mention:\n" + "\n".join(unmarked)


def test_benchmark_readme_marks_harness_plan_historical():
    path = ROOT / "benchmark" / "README.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [(n, line) for n, line in enumerate(lines, 1) if "HARNESS_PLAN" in line]
    assert hits, "benchmark/README.md no longer cites HARNESS_PLAN"
    unmarked = [f"benchmark/README.md:{n}: {line.strip()}"
                for n, line in hits if "historical" not in line.lower()]
    assert not unmarked, "unmarked HARNESS_PLAN mention:\n" + "\n".join(unmarked)


def test_gate_message_strings_omit_harness_plan():
    """ESCALATION, blocked and the deny reason name the current rule and omit HARNESS_PLAN."""
    gate = ast.parse((ROOT / "tools" / "git-hooks" / "pipeline_gate.py").read_text(encoding="utf-8"))
    found_escalation = False
    found_blocked = False
    for node in ast.walk(gate):
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "ESCALATION" in names:
                found_escalation = True
                blob = "".join(_const_strings(node.value))
                assert "HARNESS_PLAN" not in blob, blob
                assert CURRENT_RULE in blob and GATE_IMPL in blob, blob
        if isinstance(node, ast.Call) and _call_name(node) == "print":
            blob = "".join(_const_strings(node))
            if "blocked" in blob:
                found_blocked = True
                assert "HARNESS_PLAN" not in blob, blob
                assert CURRENT_RULE in blob and GATE_IMPL in blob, blob
    assert found_escalation, "ESCALATION message not found"
    assert found_blocked, "blocked message not found"

    hook = ast.parse((ROOT / ".claude" / "hooks" / "pipeline_gate.py").read_text(encoding="utf-8"))
    found_deny = False
    for node in ast.walk(hook):
        if isinstance(node, ast.FunctionDef) and node.name == "deny":
            found_deny = True
            blob = "".join(_const_strings(node))
            assert "HARNESS_PLAN" not in blob, blob
            assert CURRENT_RULE in blob and GATE_IMPL in blob, blob
    assert found_deny, "deny reason not found"


def _call_name(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None
