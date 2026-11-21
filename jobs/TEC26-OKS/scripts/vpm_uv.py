"""Compatibility import of the shared VPM UV owner; historical deliveries remain unchanged (#1380)."""
import runpy
from pathlib import Path

_owner = Path(__file__).resolve().parents[3] / 'tools' / 'blender' / 'vpm_uv.py'
globals().update({k: v for k, v in runpy.run_path(str(_owner)).items() if not k.startswith('__')})
