"""Process inbox originals into library maps and write the maps manifest [D239].

    uv run python tools/materials/inbox_maps.py --spec library/materials/maps_v001.spec.json \
        --root "G:/Мой диск/AGR-assets" --out library/materials/maps_v001.json

The spec names, per inbox source (msg id), the outputs to write under --root: plain RGB copies or
resamples, one-colour placeholders, single channels, alpha -> `_o` grey maps, padding to a power of
two. Inbox originals are only read (sha256 checked against the inbox manifest.json). An output that
already exists is never overwritten: identical bytes are kept, different bytes stop the run.
Every output is a PNG, 8 bit, no alpha (RGB; binary star opacity is grey L); NPM outputs are checked with twinqa.png (V006 rules).
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from twinqa.png import npm_texture_findings, png_facts  # noqa: E402

NPM_MAX_BYTES = 3 * 1024 * 1024  # [D015], reg p.9 §5.3
NPM_AUTO_SIZES = (2048, 1024, 512)
D207_PX_PER_M = 1000  # texture grid: 3.6 m per UDIM tile at 1000 px/m [D207]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_source(root: Path, inbox: dict, src: dict) -> tuple[Image.Image, dict]:
    item = inbox[src["src"]]
    data = (root / item["path"]).read_bytes()
    if sha256(data) != item["sha256"]:
        raise SystemExit(f"msg {src['src']}: inbox sha256 differs from manifest.json")
    ref = {"msg_id": src["src"], "file": item["file"], "sha256": item["sha256"]}
    if "member" in src:  # an image inside an inbox zip, read in memory
        data = zipfile.ZipFile(io.BytesIO(data)).read(src["member"])
        ref.update(member=src["member"], member_sha256=sha256(data))
    im = Image.open(io.BytesIO(data))
    im.load()
    return im, ref


def as_rgb(im: Image.Image) -> Image.Image:
    if im.mode == "P":
        im = im.convert("RGBA")
    return im.convert("RGB") if im.mode != "RGB" else im


def grey_rgb(channel: Image.Image) -> Image.Image:
    return Image.merge("RGB", (channel, channel, channel))


def fit(im: Image.Image, out: dict) -> Image.Image:
    if "pad_to" in out:  # keep pixels, put them top-left on a black (= transparent for `_o`) canvas
        canvas = Image.new(im.mode, tuple(out["pad_to"]), 0)
        canvas.paste(im, (0, 0))
        return canvas
    size = out.get("size")
    if isinstance(size, int):
        size = (size, size)
    if size and tuple(size) != im.size:
        return im.resize(tuple(size), Image.Resampling.LANCZOS)
    return im


def render(im: Image.Image, out: dict) -> Image.Image:
    op = out["op"]
    if op == "rgb":
        return fit(as_rgb(im), out)
    if op == "alpha":
        return fit(grey_rgb(im.convert("RGBA").getchannel("A")), out)
    if op == "luma":
        return fit(grey_rgb(im.convert("L")), out)
    if op == "channel":
        return fit(grey_rgb(as_rgb(im).getchannel(out["channel"])), out)
    if op == "flat":  # one averaged colour (TEX-09 / TEX-12); `channel` makes a grey M/R placeholder
        rgb = as_rgb(im)
        if "channel" in out:
            rgb = grey_rgb(rgb.getchannel(out["channel"]))
        colour = rgb.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        return Image.new("RGB", (out["size"], out["size"]), colour)
    if op == "sprite":  # atlas-ready flora cut-out: `sprite` index, `map` d (dilated RGB) or o (alpha)
        return sprite_map(im.convert("RGBA"), out)
    raise SystemExit(f"unknown op {op!r}")


def sprites(alpha: np.ndarray, min_gap: int = 16, min_px: int = 4096) -> list[tuple[int, int, int, int]]:
    """Plant boxes (x0, y0, x1, y1) by recursive XY-cut on empty rows/columns of the alpha mask, reading order."""
    def cut(y0, y1, x0, x1):
        mask = alpha[y0:y1, x0:x1]
        if mask.sum() < min_px:
            return []
        rows, cols = np.flatnonzero(mask.any(1)), np.flatnonzero(mask.any(0))
        y0, y1, x0, x1 = y0 + rows[0], y0 + rows[-1] + 1, x0 + cols[0], x0 + cols[-1] + 1
        for axis, idx in ((0, rows), (1, cols)):  # split at the first gap >= min_gap
            gaps = np.flatnonzero(np.diff(idx) > min_gap)
            if gaps.size:
                at = idx[gaps[0]] + 1 - idx[0]
                return cut(y0, y0 + at, x0, x1) + cut(y0 + at, y1, x0, x1) if axis == 0 else \
                    cut(y0, y1, x0, x0 + at) + cut(y0, y1, x0 + at, x1)
        return [(int(x0), int(y0), int(x1), int(y1))]
    return cut(0, alpha.shape[0], 0, alpha.shape[1])


def push_pull(rgb: np.ndarray, weight: np.ndarray) -> np.ndarray:
    """Fill colour where weight == 0 from the nearest coverage (pull: 2x box means, push: upsample); square POT."""
    if rgb.shape[0] == 1 or weight.all():
        return rgb
    w = weight[..., None]
    h = rgb.shape[0] // 2
    sum_c = (rgb * w).reshape(h, 2, h, 2, 3).sum((1, 3))
    sum_w = w.reshape(h, 2, h, 2, 1).sum((1, 3))
    coarse = push_pull(np.where(sum_w > 0, sum_c / np.maximum(sum_w, 1e-9), 0), (sum_w[..., 0] > 0).astype(float))
    fill = coarse.repeat(2, 0).repeat(2, 1)
    return np.where(w > 0, rgb, fill)


def sprite_map(im: Image.Image, out: dict) -> Image.Image:
    alpha = np.asarray(im.getchannel("A")) > out.get("threshold", 8)
    boxes = sprites(alpha)
    x0, y0, x1, y1 = boxes[out["sprite"]]
    m = out.get("margin_px", 32)
    side = max(x1 - x0, y1 - y0) + 2 * m  # square, plant bottom-centred (star plane pivot at the base)
    cx, bottom = (x0 + x1) // 2, y1 + m
    box = (cx - side // 2, bottom - side, cx - side // 2 + side, bottom)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im.crop((x0, y0, x1, y1)), (x0 - box[0], y0 - box[1]))  # only this plant's pixels, never a neighbour
    size = min(out.get("max_size", 2048), 1 << (side.bit_length() - 1))  # largest POT <= side, capped
    small = canvas.convert("RGBa").resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")  # premultiplied
    a = np.asarray(small.getchannel("A"))
    if out["map"] == "o" and out.get("binary"):  # star opacity: grey L, 0/255 at 128 (build_flora_star.py)
        mask = a >= 128
        if out.get("fill_holes_px"):
            mask = fill_small_holes(mask, out["fill_holes_px"])
        return Image.fromarray((mask * 255).astype(np.uint8), "L")
    if out["map"] == "o":
        return grey_rgb(Image.fromarray(a))
    rgb = np.asarray(small.convert("RGB")).astype(float)
    return Image.fromarray(np.clip(push_pull(rgb, (a > 0).astype(float)) + 0.5, 0, 255).astype(np.uint8), "RGB")


def fill_small_holes(mask: np.ndarray, max_px: int) -> np.ndarray:
    """Close background islands enclosed by the plant with at most `max_px` pixels (4-connected)."""
    h, w = mask.shape
    seen = mask.copy()
    out = mask.copy()
    for y, x in zip(*np.nonzero(~mask)):
        if seen[y, x]:
            continue
        stack, comp, border = [(y, x)], [], False
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            comp.append((cy, cx))
            border |= cy in (0, h - 1) or cx in (0, w - 1)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if not border and len(comp) <= max_px:
            ys, xs = zip(*comp)
            out[list(ys), list(xs)] = True
    return out


def encode(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def produce(im: Image.Image, out: dict) -> tuple[bytes, Image.Image]:
    if out.get("size") != "npm_auto":
        img = render(im, out)
        return encode(img), img
    for side in NPM_AUTO_SIZES:  # largest square size whose PNG fits 3 MiB
        img = render(im, dict(out, size=side))
        data = encode(img)
        if len(data) <= NPM_MAX_BYTES:
            return data, img
    raise SystemExit(f"{out['path']}: no NPM size <= 3 MiB")


def write_new(path: Path, data: bytes) -> str:
    if path.exists():
        if sha256(path.read_bytes()) != sha256(data):
            raise SystemExit(f"{path} exists with different bytes; refusing to overwrite")
        return "kept existing (identical bytes)"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return "written"


def checks(name: str, data: bytes, profile: str, npm_profile: dict) -> str:
    facts = png_facts(name, data)
    bad = []
    if facts.has_alpha or facts.color_type not in (0, 2) or facts.bit_depth != 8:
        bad.append("not 8-bit RGB or grey without alpha")
    side = facts.width
    if facts.width != facts.height or side & (side - 1):
        bad.append("not a square power of two")
    if profile == "npm":
        bad += [f.observed for f in npm_texture_findings({name: data}, npm_profile) if f.status != "pass"]
    if profile == "vpm" and side not in (256, 2048, 4096):
        bad.append("VPM size not 2048/4096 (or 256 placeholder)")
    return "pass" if not bad else "fail: " + "; ".join(bad)


def d207(px_per_m):
    if px_per_m is None:
        return "unknown: no real-world size in the source"
    if px_per_m >= D207_PX_PER_M:
        return f"ok: {px_per_m} >= 1000 px/m"
    return f"below: {px_per_m} < 1000 px/m (D207 grid wants 3600 px per 3.6 m tile)"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--root", required=True, type=Path, help="AGR-assets root")
    ap.add_argument("--out", required=True, type=Path, help="manifest JSON to write")
    args = ap.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    npm_profile = yaml.safe_load((ROOT / "standards/NPM_STANDARD.yaml").read_text(encoding="utf-8"))
    inbox_dir = spec["inbox"]
    raw = json.loads((args.root / inbox_dir / "manifest.json").read_text(encoding="utf-8"))
    inbox = {i["msg_id"]: dict(i, path=f"{inbox_dir}/{i['file']}") for i in raw["items"]}
    rows, seen, written = [], set(), 0
    for src in spec["sources"]:
        im, ref = load_source(args.root, inbox, src)
        for out in src["outputs"]:
            data, img = produce(im, out)
            path = out["path"].replace("{size}", str(img.width))
            if path in seen:
                raise SystemExit(f"duplicate output path {path}")
            seen.add(path)
            written += write_new(args.root / path, data) == "written"
            tile_m = out.get("tile_m", src.get("tile_m"))
            px_per_m = round(img.width / tile_m, 1) if tile_m else None
            rows.append({
                "path": path,
                "library_id": src.get("library_id"),
                "key": src["key"],
                "map": out["map"],
                "profile": out["profile"],
                "width": img.width, "height": img.height, "mode": img.mode,
                "bytes": len(data), "sha256": sha256(data),
                "px_per_m": px_per_m,
                "px_per_m_basis": src.get("tile_m_basis") if tile_m else None,
                "d207": d207(px_per_m) if out["map"] in ("d", "mask") and src.get("surface") else None,
                "op": {k: v for k, v in out.items() if k not in ("path", "map", "profile", "notes", "verdict")},
                "source": ref,
                "synthetic": False,
                "verdict": out.get("verdict", src["verdict"]),
                "notes": " ".join(x for x in (src.get("notes"), out.get("notes")) if x) or None,
                "checks": checks(path, data, out["profile"], npm_profile),
            })
    manifest = {
        "schema": 1, "version": "v001", "decision": "D239",
        "root": "G:\\Мой диск\\AGR-assets",
        "inbox": inbox_dir, "inbox_manifest_sha256": sha256((args.root / inbox_dir / "manifest.json").read_bytes()),
        "spec": args.spec.as_posix(), "tool": "tools/materials/inbox_maps.py",
        "new_library_ids": spec.get("new_library_ids", []),
        "flora_candidates": spec.get("flora_candidates", []),
        "skipped": spec.get("skipped", []),
        "maps": rows,
    }
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    failed = [r["path"] for r in rows if r["checks"] != "pass"]
    print(f"{len(rows)} maps, {written} written, {len(failed)} failed checks")
    for p in failed:
        print("  FAIL", p)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
