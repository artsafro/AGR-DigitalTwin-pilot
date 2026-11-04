"""Import shim: polygon logic lives in test-polygon/polygon_core.py (no pymxs)."""
import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / 'test-polygon' / 'polygon_core.py'
_spec = importlib.util.spec_from_file_location('agr_polygon_core', _PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['agr_polygon_core'] = _mod
_spec.loader.exec_module(_mod)

load_expected = _mod.load_expected
suite_rows = _mod.suite_rows
predict_all = _mod.predict_all
compare_report = _mod.compare_report
check_paths = _mod.check_paths
ACTION_ROW = _mod.ACTION_ROW
bases = _mod.bases
stations = _mod.stations
excluded_name = _mod.excluded_name
preserve_user_bundle = _mod.preserve_user_bundle
stage_tools = _mod.stage_tools
group_runs = _mod.group_runs
render_table = _mod.render_table
checked_export_target = _mod.checked_export_target
bind_produced = _mod.bind_produced
