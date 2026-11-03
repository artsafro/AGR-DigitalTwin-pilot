"""new-case: advisory DreamSim column beside SSIM and the joint count for AC08 facade crops.

Pure helpers cover a 1-3 px shift, three planted defects, and fail-closed image checks.
They do not load a model and they do not change any gate. The ``run`` command measures
pairs. An output path that resolves to an input exits nonzero and writes nothing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "jobs" / "TEC26-OKS" / "scripts"
METHODS = ROOT / "tools" / "methods"
SPEC = ROOT / "jobs" / "TEC26-OKS" / "AC08" / "vpm_textures.json"
SHEET = ROOT / "jobs" / "TEC26-OKS" / "AC08" / "sheet-facades.json"
SLIDE_SHA256 = "256f32da2a04141fc6b62b46ed9710c1830c5ffd3f48f2bac578719c0208a8fd"
PX_PER_M = 200.0
LUMA = np.array([0.299, 0.587, 0.114])
VIEW = {"+y": "north", "-y": "south", "+x": "east", "-x": "west"}

# Local evidence. v010 renders are the accepted 400 px/m set. v007's stored PNGs are
# 1600x900, so ``run`` reads the 400 px/m re-render produced by render_facades.py.
PILOTS = {
    "v010": {
        "renders": Path(r"C:/x/tec26-oks/AC08/pilot-v010/renders"),
        "readback": Path(r"C:/x/tec26-oks/AC08/pilot-v010/readback/vpm.readback.json"),
        "panel_udim": None,
    },
    "v007": {
        "renders": Path(r"C:/x/issue-770/v007-renders-400"),
        "readback": Path(r"C:/x/tec26-oks/AC08/pilot-v007/readback/vpm.readback.json"),
        # Measured on the v007 readback: UDIM 1001 is the above-grade ribbed field on
        # every facade. The current spec's short-facade UDIM 1002 is below grade there.
        "panel_udim": 1001,
    },
}


class InputError(ValueError):
    """Empty, partial, unsupported, or non-finite image input."""


def require_rgb(image) -> np.ndarray:
    """Finite HxWx3 array with values in [0, 1]. Empty, NaN, inf, and other shapes raise."""
    if not isinstance(image, np.ndarray):
        raise InputError("image must be a numpy array")
    if image.ndim != 3 or image.shape[-1] != 3 or image.shape[0] < 1 or image.shape[1] < 1:
        raise InputError(f"image shape {getattr(image, 'shape', None)} is not HxWx3")
    if not np.issubdtype(image.dtype, np.floating):
        raise InputError(f"image dtype {image.dtype} is unsupported")
    if not np.isfinite(image).all():
        raise InputError("non-finite pixel")
    if image.min() < 0.0 or image.max() > 1.0:
        raise InputError("pixel outside [0, 1]")
    return image


def require_same_shape(a, b) -> None:
    a, b = require_rgb(a), require_rgb(b)
    if a.shape != b.shape:
        raise InputError(f"shape mismatch {a.shape} vs {b.shape}")


def _copy(image) -> np.ndarray:
    src = require_rgb(image)
    return np.array(src, dtype=np.float64, copy=True)


def _require_int(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise InputError(f"{name} must be an integer")
    return int(value)


def shift_pixels(image, dx: int, dy: int) -> np.ndarray:
    """Translate by integer pixels. Vacated pixels become white. Positive dx moves content right."""
    src = _copy(image)
    dx, dy = _require_int("dx", dx), _require_int("dy", dy)
    out = np.ones_like(src)
    h, w = src.shape[:2]
    y0, y1 = max(dy, 0), h + min(dy, 0)
    x0, x1 = max(dx, 0), w + min(dx, 0)
    if y1 <= y0 or x1 <= x0:
        return out
    out[y0:y1, x0:x1] = src[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return out


def _span(n: int, start: float, stop: float) -> tuple[int, int]:
    if not (np.isfinite(start) and np.isfinite(stop) and 0.0 <= start < stop <= 1.0):
        raise InputError("fraction span must be finite and inside [0, 1]")
    i0, i1 = int(np.floor(start * n)), int(np.ceil(stop * n))
    if i1 <= i0:
        raise InputError("fraction span is empty")
    return i0, i1


def plant_shifted_band(image, px_per_m: float, metres: float = 0.1, band_frac=(0.4, 0.7)) -> np.ndarray:
    """Shift one horizontal band to the right by ``metres`` at ``px_per_m``. The gap is white."""
    src = _copy(image)
    if isinstance(px_per_m, bool) or isinstance(metres, bool):
        raise InputError("px_per_m and metres must be finite numbers")
    px_per_m, metres = float(px_per_m), float(metres)
    if not np.isfinite(px_per_m) or not np.isfinite(metres) or px_per_m <= 0 or metres <= 0:
        raise InputError("px_per_m and metres must be finite and positive")
    shift = int(round(metres * px_per_m))
    if shift < 1:
        raise InputError("band shift is below 1 px")
    y0, y1 = _span(src.shape[0], float(band_frac[0]), float(band_frac[1]))
    band = src[y0:y1]
    moved = shift_pixels(band, shift, 0)
    src[y0:y1] = moved
    return src


def plant_wrong_colour(image, zone_frac, colour) -> np.ndarray:
    """Overwrite an axis-aligned zone (y0, y1, x0, x1 as fractions) with a constant RGB colour."""
    src = _copy(image)
    colour = np.asarray(colour, dtype=np.float64)
    if colour.shape != (3,) or not np.isfinite(colour).all() or colour.min() < 0 or colour.max() > 1:
        raise InputError("colour must be a finite RGB triple in [0, 1]")
    y0, y1 = _span(src.shape[0], float(zone_frac[0]), float(zone_frac[1]))
    x0, x1 = _span(src.shape[1], float(zone_frac[2]), float(zone_frac[3]))
    src[y0:y1, x0:x1] = colour
    return src


def plant_missing_rib(image, row_frac: float = 0.30) -> np.ndarray:
    """Paint out one interior dark run on ``row_frac``, the rib closest to centre.

    The run is replaced on every row with the mean of the columns just outside it.
    A full-height mean would pick the border, not a rib, so the run comes from the
    same row the crop joint count uses.
    """
    src = _copy(image)
    if not np.isfinite(row_frac) or not 0.0 <= float(row_frac) <= 1.0:
        raise InputError("row_frac must be inside [0, 1]")
    y = int(round(float(row_frac) * (src.shape[0] - 1)))
    lum = src[y] @ LUMA
    content = lum < 0.97
    if int(content.sum()) < 10:
        raise InputError("no panel samples on the rib row")
    dark = content & (lum < 0.85 * float(np.median(lum[content])))
    mask = np.concatenate([[False], dark, [False]])
    delta = np.diff(mask.astype(int))
    margin = int(round(0.08 * src.shape[1]))
    runs = []
    for a, b in zip(np.where(delta == 1)[0], np.where(delta == -1)[0]):
        centre = (int(a) + int(b) - 1) / 2.0
        if margin < centre < src.shape[1] - margin:
            runs.append((int(a), int(b)))
    if not runs:
        raise InputError("no interior rib to remove")
    a, b = min(runs, key=lambda run: abs((run[0] + run[1] - 1) / 2.0 - (src.shape[1] - 1) / 2.0))
    left = src[:, a - 1] if a > 0 else None
    right = src[:, b] if b < src.shape[1] else None
    if left is None and right is None:
        raise InputError("rib has no neighbour column")
    fill = left if right is None else right if left is None else (left + right) / 2.0
    src[:, a:b] = fill[:, None]
    return src


def crop_joint_count(image, row_frac: float = 0.30) -> int:
    """Dark vertical runs on one row of a 200 px/m crop, ignoring the outer 8 % (frame outline)."""
    src = require_rgb(image)
    if not np.isfinite(row_frac) or not 0.0 <= float(row_frac) <= 1.0:
        raise InputError("row_frac must be inside [0, 1]")
    y = int(round(float(row_frac) * (src.shape[0] - 1)))
    lum = src[y] @ LUMA
    content = lum < 0.97
    if int(content.sum()) < 10:
        raise InputError("no panel samples on the crop row")
    dark = content & (lum < 0.85 * float(np.median(lum[content])))
    mask = np.concatenate([[False], dark, [False]])
    delta = np.diff(mask.astype(int))
    margin = int(round(0.08 * src.shape[1]))
    count = 0
    for a, b in zip(np.where(delta == 1)[0], np.where(delta == -1)[0]):
        centre = (int(a) + int(b) - 1) / 2.0
        if margin < centre < src.shape[1] - margin:
            count += 1
    return count


def load_rgb(path: Path) -> np.ndarray:
    """Load an RGB image. RGBA is composited on white, as the facade renders are. Anything else raises."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise InputError(f"empty image {path}")
    try:
        with Image.open(path) as im:
            im.load()
            if im.mode == "RGBA":
                base = Image.new("RGB", im.size, (255, 255, 255))
                base.paste(im, mask=im.getchannel("A"))
                im = base
            elif im.mode != "RGB":
                raise InputError(f"unsupported mode {im.mode}")
            arr = np.asarray(im, dtype=np.float64) / 255.0
    except InputError:
        raise
    except Exception as exc:
        raise InputError(f"unsupported image {path}: {exc}") from exc
    return require_rgb(arr)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def output_collides(output: Path, inputs: list[Path]) -> bool:
    out = Path(output).resolve()
    for src in inputs:
        src = Path(src)
        if src.resolve() == out:
            return True
        if src.exists() and Path(output).exists():
            try:
                if src.samefile(output):
                    return True
            except OSError:
                pass
    return False


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".partial", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _scripts():
    for folder in (str(SCRIPTS), str(METHODS)):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    import compare_facades
    import joint_count
    import methods_metrics
    return compare_facades, joint_count, methods_metrics


