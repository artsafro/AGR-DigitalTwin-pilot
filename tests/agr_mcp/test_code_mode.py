"""new-case: synthetic Max Code Mode protocol fixtures; never connects to a live DCC."""
import importlib.util


def test_prototype_exists():
    assert importlib.util.find_spec("agr_mcp.code_mode") is not None, "safe Code Mode is missing"
