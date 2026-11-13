"""new-case: synthetic source/model mode-A discrepancy and evidence contracts."""
import copy


def synthetic_bundle():
    """Entirely synthetic, not KPP1 evidence."""
    return {
        "schema": "album-model-audit-input/1",
        "trust_rule": "D271",
        "frame": {"name": "synthetic-local-m", "placement": "synthetic identity"},
        "pdf": [{"id": "level-1", "category": "level", "mark": "roof", "facade": "F1",
                 "position_m": [0, 8], "value": 8.0, "unit": "m", "tolerance": 0.01,
                 "verified": True, "calibrated": False,
                 "evidence": {"path": "synthetic.pdf", "sha256": "a" * 64,
                              "page": 1, "sheet": "synthetic facade", "bbox": [1, 2, 3, 4],
                              "method": "synthetic vector text"}}],
        "models": [{"id": "source", "observations": [
            {"id": "roof-face", "category": "level", "mark": "roof", "facade": "F1",
             "position_m": [0, 8], "value": 8.005, "unit": "m", "verified": True,
             "object_id": "42", "object_name": "synthetic roof",
             "evidence": {"path": "synthetic.fbx", "sha256": "b" * 64,
                          "method": "synthetic measured face", "locator": "face 3"}}]}],
        "match_tolerance_m": 0.1,
    }


def test_synthetic_level_comparison_retains_both_evidences():
    from dt_ai.album.compare import compare
    bundle = synthetic_bundle()
    original = copy.deepcopy(bundle)
    result = compare(bundle)
    assert result["rows"][0]["status"] == "match"
    assert abs(result["rows"][0]["difference"] - 0.005) < 1e-12
    assert result["rows"][0]["pdf"] == bundle["pdf"][0]
    assert result["rows"][0]["model"] == bundle["models"][0]["observations"][0]
    assert result["counts"] == {"match": 1, "mismatch": 0, "needs manual check": 0}
    assert result["passed"] is False  # diagnostic, never delivery approval
    assert bundle == original
