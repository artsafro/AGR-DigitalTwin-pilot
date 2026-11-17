"""Kept for old imports and evidence: the KPP1 seam seal moved unchanged to tools/blender/seam_seal.py (#1381).

`import seal` (jobs/KPP1/scripts/build_kpp1.py, jobs/PSU275/scripts/vpm_stage5.py) gets that owner module itself.
"""
import importlib.util
import sys
from pathlib import Path

_OWNER = Path(__file__).resolve().parents[3] / "tools" / "blender" / "seam_seal.py"
_spec = importlib.util.spec_from_file_location(__name__, _OWNER)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[__name__] = _mod
_spec.loader.exec_module(_mod)
