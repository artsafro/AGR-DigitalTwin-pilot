"""#1416: fail-closed probes for the KPP1 Ground budget xView diff helper."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "xview_new_pairs", Path(__file__).resolve().parents[2] / "jobs/KPP1/ground-budget-1416/xview_new_pairs.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def report(path, parts):
    path.write_text(json.dumps({"parts": [
        {"part": n, "location": [0, 0, 0], "face_pairs": [{"centre": c} for c in cs]} for n, cs in parts.items()]}))
    return str(path)


def test_identical_reports_have_no_new_pairs(tmp_path):
    b = report(tmp_path / "b.json", {"Flora": [[1, 2, 3]], "Ground": []})
    a = report(tmp_path / "a.json", {"Flora": [[1, 2, 3.0005]], "Ground": []})
    assert mod.main([b, a, str(tmp_path / "p.json")]) == 0
    assert not (tmp_path / "p.json").exists()


def test_new_pair_writes_protect_points(tmp_path):
    b = report(tmp_path / "b.json", {"Flora": [[1, 2, 3]]})
    a = report(tmp_path / "a.json", {"Flora": [[1, 2, 3], [5, 5, 5]]})
    assert mod.main([b, a, str(tmp_path / "p.json"), "0.3"]) == 1
    data = json.loads((tmp_path / "p.json").read_text())
    assert data["points"] == [[5, 5, 5]] and data["radius_m"] == 0.3


@pytest.mark.parametrize("radius", ["0", "-1", "nan", "inf"])
def test_bad_radius_fails_closed(tmp_path, radius):
    b = report(tmp_path / "b.json", {"Flora": []})
    a = report(tmp_path / "a.json", {"Flora": [[5, 5, 5]]})
    assert mod.main([b, a, str(tmp_path / "p.json"), radius]) == 2
    assert not (tmp_path / "p.json").exists()


def test_output_alias_or_existing_fails_closed(tmp_path):
    b = report(tmp_path / "b.json", {"Flora": []})
    a = report(tmp_path / "a.json", {"Flora": [[5, 5, 5]]})
    before = Path(b).read_bytes()
    assert mod.main([b, a, b]) == 2
    assert Path(b).read_bytes() == before
    assert mod.main([b, a, a]) == 2


def test_part_set_mismatch_fails_closed(tmp_path):
    b = report(tmp_path / "b.json", {"Flora": []})
    a = report(tmp_path / "a.json", {"Flora": [], "Extra": []})
    assert mod.main([b, a, str(tmp_path / "p.json")]) == 2


def test_missing_args(tmp_path):
    assert mod.main([]) == 2
