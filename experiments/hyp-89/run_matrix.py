"""Hypothesis #89, step 2: export/readback matrix, headless blender.exe 5.1.2 vs bpy==5.1.2 wheel.

    python experiments/hyp-89/run_matrix.py <work dir with common/> <wheel python.exe> [reps=2]

Per repetition (fresh dir rep<N>), per model, per exporter lane E in {exe, whl}:
  export_mesh_blender.py  dump -> E/model.blend, E/model.fbx           (lane E)
  measure_spec_blender.py E/model.blend -> ms-blend.json                (lane E)
  for reader lane R in {exe, whl}:
    fbx_readback.py       E/model.fbx -> rb-R.json                      (lane R)
    measure_spec_blender.py E/model.fbx -> ms-fbx-R.json                (lane R)
Scripts are the repository's, unchanged. Every call is a separate process with a timeout and a log.
Writes <work>/runs.json (exit codes, seconds, log tail).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXE = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
EXPORT = ROOT / "tools/export/export_mesh_blender.py"
READBACK = ROOT / "tools/blender/fbx_readback.py"
MEASURE = ROOT / "tools/source/measure_spec_blender.py"
work, wheel = Path(sys.argv[1]).resolve(), sys.argv[2]
reps = int(sys.argv[3]) if len(sys.argv) > 3 else 2
runs = []


def call(lane, script, args, log):
    if lane == "exe":
        cmd = [EXE, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
               "--python", str(script), "--", *map(str, args)]
    else:
        cmd = [wheel, str(script), "--", *map(str, args)]
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
        code, text = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        code, text = "timeout", str(e)
    dt = time.perf_counter() - t
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(text, encoding="utf-8")
    runs.append({"lane": lane, "script": script.name, "args": [str(a) for a in args], "exit": code,
                 "seconds": round(dt, 3), "log": str(log), "tail": text.strip().splitlines()[-2:]})
    print(f"{lane} {script.name:26s} exit={code} {dt:6.2f}s {Path(args[-1]).relative_to(work)}", flush=True)


for rep in range(1, reps + 1):
    base = work / f"rep{rep}"
    base.mkdir(exist_ok=False)
    for model in ("B01", "B02", "B02t"):
        dump = work / "common" / f"{model}-dump.json"
        for e in ("exe", "whl"):
            d = base / model / e
            call(e, EXPORT, [dump, d / "model.blend", d / "model.fbx"], d / "export.log")
            call(e, MEASURE, [d / "model.blend", d / "ms-blend.json"], d / "ms-blend.log")
            for r in ("exe", "whl"):
                call(r, READBACK, [d / "model.fbx", d / f"rb-{r}.json"], d / f"rb-{r}.log")
                call(r, MEASURE, [d / "model.fbx", d / f"ms-fbx-{r}.json"], d / f"ms-fbx-{r}.log")
(work / "runs.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
