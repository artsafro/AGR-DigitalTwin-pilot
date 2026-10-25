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
