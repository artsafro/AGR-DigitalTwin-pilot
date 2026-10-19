"""Procedural Vatutino Ground diffuse recipes: names, seams, fail-closed delivery."""

import ast
import copy
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = ROOT / "tools" / "materials" / "ground_recipes.json"
MODULE_PATH = ROOT / "tools" / "materials" / "ground_recipes.py"
DELIVERY = Path("C:/x/vatutino-ground-textures/v001")
SLOTS = (
    "TileLight",
    "Mulch",
    "LawnReinforced",
    "TileRed",
    "Gravel",
    "LawnRolled",
    "Pebbles",
    "TileDark",
    "FlowerBed",
    "Skirt",
)
_NAME = re.compile(
    r"^T_[A-Za-z0-9_]+_Ground_Diffuse_[A-Za-z0-9_]+(?:\.1001)?\.png$"
)


@pytest.fixture(scope="module")
def recipes():
    spec = importlib.util.spec_from_file_location("ground_recipes", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def recipe(recipes):
    return recipes.load_recipe(RECIPE_PATH)


def _seam_ratios(image: np.ndarray) -> tuple[float, float]:
    """Wrap mean |RGB| / median interior adjacent step, horizontal then vertical.

    Each adjacent step is averaged along the seam and across RGB. The median
    drops the first and last of those steps. This is the acceptance definition.
    """
    data = np.ascontiguousarray(image).astype(np.int16)

    def _axis(seam: np.ndarray, steps: np.ndarray, along: tuple[int, ...]) -> float:
        means = np.mean(np.abs(steps), axis=along)
        interior = means[1:-1] if means.size >= 3 else means
        median = float(np.median(interior)) if interior.size else 0.0
        seam_mean = float(np.mean(np.abs(seam)))
        if median == 0:
            return 0.0 if seam_mean == 0 else math.inf
        return seam_mean / median

    horizontal = _axis(data[:, 0, :] - data[:, -1, :], data[:, 1:, :] - data[:, :-1, :], (0, 2))
    vertical = _axis(data[0, :, :] - data[-1, :, :], data[1:, :, :] - data[:-1, :, :], (1, 2))
    return horizontal, vertical


def _seam_ok(image: np.ndarray, limit: float = 1.5) -> tuple[bool, float, float]:
    """Independent wrap check: both axes <= limit."""
    horizontal, vertical = _seam_ratios(image)
    return horizontal <= limit and vertical <= limit, max(horizontal, vertical), 0.0


def test_module_source_has_no_network_or_photo_loader():
    text = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"argparse", "hashlib", "io", "json", "math", "os", "re", "sys", "pathlib", "numpy", "PIL"}
    lowered = text.lower()
    for banned in ("openai", "requests.get", "urllib.request", "download", "huggingface"):
        assert banned not in lowered


