"""Vatutino Flora route A, run v003 (#1146, [D232], [D245]): maps -> atlas -> stars -> placement v007 -> readback -> sheet.

Job script (not a shared tool). Inputs are read-only copies and are hashed; every output goes to a new run directory
outside git (rule 57). Stages (each refuses an existing output dir):

  maps      resolve the D245 map pair per row (approved / A101 / stand-in), crop it to a square around the plant
  atlas     one 2048 Flora atlas from the cropped pairs (tools/library/flora_atlas_from_scene.py) + UV sample check
  stars     NPM star + VPM shell per row, UVs in the row's atlas cell, VPM in UDIM 1002 (tools/flora/build_flora_star.py)
  place     placement v007 on Ground v015 through place_site.run (engine #316 + Blender instancing)
  readback  export the placed Flora to FBX per variant and read it back in a fresh Blender (flora_v007_blender.py)
  sheet     renders: 6 site views + 1 species sheet NPM/VPM (visual gate, route step 9)

  uv run python jobs/VATUTINO-SITE/flora_route_a.py all --run C:/x/ev_t_c9ff2af1/run-v003
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVIDENCE = Path("G:/Мой диск/AGR-evidence/1146-flora-star")
A101_COPIES = EVIDENCE / "a101-matched"
V001_SPEC = EVIDENCE / "star-spec-v001.json"            # key -> approved map slug of the v001 stars
V001_FBM = EVIDENCE / "star-v001"                        # <key>_vpm.fbm = byte copies of the approved maps
KASATKINO_MAPS = Path("C:/Users/artsafro/Desktop/!3D viz/NTR/32_Kasatkino/flora_npm/maps")
GROUND_ZIP = Path("G:/Мой диск/AGR-evidence/371-ground-v015-route-a-20261104/session-v001.zip")
GROUND_ZIP_SHA = "7441764b82ce799684b400a6dd90fcd7a61991ff575f3fbb00d77cef1fef52bb"
GROUND_PREFIX = "artefacts/ground-v015-dcc-v001/textured/"
ADAPTER = Path("C:/x/t_d94665f2/paving_ground_inputs_v4.json")
ATLAS_ADDRESS = "VATUTINO"
UDIM_TILE = 1002                                         # G3: Ground v015 VPM = 1001 [D210]
MARGIN = 0.015                                           # D155: plane slightly larger than the plant
# Ива is not in schedule *T3509: assumed dwarf-willow band, flagged to Artem at the visual gate
IVA = {"pos": "Ива", "ru": "Ива швейцарская", "latin": "Salix helvetica", "block": "Ива швейцарская (Salix helvetica) К",
       "h_cm": [60, 100]}
SEED = 296


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path) -> str:
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def fresh(path: Path) -> Path:
    if path.exists():
        raise SystemExit(f"{path} exists: new versioned output dirs only")
    path.mkdir(parents=True)
    return path


def key_of(rec) -> str:
    pos = rec["pos"] if isinstance(rec["pos"], int) else 0
    return f"pos{pos:02d}_{rec['material_id']}" if pos else f"iva_{rec['material_id']}"


def rows():
    """flora_species records with the Ива height filled in (assumed, not in the schedule)."""
    sheet = _load("flora_species", "jobs/VATUTINO-SITE/flora_species.py")
    recs = sheet.records()
    for r in recs:
        if r["pos"] == "Ива":
            lo, hi = IVA["h_cm"]
            r.update(schedule_cm=None, assumed_cm=[lo, hi], band_m=[round(lo / 100 * 0.8, 3), round(hi / 100 * 1.2, 3)],
                     target_height_m=round((lo + hi) / 200, 3))
        r["key"] = key_of(r)
    return recs


# ------------------------------------------------------------------------------------------------ maps
def approved_sources():
    """approved-map slug -> [(diffuse, opacity)] found on disk (byte copies of library/flora/maps.json files)."""
    found = {}
    v001 = json.loads(V001_SPEC.read_text(encoding="utf-8"))
    for s in v001["species"]:
        slug = Path(s["diffuse"]).parent.name
        d = V001_FBM / f"{s['key']}_vpm.fbm"
        found.setdefault(slug, []).append((d / "diffuse-v001.png", d / "opacity-v001.png"))
    if KASATKINO_MAPS.is_dir():
        for d in KASATKINO_MAPS.iterdir():
            found.setdefault(d.name, []).append((d / "diffuse-v001.png", d / "opacity-v001.png"))
    return found


def resolve_pair(rec, found):
    ra = rec["route_a"]
    if ra["source"] == "a101":
        src = A101_COPIES / ra["a101_file"]
        want = json.loads((HERE / "flora-a101-match.json").read_text(encoding="utf-8"))["copied_sha256"][ra["a101_file"]]
        got = sha(src)
        if got != want:
            raise SystemExit(f"{src}: sha256 {got} != committed {want}")
        rgba = np.asarray(Image.open(src).convert("RGBA"))
        alpha = rgba[..., 3]
        s_rgb, s_op, side = a101_side_view(rgba[..., :3], np.where(alpha >= 128, 255, 0).astype(np.uint8))
        return {"kind": "a101", "files": {"rgba": str(src)}, "sha256": {"rgba": got},
                "alpha_binary_before": round(float(np.mean((alpha == 0) | (alpha == 255))), 4), "side_view": side,
                "rgb": s_rgb, "opacity": s_op}
    slug = Path(ra["map"]["diffuse"]).parent.name
    cands = [(d, o) for d, o in found.get(slug, []) if d.is_file() and o.is_file()]
    if not cands:
        raise SystemExit(f"pos {rec['pos']}: approved map {ra['map_key']!r} ({slug}) not found on disk")
    hashes = {(sha(d), sha(o)) for d, o in cands}
    if len(hashes) != 1:
        raise SystemExit(f"pos {rec['pos']}: copies of {slug} differ: {sorted(hashes)}")
    d, o = cands[0]
    op = np.asarray(Image.open(o).convert("L"))
    return {"kind": "approved-map", "files": {"diffuse": str(d), "opacity": str(o)},
            "copies": [[str(a), str(b)] for a, b in cands], "sha256": dict(zip(("diffuse", "opacity"), hashes.pop())),
            "rgb": np.asarray(Image.open(d).convert("RGB")), "opacity": np.where(op >= 128, 255, 0).astype(np.uint8)}


def a101_side_view(rgb, opacity):
    """A101 sheet = side view (upper right) + top view (lower left). Keep the component holding the topmost
    plant pixel (the side view); leaf gaps up to ~size/256 px are closed first so loose leaves stay with it."""
    from PIL import ImageDraw, ImageFilter
    mask = opacity >= 128
    if not mask.any():
        raise SystemExit("opacity has no plant pixels")
    size = opacity.shape[0]
    k = 2 * (size // 512) + 1
    img = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), "L").copy()  # copy: fromarray shares a read-only buffer
    if k > 1:
        img = img.filter(ImageFilter.MaxFilter(k))
    y = int(np.flatnonzero(mask.any(axis=1))[0])
    x = int(np.flatnonzero(mask[y])[0])
    ImageDraw.floodfill(img, (x, y), 128)
    keep = mask & (np.asarray(img) == 128)
    ys, xs = np.flatnonzero(keep.any(axis=1)), np.flatnonzero(keep.any(axis=0))
    out_op = np.where(keep, 255, 0).astype(np.uint8)
    out_rgb = np.where(keep[..., None], rgb, 0).astype(np.uint8)
    return out_rgb, out_op, {"close_kernel_px": k, "kept_px": int(keep.sum()), "dropped_px": int((mask & ~keep).sum()),
                             "kept_bbox": [int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1]}


def square_crop(rgb, opacity, margin=MARGIN):
    """Square window around the opaque bbox + margin (D155); outside the source = transparent. -> (rgb, op, box)."""
    mask = opacity >= 128
    if not mask.any():
        raise SystemExit("opacity has no plant pixels")
    size = opacity.shape[0]
    ys, xs = np.flatnonzero(mask.any(axis=1)), np.flatnonzero(mask.any(axis=0))
    x0, x1, y0, y1 = int(xs[0]), int(xs[-1]) + 1, int(ys[0]), int(ys[-1]) + 1
    pad = int(round(margin * size))
    side = max(x1 - x0, y1 - y0) + 2 * pad
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    left, top = cx - side // 2, cy - side // 2
    out_rgb = np.zeros((side, side, 3), np.uint8)
    out_op = np.zeros((side, side), np.uint8)
    sx0, sy0 = max(0, left), max(0, top)
    sx1, sy1 = min(rgb.shape[1], left + side), min(rgb.shape[0], top + side)
    out_rgb[sy0 - top:sy1 - top, sx0 - left:sx1 - left] = rgb[sy0:sy1, sx0:sx1]
    out_op[sy0 - top:sy1 - top, sx0 - left:sx1 - left] = opacity[sy0:sy1, sx0:sx1]
    if np.count_nonzero(out_op >= 128) != np.count_nonzero(mask):
        raise SystemExit("crop lost plant pixels")
    return out_rgb, out_op, {"source_px": size, "bbox": [x0, y0, x1, y1], "window": [left, top, side]}


def stage_maps(run: Path):
    out = fresh(run / "maps")
    found = approved_sources()
    report = []
    for r in rows():
        pair = resolve_pair(r, found)
        rgb, op, box = square_crop(pair.pop("rgb"), pair.pop("opacity"))
        d = out / r["key"]
        d.mkdir()
        Image.fromarray(rgb, "RGB").save(d / "diffuse.png")
        Image.fromarray(op, "L").save(d / "opacity.png")
        report.append({"pos": r["pos"], "key": r["key"], "material_id": r["material_id"], "kind": r["kind"],
                       "exact_latin": r["exact_latin"], "route_a": {k: v for k, v in r["route_a"].items() if k != "map"},
                       "stand_in": r["route_a"]["source"] == "stand-in", "source": pair, "crop": box,
                       "plant_fill": round(float(np.mean(op >= 128)), 4),
                       "out": {"diffuse": str(d / "diffuse.png"), "opacity": str(d / "opacity.png"),
                               "diffuse_sha256": sha(d / "diffuse.png"), "opacity_sha256": sha(d / "opacity.png")}})
    dump(out / "maps.json", {"schema": "vatutino-flora-route-a-maps-v1", "rows": report})
    print(f"maps: {len(report)} rows -> {out}")


# ------------------------------------------------------------------------------------------------ atlas
def uv_sample_check(src_rgb, src_op, atlas_rgb, atlas_op, cell, n=20000, seed=7):
    """Sample n UVs of the species map, map them into the atlas cell and compare (route step 5, <= 2 %)."""
    rng = np.random.default_rng(seed)
    uv = rng.random((n, 2))
    hs, ws = src_op.shape
    sx = np.minimum((uv[:, 0] * ws).astype(int), ws - 1)
    sy = np.minimum(((1 - uv[:, 1]) * hs).astype(int), hs - 1)
    u0, v0, u1, v1 = cell
    A = atlas_op.shape[0]
    au = u0 + uv[:, 0] * (u1 - u0)
    av = v0 + uv[:, 1] * (v1 - v0)
    ax = np.minimum((au * A).astype(int), A - 1)
    ay = np.minimum(((1 - av) * A).astype(int), A - 1)
    so, ao = src_op[sy, sx] >= 128, atlas_op[ay, ax] >= 128
    both = so & ao
    dc = np.abs(src_rgb[sy, sx].astype(int) - atlas_rgb[ay, ax].astype(int)).mean(axis=1)[both]
    return {"samples": n, "opacity_mismatch_pct": round(100.0 * float(np.mean(so != ao)), 3),
            "colour_mean_abs_diff": round(float(dc.mean()) if dc.size else 0.0, 2)}


def stage_atlas(run: Path):
    fa = _load("flora_atlas_from_scene", "tools/library/flora_atlas_from_scene.py")
    out = fresh(run / "atlas")
    maps = json.loads((run / "maps" / "maps.json").read_text(encoding="utf-8"))["rows"]
    cat = {"schema": "flora-library-v1", "species": [
        {"material_id": m["material_id"], "type": m["kind"], "latin": m["exact_latin"],
         "maps": {"diffuse": m["out"]["diffuse"], "opacity": m["out"]["opacity"], "review_status": "approved"}}
        for m in maps]}
    scene = {"schema": "flora-placed-v1", "objects": [
        {"name": m["key"], "faces": [{"material_id": m["material_id"], "uvs": [[0, 0], [1, 0], [1, 1]]}]} for m in maps]}
    dump(out / "catalogue.json", cat)
    dump(out / "scene.json", scene)
    rep = fa.build_atlas(out / "scene.json", out / "catalogue.json", out_diffuse=out / f"T_{ATLAS_ADDRESS}_Flora_Diffuse.png",
                         out_opacity=out / f"T_{ATLAS_ADDRESS}_Flora_Opacity.png", out_report=out / "atlas-report.json",
                         address=ATLAS_ADDRESS)
    a_rgb = np.asarray(Image.open(out / f"T_{ATLAS_ADDRESS}_Flora_Diffuse.png").convert("RGB"))
    a_op = np.asarray(Image.open(out / f"T_{ATLAS_ADDRESS}_Flora_Opacity.png").convert("L"))
    cells = {i["material_id"]: i["uv"] for i in rep["ids"]}
    checks = {}
    for m in maps:
        s_rgb_img = Image.open(m["out"]["diffuse"]).convert("RGB")
        s_op_img = Image.open(m["out"]["opacity"]).convert("L")
        cell = cells[m["material_id"]]
        cw = max(1, round((cell[2] - cell[0]) * rep["atlas_size"]))
        ch = max(1, round((cell[3] - cell[1]) * rep["atlas_size"]))
        # mapping check at the cell resolution (what a render of the object can show) + loss vs the full map
        at_cell = uv_sample_check(np.asarray(s_rgb_img.resize((cw, ch), Image.Resampling.LANCZOS)),
                                  np.where(np.asarray(s_op_img.resize((cw, ch), Image.Resampling.BOX)) >= 128, 255, 0),
                                  a_rgb, a_op, cell)
        full = uv_sample_check(np.asarray(s_rgb_img), np.asarray(s_op_img), a_rgb, a_op, cell)
        checks[m["key"]] = {"at_cell_resolution": at_cell, "vs_full_map": full, "cell_px": [cw, ch]}
    worst = max(c["at_cell_resolution"]["opacity_mismatch_pct"] for c in checks.values())
    worst_full = max(c["vs_full_map"]["opacity_mismatch_pct"] for c in checks.values())
    dump(out / "atlas-check.json", {"atlas_count": rep["atlas_count"], "atlas_size": rep["atlas_size"],
                                    "scale_factor": rep["scale_factor"], "fill_percent": round(rep["fill_percent"], 2),
                                    "cells": {str(k): v for k, v in cells.items()}, "uv_sample": checks,
                                    "worst_opacity_mismatch_pct": worst, "pass": worst <= 2.0,
                                    "worst_opacity_loss_vs_full_map_pct": worst_full,
                                    "diffuse_sha256": sha(out / f"T_{ATLAS_ADDRESS}_Flora_Diffuse.png"),
                                    "opacity_sha256": sha(out / f"T_{ATLAS_ADDRESS}_Flora_Opacity.png")})
    print(f"atlas: {rep['atlas_count']} x {rep['atlas_size']}, scale {rep['scale_factor']:.4f}, "
          f"fill {rep['fill_percent']:.1f} %, worst opacity mismatch at cell res {worst} % (vs full map {worst_full} %)")


# ------------------------------------------------------------------------------------------------ stars
def stage_stars(run: Path):
    maps = {m["key"]: m for m in json.loads((run / "maps" / "maps.json").read_text(encoding="utf-8"))["rows"]}
    check = json.loads((run / "atlas" / "atlas-check.json").read_text(encoding="utf-8"))
    species = []
    for r in rows():
        m = maps[r["key"]]
        tag = "" if r["route_a"]["source"] != "stand-in" else f" [stand-in: {r['route_a']['map_key']}]"
        species.append({"key": r["key"], "latin": r["exact_latin"] + tag, "kind": r["kind"],
                        "height_m": r["target_height_m"], "band_m": r["band_m"], "material_id": r["material_id"],
                        "diffuse": m["out"]["diffuse"], "opacity": m["out"]["opacity"],
                        "atlas_cell": check["cells"][str(r["material_id"])]})
    spec = {"udim_tile": UDIM_TILE, "species": species,
            "atlas": {"diffuse": str(run / "atlas" / f"T_{ATLAS_ADDRESS}_Flora_Diffuse.png"),
                      "opacity": str(run / "atlas" / f"T_{ATLAS_ADDRESS}_Flora_Opacity.png"), "size": check["atlas_size"],
                      "material": f"M_{ATLAS_ADDRESS}_Flora_1"}}
    dump(run / "star-spec-v002.json", spec)
    r = subprocess.run([sys.executable, str(ROOT / "tools/flora/build_flora_star.py"), "--spec",
                        str(run / "star-spec-v002.json"), "--out", str(run / "stars"), "--fbx"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-1500:], r.stderr[-1500:])
    if r.returncode:
        raise SystemExit(f"star build failed ({r.returncode})")


# ------------------------------------------------------------------------------------------------ place
def ground_inputs(run: Path) -> Path:
    if sha(GROUND_ZIP) != GROUND_ZIP_SHA:
        raise SystemExit(f"{GROUND_ZIP}: sha256 changed")
    dest = run / "inputs" / "ground-v015"
    if not dest.exists():
        with zipfile.ZipFile(GROUND_ZIP) as z:
            for n in z.namelist():
                rel = n[len(GROUND_PREFIX):]
                if n.startswith(GROUND_PREFIX) and rel and "fingerprint" not in rel and "independent" not in rel:
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(n))
    return dest


def stage_place(run: Path):
    ps = _load("place_site", "jobs/VATUTINO-SITE/place_site.py")
    stars = json.loads((run / "stars" / "meshes.json").read_text(encoding="utf-8"))
    inputs = run / "inputs"
    inputs.mkdir(exist_ok=True)
    ground = ground_inputs(run)
    adapter = inputs / "paving_ground_inputs_v4.json"
    if not adapter.exists():
        shutil.copy2(ADAPTER, adapter)
    fl = fresh(run / "flora_fbx")
    export, picks = {}, {}
    parts = json.loads((HERE / "site-parts.json").read_text(encoding="utf-8"))
    recs = {r["pos"]: r for r in rows()}
    flora = []
    for f in parts["flora"] + [{**IVA, "qty": recs["Ива"]["plants_in_plot"], "spozu_in": recs["Ива"]["plants_in_plot"],
                                "spozu_total": recs["Ива"]["plants_in_plot"]}]:
        r = recs[f["pos"]]
        objs = {}
        for prof in ("npm", "vpm"):
            obj = f"{r['key']}_{prof}"
            shutil.copy2(run / "stars" / f"{obj}.fbx", fl / f"{obj}.fbx")
            zs = [v[2] for v in stars[r["key"]][prof]["verts"]]
            xs = [v[0] for v in stars[r["key"]][prof]["verts"]]
            ys = [v[1] for v in stars[r["key"]][prof]["verts"]]
            export[obj] = {"ok": True, "bbmin": [min(xs), min(ys), min(zs)], "bbmax": [max(xs), max(ys), max(zs)]}
            objs[prof.upper()] = obj
        picks[f["pos"]] = r["material_id"]
        h_cm = f.get("h_cm") or IVA["h_cm"]
        flora.append({**{k: f[k] for k in ("pos", "ru", "latin", "block", "qty", "spozu_in", "spozu_total")},
                      "h_cm": h_cm, "cands": [{"id": r["material_id"], "latin": r["exact_latin"], "obj": objs,
                                               "route_a": r["route_a"]["source"]}]})
    dump(fl / "export.json", {"objects": export})
    dump(inputs / "site-parts-v007.json", {"flora": flora})
    cfg = {"adapter": adapter, "ground": ground, "flora_fbx": fl, "site_parts": inputs / "site-parts-v007.json",
           "maf_set": None, "exceptions": HERE / "ground-exceptions.json", "flora_library": "star-v002 (route A, D245)",
           "flora_picks": picks, "exact": {11, 14, 16}, "version": "v007"}
    rc = ps.run(cfg, run / "place", SEED)
    print(f"place: exit {rc}")
    if rc:
        raise SystemExit(rc)


# ------------------------------------------------------------------------------------------------ blender
def _blender(*args, timeout=7200):
    from twinqa.scene import find_blender
    cmd = [find_blender(), "--background", "--factory-startup", "--python-exit-code", "1", "--python",
           str(HERE / "flora_v007_blender.py"), "--", *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    print(r.stdout[-2000:])
    if r.returncode:
        raise SystemExit(f"blender failed {r.returncode}: {r.stderr[-3000:]}")


def stage_readback(run: Path):
    out = fresh(run / "fbx")
    for var in ("npm", "vpm"):
        blend = run / "place" / var / f"VATUTINO-SITE_placement_{var}_v007.blend"
        fbx = out / f"SM_VATUTINO-SITE_Flora_{var.upper()}_v007.fbx"
        _blender("export", blend, fbx)
        _blender("readback", fbx, out / f"readback_{var}.json", UDIM_TILE if var == "vpm" else 1001)
    print(f"readback -> {out}")


def stage_sheet(run: Path):
    out = fresh(run / "sheet")
    atlas = run / "atlas"
    _blender("site", run / "place" / "npm" / "VATUTINO-SITE_placement_npm_v007.blend",
             atlas / f"T_{ATLAS_ADDRESS}_Flora_Diffuse.png", atlas / f"T_{ATLAS_ADDRESS}_Flora_Opacity.png", out)
    _blender("species", run / "stars" / "meshes.json", atlas / f"T_{ATLAS_ADDRESS}_Flora_Diffuse.png",
             atlas / f"T_{ATLAS_ADDRESS}_Flora_Opacity.png", out)
    compose_sheets(run, out)


def compose_sheets(run: Path, out: Path):
    from PIL import ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
        small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    except OSError:
        font = small = ImageFont.load_default()
    views = sorted(out.glob("site_*.png"))
    if views:
        w, h = Image.open(views[0]).size
        cols = 3
        sheet = Image.new("RGB", (cols * w, ((len(views) + cols - 1) // cols) * (h + 34) + 50), "white")
        d = ImageDraw.Draw(sheet)
        d.text((10, 10), "Vatutino Flora v007 on Ground v015 (NPM) — #1146 route A, visual gate; passed=false", fill="black", font=font)
        for i, v in enumerate(views):
            x, y = (i % cols) * w, 50 + (i // cols) * (h + 34)
            sheet.paste(Image.open(v).convert("RGB"), (x, y))
            d.text((x + 8, y + h + 4), v.stem, fill="black", font=small)
        sheet.save(out / "sheet-site-v007.png")
    maps = {m["key"]: m for m in json.loads((run / "maps" / "maps.json").read_text(encoding="utf-8"))["rows"]}
    tiles = sorted(out.glob("sp_*_npm.png"))
    if tiles:
        w, h = Image.open(tiles[0]).size
        cols = 6
        rows_n = (len(tiles) + cols - 1) // cols
        cell_h = 2 * h + 70
        sheet = Image.new("RGB", (cols * w, rows_n * cell_h + 50), "white")
        d = ImageDraw.Draw(sheet)
        d.text((10, 10), "Flora route A stars: NPM (top) / VPM (bottom), atlas M_VATUTINO_Flora_1; red = stand-in [D245]",
               fill="black", font=font)
        for i, t in enumerate(tiles):
            key = t.stem[3:-4]
            m = maps[key]
            x, y = (i % cols) * w, 50 + (i // cols) * cell_h
            sheet.paste(Image.open(t).convert("RGB"), (x, y))
            vp = out / f"sp_{key}_vpm.png"
            if vp.exists():
                sheet.paste(Image.open(vp).convert("RGB"), (x, y + h))
            ra = m["route_a"]
            src = ra["a101_file"].split("_t")[0] + " (A101)" if ra["source"] == "a101" else ra["map_key"]
            d.text((x + 6, y + 2 * h + 4), f"{m['pos']}  {m['exact_latin']}"[:44], fill="black", font=small)
            d.text((x + 6, y + 2 * h + 26), f"{ra['source']}: {src}"[:44],
                   fill="red" if m["stand_in"] else "darkgreen", font=small)
        sheet.save(out / "sheet-species-v007.png")
    print(f"sheet -> {out}")


STAGES = {"maps": stage_maps, "atlas": stage_atlas, "stars": stage_stars, "place": stage_place,
          "readback": stage_readback, "sheet": stage_sheet}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=[*STAGES, "all", "compose"])
    ap.add_argument("--run", required=True, type=Path)
    a = ap.parse_args(argv)
    a.run.mkdir(parents=True, exist_ok=True)
    if a.stage == "compose":
        compose_sheets(a.run, a.run / "sheet")
        return 0
    for name in (STAGES if a.stage == "all" else [a.stage]):
        STAGES[name](a.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
