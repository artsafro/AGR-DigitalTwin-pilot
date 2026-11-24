"""Render four 63C review panels, using Workbench on a disposable copy of the scene.
Blender --background scene.blend --python stage2_views.py -- OUT_DIR FRAME_ID [ISO_ORTHO_SCALE]

Shim (t_3820c6be): the render lives in the owner tools/blender/stage2_review.py (render_views); 63B calls this
path too (jobs/POLY63-B/stage2/README.md).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools' / 'blender'))
import stage2_review  # noqa: E402

stage2_review.main(sys.argv[sys.argv.index('--') + 1:])
