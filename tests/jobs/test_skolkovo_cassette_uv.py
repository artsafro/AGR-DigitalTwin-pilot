"""new-case: measured chart proof for the job-scoped delegated slender-profile policy."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops.inv_texel import PolyMesh

SPEC = importlib.util.spec_from_file_location(
    "skolkovo_cassette_uv", Path(__file__).parents[2] / "jobs/SKOLKOVO-L4/cassette_uv.py"
)
job = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(job)


def rectangle(length=3.0, width=0.02):
    mesh = PolyMesh(np.array([[0, 0, 0], [length, 0, 0], [length, width, 0], [0, width, 0]]), ((0, 1, 2, 3),))
    uv = (mesh.vertices[:, :2] * 1024 + 32) / 4096
    return mesh, [{"face": 0, "tile": 1001, "uv": uv.tolist()}]


def test_long_rectangle_with_actual_density_and_padding_is_diagnostic():
    mesh, charts = rectangle()
    result = job.qualify(job.PART, mesh, charts)
    assert result["qualified"], result


def test_strict_checker_still_rejects_slender_rectangle():
    from dt_ai.ops.inv_texel import texel_ready
    mesh, _ = rectangle()
    assert not texel_ready({job.PART: mesh}, "VPM-OKS").passed


@pytest.mark.parametrize("kind", ["empty", "partial", "duplicate", "unknown", "nan", "inf", "wrong_part"])
def test_missing_or_malformed_evidence_refuses(kind):
    mesh, charts = rectangle()
    part = job.PART
    if kind == "empty":
        mesh = PolyMesh(np.empty((0, 3)), ())
        charts = []
    elif kind == "partial":
        charts = []
    elif kind == "duplicate":
        mesh = PolyMesh(mesh.vertices, mesh.faces * 2)
        charts *= 2
    elif kind == "unknown":
        charts[0]["face"] = 1
    elif kind in ("nan", "inf"):
        charts[0]["uv"][0][0] = float(kind)
    elif kind == "wrong_part":
        part = "rods_primary_mast_meshes_rod_ladder_contour_rebuild"
    with pytest.raises(ValueError):
        job.qualify(part, mesh, charts)


@pytest.mark.parametrize("kind", ["density", "padding", "shear", "fold", "geometry_changed", "oversize"])
def test_negative_chart_proofs_are_not_waivers(kind):
    mesh, charts = rectangle()
    uv = np.array(charts[0]["uv"])
    if kind == "density":
        uv = uv * 0.5 + 0.1
    elif kind == "padding":
        uv[:, 0] -= 0.001
    elif kind == "shear":
        uv[2, 0] -= 0.001
    elif kind == "fold":
        uv[[2, 3]] = uv[[3, 2]]
    elif kind == "geometry_changed":
        vertices = mesh.vertices.copy()
        vertices[1:3, 0] += 0.01
        mesh = PolyMesh(vertices, mesh.faces)
    elif kind == "oversize":
        mesh, charts = rectangle(4.01)
        uv = np.array(charts[0]["uv"])
    charts[0]["uv"] = uv.tolist()
    result = job.qualify(job.PART, mesh, charts)
    assert not result["qualified"], result
    assert job.qualify(job.PART, *rectangle())["qualified"]


def test_exact_padded_tile_boundary_is_inclusive_but_above_refuses():
    assert job.qualify(job.PART, *rectangle(3.9375))["qualified"]
    assert not job.qualify(job.PART, *rectangle(3.9375 + 0.00001))["qualified"]


def test_overlapping_charts_refuse_and_separate_tiles_reset():
    mesh, charts = rectangle()
    mesh = PolyMesh(mesh.vertices, mesh.faces * 2)
    charts = [charts[0], {**charts[0], "face": 1}]
    assert not job.qualify(job.PART, mesh, charts)["qualified"]
    charts[1] = {**charts[1], "tile": 1002}
    assert job.qualify(job.PART, mesh, charts)["qualified"]


def test_generated_rectangles_preserve_inputs():
    rng = np.random.default_rng(353)
    for _ in range(50):
        mesh, charts = rectangle(rng.uniform(0.1, 3.9375), rng.uniform(0.001, 0.01))
        vertices = mesh.vertices.copy()
        original = repr(charts)
        assert job.qualify(job.PART, mesh, charts)["qualified"]
        np.testing.assert_array_equal(mesh.vertices, vertices)
        assert repr(charts) == original
