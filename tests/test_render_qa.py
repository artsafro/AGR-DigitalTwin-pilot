"""new-case: public render-QA configuration and numerical verdict contracts."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_checker():
    spec = importlib.util.spec_from_file_location("render_qa", ROOT / "tools/qa/render_qa.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_numeric_verdicts():
    qa = load_checker()
    config = qa.validate_config({"targets": ["Cube"], "cameras": ["Camera"],
                                 "ground_resting": ["Cube"], "ground_objects": ["Ground"]})
    assert config["thresholds"]["crop_margin"] == 0.02
    assert config["thresholds"]["minimum_coverage"] == 0.05
    assert config["thresholds"]["floating_m"] == 0.01
    good = {"bbox": [0.2, 0.2, 0.8, 0.8], "depth": [1, 3],
            "coverage": 0.36, "visible_faces": 2, "ground_gap_m": 0.0}
    assert qa.verdicts("Cube", "Camera", good, config["thresholds"]) == []
    for key, value, expected in [("bbox", [-0.03, 0.2, 0.8, 0.8], "cropped"),
                                  ("coverage", 0.04, "empty"),
                                  ("visible_faces", 0, "empty"),
                                  ("ground_gap_m", 0.1, "floating")]:
        failures = qa.verdicts("Cube", "Camera", {**good, key: value}, config["thresholds"])
        assert [f["code"] for f in failures] == [expected]
        assert all(f["object"] == "Cube" and f["frame"] == "Camera" for f in failures)
