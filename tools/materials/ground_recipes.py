"""Procedural Ground diffuse maps for Vatutino (issue 319, [D117], [D097], GND-11).

Pillow and numpy only. Colours and snapped grid periods that are not in the
SPOZU are marked provisional on each slot. Delivery writes only the version
folder C:/x/vatutino-ground-textures/v001.
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
from PIL import Image, ImageDraw, ImageFont

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
    image = _draw(body, slot, profile, size, delivery_size, rng)
    return _finish(image)


def png_bytes(image: np.ndarray) -> bytes:
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise GroundRecipeError("map must be 8-bit RGB without alpha")
    buffer = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(image), "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def contact_label(recipe, slot: str) -> str:
    body = recipe["slots"][slot]
    return f"{slot}  {body['tile_size_label']}  PROVISIONAL"


def build_contact_sheet(recipe, rendered: dict) -> Image.Image:
    px_per_m = recipe["profiles"]["vpm"]["px_per_m"]
    slots = [slot for slot in CANONICAL_SLOTS if slot in rendered]
    if slots != list(CANONICAL_SLOTS):
        raise GroundRecipeError("contact sheet is missing a slot")
    crops = [_one_metre(rendered[slot]["vpm"], px_per_m) for slot in slots]
    cell = crops[0].shape[0]
    label_w = max(360, cell)
    sheet = Image.new("RGB", (cell * 3 + label_w, cell * len(slots)), (244, 244, 240))
    draw = ImageDraw.Draw(sheet)
    font = _font(max(16, min(32, cell // 16)))
    for index, slot in enumerate(slots):
        y = index * cell
        sheet.paste(_fit(rendered[slot]["npm"], cell), (0, y))
        tiled = np.tile(np.ascontiguousarray(rendered[slot]["npm"]), (2, 2, 1))
        sheet.paste(_fit(tiled, cell), (cell, y))
        sheet.paste(Image.fromarray(crops[index], "RGB"), (cell * 2, y))
        draw.multiline_text(
            (cell * 3 + 16, y + 16),
            contact_label(recipe, slot),
            fill=(24, 24, 24),
            font=font,
            spacing=6,
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
        "provisional": body["provisional"],
        "seed": recipe["seed"],
        "sha256": hashlib.sha256(png_bytes(np.ascontiguousarray(image).astype(np.uint8))).hexdigest(),
    }


def write_delivery(recipe_path, out_dir) -> dict:
    recipe_path = Path(recipe_path)
    out_dir = Path(out_dir)
    if _resolves_to_input(out_dir, recipe_path):
        raise GroundRecipeError("output path resolves to an input")
    if _inside_repo(out_dir):
        raise GroundRecipeError("output directory is inside the repository")
    if not _same(out_dir, DELIVERY_DIR):
        raise GroundRecipeError(
            "output directory is not the version folder C:/x/vatutino-ground-textures/v001"
        )
    if out_dir.exists() and any(out_dir.iterdir()):
        raise GroundRecipeError("version folder already contains files")
    recipe = load_recipe(recipe_path)
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
    manifest = {"address": recipe["address"], "seed": recipe["seed"], "maps": entries}
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise GroundRecipeError("version folder already contains files")
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.iterdir()):
        raise GroundRecipeError("version folder already contains files")
    for name, payload in files:
        (out_dir / name).write_bytes(payload)
    (out_dir / "contact_sheet.jpg").write_bytes(sheet_buffer.getvalue())
    (out_dir / "manifest.json").write_bytes(manifest_bytes)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ground_recipes")
    sub = parser.add_subparsers(dest="command", required=True)
    deliver = sub.add_parser("deliver")
    deliver.add_argument("--recipe", default=str(_DEFAULT_RECIPE))
    deliver.add_argument("--out", required=True)
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code) if exc.code else 0
    try:
        write_delivery(args.recipe, args.out)
    except GroundRecipeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("wrote 20 ground diffuse maps")
    return 0


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
    flags = body["provisional"]
    if not isinstance(flags, list) or not flags:
        raise GroundRecipeError(f"{name} provisional flags are missing")
    for flag in flags:
        if not isinstance(flag, dict):
            raise GroundRecipeError(f"{name} provisional flag must be an object")
        _require_key(flag, "field")
        _require_key(flag, "reason")
        if not isinstance(flag["field"], str) or not flag["field"].strip():
            raise GroundRecipeError(f"{name} provisional field is empty")
        if not isinstance(flag["reason"], str) or len(flag["reason"].strip()) < 8:
            raise GroundRecipeError(f"{name} provisional reason is empty")
    if family == "tile":
        _require_key(body, "nominal_tile_mm")
        _positive_pair(body["nominal_tile_mm"], "nominal_tile_mm")
        _rgb(body.get("base_rgb"), "base_rgb")
        _rgb(body.get("joint_rgb"), "joint_rgb")
        _period_pair(body, "npm")
        _period_pair(body, "vpm")
        _joint(body, "npm")
        _joint(body, "vpm")
    elif family == "particles":
        _palette(body)
        _cell(body, "npm")
        _cell(body, "vpm")
        if name == "Gravel":
            _require_key(body, "fraction_mm")
            _positive_pair(body["fraction_mm"], "fraction_mm")
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


def _joint(body, profile: str) -> None:
    key = f"{profile}_joint_px"
    _require_key(body, key)
    joint = _positive_int(body[key], key)
    period = body[f"{profile}_period_px"]
    if joint >= min(period) / 2:
        raise GroundRecipeError(f"{key} leaves no tile face")


def _cell(body, profile: str) -> None:
    key = f"{profile}_cell_px"
    _require_key(body, key)
    value = _positive_int(body[key], key)
    size = _PROFILE_SIZE[profile]
    if size % value != 0:
        raise GroundRecipeError(f"{key} {value} does not divide the map size {size}")


def _draw(body, slot: str, profile: str, size: int, delivery_size: int, rng) -> np.ndarray:
    family = body["family"]
    if family == "tile":
        period = _scale_pair(body[f"{profile}_period_px"], delivery_size, size, f"{profile}_period_px")
        joint = _scale_int(body[f"{profile}_joint_px"], delivery_size, size, f"{profile}_joint_px")
        image = _draw_tile(size, period, joint, body["base_rgb"], body["joint_rgb"], rng)
    elif family in {"particles", "foliage", "ecogrid"}:
        cell = _scale_int(body[f"{profile}_cell_px"], delivery_size, size, f"{profile}_cell_px")
        if family == "particles":
            image = _draw_particles(size, cell, body["palette"], rng)
        elif family == "foliage":
            image = _draw_foliage(size, cell, body["palette"], body["bloom_palette"], rng)
        else:
            image = _draw_ecogrid(size, cell, body["palette"], body["grid_rgb"], rng)
    elif family == "lawn":
        image = _draw_lawn(size, body["palette"], rng)
    else:
        image = _draw_soil(size, body["palette"], rng)
    cycles = 11 + CANONICAL_SLOTS.index(slot) + (0 if profile == "npm" else 3)
    carrier = _carrier(size, cycles)
    return image * (0.90 + 0.10 * carrier[..., None])


def _draw_tile(size, period, joint, base, grout, rng) -> np.ndarray:
    px, py = period
    ys, xs = np.indices((size, size), dtype=np.int32)
    row = ys // py
    rows = size // py
    # A 3-row bond shares an offset on the first and last row only when the
    # row count is 1 mod 3. Otherwise the vertical joint stays on one column
    # so the period closes across the row wrap.
    if px >= 8 and rows % 3 == 1:
        jitter = (row % 3) - 1
    else:
        jitter = 0
    lx = xs % px
    ly = ys % py
    jx = (px - joint) // 2 + jitter
    jy = (py - joint) // 2
    mask = ((lx >= jx) & (lx < jx + joint)) | ((ly >= jy) & (ly < jy + joint))
    noise = _fbm(size, rng)
    face = np.array(base, dtype=np.float32) * (0.86 + 0.14 * noise[..., None])
    seam = np.array(grout, dtype=np.float32) * (0.78 + 0.22 * _fbm(size, rng)[..., None])
    return np.where(mask[..., None], seam, face)


def _draw_particles(size, cell, palette, rng) -> np.ndarray:
    shade, choice = _worley(size, cell, len(palette), rng)
    colours = np.array(palette, dtype=np.float32)
    image = colours[choice]
    grain = 0.82 + 0.18 * (1.0 - np.clip(shade / max(cell, 1), 0.0, 1.0))
    fleck = 0.94 + 0.06 * _fbm(size, rng)
    return image * grain[..., None] * fleck[..., None]


def _draw_lawn(size, palette, rng) -> np.ndarray:
    noise = _fbm(size, rng)
    warp = _fbm(size, rng)
    xs = np.arange(size, dtype=np.float32)
    blades = 0.5 + 0.5 * np.sin((xs[None, :] / size + warp * 0.01) * (2 * np.pi * 37))
    colours = np.array(palette, dtype=np.float32)
    low = colours[0]
    high = colours[min(1, len(colours) - 1)]
    mix = np.clip(0.35 + 0.45 * noise + 0.20 * blades, 0.0, 1.0)
    return low + (high - low) * mix[..., None]


def _draw_ecogrid(size, cell, palette, grid_rgb, rng) -> np.ndarray:
    grass = _draw_lawn(size, palette, rng)
    ys, xs = np.indices((size, size), dtype=np.int32)
    band = max(1, cell // 12)
    mid_x = cell // 2
    mid_y = cell // 2
    lx = xs % cell
    ly = ys % cell
    grid = (np.abs(lx - mid_x) <= band) | (np.abs(ly - mid_y) <= band)
    plastic = np.array(grid_rgb, dtype=np.float32) * (0.9 + 0.1 * _fbm(size, rng)[..., None])
    return np.where(grid[..., None], plastic, grass)


def _draw_foliage(size, cell, palette, blooms, rng) -> np.ndarray:
    bed = _draw_lawn(size, palette, rng)
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


def _finish(image: np.ndarray) -> np.ndarray:
    base = image.astype(np.float32)
    current = _u8(base)
    if _seam_ok(current):
        return current
    for radius in (1, 2, 4):
        current = _u8(_box_blur(base, radius))
        if _seam_ok(current):
            return current
    for amplitude in (6, 12, 18):
        lifted = base + _micro(base.shape[0], amplitude)
        current = _u8(lifted)
        if _seam_ok(current):
            return current
        current = _u8(_box_blur(lifted, 1))
        if _seam_ok(current):
            return current
    raise GroundRecipeError("wrap seam exceeds 1.5 times the interior median")


def _micro(size: int, amplitude: float) -> np.ndarray:
    """Periodic 4px triangle. Same step on every column and row, including the wrap."""
    period = 4
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
