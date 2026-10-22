"""Normalise the TEC26 OKS 3 truba maps to 24-bit RGB delivery names.

Source maps are read only. Outputs are PNG with no alpha channel:
NPM ``T_<Address>_<NNN>_<Geom>_{d|r|m|n|o}_<slot>.png`` and
VPM ``T_<Address>_{Diffuse|ERM|Normal}_1.<UDIM>.png``.

Solid finishes are 256 px placeholders (KPP1 ``size_placeholder``). The railing
keeps its source raster: RGB diffuse plus a separate greyscale opacity. Roughness,
metallic, normal, ERM and the solid opacity maps are 256 px stubs. ERM is
emissive / roughness / metallic. The normal stub is flat DirectX (128, 128, 255).

Usage: python jobs/tec26-oks/make_textures.py [--src DIR] [--out DIR] [--sums FILE]

new-case: normalise a laid-out DCC texture set (solid swatches + RGBA railing) to
24-bit RGB delivery names (NPM suffix set + VPM UDIM Diffuse/ERM/Normal).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

HERE = Path(__file__).resolve().parent
STUB = 256
DEFAULT_SRC = Path(r"C:\Users\artsafro\Desktop\!3D viz\Dima_Andrew\2_kotelnya\Vlad_OKS\maps_truba")
DEFAULT_OUT = Path(r"C:\x\tec26-oks\textures-v001")
DEFAULT_SUMS = Path(r"C:\x\tec26-oks\SHA256SUMS.txt")
NPM_SUFFIXES = ("d", "r", "m", "n", "o")
VPM_KINDS = ("Diffuse", "ERM", "Normal")


class TextureError(Exception):
    """A bad input or a refused output path. Nothing is written."""


def assert_finite(samples: np.ndarray) -> None:
    """Reject NaN or inf. Integer images cannot carry either."""
    arr = np.asarray(samples)
    if arr.dtype.kind == "f" and not np.isfinite(arr).all():
        raise ValueError("non-finite sample")


def _resolved(path: Path) -> Path:
    return Path(str(path.resolve()))


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalise TEC26 truba texture maps.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sums", type=Path, default=DEFAULT_SUMS)
    parser.add_argument("--materials", type=Path, default=HERE / "materials.json")
    return parser.parse_args(argv)


def _load_spec(path: Path) -> dict:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TextureError(f"unreadable materials: {exc}") from exc
    if int(spec.get("size_placeholder", 0)) != STUB:
        raise TextureError("size_placeholder must be the KPP stub size 256")
    finishes = spec.get("finishes")
    if not isinstance(finishes, dict) or not finishes:
        raise TextureError("materials.json has no finishes")
    for key in ("udim", "slot", "source"):
        values = [item[key] for item in finishes.values()]
        if len(values) != len(set(values)):
            raise TextureError(f"duplicate finish {key}")
    return spec


def _guard_paths(out: Path, sums: Path, inputs: list[Path], planned: list[str]) -> None:
    blocked = {_resolved(path) for path in inputs}
    if _resolved(out) in blocked or _resolved(sums) in blocked:
        raise TextureError("output path resolves to an input")
    if out.exists() and not out.is_dir():
        raise TextureError("output path resolves to an input")
    if not out.exists() or out.is_dir():
        for name in planned:
            if _resolved(out / name) in blocked:
                raise TextureError("output path resolves to an input")


def _read_image(path: Path) -> np.ndarray:
    if not path.is_file() or path.stat().st_size == 0:
        raise TextureError(f"empty image: {path.name}")
    try:
        with Image.open(path) as image:
            image.load()
            pixels = np.array(image)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise TextureError(f"unreadable image: {path.name}") from exc
    assert_finite(pixels)
    return pixels


def _as_rgb_uint8(pixels: np.ndarray, name: str) -> np.ndarray:
    if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] not in (3, 4):
        raise TextureError(f"unsupported mode: {name}")
    if pixels.shape[0] < 1 or pixels.shape[1] < 1 or pixels.shape[0] != pixels.shape[1]:
        raise TextureError(f"expected a square image: {name}")
    return pixels


def _solid_rgb(pixels: np.ndarray, expected: list, name: str) -> tuple[int, int, int]:
    rgb = _as_rgb_uint8(pixels, name)
    if rgb.shape[2] != 3:
        raise TextureError(f"unsupported mode: {name}")
    flat = rgb.reshape(-1, 3)
    if not np.all(flat == flat[0]):
        raise TextureError(f"solid swatch is not uniform: {name}")
    colour = (int(flat[0, 0]), int(flat[0, 1]), int(flat[0, 2]))
    if expected is not None and colour != tuple(int(v) for v in expected):
        raise TextureError(f"source colour does not match materials.json: {name}")
    return colour


def _unit_byte(value: float, name: str) -> int:
    number = float(value)
    if not np.isfinite(number) or not 0.0 <= number <= 1.0:
        raise TextureError(f"non-finite or out-of-range {name}")
    return int(round(number * 255))


def _fill(size: int, rgb: tuple[int, int, int]) -> np.ndarray:
    return np.broadcast_to(np.array(rgb, np.uint8), (size, size, 3)).copy()


def _save_rgb(path: Path, arr: np.ndarray) -> None:
    if arr.dtype != np.uint8 or arr.ndim != 3 or arr.shape[2] != 3:
        raise TextureError(f"refusing to write a non-RGB map: {path.name}")
    Image.fromarray(arr, "RGB").save(path, format="PNG")


def _planned_names(spec: dict, finishes: list[tuple[str, dict]]) -> list[str]:
    address = spec["address"]
    number = spec["npm_number"]
    geom = spec["geom_suffix"]
    names = []
    for _name, item in finishes:
        slot = int(item["slot"])
        udim = int(item["udim"])
        for suffix in NPM_SUFFIXES:
            names.append(f"T_{address}_{number}_{geom}_{suffix}_{slot}.png")
        for kind in VPM_KINDS:
            names.append(f"T_{address}_{kind}_1.{udim}.png")
    return names


def _prepare(item: dict, path: Path) -> dict:
    pixels = _as_rgb_uint8(_read_image(path), path.name)
    kind = item["kind"]
    rough = _unit_byte(item["rough"], "rough")
    metal = _unit_byte(item["metal"], "metal")
    if kind == "placeholder":
        colour = _solid_rgb(pixels, item.get("rgb"), path.name)
        diffuse = _fill(STUB, colour)
        opacity = _fill(STUB, (255, 255, 255))
    elif kind == "full":
        if pixels.shape[2] != 4:
            raise TextureError(f"unsupported mode: {path.name}")
        diffuse = np.ascontiguousarray(pixels[..., :3])
        alpha = pixels[..., 3]
        opacity = np.stack([alpha, alpha, alpha], axis=-1)
    else:
        raise TextureError(f"unsupported kind: {kind}")
    return {
        "slot": int(item["slot"]),
        "udim": int(item["udim"]),
        "diffuse": diffuse,
        "opacity": opacity,
        "rough": _fill(STUB, (rough, rough, rough)),
        "metal": _fill(STUB, (metal, metal, metal)),
        "normal": _fill(STUB, (128, 128, 255)),
        "erm": _fill(STUB, (0, rough, metal)),
    }


def _write_sums(path: Path, files: list[Path]) -> None:
    lines = []
    for file in sorted(files, key=lambda item: item.name):
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        lines.append(f"{digest}  {file.name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(argv: list[str]) -> None:
    args = _parse(argv)
    spec = _load_spec(args.materials)
    finishes = sorted(spec["finishes"].items(), key=lambda pair: int(pair[1]["udim"]))
    inputs = [args.src / item["source"] for _name, item in finishes]
    missing = [path.name for path in inputs if not path.is_file()]
    if missing:
        raise TextureError("missing source: " + ", ".join(missing))
    planned = _planned_names(spec, finishes)
    _guard_paths(args.out, args.sums, inputs, planned)
    prepared = [_prepare(item, path) for (_name, item), path in zip(finishes, inputs)]

    address = spec["address"]
    number = spec["npm_number"]
    geom = spec["geom_suffix"]
    args.out.mkdir(parents=True, exist_ok=True)
    if args.sums.parent != args.out:
        args.sums.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item in prepared:
        maps = {
            "d": item["diffuse"],
            "r": item["rough"],
            "m": item["metal"],
            "n": item["normal"],
            "o": item["opacity"],
        }
        for suffix, arr in maps.items():
            path = args.out / f"T_{address}_{number}_{geom}_{suffix}_{item['slot']}.png"
            _save_rgb(path, arr)
            written.append(path)
        vpm = {
            "Diffuse": item["diffuse"],
            "ERM": item["erm"],
            "Normal": item["normal"],
        }
        for kind, arr in vpm.items():
            path = args.out / f"T_{address}_{kind}_1.{item['udim']}.png"
            _save_rgb(path, arr)
            written.append(path)
    _write_sums(args.sums, written)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        run(argv)
    except (TextureError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
