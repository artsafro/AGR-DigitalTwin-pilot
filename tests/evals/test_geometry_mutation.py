"""new-case: independent controls for the seeded synthetic geometry recall evaluator."""
import importlib.util
import json
import copy
import subprocess
import sys

import pytest

import numpy as np
from twinqa.geometry.mesh import from_dump
from pathlib import Path


def evaluator():
    path = Path(__file__).resolve().parents[2] / "tools/evals_geometry_mutation.py"
    assert path.is_file(), "geometry mutation evaluator must exist"
    spec = importlib.util.spec_from_file_location("geometry_mutation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mutants_are_valid_and_single_component():
    ev = evaluator()
    base, mutants = ev.corpus()
    assert set(mutants) == {"moved_opening", "wall_slab_gap", "false_contact", "flipped_normals",
                            "sliver_triangle", "duplicate_faces", "low_density", "polycount"}
    for name, case in mutants.items():
        scene = json.loads(json.dumps(case["scene"], allow_nan=False))
        soup = from_dump(scene)
        assert np.isfinite(soup.vertices).all() and len(soup.triangles) > 0
        assert soup.triangles.min() >= 0 and soup.triangles.max() < len(soup.vertices)
        assert all(len(set(t)) == 3 for t in soup.triangles)
        # Each mutant changes exactly one component (density changes only its UVs).
        changed = [a["name"] for a, b in zip(base["meshes"], scene["meshes"]) if a != b]
        assert changed == ([] if name == "low_density" else [case["target"]])
        assert (scene["uv"] != base["uv"]) == (name == "low_density")
    # Independent geometric witnesses, not mutant labels.
    by = lambda s, n: next(m for m in s["meshes"] if m["name"] == n)
    moved = np.array(by(mutants["moved_opening"]["scene"], "opening")["vertices"])
    assert np.allclose(moved - by(base, "opening")["vertices"], [0.3, 0, 0])
    gap = by(mutants["wall_slab_gap"]["scene"], "wall")
    assert np.isclose(min(v[2] for v in gap["vertices"]) - .2, .005)
    contact = by(mutants["false_contact"]["scene"], "contact_b")
    assert {v[2] for v in contact["vertices"]} == {0}
    original = by(base, "normal_target")
    flipped = by(mutants["flipped_normals"]["scene"], "normal_target")
    assert flipped["triangles"][-2:] == [t[::-1] for t in original["triangles"][-2:]]
    sliver = by(mutants["sliver_triangle"]["scene"], "normal_target")
    corners = np.array(sliver["vertices"])[sliver["triangles"]]
    areas = np.linalg.norm(np.cross(corners[:,1]-corners[:,0], corners[:,2]-corners[:,0]), axis=1)/2
    assert 0 < min(areas) < 1e-8
    dup = by(mutants["duplicate_faces"]["scene"], "normal_target")
    assert np.allclose(np.array(dup["vertices"][-3:]) - np.array(original["vertices"])[original["triangles"][-1]], [0,0,.001])
    density = mutants["low_density"]["scene"]
    assert density["uv"]["density"][1][0] * 4096 < 512
    assert len(by(mutants["polycount"]["scene"], "budget")["triangles"]) > 150000


def test_detection_table():
    ev = evaluator()
    report = ev.evaluate()
    assert len(report["defects"]) == 8
    assert report["false_positives"] == 0
    assert report["summary"]["total"] == 8
    assert set(report["by_checker"]) == {"opening_planes", "mesh_joint", "clearance", "orientation",
        "horizontal_faces", "topology", "mesh_target", "clearance_target", "uv_density_adapter",
        "triangle_budget", "complexity"}
    for row in report["defects"]:
        assert row["expected"] == list(ev.CASES[row["defect"]][1])
        assert [r["checker"] for r in row["checks"]] == row["expected"]
        assert row["caught"] == any(r["status"] == "fail" for r in row["checks"])
        assert all(r["status"] in ("pass", "fail", "not_measured") for r in row["checks"])
    # Required known positive controls cannot become no-op/mocked checkers.
    by = {r["defect"]: r for r in report["defects"]}
    for name in ("moved_opening", "false_contact", "flipped_normals", "polycount"):
        assert by[name]["caught"]
    assert report["summary"]["caught"] == sum(r["caught"] for r in report["defects"])


@pytest.mark.parametrize("kind", ["empty", "partial", "unsupported", "nan", "inf", "index", "duplicate",
    "material", "uv", "texture", "triangle_partial", "polygon_sizes"])
def test_invalid_mesh_rejected(kind):
    ev = evaluator()
    scene = ev.base_scene()
    m = scene["meshes"][0]
    if kind == "empty": scene["meshes"] = []
    elif kind == "partial": del m["triangles"]
    elif kind == "unsupported": scene["units"] = "cm"
    elif kind in ("nan", "inf"): m["vertices"][0][0] = float(kind)
    elif kind == "index": m["triangles"][0][0] = -1
    elif kind == "duplicate": scene["meshes"].append(copy.deepcopy(m))
    elif kind == "material": m["material_ids"][0] = 999
    elif kind == "uv": scene["uv"]["unknown-material"] = [[0,0]]
    elif kind == "texture": scene["texture_size"] = 0
    elif kind == "triangle_partial": m["triangles"][0].pop()
    elif kind == "polygon_sizes": m["polygon_sizes"] = []
    with pytest.raises(ValueError):
        ev.run_checker("orientation", scene)


@pytest.mark.parametrize("seed", [0,1,2,3,4,461])
def test_repeat_reset_order(seed, monkeypatch):
    ev = evaluator()
    first = ev.evaluate(seed)
    _, mutants = ev.corpus(seed)
    for case in mutants.values():
        ev.validate_scene(json.loads(json.dumps(case["scene"], allow_nan=False)))
    # Mutating a returned report or a previous scene cannot leak into the next run.
    mutants["moved_opening"]["scene"]["meshes"].clear()
    again = ev.evaluate(seed)
    assert first == again
    first["base"].clear()
    monkeypatch.setattr(ev, "CASES", dict(reversed(list(ev.CASES.items()))))
    assert ev.evaluate(seed) == again
    assert len(again["corpus_sha256"]) == 64


def test_cli_and_markdown():
    ev = evaluator()
    assert ev.__file__ is not None
    script = Path(ev.__file__).resolve()
    before = script.read_bytes()
    result = subprocess.run([sys.executable, str(script), "--json"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == ev.evaluate()
    assert "runtime_seconds=" in result.stderr
    md = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert md.returncode == 0
    assert md.stdout == ev.markdown(report) + "\n"
    assert "| sliver_triangle |" in md.stdout and "MISSED" in md.stdout
    bad = subprocess.run([sys.executable, str(script), "--output", str(script)], capture_output=True, text=True)
    assert bad.returncode != 0 and bad.stdout == ""
    assert script.read_bytes() == before


@pytest.mark.parametrize("status, expected", [("fail",True), ("pass",False), ("not_measured",False)])
def test_status_accounting(status, expected):
    ev = evaluator()
    assert ev.is_caught({"status": status}) is expected
    for bad in ("error", "unknown", "review", "not_run", None):
        with pytest.raises(ValueError): ev.is_caught({"status": bad})


def test_boundary_controls():
    ev = evaluator()
    scene = ev.base_scene()
    scene["uv"]["density"] = [[0,0], [.125,0], [.125,.125], [0,.125]]
    assert ev.run_checker("uv_density_adapter", scene)["status"] == "pass"
    scene["uv"]["density"][1][0] -= 1e-6
    assert ev.run_checker("uv_density_adapter", scene)["status"] == "fail"
    # Native inclusive profile cap, without allocating a huge surface.
    from twinqa.geometry import checks
    from types import SimpleNamespace
    for count, expected in [(149999,"pass"), (150000,"pass"), (150001,"fail")]:
        assert checks.check_budget(SimpleNamespace(triangles=range(count)), {"triangles_max": 150000})["status"] == expected
    for seed in (None, True, 1.5, float("nan"), float("inf"), "461"):
        with pytest.raises(ValueError): ev.evaluate(seed)
    with pytest.raises(ValueError, match="unsupported checker"):
        ev.run_checker("missing", ev.base_scene())


def test_fail_closed_checker_errors_and_state_changes(tmp_path, monkeypatch):
    ev = evaluator()
    real = ev.run_checker
    # Dirty clean-control status must abort, never yield zero false positives.
    monkeypatch.setattr(ev, "run_checker", lambda *args: {"status": "not_measured"})
    with pytest.raises(ValueError, match="base is not clean"): ev.evaluate()
    monkeypatch.setattr(ev, "run_checker", real)
    probe = tmp_path / "config.json"
    probe.write_text("before")
    monkeypatch.setattr(ev, "INPUTS", (*ev.INPUTS, str(probe)))
    def changing(name, scene):
        probe.write_text("after")
        return real(name, scene)
    monkeypatch.setattr(ev, "run_checker", changing)
    with pytest.raises(ValueError, match="inputs changed"): ev.evaluate()
    monkeypatch.setattr(ev, "run_checker", real)
    assert ev.evaluate()["false_positives"] == 0


def test_scope_disposition():
    ev = evaluator()
    report = ev.evaluate()
    all_names = {m["name"] for m in ev.base_scene()["meshes"]}
    for adapter in report["adapters"].values():
        assert adapter["function"].startswith("twinqa.")
        assert set(adapter["scope"]) | set(adapter["excluded"]) == all_names
        assert not set(adapter["scope"]) & set(adapter["excluded"])
        assert adapter["exclusion_reason"]
    assert report["by_function"]["twinqa.geometry.checks.check_mesh"] == {"caught": 2, "total": 3}


def test_committed_report_matches():
    ev = evaluator()
    saved = (Path(__file__).resolve().parents[2] / "docs/evals/geometry_mutation_2026-10-21.md").read_text(encoding="utf-8")
    assert saved.startswith(ev.markdown(ev.evaluate()) + "\n")


def test_base_is_clean():
    ev = evaluator()
    report = ev.evaluate()
    assert report["synthetic"] is True
    assert report["base"]
    assert all(row["status"] == "pass" for row in report["base"]), report["base"]
