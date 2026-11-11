"""Process inbox originals into library maps and write the maps manifest [D239].

    uv run python tools/materials/inbox_maps.py --spec library/materials/maps_v001.spec.json \
        --root "G:/Мой диск/AGR-assets" --out library/materials/maps_v001.json

The spec names, per inbox source (msg id), the outputs to write under --root: plain RGB copies or
resamples, one-colour placeholders, single channels, alpha -> `_o` grey maps, padding to a power of
two. Inbox originals are only read (sha256 checked against the inbox manifest.json). An output that
already exists is never overwritten: identical bytes are kept, different bytes stop the run.
Every output is a PNG, 8 bit RGB, no alpha; NPM outputs are checked with twinqa.png (V006 rules).
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

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from twinqa.png import npm_texture_findings, png_facts  # noqa: E402

NPM_MAX_BYTES = 3 * 1024 * 1024  # [D015], reg p.9 §5.3
NPM_AUTO_SIZES = (2048, 1024, 512)
D207_PX_PER_M = 1000  # texture grid: 3.6 m per UDIM tile at 1000 px/m [D207]
DEFAULT_ROOT = Path("G:/Мой диск/AGR-assets")  # D239 layout root


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


def checks(name: str, data: bytes, profile: str, npm_profile: dict) -> str:
    facts = png_facts(name, data)
    bad = []
    if facts.has_alpha or facts.color_type != 2 or facts.bit_depth != 8:
        bad.append("not 8-bit RGB without alpha")
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
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=f"AGR-assets root (default {DEFAULT_ROOT})")
    ap.add_argument("--out", required=True, type=Path, help="manifest JSON to write")
    args = ap.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    npm_profile = yaml.safe_load((ROOT / "standards/NPM_STANDARD.yaml").read_text(encoding="utf-8"))
    inbox_dir = spec["inbox"]
    raw = json.loads((args.root / inbox_dir / "manifest.json").read_text(encoding="utf-8"))
    inbox = {i["msg_id"]: dict(i, path=f"{inbox_dir}/{i['file']}") for i in raw["items"]}
    rows, seen = [], set()
    for src in spec["sources"]:
        im, ref = load_source(args.root, inbox, src)
        for out in src["outputs"]:
            data, img = produce(im, out)
            path = out["path"].replace("{size}", str(img.width))
            if path in seen:
                raise SystemExit(f"duplicate output path {path}")
            seen.add(path)
            state = write_new(args.root / path, data)
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
                "write": state,
            })
    manifest = {
        "schema": 1, "version": "v001", "decision": "D239",
        "root": str(args.root),  # the root the files were written under; paths below are relative to it
        "inbox": inbox_dir, "inbox_manifest_sha256": sha256((args.root / inbox_dir / "manifest.json").read_bytes()),
        "spec": args.spec.as_posix(), "tool": "tools/materials/inbox_maps.py",
        "new_library_ids": spec.get("new_library_ids", []),
        "skipped": spec.get("skipped", []),
        "maps": rows,
    }
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    failed = [r["path"] for r in rows if r["checks"] != "pass"]
    print(f"{len(rows)} maps, {sum(r['write'] == 'written' for r in rows)} written, {len(failed)} failed checks")
    for p in failed:
        print("  FAIL", p)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
