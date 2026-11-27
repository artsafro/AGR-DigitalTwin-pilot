"""NPM UV + white sheet for the accepted marking mesh (moskovsky-sosh1200 ground-npm v003) - geometry unchanged.

Pattern: n/a | new-case: the v002 marking mesh (accepted geometry, frozen) gets UVs in its own UDIM tile placed right after
the Ground cover tiles (consecutive from 1001 [D399]; one more Ground texture set, GND-02 <= 20 surface sets), the same
cell mapping as the Ground (cell metres -> one tile, so 2048 / cell px/m, GND-08 band) and a flat white 2048 sheet.
Per triangle the cell is taken at its centroid and corners are clamped to the tile (flat colour: no visible effect,
no straddling). Vertex lines are copied byte for byte.

usage: uv run python jobs/moskovsky-sosh1200/scripts/markings_uv.py IN.obj NEW_DIR NAME UDIM [--cell 54] [--rgb 240 240 240]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image
from twinqa.uv import tile_origin


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("name")
    ap.add_argument("udim", type=int)
    ap.add_argument("--cell", type=float, default=54.0)
    ap.add_argument("--rgb", type=int, nargs=3, default=[240, 240, 240])
    ap.add_argument("--px", type=int, default=2048)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists: give a new versioned path")
    du, dv = tile_origin(a.udim)
    lines = a.src.read_text(encoding="utf-8").splitlines()
    V = [tuple(map(float, l.split()[1:4])) for l in lines if l.startswith("v ")]
    a.out.mkdir(parents=True)
    tex = f"T_{a.name.removeprefix('SM_')}_Diffuse_Marking_White.{a.udim}.png"
    Image.new("RGB", (a.px, a.px), tuple(a.rgb)).save(a.out / tex)
    out, vt, faces = [], 1, 0
    for l in lines:
        if l.startswith("mtllib"):
            out.append(f"mtllib {a.name}.mtl")
        elif l.startswith("f "):
            idx = [int(t) for t in l.split()[1:]]
            pts = [V[i - 1] for i in idx]
            cx = math.floor(sum(p[0] for p in pts) / 3 / a.cell)
            cy = math.floor(sum(p[1] for p in pts) / 3 / a.cell)
            for x, y, _ in pts:
                u = min(max(x / a.cell - cx, 0.0), 1.0)
                v = min(max(y / a.cell - cy, 0.0), 1.0)
                out.append(f"vt {u + du:.7f} {v + dv:.7f}")
            out.append("f " + " ".join(f"{i}/{vt + k}" for k, i in enumerate(idx)))
            vt += 3; faces += 1
        else:
            out.append(l)
    (a.out / f"{a.name}.obj").write_text("\n".join(out) + "\n", encoding="utf-8")
    (a.out / f"{a.name}.mtl").write_text(f"newmtl Marking_White\nKd 1.000000 1.000000 1.000000\nmap_Kd {tex}\n",
                                         encoding="utf-8")
    rep = {"source_obj": str(a.src), "source_sha256": hashlib.sha256(a.src.read_bytes()).hexdigest(), "udim": a.udim,
           "cell_m": a.cell, "px": a.px, "px_per_m": round(a.px / a.cell, 3), "rgb": a.rgb, "texture": tex,
           "faces": faces, "vertices": len(V)}
    (a.out / "markings-uv.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
