"""Ground for any site (`dt ground site` / `agr ground site`, #1406): D293 order from a site spec JSON.

Pattern: n/a | new-case: site-spec CLI over dt_ai.geometry.ground_site (no job-specific code).

usage: dt ground site SPEC.json NEW_OUT_DIR

The spec names the DXF (with sha256), boundary handle, project zero (+ source), covers (ID, name, hatch handles;
ID colour = hatch background colour or a stated colour with reason), base ID, relief marks (block / INSERT names /
contour layers) and optional crop box and parameters. Output (new directory, written via NEW_OUT_DIR.partial):
ground-flat.obj (flat-first stage), SM_<site>_Ground.obj (projected + skirt, UDIM = ID), ground-report.json
(every stage, OBJ readback and the project zero check). Exit 0 built (UCX not_run: #1404), 1 findings, 2 refused.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dt_ai.core.heights import export_z_check
from dt_ai.geometry import ground_site as gs

TOP_KEYS = {"site", "dxf", "boundary", "crop_box", "zero", "covers", "base_id", "relief", "params", "note", "unhatched"}
PARAMS = {"cell", "chord", "step", "snap", "relief_tol", "skirt_m", "tex_px", "footprint_min_area", "origin_xy"}


def run(spec_path: Path, out: Path) -> int:
    spec = gs.load_spec(spec_path)
    unknown = set(spec) - TOP_KEYS
    if unknown:
        raise ValueError(f"unknown spec keys {sorted(unknown)}")
    for key in ("site", "dxf", "boundary", "zero", "covers", "base_id", "relief"):
        if key not in spec:
            raise ValueError(f"spec misses {key!r}" + (" (take it from the project or ask, D293)"
                                                        if key == "zero" else ""))
    params = spec.get("params") or {}
    if set(params) - PARAMS:
        raise ValueError(f"unknown params {sorted(set(params) - PARAMS)}")
    site = spec["site"]
    if not isinstance(site, str) or not site or not all(c.isalnum() or c == "_" for c in site):
        raise ValueError(f"site {site!r}: Latin letters, digits and _ only")
    zero = spec["zero"]
    if not isinstance(zero, dict) or not str(zero.get("source", "")).strip():
        raise ValueError("zero needs project_zero_m and source (from the project or the agent asks, D293)")
    dxf = Path(spec["dxf"]["path"])
    if not spec_path.is_absolute():
        spec_path = spec_path.resolve()
    inputs = {spec_path.resolve(), dxf.resolve()}
    out_r, partial = out.resolve(), Path(str(out.resolve()) + ".partial")
    if out_r in inputs or partial in inputs:
        raise ValueError(f"output {out} resolves to an input")
    if out_r.exists() or partial.exists():
        raise ValueError(f"output {out} (or its .partial) exists: give a new versioned path")
    digest = gs.sha256(dxf)
    if digest != spec["dxf"].get("sha256"):
        raise ValueError(f"DXF sha256 {digest} != spec {spec['dxf'].get('sha256')}")

    import ezdxf
    doc = ezdxf.readfile(str(dxf))
    chord = float(params.get("chord", 0.02))
    boundary = gs.boundary_from_dxf(doc, spec["boundary"]["handle"])
    covers = gs.covers_from_dxf(doc, spec["covers"], max(chord, 0.002))
    relief = gs.relief_from_dxf(doc, spec["relief"])
    kw = {k: params[k] for k in params if k in PARAMS and k != "origin_xy"}
    result = gs.build_site(boundary, covers, spec["base_id"], relief, zero["project_zero_m"],
                           origin_xy=params.get("origin_xy"), crop_box=spec.get("crop_box"),
                           unhatched=spec.get("unhatched"), **kw)
    rep = result.report
    rep["site"] = site
    rep["stages"]["sources"].update({"dxf": str(dxf), "dxf_sha256": digest, "spec": str(spec_path),
                                     "spec_sha256": gs.sha256(spec_path), "zero_source": zero["source"]})
    prefix = f"SM_{site}_Ground"
    partial.mkdir(parents=True)
    gs.write_obj(partial / "ground-flat.obj", result.flat, result.slots, prefix, "flat-first stage, Z = level*step")
    gs.write_obj(partial / f"{prefix}.obj", result.mesh, result.slots, prefix,
                 f"local XY = source - {rep['stages']['sources']['origin_xy_m']}; Z = mark - {zero['project_zero_m']}")
    back = gs.read_obj(partial / f"{prefix}.obj")
    rep["readback"] = {k: v for k, v in back.items() if k != "z_values"}
    rep["project_zero_check"] = export_z_check(zero["project_zero_m"], 0.0, back["z_values"]["ground"],
                                               rep["stages"]["zero"]["relief_abs_range_m"],
                                               float(params.get("relief_tol", 0.01))
                                               + 2 * float(params.get("step", 0.006)))  # inset levels
    rep["project_zero_check"]["zero_source"] = zero["source"]
    expected = {f"M_{site}_Ground_{s}": [1000 + int(s[2:4])] for s in result.slots
                if f"M_{site}_Ground_{s}" in back["tiles"]}
    if back["tiles"] != expected:
        rep["findings"].append(f"readback UDIM tiles {back['tiles']} != ID tiles {expected}")
    if rep["project_zero_check"]["status"] != "pass":
        rep["findings"].append("project zero check: " + "; ".join(rep["project_zero_check"]["findings"]))
    status = 1 if len(rep["findings"]) > 1 else 0
    rep["geometry_status"] = "fail" if status else "built"
    rep["passed"] = False
    (partial / "ground-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8", newline="\n")
    os.replace(partial, out_r)
    print(json.dumps({"out": str(out_r), "geometry_status": rep["geometry_status"], "findings": rep["findings"],
                      "triangles": back["triangles"]}, ensure_ascii=False))
    return status


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--help"], ["-h"]) or len(args) != 2:
        print(__doc__)
        return 0 if args in (["--help"], ["-h"]) else 2
    try:
        return run(Path(args[0]), Path(args[1]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
