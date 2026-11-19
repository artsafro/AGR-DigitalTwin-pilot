"""Kept for old commands and evidence: runs the one master-geometry QA tools/blender/qa_master.py (#1379).

Unchanged use: blender --background --factory-startup <file.blend|-> --python qa_master.py -- <out.json> [fbx]
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[3] / "tools" / "blender" / "qa_master.py"), run_name="__main__")
