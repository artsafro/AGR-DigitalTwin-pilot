"""Documentation contract tests for CAD plan DXF modules (Issue #99)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

MODULES = [
    "src/dt_ai/cad/__init__.py",
    "src/dt_ai/cad/plan_dxf.py",
]


@pytest.mark.parametrize("relative_path", MODULES)
def test_cad_module_docstring_contract(relative_path: str) -> None:
    path = ROOT / relative_path
    assert path.is_file(), f"Target module file does not exist: {path}"

    content = path.read_text(encoding="utf-8")
    docstring = ast.get_docstring(ast.parse(content))

    assert docstring is not None, f"Module {relative_path} must have a docstring"
    assert "new-case" in docstring, (
        f"Docstring in {relative_path} must contain 'new-case'"
    )
    assert re.search(r"\bstraight\b", docstring, re.IGNORECASE), (
        f"Docstring in {relative_path} must contain the word 'straight'"
    )
    assert re.search(r"\bserialization\b", docstring, re.IGNORECASE), (
        f"Docstring in {relative_path} must contain the word 'serialization'"
    )
