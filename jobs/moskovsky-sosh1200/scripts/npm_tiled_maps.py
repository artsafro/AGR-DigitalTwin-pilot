"""NPM Ground 2K diffuse maps that span one Ground UV cell (job-side, moskovsky-sosh1200 ground-npm v001).

Pattern: n/a | new-case: `agr ground site` maps one UV cell (= ``params.cell`` metres) onto the whole UDIM tile;
the library `*_npm_*` maps hold one material period (e.g. 3.6 m paving), so at an NPM cell of 54 m
(2048 / 54 = 37.9 px/m, inside the 10-40 px/m band of GND-08 / [D097]) the period is repeated
``cell / period`` times and resampled to 2048 px. No new material: every output is a tiled copy of one library map
(sha256 recorded); periods of maps whose real size is unknown in the library manifest are ASSUMED and say so.

usage: uv run python jobs/moskovsky-sosh1200/scripts/npm_tiled_maps.py LIBRARY_DIR NEW_OUT_DIR [--cell 54] [--px 2048]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

# library file, period in metres, basis (library manifest library/materials/maps_v002.json)
MAPS = {
    "19": ("19/19_paving_100x300_light_d_npm_2048.png", 3.6, "manifest: 3.6 m period at 568.9 px/m"),
    "22": ("22/22_asphalt_d_1024.png", 2.0, "ASSUMED 2.0 m: manifest 'Real-world size unknown'"),
    "27": ("27/27_rubber_crumb_d_npm_1024.png", 2.0, "ASSUMED 2.0 m: manifest 'real size of the tile unknown'"),
    "42": ("42/42_lawn_rolled_d_npm_1024.png", 2.0, "ASSUMED 2.0 m: manifest 'real size of the tile unknown'"),
    "25": ("25/25_mulch_d_npm_1024.png", 2.0, "manifest: 1024 px at 512 px/m = 2.0 m"),
    "23": ("23/23_gravel_2_8_d_npm_1024.png", 2.0, "ASSUMED 2.0 m: manifest 'real size of the tile unknown'"),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("library", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--cell", type=float, default=54.0)
    ap.add_argument("--px", type=int, default=2048)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists: give a new versioned path")
    rows = []
    for lib_id, (rel, period, basis) in MAPS.items():
        reps = a.cell / period
        if abs(reps - round(reps)) > 1e-9:
            raise SystemExit(f"{rel}: cell {a.cell} m is not a whole number of {period} m periods")
        reps = int(round(reps))
        src = a.library / rel
        with Image.open(src) as im:
            im = im.convert("RGB")
            tile = max(1, round(a.px * 2 / reps))  # oversample x2, then one Lanczos resample to the target
            small = im.resize((tile, tile), Image.LANCZOS)
        canvas = Image.new("RGB", (tile * reps, tile * reps))
        for i in range(reps):
            for j in range(reps):
                canvas.paste(small, (i * tile, j * tile))
        out_img = canvas.resize((a.px, a.px), Image.LANCZOS)
        dst = a.out / lib_id / (Path(rel).stem + f"_tiled{int(a.cell)}m_{a.px}.png")
        dst.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(dst)
        rows.append({"library_id": lib_id, "library_file": rel, "library_sha256": sha(src), "period_m": period,
                     "period_basis": basis, "repeats": reps, "cell_m": a.cell, "px": a.px,
                     "px_per_m": round(a.px / a.cell, 3), "file": str(dst.relative_to(a.out)).replace("\\", "/"),
                     "sha256": sha(dst)})
    (a.out / "manifest.json").write_text(json.dumps({
        "schema": "npm-tiled-maps/1", "library": str(a.library), "cell_m": a.cell, "px": a.px,
        "note": "derived NPM copies of library diffuse maps; not new materials", "maps": rows},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps([(r["file"], r["repeats"], r["px_per_m"]) for r in rows]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
