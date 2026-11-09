"""Shared NPM atlas step (`dt derive atlas`): one 2048 atlas per OKS from a VPM texture spec.

Pattern: n/a | new-case: one shared NPM atlas tool replacing the per-job make_npm_atlas.py copies (#1106).

Generalised from jobs/TEC26-OKS/scripts/make_npm_atlas.py (KPP1 recipe, accepted AC08 pilot-v010), which is
itself the KPP1 v005 script with an explicit spec; PSU275's extra-OKS options are --address / --index.
Usage: python tools/derive/npm_atlas.py <spec.json> <new_out_dir> [--address A] [--index N] [--recipe-dir D]
Writes T_<A>_<NNN>_Main_d_1.png (Diffuse RGB), T_<A>_<NNN>_Main_o_1.png (Opacity RGB, white = solid,
reg p.9 §5.8; no alpha anywhere, conflict #21) and npm_atlas.json (finish -> region). One square region per
finish on a 5 x 4 grid of 409 px cells, 6 px edge padding (reg p.9 §5.4); each region stands for the
finish's VPM tile S metres, joints >= 1.5 px. Texture painters (make_textures, finish_map) come from the
recipe dir (default jobs/TEC26-OKS/scripts, the KPP recipe library).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RECIPE = os.path.normpath(os.path.join(HERE, "..", "..", "jobs", "TEC26-OKS", "scripts"))

ATLAS, CELL, PAD, COLS = 2048, 409, 6, 5
REGION = CELL - 2 * PAD
NPM_JOINT_HALF_MM = 8  # 16 mm on the atlas ~ 1.5 px at 97 px/m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="VPM texture spec JSON (address, size_full, finishes)")
    ap.add_argument("out", help="new, empty output directory")
    ap.add_argument("--address", help="NPM address (default: spec address); extra OKS share the main address")
    ap.add_argument("--index", type=int, default=1, help="OKS index inside the NPM package (NNN), default 1")
    ap.add_argument("--recipe-dir", default=RECIPE, help="directory with make_textures.py / finish_map.py")
    a = ap.parse_args(argv)
    if not 1 <= a.index <= 999:
        raise ValueError(f"OKS index {a.index} outside 1..999")
    sys.path.insert(0, a.recipe_dir)
    import finish_map
    import make_textures as mt
    spec = json.load(open(a.spec, encoding="utf-8"))
    finish_map.validate_spec(spec, finish_map.load_kpp())
    if len(spec["finishes"]) > COLS * (ATLAS // CELL):
        raise ValueError(f"{len(spec['finishes'])} finishes do not fit the {COLS} x {ATLAS // CELL} atlas grid")
    addr = a.address or spec["address"]
    if not addr:
        raise ValueError("empty NPM address")
    nnn = f"{a.index:03d}"
    out = a.out
    finish_map.fresh_out_dir(out, [a.spec, HERE, a.recipe_dir])
    dif = np.zeros((ATLAS, ATLAS, 3), np.uint8)
    opa = np.full((ATLAS, ATLAS, 3), 255, np.uint8)
    layout = {}
    for k, (f, t) in enumerate(sorted(spec["finishes"].items(), key=lambda kv: kv[1]["udim"])):
        cx, cy = (k % COLS) * CELL, (k // COLS) * CELL      # cell origin, image rows from the top
        if t["kind"] == "full":
            # >= 1.5 px joints whatever metres the region spans (S = 4.096 gives the KPP value 8 mm)
            tt = dict(t, joint_half_mm=max(NPM_JOINT_HALF_MM, math.ceil(750 * t.get("S", 4.096) / REGION)))
            d, alpha, _, _ = mt.make_full(tt, spec["size_full"])
            reg = np.asarray(Image.fromarray(d, "RGB").resize((REGION, REGION), Image.LANCZOS))
            if alpha is not None:
                m = np.asarray(Image.fromarray(alpha, "L").resize((REGION, REGION), Image.BOX))
                solid = m >= 128                                  # 0-127 void, 128-255 solid (reg p.36 §12.2)
                o = np.where(solid, 255, 0).astype(np.uint8)
                o = np.pad(o, PAD, mode="edge")
                opa[cy:cy + CELL, cx:cx + CELL] = o[..., None]
                mean = d[alpha >= 128].mean(0) if (alpha >= 128).any() else d.reshape(-1, 3).mean(0)
                reg = np.where(solid[..., None], reg, mean.round().astype(np.uint8))  # void colour = average
        else:  # placeholder / solid finishes: flat colour (missing "rgb" -> KeyError naming it)
            reg = np.broadcast_to(np.array(t["rgb"], np.uint8), (REGION, REGION, 3))
        dif[cy:cy + CELL, cx:cx + CELL] = np.pad(reg, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
        # region in UV space (v up): x0, y0 of the region's lower-left corner and its size
        layout[f] = {"udim": t["udim"], "u0": (cx + PAD) / ATLAS, "v0": 1 - (cy + PAD + REGION) / ATLAS,
                     "size": REGION / ATLAS, "px_per_m": round(REGION / t.get("S", 4.096), 1)
                     if t["kind"] == "full" else None}
        print(f, t["udim"], t["kind"], (cx, cy))
    dn = os.path.join(out, f"T_{addr}_{nnn}_Main_d_1.png")
    on = os.path.join(out, f"T_{addr}_{nnn}_Main_o_1.png")
    Image.fromarray(dif, "RGB").save(dn, optimize=True)
    Image.fromarray(opa, "RGB").save(on, optimize=True)
    json.dump({"atlas": ATLAS, "cell": CELL, "pad": PAD, "region": REGION, "finishes": layout},
              open(os.path.join(out, "npm_atlas.json"), "w", encoding="utf-8"), indent=1)
    for p in (dn, on):
        print(os.path.basename(p), os.path.getsize(p), "bytes")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
