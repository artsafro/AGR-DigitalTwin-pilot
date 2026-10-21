"""new-case: independent controls for the seeded synthetic geometry recall evaluator."""
import importlib.util
from pathlib import Path


def evaluator():
    path = Path(__file__).resolve().parents[2] / "tools/evals_geometry_mutation.py"
    assert path.is_file(), "geometry mutation evaluator must exist"
    spec = importlib.util.spec_from_file_location("geometry_mutation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_base_is_clean():
    ev = evaluator()
    report = ev.evaluate()
    assert report["synthetic"] is True
    assert report["base"]
    assert all(row["status"] == "pass" for row in report["base"]), report["base"]
