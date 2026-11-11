"""Shim: the v015 Ground producer moved to tools/ground/build_ground_v015.py (`dt ground v015`, #1106).
Pattern: n/a | new-case: job-path shim routing recorded commands to the shared tool.
"""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "tools" / "ground" / "build_ground_v015.py"),
                   run_name="__main__")
