"""Failure-mode matrix: current Blender call sites vs prototype runner, on a fake Blender (synthetic).

uv run python experiments/scripts-logic/probe_matrix.py <workdir>
Prints a JSON matrix: site -> mode -> outcome (accepted | clear:<Type> | raw:<Type>) and elapsed s.
"""
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools/qa"), str(ROOT), str(HERE)]

WORK = Path(sys.argv[1]).resolve()
WORK.mkdir(parents=True, exist_ok=True)
FAKE = WORK / "blender.cmd"
FAKE.write_text(f'@"{sys.executable}" "{HERE / "fake_blender.py"}" %*\r\n', encoding="ascii")
os.environ["TWINQA_BLENDER"] = str(FAKE)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


from dt_ai.core import build  # noqa: E402
from twinqa import scene  # noqa: E402
import blender_runner  # noqa: E402

clearance = load(ROOT / "tools/qa/check_clearance.py", "check_clearance")
bench = load(ROOT / "tools/qa/run_benchmark.py", "run_benchmark")
uvc = load(ROOT / "technical_library/uv_continuous/common.py", "uvc_common")
SCRIPT = ROOT / "tools/blender/fbx_readback.py"  # never executed by the fake; only its name is used
FBX = WORK / "in.fbx"
FBX.write_bytes(b"synthetic")


def fresh(name):
    d = WORK / name
    d.mkdir(parents=True, exist_ok=True)
    for f in d.iterdir():
        if f.is_file():
            f.unlink()
    return d


def site_build(timeout):
    d = fresh("build")
    req = {"operation": "audit", "result": str(d / "result.json")}
    return build.run_blender(str(FAKE), ROOT, req, d)


def site_scene(timeout):
    return scene.readback(FBX, str(FAKE), timeout=timeout)


def site_clearance(timeout):
    return clearance.faces_from_fbx(FBX)


def site_benchmark(timeout):
    out = fresh("bench") / "dump.json"
    bench.blender_run(str(FAKE), SCRIPT, FBX, out, timeout=timeout)
    bench.produced(out)  # what run_benchmark.run() does after each step
    return json.loads(out.read_text(encoding="utf-8"))


def site_uvc(timeout):
    return uvc.run_dcc(SCRIPT, fresh("uvc"), FAKE)


def site_runner(timeout):
    out = fresh("runner") / "readback.json"
    return blender_runner.run(FAKE, SCRIPT, FBX, out, outputs=[out], log=out.with_suffix(".log"),
                              timeout=timeout)


SITES = {"dt_ai.core.build.run_blender": site_build, "twinqa.scene.readback": site_scene,
         "tools/qa/check_clearance.faces_from_fbx": site_clearance,
         "tools/qa/run_benchmark.blender_run+produced": site_benchmark,
         "technical_library/uv_continuous.run_dcc": site_uvc,
         "PROTOTYPE blender_runner.run": site_runner}
HANG_SITES = {"twinqa.scene.readback", "tools/qa/run_benchmark.blender_run+produced", "PROTOTYPE blender_runner.run"}
if sys.argv[2:] == ["runner"]:  # re-measure only the prototype (baseline hang costs ~120 s per site)
    SITES = {k: v for k, v in SITES.items() if k.startswith("PROTOTYPE")} | {"twinqa.scene.readback": site_scene}
    HANG_SITES = {"PROTOTYPE blender_runner.run"}
MODES = ["ok", "valid_exit7", "no_output", "malformed", "empty"]


def outcome(fn, timeout=30):
    t = time.perf_counter()
    try:
        fn(timeout)
        res = "accepted"
    except (RuntimeError, blender_runner.BlenderRunError) as exc:
        res = f"clear:{type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001
        res = f"raw:{type(exc).__name__}"
    return res, round(time.perf_counter() - t, 2)


matrix = {}
for site, fn in SITES.items():
    matrix[site] = {}
    for mode in MODES:
        os.environ["FAKE_BLENDER_MODE"] = mode
        matrix[site][mode] = outcome(fn)[0]
    if site in HANG_SITES:
        os.environ["FAKE_BLENDER_MODE"] = "hang"
        matrix[site]["hang(timeout=2s)"] = outcome(fn, timeout=2)
# overhead: ok mode, 5 runs each, scene.readback vs prototype runner
os.environ["FAKE_BLENDER_MODE"] = "ok"
timing = {}
for site in ("twinqa.scene.readback", "PROTOTYPE blender_runner.run"):
    runs = [outcome(SITES[site])[1] for _ in range(5)]
    timing[site] = {"median_s": statistics.median(runs), "runs": runs}
cmds = {"prototype": blender_runner.command("blender", "x.py")}
print(json.dumps({"matrix": matrix, "timing_ok_mode": timing, "prototype_cmd": cmds}, indent=1))
