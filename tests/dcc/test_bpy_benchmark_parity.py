"""Live bpy 5.1.2 wheel vs blender.exe 5.1.2 parity. Skipped unless both lanes are present.

Synthetic benchmark dumps and a synthetic UV fixture. delivery_passed is false.
Select with pytest -m dcc (the default suite excludes this marker).
"""
import importlib.util
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.dcc

ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = ROOT / "experiments/bpy-benchmark-parity/parity_lib.py"
LANE_BITS = ("vs exe/exe", "vs exe blend", "rep2 vs rep1")
REQUIRED = (
    "blend vs engine dump",
    "blend vs exe blend",
    "readback vs exe/exe",
    "fbx measure vs exe/exe",
    "fbx measure vs engine dump",
    "readback rep2 vs rep1",
    "fbx measure rep2 vs rep1",
    "uv blend vs exe blend",
    "uv readback vs exe/exe",
    "uv fbx measure vs exe/exe",
    "uv udim_tiles expected",
)


def load_lib():
    spec = importlib.util.spec_from_file_location("bpy_benchmark_parity_lib_dcc", LIB_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blender_512(text):
    for line in text.splitlines():
        if line == "Blender 5.1.2" or line.startswith("Blender 5.1.2 "):
            return True
    return False


def skip_reason(blender, wheel):
    if not blender or not Path(blender).is_file():
        return "blender.exe 5.1.2 not found (DT_BLENDER or the default Blender 5.1 path)"
    if not wheel or not Path(wheel).is_file():
        return "bpy==5.1.2 interpreter not found (set DT_BPY_PYTHON)"
    try:
        version = subprocess.run([blender, "--version"], capture_output=True, text=True, timeout=120,
                                 encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"blender.exe --version failed: {exc}"
    if version.returncode != 0 or not _blender_512(version.stdout or ""):
        return "blender.exe is not Blender 5.1.2"
    try:
        wheel_version = subprocess.run(
            [wheel, "-c", "import bpy; print(bpy.app.version_string)"],
            capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"bpy interpreter failed: {exc}"
    lines = [line.strip() for line in (wheel_version.stdout or "").splitlines() if line.strip()]
    if wheel_version.returncode != 0 or not lines or lines[-1] != "5.1.2":
        return "DT_BPY_PYTHON is not bpy 5.1.2"
    return None


def test_bpy_wheel_matches_blender_exe_on_benchmarks_and_uv(tmp_path):
    lib = load_lib()
    assert lib.DELIVERY_PASSED is False
    blender, wheel = lib.resolve_lanes()
    reason = skip_reason(blender, wheel)
    if reason:
        pytest.skip(reason)
    lib.build_dumps(tmp_path / "common")
    lib.run_matrix(tmp_path, blender, wheel, reps=2)
    result = lib.compare(tmp_path)
    assert result["completion_fail"] == []
    assert result["ok"] is True
    assert all(row["ok"] for row in result["rows"])
    checks = {row["check"] for row in result["rows"]}
    for name in REQUIRED:
        assert name in checks
    for check, bucket in result["summary"].items():
        assert bucket["fail"] == 0
        assert bucket["max"].get("geom", 0.0) <= 1e-5
        assert bucket["max"].get("locscale", 0.0) <= 1e-6
        assert bucket["max"].get("rot", 0.0) <= 1e-4
        if any(bit in check for bit in LANE_BITS):
            assert bucket["max"].get("geom", 0.0) == 0.0
