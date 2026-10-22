"""Normalise the TEC26 OKS 3 truba maps into separate NPM and VPM sets.

Source maps are read only. NPM writes 24-bit RGB only, with no normal map:
``T_<Address>_<NNN>_<Geom>_{d|r|m|o}_<slot>.png``.
The railing diffuse and opacity are capped at 2048. Constant roughness and
metallic plates are 128. Solid swatches stay on the 256 plate. Opacity is a
separate map; the NPM diffuse has no alpha.

VPM writes ``T_<Address>_{Diffuse|ERM|Normal}_1.<UDIM>.png``.
A cutout Diffuse keeps the source RGBA alpha. Solid Diffuse is RGB at 256.
ERM and Normal are 256 RGB stubs with no alpha. ERM is emissive / roughness /
metallic. The normal stub is flat DirectX (128, 128, 255).

Any alias among the materials JSON, a source, ``--out``, ``--sums`` and a
planned output refuses the run before a directory or file is created.

Usage: python jobs/tec26-oks/make_textures.py [--src DIR] [--out DIR] [--sums FILE]

new-case: normalise a laid-out DCC texture set (solid swatches + RGBA railing)
to separate NPM and VPM delivery profiles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

HERE = Path(__file__).resolve().parent
NPM_RM = 128
VPM_STUB = 256
NPM_MAX = 2048
SIZE_FULL = 4096
DEFAULT_SRC = Path(r"C:\Users\artsafro\Desktop\!3D viz\Dima_Andrew\2_kotelnya\Vlad_OKS\maps_truba")
DEFAULT_OUT = Path(r"C:\x\tec26-oks\textures-v001")
DEFAULT_SUMS = Path(r"C:\x\tec26-oks\SHA256SUMS.txt")
NPM_SUFFIXES = ("d", "r", "m", "o")
VPM_KINDS = ("Diffuse", "ERM", "Normal")


class TextureError(Exception):
    """A bad input or a refused output path. Nothing is written."""


def assert_finite(samples: np.ndarray) -> None:
    """Reject NaN or inf. Integer images cannot carry either."""
    arr = np.asarray(samples)
    if arr.dtype.kind == "f" and not np.isfinite(arr).all():
        raise ValueError("non-finite sample")


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalise TEC26 truba texture maps.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sums", type=Path, default=DEFAULT_SUMS)
    parser.add_argument("--materials", type=Path, default=HERE / "materials.json")
    return parser.parse_args(argv)


def _expect_size(spec: dict, key: str, expected: int) -> None:
    if key not in spec:
        raise TextureError(f"unmapped key: {key}")
    try:
        value = int(spec[key])
    except (TypeError, ValueError) as exc:
        raise TextureError(f"unmapped key: {key}") from exc
    if value != expected:
        raise TextureError(f"{key} must be {expected}")


def _load_spec(path: Path) -> dict:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TextureError(f"unreadable materials: {exc}") from exc
    if not isinstance(spec, dict):
        raise TextureError("unreadable materials: not an object")
    _expect_size(spec, "size_placeholder", NPM_RM)
    _expect_size(spec, "size_vpm_stub", VPM_STUB)
    _expect_size(spec, "npm_max", NPM_MAX)
    _expect_size(spec, "size_full", SIZE_FULL)
    finishes = spec.get("finishes")
    if not isinstance(finishes, dict) or not finishes:
        raise TextureError("materials.json has no finishes")
    for key in ("udim", "slot", "source"):
        values = []
        for name, item in finishes.items():
            if not isinstance(item, dict) or key not in item:
                raise TextureError(f"unmapped key: {name}.{key}")
            values.append(item[key])
        if len(values) != len(set(values)):
            raise TextureError(f"duplicate finish {key}")
    return spec


def _resolved_key(path: Path) -> str:
    try:
        text = str(path.resolve())
    except OSError:
        text = os.path.abspath(path)
    return os.path.normcase(os.path.normpath(text))


def _same_file(left: Path, right: Path) -> bool:
    """Inode identity when both exist (hard links); resolved path otherwise."""
    if left.exists() and right.exists():
        try:
            return os.path.samefile(left, right)
        except OSError:
            pass
    return _resolved_key(left) == _resolved_key(right)


def _guard_paths(
    out: Path,
    sums: Path,
    materials: Path,
    inputs: list[Path],
    planned: list[str],
) -> None:
    labeled: list[Path] = [materials, out, sums, *inputs]
    for name in planned:
        labeled.append(out / name)
    for index, left in enumerate(labeled):
        for right in labeled[index + 1 :]:
            if _same_file(left, right):
                raise TextureError(f"alias: {left} and {right} are the same file")
    if out.exists() and not out.is_dir():
        raise TextureError(f"output path is a file: {out}")


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


def _resize_max(arr: np.ndarray, limit: int) -> np.ndarray:
    height, width = arr.shape[:2]
    if height != width:
        raise TextureError("expected a square image")
    if height <= limit:
        return np.ascontiguousarray(arr)
    mode = "RGBA" if arr.shape[2] == 4 else "RGB"
    resized = Image.fromarray(arr, mode).resize((limit, limit), Image.Resampling.BOX)
    return np.array(resized)


def _save(path: Path, arr: np.ndarray, *, allow_alpha: bool) -> None:
    if arr.dtype != np.uint8 or arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise TextureError(f"refusing to write a non-RGB map: {path.name}")
    if arr.shape[2] == 4 and not allow_alpha:
        raise TextureError(f"refusing to write alpha: {path.name}")
    mode = "RGBA" if arr.shape[2] == 4 else "RGB"
    Image.fromarray(arr, mode).save(path, format="PNG")


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


def _require(item: dict, key: str, name: str):
    if key not in item:
        raise TextureError(f"unmapped key: {name}.{key}")
    return item[key]


def _prepare(name: str, item: dict, path: Path) -> dict:
    pixels = _as_rgb_uint8(_read_image(path), path.name)
    kind = _require(item, "kind", name)
    rough = _unit_byte(_require(item, "rough", name), "rough")
    metal = _unit_byte(_require(item, "metal", name), "metal")
    if kind == "placeholder":
        colour = _solid_rgb(pixels, item.get("rgb"), path.name)
        diffuse = _fill(VPM_STUB, colour)
        opacity = _fill(VPM_STUB, (255, 255, 255))
        vpm_diffuse = diffuse
    elif kind == "full":
        if pixels.shape[2] != 4:
            raise TextureError(f"unsupported mode: {path.name}")
        vpm_diffuse = np.ascontiguousarray(pixels)
        capped = _resize_max(pixels, NPM_MAX)
        diffuse = np.ascontiguousarray(capped[..., :3])
        alpha = capped[..., 3]
        opacity = np.stack([alpha, alpha, alpha], axis=-1)
    else:
        raise TextureError(f"unsupported kind: {kind}")
    return {
        "slot": int(_require(item, "slot", name)),
        "udim": int(_require(item, "udim", name)),
        "diffuse": diffuse,
        "opacity": opacity,
        "vpm_diffuse": vpm_diffuse,
        "rough": _fill(NPM_RM, (rough, rough, rough)),
        "metal": _fill(NPM_RM, (metal, metal, metal)),
        "normal": _fill(VPM_STUB, (128, 128, 255)),
        "erm": _fill(VPM_STUB, (0, rough, metal)),
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
    _guard_paths(args.out, args.sums, args.materials, inputs, planned)
    prepared = [_prepare(name, item, path) for (name, item), path in zip(finishes, inputs)]

    address = spec["address"]
    number = spec["npm_number"]
    geom = spec["geom_suffix"]
    args.out.mkdir(parents=True, exist_ok=True)
    if args.sums.parent != args.out:
        args.sums.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item in prepared:
        npm = {
            "d": item["diffuse"],
            "r": item["rough"],
            "m": item["metal"],
            "o": item["opacity"],
        }
        for suffix, arr in npm.items():
            path = args.out / f"T_{address}_{number}_{geom}_{suffix}_{item['slot']}.png"
            _save(path, arr, allow_alpha=False)
            written.append(path)
        vpm_diffuse = args.out / f"T_{address}_Diffuse_1.{item['udim']}.png"
        _save(vpm_diffuse, item["vpm_diffuse"], allow_alpha=item["vpm_diffuse"].shape[2] == 4)
        written.append(vpm_diffuse)
        for kind, arr in (("ERM", item["erm"]), ("Normal", item["normal"])):
            path = args.out / f"T_{address}_{kind}_1.{item['udim']}.png"
            _save(path, arr, allow_alpha=False)
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
