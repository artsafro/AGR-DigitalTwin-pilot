"""Synthetic controls for the report-only #66 runner; no native inputs needed."""
import pytest

from replay import measure, summarize


def test_exercised_target_and_untouched_solid():
    vertices = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    uv = [[0.25, 0.25], [0.5, 0.25], [0.5, 0.5], [0.25, 0.5]]
    solid = [[1 + u, v] for u, v in uv]
    rb = {"meshes": [{"name": "Main", "face_geometry": {
        "vertices": vertices, "polygons": [[0, 1, 2, 3]] * 2, "polygon_uv": [uv, solid],
    }}]}
    result = measure(rb, {1001: 4096, 1002: 256}, {1001})
    assert rb["meshes"][0]["face_geometry"]["polygon_uv"] == [uv, solid]
    assert result["excluded_faces"] == {1002: 1}
    assert result["states"]["clean"]["tiles"][1001]["median"] == 1024
    for state, expected in [("0.75", 768), ("0.50", 512)]:
        row = result["states"][state]["tiles"][1001]
        assert (row["median"], row["changed_faces"], row["changed_loops"]) == (expected, 1, 4)
    with pytest.raises(ValueError, match="not_exercised"):
        measure(rb, {1001: 4096, 1002: 256, 1003: 4096}, {1001, 1003})


def test_same_density_is_refuted_not_inconclusive_after_exercised_series():
    states = {k: {"score": value} for k, value in [("clean", 0.01), ("0.75", 0.25), ("0.50", 0.5)]}
    rows = [{v: {"states": states} for v in ("v007", "v010")} for _ in range(3)]
    result = summarize(rows)
    assert result["hypothesis"] == "refuted"
    assert result["paired_clean_delta"] == {"median": 0.0, "spread": 0.0}
