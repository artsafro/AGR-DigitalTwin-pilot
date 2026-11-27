"""Stage-2 review sheet has one owner (t_3820c6be, harvest #1804): tools/blender/stage2_review.py.

Pattern: n/a | new-case: static regression of the stage-2 review owner promotion (POLY63-A/B/C hooks call it).
Pixel equality of the hooks before/after was measured in real Blender 5.1 (PR body); here only static facts.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import skeleton_guard as sg  # noqa: E402

OWNER = "tools/blender/stage2_review.py"
VIEWS = ROOT / "jobs/POLY63-C/hooks/stage2_views.py"
SHEET = ROOT / "jobs/POLY63-A/stage2-1619/hooks/stage2_sheet.py"
SK = sg.load_skeletons(ROOT)


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _defs(tree):
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def _imports(tree):
    return {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}


def test_owner_defines_the_shared_blocks():
    defs = _defs(_tree(ROOT / OWNER))
    assert {"render_views", "wire_copy", "opening_axes", "workbench", "show_only", "aim", "tile_2x2"} <= defs


def test_63c_views_is_a_shim_of_the_owner():
    tree = _tree(VIEWS)
    assert "stage2_review" in _imports(tree)
    assert not _defs(tree)
    assert "WIREFRAME" not in VIEWS.read_text(encoding="utf-8")


def test_63a_sheet_calls_owner_blocks_not_copies():
    tree = _tree(SHEET)
    text = SHEET.read_text(encoding="utf-8")
    assert "stage2_review" in _imports(tree)
    assert not _defs(tree) & {"wire_of", "centre", "wire_copy", "tile_2x2"}
    assert "WIREFRAME" not in text and "numpy" not in text
    for call in ("sr.wire_copy", "sr.opening_axes", "sr.workbench", "sr.show_only", "sr.aim", "sr.tile_2x2"):
        assert call in text


def test_63b_readme_still_points_at_the_shim():
    readme = (ROOT / "jobs/POLY63-B/stage2/README.md").read_text(encoding="utf-8")
    assert "stage2_views.py -- " in readme and VIEWS.is_file()


def test_readback_stage_lists_the_owner():
    spec = SK["stages"]["readback"]
    assert OWNER in spec["owners"] and OWNER in spec["calls"]
    assert {"wire_copy", "render_views"} <= set(spec["entry_defs"])


def test_guard_flags_a_job_local_copy_of_the_review_render():
    src = b"def wire_copy(ob, t, m, c):\n    return ob\n"
    problems = sg.stage_problems(src, "jobs/X/hooks/h.py", [("readback", SK["stages"]["readback"])])
    assert len(problems) == 1 and "wire_copy" in problems[0] and "stage2_review.py" in problems[0]
