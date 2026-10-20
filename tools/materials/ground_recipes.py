"""Procedural Ground diffuse maps for Vatutino (issue 319, [D117], [D097], GND-11).

Pillow and numpy only. Sourced paver faces (`nominal_tile_mm`) and gravel
fractions (`fraction_mm`) set the pattern scale. Pixel periods and joints must
match those sizes at the profile px/m; a mismatch raises GroundRecipeError
before any pixel is written. The periodic supertile closes with at most 1% scale error per axis;
physical joint width is provisional, never widened to force integer periods.
Delivery writes only new version folders below C:/x/vatutino-ground-textures.

new-case: seeded procedural Ground diffuse recipes with physical supertile rasterization.

Unsourced visual choices are recipe parameters with their own provisional
flags: visual.blade_cycles, visual.grid_band_divisor, visual.micro_period_px,
visual.micro_amplitudes and visual.blur_radii. Tile npm_joint_px and
vpm_joint_px are flagged as the raster of provisional joint_mm, not as a
second source. Contact labels state the generated physical size. The
LawnReinforced band is the raster mask width: a centred bar of
2 * (cell // grid_band_divisor) + 1 texels, saturated at the cell, not the
divisor quotient. The contact sheet grows its label column and row so every
complete label fits.
"""

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

CANONICAL_SLOTS = (
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
    "CurbGarden",
    "Stairs",
)
FAMILIES = frozenset({"tile", "particles", "lawn", "ecogrid", "foliage", "soil"})
DELIVERY_DIR = Path("C:/x/vatutino-ground-textures/v001")
_MODULE = Path(__file__).resolve()
_REPO = _MODULE.parents[2]
_DEFAULT_RECIPE = _MODULE.with_name("ground_recipes.json")
_TOKEN = re.compile(r"^[A-Za-z0-9_]+$")
_NAME = re.compile(r"^T_[A-Za-z0-9_]+_Ground_Diffuse_[A-Za-z0-9_]+(?:\.1001)?\.png$")
_PROFILE_SIZE = {"npm": 2048, "vpm": 4096}
_PROFILE_DENSITY = {"npm": 30, "vpm": 1024}


class GroundRecipeError(ValueError):
    """The recipe, size, seam or output path cannot be delivered."""


def texture_filename(address: str, slot: str, profile: str) -> str:
    _token(address, "address")
    _token(slot, "slot")
    if profile == "npm":
        name = f"T_{address}_Ground_Diffuse_{slot}.png"
    elif profile == "vpm":
        name = f"T_{address}_Ground_Diffuse_{slot}.1001.png"
    else:
        raise GroundRecipeError(f"unknown profile {profile}")
    if len(name) > 254 or not _NAME.fullmatch(name):
        raise GroundRecipeError(f"texture name {name!r} is outside GND-11")
    return name


def require_px_per_m(profile: str, value) -> None:
    if profile not in _PROFILE_SIZE:
        raise GroundRecipeError(f"unknown profile {profile}")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise GroundRecipeError(f"{profile} px_per_m must be a finite number")
    low, high = (10, 40) if profile == "npm" else (520, 1706)
    if value < low or value > high:
        raise GroundRecipeError(f"{profile} px_per_m {value} is outside {low}-{high}")


def load_recipe(path) -> dict:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GroundRecipeError(f"recipe is not readable JSON: {exc}") from exc
    return validate_recipe(payload)


