"""Build one Flora atlas from the plants actually placed in a scene.

Pattern / new-case: one 2048 Flora diffuse+opacity atlas from a placed NPM scene (#217).
Packing reuses ``pack_uniform_tiles`` in ``tools/materials/atlas_maf.py`` (MAF atlas, #184).
The tool never writes a second atlas: every used species shares one scale factor.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image


ATLAS_SIZE = 2048
MIN_TILE_PX = 256
RANGE_NAMES = {
    "tree": (101, 199),
    "bush": (201, 299),
    "hedge": (301, 399),
    "flower": (401, 499),
    "climber": (501, 599),
}
REPO = Path(__file__).resolve().parents[2]


def _load_maf():
    path = Path(__file__).resolve().parents[1] / "materials" / "atlas_maf.py"
    spec = importlib.util.spec_from_file_location("atlas_maf", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MAF = _load_maf()
pack_uniform_tiles = _MAF.pack_uniform_tiles
FloraAtlasError = _MAF.AtlasError


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remap_uv(uv, tile) -> tuple[float, float]:
    """Map a UV inside a species tile. Relative layout inside the tile is kept."""

    u, v = _uv_pair(uv)
    u0, v0, u1, v1 = _tile_rect(tile)
    return (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def uv_roundtrip_delta(src, mapped, tile) -> float:
    u0, v0, u1, v1 = _tile_rect(tile)
    if u1 == u0 or v1 == v0:
        raise FloraAtlasError("tile rect has zero area")
    back_u = (mapped[0] - u0) / (u1 - u0)
    back_v = (mapped[1] - v0) / (v1 - v0)
    src_u, src_v = _uv_pair(src)
    return max(abs(back_u - src_u), abs(back_v - src_v))


def uv_within_tolerance(delta, tolerance=1e-6) -> bool:
    """True only when ``delta`` is strictly inside the tolerance.

    Exactly ``tolerance`` is rejected. NaN and infinity raise.
    """

    _real(delta, "delta")
    _real(tolerance, "tolerance")
    if delta < 0:
        raise FloraAtlasError("delta is negative")
    if tolerance <= 0:
        raise FloraAtlasError("tolerance must be positive")
    return delta < tolerance


def remap_faces(faces, tiles_by_id) -> list[dict]:
    """Return faces with the same material ids and UVs moved into atlas tiles."""

    if not isinstance(faces, list) or not faces:
        raise FloraAtlasError("face list is empty")
    remapped = []
    for index, face in enumerate(faces):
        if not isinstance(face, dict):
            raise FloraAtlasError(f"face {index} is not an object")
        material_id = _material_id(face.get("material_id"), f"face {index}")
        if material_id not in tiles_by_id:
            raise FloraAtlasError(f"face {index} material_id {material_id} has no tile")
        uvs = face.get("uvs")
        if not isinstance(uvs, list) or len(uvs) < 3:
            raise FloraAtlasError(f"face {index} needs at least 3 UV pairs")
        remapped.append({
            "material_id": material_id,
            "uvs": [list(remap_uv(pair, tiles_by_id[material_id])) for pair in uvs],
        })
    return remapped


def build_atlas(
    scene_json,
    catalogue_path,
    *,
    out_diffuse,
    out_opacity,
    out_report,
    address,
    scene_path=None,
    min_tile_px=MIN_TILE_PX,
    padding_px=_MAF.MIN_PADDING,
    atlas_size=ATLAS_SIZE,
    force=False,
) -> dict:
    """Pack one atlas for the species used by ``scene_json`` and write the report.

    PNG paths inside this repository are rejected. An output that resolves to an
    input raises before any output file is created.
    """

    if atlas_size != ATLAS_SIZE:
        raise FloraAtlasError(
            f"Flora atlas size must be {ATLAS_SIZE}; a second atlas is not allowed, got {atlas_size}"
        )
    _address(address)
    _padding(padding_px)
    _positive_int(min_tile_px, "min_tile_px")
    outputs = {
        "diffuse": Path(out_diffuse),
        "opacity": Path(out_opacity),
        "report": Path(out_report),
    }
    for path in outputs.values():
        if _inside_repo(path):
            raise FloraAtlasError(f"refusing to write atlas output inside the repository: {path}")
    scene_file = Path(scene_json)
    catalogue_file = Path(catalogue_path)
    placed = _read_json(scene_file, "scene")
    catalogue = _read_json(catalogue_file, "catalogue")
    by_id = _index_catalogue(catalogue)
    used, object_count = _used_faces(placed, by_id)
    images = {material_id: _load_maps(by_id[material_id]) for material_id in used}
    before = sha256_file(scene_path) if scene_path is not None else None
    inputs = [scene_file, catalogue_file]
    if scene_path is not None:
        inputs.append(Path(scene_path))
    for pair in images.values():
        inputs.extend(pair["paths"])
    _reject_aliases(outputs, inputs)
    if not force:
        for path in outputs.values():
            if path.exists():
                raise FloraAtlasError(f"refusing to overwrite existing output {path}; pass --force")
    items = []
    for material_id, pair in images.items():
        width, height = pair["diffuse"].size
        items.append({"key": material_id, "width": width, "height": height})
    packed = pack_uniform_tiles(
        items,
        ATLAS_SIZE,
        padding_px=padding_px,
        min_long_side=min_tile_px,
    )
    if packed["atlas_count"] != 1 or packed["atlas_size"] != ATLAS_SIZE:
        raise FloraAtlasError("packer returned more than one atlas")
    diffuse, opacity = _render(packed, images)
    after = sha256_file(scene_path) if scene_path is not None else None
    if before != after:
        raise FloraAtlasError("scene copy changed while the atlas was built")
    report = _report(
        packed,
        used,
        by_id,
        images,
        outputs,
        address,
        object_count,
        min_tile_px,
        before,
        after,
    )
    _write_outputs(diffuse, opacity, report, outputs)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pack one 2048 Flora atlas from a placed scene")
    parser.add_argument("--scene-json", required=True, help="placed-scene JSON (flora-placed-v1)")
    parser.add_argument("--catalogue", required=True, help="flora-library-v1 catalogue")
    parser.add_argument("--out-dir", required=True, help="directory for atlas PNGs and the report")
    parser.add_argument("--address", required=True, help="address token in T_{Address}_Flora and M_{Address}_Flora_1")
    parser.add_argument("--scene", help="scene copy to hash; this file is never written")
    parser.add_argument("--out-diffuse")
    parser.add_argument("--out-opacity")
    parser.add_argument("--out-report")
    parser.add_argument("--min-tile-px", type=int, default=MIN_TILE_PX)
    parser.add_argument("--padding-px", type=int, default=_MAF.MIN_PADDING)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    diffuse = Path(args.out_diffuse) if args.out_diffuse else out_dir / f"T_{args.address}_Flora_d_1.png"
    opacity = Path(args.out_opacity) if args.out_opacity else out_dir / f"T_{args.address}_Flora_o_1.png"
    report = Path(args.out_report) if args.out_report else out_dir / "flora-atlas.json"
    try:
        result = build_atlas(
            args.scene_json,
            args.catalogue,
            out_diffuse=diffuse,
            out_opacity=opacity,
            out_report=report,
            address=args.address,
            scene_path=args.scene,
            min_tile_px=args.min_tile_px,
            padding_px=args.padding_px,
            force=args.force,
        )
    except FloraAtlasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"flora atlas {result['atlas_size']}: {result['species_count']} species, "
        f"scale {result['scale_factor']}, fill {result['fill_percent']:.4f}%"
    )
    return 0


def _report(packed, used, by_id, images, outputs, address, object_count, min_tile_px, before, after) -> dict:
    slots = {slot["key"]: slot for slot in packed["slots"]}
    ids = []
    content_area = 0
    for material_id in sorted(used):
        slot = slots[material_id]
        uv = _uv_of(slot, packed["atlas_size"])
        content_area += slot["content_w"] * slot["content_h"]
        ids.append({
            "material_id": material_id,
            "species": by_id[material_id]["latin"],
            "tile_px": [slot["content_x"], slot["content_y"], slot["content_w"], slot["content_h"]],
            "size_px": [slot["content_w"], slot["content_h"]],
            "uv": uv,
            "source_px": [images[material_id]["diffuse"].size[0], images[material_id]["diffuse"].size[1]],
        })
    atlas_area = packed["atlas_size"] * packed["atlas_size"]
    report = {
        "schema": "flora-atlas-v1",
        "atlas_count": 1,
        "atlas_size": packed["atlas_size"],
        "scale_factor": packed["scale_factor"],
        "scale_numerator": packed["scale_numerator"],
        "scale_denominator": packed["scale_denominator"],
        "padding_px": packed["padding_px"],
        "min_tile_px": min_tile_px,
        "fill_ratio": content_area / atlas_area,
        "fill_percent": 100.0 * content_area / atlas_area,
        "species_count": len(ids),
        "object_count": object_count,
        "warnings": list(packed["warnings"]),
        "material": {
            "name": f"M_{address}_Flora_1",
            "diffuse": str(outputs["diffuse"]),
            "opacity": str(outputs["opacity"]),
        },
        "ids": ids,
    }
    if before is not None:
        report["scene_sha256_before"] = before
        report["scene_sha256_after"] = after
    return report


def _render(packed, images) -> tuple[Image.Image, Image.Image]:
    size = packed["atlas_size"]
    inset = packed["padding_px"] // 2
    diffuse = np.zeros((size, size, 3), dtype=np.uint8)
    opacity = np.zeros((size, size), dtype=np.uint8)
    for slot in packed["slots"]:
        pair = images[slot["key"]]
        color = _resize_rgb(pair["diffuse"], slot["content_w"], slot["content_h"])
        mask = _resize_opacity(pair["opacity"], slot["content_w"], slot["content_h"])
        if inset:
            color = np.pad(color, ((inset, inset), (inset, inset), (0, 0)), mode="edge")
            mask = np.pad(mask, ((inset, inset), (inset, inset)), mode="edge")
        y, x = slot["y"], slot["x"]
        diffuse[y:y + color.shape[0], x:x + color.shape[1]] = color
        opacity[y:y + mask.shape[0], x:x + mask.shape[1]] = mask
    return Image.fromarray(diffuse, "RGB"), Image.fromarray(opacity, "L")


def _resize_rgb(image: Image.Image, width: int, height: int) -> np.ndarray:
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(resized.convert("RGB"), dtype=np.uint8)


def _resize_opacity(image: Image.Image, width: int, height: int) -> np.ndarray:
    resized = image.resize((width, height), Image.Resampling.BOX)
    values = np.asarray(resized.convert("L"), dtype=np.uint8)
    return np.where(values >= 128, np.uint8(255), np.uint8(0))


def _uv_of(slot, atlas_size) -> list[float]:
    x = slot["content_x"]
    y = slot["content_y"]
    w = slot["content_w"]
    h = slot["content_h"]
    return [
        x / atlas_size,
        (atlas_size - (y + h)) / atlas_size,
        (x + w) / atlas_size,
        (atlas_size - y) / atlas_size,
    ]


def _write_outputs(diffuse, opacity, report, outputs) -> None:
    for path in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    diffuse.save(outputs["diffuse"], format="PNG")
    opacity.save(outputs["opacity"], format="PNG")
    outputs["report"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _used_faces(placed, by_id) -> tuple[dict, int]:
    if not isinstance(placed, dict) or placed.get("schema") != "flora-placed-v1":
        raise FloraAtlasError("scene schema must be flora-placed-v1")
    objects = placed.get("objects")
    if not isinstance(objects, list):
        raise FloraAtlasError("scene objects must be a list")
    if not objects:
        raise FloraAtlasError("scene has no placed Flora objects")
    used: dict[int, dict] = {}
    object_count = 0
    saw_face = False
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict):
            raise FloraAtlasError(f"object {index} is not an object")
        faces = obj.get("faces")
        if not isinstance(faces, list):
            raise FloraAtlasError(f"object {index} faces must be a list")
        if not faces:
            raise FloraAtlasError(f"object {obj.get('name', index)!r} has no faces")
        object_count += 1
        for face_index, face in enumerate(faces):
            if not isinstance(face, dict):
                raise FloraAtlasError(f"object {index} face {face_index} is not an object")
            saw_face = True
            material_id = _material_id(face.get("material_id"), f"object {index} face {face_index}")
            _require_flora_id(material_id)
            if material_id not in by_id:
                raise FloraAtlasError(f"material_id {material_id} is not in the Flora catalogue")
            _uvs(face.get("uvs"), f"object {index} face {face_index}")
            used[material_id] = by_id[material_id]
    if not saw_face or not used:
        raise FloraAtlasError("scene has no placed Flora faces")
    return used, object_count


def _index_catalogue(catalogue) -> dict[int, dict]:
    if not isinstance(catalogue, dict) or catalogue.get("schema") != "flora-library-v1":
        raise FloraAtlasError("catalogue schema must be flora-library-v1")
    species = catalogue.get("species")
    if not isinstance(species, list) or not species:
        raise FloraAtlasError("catalogue species list is empty")
    by_id = {}
    for index, item in enumerate(species):
        if not isinstance(item, dict):
            raise FloraAtlasError(f"catalogue species {index} is not an object")
        material_id = _material_id(item.get("material_id"), f"catalogue species {index}")
        kind = item.get("type")
        if kind not in RANGE_NAMES:
            raise FloraAtlasError(f"catalogue species {index} has unsupported type {kind!r}")
        low, high = RANGE_NAMES[kind]
        if not low <= material_id <= high:
            raise FloraAtlasError(
                f"material_id {material_id} is outside the {kind} range {low}-{high}"
            )
        latin = item.get("latin")
        if not isinstance(latin, str) or not latin.strip():
            raise FloraAtlasError(f"catalogue species {index} has no latin name")
        if material_id in by_id:
            raise FloraAtlasError(f"duplicate material_id {material_id}")
        by_id[material_id] = item
    return by_id


def _load_maps(species) -> dict:
    maps = species.get("maps")
    if not isinstance(maps, dict):
        raise FloraAtlasError(f"{species.get('latin')} has no maps object")
    if maps.get("review_status") != "approved":
        raise FloraAtlasError(
            f"{species.get('latin')} maps are not approved ({maps.get('review_status')!r})"
        )
    diffuse_path = maps.get("diffuse")
    opacity_path = maps.get("opacity")
    if not isinstance(diffuse_path, str) or not diffuse_path.strip():
        raise FloraAtlasError(f"{species.get('latin')} is missing a diffuse map")
    if not isinstance(opacity_path, str) or not opacity_path.strip():
        raise FloraAtlasError(f"{species.get('latin')} is missing an opacity map")
    diffuse_file = Path(diffuse_path)
    opacity_file = Path(opacity_path)
    if not diffuse_file.is_file():
        raise FloraAtlasError(f"diffuse map not found: {diffuse_file}")
    if not opacity_file.is_file():
        raise FloraAtlasError(f"opacity map not found: {opacity_file}")
    diffuse = _open_diffuse(diffuse_file, species["latin"])
    opacity = _open_opacity(opacity_file, species["latin"])
    if diffuse.size != opacity.size:
        raise FloraAtlasError(f"{species['latin']} diffuse and opacity sizes differ")
    if diffuse.size[0] < 1 or diffuse.size[1] < 1:
        raise FloraAtlasError(f"{species['latin']} map size is empty")
    return {"diffuse": diffuse, "opacity": opacity, "paths": (diffuse_file, opacity_file)}


def _open_diffuse(path: Path, latin: str) -> Image.Image:
    try:
        with Image.open(path) as image:
            if image.mode != "RGB" or "A" in image.getbands() or "transparency" in image.info:
                raise FloraAtlasError(f"{latin} diffuse must be RGB without alpha")
            return image.copy()
    except FloraAtlasError:
        raise
    except (OSError, ValueError) as exc:
        raise FloraAtlasError(f"{latin} diffuse cannot be read: {exc}") from exc


def _open_opacity(path: Path, latin: str) -> Image.Image:
    try:
        with Image.open(path) as image:
            if image.mode != "L":
                raise FloraAtlasError(f"{latin} opacity must be an L PNG without alpha")
            return image.copy()
    except FloraAtlasError:
        raise
    except (OSError, ValueError) as exc:
        raise FloraAtlasError(f"{latin} opacity cannot be read: {exc}") from exc


def _reject_aliases(outputs, inputs) -> None:
    names = list(outputs)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            if _MAF._same_destination(outputs[left], outputs[right]):
                raise FloraAtlasError(f"output {left} and output {right} are the same destination")
    for name, output in outputs.items():
        for source in inputs:
            if _MAF._same_destination(output, source):
                raise FloraAtlasError(f"output {output} resolves to input {source}")


def _read_json(path: Path, label: str):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FloraAtlasError(f"{label} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise FloraAtlasError(f"{label} cannot be read: {exc}") from exc
    return payload


def _uvs(value, label: str) -> None:
    if not isinstance(value, list) or len(value) < 3:
        raise FloraAtlasError(f"{label} needs at least 3 UV pairs")
    for pair in value:
        _uv_pair(pair)


def _uv_pair(value) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise FloraAtlasError(f"UV {value!r} is not a pair")
    return (_real(value[0], "u"), _real(value[1], "v"))


def _tile_rect(tile) -> tuple[float, float, float, float]:
    if not isinstance(tile, (list, tuple)) or len(tile) != 4:
        raise FloraAtlasError("tile rect must be u0, v0, u1, v1")
    return tuple(_real(value, "tile") for value in tile)


def _real(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FloraAtlasError(f"{label} is not a real number")
    number = float(value)
    if not math.isfinite(number):
        raise FloraAtlasError(f"{label} is not finite")
    return number


def _material_id(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FloraAtlasError(f"{label} material_id is not an int")
    return value


def _require_flora_id(material_id: int) -> None:
    if 1 <= material_id <= 100:
        raise FloraAtlasError(f"material_id {material_id} is in 1-100, which is not Flora")
    if not any(low <= material_id <= high for low, high in RANGE_NAMES.values()):
        raise FloraAtlasError(f"material_id {material_id} is outside the Flora ranges")


def _address(value) -> None:
    if not isinstance(value, str) or not value or any(not (ch.isalnum() or ch == "_") for ch in value):
        raise FloraAtlasError("address must use only Latin letters, digits and underscore")


def _padding(value) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FloraAtlasError("padding_px must be an even integer >= 8")
    if value < _MAF.MIN_PADDING or value % 2 != 0:
        raise FloraAtlasError(f"padding_px must be an even integer >= {_MAF.MIN_PADDING}, got {value}")


def _positive_int(value, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FloraAtlasError(f"{label} must be a positive integer")


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO.resolve())
    except (OSError, ValueError):
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
