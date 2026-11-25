"""new-case: TEC26 copy of jobs/KPP1/scripts/make_textures.py (KPP1 recipe, card #559). Generate the KPP1 VPM UDIM texture sets (Diffuse, ERM, Normal) from vpm_textures.json.

Usage: python make_textures.py <spec.json> <new_out_dir>   (TEC26 copy of jobs/KPP1/scripts/make_textures.py)
Writes T_<Address>_{Diffuse|ERM|Normal}_1.<UDIM>.png (VPM naming, reg p.34 §4.3).
- full finishes: 4096 px, S = 4.096 m -> 1 px = 1 mm; patterns are periodic with the finish period P
  so faces shifted by whole periods keep the phase (vpm_uv.pack_uv);
- placeholders: 256 px single colour, no alpha (reg p.31 §3);
- ERM = R emissive (0 here), G roughness, B metallic; Normal = DirectX (G = -Y), reg p.30 §5.1.7;
- alpha only in Diffuse of alpha-cut finishes (0 = void, 255 = solid), reg p.36 §12.
Procedural, deterministic (fixed seeds). Colours are approximate RAL sRGB, not calibrated samples.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
from PIL import Image
from tools.derive.finish_painter import (  # noqa: F401,E402 - replay API
    load_user_texture, make_full, make_user_vjoints, normal_from_height,
    periodic_noise, tile, uv_grid,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def save(arr, path, mode):
    Image.fromarray(arr, mode).save(path, optimize=True)


def main(spec_path, out):
    sys.path.insert(0, HERE)
    import finish_map
    spec = json.load(open(spec_path, encoding="utf-8"))
    finish_map.validate_spec(spec, finish_map.load_kpp())
    finish_map.fresh_out_dir(out, [spec_path, HERE])
    a, fs, ps = spec["address"], spec["size_full"], spec["size_placeholder"]
    name = lambda kind, udim: os.path.join(out, f"T_{a}_{kind}_1.{udim}.png")
    flat_normal = np.broadcast_to(np.array([128, 128, 255], np.uint8), (ps, ps, 3)).copy()
    for f, t in sorted(spec["finishes"].items(), key=lambda kv: kv[1]["udim"]):
        u = t["udim"]
        if t["kind"] == "placeholder":
            save(np.broadcast_to(np.array(t["rgb"], np.uint8), (ps, ps, 3)).copy(), name("Diffuse", u), "RGB")
            erm = np.array([0, round(t["rough"] * 255), round(t["metal"] * 255)], np.uint8)
            save(np.broadcast_to(erm, (ps, ps, 3)).copy(), name("ERM", u), "RGB")
            save(flat_normal, name("Normal", u), "RGB")
        else:
            dif, alpha, erm, nrm = make_full(t, fs)
            if alpha is not None:
                save(np.dstack([dif, alpha]), name("Diffuse", u), "RGBA")
            else:
                save(dif, name("Diffuse", u), "RGB")
            if nrm is None:  # alpha-cut wire elements: flat normal and constant ERM as placeholders
                save(flat_normal, name("Normal", u), "RGB")
                e = np.array([0, round(t["rough"] * 255), round(t["metal"] * 255)], np.uint8)
                save(np.broadcast_to(e, (ps, ps, 3)).copy(), name("ERM", u), "RGB")
            else:
                save(nrm, name("Normal", u), "RGB")
                if (erm == erm[0, 0]).all():  # uniform map -> 256 placeholder (reg p.31 §3; SINTEZ 2.5.3.1)
                    save(np.broadcast_to(erm[0, 0], (ps, ps, 3)).copy(), name("ERM", u), "RGB")
                else:
                    save(erm, name("ERM", u), "RGB")
        print(f, u, t["kind"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
