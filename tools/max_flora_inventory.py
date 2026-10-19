"""New case #189: native read-only Text/TextPlus/mesh inventory entry point.

Only via dcc_batch.py max (2026), on the two hash-verified card-root scene copies.
Implementation and pure parser/pairing probes are isolated in the experiment.
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[1] / 'experiments/flora-library-audit/inspect_scene.py'), run_name='__main__')
