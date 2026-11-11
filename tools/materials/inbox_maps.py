"""Process inbox originals into library maps and write the maps manifest [D239].

    uv run python tools/materials/inbox_maps.py --spec library/materials/maps_v001.spec.json \
        --root "G:/Мой диск/AGR-assets" --out library/materials/maps_v001.json

The spec names, per source, the outputs to write under --root: plain RGB copies or
resamples, one-colour placeholders, single channels, alpha -> `_o` grey maps, padding to a power of
two. A source is one of:
* `src`: an inbox msg id; the original is only read (sha256 checked against the inbox manifest.json);
* `file`: an image from one of our own projects (absolute path, expected sha256, `project`); only read;
* `generate`: a synthetic recipe of `texture_surfaces.py` (rows get `synthetic: true`); outputs pick
  the generated image by `image` (`d`, `n`, `mask`) and may tile it `repeat` x `repeat` first.
`base_manifest` (optional) carries the rows of an earlier manifest over unchanged (v002 = v001 + new);
it must have been written under the same --root.
Profile `d207` is the master at exactly 1000 px/m over a whole period (size need not be a power of two).
An output that already exists is never overwritten: identical bytes are kept, different bytes stop the
run. Every output is a PNG, 8 bit RGB, no alpha; NPM outputs are checked with twinqa.png (V006 rules).
Manifest paths are relative to --root (the D239 layout) and the manifest records that root.

Pattern: n/a | new-case: inbox -> library map processing with a hashed manifest (#1188); no registry
pattern in docs/domain/patterns/INDEX.md covers texture intake.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import texture_surfaces  # noqa: E402

Image.MAX_IMAGE_PIXELS = None  # own 4096 project maps

NPM_MAX_BYTES = 3 * 1024 * 1024  # [D015], reg p.9 §5.3
NPM_AUTO_SIZES = (2048, 1024, 512)
D207_PX_PER_M = 1000  # texture grid: 3.6 m per UDIM tile at 1000 px/m [D207]
DEFAULT_ROOT = Path("G:/Мой диск/AGR-assets")  # D239 layout root


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_source(root: Path, inbox: dict, src: dict):
    """(image or {name: image}, source ref, synthetic, generated period in metres or None)."""
    if "generate" in src:
        gen = src["generate"]
        images, period_m, info = texture_surfaces.generate(gen)
        ref = {"generator": "tools/materials/texture_surfaces.py", "recipe": gen,
               "recipe_sha256": sha256(json.dumps(gen, sort_keys=True).encode()), "info": info}
        return images, ref, True, period_m
    if "file" in src:
        path = Path(src["file"])
        data = path.read_bytes()
        if sha256(data) != src["sha256"]:
            raise SystemExit(f"{path}: sha256 differs from the spec")
        im = Image.open(io.BytesIO(data))
        im.load()
        ref = {"file": str(path), "sha256": src["sha256"], "project": src["project"]}
        if src.get("made_by"):
            ref["made_by"] = src["made_by"]
        return im, ref, False, None
    im, ref = load_inbox(root, inbox, src)
    return im, ref, False, None


def load_inbox(root: Path, inbox: dict, src: dict) -> tuple[Image.Image, dict]:
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
    n = out.get("repeat", 1)
    if n > 1:  # whole periods side by side before the resample keep the map tileable
        tiled = Image.new(im.mode, (im.width * n, im.height * n))
        for i in range(n):
            for j in range(n):
                tiled.paste(im, (i * im.width, j * im.height))
        im = tiled
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
    if op == "solid":  # a given colour, e.g. ERM placeholder from the library record (emissive, roughness, metallic)
        return Image.new("RGB", (out["size"], out["size"]), tuple(out["rgb"]))
    if op == "height_normal":  # 8/16-bit height map (white = depth_m) -> DirectX normal (green down), wrapped
        a = np.asarray(im, np.float32)
        a = a / (65535.0 if im.mode.startswith("I") else 255.0)
        h = np.asarray(fit(Image.fromarray(a[..., 0] if a.ndim == 3 else a, "F"), out)) * out["depth_m"]
        px_m = out["tile_m"] / h.shape[1]
        dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * px_m)
        dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * px_m)
        nrm = np.stack([-dx, dy, np.ones_like(dx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        return Image.fromarray(np.clip(np.rint((nrm * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8), "RGB")
    if op == "erm_from_roughness":  # grey roughness map -> ERM: R emissive, G roughness, B metallic
        g = fit(im.convert("L"), out)
        return Image.merge("RGB", (Image.new("L", g.size, out.get("emissive", 0)), g,
                                   Image.new("L", g.size, out.get("metallic", 0))))
    raise SystemExit(f"unknown op {op!r}")


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


def checks(name: str, data: bytes, profile: str, npm_profile: dict, tile_m=None) -> str:
    facts = png_facts(name, data)
    bad = []
    if facts.has_alpha or facts.color_type != 2 or facts.bit_depth != 8:
        bad.append("not 8-bit RGB without alpha")
    side = facts.width
    if profile == "d207":  # master: one whole period at exactly 1000 px/m [D207]
        if not tile_m or facts.width != facts.height or side != round(tile_m * D207_PX_PER_M):
            bad.append(f"d207 master is not {tile_m} m x 1000 px/m")
    elif facts.width != facts.height or side & (side - 1):
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
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=f"AGR-assets root (default {DEFAULT_ROOT})")
    ap.add_argument("--out", required=True, type=Path, help="manifest JSON to write")
    args = ap.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    npm_profile = yaml.safe_load((ROOT / "standards/NPM_STANDARD.yaml").read_text(encoding="utf-8"))
    inbox_dir = spec["inbox"]
    raw = json.loads((args.root / inbox_dir / "manifest.json").read_text(encoding="utf-8"))
    inbox = {i["msg_id"]: dict(i, path=f"{inbox_dir}/{i['file']}") for i in raw["items"]}
    base = json.loads((ROOT / spec["base_manifest"]).read_text(encoding="utf-8")) if "base_manifest" in spec else {}
    if base and Path(base["root"]) != args.root:  # carried rows are relative to the base manifest's root
        raise SystemExit(f"base manifest root {base['root']} differs from --root {args.root}")
    rows = list(base.get("maps", []))
    seen = {r["path"] for r in rows}
    for src in spec["sources"]:
        loaded, ref, synthetic, period_m = load_source(args.root, inbox, src)
        print(src["key"], flush=True)
        for out in src["outputs"]:
            if period_m and "tile_m" not in out and out["op"] not in ("flat", "solid"):  # covers repeat x period m
                out = dict(out, tile_m=round(period_m * out.get("repeat", 1), 6))
            im = loaded[out.get("image", "d")] if isinstance(loaded, dict) else loaded
            data, img = produce(im, out)
            path = out["path"].replace("{size}", str(img.width))
            if path in seen:
                raise SystemExit(f"duplicate output path {path}")
            seen.add(path)
            state = write_new(args.root / path, data)
            tile_m = out.get("tile_m", src.get("tile_m"))
            px_per_m = round(img.width / tile_m, 1) if tile_m else None
            basis = src.get("tile_m_basis")
            if period_m:
                basis = f"generated: {tile_m} m ({out.get('repeat', 1)} x {period_m} m period) at 1000 px/m [D207]"
            rows.append({
                "path": path,
                "library_id": src.get("library_id"),
                "key": src["key"],
                "map": out["map"],
                "profile": out["profile"],
                "width": img.width, "height": img.height, "mode": img.mode,
                "bytes": len(data), "sha256": sha256(data),
                "px_per_m": px_per_m,
                "px_per_m_basis": basis if tile_m else None,
                "d207": d207(px_per_m) if out["map"] in ("d", "mask") and src.get("surface") else None,
                "op": {k: v for k, v in out.items() if k not in ("path", "map", "profile", "notes", "verdict")},
                "source": ref,
                "synthetic": synthetic,
                "verdict": out.get("verdict", src["verdict"]),
                "notes": " ".join(x for x in (src.get("notes"), out.get("notes")) if x) or None,
                "checks": checks(path, data, out["profile"], npm_profile, tile_m),
                "write": state,
            })
            if "provenance" in src:  # licence risk of the source, readable by the next agent
                rows[-1]["provenance"] = src["provenance"]
    manifest = {
        "schema": 1, "version": spec.get("version", "v001"), "decision": "D239",
        "root": str(args.root),  # the root the files were written under; paths below are relative to it
        "inbox": inbox_dir, "inbox_manifest_sha256": sha256((args.root / inbox_dir / "manifest.json").read_bytes()),
        "spec": args.spec.as_posix(), "tool": "tools/materials/inbox_maps.py",
        "base_manifest": spec.get("base_manifest"),
        "new_library_ids": base.get("new_library_ids", []) + spec.get("new_library_ids", []),
        "skipped": base.get("skipped", []) + spec.get("skipped", []),
        "excluded_sources": spec.get("excluded_sources", []),
        "maps": rows,
    }
    if not base:
        del manifest["base_manifest"], manifest["excluded_sources"]
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    failed = [r["path"] for r in rows if r["checks"] != "pass"]
    print(f"{len(rows)} maps, {sum(r['write'] == 'written' for r in rows)} written, {len(failed)} failed checks")
    for p in failed:
        print("  FAIL", p)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
