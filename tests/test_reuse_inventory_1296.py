"""Research artifact checks, not geometry or proposed agr CLI certification."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "docs/research/reuse-1296/measure.py"


def analyzer():
    assert ANALYZER.is_file(), "Missing reproducible research inventory analyzer"
    spec = importlib.util.spec_from_file_location("reuse_1296", ANALYZER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_covers_scripts_not_config():
    m = analyzer()
    paths = ["jobs/A/scripts/export.py", "jobs/A/scripts/settings.json",
             "tools/example.sh", "adapters/max/agr_tools/core.py",
             "src/dt_ai/cli/main.py", "src/dt_ai/ordinary.py"]
    texts = {p: "print('ok')" for p in paths}
    assert m.select_paths(paths, texts) == [paths[i] for i in (0, 2, 3, 4)]
