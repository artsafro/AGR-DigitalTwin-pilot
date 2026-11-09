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


@pytest.mark.parametrize("density", [511.999, 1706.001, float("nan"), float("inf"), -float("inf"), None, True])
def test_invalid_recipe_and_binding_density_rejected(density):
    recipes = load("ground_recipes")
    with pytest.raises(recipes.GroundRecipeError):
        recipes.require_px_per_m("vpm", density)
    bind = load("bind_ground_textures")
    area = (density / 4096.) ** 2 if isinstance(density, float) else density
    with pytest.raises(bind.BindError):
        bind.density_report([{"slot": "TileLight", "world_area_m2": 1., "uv_area": area}], "vpm")


def test_npm_band_and_invalid_profiles_unchanged():
    recipes = load("ground_recipes")
    for value in [10., 40.]: recipes.require_px_per_m("npm", value)
    for value in [9.999, 40.001]:
        with pytest.raises(recipes.GroundRecipeError): recipes.require_px_per_m("npm", value)
    with pytest.raises(recipes.GroundRecipeError): recipes.require_px_per_m("other", 512.)
    bind = load("bind_ground_textures")
    with pytest.raises(bind.BindError): bind.density_report([], "vpm")
    with pytest.raises(bind.BindError): bind.density_report([], "other")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_detail_nonfinite_geometry_is_not_ready(bad):
    verts = np.array([[0.,0.,0.],[8.,0.,0.],[0.,8.,0.]])
    verts[1, 0] = bad
    with pytest.raises(ValueError, match="finite"):
        gd.triangle_uv(verts, np.array([[0,1,2]]))


def test_detail_empty_geometry_is_not_ready():
    with pytest.raises(ValueError, match="nonempty"):
        gd.triangle_uv(np.empty((0,3)), np.empty((0,3), dtype=int))


def test_detail_below_lower_bound_rejected():
    with pytest.raises(ValueError, match="512 px/m"):
        gd.triangle_uv(np.array([[0.,0.,0.],[8.001,0.,0.],[0.,8.001,0.]]), np.array([[0,1,2]]))
