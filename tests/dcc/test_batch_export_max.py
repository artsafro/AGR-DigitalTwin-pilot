"""Headless 3ds Max check of the shared export benchmark. Not part of the default suite."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path():
    """Writable temp dir. The machine's pytest-of-<user> folder currently denies listing."""
    path = Path(tempfile.mkdtemp(prefix="agr-batch-export-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

pytestmark = pytest.mark.dcc

ROOT = Path(__file__).resolve().parents[2]
MAX_BATCH = Path(r"C:/Program Files/Autodesk/3ds Max 2026/3dsmaxbatch.exe")
DCC_BATCH = Path(r"C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py")
JOB = ROOT / "tools" / "export" / "benchmark_export_max.py"


@pytest.mark.skipif(
    not MAX_BATCH.exists() or not DCC_BATCH.exists(),
    reason="3ds Max 2026 or dcc_batch.py is not installed",
)
def test_benchmark_one_pass_and_fbx(tmp_path):
    out = tmp_path / "bench-v001"
    env = os.environ.copy()
    env["AGR_BENCH_OUT"] = str(out)
    env["AGR_BENCH_SIZES"] = "4"
    env["AGR_BENCH_ROUTES"] = "c_one_pass,b_fbx"
    env["AGR_BENCH_ROUTE_BUDGET_S"] = "240"
    completed = subprocess.run(
        [
            sys.executable,
            str(DCC_BATCH),
            "max",
            "--file",
            str(JOB),
            "--timeout",
            "900",
            "--out",
            str(tmp_path / "dcc.json"),
        ],
        env=env,
        check=False,
    )
    bench_path = out / "benchmark.json"
    assert bench_path.is_file(), completed.returncode
    bench = json.loads(bench_path.read_text(encoding="utf-8"))
    for route in ("c_one_pass", "b_fbx"):
        rows = [row for row in bench["rows"] if row["route"] == route]
        assert rows, route
        assert all(row["ok"] is True for row in rows)
