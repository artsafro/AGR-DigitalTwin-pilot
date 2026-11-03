"""new-case: diff logic for a second FBX reader (legacy vs wm.fbx_import).

Guarantees probed here, without Blender:
- identical snapshots -> diff = 0
- a swapped material id, a missing UV layer, or a renamed node is caught
- empty, partial, NaN and inf input is an error, never a pass
- an output path that resolves to an input exits nonzero and writes nothing
- a run does not delete an input
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "research" / "fbx_reader_compare.py"


def load():
    spec = importlib.util.spec_from_file_location("fbx_reader_compare", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snap(name="Body", triangles=2, material_ids=(0, 1), uv_layers=1, uv_bbox=(0.0, 0.0, 1.0, 1.0),
         images=()):
    return {
        "objects": [{
            "name": name,
            "triangles": triangles,
            "material_ids": list(material_ids),
            "uv_layer_count": uv_layers,
            "uv_bbox": None if uv_bbox is None else list(uv_bbox),
        }],
        "embedded_images": [dict(item) for item in images],
    }


def test_module_docstring_marks_new_case():
    module = load()
    assert module.__doc__ and "new-case" in module.__doc__


def test_generated_identical_snapshots_diff_zero():
    module = load()
    image = {"name": "atlas", "sha256": "ab" * 32, "size": [2, 2]}
    for index in range(6):
        ids = tuple((index + face) % 3 for face in range(index + 1))
        bbox = None if index % 2 else (0.0, float(index), 1.0, float(index) + 0.5)
        layers = 0 if bbox is None else 1
        left = snap(name=f"Part{index}", triangles=index + 1, material_ids=ids,
                    uv_layers=layers, uv_bbox=bbox, images=(image,) if index else ())
        right = json.loads(json.dumps(left))
        result = module.diff_snapshots(left, right)
        assert result["diff"] == 0
        assert result["differences"] == []


def test_generated_planted_defects_are_caught():
    module = load()
    base = snap(images=({"name": "atlas", "sha256": "cd" * 32, "size": [4, 4]},))
    swapped = snap(material_ids=(1, 0), images=({"name": "atlas", "sha256": "cd" * 32, "size": [4, 4]},))
    missing_uv = snap(uv_layers=0, uv_bbox=None, images=({"name": "atlas", "sha256": "cd" * 32, "size": [4, 4]},))
    renamed = snap(name="BodyRenamed", images=({"name": "atlas", "sha256": "cd" * 32, "size": [4, 4]},))
    cases = {
        "material_ids": swapped,
        "uv_layer_count": missing_uv,
        "name": renamed,
    }
    for kind, mutant in cases.items():
        result = module.diff_snapshots(base, mutant)
        assert result["diff"] > 0
        assert kind in {item["kind"] for item in result["differences"]}


@pytest.mark.parametrize("mode", ["empty", "partial", "nan", "inf"])
def test_generated_bad_snapshot_errors(mode):
    module = load()
    good = snap()
    bad = json.loads(json.dumps(good))
    if mode == "empty":
        bad["objects"] = []
    elif mode == "partial":
        del bad["objects"][0]["uv_bbox"]
    elif mode == "nan":
        bad["objects"][0]["uv_bbox"][0] = float("nan")
    elif mode == "inf":
        bad["objects"][0]["uv_bbox"][2] = float("inf")
    with pytest.raises(module.SnapshotError):
        module.diff_snapshots(good, bad)
    with pytest.raises(module.SnapshotError):
        module.diff_snapshots(bad, good)


def run_diff(left, right, output):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "diff", "--left", str(left), "--right", str(right), "--output", str(output)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_generated_output_alias_of_input_writes_nothing(tmp_path):
    payload = snap()
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text(json.dumps(payload), encoding="utf-8")
    right.write_text(json.dumps(payload), encoding="utf-8")
    before = left.read_bytes()
    direct = run_diff(left, right, left)
    assert direct.returncode != 0
    assert left.read_bytes() == before
    relative = run_diff(left, right, tmp_path / "." / "left.json")
    assert relative.returncode != 0
    assert left.read_bytes() == before
    alias = tmp_path / "alias.json"
    alias.hardlink_to(left)
    linked = run_diff(left, right, alias)
    assert linked.returncode != 0
    assert left.read_bytes() == before
    assert not (tmp_path / "out.json").exists()


def test_generated_bad_file_and_success_keep_inputs(tmp_path):
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text("{", encoding="utf-8")
    right.write_text(json.dumps(snap()), encoding="utf-8")
    output = tmp_path / "out.json"
    failed = run_diff(left, right, output)
    assert failed.returncode != 0
    assert not output.exists()
    assert left.read_text(encoding="utf-8") == "{"
    assert right.exists()
    left.write_text(json.dumps(snap()), encoding="utf-8")
    right.write_text("NaN", encoding="utf-8")
    failed_nan = run_diff(left, right, output)
    assert failed_nan.returncode != 0
    assert not output.exists()
    right.write_text(json.dumps(snap()), encoding="utf-8")
    ok = run_diff(left, right, output)
    assert ok.returncode == 0, ok.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["diff"] == 0
    assert left.exists() and right.exists()
