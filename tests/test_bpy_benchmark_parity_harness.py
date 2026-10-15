"""Offline checks for the synthetic bpy parity harness. No Blender. delivery_passed=false."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB_PATH = ROOT / "experiments/bpy-benchmark-parity/parity_lib.py"


def load_lib():
    spec = importlib.util.spec_from_file_location("bpy_benchmark_parity_lib", LIB_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def benchmark_hashes():
    lib = load_lib()
    found = {}
    for bench in lib.MODELS.values():
        for name in ("spec.json", "object.json"):
            path = ROOT / "benchmark" / bench / name
            found[f"{bench}/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def test_comparator_thresholds_and_exclusions():
    lib = load_lib()
    origin = {"vertices": [[0.0, 0.0, 0.0]], "material_ids": [1]}

    shifted = {"vertices": [[2e-5, 0.0, 0.0]], "material_ids": [1]}
    failed = lib.verdict(lib.diff(origin, shifted))
    assert failed["ok"] is False
    assert failed["max"]["geom"] == pytest.approx(2e-5)
    assert failed["over"]

    within = {"vertices": [[1.72e-6, 0.0, 0.0]], "material_ids": [1]}
    passed = lib.verdict(lib.diff(origin, within))
    assert passed["ok"] is True
    assert passed["max"]["geom"] == pytest.approx(1.72e-6)

    plus_one = {"vertices": [[0.0, 0.0, 0.0]], "material_ids": [2]}
    material = lib.verdict(lib.diff(origin, plus_one))
    assert material["ok"] is False
    assert material["n_discrete"] == 1

    left = {"source": "engine", "sha256": "aaa", "meshes": [
        {"name": "b", "vertices": [[0.0, 0.0, 0.0]]},
        {"name": "a", "vertices": [[1.0, 0.0, 0.0]]},
    ]}
    right = {"source": "other-lane", "sha256": "zzz", "meshes": [
        {"name": "a", "vertices": [[1.0, 0.0, 0.0]]},
        {"name": "b", "vertices": [[0.0, 0.0, 0.0]]},
    ]}
    assert lib.verdict(lib.diff(lib.norm(left), lib.norm(right)))["ok"] is True


def _assert_non_finite(lib, left, right, path):
    result = lib.verdict(lib.diff(left, right))
    assert result["ok"] is False
    assert result["over"] == []
    assert any(path in item and "non-finite" in item for item in result["discrete"])


def test_non_finite_numbers_fail_closed():
    lib = load_lib()
    nan = float("nan")
    pos = float("inf")
    neg = float("-inf")
    origin = {"vertices": [[0.0, 0.0, 0.0]]}

    _assert_non_finite(lib, origin, {"vertices": [[nan, 0.0, 0.0]]}, ".vertices[0][0]")
    _assert_non_finite(lib, {"vertices": [[nan, 0.0, 0.0]]}, origin, ".vertices[0][0]")
    _assert_non_finite(lib, {"vertices": [[nan, 0.0, 0.0]]}, {"vertices": [[nan, 0.0, 0.0]]}, ".vertices[0][0]")
    _assert_non_finite(lib, {"vertices": [[pos, 0.0, 0.0]]}, {"vertices": [[pos, 0.0, 0.0]]}, ".vertices[0][0]")
    _assert_non_finite(lib, {"vertices": [[neg, 0.0, 0.0]]}, {"vertices": [[pos, 0.0, 0.0]]}, ".vertices[0][0]")
    _assert_non_finite(lib, origin, {"vertices": [[pos, 0.0, 0.0]]}, ".vertices[0][0]")

    meshes = {"meshes": [{"vertices": [[0.0, 0.0, 0.0]]}]}
    meshes_nan = {"meshes": [{"vertices": [[nan, 0.0, 0.0]]}]}
    _assert_non_finite(lib, meshes, meshes_nan, ".meshes[0].vertices[0][0]")

    located = {"meshes": [{"location": [0.0, 0.0, 0.0]}]}
    located_nan = {"meshes": [{"location": [nan, 0.0, 0.0]}]}
    _assert_non_finite(lib, located, located_nan, ".meshes[0].location[0]")

    assert lib.verdict(lib.diff(origin, {"vertices": [[0.0, 0.0, 0.0]]}))["ok"] is True
    within = lib.verdict(lib.diff(origin, {"vertices": [[1e-6, 0.0, 0.0]]}))
    assert within["ok"] is True
    assert within["over"] == []
    outside = lib.verdict(lib.diff(origin, {"vertices": [[2e-5, 0.0, 0.0]]}))
    assert outside["ok"] is False
    assert outside["over"]

    poisoned = lib.verdict({"max": {"geom": nan}, "discrete": []})
    assert poisoned["ok"] is False
    assert poisoned["over"]


def test_lane_cmd_and_resolve_lanes(monkeypatch):
    lib = load_lib()
    exe = lib.lane_cmd("exe", "blender.exe", "python.exe", "script.py", ["a", "b"])
    assert exe == ["blender.exe", "--background", "--factory-startup", "--disable-autoexec",
                   "--python-exit-code", "1", "--python", "script.py", "--", "a", "b"]
    assert lib.lane_cmd("whl", "blender.exe", "python.exe", "script.py", ["a"]) == [
        "python.exe", "script.py", "--", "a"]
    with pytest.raises(ValueError):
        lib.lane_cmd("other", "blender.exe", "python.exe", "script.py", [])

    monkeypatch.delenv("DT_BLENDER", raising=False)
    monkeypatch.delenv("DT_BPY_PYTHON", raising=False)
    assert lib.resolve_lanes() == (lib.DEFAULT_BLENDER, None)
    monkeypatch.setenv("DT_BLENDER", "env-blender")
    monkeypatch.setenv("DT_BPY_PYTHON", "env-wheel")
    assert lib.resolve_lanes() == ("env-blender", "env-wheel")
    assert lib.resolve_lanes("arg-blender", "arg-wheel") == ("arg-blender", "arg-wheel")


def test_build_dumps_matches_benchmark_counts_and_leaves_inputs(tmp_path):
    lib = load_lib()
    before = benchmark_hashes()
    info = lib.build_dumps(tmp_path / "common")
    assert lib.DELIVERY_PASSED is False
    assert info["triangles"] == {"B01": 282, "B02": 472, "B02t": 648}
    assert info["hashes"] == before
    assert benchmark_hashes() == before
    written = json.loads((tmp_path / "common" / "input-hashes.json").read_text(encoding="utf-8"))
    assert written == before
    for key in lib.MODELS:
        dump = json.loads((tmp_path / "common" / f"{key}-dump.json").read_text(encoding="utf-8"))
        assert len(dump["meshes"]) == 1
        assert len(dump["helpers"]) == 3
        assert all(helper["name"].startswith("LEVEL_") for helper in dump["helpers"])


def test_run_matrix_schedules_models_and_uv_fixture(tmp_path):
    lib = load_lib()
    calls = []

    def runner(cmd, **kwargs):
        assert kwargs["timeout"] == 300
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="synthetic\n", stderr="")

    runs = lib.run_matrix(tmp_path, "BLENDER", "WHEEL", reps=1, runner=runner)
    assert len(calls) == 48
    assert len(runs) == 48
    assert json.loads((tmp_path / "runs.json").read_text(encoding="utf-8"))[0]["exit"] == 0

    def script_name(cmd):
        if "--python" in cmd:
            return Path(cmd[cmd.index("--python") + 1]).name
        return Path(cmd[1]).name

    counts = {}
    for cmd in calls:
        counts[script_name(cmd)] = counts.get(script_name(cmd), 0) + 1
    assert counts == {
        "export_mesh_blender.py": 6,
        "make_uv_fixture.py": 2,
        "fbx_readback.py": 16,
        "measure_spec_blender.py": 24,
    }
    assert sum(cmd[0] == "BLENDER" for cmd in calls) == 24
    assert sum(cmd[0] == "WHEEL" for cmd in calls) == 24
    assert all("job" in row for row in runs)
    expected_ids = [job["job"] for job in lib.expected_jobs(tmp_path, 1)]
    assert [row["job"] for row in runs] == expected_ids
    assert set(row["job"] for row in runs) == set(expected_ids)
    with pytest.raises(ValueError):
        lib.run_matrix(tmp_path / "missing-wheel", "BLENDER", None, reps=1, runner=runner)


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _plant(work, view, readback, uv_measure):
    """Synthetic rep1/rep2 files. Model measures are the engine view; UV carries expected tiles."""
    for rep in (1, 2):
        for exporter in ("exe", "whl"):
            slot = work / f"rep{rep}" / "B01" / exporter
            (slot / "model.blend").parent.mkdir(parents=True, exist_ok=True)
            (slot / "model.blend").write_bytes(b"synthetic-blend")
            (slot / "model.fbx").write_bytes(b"synthetic-fbx")
            _write(slot / "ms-blend.json", view)
            _write(slot / "ms-fbx-exe.json", view)
            _write(slot / "ms-fbx-whl.json", view)
            for reader in ("exe", "whl"):
                payload = dict(readback)
                payload["source"] = f"synthetic-{rep}-{exporter}-{reader}"
                payload["sha256"] = payload["source"]
                if reader == "whl":
                    payload["other_objects"] = list(reversed(readback["other_objects"]))
                _write(slot / f"rb-{reader}.json", payload)
            uv = work / f"rep{rep}" / "UV" / exporter
            (uv / "model.blend").parent.mkdir(parents=True, exist_ok=True)
            (uv / "model.blend").write_bytes(b"synthetic-uv-blend")
            (uv / "model.fbx").write_bytes(b"synthetic-uv-fbx")
            _write(uv / "ms-blend.json", uv_measure)
            _write(uv / "ms-fbx-exe.json", uv_measure)
            _write(uv / "ms-fbx-whl.json", uv_measure)
            for reader in ("exe", "whl"):
                payload = dict(readback)
                payload["source"] = f"synthetic-uv-{rep}-{exporter}-{reader}"
                payload["sha256"] = payload["source"]
                _write(uv / f"rb-{reader}.json", payload)
    lib = load_lib()
    records = []
    for job in lib.expected_jobs(work, (1, 2), ("B01",)):
        records.append({"lane": job["lane"], "script": Path(job["script"]).name,
                        "args": [str(arg) for arg in job["args"]], "exit": 0, "job": job["job"]})
    _write(work / "runs.json", records)


def test_compare_on_synthetic_b01_matrix(tmp_path):
    lib = load_lib()
    lib.build_dumps(tmp_path / "common")
    dump = json.loads((tmp_path / "common" / "B01-dump.json").read_text(encoding="utf-8"))
    view = lib.engine_view(dump)
    readback = {
        "readback_ok": True,
        "source": "synthetic",
        "sha256": "synthetic",
        "meshes": [{"name": "body", "polygons": 1, "location": [0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0], "rotation_euler_deg": [0.0, 0.0, 0.0],
                    "bounds_m": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]}],
        "other_objects": [{"name": "LEVEL_1", "type": "EMPTY"}, {"name": "LEVEL_0", "type": "EMPTY"}],
    }
    uv_measure = {
        "source": "synthetic-uv-fixture",
        "sha256": "synthetic",
        "meshes": [{"name": "UV_FIXTURE",
                    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]],
                    "triangles": [[0, 1, 2]],
                    "material_ids": [1],
                    "polygon_sizes": [4, 4, 4, 4],
                    "udim_tiles": list(lib.UV_EXPECTED_TILES)}],
        "helpers": [],
    }
    _plant(tmp_path, view, readback, uv_measure)
    result = lib.compare(tmp_path, models=("B01",))
    assert result["ok"] is True
    assert result["completion_fail"] == []
    assert json.loads((tmp_path / "compare.json").read_text(encoding="utf-8"))["ok"] is True
    for bucket in result["summary"].values():
        assert set(bucket) == {"n", "fail", "max"}
        assert bucket["fail"] == 0

    target = tmp_path / "rep1" / "B01" / "whl" / "ms-fbx-whl.json"
    original = target.read_text(encoding="utf-8")
    measured = json.loads(original)
    measured["meshes"][0]["vertices"][0][0] += 2e-5
    target.write_text(json.dumps(measured), encoding="utf-8")
    shifted = lib.compare(tmp_path, models=("B01",))
    assert shifted["ok"] is False
    failed = {row["check"] for row in shifted["rows"] if not row["ok"]}
    assert "fbx measure vs exe/exe" in failed
    target.write_text(original, encoding="utf-8")

    measured = json.loads(original)
    measured["meshes"][0]["vertices"][0][0] = float("nan")
    target.write_text(json.dumps(measured), encoding="utf-8")
    poisoned = lib.compare(tmp_path, models=("B01",))
    assert poisoned["ok"] is False
    assert any(not row["ok"] for row in poisoned["rows"])
    target.write_text(original, encoding="utf-8")

    runs = json.loads((tmp_path / "runs.json").read_text(encoding="utf-8"))
    runs[0]["exit"] = 1
    (tmp_path / "runs.json").write_text(json.dumps(runs), encoding="utf-8")
    stopped = lib.compare(tmp_path, models=("B01",))
    assert stopped["completion_fail"]
    assert stopped["ok"] is False


def _record(job, exit_code=0):
    return {"lane": job["lane"], "script": Path(job["script"]).name,
            "args": [str(arg) for arg in job["args"]], "exit": exit_code, "job": job["job"]}


def test_compare_requires_every_expected_job_once(tmp_path):
    lib = load_lib()
    lib.build_dumps(tmp_path / "common")
    dump = json.loads((tmp_path / "common" / "B01-dump.json").read_text(encoding="utf-8"))
    view = lib.engine_view(dump)
    readback = {
        "readback_ok": True,
        "source": "synthetic",
        "sha256": "synthetic",
        "meshes": [{"name": "body", "polygons": 1, "location": [0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0], "rotation_euler_deg": [0.0, 0.0, 0.0],
                    "bounds_m": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]}],
        "other_objects": [{"name": "LEVEL_1", "type": "EMPTY"}, {"name": "LEVEL_0", "type": "EMPTY"}],
    }
    uv_measure = {
        "source": "synthetic-uv-fixture",
        "sha256": "synthetic",
        "meshes": [{"name": "UV_FIXTURE",
                    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]],
                    "triangles": [[0, 1, 2]],
                    "material_ids": [1],
                    "polygon_sizes": [4, 4, 4, 4],
                    "udim_tiles": list(lib.UV_EXPECTED_TILES)}],
        "helpers": [],
    }
    _plant(tmp_path, view, readback, uv_measure)
    # 2 reps * (B01 + UV) * 2 exporters * (export, blend measure, 2 readers * readback and fbx measure)
    expected = lib.expected_jobs(tmp_path, (1, 2), ("B01",))
    assert len(expected) == 2 * 2 * 2 * (2 + 2 * 2)

    happy = lib.compare(tmp_path, models=("B01",))
    assert happy["ok"] is True
    assert happy["completion_fail"] == []

    _write(tmp_path / "runs.json", [])
    empty = lib.compare(tmp_path, models=("B01",))
    assert empty["ok"] is False
    missing = [row for row in empty["completion_fail"] if "missing_job" in row]
    assert len(missing) == len(expected)
    assert [row["missing_job"] for row in missing] == [job["job"] for job in expected]

    planted = [_record(job) for job in expected]
    removed = planted.pop(3)
    _write(tmp_path / "runs.json", planted)
    one_gone = lib.compare(tmp_path, models=("B01",))
    assert one_gone["ok"] is False
    assert one_gone["completion_fail"] == [{"missing_job": removed["job"]}]

    substituted = [_record(job) for job in expected]
    victim = substituted[5]
    substituted[5] = dict(substituted[0])
    _write(tmp_path / "runs.json", substituted)
    swapped = lib.compare(tmp_path, models=("B01",))
    assert swapped["ok"] is False
    assert {"missing_job": victim["job"]} in swapped["completion_fail"]
    assert {"duplicate_job": substituted[0]["job"], "count": 2} in swapped["completion_fail"]
    assert sum("missing_job" in row for row in swapped["completion_fail"]) == 1
    assert sum("duplicate_job" in row for row in swapped["completion_fail"]) == 1

    extra_source = lib.expected_jobs(tmp_path, (1,), ("B02",))[0]
    _write(tmp_path / "runs.json", [_record(job) for job in expected] + [_record(extra_source)])
    extra = lib.compare(tmp_path, models=("B01",))
    assert extra["ok"] is True
    assert extra["completion_fail"] == []

    _write(tmp_path / "runs.json", {"not": "a list"})
    broken = lib.compare(tmp_path, models=("B01",))
    assert broken["ok"] is False
    assert {"runs_json": "not a list"} in broken["completion_fail"]
