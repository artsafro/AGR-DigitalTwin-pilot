"""KPP1 #1230 texture sets for the offline rerun: VPM UDIM maps (Diffuse/ERM/Normal) and the NPM 2048 atlas.

Pattern: new-case: procedural finish maps for the offline KPP1 rerun (one UDIM tile per used finish, sequential from
1001; colours / roughness / metallic and the joint periods from jobs/KPP1/scripts/vpm_textures.json, which are
approximate RAL sRGB, not calibrated).

    uv run python jobs/KPP1/rerun-1230/make_textures.py <out_dir>

VPM: T_Kpp_1_Diffuse_1.<UDIM>.png 2048 px for S = 2.048 m (1000 px/m, reg band 512..1706) with the joint grid
of the finish period P (dark 3 px lines) or one colour for smooth finishes; ERM and Normal are 256 px one-colour
placeholders (ERM: R 0 emissive, G roughness, B metallic; Normal flat 128,128,255), density-exempt.
NPM: T_Kpp_1_001_Main_d_1.png, one 2048 RGB atlas, 4 x 4 cells of 512 px, one cell per finish with 8 px padding;
the cell stands for the same S as the VPM tile. Writes textures.json (finish -> udim, cell). Fail-closed: an
unknown finish name or a finish list longer than 16 cells -> SystemExit; out_dir equal to the script dir -> exit 4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SPEC = HERE.parents[0] / "scripts" / "vpm_textures.json"
FINISHES = json.loads((HERE / "finishes.json").read_text(encoding="utf-8"))
ADDRESS = "Kpp_1"
S_M, SIZE, SMALL, CELL, NPM_SIZE, NPM_PAD = 2.048, 2048, 256, 512, 2048, 8
JOINT_PX = 3


def finish_table():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))["finishes"]
    order = FINISHES["order"]
    if len(order) > (NPM_SIZE // CELL) ** 2:
        raise SystemExit(f"{len(order)} finishes do not fit the {NPM_SIZE // CELL}^2 NPM atlas cells")
    out = {}
    for i, name in enumerate(order):
        if name not in spec:
            raise SystemExit(f"finish {name!r} not in {SPEC.name}")
        t = spec[name]
        period = t["P"] if t["kind"] == "full" else None
        out[name] = {"udim": 1001 + i, "cell": [i % (NPM_SIZE // CELL), i // (NPM_SIZE // CELL)],
                     "rgb": t["rgb"], "rough": t["rough"], "metal": t["metal"], "P": period,
                     "pattern": t.get("pattern") if period else None}
    return out


def diffuse(t, size, metres):
    img = np.empty((size, size, 3), np.uint8)
    img[:] = t["rgb"]
    if t["P"]:
        px = np.arange(size) * metres / size
        dark = (np.array(t["rgb"]) * 0.55).astype(np.uint8)
        jw = JOINT_PX / 1000.0                                 # 3 mm joint
        for axis, per in enumerate(t["P"]):
            if per >= metres:
                continue
            mask = (px % per) < max(jw, metres / size)
            if axis == 0:
                img[:, mask] = dark
            else:
                img[mask[::-1], :] = dark
    return img


def main(argv):
    if len(argv) != 1:
        raise SystemExit(__doc__)
    out = Path(argv[0])
    if out.resolve() == HERE:
        print("output dir resolves to the script dir", file=sys.stderr)
        return 4
    out.mkdir(parents=True, exist_ok=True)
    table = finish_table()
    atlas = np.zeros((NPM_SIZE, NPM_SIZE, 3), np.uint8)
    for name, t in table.items():
        u = t["udim"]
        Image.fromarray(diffuse(t, SIZE, S_M)).save(out / f"T_{ADDRESS}_Diffuse_1.{u}.png", optimize=True)
        erm = np.empty((SMALL, SMALL, 3), np.uint8)
        erm[:] = (0, round(t["rough"] * 255), round(t["metal"] * 255))
        Image.fromarray(erm).save(out / f"T_{ADDRESS}_ERM_1.{u}.png")
        nrm = np.empty((SMALL, SMALL, 3), np.uint8)
        nrm[:] = (128, 128, 255)
        Image.fromarray(nrm).save(out / f"T_{ADDRESS}_Normal_1.{u}.png")
        cx, cy = t["cell"]
        cell = diffuse(t, CELL, S_M)
        y0 = NPM_SIZE - (cy + 1) * CELL                         # image rows go down; UV v goes up
        atlas[y0:y0 + CELL, cx * CELL:(cx + 1) * CELL] = cell
    Image.fromarray(atlas).save(out / f"T_{ADDRESS}_001_Main_d_1.png", optimize=True)
    meta = {"address": ADDRESS, "S_m": S_M, "size": SIZE, "npm": {"size": NPM_SIZE, "cell": CELL, "pad": NPM_PAD},
            "finishes": table, "note": "approximate RAL sRGB from jobs/KPP1/scripts/vpm_textures.json, not calibrated"}
    (out / "textures.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps({"finishes": len(table), "vpm_png": 3 * len(table), "npm_atlas": 1}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