def _tile(uv) -> int:
    c = np.mean(np.asarray(uv, float), axis=0)
    return int(1001 + np.floor(c[0]) + 10 * np.floor(c[1]))


def _ssim(mm, a: np.ndarray, b: np.ndarray) -> float:
    require_same_shape(a, b)
    return float(mm.ssim(a @ LUMA, b @ LUMA))


def _align(slide: np.ndarray, render: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Center-crop a 1 px rounding gap. A larger gap is an error, not a resized pass."""
    require_rgb(slide)
    require_rgb(render)
    note = {"slide_hw": list(slide.shape[:2]), "render_hw": list(render.shape[:2]), "cropped_px": [0, 0]}
    if slide.shape == render.shape:
        return slide, render, note
    dh = abs(slide.shape[0] - render.shape[0])
    dw = abs(slide.shape[1] - render.shape[1])
    if dh > 2 or dw > 2:
        raise InputError(f"shape mismatch {slide.shape} vs {render.shape}")
    h = min(slide.shape[0], render.shape[0])
    w = min(slide.shape[1], render.shape[1])

    def crop(img):
        y0 = (img.shape[0] - h) // 2
        x0 = (img.shape[1] - w) // 2
        return img[y0:y0 + h, x0:x0 + w]

    note["cropped_px"] = [dh, dw]
    return crop(slide), crop(render), note


def _field(jc, V, faces, uvs, key: str, udim: int):
    keep = lambda t, udim=udim: _tile(uvs[t]) == udim  # noqa: E731
    tris = jc.facade_triangles(V, faces, keep, key)
    if not tris:
        raise InputError(f"no panel triangles facing {key} on UDIM {udim}")
    lo, hi, zlo, zhi = jc.field_extent(V, faces, tris, key)
    if not (zlo < 0.5 < zhi):
        raise InputError(f"UDIM {udim} on {key} is not an above-grade field (z {zlo:.3f}..{zhi:.3f})")
    return lo, hi, zlo, zhi


def measure_pilot(pilot: str, work: Path) -> list[dict]:
    """200 px/m slide and VPM/NPM crops, SSIM, and joint counts. DreamSim is filled later."""
    cf, jc, mm = _scripts()
    cfg = PILOTS[pilot]
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    slide_path = Path(spec["presentation"]["image"])
    digest = sha256_file(slide_path)
    if digest != spec["presentation"]["image_sha256"] or digest != SLIDE_SHA256:
        raise InputError("slide sha256 does not match the pinned presentation")
    meta = json.loads((cfg["renders"] / "renders.json").read_text(encoding="utf-8"))
    readback = json.loads(cfg["readback"].read_text(encoding="utf-8"))
    mesh = next(o for o in readback["objects"] if o["name"] == "SM_Nku_1_Main")
    V = np.asarray(mesh["vertices"], float)
    faces, uvs = mesh["faces"], mesh["face_uvs"]
    slide = np.asarray(Image.open(slide_path).convert("RGB"))
    boxes = dict(zip(spec["presentation"]["quadrants"], cf.slide_boxes(slide)))
    rows = []
    crop_dir = work / "crops" / pilot
    crop_dir.mkdir(parents=True, exist_ok=True)
    for name, fc in spec["facades"].items():
        f = sheet["facades"][name]
        key = fc["normal"]
        udim = cfg["panel_udim"] if cfg["panel_udim"] is not None else spec["finishes"][fc["finish"]]["udim"]
        lo, hi, zlo, zhi = _field(jc, V, faces, uvs, key, int(udim))
        blo = lo - f["frame_bands_mm"]["left"] / 1000.0
        bhi = hi + f["frame_bands_mm"]["right"] / 1000.0
        ground = min(p["bbox_mm"][1] for p in f["plinth"]) / 1000.0
        sc = cf.slide_count(slide, boxes[name], f)
        slide_img = np.asarray(cf.panel_slide(slide, boxes[name], f, PX_PER_M), dtype=np.float64) / 255.0
        slide_img = require_rgb(slide_img)
        for tag in ("vpm", "npm"):
            view = meta[tag]["views"][VIEW[key]]
            png = cfg["renders"] / view["png"]
            panel = cf.panel_render(str(png), view, key, blo, bhi, PX_PER_M, ground)
            render = require_rgb(np.asarray(panel, dtype=np.float64) / 255.0)
            slide_c, render_c, align = _align(slide_img, render)
            full = np.asarray(Image.open(png).convert("RGB"))
            axis = 1 if key in ("+x", "-x") else 0
            z = zlo + 0.95 * (zhi - zlo)
            s, lum = jc.render_row(full, view, axis, z, lo, hi)
            counted = jc.count_joints(s, lum, lo, hi, fc["ribs"], tol=0.01, dark=0.85)
            slide_file = crop_dir / f"{VIEW[key]}_{name}_slide.png"
            render_file = crop_dir / f"{VIEW[key]}_{name}_{tag}.png"
            _save_png(slide_file, slide_c)
            _save_png(render_file, render_c)
            rows.append({
                "kind": "facade",
                "pilot": pilot,
                "facade": name,
                "view": VIEW[key],
                "tag": tag,
                "px_per_m": PX_PER_M,
                "panel_udim": int(udim),
                "ssim": round(_ssim(mm, slide_c, render_c), 5),
                "dreamsim": None,
                "dreamsim_s": None,
                "slide_joints": int(sc["joints"]),
                "render_joints": int(counted["joints_found"]),
                "render_joints_expected": int(counted["joints_expected"]),
                "render_joint_ok": bool(counted["ok"]),
                "align": align,
                "slide_sha256": sha256_file(slide_file),
                "render_sha256": sha256_file(render_file),
                "source_render_sha256": sha256_file(png),
                "source_slide_sha256": digest,
                "slide_crop": str(slide_file),
                "render_crop": str(render_file),
            })
    return rows


def _save_png(path: Path, image: np.ndarray) -> None:
    require_rgb(image)
    arr = np.clip(np.round(image * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(path)


def _controls(base: np.ndarray) -> list[tuple[str, np.ndarray]]:
    band = (0.20, 0.55)
    return [
        ("shift_1px", shift_pixels(base, 1, 0)),
        ("shift_2px", shift_pixels(base, 2, 0)),
        ("shift_3px", shift_pixels(base, 3, 0)),
        ("shifted_band_0.1m", plant_shifted_band(base, PX_PER_M, 0.1, band)),
        ("wrong_colour_zone", plant_wrong_colour(base, (0.30, 0.70, 0.30, 0.70), (0.80, 0.10, 0.10))),
        ("missing_rib", plant_missing_rib(base)),
    ]


def control_rows(facade_rows: list[dict], mm) -> list[dict]:
    """Harmless shifts and planted defects on the accepted v010 VPM north crop, versus that crop."""
    base_row = next(r for r in facade_rows if r["pilot"] == "v010" and r["tag"] == "vpm" and r["view"] == "north")
    base = load_rgb(base_row["render_crop"])
    base_joints = crop_joint_count(base)
    out = []
    for name, image in _controls(base):
        out.append({
            "kind": "control",
            "name": name,
            "pilot": "v010",
            "view": "north",
            "tag": "vpm",
            "ssim": round(_ssim(mm, base, image), 5),
            "dreamsim": None,
            "dreamsim_s": None,
            "base_crop_joints": base_joints,
            "defect_crop_joints": crop_joint_count(image),
        })
    return out


def _separation(rows: list[dict], key: str, higher_is_closer: bool) -> dict:
    harmless = [r for r in rows if r["name"].startswith("shift_")]
    defects = [r for r in rows if not r["name"].startswith("shift_")]
    hvals = [r[key] for r in harmless]
    dvals = [r[key] for r in defects]
    if any(v is None for v in hvals + dvals):
        return {"separates": None, "reason": "missing value"}
    if higher_is_closer:
        separates = min(hvals) > max(dvals)
    else:
        separates = max(hvals) < min(dvals)
    return {
        "separates": bool(separates),
        "harmless_min": min(hvals),
        "harmless_max": max(hvals),
        "defect_min": min(dvals),
        "defect_max": max(dvals),
        "rule": "harmless closer than every planted defect" if higher_is_closer
        else "harmless distance below every planted defect",
    }


def joint_separation(rows: list[dict]) -> dict:
    same = all(r["defect_crop_joints"] == r["base_crop_joints"] for r in rows if r["name"].startswith("shift_"))
    changed = {r["name"]: r["defect_crop_joints"] != r["base_crop_joints"]
               for r in rows if not r["name"].startswith("shift_")}
    return {
        "shifts_keep_count": bool(same),
        "defect_changes_count": changed,
        "separates": bool(same and all(changed.values())),
    }


def _dreamsim_distance(model, preprocess, a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    require_same_shape(a, b)
    import torch
    t0 = time.perf_counter()
    ia = preprocess(_pil(a))
    ib = preprocess(_pil(b))
    with torch.no_grad():
        dist = model(ia, ib)
    value = float(dist.detach().cpu().reshape(-1)[0])
    if not np.isfinite(value):
        raise InputError("DreamSim returned a non-finite distance")
    return value, time.perf_counter() - t0


def _pil(image: np.ndarray) -> Image.Image:
    arr = np.clip(np.round(require_rgb(image) * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def load_dreamsim(cache: Path):
    import torch
    from dreamsim import dreamsim
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    model, preprocess = dreamsim(pretrained=True, device="cpu", cache_dir=str(cache), dreamsim_type="ensemble")
    return model, preprocess, time.perf_counter() - t0, torch.__version__


def _public_row(row: dict) -> dict:
    skip = {"slide_crop", "render_crop"}
    return {k: v for k, v in row.items() if k not in skip}


def _weight_files(cache: Path) -> list[dict]:
    """Checkpoint and licence files only. The DINO unpack also drops a full source tree."""
    keep = {".pth", ".safetensors", ".zip", ".bin"}
    found = []
    if not cache.exists():
        return found
    for p in sorted(cache.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in keep or p.name.lower() == "license" or p.name.endswith(".pth.tar"):
            found.append({"name": str(p.relative_to(cache)).replace("\\", "/"), "bytes": p.stat().st_size,
                          "sha256": sha256_file(p)})
    return found


def run(results: Path, csv_path: Path, work: Path, cache: Path) -> int:
    inputs = [SPEC, SHEET]
    for cfg in PILOTS.values():
        inputs.append(cfg["readback"])
        inputs.append(cfg["renders"] / "renders.json")
    if output_collides(results, inputs + [csv_path]) or output_collides(csv_path, inputs + [results]):
        raise SystemExit(2)
    _, _, mm = _scripts()
    rows = []
    for pilot in ("v010", "v007"):
        rows.extend(measure_pilot(pilot, work))
    controls = control_rows(rows, mm)
    dream = {"loaded": False, "error": None, "load_s": None, "torch": None, "cache": str(cache)}
    try:
        model, preprocess, load_s, torch_version = load_dreamsim(cache)
        dream.update({"loaded": True, "load_s": round(load_s, 3), "torch": torch_version})
        for row in rows:
            dist, sec = _dreamsim_distance(model, preprocess, load_rgb(row["slide_crop"]), load_rgb(row["render_crop"]))
            row["dreamsim"] = round(dist, 6)
            row["dreamsim_s"] = round(sec, 4)
        base = load_rgb(next(r["render_crop"] for r in rows if r["pilot"] == "v010" and r["tag"] == "vpm" and r["view"] == "north"))
        for row, (_, image) in zip(controls, _controls(base)):
            dist, sec = _dreamsim_distance(model, preprocess, base, image)
            row["dreamsim"] = round(dist, 6)
            row["dreamsim_s"] = round(sec, 4)
    except Exception as exc:
        dream["error"] = f"{type(exc).__name__}: {exc}"
    weight_files = _weight_files(cache)
    payload = {
        "schema": "dreamsim-ac08/1",
        "px_per_m": PX_PER_M,
        "dreamsim_package": "0.2.1",
        "dreamsim_type": "ensemble",
        "device": "cpu",
        "dreamsim": dream,
        "weights": weight_files,
        "separation": {
            "ssim": _separation(controls, "ssim", True),
            "dreamsim": _separation(controls, "dreamsim", False),
            "crop_joints": joint_separation(controls),
        },
        "facades": [_public_row(r) for r in rows],
        "controls": controls,
    }
    _atomic_write(results, json.dumps(payload, indent=1))
    _write_csv(csv_path, rows, controls)
    complete = all(r.get("dreamsim") is not None for r in rows + controls)
    return 0 if dream["loaded"] and dream["error"] is None and complete else 1


def _write_csv(path: Path, rows: list[dict], controls: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".partial", dir=path.parent)
    tmp = Path(name)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "kind", "pilot", "view", "facade", "tag", "name", "ssim", "dreamsim", "dreamsim_s",
            "slide_joints", "render_joints", "base_crop_joints", "defect_crop_joints"])
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in w.fieldnames})
        for row in controls:
            w.writerow({k: row.get(k, "") for k in w.fieldnames})
    os.replace(tmp, path)


def _cmd_write_array(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="write-array")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    src, dst = Path(args.input), Path(args.output)
    if output_collides(dst, [src]):
        raise SystemExit(2)
    try:
        image = load_rgb(src)
    except InputError as exc:
        raise SystemExit(3) from exc
    _atomic_write(dst, json.dumps({"shape": list(image.shape)}))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"write-array", "run"}:
        raise SystemExit(2)
    if argv[0] == "write-array":
        _cmd_write_array(argv[1:])
        return 0
    parser = argparse.ArgumentParser(prog="run")
    parser.add_argument("--results", default=str(ROOT / "docs/experiments/2026-11-02-dreamsim-ac08/results.json"))
    parser.add_argument("--csv", default=str(ROOT / "docs/experiments/2026-11-02-dreamsim-ac08/results.csv"))
    parser.add_argument("--work", default=r"C:/x/issue-770")
    parser.add_argument("--cache", default=r"C:/x/issue-770/dreamsim-weights")
    args = parser.parse_args(argv[1:])
    return run(Path(args.results), Path(args.csv), Path(args.work), Path(args.cache))


if __name__ == "__main__":
    sys.exit(main())
