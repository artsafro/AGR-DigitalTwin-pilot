"""oks-vpm/body after hook: run the shared body core (#1736) with this job's floor.

Blender 4.4+: blender -b --factory-startup --disable-autoexec --python-exit-code 1 \\
    --python jobs/POLY63-C/hooks/build_body.py -- NEW_OUT_DIR
Job config only: the floor (plan format schemas/BodyPlan.schema.json) is `config.sources` of skeleton.json; the
builder is tools/methods/body/body_lattice_blender.py (was: module_build.py pinned at ce3c8a38 via git show).
"""
import json
import runpy
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[3] / "tools" / "methods" / "body" / "body_lattice_blender.py"


def main():
    job = Path(__file__).resolve().parents[1]
    out, = sys.argv[sys.argv.index("--") + 1:]
    floor = json.loads((job / "skeleton.json").read_text(encoding="utf-8"))["config"]["sources"]
    sys.argv = [str(CORE), "--", floor, str(Path(out).resolve())]
    runpy.run_path(str(CORE), run_name="__main__")


if __name__ == "__main__":
    main()
