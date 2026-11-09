"""new-case: path-safe Max Python startup, without interpolating path literals."""
import importlib.util
from pathlib import Path
from pymxs import runtime as _agr_rt

_agr_spec = importlib.util.spec_from_file_location('agr_tools_runtime', Path(str(_agr_rt.AGRToolsRoot)) / 'runtime.py')
agr_tools_runtime = importlib.util.module_from_spec(_agr_spec)
_agr_spec.loader.exec_module(agr_tools_runtime)
