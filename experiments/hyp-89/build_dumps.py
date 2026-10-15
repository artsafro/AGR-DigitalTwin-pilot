"""Hypothesis #89, step 1: one common engine dump per benchmark model (synthetic reference proxy).

    uv run python experiments/hyp-89/build_dumps.py <out dir>

Same calls as tools/qa/run_benchmark.py step 3, but from the TRACKED spec.json (no etalon needed):
build(Spec.model_validate(spec), BuildInputs.from_object(object)). Inputs are copied to <out>/inputs first
and hashed; the originals are only read.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dt_ai.geometry.from_spec import BuildInputs, build  # noqa: E402
from dt_ai.spec.model import Spec  # noqa: E402

MODELS = {"B01": "bench-b01-box", "B02": "bench-b02-corner-niche", "B02t": "bench-b02t-terrace"}
out = Path(sys.argv[1]).resolve()
(out / "inputs").mkdir(parents=True, exist_ok=False)
hashes = {}
for key, bench in MODELS.items():
    for name in ("spec.json", "object.json"):
        src = ROOT / "benchmark" / bench / name
        dst = out / "inputs" / f"{key}-{name}"
        shutil.copyfile(src, dst)
        hashes[f"{bench}/{name}"] = hashlib.sha256(src.read_bytes()).hexdigest()
    spec = json.loads((out / "inputs" / f"{key}-spec.json").read_text(encoding="utf-8"))
    obj = json.loads((out / "inputs" / f"{key}-object.json").read_text(encoding="utf-8"))
    dump = build(Spec.model_validate(spec), BuildInputs.from_object(obj))
    (out / f"{key}-dump.json").write_text(json.dumps(dump, indent=2), encoding="utf-8")
    print(key, "meshes", len(dump["meshes"]), "helpers", len(dump.get("helpers", [])),
          "tris", sum(len(m["triangles"]) for m in dump["meshes"]))
(out / "input-hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
