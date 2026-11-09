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


def test_addopts_with_m_returns_expression():
    assert _markexpr.markexpr_from_addopts("-m 'not blender and not job'") == "not blender and not job"


def test_addopts_without_m_returns_empty():
    assert _markexpr.markexpr_from_addopts("--tb=short -q") == ""
    assert _markexpr.markexpr_from_addopts("") == ""


def test_glued_m_forms_return_expression():
    assert _markexpr.markexpr_from_addopts("-mnot job") == "not job"
    assert _markexpr.markexpr_from_addopts("-m=not job") == "not job"


def test_last_m_wins():
    assert _markexpr.markexpr_from_addopts("-m a -m b") == "b"


def test_trailing_m_raises_value_error():
    with pytest.raises(ValueError):
        _markexpr.markexpr_from_addopts("-q -m")
    with pytest.raises(ValueError):
        _markexpr.markexpr_from_addopts("-m")


def test_space_m_takes_exactly_next_token():
    # pytest store semantics: `-m` takes one value, the rest are positionals.
    assert _markexpr.markexpr_from_addopts("-m 'not job' tests") == "not job"
    assert _markexpr.markexpr_from_addopts("-m slow tests/x") == "slow"


def test_m_followed_by_option_raises():
    with pytest.raises(ValueError):
        _markexpr.markexpr_from_addopts("-m -q")


def test_empty_glued_m_equals_raises():
    with pytest.raises(ValueError):
        _markexpr.markexpr_from_addopts("-m=")


def test_pyproject_list_addopts(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.pytest.ini_options]\naddopts = ["-q", "-m", "not job"]\n',
        encoding="utf-8",
    )
    assert _markexpr.markexpr_from_pyproject(pyproject) == "not job"


def test_pyproject_list_m_takes_exactly_next_token(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.pytest.ini_options]\naddopts = ["-m", "not job", "tests"]\n',
        encoding="utf-8",
    )
    assert _markexpr.markexpr_from_pyproject(pyproject) == "not job"


def test_pyproject_list_non_string_item_raises(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.pytest.ini_options]\naddopts = ["-m", 5]\n', encoding="utf-8")
    with pytest.raises(ValueError):
        _markexpr.markexpr_from_pyproject(pyproject)


def test_pyproject_non_str_non_list_addopts_raises(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.pytest.ini_options]\naddopts = 5\n', encoding="utf-8")
    with pytest.raises(ValueError):
        _markexpr.markexpr_from_pyproject(pyproject)


def test_pyproject_real_addopts_contains_not_job():
    """Parse the real pyproject.toml and check the expr carries 'not job'.

    Replaces the near-tautological helper-vs-helper comparison: read the actual
    ``[tool.pytest.ini_options].addopts`` with tomllib and assert the helper's
    returned expression contains ``not job``.
    """
    with open(PYPROJECT, "rb") as fh:
        addopts = tomllib.load(fh)["tool"]["pytest"]["ini_options"]["addopts"]
    assert "not job" in str(addopts)
    assert "not job" in _markexpr.markexpr_from_pyproject(PYPROJECT)


def test_dcc_default_markexpr_matches_pyproject():
    dcc = _dcc_module()
    assert dcc.DEFAULT_MARKEXPR == _markexpr.markexpr_from_pyproject(PYPROJECT)
    assert "not job" in dcc.DEFAULT_MARKEXPR