def test_shipped_recipe_covers_the_ten_vatutino_slots(recipe):
    assert recipe["address"] == "Vatutino"
    assert recipe["seed"] == 319
    assert list(recipe["slots"]) == list(SLOTS)
    assert recipe["profiles"]["npm"]["size"] == 2048
    assert recipe["profiles"]["npm"]["px_per_m"] == 30
    assert recipe["profiles"]["vpm"]["size"] == 4096
    assert recipe["profiles"]["vpm"]["px_per_m"] == 1024
    npm_metres = recipe["profiles"]["npm"]["metres_per_repeat"]
    vpm_metres = recipe["profiles"]["vpm"]["metres_per_repeat"]
    assert math.isclose(npm_metres, 2048 / 30, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(round(npm_metres, 2), 68.27)
    assert vpm_metres == 4
    tile = recipe["slots"]["TileLight"]
    assert tile["nominal_tile_mm"] == [100, 300]
    assert recipe["slots"]["TileRed"]["nominal_tile_mm"] == [100, 300]
    assert recipe["slots"]["TileDark"]["nominal_tile_mm"] == [100, 300]
    assert recipe["slots"]["Gravel"]["fraction_mm"] == [2, 8]
    assert len(recipe["slots"]["FlowerBed"]["species"]) == 8


def test_every_slot_documents_provisional_values(recipe):
    for slot in SLOTS:
        flags = recipe["slots"][slot]["provisional"]
        assert isinstance(flags, list) and flags
        for flag in flags:
            assert isinstance(flag["field"], str) and flag["field"].strip()
            assert isinstance(flag["reason"], str) and len(flag["reason"].strip()) >= 8


def test_filename_grammar_and_length_ceiling(recipes):
    seen = set()
    for slot in SLOTS:
        for profile in ("npm", "vpm"):
            name = recipes.texture_filename("Vatutino", slot, profile)
            assert _NAME.fullmatch(name)
            assert len(name) <= 254
            assert "." not in name.replace(".1001", "").replace(".png", "")
            seen.add(name)
    assert len(seen) == 20
    suffix = "_Ground_Diffuse_TileLight.png"
    room = 254 - len("T_") - len(suffix)
    exact = recipes.texture_filename("A" * room, "TileLight", "npm")
    assert len(exact) == 254
    with pytest.raises(recipes.GroundRecipeError):
        recipes.texture_filename("A" * (room + 1), "TileLight", "npm")
    with pytest.raises(recipes.GroundRecipeError):
        recipes.texture_filename("Bad-Name", "TileLight", "npm")
    with pytest.raises(recipes.GroundRecipeError):
        recipes.texture_filename("Ватутино", "TileLight", "npm")


def test_regression_unknown_slot_missing_parameter_and_bad_period(recipes, recipe):
    with pytest.raises(recipes.GroundRecipeError, match="unknown slot"):
        recipes.render_map(recipe, "Water", "npm", size=256)
    broken = copy.deepcopy(recipe)
    del broken["slots"]["TileLight"]["nominal_tile_mm"]
    with pytest.raises(recipes.GroundRecipeError, match="nominal_tile_mm"):
        recipes.validate_recipe(broken)
    broken = copy.deepcopy(recipe)
    broken["slots"]["TileLight"]["npm_period_px"] = [100, 64]
    with pytest.raises(recipes.GroundRecipeError, match="divide"):
        recipes.validate_recipe(broken)
    broken = copy.deepcopy(recipe)
    broken["slots"]["Mulch"]["npm_cell_px"] = 100
    with pytest.raises(recipes.GroundRecipeError, match="divide"):
        recipes.render_map(broken, "Mulch", "npm", size=256)


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf"), -100, 0, -0.0],
)
def test_nonfinite_or_nonpositive_tile_size_errors(recipes, recipe, value):
    broken = copy.deepcopy(recipe)
    broken["slots"]["TileLight"]["nominal_tile_mm"] = [value, 300]
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe(broken)


def test_empty_partial_and_unsupported_recipes_error(recipes, recipe):
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe({})
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe({"address": "Vatutino", "seed": 319, "profiles": {}, "slots": {}})
    partial = copy.deepcopy(recipe)
    del partial["slots"]["Skirt"]
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe(partial)
    partial = copy.deepcopy(recipe)
    del partial["profiles"]["vpm"]["px_per_m"]
    with pytest.raises(recipes.GroundRecipeError, match="px_per_m"):
        recipes.validate_recipe(partial)
    unsupported = copy.deepcopy(recipe)
    unsupported["slots"]["Skirt"]["family"] = "photo"
    with pytest.raises(recipes.GroundRecipeError, match="unsupported"):
        recipes.validate_recipe(unsupported)
    extra = copy.deepcopy(recipe)
    extra["slots"]["Glass"] = copy.deepcopy(recipe["slots"]["Skirt"])
    with pytest.raises(recipes.GroundRecipeError, match="unknown slot"):
        recipes.validate_recipe(extra)


@pytest.mark.parametrize(
    ("profile", "value"),
    [
        ("npm", 10),
        ("npm", 40),
        ("vpm", 520),
        ("vpm", 1706),
    ],
)
def test_density_endpoints_inside_d097_are_accepted(recipes, profile, value):
    recipes.require_px_per_m(profile, value)


@pytest.mark.parametrize(
    ("profile", "value"),
    [
        ("npm", 10 - 1e-9),
        ("npm", 40 + 1e-9),
        ("vpm", 520 - 1e-9),
        ("vpm", 1706 + 1e-9),
        ("npm", float("nan")),
        ("vpm", float("inf")),
        ("npm", -30),
    ],
)
def test_density_outside_band_or_nonfinite_errors(recipes, profile, value):
    with pytest.raises(recipes.GroundRecipeError):
        recipes.require_px_per_m(profile, value)


def test_seam_ceiling_accepts_exact_ratio_and_rejects_above():
    image = np.zeros((6, 8, 3), dtype=np.uint8)
    image[:] = (np.arange(8, dtype=np.uint8) * 2)[None, :, None]
    image[:, -1, :] = 3
    ok, _worst, _med = _seam_ok(image, 1.5)
    assert ok
    image[:, -1, :] = 4
    ok, _worst, _med = _seam_ok(image, 1.5)
    assert not ok


