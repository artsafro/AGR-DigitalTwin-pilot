"""Roof/parapet seam on K01 (KPP1): welded roof (before) against a separate inset plate (after), issue #1339.

Pattern: roof-inset-plane (docs/domain/patterns/roof-inset-plane.md); evidence runner for the R6 recipe step
"roof membrane and parapet are separate pieces", not a new building node.

    uv run python jobs/KPP1/seam-1339/measure_roof_seam.py --etalon <copy of SM_Kpp_1.fbx> --output <new folder>

Both variants run the whole K01 pipeline of tools/qa/run_benchmark.py (etalon -> spec -> engine -> FBX ->
readback -> checks) on the same etalon copy; only the engine differs:
- `separate` (after): dt_ai.geometry.from_spec as on this branch - the roof inside the parapet is its own plate,
  `plate_gap_m` above the hole and `plate_overlap_m` under the parapet (D038/D039);
- `welded` (before): an in-memory copy of the same engine whose roof inside the parapet is welded to the foot
  of the parapet inner walls (one face set with the body: the seam the PSU275 seal cascade ran through).
  The copy changes exactly one source line (WELD_FROM -> WELD_TO); any other engine text is an error.
Numbers come from the exported file read back (model-readback.json) and the checker report (report.json):
quads, roof-band triangles, T-junctions, open edges / loops, non-manifold, slabs not inset.
Exit 0 when every variant ran to the checker, 2 when a variant stopped or the input is wrong.
Nothing is overwritten: the output folder must not exist and must not contain or be the etalon.
"""
import argparse
import contextlib
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "qa"))

import run_benchmark as rb  # noqa: E402
from dt_ai.geometry import from_spec  # noqa: E402
from roof_parapet_seam import FLAT_M, ROOF_BAND_M, T_TOL_M, measure  # noqa: E402,F401  (#1381: the one seam check)

OBJECT = ROOT / "benchmark/bench-k01-kpp1/object.json"
TOLERANCES = ROOT / "benchmark/bench-k01-kpp1/tolerances.json"
WELD_FROM = '        slabs.append((inner, roof, "the roof", outer))\n'
WELD_TO = "        faces.append((inner, roof, inputs.roof_id, 1))  # #1339 before: roof welded to the parapet foot\n"
VARIANTS = ("welded", "separate")


def welded_engine():
    """The engine module with the roof welded into the parapet foot; one line changed, else RuntimeError."""
    path = Path(from_spec.__file__)
    text = path.read_text(encoding="utf-8")
    if text.count(WELD_FROM) != 1:
        raise RuntimeError(f"{path}: the roof-slab line occurs {text.count(WELD_FROM)} times, expected 1; "
                           "the welded variant would not be the same engine")
    name = "dt_ai.geometry._from_spec_welded_1339"
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    sys.modules[name] = mod                       # dataclasses resolve their module through sys.modules
    exec(compile(text.replace(WELD_FROM, WELD_TO), str(path), "exec"), mod.__dict__)
    return mod


@contextlib.contextmanager
def engine(variant):
    """run_benchmark with the variant's engine (build, BuildInputs and BuildError of the same module)."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; known: {', '.join(VARIANTS)}")
    mod = welded_engine() if variant == "welded" else from_spec
    saved = rb.build, rb.BuildInputs, rb.BuildError
    rb.build, rb.BuildInputs, rb.BuildError = mod.build, mod.BuildInputs, mod.BuildError
    try:
        yield
    finally:
        rb.build, rb.BuildInputs, rb.BuildError = saved


def mesh_check(report):
    """The checker's mesh result (K01 `mesh` check) reduced to the seam facts."""
    mesh = next(c for c in report["checks"] if c.get("id") == "mesh")
    d = mesh["details"]
    return {"status": mesh["status"], "value": mesh["value"], "boundary_edges": d.get("boundary_edges"),
            "open_loops": [{k: lp.get(k) for k in ("kind", "edges", "z", "closed", "allowed", "embed_m", "gap_m")}
                           for lp in d.get("open_loops", [])]}


def run_variant(variant, etalon, out, blender):
    with engine(variant):
        summary = rb.run(etalon, OBJECT, TOLERANCES, out, blender)
    rb.write(out / "summary.json", summary)
    row = {"variant": variant, "steps": summary["steps"], "stopped": summary.get("stopped")}
    if row["stopped"]:
        return row
    spec = json.loads((out / "spec.json").read_text(encoding="utf-8"))
    roof_z = next(lv["elev_m"] for lv in spec["levels"] if lv["name"] == "roof")
    readback = json.loads((out / "model-readback.json").read_text(encoding="utf-8"))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    row.update(roof_z=roof_z, readback=measure(readback, roof_z), mesh=mesh_check(report),
               failed=summary["steps"]["model_check"]["failed"])
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--etalon", type=Path, required=True, help="a copy of the KPP1 v007 VPM FBX (K01 etalon)")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--blender", help="default: TWINQA_BLENDER or pinned Blender 5.1.2 installation")
    args = ap.parse_args(argv)
    etalon, out = args.etalon.resolve(), args.output.resolve()
    if not etalon.is_file():
        print(f"Error: {args.etalon} does not exist", file=sys.stderr)
        return 2
    if out.exists() or out == etalon or out in etalon.parents:
        print(f"Error: {args.output} exists or holds the etalon; use a new folder", file=sys.stderr)
        return 2
    blender = rb.blender_executable(args.blender)
    if not blender:
        print("Error: Blender not found (set TWINQA_BLENDER)", file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    rows = []
    for variant in VARIANTS:
        (out / variant).mkdir()
        rows.append(run_variant(variant, etalon, out / variant, blender))
    rb.write(out / "seam-report.json", {"etalon": str(etalon), "issue": 1339, "variants": rows})
    print(json.dumps(rows, ensure_ascii=False)[:4000])
    return 2 if any(r["stopped"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
