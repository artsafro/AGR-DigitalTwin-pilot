"""Bake the 512 NPM MAF atlas from the team atlas 53407 by a slot table (plan step 2.3).

new-case: one-off bake of a labelled 4096 source atlas into the 512 GroundEl set (MAF-09: one set <= 512 px;
TEX-07 [D020]: RGB, no alpha; TEX-13: >= 8 px between unique images; ID number small in the bottom-right corner of
every cell, Artem 2026-10-21). Reuses tools/materials/atlas_maf.py (buddy placement, edge-repeated gutters,
Lanczos) and the ID-corner drawing of tools/library/maf_atlas_ids.py / maf_atlas_layout.py.

Slot sizes are fixed by the table (solid 64, wood and log end 256), not grown. A slot with `clean` has its painted
label removed by `ring_clone` (r2, review of PR #1187: the r1 log end was a 108 px patch, upscaled).

Usage:
  uv run python jobs/maf-atlas-512/scripts/atlas_maf_from_source.py --slots jobs/maf-atlas-512/slots_53407.json \
      --out-dir "G:/Мой диск/AGR-assets/maf/atlas/v007" --out-json library/maf/atlas_512_v007.json [--rev r2]
Fail closed (exit 2, nothing written): source or ids hash/key mismatch, a crop with a label or frame pixel, a
solid crop that is not flat, a slot table that does not fit, an existing output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "library"))
sys.path.insert(0, str(ROOT / "tools" / "materials"))
import atlas_maf  # noqa: E402
from maf_atlas_ids import _font, draw_id, id_corner, save_png  # noqa: E402
from maf_atlas_layout import _uv, fit_font  # noqa: E402

ATLAS = "T_MAF_Atlas_v007_GroundEl_d_512.png"
PREVIEW = "preview_T_MAF_Atlas_v007_512_slots.png"


class BakeError(Exception):
    pass


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ring_clone(src: np.ndarray, s: dict) -> np.ndarray:
    """Remove the painted label from a log end: each label pixel takes the pixel at the same radius from the ring
    centre, rotated by the first angle in ``rotations`` whose source is clean (rings are concentric, so the same
    radius carries the same ring). Real source pixels only; a 1 px seam blend at the label border."""
    cl = s["clean"]
    x0, y0, x1, y1 = s["box"]
    cx, cy = cl["centre"]
    m = src.min(axis=2) > cl["label_min"]
    for _ in range(cl["dilate_px"]):
        n = m.copy()
        n[1:] |= m[:-1]; n[:-1] |= m[1:]; n[:, 1:] |= m[:, :-1]; n[:, :-1] |= m[:, 1:]  # noqa: E702
        m = n
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx, dy = xx - cx, yy - cy
    out = src[y0:y1, x0:x1].copy()
    todo = m[y0:y1, x0:x1].copy()
    border = todo.copy()
    for deg in cl["rotations"]:
        t = np.deg2rad(deg)
        sx = np.rint(np.cos(t) * dx - np.sin(t) * dy + cx).astype(int)
        sy = np.rint(np.sin(t) * dx + np.cos(t) * dy + cy).astype(int)
        ok = todo & (sx >= x0 - 160) & (sx < x1 + 160) & (sy >= y0 - 160) & (sy < y1 + 160)
        ok[ok] &= ~m[sy[ok], sx[ok]]
        out[ok] = src[sy[ok], sx[ok]]
        todo &= ~ok
    if todo.any():
        raise BakeError(f"slot {s['slot']}: {int(todo.sum())} label pixels found no clean ring source")
    edge = border ^ (border & np.roll(border, 1, 0) & np.roll(border, -1, 0) & np.roll(border, 1, 1)
                     & np.roll(border, -1, 1))
    f = out.astype(np.float32)
    blur = (f + np.roll(f, 1, 0) + np.roll(f, -1, 0) + np.roll(f, 1, 1) + np.roll(f, -1, 1)) / 5
    out[edge] = blur[edge].round().astype(np.uint8)
    return out


def crop_slot(src: np.ndarray, s: dict) -> np.ndarray:
    x0, y0, x1, y1 = s["box"]
    c = ring_clone(src, s) if "clean" in s else src[y0:y1, x0:x1]
    label = (c.min(axis=2) > 235).sum()  # painted IDs are pure white
    frame = ((c[:, :, 1] > 200) & (c[:, :, 0] < 60) & (c[:, :, 2] < 60)).sum()  # green 8 px frames
    if label or frame:
        raise BakeError(f"slot {s['slot']}: crop has {label} label and {frame} frame pixels")
    if s["kind"] == "solid" and int((c.max(axis=(0, 1)).astype(int) - c.min(axis=(0, 1))).max()) > 2:
        raise BakeError(f"slot {s['slot']}: solid crop is not flat")
    if s["kind"] == "patterned" and (x1 - x0) != (y1 - y0):
        raise BakeError(f"slot {s['slot']}: patterned crop must be square")
    return c


def bake(spec: dict, out_dir: Path, rev: str = "") -> dict:
    src_path = spec["source"]["path"]
    if sha256(src_path) != spec["source"]["sha256"]:
        raise BakeError("source atlas does not match its recorded SHA256")
    ids = {e["id"]: e for e in json.loads((ROOT / spec["ids"]).read_text(encoding="utf-8"))["ids"]}
    slots = spec["slots"]
    if len({s["id"] for s in slots}) != len(slots):
        raise BakeError("two slots map to one id")
    for s in slots:
        if s["id"] not in ids or ids[s["id"]]["key"] != s["key"] or not ids[s["id"]].get("atlas", True):
            raise BakeError(f"slot {s['slot']}: id {s['id']} / key {s['key']} not an atlas id of {spec['ids']}")
    with Image.open(src_path) as im:
        src = np.asarray(im.convert("RGB"))
    size, pad = spec["atlas_size"], spec["padding_px"]
    crops = [crop_slot(src, s) for s in slots]  # validate every crop before anything is written
    sfx = f"_{rev}" if rev else ""
    atlas_path = out_dir / ATLAS.replace(".png", f"{sfx}.png")
    preview_path = out_dir / PREVIEW.replace(".png", f"{sfx}.png")
    crops_dir, sums_path = out_dir / f"crops{sfx}", out_dir / f"SHA256SUMS{sfx}.txt"
    if any(p.exists() for p in (atlas_path, preview_path, crops_dir, sums_path)):
        raise BakeError(f"refusing to overwrite an output of revision {rev or 'r1'} in {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=bool(rev))
    crops_dir.mkdir()
    mats, rows = [], []
    for n, (s, c) in enumerate(zip(slots, crops)):
        row = {k: s[k] for k in ("slot", "text", "id", "key", "kind", "px", "box")}
        mean = tuple(int(v) for v in c.reshape(-1, 3).mean(axis=0).round())
        row["colour"] = "#%02X%02X%02X" % mean
        if s["kind"] == "solid":
            mats.append(atlas_maf.Material(s["key"], "solid", s["px"], n, color=tuple(int(v) for v in c[0, 0])))
        else:
            p = crops_dir / f"slot{s['slot']:02d}_ID_{s['id']:02d}_{s['key']}.png"
            if "clean" in s:
                row["clean"] = s["clean"]
            Image.fromarray(c, "RGB").save(p)
            row["crop"] = {"path": p.relative_to(out_dir).as_posix(), "sha256": sha256(p)}
            mats.append(atlas_maf.Material(s["key"], "patterned", s["px"], n, texture=p))
        if "note" in s:
            row["note"] = s["note"]
        rows.append(row)
    placed = atlas_maf._place([(m.index, m.size) for m in mats], size)
    if placed is None:
        raise BakeError("slot table does not fit the atlas")
    slot_objs = [atlas_maf.Slot(m.name, m.kind, *placed[m.index], m.size) for m in mats]
    img = atlas_maf.render_atlas(slot_objs, mats, size, pad)
    d = ImageDraw.Draw(img)
    by_key = {s["key"]: s for s in slots}
    cells = []
    for so in slot_objs:
        content = list(atlas_maf._content_box(so.x, so.y, so.size, pad))
        corner = id_corner(content)
        sid = by_key[so.name]["id"]
        zx, zy, zs, _ = corner
        draw_id(d, (zx, zy, zx + zs - 1, zy + zs - 1), str(sid), fit_font(str(sid), zs))
        cells.append({"id": sid, "key": so.name, "kind": so.kind, "slot_px": [so.x, so.y, so.size, so.size],
                      "content_px": content, "id_corner_px": corner, "uv": _uv(content, size)})
    cells.sort(key=lambda c: c["id"])
    save_png(img, str(atlas_path))
    render_preview(img, cells, by_key, preview_path)
    with Image.open(atlas_path) as chk:
        mode, dims = chk.mode, list(chk.size)
    used = sum(c["slot_px"][2] ** 2 for c in cells)
    files = [atlas_path, preview_path, *sorted(crops_dir.iterdir())]
    sums = "".join(f"{sha256(f)} *./{f.relative_to(out_dir).as_posix()}\n" for f in files)
    sums_path.write_text(sums, encoding="utf-8", newline="\n")
    return {
        "schema": "library-maf-atlas-512",
        "version": "v007",
        "revision": rev or "r1",
        "status": "technical QA only; visual acceptance by the user open",
        "decision": "pine as its own WOOD2 id 33: user 2026-11-10 (plan step 2.3); D id to be assigned at merge",
        "generated_by": "jobs/maf-atlas-512/scripts/atlas_maf_from_source.py",
        "inputs": {
            "source": {k: spec["source"][k] for k in ("path", "sha256", "size")},
            "id_map": spec["source"]["id_map"],
            "slots": {"path": "jobs/maf-atlas-512/slots_53407.json"},
            "ids": {"path": spec["ids"], "sha256": sha256(ROOT / spec["ids"])},
        },
        "atlas": {"path": atlas_path.as_posix(), "sha256": sha256(atlas_path), "bytes": atlas_path.stat().st_size,
                  "size": dims, "mode": mode},
        "preview": {"path": preview_path.as_posix(), "sha256": sha256(preview_path)},
        "padding_px": pad,
        "free_share": round(1 - used / size ** 2, 4),
        "slots": rows,
        "cells": cells,
    }


def render_preview(img: Image.Image, cells: list, by_key: dict, path: Path) -> None:
    scale = 2
    big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(big)
    font = _font(14)
    for c in cells:
        x, y, w, _ = (v * scale for v in c["slot_px"])
        d.rectangle((x, y, x + w - 1, y + w - 1), outline=(255, 0, 255))
        s = by_key[c["key"]]
        for i, line in enumerate((f"slot {s['slot']} -> ID {c['id']}", c["key"])):
            tb = d.textbbox((0, 0), line, font=font)
            tx, ty = x + 4, y + 4 + i * 17
            d.rectangle((tx - 2, ty - 1, tx + tb[2] - tb[0] + 2, ty + tb[3] + 1), fill=(255, 255, 255))
            d.text((tx - tb[0], ty), line, fill=(0, 0, 0), font=font)
    save_png(big, str(path))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slots", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--rev", default="", help="review revision (r2, ...): new suffixed files next to the earlier "
                    "ones; the record is replaced and keeps the earlier atlas under 'previous'")
    a = ap.parse_args(argv)
    try:
        prev = None
        if os.path.exists(a.out_json):
            if not a.rev:
                raise BakeError(f"refusing to overwrite {a.out_json}")
            old = json.loads(Path(a.out_json).read_text(encoding="utf-8"))
            prev = old.get("previous", []) + [{"revision": old.get("revision", "r1"), "atlas": old["atlas"],
                                               "preview": old["preview"]}]
        spec = json.loads(Path(a.slots).read_text(encoding="utf-8"))
        rec = bake(spec, Path(a.out_dir), a.rev)
        if prev:
            rec["previous"] = prev
    except (BakeError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    Path(a.out_json).write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"atlas": rec["atlas"], "free_share": rec["free_share"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
