"""Standing #31 harness: inputs -> metre dumps (xview_gate NPZ format). Read-only on every input.

FBX: repo dump tools/blender/xview_dump.py through dt_ai.core.blender_runner, then xview_gate.to_metres.
NPZ in dump format: copied as is. F1 (vertices/faces arrays): converted to one part, location 0.
Usage: uv run python dump.py [--inputs C:/x/ev_t_193a0887/inputs] [--out C:/x/ev_t_193a0887/dumps-v002]
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

from dt_ai.core.blender_runner import run_blender
from dt_ai.ops import xview_gate
from dt_ai.ops.xview_gate import Part

HERE = Path(__file__).resolve().parent


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="C:/x/ev_t_193a0887/inputs")
    ap.add_argument("--out", default="C:/x/ev_t_193a0887/dumps-v002")
    a = ap.parse_args()
    src, out = Path(a.inputs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    frozen = {ln.split()[1].lstrip("*"): ln.split()[0] for ln in (HERE / "inputs.sha256").read_text().splitlines() if ln}
    rows = []
    for name, h in sorted(frozen.items()):
        p = src / name
        if sha(p) != h:
            raise SystemExit(f"hash mismatch: {p}")
        dst = out / (p.stem.replace("_raw", "") + ".npz")
        t0 = time.time()
        info = {}
        if dst.exists():
            info["reused"] = True
        elif p.suffix.lower() == ".fbx":
            tmp = out / (p.stem + ".tmp")
            tmp.mkdir(exist_ok=True)
            npz, man, blend = tmp / "parts.npz", tmp / "manifest.json", tmp / "scene.blend"
            run_blender(HERE / "fbx_to_blend.py", [p.resolve(), blend], outputs=[blend], timeout=3600,
                        log_path=tmp / "fbx_to_blend.log")
            dump = run_blender(xview_gate.DUMP_SCRIPT, [blend, npz, man], output_json=man, outputs=[npz],
                               timeout=3600, log_path=tmp / "blender.log")
            parts, units = xview_gate.to_metres(xview_gate.load_npz(npz), dump)
            xview_gate.save_npz(dst, parts)
            info = {"units": units, "dropped": dump.get("dropped", []), "blender": dump.get("blender")}
        else:
            with np.load(p, allow_pickle=False) as z:
                keys = set(z.files)
                if "names" in keys:      # dump format; F3 also carries parent_face / parent_vertex (dropped)
                    parts = [Part(str(n), np.asarray(z[f"v{i}"], dtype=np.float64),
                                  xview_gate._faces(z[f"lt{i}"], z[f"lv{i}"], where=str(n)),
                                  np.asarray(z[f"loc{i}"], dtype=np.float64))
                             for i, n in enumerate(z["names"].tolist())]
                else:   # F1 r1 pilot arrays
                    parts = [Part("SM_SIL13_Ground", np.asarray(z["vertices"], dtype=np.float64),
                                  tuple(tuple(int(i) for i in f) for f in z["faces"]), np.zeros(3))]
            xview_gate.save_npz(dst, parts)
        rows.append({"id": p.stem.split("_")[0], "input": name, "input_sha256": h, "dump": dst.name,
                     "dump_sha256": sha(dst), "seconds": round(time.time() - t0, 1), **info})
        print(rows[-1]["id"], rows[-1]["dump_sha256"][:12], rows[-1]["seconds"], flush=True)
    (out / "dumps.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "dumps.sha256").write_text("".join(f"{r['dump_sha256']} *{r['dump']}\n" for r in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