def validate_recipe(recipe) -> dict:
    if not isinstance(recipe, dict):
        raise GroundRecipeError("recipe must be an object")
    _require_key(recipe, "address")
    _require_key(recipe, "seed")
    _require_key(recipe, "profiles")
    _require_key(recipe, "slots")
    _token(recipe["address"], "address")
    seed = recipe["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise GroundRecipeError("seed must be a non-negative integer")
    profiles = recipe["profiles"]
    if not isinstance(profiles, dict):
        raise GroundRecipeError("profiles must be an object")
    for profile, size in _PROFILE_SIZE.items():
        if profile not in profiles:
            raise GroundRecipeError(f"missing profile {profile}")
        body = profiles[profile]
        if not isinstance(body, dict):
            raise GroundRecipeError(f"{profile} profile must be an object")
        _require_key(body, "size")
        _require_key(body, "px_per_m")
        _require_key(body, "metres_per_repeat")
        if body["size"] != size:
            raise GroundRecipeError(f"{profile} size must be {size}")
        if body["px_per_m"] != _PROFILE_DENSITY[profile]:
            raise GroundRecipeError(f"{profile} px_per_m must be {_PROFILE_DENSITY[profile]}")
        require_px_per_m(profile, body["px_per_m"])
        metres = body["metres_per_repeat"]
        if isinstance(metres, bool) or not isinstance(metres, (int, float)) or not math.isfinite(metres):
            raise GroundRecipeError(f"{profile} metres_per_repeat must be finite")
        if not math.isclose(metres, size / body["px_per_m"], rel_tol=0, abs_tol=1e-9):
            raise GroundRecipeError(f"{profile} metres_per_repeat does not match size / px_per_m")
    slots = recipe["slots"]
    if not isinstance(slots, dict):
        raise GroundRecipeError("slots must be an object")
    for name in slots:
        if name not in CANONICAL_SLOTS:
            raise GroundRecipeError(f"unknown slot {name}")
    for name in CANONICAL_SLOTS:
        if name not in slots:
            raise GroundRecipeError(f"missing slot {name}")
    for name in CANONICAL_SLOTS:
        _validate_slot(name, slots[name])
    _validate_visual(recipe)
    return recipe


def render_map(recipe, slot: str, profile: str, size: int | None = None, delivery: bool = False) -> np.ndarray:
    validate_recipe(recipe)
    if slot not in CANONICAL_SLOTS or slot not in recipe["slots"]:
        raise GroundRecipeError(f"unknown slot {slot}")
    if profile not in _PROFILE_SIZE:
        raise GroundRecipeError(f"unknown profile {profile}")
    delivery_size = _PROFILE_SIZE[profile]
    if delivery:
        if size is None:
            size = delivery_size
        if size != delivery_size:
            raise GroundRecipeError(f"{profile} delivery size must be {delivery_size}")
    else:
        size = delivery_size if size is None else size
        if isinstance(size, bool) or not isinstance(size, int) or size < 16:
            raise GroundRecipeError(f"size {size} is not a usable map size")
        if delivery_size % size != 0:
            raise GroundRecipeError(f"size {size} does not divide the map size {delivery_size}")
    body = recipe["slots"][slot]
    rng = _rng(recipe["seed"], slot, profile, size)
    image = _draw(
        body,
        slot,
        profile,
        size,
        delivery_size,
        recipe["profiles"][profile]["px_per_m"],
        rng,
        recipe["visual"],
    )
    return _finish(image, recipe["visual"])


def png_bytes(image: np.ndarray) -> bytes:
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise GroundRecipeError("map must be 8-bit RGB without alpha")
    buffer = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add(b"sRGB", b"\x00")
    Image.fromarray(np.ascontiguousarray(image), "RGB").save(buffer, format="PNG", pnginfo=info)
    return buffer.getvalue()


def contact_label(recipe, slot: str) -> str:
    body = recipe["slots"][slot]
    return f"{slot}  {body['tile_size_label']}  PROVISIONAL\n{_actual_size_text(recipe, slot)}"


def build_contact_sheet(recipe, rendered: dict) -> Image.Image:
    px_per_m = recipe["profiles"]["vpm"]["px_per_m"]
    slots = [slot for slot in CANONICAL_SLOTS if slot in rendered]
    if slots != list(CANONICAL_SLOTS):
        raise GroundRecipeError("contact sheet is missing a slot")
    crops = [_one_metre(rendered[slot]["vpm"], px_per_m) for slot in slots]
    cell = crops[0].shape[0]
    if any(crop.shape[0] != cell or crop.shape[1] != cell for crop in crops):
        raise GroundRecipeError("contact sheet crops differ in size")
    labels = [contact_label(recipe, slot) for slot in slots]
    font = _font(max(16, min(32, cell // 16)))
    spacing = 6
    pad = 16
    label_w, row_h = _label_panel(labels, font, cell, pad, spacing)
    sheet = Image.new("RGB", (cell * 3 + label_w, row_h * len(slots)), (244, 244, 240))
    draw = ImageDraw.Draw(sheet)
    for index, slot in enumerate(slots):
        y = index * row_h
        sheet.paste(_fit(rendered[slot]["npm"], cell), (0, y))
        tiled = np.tile(np.ascontiguousarray(rendered[slot]["npm"]), (2, 2, 1))
        sheet.paste(_fit(tiled, cell), (cell, y))
        sheet.paste(Image.fromarray(crops[index], "RGB"), (cell * 2, y))
        draw.multiline_text(
            (cell * 3 + pad, y + pad),
            labels[index],
            fill=(24, 24, 24),
            font=font,
            spacing=spacing,
        )
    return sheet


def manifest_entry(recipe, slot: str, profile: str, image: np.ndarray, delivery_size: bool = False) -> dict:
    validate_recipe(recipe)
    if image.ndim != 3 or image.shape[2] != 3:
        raise GroundRecipeError("map must be RGB")
    height, width = int(image.shape[0]), int(image.shape[1])
    if height != width:
        raise GroundRecipeError("map must be square")
    spec = recipe["profiles"][profile]
    if delivery_size and (height, width) != (spec["size"], spec["size"]):
        raise GroundRecipeError(f"{profile} delivery size must be {spec['size']}")
    body = recipe["slots"][slot]
    return {
        "file": texture_filename(recipe["address"], slot, profile),
        "slot": slot,
        "profile": profile,
        "size": [height, width],
        "metres_per_repeat": spec["metres_per_repeat"],
        "px_per_m": spec["px_per_m"],
        "recipe_parameters": body,
        "physical_layout": tile_facts(body, profile) if body["family"] == "tile" else None,
        "provisional": body["provisional"],
        "seed": recipe["seed"],
        "sha256": hashlib.sha256(png_bytes(np.ascontiguousarray(image).astype(np.uint8))).hexdigest(),
    }


def delivery_directory(version: str) -> Path:
    if not isinstance(version, str) or not re.fullmatch(r"v[0-9]{3}", version) or version == "v000":
        raise GroundRecipeError("invalid output version; expected v001..v999")
    return DELIVERY_DIR.parent / version


def write_delivery(recipe_path, out_dir, *, version=None, address=None) -> dict:
    recipe_path = Path(recipe_path)
    out_dir = Path(out_dir)
    if _resolves_to_input(out_dir, recipe_path):
        raise GroundRecipeError("output path resolves to an input")
    if _inside_repo(out_dir):
        raise GroundRecipeError("output directory is inside the repository")
    allowed = DELIVERY_DIR if version is None else delivery_directory(version)
    if not _same(out_dir, allowed):
        raise GroundRecipeError(
            f"output directory is not the version folder {allowed}"
        )
    if out_dir.exists() and any(out_dir.iterdir()):
        raise GroundRecipeError("version folder already contains files")
    recipe = load_recipe(recipe_path)
    if address is not None:
        recipe["address"] = address
    for slot in CANONICAL_SLOTS:
        for profile in _PROFILE_SIZE:
            texture_filename(recipe["address"], slot, profile)
    if _resolves_to_input(out_dir, recipe_path):
        raise GroundRecipeError("output path resolves to an input")
    rendered = {}
    entries = []
    files = []
    for slot in CANONICAL_SLOTS:
        rendered[slot] = {}
        for profile in ("npm", "vpm"):
            image = render_map(recipe, slot, profile, delivery=True)
            name = texture_filename(recipe["address"], slot, profile)
            files.append((name, png_bytes(image)))
            entries.append(manifest_entry(recipe, slot, profile, image, delivery_size=True))
            if profile == "vpm":
                rendered[slot][profile] = _one_metre(image, recipe["profiles"]["vpm"]["px_per_m"])
            else:
                rendered[slot][profile] = image
    sheet = build_contact_sheet(recipe, rendered)
    sheet_buffer = io.BytesIO()
    sheet.save(sheet_buffer, format="JPEG", quality=90, subsampling=0)
    manifest = {
        "address": recipe["address"],
        "seed": recipe["seed"],
        "source_versions": recipe.get("source_versions", {}),
        "visual": recipe["visual"],
        "maps": entries,
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise GroundRecipeError("version folder already contains files")
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.iterdir()):
        raise GroundRecipeError("version folder already contains files")
    for name, payload in files:
        with (out_dir / name).open("xb") as stream:
            stream.write(payload)
    (out_dir / "contact_sheet.jpg").write_bytes(sheet_buffer.getvalue())
    (out_dir / "manifest.json").write_bytes(manifest_bytes)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ground_recipes")
    sub = parser.add_subparsers(dest="command", required=True)
    deliver = sub.add_parser("deliver")
    deliver.add_argument("--recipe", default=str(_DEFAULT_RECIPE))
    deliver.add_argument("--out", required=True)
    deliver.add_argument("--version", default="v001")
    deliver.add_argument("--address")
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code) if exc.code else 0
    try:
        manifest = write_delivery(args.recipe, args.out, version=args.version, address=args.address)
    except GroundRecipeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(manifest['maps'])} ground diffuse maps")
    return 0


def _validate_visual(recipe) -> None:
    _require_key(recipe, "visual")
    visual = recipe["visual"]
    if not isinstance(visual, dict):
        raise GroundRecipeError("visual must be an object")
    for key in (
        "blade_cycles",
        "grid_band_divisor",
        "micro_period_px",
        "micro_amplitudes",
        "blur_radii",
        "provisional",
    ):
        _require_key(visual, key)
    cycles = visual["blade_cycles"]
    if isinstance(cycles, bool) or not isinstance(cycles, (int, float)) or not math.isfinite(cycles) or cycles <= 0:
        raise GroundRecipeError("blade_cycles must be finite and positive")
    _positive_int(visual["grid_band_divisor"], "grid_band_divisor")
    _positive_int(visual["micro_period_px"], "micro_period_px")
    amplitudes = visual["micro_amplitudes"]
    if not isinstance(amplitudes, list) or not amplitudes:
        raise GroundRecipeError("micro_amplitudes are missing")
    for item in amplitudes:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or item <= 0:
            raise GroundRecipeError("micro_amplitudes must be finite and positive")
    radii = visual["blur_radii"]
    if not isinstance(radii, list) or not radii:
        raise GroundRecipeError("blur_radii are missing")
    for item in radii:
        _positive_int(item, "blur_radii")
    fields = _provisional_fields(visual["provisional"], "visual")
    for key in ("blade_cycles", "grid_band_divisor", "micro_period_px", "micro_amplitudes", "blur_radii"):
        if key not in fields:
            raise GroundRecipeError(f"visual {key} has no provisional flag")


def _provisional_fields(flags, name: str) -> set[str]:
    if not isinstance(flags, list) or not flags:
        raise GroundRecipeError(f"{name} provisional flags are missing")
    fields: set[str] = set()
    for flag in flags:
        if not isinstance(flag, dict):
            raise GroundRecipeError(f"{name} provisional flag must be an object")
        _require_key(flag, "field")
        _require_key(flag, "reason")
        if not isinstance(flag["field"], str) or not flag["field"].strip():
            raise GroundRecipeError(f"{name} provisional field is empty")
        if not isinstance(flag["reason"], str) or len(flag["reason"].strip()) < 8:
            raise GroundRecipeError(f"{name} provisional reason is empty")
        fields.add(flag["field"])
    return fields


def _validate_slot(name: str, body) -> None:
    if not isinstance(body, dict):
        raise GroundRecipeError(f"{name} must be an object")
    for key in ("family", "source", "tile_size_label", "provisional"):
        _require_key(body, key)
    family = body["family"]
    if family not in FAMILIES:
        raise GroundRecipeError(f"unsupported family {family}")
    if not isinstance(body["source"], str) or len(body["source"].strip()) < 8:
        raise GroundRecipeError(f"{name} source is missing")
    if not isinstance(body["tile_size_label"], str) or not body["tile_size_label"].strip():
        raise GroundRecipeError(f"{name} tile_size_label is missing")
    fields = _provisional_fields(body["provisional"], name)
    if family == "tile":
        _require_key(body, "nominal_tile_mm")
        _positive_pair(body["nominal_tile_mm"], "nominal_tile_mm")
        _rgb(body.get("base_rgb"), "base_rgb")
        _rgb(body.get("joint_rgb"), "joint_rgb")
        _require_key(body, "joint_mm")
        _positive_pair([body["joint_mm"], body["joint_mm"]], "joint_mm")
        for profile in _PROFILE_SIZE:
            if f"{profile}_period_px" in body:
                _period_pair(body, profile)
                raise GroundRecipeError("pixel periods cannot override physical nominal_tile_mm")
            if f"{profile}_joint_px" in body:
                raise GroundRecipeError("pixel joints cannot override physical joint_mm")
            tile_facts(body, profile)
    elif family == "particles":
        _palette(body)
        if name == "Gravel":
            _require_key(body, "fraction_mm")
            _fraction_pair(body["fraction_mm"])
            for profile in ("npm", "vpm"):
                if f"{profile}_cell_px" in body:
                    raise GroundRecipeError(f"{profile}_cell_px cannot override fraction_mm")
                _grain_count(body["fraction_mm"], profile)
        else:
            if "fraction_mm" in body:
                raise GroundRecipeError("fraction_mm is only valid for Gravel")
            _cell(body, "npm")
            _cell(body, "vpm")
    elif family == "lawn":
        _palette(body)
    elif family == "ecogrid":
        _palette(body)
        _rgb(body.get("grid_rgb"), "grid_rgb")
        _cell(body, "npm")
        _cell(body, "vpm")
    elif family == "foliage":
        _palette(body)
        _require_key(body, "bloom_palette")
        blooms = body["bloom_palette"]
        if not isinstance(blooms, list) or len(blooms) < 2:
            raise GroundRecipeError("bloom_palette is missing")
        for colour in blooms:
            _rgb(colour, "bloom_palette")
        _require_key(body, "species")
        species = body["species"]
        if not isinstance(species, list) or len(species) != 8:
            raise GroundRecipeError("species must list the eight flower-bed names")
        if any(not isinstance(item, str) or not item.strip() for item in species):
            raise GroundRecipeError("species names are missing")
        _cell(body, "npm")
        _cell(body, "vpm")
    elif family == "soil":
        _palette(body)
    if family == "tile":
        for key in ("npm_joint_px", "vpm_joint_px"):
            if key not in fields:
                raise GroundRecipeError(f"{name} {key} has no provisional flag")
    for key in body:
        if isinstance(key, str) and key.endswith("_cell_px") and key not in fields:
            raise GroundRecipeError(f"{name} {key} has no provisional flag")


def _period_pair(body, profile: str) -> None:
    key = f"{profile}_period_px"
    _require_key(body, key)
    period = body[key]
    if not isinstance(period, (list, tuple)) or len(period) != 2:
        raise GroundRecipeError(f"{key} must be a pair")
    size = _PROFILE_SIZE[profile]
    for item in period:
        value = _positive_int(item, key)
        if size % value != 0:
            raise GroundRecipeError(f"{key} {value} does not divide the map size {size}")


def tile_facts(body, profile: str) -> dict:
    """Fit an integer number of physical tiles into a periodic supertile, <=1% error."""
    size = _PROFILE_SIZE[profile]
    density = _PROFILE_DENSITY[profile]
    repeat_mm = size / density * 1000
    nominal = body["nominal_tile_mm"]
    gap = body["joint_mm"]
    counts, factors = [], []
    for face in nominal:
        pitch = face + gap
        count = int(round(repeat_mm / pitch))
        if count < 1 or face >= repeat_mm:
            raise GroundRecipeError("nominal_tile_mm does not fit the repeat")
        factor = repeat_mm / (count * pitch)
        if abs(factor - 1) > 0.01 + 1e-12:
            raise GroundRecipeError("physical tile grid cannot close within 1% scale error")
        counts.append(count)
        factors.append(factor)
    return {
        "nominal_face_mm": list(nominal), "nominal_joint_mm": gap,
        "count": counts, "period_px": [size / n for n in counts],
        "scale_factor": factors, "scale_error_percent": [(s - 1) * 100 for s in factors],
        "actual_face_mm": [v * s for v, s in zip(nominal, factors)],
        "actual_joint_mm": [gap * s for s in factors],
        "rasterization": "analytic pixel-area joint coverage; subpixel details averaged",
    }


def _fraction_pair(value) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise GroundRecipeError("fraction_mm must be a pair")
    numbers = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or item <= 0:
            raise GroundRecipeError("fraction_mm must be finite and positive")
        numbers.append(float(item))
    if numbers[0] > numbers[1]:
        raise GroundRecipeError("fraction_mm minimum is greater than its maximum")
    return numbers[0], numbers[1]


def _grain_count(fraction_mm, profile: str) -> int:
    """Cells across one repeat. Pitch may move by less than half a texel, never more."""
    lo, hi = _fraction_pair(fraction_mm)
    px_per_m = _PROFILE_DENSITY[profile]
    repeat_m = _PROFILE_SIZE[profile] / px_per_m
    target = (lo + hi) / 2.0 / 1000.0
    if target >= repeat_m:
        raise GroundRecipeError("fraction_mm is larger than the repeat")
    count = int(round(repeat_m / target))
    if count < 1:
        raise GroundRecipeError("fraction_mm is not representable")
    pitch = repeat_m / count
    err_px = abs(pitch - target) * px_per_m
    if err_px >= 0.5:
        raise GroundRecipeError("fraction_mm cannot be represented at this px/m without changing scale")
    return count


def _cell(body, profile: str) -> None:
    key = f"{profile}_cell_px"
    _require_key(body, key)
    value = _positive_int(body[key], key)
    size = _PROFILE_SIZE[profile]
    if size % value != 0:
        raise GroundRecipeError(f"{key} {value} does not divide the map size {size}")


def _draw(body, slot: str, profile: str, size: int, delivery_size: int, px_per_m, rng, visual) -> np.ndarray:
    family = body["family"]
    if family == "tile":
        period, joint = _tile_layout(body, profile, size, delivery_size, px_per_m)
        image = _draw_tile(size, period, joint, body["base_rgb"], body["joint_rgb"], rng)
    elif family == "particles" and slot == "Gravel":
        count = _grain_count(body["fraction_mm"], profile)
        image = _draw_grains(size, count, body["palette"], rng, body["fraction_mm"])
    elif family in {"particles", "foliage", "ecogrid"}:
        cell = _scale_int(body[f"{profile}_cell_px"], delivery_size, size, f"{profile}_cell_px")
        if family == "particles":
            image = _draw_particles(size, cell, body["palette"], rng)
        elif family == "foliage":
            image = _draw_foliage(size, cell, body["palette"], body["bloom_palette"], rng, visual["blade_cycles"])
        else:
            image = _draw_ecogrid(
                size, cell, body["palette"], body["grid_rgb"], rng,
                visual["grid_band_divisor"], visual["blade_cycles"],
            )
    elif family == "lawn":
        image = _draw_lawn(size, body["palette"], rng, visual["blade_cycles"])
    else:
        image = _draw_soil(size, body["palette"], rng)
    cycles = 11 + CANONICAL_SLOTS.index(slot) + (0 if profile == "npm" else 3)
    carrier = _carrier(size, cycles)
    return image * (0.90 + 0.10 * carrier[..., None])


def _tile_layout(body, profile: str, size: int, delivery_size: int, px_per_m):
    facts = tile_facts(body, profile)
    period = tuple(size / n for n in facts["count"])
    joint = tuple(p * body["joint_mm"] / (face + body["joint_mm"])
                  for p, face in zip(period, body["nominal_tile_mm"]))
    return period, joint


def _joint_coverage(size, period, width):
    """Exact area coverage of centred joint intervals, including subpixel NPM joints."""
    start = (period - width) / 2
    def primitive(x):
        cycles = np.floor((x - start) / period)
        local = x - start - cycles * period
        return cycles * width + np.clip(local, 0, width)
    edges = np.arange(size + 1, dtype=np.float64)
    return np.clip(np.diff(primitive(edges)), 0, 1).astype(np.float32)


def _draw_tile(size, period, joint, base, grout, rng) -> np.ndarray:
    px, py = period
    if any(not math.isclose(size / p, round(size / p), abs_tol=1e-6) for p in period):
        raise GroundRecipeError("tile period does not divide the map size")
    x = _joint_coverage(size, px, joint[0])
    y = _joint_coverage(size, py, joint[1])
    coverage = 1 - (1 - x[None, :]) * (1 - y[:, None])
    # Stack bond; per-tile colour jitter closes with the supertile.
    rows, cols = int(round(size / py)), int(round(size / px))
    # Avoid huge tile grids for heavily reduced NPM previews: hash tile identities.
    salt = int(rng.integers(0, 2**20))
    ix = np.floor((np.arange(size) + 0.5 + px / 2) / px).astype(np.int64) % cols
    iy = np.floor((np.arange(size) + 0.5 + py / 2) / py).astype(np.int64) % rows
    shade = ((iy[:, None] * 73856093 + ix[None, :] * 19349663 + salt) % 997) / 996
    noise = _fbm(size, rng)
    face = np.array(base, dtype=np.float32) * (0.88 + 0.06 * noise[..., None] + 0.06 * shade[..., None])
    seam = np.array(grout, dtype=np.float32) * (0.88 + 0.12 * noise[..., None])
    return face * (1 - coverage[..., None]) + seam * coverage[..., None]


def _draw_grains(size, count, palette, rng, fraction_mm) -> np.ndarray:
    """Grain pitch follows fraction_mm. Below two pixels the texel is an aggregate."""
    lo, hi = fraction_mm
    colours = np.array(palette, dtype=np.float32)
    cell = size / float(count)
    if cell >= 2.0:
        shade, choice = _worley_count(size, count, len(palette), rng)
        image = colours[choice]
        grain = 0.82 + 0.18 * (1.0 - np.clip(shade / max(cell, 1.0), 0.0, 1.0))
        fleck = 0.94 + 0.06 * _fbm(size, rng)
        return image * grain[..., None] * fleck[..., None]
    return _aggregate_grains(size, count, colours, rng, float(lo), float(hi))


def _aggregate_grains(size, count, colours, rng, lo: float, hi: float) -> np.ndarray:
    """Mean of a periodic grain hash. The wavelength is one repeat divided by count."""
    samples = 4
    salt = int(rng.integers(0, 2**31 - 1))
    lo_q = int(round(lo * 1000.0))
    hi_q = int(round(hi * 1000.0))
    total = np.zeros((size, size, 3), dtype=np.float32)
    axis_y = np.arange(size, dtype=np.float64)[:, None]
    axis_x = np.arange(size, dtype=np.float64)[None, :]
    kinds = int(colours.shape[0])
    for sy in range(samples):
        for sx in range(samples):
            along = (axis_y + (sy + 0.5) / samples) / size
            across = (axis_x + (sx + 0.5) / samples) / size
            iy = np.mod(np.floor(along * count), count).astype(np.int64)
            ix = np.mod(np.floor(across * count), count).astype(np.int64)
            mixed = (iy * 73856093 + ix * 19349663 + salt + lo_q * 17 + hi_q * 131) & np.int64(0x7FFFFFFF)
            choice = (mixed % kinds).astype(np.int32)
            total += colours[choice]
    return total / float(samples * samples)


def _worley_count(size, count, colours, rng):
    cell = size / float(count)
    span = cell - 1.0 if cell > 1.0 else cell * 0.5
    jitter_y = rng.random((count, count))
    jitter_x = rng.random((count, count))
    choice_grid = rng.integers(0, colours, size=(count, count))
    ys = np.arange(size, dtype=np.float32)[:, None]
    xs = np.arange(size, dtype=np.float32)[None, :]
    cy0 = np.floor(np.arange(size, dtype=np.float64) / cell + 1e-9).astype(np.int32)[:, None]
    cx0 = np.floor(np.arange(size, dtype=np.float64) / cell + 1e-9).astype(np.int32)[None, :]
    best = np.full((size, size), np.inf, dtype=np.float32)
    choice = np.zeros((size, size), dtype=np.int32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cy = (cy0 + oy) % count
            cx = (cx0 + ox) % count
            py = (cy0 + oy) * cell + jitter_y[cy, cx] * span
            px = (cx0 + ox) * cell + jitter_x[cy, cx] * span
            dist = (ys - py) ** 2 + (xs - px) ** 2
            nearer = dist < best
            best = np.where(nearer, dist, best)
            choice = np.where(nearer, choice_grid[cy, cx], choice)
    return np.sqrt(best).astype(np.float32), choice


def _draw_particles(size, cell, palette, rng) -> np.ndarray:
    shade, choice = _worley(size, cell, len(palette), rng)
    colours = np.array(palette, dtype=np.float32)
    image = colours[choice]
    grain = 0.82 + 0.18 * (1.0 - np.clip(shade / max(cell, 1), 0.0, 1.0))
    fleck = 0.94 + 0.06 * _fbm(size, rng)
    return image * grain[..., None] * fleck[..., None]


def _draw_lawn(size, palette, rng, blade_cycles) -> np.ndarray:
    noise = _fbm(size, rng)
    warp = _fbm(size, rng)
    xs = np.arange(size, dtype=np.float32)
    blades = 0.5 + 0.5 * np.sin((xs[None, :] / size + warp * 0.01) * (2 * np.pi * float(blade_cycles)))
    colours = np.array(palette, dtype=np.float32)
    low = colours[0]
    high = colours[min(1, len(colours) - 1)]
    mix = np.clip(0.35 + 0.45 * noise + 0.20 * blades, 0.0, 1.0)
    return low + (high - low) * mix[..., None]


def _draw_ecogrid(size, cell, palette, grid_rgb, rng, band_divisor, blade_cycles) -> np.ndarray:
    grass = _draw_lawn(size, palette, rng, blade_cycles)
    ys, xs = np.indices((size, size), dtype=np.int32)
    band = max(1, cell // int(band_divisor))
    mid_x = cell // 2
    mid_y = cell // 2
    lx = xs % cell
    ly = ys % cell
    grid = (np.abs(lx - mid_x) <= band) | (np.abs(ly - mid_y) <= band)
    plastic = np.array(grid_rgb, dtype=np.float32) * (0.9 + 0.1 * _fbm(size, rng)[..., None])
    return np.where(grid[..., None], plastic, grass)


def _draw_foliage(size, cell, palette, blooms, rng, blade_cycles) -> np.ndarray:
    bed = _draw_lawn(size, palette, rng, blade_cycles)
    shade, choice = _worley(size, cell, len(blooms), rng)
    colours = np.array(blooms, dtype=np.float32)
    spot = shade < cell * 0.28
    tint = colours[choice]
    out = bed.copy()
    out[spot] = out[spot] * 0.35 + tint[spot] * 0.65
    return out


def _draw_soil(size, palette, rng) -> np.ndarray:
    noise = _fbm(size, rng)
    colours = np.array(palette, dtype=np.float32)
    low, high = colours[0], colours[min(1, len(colours) - 1)]
    mix = 0.5 + 0.5 * (noise - 0.5)
    mix = np.clip(mix, 0.25, 0.75)
    return low + (high - low) * mix[..., None]


def _worley(size, cell, colours, rng):
    count_y = size // cell
    count_x = size // cell
    jitter_y = rng.random((count_y, count_x))
    jitter_x = rng.random((count_y, count_x))
    choice_grid = rng.integers(0, colours, size=(count_y, count_x))
    ys = np.arange(size, dtype=np.float32)[:, None]
    xs = np.arange(size, dtype=np.float32)[None, :]
    cy0 = (np.arange(size) // cell)[:, None]
    cx0 = (np.arange(size) // cell)[None, :]
    best = np.full((size, size), np.inf, dtype=np.float32)
    choice = np.zeros((size, size), dtype=np.int32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cy = (cy0 + oy) % count_y
            cx = (cx0 + ox) % count_x
            py = (cy0 + oy) * cell + jitter_y[cy, cx] * (cell - 1)
            px = (cx0 + ox) * cell + jitter_x[cy, cx] * (cell - 1)
            dist = (ys - py) ** 2 + (xs - px) ** 2
            nearer = dist < best
            best = np.where(nearer, dist, best)
            choice = np.where(nearer, choice_grid[cy, cx], choice)
    return np.sqrt(best).astype(np.float32), choice


def _fbm(size, rng) -> np.ndarray:
    total = np.zeros((size, size), dtype=np.float32)
    weight = 0.0
    amplitude = 1.0
    spacing = size // 2
    while spacing >= 4:
        total += amplitude * _value_noise(size, spacing, rng)
        weight += amplitude
        amplitude *= 0.5
        spacing //= 2
    return total / weight


def _value_noise(size, spacing, rng) -> np.ndarray:
    cells = size // spacing
    grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
    grid[-1, :] = grid[0, :]
    grid[:, -1] = grid[:, 0]
    grid[-1, -1] = grid[0, 0]
    ys = np.linspace(0, cells, size, endpoint=False, dtype=np.float32)
    xs = np.linspace(0, cells, size, endpoint=False, dtype=np.float32)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3.0 - 2.0 * fy)
    fx = fx * fx * (3.0 - 2.0 * fx)
    v00 = grid[y0][:, x0]
    v01 = grid[y0][:, x0 + 1]
    v10 = grid[y0 + 1][:, x0]
    v11 = grid[y0 + 1][:, x0 + 1]
    top = v00 * (1.0 - fx) + v01 * fx
    bot = v10 * (1.0 - fx) + v11 * fx
    return top * (1.0 - fy) + bot * fy


def _carrier(size, cycles) -> np.ndarray:
    axis = np.arange(size, dtype=np.float32)
    sx = np.sin(2.0 * np.pi * cycles * axis / size)
    sy = np.sin(2.0 * np.pi * (cycles + 5) * axis / size)
    return (0.5 + 0.5 * (0.65 * sx[None, :] + 0.35 * sy[:, None])).astype(np.float32)


def _finish(image: np.ndarray, visual) -> np.ndarray:
    base = image.astype(np.float32)
    current = _u8(base)
    if _seam_ok(current):
        return current
    # Periodic lift and blur are recipe fallbacks. Blur widens a 1px joint.
    period = _positive_int(visual["micro_period_px"], "micro_period_px")
    if base.shape[0] % period != 0:
        raise GroundRecipeError("micro_period_px does not divide the map size")
    for amplitude in visual["micro_amplitudes"]:
        current = _u8(base + _micro(base.shape[0], float(amplitude), period))
        if _seam_ok(current):
            return current
    for radius in visual["blur_radii"]:
        current = _u8(_box_blur(base, _positive_int(radius, "blur_radii")))
        if _seam_ok(current):
            return current
    raise GroundRecipeError("wrap seam exceeds 1.5 times the interior median")


def _micro(size: int, amplitude: float, period: int) -> np.ndarray:
    """Periodic triangle. Same step on every column and row, including the wrap."""
    position = np.arange(size, dtype=np.float32) % period
    wave = np.where(position <= period / 2.0, position, period - position)
    wave = wave * (amplitude / (period / 2.0))
    field = 0.5 * wave[None, :] + 0.5 * wave[:, None]
    return field.astype(np.float32)[..., None]


def _seam_ok(image: np.ndarray, limit: float = 1.5) -> bool:
    """Wrap mean |RGB| <= limit * median interior adjacent step on both axes.

    Each adjacent step is averaged along the seam and across RGB. The median
    is taken over those steps, excluding the first and last.
    """
    data = np.ascontiguousarray(image).astype(np.int16)

    def _axis(seam, steps, along) -> bool:
        means = np.mean(np.abs(steps), axis=along)
        interior = means[1:-1] if means.size >= 3 else means
        median = float(np.median(interior)) if interior.size else 0.0
        seam_mean = float(np.mean(np.abs(seam)))
        return seam_mean <= limit * median

    columns = _axis(data[:, 0, :] - data[:, -1, :], data[:, 1:, :] - data[:, :-1, :], (0, 2))
    rows = _axis(data[0, :, :] - data[-1, :, :], data[1:, :, :] - data[:-1, :, :], (1, 2))
    return columns and rows


def _box_blur(image: np.ndarray, radius: int) -> np.ndarray:
    src = image.astype(np.float32)
    padded = np.pad(src, ((radius, radius), (radius, radius), (0, 0)), mode="wrap")
    integral = np.pad(padded, ((1, 0), (1, 0), (0, 0)), mode="constant")
    np.cumsum(integral, axis=0, out=integral)
    np.cumsum(integral, axis=1, out=integral)
    height, width = src.shape[:2]
    side = 2 * radius + 1
    y0 = np.arange(height)[:, None]
    x0 = np.arange(width)[None, :]
    y1 = y0 + side
    x1 = x0 + side
    total = integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]
    return total / float(side * side)


def _u8(image: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def _scale_int(value, delivery: int, size: int, label: str) -> int:
    value = _positive_int(value, label)
    if delivery % value != 0:
        raise GroundRecipeError(f"{label} {value} does not divide the map size {delivery}")
    if size == delivery:
        scaled = value
    else:
        factor = delivery // size
        if value % factor != 0:
            raise GroundRecipeError(f"{label} {value} does not divide the map size {size}")
        scaled = value // factor
    if size % scaled != 0 and label.endswith("_period_px"):
        raise GroundRecipeError(f"{label} {scaled} does not divide the map size {size}")
    if label.endswith("_cell_px") and size % scaled != 0:
        raise GroundRecipeError(f"{label} {scaled} does not divide the map size {size}")
    return scaled


def _scale_pair(value, delivery: int, size: int, label: str):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise GroundRecipeError(f"{label} must be a pair")
    return tuple(_scale_int(item, delivery, size, label) for item in value)


def _actual_size_text(recipe, slot: str) -> str:
    """Physical size the generator emits, per profile, after scale fitting."""
    body = recipe["slots"][slot]
    family = body["family"]
    parts = []
    for profile in ("npm", "vpm"):
        spec = recipe["profiles"][profile]
        px_per_m = spec["px_per_m"]
        repeat_m = spec["metres_per_repeat"]
        if family == "tile":
            facts = tile_facts(body, profile)
            face = facts["actual_face_mm"]
            joint = facts["actual_joint_mm"]
            parts.append(
                f"{profile} actual {face[0]:.2f} x {face[1]:.2f} mm face, "
                f"joint {joint[0]:.2f} x {joint[1]:.2f} mm"
            )
        elif family == "particles" and slot == "Gravel":
            count = _grain_count(body["fraction_mm"], profile)
            parts.append(f"{profile} actual pitch {repeat_m / count * 1000.0:.2f} mm")
        elif family == "lawn":
            spacing = repeat_m / float(recipe["visual"]["blade_cycles"])
            parts.append(f"{profile} actual blade spacing {spacing:.4f} m")
        elif family == "soil":
            parts.append(f"{profile} actual repeat {repeat_m:.4f} m")
        else:
            cell = body[f"{profile}_cell_px"]
            text = f"{profile} actual cell {cell / px_per_m * 1000.0:.2f} mm"
            if family == "ecogrid":
                band_px = _raster_grid_band_px(cell, recipe["visual"]["grid_band_divisor"])
                spacing = repeat_m / float(recipe["visual"]["blade_cycles"])
                text += (
                    f", band {band_px / px_per_m * 1000.0:.2f} mm, "
                    f"blade spacing {spacing:.4f} m"
                )
            elif family == "foliage":
                spacing = repeat_m / float(recipe["visual"]["blade_cycles"])
                text += f", blade spacing {spacing:.4f} m"
            parts.append(text)
    return "; ".join(parts)


def _raster_grid_band_px(cell: int, band_divisor: int) -> int:
    """Texel width of the ecogrid bar on the first row of one cell.

    The mask is abs(index - cell // 2) <= band, with band = max(1, cell // divisor).
    That bar is 2 * band + 1 texels and saturates at the cell width.
    """
    band = max(1, int(cell) // int(band_divisor))
    mid = int(cell) // 2
    if band >= mid:
        return int(cell)
    return 2 * band + 1


def _label_panel(labels, font, cell: int, pad: int, spacing: int) -> tuple[int, int]:
    """Label column and row large enough for every complete label."""
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    width = max(360, cell)
    height = cell
    for label in labels:
        box = probe.multiline_textbbox((pad, pad), label, font=font, spacing=spacing)
        width = max(width, int(box[2]) + pad)
        height = max(height, int(box[3]) + pad)
    return width, height


def _one_metre(image: np.ndarray, px_per_m) -> np.ndarray:
    if isinstance(px_per_m, bool) or not isinstance(px_per_m, (int, float)) or not math.isfinite(px_per_m):
        raise GroundRecipeError("px_per_m must be finite")
    side = int(round(float(px_per_m)))
    if side <= 0 or side > image.shape[0] or side > image.shape[1]:
        raise GroundRecipeError("map is smaller than one metre at the stated px/m")
    return np.ascontiguousarray(image[:side, :side])


def _fit(image: np.ndarray, side: int) -> Image.Image:
    picture = Image.fromarray(np.ascontiguousarray(image), "RGB")
    if picture.size != (side, side):
        picture = picture.resize((side, side), Image.Resampling.BOX)
    return picture


def _font(size: int):
    windir = os.environ.get("WINDIR", r"C:\Windows")
    path = Path(windir) / "Fonts" / "arial.ttf"
    if path.is_file():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _rng(seed: int, slot: str, profile: str, size: int):
    token = f"{seed}|{slot}|{profile}|{size}".encode("utf-8")
    mixed = int.from_bytes(hashlib.sha256(token).digest()[:8], "little")
    return np.random.default_rng(mixed)


def _resolves_to_input(out_dir: Path, recipe_path: Path) -> bool:
    recipe_key = _key(recipe_path)
    if _key(out_dir) == recipe_key or _key(out_dir) == _key(_MODULE):
        return True
    for name in ("manifest.json", "contact_sheet.jpg"):
        if _key(out_dir / name) == recipe_key:
            return True
    return False


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(_REPO)
    except ValueError:
        return False
    return True


def _same(left, right) -> bool:
    return _key(left) == _key(right)


def _key(path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(Path(path).resolve())))


def _token(value, label: str) -> None:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise GroundRecipeError(f"{label} must be Latin letters, digits or underscore")


def _require_key(body: dict, key: str) -> None:
    if key not in body:
        raise GroundRecipeError(f"missing {key}")


def _positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GroundRecipeError(f"{label} must be a positive integer")
    return value


def _positive_pair(value, label: str) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise GroundRecipeError(f"{label} must be a pair")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or item <= 0:
            raise GroundRecipeError(f"{label} must be finite and positive")


def _rgb(value, label: str) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise GroundRecipeError(f"missing {label}")
    for channel in value:
        if isinstance(channel, bool) or not isinstance(channel, int) or channel < 0 or channel > 255:
            raise GroundRecipeError(f"{label} must be 8-bit RGB")


def _palette(body) -> None:
    _require_key(body, "palette")
    colours = body["palette"]
    if not isinstance(colours, list) or len(colours) < 2:
        raise GroundRecipeError("palette is missing")
    for colour in colours:
        _rgb(colour, "palette")


if __name__ == "__main__":
    sys.exit(main())
