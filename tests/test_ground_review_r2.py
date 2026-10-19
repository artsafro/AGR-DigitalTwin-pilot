"""Regression table of PR #308 review round 2 (#295): the 5-20 mm normal-gap band is a gate at BOTH bounds.

| # | failing input (review round 2, head 912c6d4) | expected output |
|---|----------------------------------------------|-----------------|
| 1 | real paving_ground_inputs_v4.json --snap 0.003: 18 corner samples up to 36.924 mm and 6 centroids up to 26.623 mm over 20 mm; exit 0, both masters written, all 11 gates true | gate ``normal_gap_max_20mm`` false, exit 1, no ``ground_master_*.json`` written, report lists the over-band faces and vertices |
| 1s | synthetic: a lawn plate across a 0.5 m 6:1 bank (|n_z| 0.164) between flat terraces, where no continuous Z-only offset is in 5-20 mm on both faces | same as 1 |
| c | in-band control: the flat 8 x 8 m site (and the gate fed an in-band report) | exit 0, every gate true, both masters written |
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import shapely
from shapely.geometry import box, mapping

ROOT = Path(__file__).resolve().parents[1]


def _bg():
    spec = importlib.util.spec_from_file_location("build_ground_vatutino_r2", ROOT / "jobs/VATUTINO-SITE/build_ground.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_ground_vatutino_r2"] = mod
    spec.loader.exec_module(mod)
    return mod


def _adapter(steep: bool) -> dict:
    b = box(0, 0, 16, 8)
    cov = {"tile_light": {"geometry": mapping(shapely.MultiPolygon([b]))}}
    xs = (-1, 8, 8.5, 17)
    if steep:  # a lawn plate across a 0.5 m wide 6:1 bank (|n_z| 0.164) between two flat terraces
        cov["lawn_rolled"] = {"geometry": mapping(shapely.MultiPolygon([box(5, 2, 11, 6)]))}
        z = lambda x: 100.0 + 6.0 * min(max(x - 8.0, 0.0), 0.5)  # noqa: E731
    else:
        z = lambda x: 100.0 + 0.01 * x  # noqa: E731
    return {"boundary": mapping(b), "coverings": cov, "base_covering": "tile_light",
            "elevations": [{"x": x, "y": y, "z": z(x), "source": "point"} for x in xs for y in (-1, 9)]}


def _run(tmp_path, steep: bool):
    src = tmp_path / "a.json"
    src.write_text(json.dumps(_adapter(steep)), encoding="utf-8")
    out = tmp_path / "out"
    code = _bg().main([str(src), "--out", str(out)])
    return code, out, json.loads((out / "ground_report.json").read_text(encoding="utf-8"))


def test_r2_over_20mm_fails_closed_without_deliverables(tmp_path):
    code, out, rep = _run(tmp_path, steep=True)
    sg = rep["stack_gaps"]
    assert sg["normal_gap_vertices_above"] > 0 and sg["normal_gap_vertex_max_mm"] > 20.0  # the defect exists
    assert code == 1  # head 912c6d4: exit 0 and both masters written
    assert not list(out.glob("ground_master_*.json"))
    assert rep["gates"]["normal_gap_min_5mm"]["pass"]  # the lower bound is met: only the upper one fails
    gate = rep["gates"]["normal_gap_max_20mm"]
    assert gate["pass"] is False and gate["value"]["over_gap_max_vertices"]


def test_r2_in_band_control_writes_and_passes(tmp_path):
    code, out, rep = _run(tmp_path, steep=False)
    assert code == 0 and all(g["pass"] for g in rep["gates"].values())
    assert rep["gates"]["normal_gap_max_20mm"]["pass"]
    assert (out / "ground_master_vpm.json").exists() and (out / "ground_master_npm.json").exists()


def test_r2_gate_reads_both_upper_counters(tmp_path):
    """The gate fails on either counter alone (a centroid or a corner sample over 20 mm) and passes at 0 / 0."""
    _, _, rep = _run(tmp_path, steep=False)
    bg = _bg()
    for key in ("normal_gap_vertices_above", "normal_gap_centroids_above"):
        r = json.loads(json.dumps(rep))
        r["stack_gaps"][key] = 1
        assert bg.acceptance_gates(r)["normal_gap_max_20mm"]["pass"] is False
    assert bg.acceptance_gates(rep)["normal_gap_max_20mm"]["pass"] is True
