"""Pack a MAF material list into one square atlas and a UV-rect map.

Pattern / Scope (docs/agents/REVIEW_CHECKLIST.md Q1):
Marked explicit new-case: shared NPM GroundEl atlas packing with buddy allocator
and patterned growth, not a registered/proven pattern (registry docs/domain/patterns/INDEX.md).

Normative References (docs/domain/uv-textures.md):
- reg p.10 §5.12: GroundEl uses one texture set for all elements, <= 512x512 px.
- reg p.9 §5.4: Padding >= 8 px between neighbouring islands with unique images.
- reg p.9 §5.1: Textures delivered as PNG (embedded in FBX).
- reg p.9 §5.5: Alpha channel forbidden in NPM textures.

Algorithm Choices vs Regulation:
The regulation defines delivery constraints (PNG up to 512x512, no alpha, >= 8 px padding).
The quadtree buddy allocator for power-of-two square slots, largest-first placement,
iterative doubling growth of patterned slots into leftover space, and edge pixel
clamping in padding gutters are algorithmic implementation choices, not normative rules.
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

CELL = 64
ATLAS_SIZE = 512
MIN_PADDING = 8
DEFAULT_ATLAS = ATLAS_SIZE
DEFAULT_PADDING = MIN_PADDING
NEUTRAL = (128, 128, 128)

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_HEX_RE = re.compile(r"^#([0-9A-Fa-f]{6})$")
_RAL_RE = re.compile(r"^RAL\s*(\d{4})$", re.IGNORECASE)

__all__ = [
    "AtlasDoesNotFit",
    "AtlasError",
    "Material",
    "Slot",
    "build_atlas",
    "load_material_list",
    "main",
    "pack_uniform_tiles",
    "plan_atlas",
    "render_atlas",
    "uv_map",
]


class AtlasError(ValueError):
    """Invalid material list, colour, padding, or output path."""


class AtlasDoesNotFit(AtlasError):
    """Minimum slot area is larger than the atlas."""


class Material:
    """One atlas entry. ``size`` is the minimum slot, not the grown size."""

    def __init__(self, name, kind, size, index, color=None, texture=None):
        self.name = name
        self.kind = kind
        self.size = size
        self.index = index
        self.color = color
        self.texture = texture


class Slot:
    """Placed square. ``x`` and ``y`` are the top-left corner in pixels."""

    def __init__(self, name, kind, x, y, size):
        self.name = name
        self.kind = kind
        self.x = x
        self.y = y
        self.size = size


def load_material_list(path: str | Path) -> tuple[list[Material], int, int]:
    """Read a material-list JSON file.

    Texture paths are resolved relative to the JSON file's folder.
    """

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AtlasError(f"material list is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise AtlasError(f"material list cannot be read: {exc}") from exc
    if not isinstance(payload, dict):
        raise AtlasError("material list must be a JSON object")

    atlas_size = _optional_int(payload, "atlas_size", DEFAULT_ATLAS)
    padding_px = _optional_int(payload, "padding_px", DEFAULT_PADDING)
    raw_items = payload.get("materials")
    if not isinstance(raw_items, list):
        raise AtlasError("material list requires a materials array")
    if not raw_items:
        raise AtlasError("material list is empty")

    materials: list[Material] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items):
        materials.append(_parse_material(item, index, source.parent, seen))
    return materials, atlas_size, padding_px


def plan_atlas(
    materials: list[Material],
    atlas_size: int = DEFAULT_ATLAS,
    padding_px: int = DEFAULT_PADDING,
) -> list[Slot]:
    """Place one power-of-two square per material, largest first.

    Patterned slots then grow by doubling the current smallest one whenever
    the total area still fits and the buddy allocator can place every slot.
    """

    _validate_layout_args(materials, atlas_size, padding_px)
    atlas_area = atlas_size * atlas_size
    if sum(material.size * material.size for material in materials) > atlas_area:
        raise AtlasDoesNotFit(_does_not_fit_message(materials, atlas_size))

    size_of = {material.index: material.size for material in materials}
    done: set[int] = set()
    patterned = [material for material in materials if material.kind == "patterned"]
    while True:
        growable = [
            material
            for material in patterned
            if material.index not in done and size_of[material.index] * 2 <= atlas_size
        ]
        if not growable:
            break
        growable.sort(key=lambda material: (size_of[material.index], material.index))
        chosen = growable[0]
        trial = dict(size_of)
        trial[chosen.index] *= 2
        trial_items = [(material.index, trial[material.index]) for material in materials]
        trial_area = sum(side * side for _, side in trial_items)
        if trial_area <= atlas_area and _place(trial_items, atlas_size) is not None:
            size_of = trial
        else:
            done.add(chosen.index)

    smallest = min(size_of.values())
    if padding_px >= smallest:
        names = ", ".join(
            material.name
            for material in materials
            if size_of[material.index] == smallest
        )
        raise AtlasError(
            f"padding_px {padding_px} must be smaller than the smallest slot "
            f"({smallest}: {names})"
        )

    items = [(material.index, size_of[material.index]) for material in materials]
    placed = _place(items, atlas_size)
    if placed is None:
        raise AtlasError("internal packer failed although the total area fits")
    return [
        Slot(
            name=material.name,
            kind=material.kind,
            x=placed[material.index][0],
            y=placed[material.index][1],
            size=size_of[material.index],
        )
        for material in materials
    ]


def render_atlas(
    slots: list[Slot],
    materials: list[Material],
    atlas_size: int,
    padding_px: int,
) -> Image.Image:
    """Rasterise slots. Patterned gutters repeat the content edge."""

    by_name = {material.name: material for material in materials}
    if len(by_name) != len(list(materials)):
        raise AtlasError("material names must be unique")
    canvas = np.full((atlas_size, atlas_size, 3), NEUTRAL, dtype=np.uint8)
    inset = padding_px // 2
    for slot in slots:
        material = by_name.get(slot.name)
        if material is None:
            raise AtlasError(f"material {slot.name!r}: missing from the material list")
        if material.kind == "solid":
            if material.color is None:
                raise AtlasError(f"material {material.name!r}: solid material requires a color")
            canvas[slot.y:slot.y + slot.size, slot.x:slot.x + slot.size] = material.color
            continue
        if material.kind != "patterned":
            raise AtlasError(f"material {material.name!r}: kind must be 'solid' or 'patterned'")
        if material.texture is None:
            raise AtlasError(f"material {material.name!r}: patterned material requires a texture")
        content_w = slot.size - 2 * inset
        if content_w <= 0:
            raise AtlasError(
                f"material {material.name!r}: padding_px {padding_px} leaves no content"
            )
        block = _pattern_block(material.texture, content_w, inset)
        canvas[slot.y:slot.y + slot.size, slot.x:slot.x + slot.size] = block
    return Image.fromarray(canvas, "RGB")


def uv_map(slots: list[Slot], atlas_size: int, padding_px: int) -> dict:
    """Normalised content rects with V origin at the bottom of the atlas."""

    materials: dict[str, dict] = {}
    for slot in slots:
        cx, cy, cw, ch = _content_box(slot.x, slot.y, slot.size, padding_px)
        materials[slot.name] = {
            "kind": slot.kind,
            "slot_px": [slot.x, slot.y, slot.size, slot.size],
            "content_px": [cx, cy, cw, ch],
            "uv": [
                cx / atlas_size,
                1 - (cy + ch) / atlas_size,
                (cx + cw) / atlas_size,
                1 - cy / atlas_size,
            ],
        }
    return {
        "atlas_size": atlas_size,
        "padding_px": padding_px,
        "v_origin": "bottom",
        "materials": materials,
    }


def build_atlas(list_path: str | Path, out_png: str | Path, out_json: str | Path) -> dict:
    """Plan, render, and write the PNG and UV JSON. Returns the UV map."""

    materials, atlas_size, padding_px = load_material_list(list_path)
    _reject_aliased_outputs(list_path, out_png, out_json, materials)
    slots = plan_atlas(materials, atlas_size, padding_px)
    image = render_atlas(slots, materials, atlas_size, padding_px)
    mapping = uv_map(slots, atlas_size, padding_px)
    png_path = Path(out_png)
    json_path = Path(out_json)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path, format="PNG")
    json_path.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    return mapping


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Prints ``error: ...`` and returns 2 on AtlasError."""

    parser = argparse.ArgumentParser(
        description="Pack a MAF material list into one 512 atlas and a UV map"
    )
    parser.add_argument("list_json", help="JSON material list")
    parser.add_argument("--out-png", required=True, help="output atlas PNG")
    parser.add_argument("--out-json", required=True, help="output UV JSON")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing output files",
    )
    args = parser.parse_args(argv)
    try:
        if not args.force:
            for raw in (args.out_png, args.out_json):
                if Path(raw).exists():
                    raise AtlasError(
                        f"refusing to overwrite existing output {raw}; pass --force to replace it"
                    )
        mapping = build_atlas(args.list_json, args.out_png, args.out_json)
    except AtlasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    count = len(mapping["materials"])
    size = mapping["atlas_size"]
    print(f"atlas {size}x{size}: {count} materials -> {args.out_png}, {args.out_json}")
    return 0


