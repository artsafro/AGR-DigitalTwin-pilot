"""Shared NPM atlas step (`dt derive atlas`): one 2048 atlas per OKS from a VPM texture spec.

Pattern: n/a | new-case: one shared NPM atlas tool replacing the per-job make_npm_atlas.py copies (#1106).

Generalised from jobs/TEC26-OKS/scripts/make_npm_atlas.py (KPP1 recipe, accepted AC08 pilot-v010), which is
itself the KPP1 v005 script with an explicit spec; PSU275's extra-OKS options are --address / --index.
Usage: python tools/derive/npm_atlas.py <spec.json> <new_out_dir> [--address A] [--index N] [--recipe-dir D]
Writes T_<A>_<NNN>_Main_d_1.png (Diffuse RGB), T_<A>_<NNN>_Main_o_1.png (Opacity RGB, white = solid,
reg p.9 §5.8; no alpha anywhere, conflict #21) and npm_atlas.json (finish -> region). One square region per
finish on a 5 x 4 grid of 409 px cells, 16 px per-side edge extrusion [D278], hence 32 px between
adjacent regions and >=16 px at the outer atlas edge (reg p.9 §5.4 floor: 8 px between islands).
--cell / --pad retain an explicitly approved job layout (R1: 512 / 8 [D280]);
padding below 4 px per side is refused before writes (8 px inter-island floor).
Each region (377 px by default) stands for the
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

ATLAS, CELL, PAD, COLS = 2048, 409, 16, 5  # [D278]: per-side padding; adjacent regions have a 32 px gap.
REGION = CELL - 2 * PAD
NPM_JOINT_HALF_MM = 8  # 16 mm on the atlas ~ 1.5 px at 97 px/m


def validate_export(layout_path, diffuse_path, opacity_path):
    """Read exported UV rectangles + RGB PNGs; measure spacing, not a declared `pad`.

    Scope: this generator's square, axis-aligned cell layout (not arbitrary FBX islands).
    Colours alone cannot identify UV islands, especially flat or identical finishes.
    Geometry is measured from exported UV bounds against decoded PNG dimensions;
    every occupied cell's edge extrusion is independently checked in both images.
    This read-only check never writes a receipt that could become stale.
    """
    from pathlib import Path

    paths = [Path(p).resolve(strict=True) for p in (layout_path, diffuse_path, opacity_path)]
    if any(os.path.samefile(a, b) for i, a in enumerate(paths) for b in paths[i+1:]):
        raise ValueError('atlas inputs must be distinct files')
    raw = [p.read_bytes() for p in paths]
    import io
    data = json.loads(raw[0])
    if not isinstance(data, dict) or data.get('atlas') != ATLAS:
        raise ValueError('unsupported atlas layout: expected 2048 px')
    cell, pad = data.get('cell'), data.get('pad')
    if (type(cell) is not int or type(pad) is not int or not 1 <= cell <= ATLAS
            or pad < 4 or 2*pad >= cell):
        raise ValueError('invalid cell/pad: require >= 4 px per side (8 px regulatory floor)')
    cols = ATLAS // cell
    finishes = data.get('finishes')
    if not isinstance(finishes, dict) or not 1 <= len(finishes) <= cols*cols:
        raise ValueError(f'atlas needs 1..{cols*cols} finish regions')
    images = []
    for content in raw[1:]:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != 'PNG' or image.mode != 'RGB' or image.size != (ATLAS, ATLAS):
                raise ValueError('atlas must be a 2048 x 2048 RGB PNG')
            images.append(np.asarray(image).copy())
    rectangles, udims, cells, margins, sides = [], set(), set(), [], []
    for name, region in finishes.items():
        if not isinstance(region, dict):
            raise ValueError(f'finish {name}: missing region')
        udim = region.get('udim')
        if type(udim) is not int or not 1001 <= udim <= 1100 or udim in udims:
            raise ValueError(f'finish {name}: invalid or duplicate UDIM {udim}')
        udims.add(udim)
        uv = [region.get(k) for k in ('u0', 'v0', 'size')]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in uv):
            raise ValueError(f'finish {name}: finite numeric u0/v0/size required')
        u, v, size = uv
        pixel = [u*ATLAS, (1-v-size)*ATLAS, size*ATLAS]
        if any(not math.isfinite(x) or abs(x-round(x)) > 1e-7 for x in pixel):
            raise ValueError(f'finish {name}: bounds must be finite whole pixels')
        x, y, length = map(round, pixel)
        if length <= 0 or x < 0 or y < 0 or x+length > ATLAS or y+length > ATLAS:
            raise ValueError(f'finish {name}: region outside atlas or empty')
        cx, cy = x//cell*cell, y//cell*cell
        if cx//cell >= cols or cy//cell >= cols or (cx, cy) in cells:
            raise ValueError(f'finish {name}: duplicate or unsupported cell')
        cells.add((cx, cy))
        side = min(x-cx, y-cy, cx+cell-x-length, cy+cell-y-length)
        edge = min(x, y, ATLAS-x-length, ATLAS-y-length)
        if side < pad or edge < pad:
            raise ValueError(f'finish {name}: measured edge {edge} px, per-side {side} px; '
                             f'require {pad} px per side from layout (8 px regulatory floor between islands)')
        margins.append(edge)
        sides.append(side)
        rectangles.append((name, x, y, x+length, y+length))
        for image in images:
            core = image[y:y+length, x:x+length]
            expected = np.pad(core, ((y-cy, cy+cell-y-length),
                                     (x-cx, cx+cell-x-length), (0, 0)), mode='edge')
            if not np.array_equal(expected, image[cy:cy+cell, cx:cx+cell]):
                raise ValueError(f'finish {name}: exported padding pixels are not edge-extruded')
    gaps = []
    for i, (name, x0, y0, x1, y1) in enumerate(rectangles):
        for other, a0, b0, a1, b1 in rectangles[i+1:]:
            dx, dy = max(x0-a1, a0-x1, 0), max(y0-b1, b0-y1, 0)
            gap = math.hypot(dx, dy)
            if gap < 2*pad:
                raise ValueError(f'{name}/{other}: measured gap {gap:g} px; require {2*pad} px '
                                 f'= 2 x {pad} px per side (8 px regulatory floor)')
            gaps.append(gap)
    if any(p.read_bytes() != content for p, content in zip(paths, raw)):
        raise ValueError('atlas input changed during readback')
    return {'regions': len(rectangles), 'edge_margin_px': min(margins),
            'per_side_padding_px': min(sides), 'region_gap_px': min(gaps) if gaps else None,
            'usable_area_px': sum((r[3]-r[1])*(r[4]-r[2]) for r in rectangles),
            'bleed_checked_maps': 2}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs='?', help="VPM texture spec JSON (address, size_full, finishes)")
    ap.add_argument("out", nargs='?', help="new, empty output directory")
    ap.add_argument('--check', nargs=3, metavar=('LAYOUT', 'DIFFUSE', 'OPACITY'),
                    help='read-only measurement of an exported atlas layout and its two PNGs')
    ap.add_argument("--address", help="NPM address (default: spec address); extra OKS share the main address")
    ap.add_argument("--index", type=int, default=1, help="OKS index inside the NPM package (NNN), default 1")
    ap.add_argument("--recipe-dir", default=RECIPE, help="directory with make_textures.py / finish_map.py")
    ap.add_argument("--cell", type=int, default=CELL, help="atlas cell pixels (default: 409)")
    ap.add_argument("--pad", type=int, default=PAD, help="padding inside each cell (default: 16)")
    a = ap.parse_args(argv)
    if a.check:
        if a.spec or a.out:
            ap.error('--check cannot be combined with generation')
        print(json.dumps(validate_export(*a.check), sort_keys=True))
        return 0
    if not a.spec or not a.out:
        ap.error('generation requires spec and out')
    cell, pad = a.cell, a.pad
    if not 1 <= cell <= ATLAS or not 0 <= pad or 2 * pad >= cell:
        raise ValueError("layout requires 1 <= cell <= 2048 and 0 <= 2*pad < cell")
    if pad < 4:
        raise ValueError("layout requires >= 4 px per side: 8 px regulatory floor between islands")
    cols, region = ATLAS // cell, cell - 2 * pad
    if not 1 <= a.index <= 999:
        raise ValueError(f"OKS index {a.index} outside 1..999")
    sys.path.insert(0, a.recipe_dir)
    import finish_map
    import make_textures as mt
    spec = json.load(open(a.spec, encoding="utf-8"))
    finish_map.validate_spec(spec, finish_map.load_kpp())
    if len(spec["finishes"]) > cols * (ATLAS // cell):
        raise ValueError(f"{len(spec['finishes'])} finishes do not fit the {cols} x {ATLAS // cell} atlas grid")
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
        cx, cy = (k % cols) * cell, (k // cols) * cell      # cell origin, image rows from the top
        if t["kind"] == "full":
            # >= 1.5 px joints whatever metres the region spans (S = 4.096 gives the KPP value 8 mm)
            tt = dict(t, joint_half_mm=max(NPM_JOINT_HALF_MM, math.ceil(750 * t.get("S", 4.096) / region)))
            d, alpha, _, _ = mt.make_full(tt, spec["size_full"])
            reg = np.asarray(Image.fromarray(d, "RGB").resize((region, region), Image.LANCZOS))
            if alpha is not None:
                m = np.asarray(Image.fromarray(alpha, "L").resize((region, region), Image.BOX))
                solid = m >= 128                                  # 0-127 void, 128-255 solid (reg p.36 §12.2)
                o = np.where(solid, 255, 0).astype(np.uint8)
                o = np.pad(o, pad, mode="edge")
                opa[cy:cy + cell, cx:cx + cell] = o[..., None]
                mean = d[alpha >= 128].mean(0) if (alpha >= 128).any() else d.reshape(-1, 3).mean(0)
                reg = np.where(solid[..., None], reg, mean.round().astype(np.uint8))  # void colour = average
        else:  # placeholder / solid finishes: flat colour (missing "rgb" -> KeyError naming it)
            reg = np.broadcast_to(np.array(t["rgb"], np.uint8), (region, region, 3))
        dif[cy:cy + cell, cx:cx + cell] = np.pad(reg, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        # region in UV space (v up): x0, y0 of the region's lower-left corner and its size
        layout[f] = {"udim": t["udim"], "u0": (cx + pad) / ATLAS, "v0": 1 - (cy + pad + region) / ATLAS,
                     "size": region / ATLAS, "px_per_m": round(region / t.get("S", 4.096), 1)
                     if t["kind"] == "full" else None}
        print(f, t["udim"], t["kind"], (cx, cy))
    dn = os.path.join(out, f"T_{addr}_{nnn}_Main_d_1.png")
    on = os.path.join(out, f"T_{addr}_{nnn}_Main_o_1.png")
    # Exclusive creation closes the post-directory-check hardlink/clobber race.
    for pixels, path in ((dif, dn), (opa, on)):
        with open(path, 'xb') as stream:
            Image.fromarray(pixels, "RGB").save(stream, format='PNG', optimize=True)
    with open(os.path.join(out, "npm_atlas.json"), "x", encoding="utf-8") as stream:
        json.dump({"atlas": ATLAS, "cell": cell, "pad": pad, "region": region, "finishes": layout},
                  stream, indent=1)
    for p in (dn, on):
        print(os.path.basename(p), os.path.getsize(p), "bytes")
    print(json.dumps(validate_export(os.path.join(out, 'npm_atlas.json'), dn, on), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
