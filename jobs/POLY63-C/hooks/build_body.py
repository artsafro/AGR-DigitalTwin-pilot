"""oks-vpm/body after hook: run the pinned #1619 builder with this job's floor.

From a normal clone with the training branch fetched, Blender 4.4:
blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
    --python jobs/POLY63-C/hooks/build_body.py -- NEW_OUT_DIR
For a shallow/single-branch clone first run: git fetch origin <REVISION below>.
"""
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

REVISION = "ce3c8a384bbba35b18ab2abd19b4714fd4af91e9"
OWNER = "jobs/garibaldi22/body-training-1619/hooks/module_build.py"


def main():
    job = Path(__file__).resolve().parents[1]
    out, = sys.argv[sys.argv.index("--") + 1:]
    floor = json.loads((job / "skeleton.json").read_text(encoding="utf-8"))["config"]["sources"]
    source = subprocess.check_output(["git", "show", f"{REVISION}:{OWNER}"], cwd=job)
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "module_build.py"
        script.write_bytes(source)
        sys.argv = [str(script), "--", floor, str(Path(out).resolve())]
        runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
