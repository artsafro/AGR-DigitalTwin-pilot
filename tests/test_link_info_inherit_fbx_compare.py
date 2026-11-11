"""Synthetic CLI regressions for Q10 diagnostic reports (new-case)."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/research/link_info_inherit_fbx/compare.py"
VERTS = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]


@pytest.mark.parametrize("reader", ["blender", "max_reimport"])
@pytest.mark.parametrize("fault", ["missing", "count"])
def test_cli_preserves_readback_errors(tmp_path, reader, fault):
    """Both readers retain missing/count diagnostics alongside a clean node."""
    for variant in ("raw", "baked"):
        nodes = [{"name": name, "inherit": [1] * 9, "world_verts": VERTS}
                 for name in ("broken", "clean")]
        (tmp_path / f"max_{variant}.json").write_text(json.dumps({"nodes": nodes}))
        for target, filename in (("blender", "blender"), ("max_reimport", "maxreimport")):
            got = []
            for name in ("broken", "clean"):
                if target == reader and name == "broken" and fault == "missing":
                    continue
                verts = VERTS[:2] if target == reader and name == "broken" and fault == "count" else VERTS
                got.append({"name": name, "face_geometry": {"vertices": verts}} if target == "blender"
                           else {"name": name, "world_verts": verts})
            payload = {"meshes" if target == "blender" else "nodes": got}
            (tmp_path / f"{filename}_{variant}.json").write_text(json.dumps(payload))
    run = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    report = json.loads((tmp_path / "compare.json").read_text())
    error = "missing" if fault == "missing" else "vertex count 3 vs 2"
    for rows in report.values():
        assert rows[0][reader] == {"error": error}
        assert "pass" not in rows[0][reader]
        assert rows[1]["blender"]["pass"] is True
        assert rows[1]["max_reimport"]["pass"] is True
    assert run.stdout.count(error) == 2
    assert run.stdout.count("MISMATCH") == 2
    assert run.stdout.count("| match |") == 2
    assert "0.000" in run.stdout