def _optional_int(payload: dict, key: str, default: int) -> int:
    if key not in payload:
        return default
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise AtlasError(f"{key} must be an integer")
    return value


def _parse_material(item: object, index: int, base: Path, seen: set[str]) -> Material:
    if not isinstance(item, dict):
        raise AtlasError(f"material at index {index} is not an object")
    name = item.get("name")
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise AtlasError(
            f"material {name!r}: name must be non-empty and use only "
            "Latin letters, digits, underscore or hyphen"
        )
    if name in seen:
        raise AtlasError(f"material {name!r}: duplicate name")
    seen.add(name)

    kind = item.get("kind")
    if kind not in ("solid", "patterned"):
        raise AtlasError(f"material {name!r}: kind must be 'solid' or 'patterned'")

    if kind == "solid":
        size = _optional_size(name, item, 64)
        if size not in (64, 128):
            raise AtlasError(f"material {name!r}: solid size must be 64 or 128, got {size}")
        if "color" not in item:
            raise AtlasError(f"material {name!r}: solid material requires a color")
        return Material(
            name=name,
            kind=kind,
            size=size,
            index=index,
            color=_parse_color(name, item["color"]),
        )

    size = _optional_size(name, item, 128)
    if size < 128 or not _is_pow2(size):
        raise AtlasError(
            f"material {name!r}: patterned size must be a power of two >= 128, got {size}"
        )
    texture = item.get("texture")
    if not isinstance(texture, str) or not texture.strip():
        raise AtlasError(f"material {name!r}: patterned material requires a texture")
    texture_path = Path(texture)
    if not texture_path.is_absolute():
        texture_path = base / texture_path
    texture_path = texture_path.resolve()
    if not texture_path.is_file():
        raise AtlasError(f"material {name!r}: texture file not found: {texture_path}")
    return Material(name=name, kind=kind, size=size, index=index, texture=texture_path)


