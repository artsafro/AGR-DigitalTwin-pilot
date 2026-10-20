"""new-case: accepted SINTEZ 512 px/m lower bound at existing public seams."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
from dt_ai.geometry import ground_details as gd

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools/materials" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("density", [512., 513., 516., 519., 520., 1706.])
def test_recipe_and_binding_accept_decided_inclusive_band(density):
    load("ground_recipes").require_px_per_m("vpm", density)
    report = load("bind_ground_textures").density_report([
        {"slot": "TileLight", "world_area_m2": 1., "uv_area": (density / 4096.) ** 2}
    ], "vpm", expected_slots=["TileLight"])
    assert report["TileLight"]["min"] == pytest.approx(density)


def test_detail_projection_accepts_eight_metre_boundary():
    verts = np.array([[0., 0., 0.], [8., 0., 0.], [0., 8., 0.]])
    uv = gd.triangle_uv(verts, np.array([[0, 1, 2]]))
    assert np.isfinite(uv).all()
    assert uv.min() == 0 and uv.max() == 1