def test_grid_periods_divide_delivery_and_reduced_sizes(recipe):
    checked = 0
    for slot, body in recipe["slots"].items():
        for profile, delivery in (("npm", 2048), ("vpm", 4096)):
            periods = body.get(f"{profile}_period_px")
            cell = body.get(f"{profile}_cell_px")
            if periods is not None:
                for period in periods:
                    assert delivery % period == 0
                    scaled = period * 256 / delivery
                    assert scaled > 0
                    assert math.isclose(256 / scaled, delivery // period, rel_tol=0, abs_tol=1e-6)
                    checked += 1
            if cell is not None:
                assert delivery % cell == 0
                scaled = cell * 256 / delivery
                assert scaled > 0
                assert math.isclose(256 / scaled, delivery // cell, rel_tol=0, abs_tol=1e-6)
                checked += 1
            if periods is None and cell is None:
                assert delivery % delivery == 0
                checked += 1
    assert checked >= 20


@pytest.mark.parametrize("size", [512, 2048])
def test_npm_tile_row_wrap_on_both_axes(recipes, recipe, size):
    """NPM tile period x is at least 8 from 512px up, so the bond is active.

    256px scales that period below 8 and hides the row-wrap. The acceptance
    failure is the last row against the first at full NPM size.
    """
    for slot in ("TileLight", "TileRed", "TileDark"):
        image = recipes.render_map(recipe, slot, "npm", size=size)
        horizontal, vertical = _seam_ratios(image)
        assert horizontal <= 1.5, f"{slot} npm {size} horizontal {horizontal:.3f}"
        assert vertical <= 1.5, f"{slot} npm {size} vertical {vertical:.3f}"


def test_reduced_renders_are_deterministic_rgb_and_seamless(recipes, recipe):
    hashes = {}
    for slot in SLOTS:
        for profile in ("npm", "vpm"):
            image = recipes.render_map(recipe, slot, profile, size=256)
            again = recipes.render_map(recipe, slot, profile, size=256)
            assert image.shape == (256, 256, 3)
            assert image.dtype == np.uint8
            assert np.isfinite(image).all()
            digest = hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()
            assert digest == hashlib.sha256(np.ascontiguousarray(again).tobytes()).hexdigest()
            png_a = hashlib.sha256(recipes.png_bytes(image)).hexdigest()
            png_b = hashlib.sha256(recipes.png_bytes(again)).hexdigest()
            assert png_a == png_b
            ok, worst, _median = _seam_ok(image)
            assert ok, f"{slot} {profile} seam ratio {worst}"
            hashes[(slot, profile)] = digest
    assert len(set(hashes.values())) == 20


def test_delivery_size_other_than_2048_or_4096_errors(recipes, recipe):
    with pytest.raises(recipes.GroundRecipeError, match="2048"):
        recipes.render_map(recipe, "Skirt", "npm", size=1024, delivery=True)
    with pytest.raises(recipes.GroundRecipeError, match="4096"):
        recipes.render_map(recipe, "Skirt", "vpm", size=2048, delivery=True)
    with pytest.raises(recipes.GroundRecipeError):
        recipes.render_map(recipe, "Skirt", "npm", size=0, delivery=True)


def test_contact_labels_name_the_slot_tile_size_and_provisional_mark(recipes, recipe):
    for slot in SLOTS:
        label = recipes.contact_label(recipe, slot)
        assert slot in label
        assert "PROVISIONAL" in label
        assert recipe["slots"][slot]["tile_size_label"] in label
    assert "100 x 300 mm" in recipes.contact_label(recipe, "TileLight")
    assert "2-8 mm" in recipes.contact_label(recipe, "Gravel")


def test_contact_sheet_places_npm_tile_and_one_metre_crop(recipes, recipe):
    rendered = {}
    for slot in SLOTS:
        rendered[slot] = {
            "npm": recipes.render_map(recipe, slot, "npm", size=256),
            "vpm": np.tile(
                recipes.render_map(recipe, slot, "vpm", size=256),
                (2, 2, 1),
            )[:512, :512],
        }
    sheet_recipe = copy.deepcopy(recipe)
    sheet_recipe["profiles"]["vpm"]["px_per_m"] = 128
    sheet = recipes.build_contact_sheet(sheet_recipe, rendered)
    assert sheet.mode == "RGB"
    assert sheet.size[1] >= 10 * 128
    pixels = np.asarray(sheet)
    assert pixels.shape[2] == 3


def test_manifest_entry_carries_texel_facts(recipes, recipe):
    image = recipes.render_map(recipe, "Gravel", "npm", size=256)
    entry = recipes.manifest_entry(recipe, "Gravel", "npm", image, delivery_size=False)
    assert entry["slot"] == "Gravel"
    assert entry["profile"] == "npm"
    assert entry["size"] == [256, 256]
    assert entry["px_per_m"] == 30
    assert "fraction_mm" in entry["recipe_parameters"]
    assert entry["provisional"]
    assert entry["seed"] == 319
    assert len(entry["sha256"]) == 64
    delivery = recipes.manifest_entry(
        recipe,
        "Gravel",
        "vpm",
        np.zeros((4096, 4096, 3), dtype=np.uint8),
        delivery_size=True,
    )
    assert delivery["size"] == [4096, 4096]
    assert delivery["px_per_m"] == 1024
    assert 520 <= delivery["px_per_m"] <= 1706
    assert delivery["metres_per_repeat"] == 4


def test_output_inside_repository_is_refused_before_writing(recipes, tmp_path):
    inside = ROOT / "tmp_ground_recipe_out"
    before = set(ROOT.glob("tmp_ground_recipe_out/**"))
    with pytest.raises(recipes.GroundRecipeError, match="repository"):
        recipes.write_delivery(RECIPE_PATH, inside)
    assert not inside.exists()
    assert set(ROOT.glob("tmp_ground_recipe_out/**")) == before
    with pytest.raises(recipes.GroundRecipeError, match="version folder"):
        recipes.write_delivery(RECIPE_PATH, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_file_and_input_alias_write_nothing(recipes, tmp_path, monkeypatch):
    monkeypatch.setattr(recipes, "DELIVERY_DIR", tmp_path)
    marker = tmp_path / "already.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(recipes.GroundRecipeError, match="already"):
        recipes.write_delivery(RECIPE_PATH, tmp_path)
    assert marker.read_text(encoding="utf-8") == "keep"
    assert list(tmp_path.iterdir()) == [marker]

    empty = tmp_path / "alias"
    empty.mkdir()
    monkeypatch.setattr(recipes, "DELIVERY_DIR", empty)
    alias = empty / "manifest.json"
    alias.write_text(RECIPE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(recipes.GroundRecipeError, match="input"):
        recipes.write_delivery(alias, empty)
    assert list(empty.iterdir()) == [alias]
    assert alias.read_text(encoding="utf-8").startswith("{")


def test_cli_foreign_directory_exits_nonzero_and_writes_nothing(recipes, tmp_path, capsys):
    code = recipes.main(["deliver", "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert list(tmp_path.iterdir()) == []


def test_cli_aliases_recipe_path(recipes, capsys):
    code = recipes.main(["deliver", "--recipe", str(RECIPE_PATH), "--out", str(RECIPE_PATH)])
    captured = capsys.readouterr()
    assert code == 2
    assert "error:" in captured.err
    assert RECIPE_PATH.is_file()


def _face_px(image: np.ndarray) -> tuple[float, float]:
    """Paver face in pixels from the spacing of the dark joint's edges."""

    def _axis(profile: np.ndarray) -> float:
        values = np.asarray(profile, dtype=np.float64)
        delta = np.diff(values, append=values[:1])
        limit = max(8.0, 0.4 * float(np.max(np.abs(delta))))
        falls = np.flatnonzero(delta <= -limit)
        rises = np.flatnonzero(delta >= limit)
        if falls.size < 2 or rises.size < 2:
            raise AssertionError("joint edges are missing")
        period = float(np.median(np.diff(falls)))
        widths = []
        for fall in falls:
            later = rises[rises >= fall]
            rise = int(later[0]) if later.size else int(rises[0]) + values.size
            widths.append(rise - int(fall))
        return period - float(np.median(widths))

    return _axis(image.mean(axis=(0, 2))), _axis(image.mean(axis=(1, 2)))


@pytest.mark.parametrize(
    ("slot", "field", "value", "profile"),
    [
        ("TileLight", "nominal_tile_mm", [200, 600], "npm"),
        ("TileLight", "nominal_tile_mm", [200, 600], "vpm"),
        ("Gravel", "fraction_mm", [20, 80], "npm"),
        ("Gravel", "fraction_mm", [20, 80], "vpm"),
    ],
)
def test_physical_mutation_changes_pixels_or_errors(recipes, recipe, slot, field, value, profile):
    """Sourced millimetres are not metadata. Ignoring them leaves the map identical."""
    original = recipes.render_map(recipe, slot, profile, size=256)
    mutated = copy.deepcopy(recipe)
    mutated["slots"][slot][field] = value
    try:
        image = recipes.render_map(mutated, slot, profile, size=256)
    except recipes.GroundRecipeError:
        return
    assert image.shape == original.shape
    assert not np.array_equal(image, original)


@pytest.mark.parametrize("profile", ["npm", "vpm"])
def test_physical_supertile_keeps_faces_and_joints_within_one_percent(recipes, recipe, profile):
    body = recipe["slots"]["TileLight"]
    assert body["joint_mm"] == 5
    layout = recipes.tile_facts(body, profile)
    assert layout["nominal_face_mm"] == [100, 300]
    for axis in range(2):
        assert abs(layout["scale_error_percent"][axis]) <= 1
        assert layout["actual_face_mm"][axis] == pytest.approx(
            body["nominal_tile_mm"][axis] * layout["scale_factor"][axis])
        assert layout["actual_joint_mm"][axis] == pytest.approx(5 * layout["scale_factor"][axis])
        assert layout["period_px"][axis] * layout["count"][axis] == pytest.approx(
            recipe["profiles"][profile]["size"])
    image = recipes.render_map(recipe, "TileLight", profile, size=256)
    entry = recipes.manifest_entry(recipe, "TileLight", profile, image)
    assert entry["physical_layout"] == layout


def test_valid_scale_control_emits_the_nominal_face(recipes, recipe):
    control = copy.deepcopy(recipe)
    body = control["slots"]["TileLight"]
    body["nominal_tile_mm"] = [995, 995]
    body["joint_mm"] = 5
    image = recipes.render_map(control, "TileLight", "vpm", size=1024)
    # Four periods across 4m; threshold dark joints on a non-joint row.
    row = image[64].mean(axis=1)
    dark = row < 160
    runs = np.flatnonzero(np.diff(dark.astype(int), prepend=0) == 1)
    assert len(runs) == 4
    assert np.diff(runs) == pytest.approx([256, 256, 256], abs=1)
    facts = recipes.tile_facts(body, "vpm")
    assert facts["actual_face_mm"] == pytest.approx([995, 995])
    assert facts["scale_error_percent"] == pytest.approx([0, 0])


def test_fraction_pitch_error_of_half_a_texel_is_rejected(recipes, recipe):
    """Exactly 0.5 px of pitch error is incompatible. Just under it is still a grain size."""
    broken = copy.deepcopy(recipe)
    pitch_m = 4.0 / 3.0
    target_m = pitch_m + 0.5 / 1024.0
    broken["slots"]["Gravel"]["fraction_mm"] = [target_m * 1000.0, target_m * 1000.0]
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe(broken)
    allowed = copy.deepcopy(recipe)
    under_m = pitch_m + 0.49 / 1024.0
    allowed["slots"]["Gravel"]["fraction_mm"] = [under_m * 1000.0, under_m * 1000.0]
    recipes.validate_recipe(allowed)


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf"), -2, 0, [8, 2]],
)
def test_bad_fraction_errors(recipes, recipe, value):
    broken = copy.deepcopy(recipe)
    broken["slots"]["Gravel"]["fraction_mm"] = value
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe(broken)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True])
def test_invalid_joint_mm_errors(recipes, recipe, value):
    broken = copy.deepcopy(recipe)
    broken["slots"]["TileLight"]["joint_mm"] = value
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe(broken)


def test_tile_larger_than_the_repeat_errors(recipes, recipe):
    broken = copy.deepcopy(recipe)
    broken["slots"]["TileLight"]["nominal_tile_mm"] = [100000, 300000]
    with pytest.raises(recipes.GroundRecipeError):
        recipes.validate_recipe(broken)


def test_incompatible_recipe_does_not_render_or_write(recipes, recipe, tmp_path, monkeypatch):
    broken = copy.deepcopy(recipe)
    broken["slots"]["TileLight"]["nominal_tile_mm"] = [900, 1900]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    out = tmp_path / "empty"
    out.mkdir()
    monkeypatch.setattr(recipes, "DELIVERY_DIR", out)
    calls = []

    def _render(*_args, **_kwargs):
        calls.append(1)
        raise AssertionError("render started")

    monkeypatch.setattr(recipes, "render_map", _render)
    with pytest.raises(recipes.GroundRecipeError):
        recipes.write_delivery(path, out)
    assert calls == []
    assert list(out.iterdir()) == []


def test_version_parameter_and_address_are_fail_closed(recipes, recipe, tmp_path, monkeypatch):
    assert recipes.delivery_directory("v002") == Path("C:/x/vatutino-ground-textures/v002")
    for version in ("../v002", "v2", "v000", "v002/child", ""):
        with pytest.raises(recipes.GroundRecipeError):
            recipes.delivery_directory(version)
    for address in ("Bad-Name", "", "A" * 255):
        with pytest.raises(recipes.GroundRecipeError):
            recipes.write_delivery(RECIPE_PATH, tmp_path, version="v002", address=address)
    assert list(tmp_path.iterdir()) == []
