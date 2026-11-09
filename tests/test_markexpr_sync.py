"""new-case: guard the pytest ``-m`` exclusion expression against drift (#1122).

The default suite's opt-in marker exclusions live in pyproject.toml
``[tool.pytest.ini_options].addopts``. This test pins the parser
(``tests/_markexpr.py``) to that expression and asserts that the
``DEFAULT_MARKEXPR`` used by the AC08 native-parity tests is derived from it,
so the two can never diverge again
(docs/research/merge-gate-deselect-190-vs-card-417.md, finding 6).
"""
import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

_SPEC = importlib.util.spec_from_file_location("_markexpr", ROOT / "tests" / "_markexpr.py")
_markexpr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_markexpr)


def _dcc_module():
    path = ROOT / "tests" / "dcc" / "test_ac08_xview_native_parity.py"
    spec = importlib.util.spec_from_file_location("test_ac08_xview_native_parity", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pyproject_addopts():
    with open(PYPROJECT, "rb") as fh:
        data = tomllib.load(fh)
    return data["tool"]["pytest"]["ini_options"]["addopts"]


def test_addopts_with_m_returns_expression():
    assert _markexpr.markexpr_from_addopts("-m 'not blender and not job'") == "not blender and not job"


def test_addopts_without_m_returns_empty():
    assert _markexpr.markexpr_from_addopts("--tb=short -q") == ""
    assert _markexpr.markexpr_from_addopts("") == ""


def test_trailing_m_raises_value_error():
    with pytest.raises(ValueError):
        _markexpr.markexpr_from_addopts("-q -m")


def test_helper_equals_pyproject_addopts():
    assert _markexpr.markexpr_from_pyproject(PYPROJECT) == _markexpr.markexpr_from_addopts(_pyproject_addopts())


def test_pyproject_markexpr_contains_not_job():
    assert "not job" in _markexpr.markexpr_from_pyproject(PYPROJECT)


def test_dcc_default_markexpr_matches_pyproject():
    dcc = _dcc_module()
    assert dcc.DEFAULT_MARKEXPR == _markexpr.markexpr_from_pyproject(PYPROJECT)
    assert "not job" in dcc.DEFAULT_MARKEXPR
