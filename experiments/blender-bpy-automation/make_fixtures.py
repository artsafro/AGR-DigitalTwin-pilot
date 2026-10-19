"""Engine dumps of B01/B02/B02t (from_spec) plus synthetic defect variants (SYNTHETIC, not real objects).

    uv run python experiments/blender-bpy-automation/make_fixtures.py <out dir>

Defects (each a copy of the clean dump):
  flip1   - one wall polygon of `body` reversed (inconsistent winding)
  flipall - every polygon of `body` reversed (consistent but inward)
  cross   - extra mesh `probe`: a closed 0.4 m box whose centre sits on a facade wall plane (transverse crossing)
  selfx   - the same box appended into `body` itself (self-intersection of one mesh)
Also runs the current checker (checks.run) on every variant: the baseline.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.geometry.from_spec import BuildInputs, build  # noqa: E402
from dt_ai.spec.model import Spec  # noqa: E402
from twinqa.geometry import checks  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402

BENCHES = ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]


def box(c, h):
    v = [[c[0] + sx * h, c[1] + sy * h, c[2] + sz * h] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    f = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    return v, f


def mesh_of(name, v, polys, mid=1):
    tris, mids = [], []
    for p in polys:
        for k in range(1, len(p) - 1):
            tris.append([p[0], p[k], p[k + 1]])
            mids.append(mid)
    return {"name": name, "vertices": v, "triangles": tris, "material_ids": mids,
            "polygon_sizes": [len(p) for p in polys], "polygons": polys}


def wall_point(body):
    """Centre of the largest vertical polygon of body (a facade wall)."""
    v = np.asarray(body["vertices"])
    best = None
    for i, p in enumerate(body["polygons"]):
        pts = v[p]
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        a = np.linalg.norm(n)
        if a > 0 and abs(n[2]) / a < 1e-6 and (best is None or a > best[0]):
            best = (a, i, pts.mean(axis=0))
    return best[1], best[2]


def variants(dump):
    out = {"clean": dump}
    body = dump["meshes"][0]
    wi, c = wall_point(body)
    d = json.loads(json.dumps(dump))
    b = d["meshes"][0]
    b["polygons"][wi] = b["polygons"][wi][::-1]
    out["flip1"] = d
    d = json.loads(json.dumps(dump))
    b = d["meshes"][0]
    b["polygons"] = [p[::-1] for p in b["polygons"]]
    out["flipall"] = d
    v, f = box(c.tolist(), 0.2)
    d = json.loads(json.dumps(dump))
    d["meshes"].append(mesh_of("probe", v, f))
    out["cross"] = d
    d = json.loads(json.dumps(dump))
    b = d["meshes"][0]
    n0 = len(b["vertices"])
    extra = mesh_of("probe", v, [[n0 + i for i in q] for q in f], mid=b["material_ids"][0])
    for k in ("triangles", "material_ids", "polygon_sizes", "polygons"):
        b[k] = b[k] + extra[k]
    b["vertices"] = b["vertices"] + v
    out["selfx"] = d
    return out


def baseline(dump, spec, tol):
    t = time.perf_counter()
    rep = checks.run(from_dump(dump), from_dump(dump), spec, tol)
    dt = time.perf_counter() - t
    bad = [c["id"] for c in rep["checks"] if c["status"] != "pass"]
    return {"passed": rep["passed"], "not_pass": bad, "s": round(dt, 3)}


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for bench in BENCHES:
        d = ROOT / "benchmark" / bench
        spec = Spec.model_validate(json.loads((d / "spec.json").read_text(encoding="utf-8")))
        obj = json.loads((d / "object.json").read_text(encoding="utf-8"))
        tol = json.loads((d / "tolerances.json").read_text(encoding="utf-8"))["geometry"]
        dump = build(spec, BuildInputs.from_object(obj))
        for name, v in variants(dump).items():
            p = out / f"{bench}__{name}.json"
            p.write_text(json.dumps(v), encoding="utf-8")
            summary[p.stem] = baseline(v, spec, tol)
    (out / "baseline.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for k, v in summary.items():
        print(k, v)


if __name__ == "__main__":
    main(sys.argv[1])
