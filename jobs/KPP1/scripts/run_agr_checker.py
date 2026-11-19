"""Kept for old commands and evidence: runs the one SINTEZ checker launch tools/blender/sintez_checker.py (#1379).

Route command: `agr checker FOLDER --output NEW.json` (tools/qa/sintez_checker.py). Unchanged direct use:
    blender --background --factory-startup --python run_agr_checker.py -- <folder_with_zips> <out.json>
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[3] / "tools" / "blender" / "sintez_checker.py"), run_name="__main__")