def _optional_size(name: str, item: dict, default: int) -> int:
    if "size" not in item:
        return default
    value = item["size"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise AtlasError(f"material {name!r}: size must be an integer")
    return value


def _parse_color(name: str, value: object) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise AtlasError(f"material {name!r}: bad hex color {value!r}")
    text = value.strip()
    hex_match = _HEX_RE.fullmatch(text)
    if hex_match:
        digits = hex_match.group(1)
        return (
            int(digits[0:2], 16),
            int(digits[2:4], 16),
            int(digits[4:6], 16),
        )
    ral_match = _RAL_RE.fullmatch(text)
    if ral_match:
        code = ral_match.group(1)
        table = _ral_colors().get(code)
        if table is None:
            raise AtlasError(
                f"material {name!r}: unknown RAL code {code}; provide a hex value (#RRGGBB)"
            )
        return _parse_color(name, table)
    raise AtlasError(f"material {name!r}: bad hex color {text!r}")


def _ral_colors() -> dict[str, str]:
    path = Path(__file__).with_name("ral_classic.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AtlasError(f"RAL table cannot be read: {exc}") from exc
    colors = payload.get("colors") if isinstance(payload, dict) else None
    if not isinstance(colors, dict):
        raise AtlasError("RAL table requires a colors object")
    return {str(code): hex_value for code, hex_value in colors.items()}


def _validate_layout_args(materials: list[Material], atlas_size: int, padding_px: int) -> None:
    if not materials:
        raise AtlasError("material list is empty")
    indexes = [material.index for material in materials]
    if len(set(indexes)) != len(indexes):
        raise AtlasError("material indexes must be unique")
    if isinstance(atlas_size, bool) or not isinstance(atlas_size, int):
        raise AtlasError("atlas_size must be an integer")
    if atlas_size != ATLAS_SIZE:
        raise AtlasError(
            f"atlas_size must be {ATLAS_SIZE} "
            f"(the shared MAF atlas is {ATLAS_SIZE}x{ATLAS_SIZE}), got {atlas_size}"
        )
    if isinstance(padding_px, bool) or not isinstance(padding_px, int):
        raise AtlasError(f"padding_px must be an even integer >= {MIN_PADDING}")
    if padding_px < MIN_PADDING or padding_px % 2 != 0:
        raise AtlasError(
            f"padding_px must be an even integer >= {MIN_PADDING}, got {padding_px}"
        )
    for material in materials:
        if material.kind not in ("solid", "patterned"):
            raise AtlasError(f"material {material.name!r}: kind must be 'solid' or 'patterned'")
        if isinstance(material.size, bool) or not isinstance(material.size, int) or not _is_pow2(material.size):
            raise AtlasError(f"material {material.name!r}: slot size must be a power of two")
        if material.kind == "solid" and material.size not in (64, 128):
            raise AtlasError(
                f"material {material.name!r}: solid size must be 64 or 128, got {material.size}"
            )
        if material.kind == "patterned" and material.size < 128:
            raise AtlasError(
                f"material {material.name!r}: patterned size must be a power of two >= 128, "
                f"got {material.size}"
            )


def _reject_aliased_outputs(
    list_path: str | Path,
    out_png: str | Path,
    out_json: str | Path,
    materials: list[Material],
) -> None:
    """Refuse one destination used twice, and refuse writing over an input."""

    if _same_destination(out_png, out_json):
        raise AtlasError(
            f"output PNG {out_png} and output JSON {out_json} are the same destination"
        )
    for output in (out_png, out_json):
        if _same_destination(output, list_path):
            raise AtlasError(f"output {output} is the input material list {list_path}")
        for material in materials:
            if material.texture is None:
                continue
            if _same_destination(output, material.texture):
                raise AtlasError(
                    f"output {output} is the source texture of material {material.name!r}"
                )


def _same_destination(left: str | Path, right: str | Path) -> bool:
    """True when both paths name one file, including ``..`` and case aliases."""

    if _path_forms(left) & _path_forms(right):
        return True
    left_path = Path(left)
    right_path = Path(right)
    if not left_path.exists() or not right_path.exists():
        return False
    try:
        return os.path.samefile(left_path, right_path)
    except OSError:
        return False


def _path_forms(path: str | Path) -> set[str]:
    text = os.fspath(path)
    forms = {os.path.normcase(os.path.abspath(text))}
    try:
        resolved = os.fspath(Path(text).resolve())
    except OSError:
        return forms
    forms.add(os.path.normcase(os.path.abspath(resolved)))
    return forms


def _does_not_fit_message(materials: list[Material], atlas_size: int) -> str:
    cell = CELL * CELL
    needed = sum(material.size * material.size for material in materials) // cell
    available = (atlas_size * atlas_size) // cell
    overflow = needed - available
    shrinks: list[str] = []
    for material in materials:
        if material.kind == "solid" and material.size == 128:
            shrinks.append(f"{material.name} -> 64 frees 3 cells")
        elif material.kind == "patterned" and material.size > 128:
            half = material.size // 2
            shrinks.append(f"{material.name} {material.size} -> {half} (half)")
    if shrinks:
        advice = "shrink: " + "; ".join(shrinks)
    else:
        names = ", ".join(material.name for material in materials)
        advice = (
            "shrink by removing or merging materials "
            f"(e.g. solids with identical colour): {names}"
        )
    return (
        f"atlas does not fit: needed {needed} cells of 64x64, "
        f"available {available}, overflow {overflow}; {advice}"
    )


def _place(items: list[tuple[int, int]], atlas_size: int) -> dict[int, tuple[int, int]] | None:
    """Quadtree buddy allocation. Largest square first, then input index.

    Free blocks stay squares whose sides are powers of two. Splitting never
    goes below the size currently being placed, so a set whose area fits can
    always be placed.
    """

    free: dict[int, list[tuple[int, int]]] = {atlas_size: [(0, 0)]}

    def take(need: int) -> tuple[int, int] | None:
        if need <= 0 or need > atlas_size or not _is_pow2(need):
            return None
        size = need
        while size <= atlas_size and not free.get(size):
            size *= 2
        if size > atlas_size or not free.get(size):
            return None
        while size > need:
            x, y = free[size].pop()
            half = size // 2
            children = free.setdefault(half, [])
            children.append((x + half, y + half))
            children.append((x, y + half))
            children.append((x + half, y))
            children.append((x, y))
            size = half
        return free[need].pop()

    placed: dict[int, tuple[int, int]] = {}
    for index, size in sorted(items, key=lambda item: (-item[1], item[0])):
        origin = take(size)
        if origin is None:
            return None
        placed[index] = origin
    return placed


def _pattern_block(texture: Path, content: int, inset: int) -> np.ndarray:
    with Image.open(texture) as source:
        resized = source.convert("RGB").resize((content, content), Image.Resampling.LANCZOS)
    block = np.asarray(resized, dtype=np.uint8)
    if inset:
        block = np.pad(block, ((inset, inset), (inset, inset), (0, 0)), mode="edge")
    return np.ascontiguousarray(block)


def _content_box(x: int, y: int, size: int, padding_px: int) -> tuple[int, int, int, int]:
    inset = padding_px // 2
    return x + inset, y + inset, size - padding_px, size - padding_px


def _is_pow2(value: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0 and value & (value - 1) == 0


def pack_uniform_tiles(items, atlas_size, *, padding_px=0, min_long_side=256) -> dict:
    """Pack every tile into one atlas, scaling all of them by the same factor.

    Extension of the MAF buddy packer for Flora (#217): one bin, never a second
    atlas. Rectangles keep their aspect ratio. ``scale_factor`` is
    ``scale_numerator / scale_denominator`` and is at most 1. Pixel sizes are
    ``source * scale_numerator // scale_denominator``. A tile whose longer side
    is below ``min_long_side`` is listed in ``warnings`` and still packed.
    """

    parsed = _parse_uniform_items(items)
    _validate_uniform_args(atlas_size, padding_px, min_long_side)
    longest = max(max(item["width"], item["height"]) for item in parsed)
    low = max(_min_numerator(item["width"], item["height"], longest) for item in parsed)
    best_mid = None
    best_placed = None
    high = longest
    while low <= high:
        mid = (low + high) // 2
        placed = _try_place_uniform(parsed, mid, longest, atlas_size, padding_px)
        if placed is None:
            high = mid - 1
        else:
            best_mid = mid
            best_placed = placed
            low = mid + 1
    if best_mid is None or best_placed is None:
        raise AtlasError(
            "tiles do not fit in one atlas at a shared scale with every tile at least "
            "1 px; a second atlas is not created"
        )
    slots = []
    warnings: list[str] = []
    inset = padding_px // 2
    for item in parsed:
        slot_x, slot_y = best_placed[item["key"]]
        content_w = item["width"] * best_mid // longest
        content_h = item["height"] * best_mid // longest
        slot = {
            "key": item["key"],
            "x": slot_x,
            "y": slot_y,
            "w": content_w + padding_px,
            "h": content_h + padding_px,
            "content_x": slot_x + inset,
            "content_y": slot_y + inset,
            "content_w": content_w,
            "content_h": content_h,
            "source_w": item["width"],
            "source_h": item["height"],
        }
        slots.append(slot)
        longer_side = max(content_w, content_h)
        if longer_side < min_long_side:
            warnings.append(
                f"{item['key']} longer side {longer_side} px is below {min_long_side} px"
            )
    return {
        "atlas_count": 1,
        "atlas_size": atlas_size,
        "scale_factor": best_mid / longest,
        "scale_numerator": best_mid,
        "scale_denominator": longest,
        "padding_px": padding_px,
        "warnings": warnings,
        "slots": slots,
    }


def _parse_uniform_items(items) -> list[dict]:
    if isinstance(items, (str, bytes)) or not isinstance(items, (list, tuple)):
        raise AtlasError("tile list must be a list of {key, width, height}")
    if not items:
        raise AtlasError("tile list is empty")
    parsed = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AtlasError(f"tile at index {index} is not an object")
        key = item.get("key")
        if isinstance(key, bool) or key is None or isinstance(key, float):
            raise AtlasError(f"tile at index {index} has an invalid key")
        if not isinstance(key, (str, int)):
            raise AtlasError(f"tile at index {index} has an invalid key")
        if isinstance(key, str) and not key:
            raise AtlasError(f"tile at index {index} has an empty key")
        identity = f"{type(key).__name__}:{key}"
        if identity in seen:
            raise AtlasError(f"duplicate tile key {key!r}")
        seen.add(identity)
        width = _positive_px(item.get("width"), f"tile {key!r} width")
        height = _positive_px(item.get("height"), f"tile {key!r} height")
        parsed.append({"key": key, "width": width, "height": height})
    return parsed


def _positive_px(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AtlasError(f"{label} must be a positive integer")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AtlasError(f"{label} must be finite")
        raise AtlasError(f"{label} must be an integer")
    if value <= 0:
        raise AtlasError(f"{label} must be a positive integer")
    return value


def _validate_uniform_args(atlas_size, padding_px, min_long_side) -> None:
    if isinstance(atlas_size, bool) or not isinstance(atlas_size, int) or atlas_size <= 0:
        raise AtlasError("atlas_size must be a positive integer")
    if isinstance(padding_px, bool) or not isinstance(padding_px, int) or padding_px < 0:
        raise AtlasError("padding_px must be an even integer >= 0")
    if padding_px % 2 != 0:
        raise AtlasError(f"padding_px must be an even integer >= 0, got {padding_px}")
    if isinstance(min_long_side, bool) or not isinstance(min_long_side, int) or min_long_side <= 0:
        raise AtlasError("min_long_side must be a positive integer")


def _min_numerator(width: int, height: int, longest: int) -> int:
    need = 1
    for dim in (width, height):
        need = max(need, (longest + dim - 1) // dim)
    return need


def _try_place_uniform(items, mid, longest, atlas_size, padding_px):
    rects = []
    for item in items:
        content_w = item["width"] * mid // longest
        content_h = item["height"] * mid // longest
        if content_w < 1 or content_h < 1:
            return None
        slot_w = content_w + padding_px
        slot_h = content_h + padding_px
        if slot_w > atlas_size or slot_h > atlas_size:
            return None
        rects.append((item["key"], slot_w, slot_h))
    for placer in (_place_equal_grid, _place_shelf, _place_shelf_by_width, _place_maxrects):
        placed = placer(rects, atlas_size)
        if placed is not None and _placement_is_valid(placed, rects, atlas_size):
            return placed
    return None


def _place_equal_grid(rects, atlas_size):
    width = rects[0][1]
    height = rects[0][2]
    if any(rect[1] != width or rect[2] != height for rect in rects):
        return None
    count = len(rects)
    for columns in range(1, count + 1):
        rows = (count + columns - 1) // columns
        if columns * width <= atlas_size and rows * height <= atlas_size:
            placed = {}
            for index, (key, _width, _height) in enumerate(sorted(rects, key=lambda rect: str(rect[0]))):
                placed[key] = ((index % columns) * width, (index // columns) * height)
            return placed
    return None


def _place_shelf(rects, atlas_size):
    return _place_rows(sorted(rects, key=lambda rect: (-rect[2], -rect[1], str(rect[0]))), atlas_size)


def _place_shelf_by_width(rects, atlas_size):
    return _place_rows(sorted(rects, key=lambda rect: (-rect[1], -rect[2], str(rect[0]))), atlas_size)


def _place_rows(order, atlas_size):
    x = 0
    y = 0
    row_h = 0
    placed = {}
    for key, width, height in order:
        if width > atlas_size or height > atlas_size:
            return None
        if x > 0 and x + width > atlas_size:
            y += row_h
            x = 0
            row_h = 0
        if y + height > atlas_size:
            return None
        placed[key] = (x, y)
        x += width
        row_h = max(row_h, height)
    return placed


def _place_maxrects(rects, atlas_size):
    free = [(0, 0, atlas_size, atlas_size)]
    placed = {}
    for key, width, height in sorted(rects, key=lambda rect: (-max(rect[1], rect[2]), -rect[1] * rect[2], str(rect[0]))):
        best = None
        best_score = None
        for index, (fx, fy, fw, fh) in enumerate(free):
            if width <= fw and height <= fh:
                leftover_w = fw - width
                leftover_h = fh - height
                score = (min(leftover_w, leftover_h), max(leftover_w, leftover_h), index)
                if best_score is None or score < best_score:
                    best_score = score
                    best = (fx, fy)
        if best is None:
            return None
        x, y = best
        placed[key] = (x, y)
        free = _prune_free(_split_free(free, x, y, width, height))
    return placed


def _split_free(free, x, y, width, height):
    placed = (x, y, width, height)
    output = []
    for rect in free:
        if not _rect_overlaps(rect, placed):
            output.append(rect)
            continue
        fx, fy, fw, fh = rect
        if x > fx:
            output.append((fx, fy, x - fx, fh))
        if x + width < fx + fw:
            output.append((x + width, fy, fx + fw - (x + width), fh))
        if y > fy:
            output.append((fx, fy, fw, y - fy))
        if y + height < fy + fh:
            output.append((fx, y + height, fw, fy + fh - (y + height)))
    return output


def _prune_free(free):
    unique = []
    for rect in free:
        if rect[2] <= 0 or rect[3] <= 0 or rect in unique:
            continue
        unique.append(rect)
    kept = []
    for index, rect in enumerate(unique):
        if any(index != other and _rect_contains(candidate, rect) for other, candidate in enumerate(unique)):
            continue
        kept.append(rect)
    return kept


def _rect_overlaps(left, right) -> bool:
    return (
        left[0] < right[0] + right[2]
        and right[0] < left[0] + left[2]
        and left[1] < right[1] + right[3]
        and right[1] < left[1] + left[3]
    )


def _rect_contains(outer, inner) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[0] + outer[2] >= inner[0] + inner[2]
        and outer[1] + outer[3] >= inner[1] + inner[3]
    )


def _placement_is_valid(placed, rects, atlas_size) -> bool:
    if len(placed) != len(rects):
        return False
    sizes = {key: (width, height) for key, width, height in rects}
    boxes = []
    for key, (x, y) in placed.items():
        width, height = sizes[key]
        if x < 0 or y < 0 or x + width > atlas_size or y + height > atlas_size:
            return False
        boxes.append((x, y, width, height))
    for index, left in enumerate(boxes):
        for right in boxes[index + 1:]:
            if _rect_overlaps(left, right):
                return False
    return True


if __name__ == "__main__":
    sys.exit(main())
